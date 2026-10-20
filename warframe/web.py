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
import logging
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
from warframe.parser import DataUnavailableError, DropDataParser

# Load environment variables from .env file in project root
# This allows configuration without modifying code
load_dotenv()

logger = logging.getLogger(__name__)

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


def parse_int(raw: str | None, default: int, lo: int, hi: int) -> int:
    """Parse and clamp an integer query parameter.

    Args:
        raw: Raw parameter value (may be None or empty).
        default: Value to return when raw is None/empty.
        lo: Minimum allowed value.
        hi: Maximum allowed value.

    Returns:
        The parsed value, clamped to [lo, hi], or default if raw is empty.

    Raises:
        ValueError: If raw is present but not an integer.
    """
    if raw is None or not raw.strip():
        return default
    return max(lo, min(int(raw), hi))


def parse_bool(raw: str | None) -> bool:
    """Parse a boolean query parameter (flag-style or explicit).

    Absent -> False. Present with no value, "1", "true", "yes", or "on"
    (checkbox default) -> True. Anything else -> False.
    """
    if raw is None:
        return False
    return raw.strip().lower() in ("", "1", "true", "yes", "on")


# ============== Parser Instance ==============

# Single parser instance for the entire application.
# Data is loaded lazily on the first request (uses internal caching to
# avoid re-parsing on every request).
_parser = DropDataParser()


# ============== Search Logic ==============


def run_search(query: str, exact: bool) -> list:
    """Run search for each query and combine results.

    Takes a comma-separated query string, parses it into individual queries,
    runs each through the parser, and combines all results, deduplicating
    identical drops that appear via overlapping queries or data entries.

    Args:
        query: Comma-separated search queries.
        exact: If True, require exact item name match.

    Returns:
        Combined deduplicated list of DropResult sorted by drop chance (descending).
    """
    queries = parse_queries(query)
    results = []
    for q in queries:
        results.extend(_parser.search_items(q, exact=exact))
    # Dedupe across queries, then sort by chance, highest first
    unique = list(dict.fromkeys(results))
    return sorted(unique, key=lambda x: x.chance, reverse=True)


# ============== HTML Formatting ==============


def format_multi_table_html(results: list, max_results: int) -> str:
    """Format search results as an HTML table.

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
        max_results: Maximum rows to show (0 = all).

    Returns:
        Rendered HTML string containing the results table.
    """
    # Group results: (location, Mission) -> item -> {rotation: chance}
    by_location = defaultdict(lambda: defaultdict(dict))
    for result in results:
        key = (result.location, result.mission_type)
        rotations = by_location[key][result.item_name]
        if result.rotation not in rotations or rotations[result.rotation] < result.chance:
            rotations[result.rotation] = result.chance

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
        AAAB -> AABB -> ABBC -> BBCC -> ...
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
        matpc = mission.get_average_time_per_cycle()
        mart = Mission.get_average_restart_time()
        weights = []

        # Special case: Disruption — C only available after 2 prior completions,
        # A and B always available (A by restarting). Assumes ~10 round run with C on 8 rounds.
        if mission.get_name() == "Disruption":
            # Assume running for the A reward table exclusively, since it is available on the first three completions and can be restarted.
            weights.append((3 * a) / (3 * matpc + mart))
            # Assume running for the B reward table exclusively for 10 rounds, since it is always available.
            weights.append((10 * b) / (10 * matpc + mart))
            # Assume running for the C reward table past the second completion
            # This captures the scenario where the item is most likely to drop from the C reward table.
            weights.append((max(a, b) * 2 + c * 8) / (10 * matpc + mart))
        else:
            # Assume running only the first two completion cycles for the A reward table
            weights.append(a / (matpc + mart))
            # Assume running only up to the third completion cycle for the B reward table
            weights.append((2 * a + b) / (3 * matpc + mart))
            # Assume running up to the fourth completion cycle for the C reward table
            weights.append((2 * a + b + c) / (4 * matpc + mart))

        # Normalize by average time per cycle so longer missions don't
        # get an unfair advantage.
        return max(weights)

    # Compute each location's mission weight once (reused for sorting and row HTML)
    weighted = [((key, items_dict), mission_weight(items_dict, key[1])) for key, items_dict in by_location.items()]

    # Sort locations by mission weight desc, then more items first, then best chance
    def sort_key(entry):
        (key, items_dict), mw = entry
        best_chance = max(c for v in items_dict.values() for c in v.values())
        return mw, len(items_dict), best_chance

    weighted.sort(key=sort_key, reverse=True)

    # Determine column order: first-seen across locations preserves grouping
    item_columns = []
    seen = set()
    for (_, items_dict), _mw in weighted:
        for col in items_dict:
            if col not in seen:
                item_columns.append(col)
                seen.add(col)

    # Build table rows in sorted order (most relevant missions first).
    # Each row gets a `data-weight` attribute with the mission weight for client-side sorting.
    rows = []
    limited = weighted if max_results == 0 else weighted[:max_results]
    for idx, ((location, mission), items_dict, mw) in enumerate(((k, d, w) for (k, d), w in limited), 1):
        cells = []
        for item in item_columns:
            if item in items_dict:
                rotations = items_dict[item]
                # Per-item weight: apply the same weighted-average formula to just this
                # item's drops. This lets column headers sort by that item's relevance.
                iw = mission_weight({item: dict(rotations)}, mission)
                text = " ".join(f"{rot}:{chance:.2f}%" for rot, chance in sorted(rotations.items()))
                cells.append({"weight": f"{iw:.4f}", "text": text})
            else:
                cells.append({"weight": "0", "text": None})
        rows.append({"idx": idx, "location": location, "type": mission.get_name(), "weight": f"{mw:.4f}", "cells": cells})

    return render_template(
        "results.html",
        rows=rows,
        columns=item_columns,
        count=len(results),
        num_locations=len(weighted),
        max_results=max_results,
    )


# ============== Web Routes ==============


def _url(rule: str, **options):
    """Register a route at the app root and (when set) under WEB_ROOT.

    Registering both means the app works when served directly
    (e.g. locally, where links point at /warframe/...) as well as
    behind a reverse proxy that strips the /warframe prefix
    (e.g. the production nginx setup).
    """

    def decorator(view):
        app.add_url_rule(rule, view_func=view, **options)
        if WEB_ROOT:
            app.add_url_rule(WEB_ROOT + rule, view_func=view, **options)
        return view

    return decorator


@_url("/")
def index():
    """Main search page.

    GET parameters:
        q: Search query (required for results)
        n: Maximum results to show (0 = all)
        exact: If present/true, require exact item name match (default: partial)
        mission_type: Filter by mission type (comma-separated)
        refresh: If present, request a cache refetch (only applied if the cache is >= 5 minutes old)

    Returns:
        HTML page with search form and optional results table.
    """
    # Parse and validate query parameters from URL.
    # Each parameter is sanitized: trimmed, bounded to prevent abuse/edge cases.
    refresh = parse_bool(request.args.get("refresh"))  # Request cache refetch (guarded by 5-min minimum age)
    query = (request.args.get("q") or "").strip()[:500]  # Search query, max 500 chars
    try:
        num = parse_int(request.args.get("n"), 0, 0, 10_000)  # Clamp to [0, 10000]
    except ValueError:
        num = 0
    exact = parse_bool(request.args.get("exact"))  # Exact match mode (default: partial)
    exact_checked = " checked" if exact else ""  # For checkbox HTML
    mission_types = (request.args.get("mission_type") or "").strip()[:256]  # Mission type filter, max 256 chars

    # Parse mission type filter (comma-separated, max 20 types)
    mission_types_filter = {mt.strip().lower() for mt in mission_types.split(",")[:20] if mt.strip()}

    # Refresh data from API cache if the refresh flag is set.
    # Serve a 503 if no data could be loaded at all (API down, no cache).
    try:
        _parser.refresh(force=refresh)
    except DataUnavailableError as e:
        logger.error("Search unavailable: %s", e)
        return (
            render_template(
                "index.html",
                web_root=app.config["WEB_ROOT"],
                query=query,
                results_html="",
                max_results=num,
                error=str(e),
                mission_type=mission_types or "",
                refresh_qs="",
                cache_age="--",
                stale=False,
            ),
            503,
        )

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

    # Run search (exact or partial match), then apply optional mission type
    # filter. The formatter receives all (unlimited) results so it can
    # compute weights from the full dataset before applying the row limit.
    all_results = run_search(query, exact=exact) if query else []
    if mission_types_filter:
        all_results = [r for r in all_results if r.mission_type.get_name().lower() in mission_types_filter]

    if all_results:
        results_html = format_multi_table_html(all_results, num)
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
        exact_checked=exact_checked,
        mission_type=mission_types or "",
        refresh_qs=refresh_qs,
        cache_age=cache_age,
        stale=stale,
    )


@_url("/api/drops")
def api_drops():
    """API endpoint for drop search (JSON).

    GET parameters:
        q: Search query (required)
        exact: If true, require exact item name match (default: partial)
        mission_type: Filter by mission type (can repeat for multiple)
        n: Maximum results to show (0 = all, max 10000)

    Returns:
        JSON array of drop result objects.
    """
    query = (request.args.get("q") or "").strip()
    if not query:
        return jsonify(error="Missing query parameter 'q'"), 400

    exact = parse_bool(request.args.get("exact"))
    mission_types = {mt.strip().lower() for mt in request.args.getlist("mission_type") if mt.strip()}
    try:
        max_results = parse_int(request.args.get("n"), 0, 0, 10_000)
    except ValueError:
        return jsonify(error="Invalid 'n' parameter: must be an integer"), 400

    try:
        results = run_search(query, exact=exact)
    except DataUnavailableError as e:
        logger.error("Search unavailable: %s", e)
        return jsonify(error="Drop data temporarily unavailable"), 503

    # Apply mission type filter if specified
    if mission_types:
        results = [r for r in results if r.mission_type.get_name().lower() in mission_types]

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


@_url("/api/suggest-items")
def suggest_items():
    """Autocomplete endpoint for item names.

    GET parameters:
        q: Substring to match (case-insensitive)

    Returns:
        JSON array of up to 10 matching item names.
    """
    prefix = (request.args.get("q") or "").lower()
    try:
        data = _parser.get_drop_data()
    except DataUnavailableError:
        return jsonify(error="Drop data temporarily unavailable"), 503
    # Filter items matching prefix, limit to 10
    matches = [item for item, lowered in zip(data.items, data.items_lower) if prefix in lowered][:10]
    return jsonify(matches)


@_url("/api/suggest-mission-types")
def suggest_mission_types():
    """Autocomplete endpoint for mission types.

    GET parameters:
        q: Substring to match (case-insensitive)

    Returns:
        JSON array of up to 10 matching mission types.
    """
    prefix = (request.args.get("q") or "").lower()
    try:
        data = _parser.get_drop_data()
    except DataUnavailableError:
        return jsonify(error="Drop data temporarily unavailable"), 503
    # Filter types matching prefix, limit to 10
    matches = [mt for mt, lowered in zip(data.mission_types, data.mission_types_lower) if prefix in lowered][:10]
    return jsonify(matches)


@_url("/static/<path:filename>")
def static_file(filename):
    """Serve static files (CSS, JS, images) at the app root and under WEB_ROOT.

    Flask serves files from the static_folder configured on app creation.
    This handles requests to /static/* URLs (and /warframe/static/* when
    WEB_ROOT is set, for direct access without a prefix-stripping proxy).

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
