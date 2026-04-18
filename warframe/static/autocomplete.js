function setupAutocomplete(input, api, onSelect) {
    input.setAttribute('autocomplete', 'off');

    const wrap = document.createElement('div');
    wrap.className = 'autocomplete-wrap';
    wrap.style.position = 'relative';
    wrap.style.flex = '1';
    wrap.style.minWidth = '200px';
    wrap.style.width = 'calc(100% - 320px)';
    input.parentNode.insertBefore(wrap, input);
    wrap.appendChild(input);
    input.style.width = '100%';

    const dropdown = document.createElement('ul');
    dropdown.className = 'autocomplete-dropdown';
    dropdown.style.cssText = 'position:absolute;top:100%;left:0;right:0;background:#2a2a2a;border:1px solid #444;border-top:none;list-style:none;margin:0;padding:0;max-height:250px;overflow-y:auto;z-index:1000;display:none';
    wrap.appendChild(dropdown);

    let currentController = null;

    async function search(query) {
        if (currentController) currentController.abort();
        currentController = new AbortController();

        try {
            const url = api + encodeURIComponent(query);
            const res = await fetch(url, { signal: currentController.signal });
            const items = await res.json();
            render(items);
        } catch (e) {
            if (e.name !== 'AbortError') console.error('Autocomplete error:', e);
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
            li.onmouseover = () => {
                Array.from(dropdown.children).forEach(c => c.style.background = '');
                li.style.background = '#444';
            };
            li.onmousedown = (e) => {
                e.preventDefault();
                select(item, false);
            };
            dropdown.appendChild(li);
        });
        dropdown.style.display = 'block';
    }

    function select(value, shouldSubmit = true) {
        let current = input.value;
        const lastComma = current.lastIndexOf(',');
        if (lastComma >= 0) {
            input.value = current.slice(0, lastComma + 1).trim() + ' ' + value;
        } else {
            input.value = value;
        }
        dropdown.style.display = 'none';
        if (shouldSubmit && onSelect) onSelect(value);
    }

    let debounceTimer;
    input.addEventListener('input', () => {
        clearTimeout(debounceTimer);
        let query = input.value.trim();
        const lastComma = query.lastIndexOf(',');
        if (lastComma >= 0) query = query.slice(lastComma + 1).trim();
        if (query.length < 1) {
            dropdown.style.display = 'none';
            return;
        }
        debounceTimer = setTimeout(() => search(query), 150);
    });

    input.addEventListener('blur', () => setTimeout(() => dropdown.style.display = 'none', 150));
    input.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
            const items = Array.from(dropdown.children);
            let idx = items.findIndex(li => li.style.background !== '');
            if (idx >= 0) {
                e.preventDefault();
                select(items[idx].textContent, false);
            }
            return;
        }
        if (e.key === 'Escape') {
            dropdown.style.display = 'none';
            return;
        }
        const items = Array.from(dropdown.children);
        if (!items.length) return;
        let idx = items.findIndex(li => li.style.background !== '');
        if (e.key === 'ArrowDown') {
            e.preventDefault();
            idx = idx < 0 ? 0 : Math.min(idx + 1, items.length - 1);
        } else if (e.key === 'ArrowUp') {
            e.preventDefault();
            idx = idx < 0 ? items.length - 1 : Math.max(idx - 1, 0);
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