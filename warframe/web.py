"""
Warframe Drop Tables Web Search

Flask web application for searching Warframe item drop locations.
Provides both HTML web interface and JSON API endpoints.

Uses cached drop data from WarframeStat.us API at:
    https://drops.warframestat.us/data/all.json

The application:
- Loads drop data on first request (fetches from API or cache)
- Provides search functionality across all drop sources
- Offers autocomplete for item names and mission types
- Renders results in sortable HTML tables or JSON format
"""

# Standard library imports
import os

# defaultdict creates nested dicts automatically for grouping results
from collections import defaultdict

# Third-party imports from requirements
from dotenv import load_dotenv
from flask import Flask, jsonify, request, send_from_directory

# Local imports
from warframe.parser import DropDataParser

# Load environment variables from .env file in project root
# This allows configuration without modifying code
load_dotenv()

# Create Flask app with templates and static files
# template_folder defaults to "templates" in the app root
# static_folder defaults to "static" for CSS, JS, images
app = Flask(__name__, template_folder="templates", static_folder="static")

# Configuration from environment or sensible defaults
# These can be set in .env file or environment
HOST = os.getenv("HOST", "127.0.0.1")  # Default to localhost
PORT = int(os.getenv("PORT", "8080"))  # Default port 8080
WEB_ROOT = os.getenv("WEB_ROOT", "/warframe")  # Base URL path for deployment

# Make WEB_ROOT available in Jinja2 templates
# Allows templates to generate correct URLs
app.config["WEB_ROOT"] = WEB_ROOT


# ============== Query Parsing ==============


def parse_queries(query: str) -> list[str]:
    """Split comma-separated query string into list of trimmed queries.

    Allows users to search for multiple items at once by separating
    with commas. Whitespace is trimmed from each query.

    Example:
        "scindo,Forma Blueprint" -> ["scindo", "Forma Blueprint"]

    Args:
        query: Comma-separated search queries.

    Returns:
        List of non-empty trimmed query strings.
    """
    # Split by comma, strip whitespace, filter empty strings
    return [q.strip() for q in query.split(",") if q.strip()]


# ============== Parser Instance ==============

# Single parser instance for the entire application
# Uses internal caching to avoid re-parsing on every request
_parser = DropDataParser()


# ============== Search Logic ==============


def run_search(query: str, exact: bool) -> list:
    """Run search for each query and combine results.

    Takes a comma-separated query string, parses it into individual queries,
    runs each through the parser, and combines all results.

    Args:
        query: Comma-separated search queries.
        exact: If True, require exact item name match.

    Returns:
        Combined list of DropResult sorted by drop chance (descending).
    """
    # Parse comma-separated queries into list
    queries = parse_queries(query)
    results = []
    # Run search for each individual query
    for q in queries:
        results.extend(_parser.search_items(q, exact=exact))
    # Sort by chance, highest first
    return sorted(results, key=lambda x: x.chance, reverse=True)


# ============== HTML Formatting ==============


def format_multi_table_html(results: list, queries: list[str], max_results: int) -> str:
    """Format search results as HTML table.

    Groups results by location and mission type, showing the best drop chance
    for each item/rotation combination. Creates a table suitable for
    display on the search results page.

    Grouping logic:
    - Results are grouped by (location, mission_type) tuple
    - Each item can have multiple rotations, keep highest chance
    - Locations sorted by (# items, best chance) for relevance

    Args:
        results: List of DropResult from search.
        queries: List of individual queries (for column headers).
        max_results: Maximum rows to show (0 = all).

    Returns:
        HTML string containing the results table.
    """
    # Group results: (location, mission_type) -> item -> rotation -> chance
    # defaultdict with lambda creates nested dicts automatically
    by_location = defaultdict(lambda: defaultdict(dict))
    for result in results:
        key = (result.location, result.mission_type)
        # Keep highest chance for each item/rotation combo
        if result.rotation not in by_location[key][result.item_name] or by_location[key][result.item_name][result.rotation] < result.chance:
            by_location[key][result.item_name][result.rotation] = result.chance

    def location_score(entry):
        """Score a location for sorting (more items + higher chance = better)."""
        _, items_dict = entry
        # Best chance across all items and rotations at this location
        best_chance = max(c for v in items_dict.values() for c in v.values())
        return len(items_dict), best_chance

    # Sort locations by score (more items, higher chance first)
    sorted_locations = sorted(by_location.items(), key=location_score, reverse=True)

    # Determine column order: for multi-query, use query order; otherwise alphabetical
    if len(queries) > 1:
        item_columns = []
        for _, items_dict in by_location.items():
            for col in items_dict:
                if col not in item_columns:
                    item_columns.append(col)
    else:
        # Single query: use alphabetical item names
        item_columns = sorted(set(r.item_name for r in results))

    # Build header row with item names
    headers = "".join(f"<th>{item}</th>" for item in item_columns)

    # Build data rows
    rows = []
    # If max_results > 0, limit to that many rows; otherwise show all
    for idx, ((location, mission_type), items_dict) in enumerate(sorted_locations if max_results == 0 else sorted_locations[:max_results], 1):
        # First cells: index, location, mission type
        row_cells = f"<td>{idx}</td><td>{location}</td><td>{mission_type}</td>"
        for item in item_columns:
            if item in items_dict:
                # Show best rotation and chance for this item
                rotations = items_dict[item]
                best_rot = max(rotations.items(), key=lambda x: x[1])
                row_cells += f'<td class="chance">{best_rot[0]}:{best_rot[1]:.2f}%</td>'
            else:
                row_cells += "<td>-</td>"
        rows.append(f"<tr>{row_cells}</tr>")

    row_html = "".join(rows)
    unique_locations = len(sorted_locations)

    # Build complete HTML with header and table
    results_header = f'<div class="results-header"><span class="results-count">Found {len(results)} drops across {unique_locations} locations'
    if max_results > 0:
        results_header += f". Showing best {max_results}"
    results_header += ":</span></div>"

    table_html = (
        '<table class="sortable"><thead><tr>'
        "<th>#</th><th>Location</th><th>Type</th>" + headers + "</tr></thead><tbody>" + row_html + "</tbody></table></div>"
    )
    return '<div class="table-wrapper">' + results_header + table_html


# ============== Template Caching ==============

# Template caches - loaded once on first request
# Storing in module globals avoids file I/O on every request
INDEX_HTML = None
MULTI_RESULT_TABLE = None
NO_RESULTS = None


@app.before_request
def load_templates():
    """Load HTML templates into memory on first request.

    Flask hook that runs before each request.
    On first request, reads template files from disk and caches them
    in module globals. Subsequent requests use cached content.

    This optimization avoids disk I/O on every HTTP request.
    """
    global INDEX_HTML, MULTI_RESULT_TABLE, NO_RESULTS
    if INDEX_HTML is None:
        # Read main page template (index.html)
        with open(os.path.join(app.root_path, "templates", "index.html")) as f:
            INDEX_HTML = f.read()
        # Read multi-result table partial (for updates)
        with open(os.path.join(app.root_path, "templates", "multi_result_table.html")) as f:
            MULTI_RESULT_TABLE = f.read()
        # Read "no results" message template
        with open(os.path.join(app.root_path, "templates", "no_results.html")) as f:
            NO_RESULTS = f.read()


# ============== Web Routes ==============


@app.route("/")
def index():
    """Main search page.

    GET parameters:
        q: Search query (required for results)
        n: Maximum results to show (0 = all)
        exact: If present, require exact item name match
        mission_type: Filter by mission type (comma-separated)
        refresh: If present, force refresh from API

    Returns:
        HTML page with search form and optional results table.
    """
    # Parse query parameters from URL
    refresh = "refresh" in request.args  # Force API refresh
    query = request.args.get("q", "")  # Search query
    num = int(request.args.get("n", "0"))  # Max results (0 = all)
    partial = "partial" in request.args  # Partial match mode
    partial_checked = " checked" if partial else ""  # For checkbox HTML
    mission_types = request.args.get("mission_type", "")  # Mission type filter

    # Parse mission type filter (comma-separated)
    mission_types_filter = [mt.strip() for mt in mission_types.split(",") if mt.strip()]

    results_html = ""
    if query:
        # Refresh data if requested (from cache or API)
        _parser.refresh(force=refresh)

        # Run search and get results
        queries = parse_queries(query)
        all_results = run_search(query, exact=not partial)

        # Apply mission type filter if specified
        if mission_types_filter:
            # Case-insensitive matching
            all_results = [r for r in all_results if r.mission_type.lower() in [mt.lower() for mt in mission_types_filter]]

        # Limit results if num > 0
        results = all_results[:num] if num > 0 else all_results

        # Format results as HTML table OR show "no results" message
        if results:
            results_html = format_multi_table_html(all_results, queries, num)
        else:
            # Template expects {query} placeholder
            results_html = NO_RESULTS.format(query=query)

    # Render main page template with all variables
    html = INDEX_HTML.format(
        web_root=app.config["WEB_ROOT"],
        query=query,
        num=num,
        partial_checked=partial_checked,
        mission_type=mission_types,
        results=results_html,
    )
    return html


@app.route("/api/drops")
def api_drops():
    """API endpoint for drop search (JSON).

    GET parameters:
        q: Search query (required)
        exact: If present, require exact item name match
        mission_type: Filter by mission type (can repeat for multiple)
        n: Maximum results to show (0 = all)

    Returns:
        JSON array of drop result objects.
    """
    query = request.args.get("q", "")
    if not query:
        return jsonify(error="Missing query parameter 'q'"), 400

    partial = "partial" in request.args  # Partial match mode
    mission_types = request.args.getlist("mission_type")
    max_results = int(request.args.get("n", "0"))

    results = run_search(query, exact=not partial)

    # Apply mission type filter if specified
    if mission_types:
        results = [r for r in results if r.mission_type.lower() in [mt.lower() for mt in mission_types]]

    # Limit results if requested
    results = results[:max_results] if max_results > 0 else results

    # Convert DropResult objects to JSON-serializable dicts
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

    GET parameters:
        q: Prefix to match (case-insensitive)

    Returns:
        JSON array of up to 10 matching item names.
    """
    prefix = request.args.get("q", "").lower()
    data = _parser.get_drop_data()
    # Filter items matching prefix, limit to 10
    matches = [item for item in data.items if prefix in item.lower()][:10]
    return jsonify(matches)


@app.route("/api/suggest-mission-types")
def suggest_mission_types():
    """Autocomplete endpoint for mission types.

    GET parameters:
        q: Prefix to match (case-insensitive)

    Returns:
        JSON array of up to 10 matching mission types.
    """
    prefix = request.args.get("q", "").lower()
    data = _parser.get_drop_data()
    mission_types = data.mission_types
    # Filter types matching prefix, limit to 10
    matches = [mt for mt in mission_types if prefix in mt.lower()][:10]
    return jsonify(matches)


@app.route("/static/<path:filename>")
def static_file(filename):
    """Serve static files (CSS, JS, images).

    Flask serves files from the static_folder configured on app creation.
    This handles requests to /static/* URLs.

    Args:
        filename: Path to static file.

    Returns:
        File content with correct MIME type.
    """
    return send_from_directory(app.static_folder, filename)


# ============== Server Startup ==============


def run_server(host=HOST, port=PORT):
    """Run development server.

    Note: Flask's built-in server is for development only.
    For production, use gunicorn: gunicorn warframe.web:app

    Args:
        host: IP address to bind to.
        port: Port number to bind to.
    """
    print(f"Starting server on http://{host}:{port}")
    print("API endpoint: /api/drops?q=<query>")
    app.run(host=host, port=port)


def create_app():
    """Create and return the Flask app.

    Used by gunicorn and testing frameworks.
    Returns the global Flask app instance.

    Returns:
        The Flask application object.
    """
    return app


# ============== Main Entry Point ==============

# Run server when script is executed directly (not imported)
if __name__ == "__main__":
    run_server()
