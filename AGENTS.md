# warframe

## Setup
```bash
poetry install
```

## Commands
- `make serve` — runs webserver (gunicorn)
- `make test` — runs pytest
- `make lint` — runs black/flake8/isort/pylint
- `make deploy` — deploys to production

## Run locally
```bash
poetry run python -m warframe.web
```

## Architecture
- Entrypoint: `warframe/web.py` (Flask app)
- Backend modules: `fetcher.py` (API data), `iterators.py` (search), `models.py` (data classes)
- Routes: `/`, `/api/drops?q=<query>`, `/api/suggest-items`, `/api/suggest-mission-types`

## Notes
- .env configures HOST, PORT, WEB_ROOT
- API data cached in `.drop_cache.json` (auto-fetched on first run)
- Drop source: `https://drops.warframestat.us/data/all.json`