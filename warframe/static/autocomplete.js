// CSS constants for dropdown appearance
const DROPDOWN_STYLE = 'position:absolute;top:100%;left:0;right:0;background:#2a2a2a;border:1px solid #444;border-top:none;list-style:none;margin:0;padding:0;max-height:250px;overflow-y:auto;z-index:1000;display:none';
const ITEM_STYLE = 'padding:0.5rem 0.75rem;cursor:pointer;color:#fff';


/**
 * Set up autocomplete on an input element.
 * @param {HTMLInputElement} input - The input element to attach to.
 * @param {string} api - The API endpoint URL for suggestions.
 */
function setupAutocomplete(input, api) {
    // Disable default browser autocomplete
    input.autocomplete = 'off';

    // AbortController for canceling pending requests
    let controller = null;

    // Wrap input in relative container so dropdown positions correctly
    const wrapper = document.createElement('div');
    wrapper.style.cssText = 'position: relative; flex: 1; width: 100%;';
    input.parentNode.insertBefore(wrapper, input);
    wrapper.appendChild(input);

    // Create dropdown UL element
    const dropdown = document.createElement('ul');
    dropdown.style.cssText = DROPDOWN_STYLE;
    wrapper.appendChild(dropdown);

    /**
     * Fetch suggestions from API.
     * Uses AbortController to cancel stale requests on new input.
     */
    function search(query) {
        if (controller) controller.abort();
        controller = new AbortController();
        fetch(api + encodeURIComponent(query), { signal: controller.signal })
            .then(r => r.json())
            .then(show)
            .catch(e => { if (e.name !== 'AbortError') console.error(e); });
    }

    /** Render suggestions in dropdown. */
    function show(items) {
        dropdown.innerHTML = '';
        if (!items.length) {
            dropdown.style.display = 'none';
            return;
        }
        items.forEach(item => {
            const li = document.createElement('li');
            li.textContent = item;
            li.style.cssText = ITEM_STYLE;
            li.onmouseover = () => highlight(li);
            // Prevent blur from firing before selection
            li.onmousedown = (e) => { e.preventDefault(); select(item, false); };
            dropdown.appendChild(li);
        });
        dropdown.style.display = 'block';
    }

    /** Highlight item on hover. */
    function highlight(li) {
        Array.from(dropdown.children).forEach(c => c.style.background = '');
        li.style.background = '#444';
    }

    /** Select an item from dropdown. */
    function select(value, doSubmit = true) {
        // Handle comma-separated values - append to last or create new
        const last = input.value.lastIndexOf(',');
        input.value = last >= 0 ? input.value.slice(0, last + 1).trim() + ' ' + value : value;
        dropdown.style.display = 'none';
        if (doSubmit) input.form.submit();
    }

    /** Handle input event with debounce. */
    function handleInput() {
        let q = input.value.trim();
        // Get the last comma-separated value to search
        const last = q.lastIndexOf(',');
        q = last >= 0 ? q.slice(last + 1).trim() : q;
        if (!q) return dropdown.style.display = 'none';
        // Debounce requests by 150ms
        clearTimeout(input._timer);
        input._timer = setTimeout(() => search(q), 150);
    }

    /** Handle keyboard navigation in dropdown. */
    function handleKey(e) {
        const items = Array.from(dropdown.children);

        // Enter - select highlighted item
        if (e.key === 'Enter') {
            if (items.length && dropdown.style.display === 'block') {
                const idx = items.findIndex(li => li.style.background !== '');
                if (idx >= 0) { e.preventDefault(); select(items[idx].textContent, false); }
            }
            return;
        }
        // Escape - close dropdown
        if (e.key === 'Escape') { dropdown.style.display = 'none'; return; }
        if (!items.length || dropdown.style.display !== 'block') return;

        // Arrow keys - navigate
        let idx = items.findIndex(li => li.style.background !== '');
        if (e.key === 'ArrowDown') idx = idx < 0 ? 0 : Math.min(idx + 1, items.length - 1);
        else if (e.key === 'ArrowUp') idx = idx < 0 ? items.length - 1 : Math.max(idx - 1, 0);
        else return;
        e.preventDefault();
        items.forEach(li => li.style.background = '');
        items[idx] && (items[idx].style.background = '#444');
    }

    // Attach event listeners
    input.addEventListener('input', handleInput);
    // Delay hide to allow click to fire first
    input.addEventListener('blur', () => setTimeout(() => dropdown.style.display = 'none', 150));
    input.addEventListener('keydown', handleKey);
}


 // Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    // Main search input
    const qInput = document.querySelector('input[name="q"]');
    if (qInput) setupAutocomplete(qInput, WEB_ROOT + '/api/suggest-items?q=');

    // Mission type filter input (in drawer)
    const drawer = document.getElementById('drawer');
    const mtInput = drawer?.querySelector('input[name="mission_type"]');
    if (mtInput) setupAutocomplete(mtInput, WEB_ROOT + '/api/suggest-mission-types?q=');

    // Make table headers clickable for sorting
    document.querySelectorAll('table.sortable').forEach(table => {
        table.querySelectorAll('th').forEach((th, i) => th.onclick = () => sortTable(table, i));
    });

    // Restore drawer state from localStorage
    if (drawer) {
        const open = mtInput?.value.trim() || localStorage.getItem('drawerOpen') === 'true';
        if (open) drawer.classList.add('open');
    }
});


/** Toggle the advanced options drawer. */
function toggleDrawer() {
    const drawer = document.getElementById('drawer');
    drawer.classList.toggle('open');
    localStorage.setItem('drawerOpen', drawer.classList.contains('open'));
}


 /**
 * Sort a table by column.
 * @param {HTMLTableElement} table - The table to sort.
 * @param {number} col - Column index to sort by.
 */
function sortTable(table, col) {
    // Get table body and rows
    const tbody = table.tBodies[0];
    // Note: querying for 'tr' already removes headers, so we can just 
    //   sort by cell content without skipping the first row
    const rows = Array.from(tbody.querySelectorAll('tr'));
    // Get the header cell for the clicked column
    const th = table.querySelectorAll('th')[col];

    // Cycle through states: unsorted -> desc -> asc -> unsorted
    let state = th.classList.contains('desc') ? 'asc' : th.classList.contains('asc') ? 'unsorted' : 'desc';

    // Clear existing sort classes
    table.querySelectorAll('th').forEach(h => h.classList.remove('asc', 'desc'));
    if (state !== 'unsorted') th.classList.add(state);

    // Helper to extract percentage from "Rotation:X.XX%" format
    function extractChance(cell) {
        const m = cell.textContent.trim().match(/:(\d+\.?\d*)%/);
        return m ? parseFloat(m[1]) : NaN;
    }

    // Check if this column uses the chance format
    const isChance = rows.length && rows[0].cells[col].classList.contains('chance');
    // Get data attribute name for item columns (e.g. "data-Axi V14 Relic")
    let cellDataAttr = null;
    if (isChance) {
        const thText = table.querySelectorAll('th')[col].textContent.trim();
        if (thText !== '-') cellDataAttr = 'data-' + thText;
    }

    // Sort rows: unsorted always falls back to col 0 (data-weight), otherwise use column logic
    rows.sort((a, b) => {
        let an, bn;
        if (state === 'unsorted') {
            const aNum = parseFloat(a.cells[0].textContent.trim()) || -Infinity;
            const bNum = parseFloat(b.cells[0].textContent.trim()) || -Infinity;
            return aNum - bNum;
        } else if (isChance && cellDataAttr) {
            const aVal = a.cells[col].getAttribute(cellDataAttr);
            const bVal = b.cells[col].getAttribute(cellDataAttr);
            // Rows with data attr come first in desc, last in asc
            if (aVal === null || aVal === '') an = -Infinity;
            else an = parseFloat(aVal) || 0;
            if (bVal === null || bVal === '') bn = -Infinity;
            else bn = parseFloat(bVal) || 0;
        } else {
            // Default sort uses data-weight for numeric comparison
            const aW = a.getAttribute('data-weight');
            const bW = b.getAttribute('data-weight');
            an = (aW !== null && aW !== '') ? parseFloat(aW) || 0 : -Infinity;
            bn = (bW !== null && bW !== '') ? parseFloat(bW) || 0 : -Infinity;
        }
        return state === 'desc' ? bn - an : an - bn;
    });

    // Append sorted rows
    rows.forEach(r => tbody.appendChild(r));
}