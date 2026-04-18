document.addEventListener('DOMContentLoaded', () => {
    // Make all tables with class 'sortable' sortable by clicking headers
    document.querySelectorAll('table.sortable').forEach(table => {
        table.querySelectorAll('th').forEach((th, idx) => {
            th.style.cursor = 'pointer';
            th.addEventListener('click', () => sortTable(table, idx));
        });
    });

    // Restore drawer state from URL param or localStorage
    const drawer = document.getElementById('drawer');
    const missionTypeInput = drawer.querySelector('input[name="mission_type"]');
    if (missionTypeInput && missionTypeInput.value.trim()) {
        drawer.classList.add('open');
    } else if (localStorage.getItem('drawerOpen') === 'true') {
        drawer.classList.add('open');
    }

    // Load dropdown suggestions for autocomplete
    loadMissionTypeSuggestions();
});

// Track if suggestions have already been loaded (prevent duplicate fetches)
let suggestionsLoaded = false;

/**
 * Load mission type and item suggestions for comboboxes.
 * Called once on page load with cache-busting query param.
 */
async function loadMissionTypeSuggestions() {
    if (suggestionsLoaded) return;
    suggestionsLoaded = true;

    const missionTypesList = document.getElementById('mission-types-list');
    const itemsList = document.getElementById('items-list');

    try {
        // Fetch mission types (filter for 'A' to get all types)
        const cacheBust = Date.now();
        const mtypes = await fetch(WEB_ROOT + '/api/suggest-mission-types?q=A&_=' + cacheBust).then(r => r.json());
        mtypes.forEach(mt => {
            const opt = document.createElement('option');
            opt.value = mt;
            missionTypesList.appendChild(opt);
        });

        // Fetch all items (filter for '0' to get all items)
        const items = await fetch(WEB_ROOT + '/api/suggest-items?q=0&_=' + cacheBust).then(r => r.json());
        items.forEach(item => {
            const opt = document.createElement('option');
            opt.value = item;
            itemsList.appendChild(opt);
        });

        console.log('Loaded suggestions:', mtypes.length, 'types,', items.length, 'items');
    } catch (e) {
        console.error('Failed to load suggestions:', e);
    }
}

/**
 * Toggle the drawer (filter panel) open/closed.
 * Persists state to localStorage.
 */
function toggleDrawer() {
    const drawer = document.getElementById('drawer');
    drawer.classList.toggle('open');
    localStorage.setItem('drawerOpen', drawer.classList.contains('open'));
}

/**
 * Sort a table by clicking its header cells.
 * Cycles through asc -> desc -> unsorted on each click.
 *
 * @param {HTMLTableElement} table - The table to sort
 * @param {number} colIndex - Column index to sort by
 */
function sortTable(table, colIndex) {
    const tbody = table.tBodies[0];
    const rows = Array.from(tbody.querySelectorAll('tr'));
    const th = table.querySelectorAll('th')[colIndex];

    // Determine next sort state: asc -> desc -> unsorted -> asc -> ...
    let state;
    if (th.classList.contains('asc')) {
        state = 'desc';
    } else if (th.classList.contains('desc')) {
        state = 'unsorted';
    } else {
        state = 'asc';
    }

    // Clear previous sort indicators from all headers
    table.querySelectorAll('th').forEach(h => h.classList.remove('asc', 'desc'));
    if (state !== 'unsorted') {
        th.classList.add(state);
    }

    // Preserve header row during sort
    const header = rows.shift();

    // If unsorted, restore original order by sorting on the first column (#)
    if (state === 'unsorted') {
        colIndex = 0;
    }

    const asc = state === 'asc';
    rows.sort((a, b) => {
        const aVal = a.cells[colIndex].textContent.trim();
        const bVal = b.cells[colIndex].textContent.trim();
        const aNum = parseFloat(aVal);
        const bNum = parseFloat(bVal);

        // Numeric comparison for numbers, string comparison otherwise
        if (!isNaN(aNum) && !isNaN(bNum)) {
            return asc ? aNum - bNum : bNum - aNum;
        }
        return asc ? aVal.localeCompare(bVal) : bVal.localeCompare(aVal);
    });

    rows.unshift(header);
    rows.forEach(row => tbody.appendChild(row));
}