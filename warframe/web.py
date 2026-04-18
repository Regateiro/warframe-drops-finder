"""
Warframe Drop Tables Web Search

Flask web application for searching Warframe item drop locations.
Uses cached drop data from warframestat.us API.
"""

import os
from collections import defaultdict

from dotenv import load_dotenv
from flask import Flask, jsonify, request, send_from_directory

from warframe.parser import DropDataParser

# Load environment variables from .env file
load_dotenv()

# Create Flask app with templates and static files
app = Flask(__name__, template_folder="templates", static_folder="static")

# Configuration from environment or defaults
HOST = os.getenv("HOST", "127.0.0.1")
PORT = int(os.getenv("PORT", "8080"))
WEB_ROOT = os.getenv("WEB_ROOT", "/warframe")

# Make WEB_ROOT available in templates
app.config["WEB_ROOT"] = WEB_ROOT


def parse_queries(query: str) -> list[str]:
    """Split comma-separated query string into list of trimmed queries.
    Example: "scindo,Forma Blueprint" -> ["scindo", "Forma Blueprint"]
    """
    return [q.strip() for q in query.split(",") if q.strip()]


# Parser instance with internal caching
_parser = DropDataParser()


def run_search(query: str, exact: bool) -> list:
    """Run search for each query and combine results.
    Returns list sorted by drop chance (descending).
    """
    queries = parse_queries(query)
    results = []
    for q in queries:
        results.extend(_parser.search_items(q, exact=exact))
    return sorted(results, key=lambda x: x.chance, reverse=True)


def format_multi_table_html(results: list, queries: list[str], max_results: int) -> str:
    """Format search results as HTML table.
    Groups results by location and shows best chance per item/rotation.
    """
    by_location = defaultdict(lambda: defaultdict(dict))
    for result in results:
        key = (result.location, result.mission_type)
        if result.rotation not in by_location[key][result.item_name] or by_location[key][result.item_name][result.rotation] < result.chance:
            by_location[key][result.item_name][result.rotation] = result.chance

    def location_score(entry):
        _, items_dict = entry
        best_chance = max(c for v in items_dict.values() for c in v.values())
        return len(items_dict), best_chance

    sorted_locations = sorted(by_location.items(), key=location_score, reverse=True)

    def make_columns(item_dict: dict) -> list[str]:
        cols = []
        for item in queries:
            if item in item_dict:
                cols.append(item)
        return cols

    if len(queries) > 1:
        item_columns = []
        for _, items_dict in by_location.items():
            for col in make_columns(items_dict):
                if col not in item_columns:
                    item_columns.append(col)
    else:
        item_columns = sorted(set(r.item_name for r in results))

    headers = "".join(f"<th>{item}</th>" for item in item_columns)

    rows = []
    for idx, ((location, mission_type), items_dict) in enumerate(sorted_locations if max_results == 0 else sorted_locations[:max_results], 1):
        row_cells = f"<td>{idx}</td><td>{location}</td><td>{mission_type}</td>"
        for item in item_columns:
            if item in items_dict:
                rotations = items_dict[item]
                best_rot = max(rotations.items(), key=lambda x: x[1])
                row_cells += f'<td class="chance">{best_rot[0]}:{best_rot[1]:.2f}%</td>'
            else:
                row_cells += "<td>-</td>"
        rows.append(f"<tr>{row_cells}</tr>")

    row_html = "".join(rows)
    unique_locations = len(sorted_locations)

    return (
        '<div class="table-wrapper">'
        f'<div class="results-header"><span class="results-count">'
        f"Found {len(results)} drops across {unique_locations} locations."
        f" Showing best {max_results}:</span></div>"
        if max_results > 0
        else ""
        '<table class="sortable"><thead><tr>'
        "<th>#</th><th>Location</th><th>Type</th>" + headers + "</tr></thead><tbody>" + row_html + "</tbody></table></div>"
    )


# Template caches - loaded once on first request
INDEX_HTML = None
MULTI_RESULT_TABLE = None
NO_RESULTS = None


@app.before_request
def load_templates():
    """Load HTML templates into memory on first request.
    Avoids file I/O on every request.
    """
    global INDEX_HTML, MULTI_RESULT_TABLE, NO_RESULTS
    if INDEX_HTML is None:
        with open(os.path.join(app.root_path, "templates", "index.html")) as f:
            INDEX_HTML = f.read()
        with open(os.path.join(app.root_path, "templates", "multi_result_table.html")) as f:
            MULTI_RESULT_TABLE = f.read()
        with open(os.path.join(app.root_path, "templates", "no_results.html")) as f:
            NO_RESULTS = f.read()


@app.route("/")
def index():
    """Main search page.
    Query params: q (search), n (max results), exact, mission_type filter, refresh
    """
    # Parse query parameters
    refresh = "refresh" in request.args
    query = request.args.get("q", "")
    num = int(request.args.get("n", "0"))
    exact = "exact" in request.args
    exact_checked = " checked" if exact else ""
    mission_types = request.args.get("mission_type", "")
    mission_types_filter = [mt.strip() for mt in mission_types.split(",") if mt.strip()]

    results_html = ""
    if query:
        # Refresh data (from cache or API)
        _parser.refresh(force=refresh)

        # Run search and format results
        queries = parse_queries(query)
        all_results = run_search(query, exact=exact)

        # Apply mission type filter if specified
        if mission_types_filter:
            all_results = [r for r in all_results if r.mission_type.lower() in [mt.lower() for mt in mission_types_filter]]

        # Limit results if num > 0
        results = all_results[:num] if num > 0 else all_results

        # Format results as HTML table or show no results message
        if results:
            results_html = format_multi_table_html(all_results, queries, num)
        else:
            results_html = NO_RESULTS.format(query=query)

    # Render main page with results
    html = INDEX_HTML.format(
        web_root=app.config["WEB_ROOT"],
        query=query,
        num=num,
        exact_checked=exact_checked,
        mission_type=mission_types,
        results=results_html,
    )
    return html


@app.route("/api/drops")
def api_drops():
    """API endpoint for drop search.
    Query params: q (required), exact, mission_type (filter), n (max results)
    Returns JSON array of drop results.
    """
    query = request.args.get("q", "")
    if not query:
        return jsonify(error="Missing query parameter 'q'"), 400

    exact = "exact" in request.args
    mission_types = request.args.getlist("mission_type")
    max_results = int(request.args.get("n", "0"))

    results = run_search(query, exact=exact)

    if mission_types:
        results = [r for r in results if r.mission_type.lower() in [mt.lower() for mt in mission_types]]

    results = results[:max_results] if max_results > 0 else results

    output = [
        {
            "item_name": r.item_name,
            "chance": r.chance,
            "location": r.location,
            "mission_type": r.mission_type,
            "rotation": r.rotation,
        }
        for r in results
    ]
    return jsonify(output)


@app.route("/api/suggest-items")
def suggest_items():
    """Autocomplete endpoint for item names.
    Query param: q (prefix to match)
    Returns JSON array of up to 10 matching items.
    """
    prefix = request.args.get("q", "").lower()
    data = _parser.get_drop_data()
    matches = [item for item in data.items if prefix in item.lower()][:10]
    return jsonify(matches)


@app.route("/api/suggest-mission-types")
def suggest_mission_types():
    """Autocomplete endpoint for mission types.
    Query param: q (prefix to match)
    Returns JSON array of up to 10 matching mission types.
    """
    prefix = request.args.get("q", "").lower()
    data = _parser.get_drop_data()
    mission_types = data.mission_types
    matches = [mt for mt in mission_types if prefix in mt.lower()][:10]
    return jsonify(matches)


@app.route("/static/<path:filename>")
def static_file(filename):
    """Serve static files (CSS, JS, images)."""
    return send_from_directory(app.static_folder, filename)


def run_server(host=HOST, port=PORT):
    """Run development server.
    Uses Flask dev server (not for production).
    For production use: gunicorn warframe.web:app
    """
    print(f"Starting server on http://{host}:{port}")
    print("API endpoint: /api/drops?q=<query>")
    app.run(host=host, port=port)


def create_app():
    """Create and return the Flask app (for testing/gunicorn)."""
    return app


if __name__ == "__main__":
    run_server()
