# Warframe Drop Locations

A command-line tool and web server for searching Warframe item drop locations.

## Installation

```bash
poetry install
```

## Data Source

Drop data is fetched from [Warframe Stat](https://drops.warframestat.us/) and cached locally in `.drop_cache.json`, next to the project root. The cache is valid for 24 hours. Set the `CACHE_FILE` environment variable to override the cache location.

## Web Server

Start the web interface:

```bash
make serve
```

Or directly:

```bash
poetry run gunicorn -w 2 --bind 127.0.0.1:3333 warframe.web:app
```

The server starts on `http://localhost:3333` by default.

### Configuration

Create a `.env` file to customize the server:

```bash
cp .env.example .env
```

| Variable | Default | Description |
|----------|---------|-------------|
| `HOST` | `127.0.0.1` | Server bind address (development server only) |
| `PORT` | `8080` | Server port (development server only) |
| `WEB_ROOT` | `/warframe` | URL prefix (e.g., `/warframe`) |
| `CACHE_FILE` | `.drop_cache.json` | Path to the drop data cache |

> `HOST`/`PORT` are only used by the development server (`python -m warframe.web`). When running under gunicorn, pass `--bind` instead.

Routes are registered both at the app root (`/`, `/api/...`, `/static/...`) and under `WEB_ROOT` (e.g. `/warframe/`, `/warframe/api/...`), so the app works when served directly as well as behind a reverse proxy that strips the prefix.

### Web Interface

- Open `http://localhost:3333` in your browser
- Enter item names to search
- Use options to filter results
- Searches match item names as substrings by default; tick **Exact match** to require the full name

### REST API

```
GET /api/drops?q=<query>&exact=<bool>&mission_type=<type>&n=<count>
GET /api/suggest-items?q=<prefix>
GET /api/suggest-mission-types?q=<prefix>
```

#### Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `q` | string | Item name to search for (required) |
| `exact` | bool | Require an exact item name match (optional, default: substring match) |
| `mission_type` | string | Filter by mission type (repeatable) |
| `n` | int | Max results (default: 0 for all, capped at 10000) |

#### Response

```json
[
  {
    "item_name": "Neuroptics",
    "chance": 25.44,
    "location": "Earth - Defense",
    "mission_type": "Defense",
    "rotation": "C"
  }
]
```

### Examples

```bash
# Search via API
curl "http://localhost:3333/api/drops?q=neuroptics"

# Exact match
curl "http://localhost:3333/api/drops?q=galatine&exact=true"

# Filter by mission type
curl "http://localhost:3333/api/drops?q=forma&mission_type=defense"
```

## Development

```bash
# Run tests (also runs linters)
make test

# Run linters (check-only, does not modify files)
make lint

# Auto-format the source with black + isort
make format

# Start web server
make serve

# Deploy to server
make deploy
```