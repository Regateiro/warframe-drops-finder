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
        elif self.normalized_path == "/":
            self.handle_index()
        elif self.normalized_path in ("/static/style.css", "/static/sort.js"):
            self.handle_static()
        else:
            self.send_error(404, "Not Found")

    def handle_static(self):
        filename = "style.css" if self.path.endswith(".css") else "sort.js"
        static_path = os.path.join(os.path.dirname(__file__), "static", filename)
        with open(static_path, "rb") as f:
            self.send_response(200)
            self.send_header("Content-Type", "text/css")
            self.end_headers()
            self.wfile.write(f.read())

    def handle_index(self):
        params = parse_qs(urlparse(self.path).query)
        refresh = "refresh" in params
        query = params.get("q", [""])[0]
        num = int(params.get("n", ["0"])[0])
        exact = "exact" in params
        exact_checked = " checked" if exact else ""

        results_html = ""
        if query:
            data = refresh_drop_data() if refresh else fetch_drop_data()
            queries = parse_queries(query)
            all_results = run_search(data, query, exact=exact)
            results = all_results[:num] if num > 0 else all_results

            if results:
                if len(queries) > 1:
                    results_html = format_multi_table_html(all_results, queries, num)
                else:
                    rows = "".join(
                        f"<tr><td>{html_escape(r.item_name)}</td>"
                        f'<td class="chance">{r.chance:.2f}%</td>'
                        f"<td>{html_escape(r.location)}</td>"
                        f"<td>{html_escape(r.mission_type)}</td>"
                        f"<td>{html_escape(r.rotation)}</td></tr>"
                        for r in results
                    )
                    results_html = RESULT_ROWS.format(count=len(results), rows=rows)
            else:
                results_html = NO_RESULTS.format(query=html_escape(query))

        html = INDEX_HTML.format(web_root=WEB_ROOT, query=html_escape(query), num=num, exact_checked=exact_checked, results=results_html)

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
