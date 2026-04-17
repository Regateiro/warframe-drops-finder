import argparse

from .fetcher import fetch_drop_data
from .formatters import format_multi_results
from .iterators import search_items


def main() -> None:
    parser = argparse.ArgumentParser(description="Search Warframe drop tables")
    parser.add_argument("query", nargs="*", help="Item(s) to search for (space or comma separated)")
    parser.add_argument("-r", "--refresh", action="store_true", help="Force refresh cache")
    parser.add_argument("-n", "--num", type=int, default=20, help="Number of results to show")
    parser.add_argument("-e", "--exact", action="store_true", help="Match item names exactly")
    parser.add_argument("-m", "--mission-type", action="append", default=[], help="Filter by mission type (can be specified multiple times)")
    args = parser.parse_args()

    data = fetch_drop_data(force_refresh=args.refresh)

    if not args.query:
        input_str = input("Enter item name(s) to search (comma or space separated): ").strip()
        if not input_str:
            print("No search query provided.")
            return
        queries = input_str.replace(",", " ").split()
    else:
        queries = []
        for q in args.query:
            queries.extend(q.split(","))

    all_results = []
    for query in queries:
        query = query.strip()
        if query:
            all_results.extend(search_items(data, query, exact=args.exact))

    if args.mission_type:
        mission_types_lower = [mt.lower() for mt in args.mission_type]
        all_results = [r for r in all_results if r.mission_type.lower() in mission_types_lower]

    all_results = sorted(all_results, key=lambda x: x.chance, reverse=True)

    format_multi_results(all_results, queries=queries, max_results=args.num)


if __name__ == "__main__":
    main()
