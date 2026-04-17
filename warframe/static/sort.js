document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('table.sortable').forEach(table => {
        table.querySelectorAll('th').forEach((th, idx) => {
            th.style.cursor = 'pointer';
            th.addEventListener('click', () => sortTable(table, idx));
        });
    });

    const drawer = document.getElementById('drawer');
    const missionTypeInput = drawer.querySelector('input[name="mission_type"]');
    if (missionTypeInput && missionTypeInput.value.trim()) {
        drawer.classList.add('open');
    } else if (localStorage.getItem('drawerOpen') === 'true') {
        drawer.classList.add('open');
    }

    loadSuggestions();
});

let suggestionsLoaded = false;

async function loadSuggestions() {
    if (suggestionsLoaded) return;
    suggestionsLoaded = true;

    try {
        const itemsRes = await fetch(WEB_ROOT + '/api/suggest-items?q=');
        const items = await itemsRes.json();
        const itemsList = document.getElementById('items-list');
        items.forEach(item => {
            const opt = document.createElement('option');
            opt.value = item;
            itemsList.appendChild(opt);
        });

        const missionTypesRes = await fetch(WEB_ROOT + '/api/suggest-mission-types?q=');
        const missionTypes = await missionTypesRes.json();
        const missionTypesList = document.getElementById('mission-types-list');
        missionTypes.forEach(mt => {
            const opt = document.createElement('option');
            opt.value = mt;
            missionTypesList.appendChild(opt);
        });
    } catch (e) {
        console.error('Failed to load suggestions:', e);
    }
}

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
    if (th.classList.contains('asc')) {
        state = 'desc';
    } else if (th.classList.contains('desc')) {
        state = 'unsorted';
    } else {
        state = 'asc';
    }

    table.querySelectorAll('th').forEach(h => h.classList.remove('asc', 'desc'));
    if (state !== 'unsorted') {
        th.classList.add(state);
    }

    const header = rows.shift();

    if (state === 'unsorted') {
        rows.unshift(header);
        rows.forEach(row => tbody.appendChild(row));
    } else {
        const asc = state === 'asc';
        rows.sort((a, b) => {
            const aVal = a.cells[colIndex].textContent.trim();
            const bVal = b.cells[colIndex].textContent.trim();
            const aNum = parseFloat(aVal);
            const bNum = parseFloat(bVal);

            if (!isNaN(aNum) && !isNaN(bNum)) {
                return asc ? aNum - bNum : bNum - aNum;
            }
            return asc ? aVal.localeCompare(bVal) : bVal.localeCompare(aVal);
        });

        rows.unshift(header);
        rows.forEach(row => tbody.appendChild(row));
    }
}