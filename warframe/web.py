import os
from collections import defaultdict

from dotenv import load_dotenv
from flask import Flask, jsonify, request, send_from_directory

from warframe.fetcher import fetch_drop_data
from warframe.iterators import search_items

load_dotenv()

app = Flask(__name__, template_folder="templates", static_folder="static")

HOST = os.getenv("HOST", "127.0.0.1")
PORT = int(os.getenv("PORT", "8080"))
WEB_ROOT = os.getenv("WEB_ROOT", "/warframe")

app.config["WEB_ROOT"] = WEB_ROOT


def parse_queries(query: str) -> list[str]:
    return [q.strip() for q in query.split(",") if q.strip()]


def get_unique_items(data: dict) -> list[str]:
    items = set()
    for missions in data.get("missionRewards", {}).values():
        for details in missions.values():
            rewards = details.get("rewards", {})
            if isinstance(rewards, dict):
                for tier_list in rewards.values():
                    for item in tier_list:
                        items.add(item.get("itemName", ""))
            elif isinstance(rewards, list):
                for item in rewards:
                    items.add(item.get("itemName", ""))
    for relic in data.get("relics", []):
        for reward in relic.get("rewards", []):
            items.add(reward.get("itemName", ""))
    for mod_loc in data.get("modLocations", []):
        items.add(mod_loc.get("modName", ""))
    for bp_loc in data.get("blueprintLocations", []):
        items.add(bp_loc.get("blueprintName", bp_loc.get("itemName", "")))
        items.add(bp_loc.get("itemName", ""))
    for key in data.get("keyRewards", []):
        rewards = key.get("rewards", {})
        if isinstance(rewards, dict):
            for tier_list in rewards.values():
                for item in tier_list:
                    items.add(item.get("itemName", ""))
    for transient in data.get("transientRewards", []):
        for reward in transient.get("rewards", []):
            items.add(reward.get("itemName", ""))
    for reward in data.get("sortieRewards", []):
        items.add(reward.get("itemName", ""))
    for bounty in data.get("cetusBountyRewards", []):
        rewards = bounty.get("rewards", {})
        if isinstance(rewards, dict):
            for tier_list in rewards.values():
                for item in tier_list:
                    items.add(item.get("itemName", ""))
    return sorted(items)


def get_unique_mission_types(data: dict) -> list[str]:
    mission_types = set()
    for missions in data.get("missionRewards", {}).values():
        for details in missions.values():
            game_mode = details.get("gameMode", "")
            if game_mode:
                mission_types.add(game_mode)
    return sorted(mission_types)


_items_cache = None
_mission_types_cache = None


def _clear_caches():
    global _items_cache, _mission_types_cache
    _items_cache = None
    _mission_types_cache = None


def get_items(data: dict) -> list[str]:
    global _items_cache
    if _items_cache is None:
        _items_cache = get_unique_items(data)
    return _items_cache


def get_mission_types(data: dict) -> list[str]:
    global _mission_types_cache
    if _mission_types_cache is None:
        _mission_types_cache = get_unique_mission_types(data)
    return _mission_types_cache


def run_search(data: dict, query: str, exact: bool) -> list:
    queries = parse_queries(query)
    results = []
    for q in queries:
        results.extend(search_items(data, q, exact=exact))
    return sorted(results, key=lambda x: x.chance, reverse=True)


def format_multi_table_html(results: list, queries: list[str], max_results: int) -> str:
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
        '<table class="sortable"><thead><tr>'
        "<th>#</th><th>Location</th><th>Type</th>" + headers + "</tr></thead><tbody>" + row_html + "</tbody></table></div>"
    )


INDEX_HTML = None
MULTI_RESULT_TABLE = None
NO_RESULTS = None


@app.before_request
def load_templates():
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
    refresh = "refresh" in request.args
    query = request.args.get("q", "")
    num = int(request.args.get("n", "0"))
    exact = "exact" in request.args
    exact_checked = " checked" if exact else ""
    mission_types = request.args.get("mission_type", "")
    mission_types_filter = [mt.strip() for mt in mission_types.split(",")]

    results_html = ""
    if query:
        data = fetch_drop_data(force_refresh=refresh)
        queries = parse_queries(query)
        all_results = run_search(data, query, exact=exact)

        if mission_types_filter:
            all_results = [r for r in all_results if r.mission_type.lower() in [mt.lower() for mt in mission_types_filter]]

        results = all_results[:num] if num > 0 else all_results

        if results:
            results_html = format_multi_table_html(all_results, queries, num)
        else:
            results_html = NO_RESULTS.format(query=query)

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
    query = request.args.get("q", "")
    if not query:
        return jsonify(error="Missing query parameter 'q'"), 400

    exact = "exact" in request.args
    mission_types = request.args.getlist("mission_type")
    max_results = int(request.args.get("n", "0"))

    data = fetch_drop_data()
    results = run_search(data, query, exact=exact)

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
    _clear_caches()
    prefix = request.args.get("q", "").lower()
    data = fetch_drop_data()
    items = get_items(data)
    matches = [item for item in items if prefix in item.lower()][:10]
    return jsonify(matches)


@app.route("/api/suggest-mission-types")
def suggest_mission_types():
    _clear_caches()
    prefix = request.args.get("q", "").lower()
    data = fetch_drop_data()
    mission_types = get_mission_types(data)
    matches = [mt for mt in mission_types if prefix in mt.lower()][:10]
    return jsonify(matches)


@app.route("/static/<path:filename>")
def static_file(filename):
    return send_from_directory(app.static_folder, filename)


def run_server(host=None, port=None):
    if host is None:
        host = HOST
    if port is None:
        port = PORT
    print(f"Starting server on http://{host}:{port}")
    print("API endpoint: /api/drops?q=<query>")
    app.run(host=host, port=port)


def create_app():
    return app


if __name__ == "__main__":
    run_server()
