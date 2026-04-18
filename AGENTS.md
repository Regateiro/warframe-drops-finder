# warframe

## Setup
```bash
poetry install       # install deps
poetry run <cmd>     # run command in venv
```

## Commands
- `make lint` — runs black, flake8, isort, pylint with line-length 150
- `make test` — runs pytest with verbose output
- `make serve` — runs the webserver (gunicorn)
- `make deploy` — deploys to production server

## Dependencies
- Runtime: flask, gunicorn
- Dev: black, flake8, isort, pylint, pytest

## Notes
- Web server uses Flask with Gunicorn
- .env configures HOST, PORT, WEB_ROOT
- API endpoints: /api/drops, /api/suggest-items, /api/suggest-mission-types
- API data cached in `.drop_cache.json` (auto-fetched on first run)
- Drop data source: `https://drops.warframestat.us/data/all.json`
