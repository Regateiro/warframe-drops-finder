#!/usr/bin/env python3
"""
Warframe Drop Table Search Tool

Search for items in Warframe's drop tables and find the best locations to farm them.
Data is fetched from drops.warframestat.us and cached locally.
"""
import json
import os
import urllib.error
import urllib.request
from typing import Any

API_URL = "https://drops.warframestat.us/data/all.json"
CACHE_FILE = ".drop_cache.json"


def fetch_drop_data(force_refresh: bool = False) -> dict[str, Any]:
    """Fetch drop data from API or load from cache."""
    if not force_refresh and os.path.exists(CACHE_FILE):
        with open(CACHE_FILE) as f:
            return json.load(f)

    print("Fetching drop data from API...")
    try:
        request = urllib.request.Request(API_URL, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(request, timeout=60) as response:
            data = json.loads(response.read())
    except urllib.error.URLError as e:
        print(f"Failed to fetch data: {e}")
        if os.path.exists(CACHE_FILE):
            print("Using cached data.")
            with open(CACHE_FILE) as f:
                return json.load(f)
        raise SystemExit(1)

    with open(CACHE_FILE, "w") as f:
        json.dump(data, f)
    print("Data cached successfully.")
    return data


def iter_mission_drops(data: dict[str, Any], query: str, exact: bool = False) -> list[tuple[str, float, str, str, str]]:
    """
    Search mission rewards for items matching the query.
    Returns: list of (item_name, chance, location, mission_type, rotation)
    """
    results: list[tuple[str, float, str, str, str]] = []
    query_lower = query.lower()
    match_fn = (lambda item_name: item_name.lower() == query_lower) if exact else (lambda item_name: query_lower in item_name.lower())

    for planet, missions in data.get("missionRewards", {}).items():
        for mission, details in missions.items():
            game_mode = details.get("gameMode", "")
            rewards = details.get("rewards", {})
            location = f"{planet} - {mission}"
            if isinstance(rewards, dict):
                for tier, items in rewards.items():
                    for item in items:
                        item_name = item.get("itemName", "")
                        if match_fn(item_name):
                            results.append((item_name, item["chance"], location, game_mode, tier))
            elif isinstance(rewards, list):
                for item in rewards:
                    item_name = item.get("itemName", "")
                    if match_fn(item_name):
                        results.append((item_name, item["chance"], location, game_mode, "-"))

    return results


def iter_relic_drops(data: dict[str, Any], query: str, exact: bool = False) -> list[tuple[str, float, str, str, str]]:
    """Search relic rewards for items matching the query."""
    results: list[tuple[str, float, str, str, str]] = []
    query_lower = query.lower()
    match_fn = (lambda item_name: item_name.lower() == query_lower) if exact else (lambda item_name: query_lower in item_name.lower())

    for relic in data.get("relics", []):
        tier = relic.get("tier", "")
        relic_name = relic.get("relicName", "")
        state = relic.get("state", "Intact")
        for reward in relic.get("rewards", []):
            item_name = reward.get("itemName", "")
            if match_fn(item_name):
                results.append((item_name, reward["chance"], f"Relic: {tier} {relic_name}", "", state))

    return results


def iter_mod_drops(data: dict[str, Any], query: str, exact: bool = False) -> list[tuple[str, float, str, str, str]]:
    """Search enemy mod drops for mods matching the query."""
    results: list[tuple[str, float, str, str, str]] = []
    query_lower = query.lower()
    match_fn = (lambda item_name: item_name.lower() == query_lower) if exact else (lambda item_name: query_lower in item_name.lower())

    for mod_loc in data.get("modLocations", []):
        mod_name = mod_loc.get("modName", "Unknown")
        for enemy in mod_loc.get("enemies", []):
            enemy_name = enemy.get("enemyName", "")
            if match_fn(mod_name):
                results.append((mod_name, enemy["chance"], f"Mod drop: {enemy_name}", "", "-"))

    return results


def iter_blueprint_drops(data: dict[str, Any], query: str, exact: bool = False) -> list[tuple[str, float, str, str, str]]:
    """Search enemy blueprint drops for blueprints matching the query."""
    results: list[tuple[str, float, str, str, str]] = []
    query_lower = query.lower()
    match_fn = (lambda item_name: item_name.lower() == query_lower) if exact else (lambda item_name: query_lower in item_name.lower())

    for bp_loc in data.get("blueprintLocations", []):
        bp_name = bp_loc.get("blueprintName", bp_loc.get("itemName", "Unknown"))
        for enemy in bp_loc.get("enemies", []):
            item_name = bp_name
            if match_fn(item_name):
                results.append((item_name, enemy["chance"], f"Blueprint: {enemy['enemyName']}", "", "-"))

    return results


def iter_key_drops(data: dict[str, Any], query: str, exact: bool = False) -> list[tuple[str, float, str, str, str]]:
    """Search key rewards for items matching the query."""
    results: list[tuple[str, float, str, str, str]] = []
    query_lower = query.lower()
    match_fn = (lambda item_name: item_name.lower() == query_lower) if exact else (lambda item_name: query_lower in item_name.lower())

    for key in data.get("keyRewards", []):
        key_name = key.get("keyName", "Unknown")
        rewards = key.get("rewards", {})
        if isinstance(rewards, dict):
            for tier, items in rewards.items():
                for item in items:
                    item_name = item.get("itemName", "")
                    if match_fn(item_name):
                        results.append((item_name, item["chance"], f"Key: {key_name}", "", tier))

    return results


def iter_transient_drops(data: dict[str, Any], query: str, exact: bool = False) -> list[tuple[str, float, str, str, str]]:
    """Search transient rewards (e.g., Arbitrations) for items matching the query."""
    results: list[tuple[str, float, str, str, str]] = []
    query_lower = query.lower()
    match_fn = (lambda item_name: item_name.lower() == query_lower) if exact else (lambda item_name: query_lower in item_name.lower())

    for transient in data.get("transientRewards", []):
        place = transient.get("objectiveName", "Unknown")
        for reward in transient.get("rewards", []):
            item_name = reward.get("itemName", "")
            rotation = reward.get("rotation", "")
            if match_fn(item_name):
                results.append((item_name, reward["chance"], f"Transient: {place}", "", rotation or "-"))

    return results


def iter_sortie_drops(data: dict[str, Any], query: str, exact: bool = False) -> list[tuple[str, float, str, str, str]]:
    """Search Sortie rewards for items matching the query."""
    results: list[tuple[str, float, str, str, str]] = []
    query_lower = query.lower()
    match_fn = (lambda item_name: item_name.lower() == query_lower) if exact else (lambda item_name: query_lower in item_name.lower())

    for reward in data.get("sortieRewards", []):
        item_name = reward.get("itemName", "")
        if match_fn(item_name):
            results.append((item_name, reward["chance"], "Sortie", "", "-"))

    return results


def iter_cetus_drops(data: dict[str, Any], query: str, exact: bool = False) -> list[tuple[str, float, str, str, str]]:
    """Search Cetus bounty rewards for items matching the query."""
    results: list[tuple[str, float, str, str, str]] = []
    query_lower = query.lower()
    match_fn = (lambda item_name: item_name.lower() == query_lower) if exact else (lambda item_name: query_lower in item_name.lower())

    for bounty in data.get("cetusBountyRewards", []):
        place = bounty.get("place", "Cetus Bounty")
        rewards = bounty.get("rewards", {})
        if isinstance(rewards, dict):
            for tier, items in rewards.items():
                for item in items:
                    item_name = item.get("itemName", "")
                    if match_fn(item_name):
                        results.append((item_name, item["chance"], f"Cetus: {place}", "", tier))

    return results


def search_items(data: dict[str, Any], query: str, exact: bool = False) -> list[tuple[str, float, str, str, str]]:
    """Search all drop sources for items matching the query."""
    results: list[tuple[str, float, str, str, str]] = []

    results.extend(iter_mission_drops(data, query, exact))
    results.extend(iter_relic_drops(data, query, exact))
    results.extend(iter_mod_drops(data, query, exact))
    results.extend(iter_blueprint_drops(data, query, exact))
    results.extend(iter_key_drops(data, query, exact))
    results.extend(iter_transient_drops(data, query, exact))
    results.extend(iter_sortie_drops(data, query, exact))
    results.extend(iter_cetus_drops(data, query, exact))

    return sorted(results, key=lambda x: x[1], reverse=True)


def format_results(results: list[tuple[str, float, str, str, str]], max_results: int = 20) -> None:
    """
    Format and display results for a single item search.
    Shows item, location, mission type, and rotations side by side.
    """
    if not results:
        print("No results found.")
        return

    # Group by (item, location, mission_type) and track rotations
    grouped: dict[tuple[str, str, str], dict[str, float]] = {}
    for item, chance, location, mission_type, rotation in results:
        key = (item, location, mission_type)
        if key not in grouped:
            grouped[key] = {}
        if rotation not in grouped[key] or grouped[key][rotation] < chance:
            grouped[key][rotation] = chance

    sorted_groups = sorted(grouped.items(), key=lambda x: max(x[1].values()), reverse=True)

    # Calculate column widths based on content
    width_item = max(len("Item"), max(len(k[0]) for k, _ in sorted_groups))
    width_location = max(len("Location"), max(len(k[1]) for k, _ in sorted_groups))
    width_type = max(len("Type"), max(len(k[2]) for k, _ in sorted_groups))
    width_rotations = max(
        len("Rotations"), max(len(", ".join(f"{rot}:{chance:.2f}%" for rot, chance in sorted(rots.items()))) for _, rots in sorted_groups)
    )

    # Build rows to calculate max line length
    header = f"{'Item':<{width_item}} | {'Location':<{width_location}} | {'Type':<{width_type}} | {'Rotations':<{width_rotations}}"
    rows = []
    for (item, location, mission_type), rotations in sorted_groups[:max_results]:
        rot_str = ", ".join(f"{rot}:{chance:.2f}%" for rot, chance in sorted(rotations.items()))
        rows.append(f"{item:<{width_item}} | {location:<{width_location}} | {mission_type:<{width_type}} | {rot_str:<{width_rotations}}")

    max_line_len = max(len(header), max(len(r) for r in rows) if rows else 0)

    print(f"\nFound {len(results)} drops across {len(sorted_groups)} locations. Showing best {max_results}:\n")
    print(header)
    print("-" * max_line_len)
    for row in rows:
        print(row)


def format_multi_results(results: list[tuple[str, float, str, str, str]], queries: list[str], max_results: int = 20) -> None:
    """
    Format and display results for multi-item search.
    Shows each unique item found in its own column with rotation and drop chance.
    Locations are sorted by: most items matched first, then highest drop chance.
    """
    if not results:
        print("No results found.")
        return

    # Group by (location, mission_type) and track items and rotations
    # Strip "Relic" from names for cleaner display
    by_location: dict[tuple[str, str], dict[str, dict[str, float]]] = {}
    for item, chance, location, mission_type, rotation in results:
        key = (location, mission_type)
        display_name = item.replace(" Relic", "")
        if key not in by_location:
            by_location[key] = {}
        if display_name not in by_location[key]:
            by_location[key][display_name] = {}
        if rotation not in by_location[key][display_name] or by_location[key][display_name][rotation] < chance:
            by_location[key][display_name][rotation] = chance

    def location_score(entry: tuple) -> tuple[int, float]:
        """Score locations by number of matching items, then by best drop chance."""
        _, items_dict = entry
        best_chance = max(chance for item_chances in items_dict.values() for chance in item_chances.values())
        return len(items_dict), best_chance

    sorted_locations = sorted(by_location.items(), key=location_score, reverse=True)

    # Get all unique item names found in results, strip "Relic" suffix for cleaner display
    item_columns = sorted(set(item.replace(" Relic", "") for item, _, _, _, _ in results))

    width_num = 3
    width_location = max(len("Location"), max(len(k[0]) for k, _ in sorted_locations))
    width_type = max(len("Type"), max(len(k[1]) for k, _ in sorted_locations))
    width_item = max(len(item) for item in item_columns) if item_columns else 10
    for _, items_dict in sorted_locations:
        for item, rotations in items_dict.items():
            if rotations:
                best_rot_name = max(rotations.keys(), key=lambda x: len(x))
                best_chance = rotations[best_rot_name]
                width_item = max(width_item, len(f"{best_rot_name}:{best_chance:.2f}%"))

    # Build header and rows
    header_parts = [f"{'#':<{width_num}}", f"{'Location':<{width_location}}", f"{'Type':<{width_type}}"]
    for item in item_columns:
        header_parts.append(f"{item:<{width_item}}")
    header = " | ".join(header_parts)

    rows = []
    for idx, ((location, mission_type), items_dict) in enumerate(sorted_locations[:max_results], 1):
        row_parts = [f"{idx:<{width_num}}", f"{location:<{width_location}}", f"{mission_type:<{width_type}}"]
        for item in item_columns:
            if item in items_dict:
                rotations = items_dict[item]
                best_rot = max(rotations.items(), key=lambda x: x[1])
                formatted = f"{best_rot[0]}:{best_rot[1]:.2f}%"
                padded = formatted.ljust(width_item)
                row_parts.append(padded)
            else:
                row_parts.append("-".ljust(width_item))
        rows.append(" | ".join(row_parts))

    max_line_len = max(len(header), max(len(r) for r in rows) if rows else 0)
    sep = "-" * max_line_len

    print(f"\nFound {len(results)} drops across {len(sorted_locations)} locations. Showing best {max_results}:\n")
    print(header)
    print(sep)
    for row in rows:
        print(row)


def main() -> None:
    """Parse arguments and run the drop table search."""
    import argparse

    parser = argparse.ArgumentParser(description="Search Warframe drop tables")
    parser.add_argument("query", nargs="*", help="Item(s) to search for (space or comma separated)")
    parser.add_argument("-r", "--refresh", action="store_true", help="Force refresh cache")
    parser.add_argument("-n", "--num", type=int, default=20, help="Number of results to show")
    parser.add_argument("-e", "--exact", action="store_true", help="Match item names exactly")
    args = parser.parse_args()

    data = fetch_drop_data(force_refresh=args.refresh)

    # Get search queries from args or interactive input
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

    # Search for all items
    all_results: list[tuple[str, float, str, str, str]] = []
    for query in queries:
        query = query.strip()
        if query:
            all_results.extend(search_items(data, query, exact=args.exact))

    all_results = sorted(all_results, key=lambda x: x[1], reverse=True)

    if len(queries) > 1:
        format_multi_results(all_results, queries=queries, max_results=args.num)
    else:
        format_results(all_results, max_results=args.num)


if __name__ == "__main__":
    main()
