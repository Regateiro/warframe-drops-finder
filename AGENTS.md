# warframe

## Setup
```bash
poetry install       # install deps
poetry run <cmd>     # run command in venv
```

## Commands
- `make lint` — runs black, flake8, isort, pylint with line-length 150
- `make test` — runs pytest with verbose output

## Dependencies
- Dev: black, flake8, isort, pylint, pytest

## Notes
- Source code lives in `src/`
- `pyproject.toml` has `package-mode = false`
- API data cached in `.drop_cache.json` (auto-fetched on first run)
- Drop data source: `https://drops.warframestat.us/data/all.json`
