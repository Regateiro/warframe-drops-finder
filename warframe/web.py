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
import time

# defaultdict creates nested dicts automatically for grouping results
from collections import defaultdict
from urllib.parse import urlencode

# Third-party imports from requirements
from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request, send_from_directory

# Local imports
from warframe.fetcher import CACHE_MAX_AGE
from warframe.models import Mission
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
    # Split by comma, strip whitespace, filter empty strings (max 10 queries)
    return [q.strip() for q in query.split(",")[:10] if q.strip()]


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

    Groups results by location and mission type, showing all rotations with their
    respective drop chances (e.g. "B:6.67%/C:11.06%"). Creates a table suitable for
    display on the search results page.

    Grouping logic:
    - Results are grouped by (location, mission_type) tuple
    - Each item can have multiple rotations, keep highest chance
    - Locations sorted by query weight (weighted sum of drop chances)
    - Item weights use weighted average: max(a, (2a+b)/3 if B present, (2a+b+c)/4 if C present)

    Args:
        results: List of DropResult from search.
        queries: List of individual queries (for column headers).
        max_results: Maximum rows to show (0 = all).

    Returns:
        HTML string containing the results table.
    """
    # Group results: (location, Mission) -> item -> {rotation: chance}
    by_location = defaultdict(lambda: defaultdict(dict))
    for result in results:
        key = (result.location, result.mission_type)
        if result.rotation not in by_location[key][result.item_name] or by_location[key][result.item_name][result.rotation] < result.chance:
            by_location[key][result.item_name][result.rotation] = result.chance

    def mission_weight(items_dict: dict, mission: Mission) -> float:
        """Compute a relevance score for a set of items at one location.

        Warframe relic missions follow a 4-completion cycle: A drops on completions
        1-2, B on completion 3, C on completion 4. Each item's drop chance is
        weighted by how often it appears in the cycle (A gets double weight since
        it appears twice). The function sums all queried items' chances per rotation,
        then returns the maximum of available weighted averages:
          - A only:             a_total           (= A%)
          - A + B present:      (2*a + b) / 3    (= avg across 3 possible drops)
          - All three present:  (2*a + b + c) / 4 (= avg across all completions)
        Taking the max captures the scenario where the item is most likely to drop.

        For missions with a single reward table (no A/B/C rotations), the total drop
        chance is used directly since there is no cycle weighting needed.

        For Disruption missions, the rotation pattern differs:
        AAAB → AABB → ABBC → BBCC → ...
        A and B rewards are always available (restartable), while C only becomes
        available after 2 prior completions. Assuming a typical ~10 round run,
        C is available on roughly 8 of them, so the weight is:
          (max(A,B) * 2 + C * 8) / 10
        """
        # Check if this is a multi-table mission (has A/B/C keys)
        # vs single-table (all items keyed by "-")
        has_rotations = any(k in ("A", "B", "C") for v in items_dict.values() for k in v.keys())

        if not has_rotations:
            # Single reward table: total drop chance across all items
            raw_weight = sum(c for v in items_dict.values() for c in v.values())
            return raw_weight / mission.get_average_time_per_cycle()

        a = sum(v.get("A", 0) for v in items_dict.values())
        b = sum(v.get("B", 0) for v in items_dict.values())
        c = sum(v.get("C", 0) for v in items_dict.values())
        weights = []

        # Special case: Disruption — C only available after 2 prior completions,
        # A and B always available (A by restarting). Assumes ~10 round run with C on 8 rounds.
        if mission.get_name() == "Disruption":
            # Assume running for the A reward table exclusively, since it is available on the first three completions and can be restarted.
            weights.append(a)
            # Assume running for the B reward table exclusively, since it is always available
            weights.append(b)
            # Assume running for the C reward table past the second completion
            # This captures the scenario where the item is most likely to drop from the C reward table.
            weights.append((max(a, b) * 2 + c * 8) / 10)
        else:
            # Assume running only the first two completion cycles for the A reward table
            weights.append(a)
            # Assume running only up to the third completion cycle for the B reward table
            weights.append((2 * a + b) / 3)
            # Assume running up to the fourth completion cycle for the C reward table
            weights.append((2 * a + b + c) / 4)

        # Normalize by average time per cycle so longer missions don't
        # get an unfair advantage.
        return max(weights) / mission.get_average_time_per_cycle()

    # Sort locations by mission weight desc, then more items first, then best chance
    def sort_key(entry):
        (location, mission), items_dict = entry
        mw = mission_weight(items_dict, mission)
        num_items = len(items_dict)
        best_chance = max(c for v in items_dict.values() for c in v.values())
        return mw, num_items, best_chance

    sorted_locations = sorted(by_location.items(), key=sort_key, reverse=True)

    # Determine column order: first-seen across locations preserves grouping
    item_columns = []
    seen = set()
    for _, items_dict in by_location.items():
        for col in items_dict:
            if col not in seen:
                item_columns.append(col)
                seen.add(col)

    # Build header row with item names
    headers = "".join(f"<th>{item}</th>" for item in item_columns)

    # Build table rows in sorted order (most relevant missions first).
    # Each row gets a `data-weight` attribute with the mission weight for client-side sorting.
    rows = []
    for idx, ((location, mission), items_dict) in enumerate(sorted_locations if max_results == 0 else sorted_locations[:max_results], 1):
        row_cells = f"<td>{idx}</td><td>{location}</td><td>{mission.get_name()}</td>"
        mw = mission_weight(items_dict, mission)
        for item in item_columns:
            if item in items_dict:
                rotations = items_dict[item]
                # Per-item weight: apply the same weighted-average formula to just this
                # item's drops. This lets column headers sort by that item's relevance.
                iw = mission_weight({item: dict(rotations)}, mission)
                rot_strs = [f"{rot}:{chance:.2f}%" for rot, chance in sorted(rotations.items())]
                row_cells += f'<td class="chance" data-weight="{iw:.4f}">{" ".join(rot_strs)}</td>'
            else:
                row_cells += '<td class="chance" data-weight="0">-</td>'
        rows.append(f'<tr data-weight="{mw:.4f}">{row_cells}</tr>')

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


# ============== Web Routes ==============


@app.route("/")
def index():
    """Main search page.

    GET parameters:
        q: Search query (required for results)
        n: Maximum results to show (0 = all)
        exact: If present, require exact item name match
        mission_type: Filter by mission type (comma-separated)
        refresh: If present, request a cache refetch (only applied if the cache is ≥ 5 minutes old)

    Returns:
        HTML page with search form and optional results table.
    """
    # Parse and validate query parameters from URL.
    # Each parameter is sanitized: trimmed, bounded to prevent abuse/edge cases.
    refresh = "refresh" in request.args  # Request cache refetch (guarded by 5-min minimum age)
    query = (request.args.get("q") or "").strip()[:500]  # Search query, max 500 chars
    n_raw = request.args.get("n")
    num = max(0, min(int(n_raw), 10_000)) if n_raw else 0  # Clamp to [0, 10000]
    partial = "partial" in request.args  # Partial match mode
    partial_checked = " checked" if partial else ""  # For checkbox HTML
    mission_types = (request.args.get("mission_type") or "").strip()[:256]  # Mission type filter, max 256 chars

    # Parse mission type filter (comma-separated, max 20 types)
    mission_types_filter = [mt.strip() for mt in mission_types.split(",")[:20] if mt.strip()]

    # Refresh data from API cache if the refresh flag is set.
    _parser.refresh(force=refresh)

    # Compute cache age for display.
    ts = _parser.get_cache_timestamp()
    if ts is not None:
        elapsed_mins = (time.time() - ts) / 60
        hours, minutes = divmod(int(elapsed_mins), 60)
        cache_age = f"{hours}h:{minutes:02d}m"
        stale = int(elapsed_mins * 60) > CACHE_MAX_AGE
    else:
        cache_age = "--"
        stale = False

    # Parse comma-separated query terms, run search (exact or partial match),
    # then apply optional mission type filter and result limit.
    queries = parse_queries(query) if query else []
    all_results = run_search(query, exact=not partial) if query else []

    # Apply mission type filter if specified
    if mission_types_filter:
        all_results = [r for r in all_results if r.mission_type.get_name().lower() in [mt.lower() for mt in mission_types_filter]]

    # Limit results if num > 0
    results = all_results[:num] if num and num > 0 else all_results

    # Format search results into an HTML table with weighted sorting.
    # Passes all_results (unlimited) to the formatter so it can compute weights
    # from the full dataset before applying the row limit.
    if results:
        results_html = format_multi_table_html(all_results, queries, num)
    else:
        results_html = ""

    # Build refresh URL query string: clone all current params (excluding empty values)
    # so clicking Refresh preserves filters while adding the refresh flag.
    refresh_qs = urlencode({k: v for k, v in request.args.items(multi=False) if v}, doseq=True)

    return render_template(
        "index.html",
        web_root=app.config["WEB_ROOT"],
        query=query,
        results_html=results_html,
        max_results=num,
        partial_checked=partial_checked,
        mission_type=mission_types or "",
        refresh_qs=refresh_qs,
        cache_age=cache_age,
        stale=stale,
    )


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
        results = [r for r in results if r.mission_type.get_name().lower() in [mt.lower() for mt in mission_types]]

    # Limit results if requested
    results = results[:max_results] if max_results > 0 else results

    # Convert DropResult objects to JSON-serializable dicts
    output = [
        {
            "item_name": r.item_name,
            "chance": r.chance,
            "location": r.location,
            "mission_type": r.mission_type.get_name(),
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
