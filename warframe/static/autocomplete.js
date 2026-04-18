function setupAutocomplete(input, api, onSelect) {
    const wrap = document.createElement('div');
    wrap.className = 'autocomplete-wrap';
    wrap.style.position = 'relative';
    input.parentNode.insertBefore(wrap, input);
    wrap.appendChild(input);

    const dropdown = document.createElement('ul');
    dropdown.className = 'autocomplete-dropdown';
    dropdown.style.cssText = 'position:absolute;top:100%;left:0;right:0;background:#2a2a2a;border:1px solid #444;border-top:none;list-style:none;margin:0;padding:0;max-height:250px;overflow-y:auto;z-index:1000;display:none';
    wrap.appendChild(dropdown);

    let currentRequest = null;

    async function search(query) {
        if (currentRequest) currentRequest.cancel();
        currentRequest = { cancelled: false };

        try {
            const url = api + encodeURIComponent(query);
            const res = await fetch(url);
            const items = await res.json();
            if (currentRequest.cancelled) return;
            render(items);
        } catch (e) {
            console.error('Autocomplete error:', e);
        }
    }

    function render(items) {
        dropdown.innerHTML = '';
        if (!items.length) {
            dropdown.style.display = 'none';
            return;
        }
        items.forEach(item => {
            const li = document.createElement('li');
            li.textContent = item;
            li.style.cssText = 'padding:0.5rem 0.75rem;cursor:pointer;color:#fff';
            li.onmouseenter = () => Array.from(dropdown.children).forEach(c => c.style.background = '');
            li.onmousedown = (e) => {
                e.preventDefault();
                select(item);
            };
            li.onmouseover = () => li.style.background = '#444';
            dropdown.appendChild(li);
        });
        dropdown.style.display = 'block';
    }

    function select(value) {
        input.value = value;
        dropdown.style.display = 'none';
        if (onSelect) onSelect(value);
    }

    let debounceTimer;
    input.addEventListener('input', () => {
        clearTimeout(debounceTimer);
        const query = input.value.trim();
        if (query.length < 1) {
            dropdown.style.display = 'none';
            return;
        }
        debounceTimer = setTimeout(() => search(query), 150);
    });

    input.addEventListener('blur', () => setTimeout(() => dropdown.style.display = 'none', 150));
    input.addEventListener('keydown', (e) => {
        const items = Array.from(dropdown.children);
        if (!items.length) return;
        let idx = items.findIndex(li => li.style.background);
        if (e.key === 'ArrowDown') {
            e.preventDefault();
            idx = idx < 0 ? 0 : Math.min(idx + 1, items.length - 1);
        } else if (e.key === 'ArrowUp') {
            e.preventDefault();
            idx = idx < 0 ? items.length - 1 : Math.max(idx - 1, 0);
        } else if (e.key === 'Enter' && idx >= 0) {
            e.preventDefault();
            select(items[idx].textContent);
            return;
        } else return;
        items.forEach(li => li.style.background = '');
        if (items[idx]) {
            items[idx].style.background = '#444';
            items[idx].scrollIntoView({ block: 'nearest' });
        }
    });
}

document.addEventListener('DOMContentLoaded', () => {
    const qInput = document.querySelector('input[name="q"]');
    if (qInput) {
        setupAutocomplete(qInput, WEB_ROOT + '/api/suggest-items?q=', (item) => {
            qInput.form.submit();
        });
    }

    const drawer = document.getElementById('drawer');
    const mtInput = drawer?.querySelector('input[name="mission_type"]');
    if (mtInput) {
        setupAutocomplete(mtInput, WEB_ROOT + '/api/suggest-mission-types?q=', () => {
            mtInput.form.submit();
        });
    }

    document.querySelectorAll('table.sortable').forEach(table => {
        table.querySelectorAll('th').forEach((th, idx) => {
            th.style.cursor = 'pointer';
            th.addEventListener('click', () => sortTable(table, idx));
        });
    });

    const missionTypeInput = drawer?.querySelector('input[name="mission_type"]');
    if (missionTypeInput?.value.trim()) {
        drawer.classList.add('open');
    } else if (localStorage.getItem('drawerOpen') === 'true') {
        drawer?.classList.add('open');
    }
});

function toggleDrawer() {
    const drawer = document.getElementById('drawer');
    drawer.classList.toggle('open');
    localStorage.setItem('drawerOpen', drawer.classList.contains('open'));
}

function sortTable(table, colIndex) {
    const tbody = table.tBodies[0];
    const rows = Array.from(tbody.querySelectorAll('tr'));
    const th = table.querySelectorAll('th')[colIndex];

    let state;
    if (th.classList.contains('asc')) state = 'desc';
    else if (th.classList.contains('desc')) state = 'unsorted';
    else state = 'asc';

    table.querySelectorAll('th').forEach(h => h.classList.remove('asc', 'desc'));
    if (state !== 'unsorted') th.classList.add(state);

    const header = rows.shift();
    if (state === 'unsorted') {
        rows.unshift(header);
        rows.forEach(row => tbody.appendChild(row));
    } else {
        const asc = state === 'asc';
        rows.sort((a, b) => {
            const aVal = a.cells[colIndex].textContent.trim();
            const bVal = b.cells[colIndex].textContent.trim();
            const aNum = parseFloat(aVal), bNum = parseFloat(bVal);
            if (!isNaN(aNum) && !isNaN(bNum)) return asc ? aNum - bNum : bNum - aNum;
            return asc ? aVal.localeCompare(bVal) : bVal.localeCompare(aVal);
        });
        rows.unshift(header);
        rows.forEach(row => tbody.appendChild(row));
    }
}