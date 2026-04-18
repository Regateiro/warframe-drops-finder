# Warframe Drop Locations

A command-line tool and web server for searching Warframe item drop locations.

## Installation

```bash
poetry install
```

## Data Source

Drop data is fetched from [Warframe Stat](https://drops.warframestat.us/) and cached locally in `.drop_cache.json`. The cache is valid for 24 hours.

## CLI Usage

```bash
poetry run warframe <query> [options]
```

### Arguments

- `query` - Item name to search for (space or comma separated)

### Options

- `-r, --refresh` - Force refresh the cache
- `-n, --num N` - Number of results to show (default: 20)
- `-e, --exact` - Match item names exactly
- `-m, --mission-type` - Filter by mission type (can be specified multiple times)

### Examples

```bash
# Search for an item
poetry run warframe aura
poetry run warframe "neuroptics"

# Multiple items
poetry run warframe neptune,uranus
poetry run warframe forma blueprints

# Exact match
poetry run warframe "galatine" --exact

# Filter by mission type
poetry run warframe neuroptics --mission-type defense

# Show all results
poetry run warframeForma -n 0
```

## Web Server

Start the web interface:

```bash
make serve
```

Or directly:

```bash
poetry run gunicorn -w 2 warframe.web:app
```

The server starts on `http://localhost:8080` by default.

### Configuration

Create a `.env` file to customize the server:

```bash
cp .env.example .env
```

| Variable | Default | Description |
|----------|---------|-------------|
| `HOST` | `127.0.0.1` | Server bind address |
| `PORT` | `8080` | Server port |
| `WEB_ROOT` | `/warframe` | URL prefix (e.g., `/warframe`) |

### Web Interface

- Open `http://localhost:8080` in your browser
- Enter item names to search
- Use options to filter results

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
| `exact` | bool | Match exactly (optional) |
| `mission_type` | string | Filter by mission type (repeatable) |
| `n` | int | Max results (default: 0 for all) |

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
curl "http://localhost:8080/api/drops?q=neuroptics"

# Exact match
curl "http://localhost:8080/api/drops?q=galatine&exact=true"

# Filter by mission type
curl "http://localhost:8080/api/drops?q=forma&mission_type=defense"
```

## Development

```bash
# Run tests
make test

# Run linters
make lint

# Start web server
make serve

# Deploy to server
make deploy
```