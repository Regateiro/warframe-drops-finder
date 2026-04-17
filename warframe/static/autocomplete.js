class Autocomplete {
    constructor(input, suggestions, onSelect) {
        this.input = input;
        this.suggestions = suggestions || [];
        this.onSelect = onSelect;
        this.isOpen = false;
        this.highlightedIndex = -1;

        this.setup();
    }

    setup() {
        this.input.parentNode.style.position = 'relative';
        this.input.removeAttribute('list');

        this.dropdown = document.createElement('ul');
        this.dropdown.className = 'autocomplete-dropdown';
        this.dropdown.style.cssText = 'position:absolute;top:100%;left:0;right:0;background:#2a2a2a;border:1px solid #444;border-top:none;list-style:none;margin:0;padding:0;max-height:200px;overflow-y:auto;z-index:1000;display:none';
        this.input.parentNode.appendChild(this.dropdown);

        this.input.addEventListener('input', (e) => this.onInput(e));
        this.input.addEventListener('focus', () => this.show());
        this.input.addEventListener('blur', () => setTimeout(() => this.close(), 200));
        this.input.addEventListener('keydown', (e) => this.onKeydown(e));
    }

    setSuggestions(suggestions) {
        this.suggestions = suggestions;
        this.render();
    }

    filter() {
        const value = this.input.value.toLowerCase();
        if (!value) return this.suggestions.slice(0, 10);
        return this.suggestions.filter(s => s.toLowerCase().includes(value)).slice(0, 10);
    }

    render() {
        const filtered = this.filter();
        this.dropdown.innerHTML = '';
        filtered.forEach((item, i) => {
            const li = document.createElement('li');
            li.textContent = item;
            li.style.cssText = 'padding:0.5rem;cursor:pointer;color:#fff';
            li.onmouseenter = () => this.highlight(i);
            li.onmousedown = (e) => {
                e.preventDefault();
                this.select(item);
            };
            this.dropdown.appendChild(li);
        });
        this.dropdown.style.display = filtered.length ? 'block' : 'none';
        this.isOpen = filtered.length > 0;
    }

    show() {
        this.render();
    }

    close() {
        this.dropdown.style.display = 'none';
        this.isOpen = false;
    }

    highlight(index) {
        const items = this.dropdown.querySelectorAll('li');
        items.forEach((li, i) => {
            li.style.background = i === index ? '#444' : '';
        });
        this.highlightedIndex = index;
    }

    select(item) {
        this.input.value = item;
        this.close();
        if (this.onSelect) this.onSelect(item);
    }

    onKeydown(e) {
        const items = this.dropdown.querySelectorAll('li');
        if (e.key === 'ArrowDown') {
            e.preventDefault();
            this.highlightedIndex = Math.min(this.highlightedIndex + 1, items.length - 1);
            this.highlight(this.highlightedIndex);
            this.scrollToHighlight();
        } else if (e.key === 'ArrowUp') {
            e.preventDefault();
            this.highlightedIndex = Math.max(this.highlightedIndex - 1, 0);
            this.highlight(this.highlightedIndex);
            this.scrollToHighlight();
        } else if (e.key === 'Enter' && this.highlightedIndex >= 0) {
            e.preventDefault();
            this.select(items[this.highlightedIndex].textContent);
        } else if (e.key === 'Escape') {
            this.close();
        }
    }

    scrollToHighlight() {
        const items = this.dropdown.querySelectorAll('li');
        if (items[this.highlightedIndex]) {
            items[this.highlightedIndex].scrollIntoView({ block: 'nearest' });
        }
    }

    onInput() {
        this.show();
    }
}

let itemAutocomplete, missionTypeAutocomplete;

function loadAutocompleteSuggestions() {
    const itemsList = document.getElementById('items-list');
    if (itemsList) itemsList.remove();

    const missionTypesList = document.getElementById('mission-types-list');
    if (missionTypesList) missionTypesList.remove();

    fetch(WEB_ROOT + '/api/suggest-items?q=' + new Date().getTime())
        .then(r => r.json())
        .then(items => {
            const qInput = document.querySelector('input[name="q"]');
            itemAutocomplete = new Autocomplete(qInput, items, (item) => {
                qInput.form.submit();
            });
            console.log('Loaded', items.length, 'item suggestions');
        })
        .catch(e => console.error('Failed to load items:', e));

    fetch(WEB_ROOT + '/api/suggest-mission-types?q=' + new Date().getTime())
        .then(r => r.json())
        .then(types => {
            const mtInput = document.querySelector('input[name="mission_type"]');
            missionTypeAutocomplete = new Autocomplete(mtInput, types, () => {
                mtInput.form.submit();
            });
            console.log('Loaded', types.length, 'mission type suggestions');
        })
        .catch(e => console.error('Failed to load mission types:', e));
}

document.addEventListener('DOMContentLoaded', loadAutocompleteSuggestions);