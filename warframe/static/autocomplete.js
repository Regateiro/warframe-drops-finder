const DROPDOWN_STYLE = 'position:absolute;top:100%;left:0;right:0;background:#2a2a2a;border:1px solid #444;border-top:none;list-style:none;margin:0;padding:0;max-height:250px;overflow-y:auto;z-index:1000;display:none';
const ITEM_STYLE = 'padding:0.5rem 0.75rem;cursor:pointer;color:#fff';

function setupAutocomplete(input, api) {
    input.autocomplete = 'off';
    let controller = null;

    const dropdown = document.createElement('ul');
    dropdown.style.cssText = DROPDOWN_STYLE;
    input.parentNode.appendChild(dropdown);

    function search(query) {
        if (controller) controller.abort();
        controller = new AbortController();
        fetch(api + encodeURIComponent(query), { signal: controller.signal })
            .then(r => r.json())
            .then(show)
            .catch(e => { if (e.name !== 'AbortError') console.error(e); });
    }

    function show(items) {
        dropdown.innerHTML = items.length ? '' : (dropdown.style.display = 'none');
        items.forEach(item => {
            const li = document.createElement('li');
            li.textContent = item;
            li.style.cssText = ITEM_STYLE;
            li.onmouseover = () => highlight(li);
            li.onmousedown = (e) => { e.preventDefault(); select(item, false); };
            dropdown.appendChild(li);
        });
        if (items.length) dropdown.style.display = 'block';
    }

    function highlight(li) {
        Array.from(dropdown.children).forEach(c => c.style.background = '');
        li.style.background = '#444';
    }

    function select(value, doSubmit = true) {
        const last = input.value.lastIndexOf(',');
        input.value = last >= 0 ? input.value.slice(0, last + 1).trim() + ' ' + value : value;
        dropdown.style.display = 'none';
        if (doSubmit) input.form.submit();
    }

    function handleInput() {
        let q = input.value.trim();
        const last = q.lastIndexOf(',');
        q = last >= 0 ? q.slice(last + 1).trim() : q;
        if (!q) return dropdown.style.display = 'none';
        clearTimeout(input._timer);
        input._timer = setTimeout(() => search(q), 150);
    }

    function handleKey(e) {
        const items = Array.from(dropdown.children);
        if (e.key === 'Enter') {
            if (items.length && dropdown.style.display === 'block') {
                const idx = items.findIndex(li => li.style.background !== '');
                if (idx >= 0) { e.preventDefault(); select(items[idx].textContent, false); }
            }
            return;
        }
        if (e.key === 'Escape') { dropdown.style.display = 'none'; return; }
        if (!items.length || dropdown.style.display !== 'block') return;

        let idx = items.findIndex(li => li.style.background !== '');
        if (e.key === 'ArrowDown') idx = idx < 0 ? 0 : Math.min(idx + 1, items.length - 1);
        else if (e.key === 'ArrowUp') idx = idx < 0 ? items.length - 1 : Math.max(idx - 1, 0);
        else return;
        e.preventDefault();
        items.forEach(li => li.style.background = '');
        items[idx] && (items[idx].style.background = '#444');
    }

    input.addEventListener('input', handleInput);
    input.addEventListener('blur', () => setTimeout(() => dropdown.style.display = 'none', 150));
    input.addEventListener('keydown', handleKey);
}

document.addEventListener('DOMContentLoaded', () => {
    const qInput = document.querySelector('input[name="q"]');
    if (qInput) setupAutocomplete(qInput, WEB_ROOT + '/api/suggest-items?q=');

    const drawer = document.getElementById('drawer');
    const mtInput = drawer?.querySelector('input[name="mission_type"]');
    if (mtInput) setupAutocomplete(mtInput, WEB_ROOT + '/api/suggest-mission-types?q=');

    document.querySelectorAll('table.sortable').forEach(table => {
        table.querySelectorAll('th').forEach((th, i) => th.onclick = () => sortTable(table, i));
    });

    if (drawer) {
        const open = mtInput?.value.trim() || localStorage.getItem('drawerOpen') === 'true';
        if (open) drawer.classList.add('open');
    }
});

function toggleDrawer() {
    const drawer = document.getElementById('drawer');
    drawer.classList.toggle('open');
    localStorage.setItem('drawerOpen', drawer.classList.contains('open'));
}

function sortTable(table, col) {
    const tbody = table.tBodies[0];
    const rows = Array.from(tbody.querySelectorAll('tr'));
    const th = table.querySelectorAll('th')[col];
    let state = th.classList.contains('asc') ? 'desc' : th.classList.contains('desc') ? 'unsorted' : 'asc';
    table.querySelectorAll('th').forEach(h => h.classList.remove('asc', 'desc'));
    if (state !== 'unsorted') th.classList.add(state);
    const header = rows.shift();
    if (state === 'unsorted') { rows.unshift(header); rows.forEach(r => tbody.appendChild(r)); return; }
    rows.sort((a, b) => {
        const av = a.cells[col].textContent.trim(), bv = b.cells[col].textContent.trim();
        const an = parseFloat(av), bn = parseFloat(bv);
        return isNaN(an) || isNaN(bn)
            ? (state === 'asc' ? av.localeCompare(bv) : bv.localeCompare(av))
            : (state === 'asc' ? an - bn : bn - an);
    });
    rows.unshift(header); rows.forEach(r => tbody.appendChild(r));
}