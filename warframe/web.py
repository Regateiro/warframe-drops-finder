import json
import os
from collections import defaultdict
from html import escape as html_escape
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

from dotenv import load_dotenv

from .fetcher import fetch_drop_data, refresh_drop_data
from .iterators import search_items

load_dotenv()

HOST = os.getenv("HOST", "127.0.0.1")
PORT = int(os.getenv("PORT", "8080"))
WEB_ROOT = os.getenv("WEB_ROOT", "/warframe")

TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "templates")


def load_template(name: str) -> str:
    with open(os.path.join(TEMPLATES_DIR, name), "r") as f:
        return f.read()


INDEX_HTML = load_template("index.html")
RESULT_ROWS = load_template("result_rows.html")
MULTI_RESULT_TABLE = load_template("multi_result_table.html")
NO_RESULTS = load_template("no_results.html")


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


def strip_relic_suffix(name: str) -> str:
    return name.replace(" Relic", "").replace(" (Radiant)", "")


def strip_relic_for_display(name: str) -> str:
    return name.replace(" Relic", "")


def format_multi_table_html(results: list, queries: list[str], max_results: int) -> str:
    by_location: dict = defaultdict(lambda: defaultdict(dict))
    for result in results:
        key = (result.location, result.mission_type)
        if result.rotation not in by_location[key][result.item_name] or by_location[key][result.item_name][result.rotation] < result.chance:
            by_location[key][result.item_name][result.rotation] = result.chance

    def location_score(entry):
        _, items_dict = entry
        best_chance = max(c for v in items_dict.values() for c in v.values())
        return len(items_dict), best_chance

    sorted_locations = sorted(by_location.items(), key=location_score, reverse=True)

    base_items = [strip_relic_suffix(q) for q in queries]

    def make_columns(item_dict: dict) -> list[str]:
        cols = []
        for base in base_items:
            if base in item_dict:
                cols.append(base)
            elif f"{base} Relic" in item_dict:
                cols.append(f"{base} Relic")
            if f"{base} (Radiant)" in item_dict:
                cols.append(f"{base} (Radiant)")
            elif f"{base} Relic (Radiant)" in item_dict:
                cols.append(f"{base} Relic (Radiant)")
        return cols

    if len(queries) > 1:
        item_columns = []
        for _, items_dict in by_location.items():
            for col in make_columns(items_dict):
                if col not in item_columns:
                    item_columns.append(col)
    else:
        item_columns = sorted(set(r.item_name for r in results))

    headers = "".join(f"<th>{html_escape(strip_relic_for_display(item))}</th>" for item in item_columns)

    rows = []
    for idx, ((location, mission_type), items_dict) in enumerate(sorted_locations if max_results == 0 else sorted_locations[:max_results], 1):
        row_cells = f"<td>{idx}</td><td>{html_escape(location)}</td><td>{html_escape(mission_type)}</td>"
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

    return MULTI_RESULT_TABLE.format(count=len(results), locations=unique_locations, headers=headers, rows=row_html)


class DropHandler(BaseHTTPRequestHandler):
    @property
    def normalized_path(self):
        path = urlparse(self.path).path
        if WEB_ROOT and path.startswith(WEB_ROOT):
            path = path.removeprefix(WEB_ROOT)
        return path

    def do_GET(self):
        if self.normalized_path == "/api/drops":
            self.handle_api()
        elif self.normalized_path == "/api/suggest-items":
            self.handle_suggest_items()
        elif self.normalized_path == "/api/suggest-mission-types":
            self.handle_suggest_mission_types()
        elif self.normalized_path == "/":
            self.handle_index()
        elif self.normalized_path in ("/static/style.css", "/static/sort.js", "/static/favicon.png"):
            self.handle_static()
        else:
            self.send_error(404, "Not Found")

    def handle_static(self):
        if self.normalized_path.endswith(".css"):
            content_type = "text/css"
        elif self.normalized_path.endswith(".js"):
            content_type = "application/javascript"
        elif self.normalized_path.endswith(".png"):
            content_type = "image/png"
        else:
            content_type = "application/octet-stream"
        static_path = os.path.join(os.path.dirname(__file__), "static", os.path.basename(self.normalized_path))
        with open(static_path, "rb") as f:
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.end_headers()
            self.wfile.write(f.read())

    def handle_suggest_items(self):
        parsed = urlparse(self.path)
        prefix = parse_qs(parsed.query).get("q", [""])[0].lower()
        data = fetch_drop_data()
        items = get_items(data)
        matches = [item for item in items if prefix in item.lower()][:10]
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(matches).encode())

    def handle_suggest_mission_types(self):
        parsed = urlparse(self.path)
        prefix = parse_qs(parsed.query).get("q", [""])[0].lower()
        data = fetch_drop_data()
        mission_types = get_mission_types(data)
        matches = [mt for mt in mission_types if prefix in mt.lower()][:10]
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(matches).encode())

    def handle_index(self):
        params = parse_qs(urlparse(self.path).query)
        refresh = "refresh" in params
        query = params.get("q", [""])[0]
        num = int(params.get("n", ["0"])[0])
        exact = "exact" in params
        exact_checked = " checked" if exact else ""
        mission_types = params.get("mission_type", [""])[0]

        mission_types_filter = [mt.strip() for mt in mission_types.split(",") if mt.strip()]

        results_html = ""
        if query:
            data = refresh_drop_data() if refresh else fetch_drop_data()
            queries = parse_queries(query)
            all_results = run_search(data, query, exact=exact)

            if mission_types_filter:
                all_results = [r for r in all_results if r.mission_type.lower() in [mt.lower() for mt in mission_types_filter]]

            results = all_results[:num] if num > 0 else all_results

            if results:
                results_html = format_multi_table_html(all_results, queries, num)
            else:
                results_html = NO_RESULTS.format(query=html_escape(query))

        html = INDEX_HTML.format(
            web_root=WEB_ROOT,
            query=html_escape(query),
            num=num,
            exact_checked=exact_checked,
            mission_type=html_escape(mission_types),
            results=results_html,
        )

        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(html.encode())

    def handle_api(self):
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query).get("q", [""])[0]
        if not query:
            self.send_error(400, "Missing query parameter 'q'")
            return

        exact = "exact" in parse_qs(parsed.query)
        mission_types = parse_qs(parsed.query).get("mission_type", [])
        max_results = int(parse_qs(parsed.query).get("n", ["0"])[0])

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

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(output).encode())

    def log_message(self, format, *args):
        print(f"[{self.log_date_time_string()}] {format % args}")


def run_server(host: str = None, port: int = None):
    if host is None:
        host = HOST
    if port is None:
        port = PORT
    server = HTTPServer((host, port), DropHandler)
    print(f"Starting server on http://{host}:{port}")
    print("API endpoint: /api/drops?q=<query>")
    print("Parameters:")
    print("  q - Item name to search for (required)")
    print("  exact - Match exactly (optional)")
    print("  mission_type - Filter by mission type (repeatable)")
    print("  n - Max results (default: 0 for all)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server...")
        server.shutdown()


if __name__ == "__main__":
    run_server()
