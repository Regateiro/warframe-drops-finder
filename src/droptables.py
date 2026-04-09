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
from collections import defaultdict
from itertools import chain
from typing import Any

API_URL = "https://drops.warframestat.us/data/all.json"
CACHE_FILE = ".drop_cache.json"

# Each drop result contains: (item_name, drop_chance, location, mission_type, rotation)
# - item_name: what drops (e.g., "Forma", "Neurodes")
# - drop_chance: percentage chance (e.g., 5.0 for 5%)
# - location: where it drops (e.g., "Earth - Ceres")
# - mission_type: game mode like "Survival", "Spy", etc.
# - rotation: A/B/C for missions, relic state like "Intact" for relics, "-" for others
DropResult = tuple[str, float, str, str, str]


def make_match_fn(query: str, exact: bool) -> callable:
    """
    Create a match function for item name matching.

    Args:
        query: The search term
        exact: If True, match exact names (case-insensitive).
               If False, match items containing the query (substring match).

    Returns:
        A function that takes an item name and returns True if it matches.
    """
    query_lower = query.lower()
    return (lambda name: name.lower() == query_lower) if exact else (lambda name: query_lower in name.lower())


def fetch_drop_data(force_refresh: bool = False) -> dict[str, Any]:
    """
    Fetch drop data from API or load from cache.

    The API returns a large JSON with all drop tables including missions,
    relics, mods, blueprints, keys, transients, sorties, and Cetus bounties.

    Args:
        force_refresh: If True, ignore cache and fetch fresh data.

    Returns:
        The parsed JSON data from the API.
    """
    # Try cache first unless force refresh is requested
    if not force_refresh and os.path.exists(CACHE_FILE):
        with open(CACHE_FILE) as f:
            return json.load(f)

    print("Fetching drop data from API...")
    try:
        # Some APIs require a User-Agent header to avoid being blocked
        request = urllib.request.Request(API_URL, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(request, timeout=60) as response:
            data = json.loads(response.read())
    except urllib.error.URLError as e:
        print(f"Failed to fetch data: {e}")
        # Fall back to cache if available (network issues, rate limiting, etc.)
        if os.path.exists(CACHE_FILE):
            print("Using cached data.")
            with open(CACHE_FILE) as f:
                return json.load(f)
        raise SystemExit(1)

    # Cache the data for next time
    with open(CACHE_FILE, "w") as f:
        json.dump(data, f)
    print("Data cached successfully.")
    return data


def iter_mission_drops(data: dict[str, Any], query: str, exact: bool = False) -> list[DropResult]:
    """
    Search mission rewards for items matching the query.

    Mission rewards are organized by planet -> mission -> rewards.
    Rewards can be a dict (with rotation tiers A/B/C) or a flat list.
    """
    results: list[DropResult] = []
    match_fn = make_match_fn(query, exact)

    for planet, missions in data.get("missionRewards", {}).items():
        for mission, details in missions.items():
            game_mode = details.get("gameMode", "")
            rewards = details.get("rewards", {})
            location = f"{planet} - {mission}"

            # Rewards can be structured two ways:
            # 1. Dict with rotation tiers: {"A": [...], "B": [...], "C": [...]}
            # 2. Flat list (no rotation): [...]
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


def iter_relic_drops(data: dict[str, Any], query: str, exact: bool = False) -> list[DropResult]:
    """
    Search relic rewards for items matching the query.

    Relics contain vaulted/unvaulted items with different drop rates
    based on their state: Intact, Exceptional, Flawless, or Radiant.
    """
    results: list[DropResult] = []
    match_fn = make_match_fn(query, exact)

    for relic in data.get("relics", []):
        tier = relic.get("tier", "")  # Lith, Meso, Neo, Axi, Requiem
        relic_name = relic.get("relicName", "")  # A1, B2, etc.
        state = relic.get("state", "Intact")  # Intact by default
        for reward in relic.get("rewards", []):
            item_name = reward.get("itemName", "")
            if match_fn(item_name):
                results.append((item_name, reward["chance"], f"Relic: {tier} {relic_name}", "", state))

    return results


def iter_mod_drops(data: dict[str, Any], query: str, exact: bool = False) -> list[DropResult]:
    """
    Search enemy mod drops for mods matching the query.

    Mods are tied to specific enemies. The same mod can drop from
    multiple enemies with different drop rates.
    """
    results: list[DropResult] = []
    match_fn = make_match_fn(query, exact)

    for mod_loc in data.get("modLocations", []):
        mod_name = mod_loc.get("modName", "Unknown")
        for enemy in mod_loc.get("enemies", []):
            enemy_name = enemy.get("enemyName", "")
            if match_fn(mod_name):
                results.append((mod_name, enemy["chance"], f"Mod drop: {enemy_name}", "", "-"))

    return results


def iter_blueprint_drops(data: dict[str, Any], query: str, exact: bool = False) -> list[DropResult]:
    """Search enemy blueprint drops for blueprints matching the query."""
    results: list[DropResult] = []
    match_fn = make_match_fn(query, exact)

    for bp_loc in data.get("blueprintLocations", []):
        bp_name = bp_loc.get("blueprintName", bp_loc.get("itemName", "Unknown"))
        for enemy in bp_loc.get("enemies", []):
            item_name = bp_name
            if match_fn(item_name):
                results.append((item_name, enemy["chance"], f"Blueprint: {enemy['enemy_name']}", "", "-"))

    return results


def iter_key_drops(data: dict[str, Any], query: str, exact: bool = False) -> list[DropResult]:
    """Search key rewards for items matching the query."""
    results: list[DropResult] = []
    match_fn = make_match_fn(query, exact)

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


def iter_transient_drops(data: dict[str, Any], query: str, exact: bool = False) -> list[DropResult]:
    """
    Search transient rewards for items matching the query.

    Transient rewards include Arbitrations, Kavor Defectors, and other
    time-limited or event-based content.
    """
    results: list[DropResult] = []
    match_fn = make_match_fn(query, exact)

    for transient in data.get("transientRewards", []):
        place = transient.get("objectiveName", "Unknown")
        for reward in transient.get("rewards", []):
            item_name = reward.get("itemName", "")
            rotation = reward.get("rotation", "")
            if match_fn(item_name):
                results.append((item_name, reward["chance"], f"Transient: {place}", "", rotation or "-"))

    return results


def iter_sortie_drops(data: dict[str, Any], query: str, exact: bool = False) -> list[DropResult]:
    """Search Sortie rewards for items matching the query."""
    results: list[DropResult] = []
    match_fn = make_match_fn(query, exact)

    for reward in data.get("sortieRewards", []):
        item_name = reward.get("itemName", "")
        if match_fn(item_name):
            results.append((item_name, reward["chance"], "Sortie", "", "-"))

    return results


def iter_cetus_drops(data: dict[str, Any], query: str, exact: bool = False) -> list[DropResult]:
    """
    Search Cetus bounty rewards for items matching the query.

    Cetus bounties on Earth have reward tables organized by stage tier.
    """
    results: list[DropResult] = []
    match_fn = make_match_fn(query, exact)

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


# List of all iterator functions that search different drop sources.
# Each returns a list of DropResult tuples.
ITERATORS = [
    iter_mission_drops,  # Regular mission rewards (missions have A/B/C rotations)
    iter_relic_drops,  # Relic rewards (Intact/Exceptional/Flawless/Radiant states)
    iter_mod_drops,  # Mod drops from enemies (e.g., Bite from Tamm)
    iter_blueprint_drops,  # Blueprint drops from enemies
    iter_key_drops,  # Key rewards (now mostly deprecated)
    iter_transient_drops,  # Arbitrations and similar time-limited content
    iter_sortie_drops,  # Daily Sortie rewards
    iter_cetus_drops,  # Cetus bounty rewards
]


def search_items(data: dict[str, Any], query: str, exact: bool = False) -> list[DropResult]:
    """
    Search all drop sources for items matching the query.

    Combines results from all iterator functions and sorts by drop chance
    (highest first) so users see the best farming locations at the top.

    Args:
        data: The full drop table data from the API
        query: Item name to search for
        exact: If True, match exact names. If False, use substring matching.

    Returns:
        List of DropResult tuples sorted by drop chance (descending).
    """
    # Run all iterators and flatten results into one list
    results = list(chain.from_iterable(it(data, query, exact) for it in ITERATORS))
    # Sort by chance (index 1) descending - best drops first
    return sorted(results, key=lambda x: x[1], reverse=True)


def format_results(results: list[DropResult], max_results: int = 20) -> None:
    """
    Format and display results for a single item search.

    Groups results by (item, location, mission_type) to consolidate
    rotations, then displays them in an aligned table format.

    Output format:
    Item | Location | Type | Rotations
    """
    if not results:
        print("No results found.")
        return

    # Group by (item, location, mission_type) and track all rotations per group
    # This collapses duplicate entries for the same location into one row
    grouped: dict[tuple[str, str, str], dict[str, float]] = defaultdict(dict)
    for item, chance, location, mission_type, rotation in results:
        key = (item, location, mission_type)
        # Keep the highest chance for each rotation
        if rotation not in grouped[key] or grouped[key][rotation] < chance:
            grouped[key][rotation] = chance

    # Sort by highest single rotation chance
    sorted_groups = sorted(grouped.items(), key=lambda x: max(x[1].values()), reverse=True)

    # Calculate column widths to align output
    width_item = max(len("Item"), max(len(k[0]) for k, _ in sorted_groups))
    width_location = max(len("Location"), max(len(k[1]) for k, _ in sorted_groups))
    width_type = max(len("Type"), max(len(k[2]) for k, _ in sorted_groups))
    # Rotations column shows all rotations for this item at this location
    width_rotations = max(
        len("Rotations"),
        max(len(", ".join(f"{rot}:{chance:.2f}%" for rot, chance in sorted(rots.items()))) for _, rots in sorted_groups),
    )

    # Build the table
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


def format_multi_results(results: list[DropResult], queries: list[str], max_results: int = 20) -> None:
    """
    Format and display results for multi-item search.

    Groups results by location and shows which of the searched items
    drop at each location. Locations are sorted by:
    1. Most items from the search found at that location
    2. Highest drop chance

    Output format:
    # | Location | Type | Item1 | Item2 | ...
    """
    if not results:
        print("No results found.")
        return

    # Group by location, then by item, tracking rotations for each
    # Structure: {(location, mission_type): {item_name: {rotation: chance}}}
    by_location: dict[tuple[str, str], dict[str, dict[str, float]]] = defaultdict(lambda: defaultdict(dict))
    for item, chance, location, mission_type, rotation in results:
        key = (location, mission_type)
        # Remove " Relic" suffix for cleaner display (e.g., "Lith A1 Relic" -> "Lith A1")
        display_name = item.replace(" Relic", "")
        if rotation not in by_location[key][display_name] or by_location[key][display_name][rotation] < chance:
            by_location[key][display_name][rotation] = chance

    # Score locations: more matching items = better, then higher best chance
    def location_score(entry: tuple) -> tuple[int, float]:
        _, items_dict = entry
        best_chance = max(c for v in items_dict.values() for c in v.values())
        return len(items_dict), best_chance

    sorted_locations = sorted(by_location.items(), key=location_score, reverse=True)

    # Get unique item names found, sorted alphabetically
    item_columns = sorted(set(item.replace(" Relic", "") for item, _, _, _, _ in results))

    # Calculate column widths
    width_num = 3
    width_location = max(len("Location"), max(len(k[0]) for k, _ in sorted_locations))
    width_type = max(len("Type"), max(len(k[1]) for k, _ in sorted_locations))
    # Item columns need to fit either the item name or "Rot:Chance%"
    width_item = max(len(item) for item in item_columns) if item_columns else 10
    for _, items_dict in sorted_locations:
        for _, rotations in items_dict.items():
            if rotations:
                # Find rotation with highest chance to determine column width
                best_rot = max(rotations.items(), key=lambda x: x[1])
                width_item = max(width_item, len(f"{best_rot[0]}:{best_rot[1]:.2f}%"))

    # Build header with item names as column headers
    header_parts = [f"{'#':<{width_num}}", f"{'Location':<{width_location}}", f"{'Type':<{width_type}}"]
    for item in item_columns:
        header_parts.append(f"{item:<{width_item}}")
    header = " | ".join(header_parts)

    # Build data rows
    rows = []
    for idx, ((location, mission_type), items_dict) in enumerate(sorted_locations[:max_results], 1):
        row_parts = [f"{idx:<{width_num}}", f"{location:<{width_location}}", f"{mission_type:<{width_type}}"]
        for item in item_columns:
            if item in items_dict:
                rotations = items_dict[item]
                best_rot = max(rotations.items(), key=lambda x: x[1])
                row_parts.append(f"{best_rot[0]}:{best_rot[1]:.2f}%".ljust(width_item))
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
    parser.add_argument("-m", "--mission-type", action="append", default=[], help="Filter by mission type (can be specified multiple times)")
    args = parser.parse_args()

    data = fetch_drop_data(force_refresh=args.refresh)

    # Get search queries from args or interactive input
    if not args.query:
        # Interactive mode: prompt for input
        input_str = input("Enter item name(s) to search (comma or space separated): ").strip()
        if not input_str:
            print("No search query provided.")
            return
        # Support both comma and space separated items
        queries = input_str.replace(",", " ").split()
    else:
        # Command line mode: allow comma-separated within each arg
        queries = []
        for q in args.query:
            queries.extend(q.split(","))

    # Search for all items
    all_results: list[DropResult] = []
    for query in queries:
        query = query.strip()
        if query:
            all_results.extend(search_items(data, query, exact=args.exact))

    # Filter by mission type if specified
    if args.mission_type:
        mission_types_lower = [mt.lower() for mt in args.mission_type]
        all_results = [r for r in all_results if r[3].lower() in mission_types_lower]

    # Sort combined results by chance
    all_results = sorted(all_results, key=lambda x: x[1], reverse=True)

    # Use multi-column format for multiple items, single-column for one item
    if len(queries) > 1:
        format_multi_results(all_results, queries=queries, max_results=args.num)
    else:
        format_results(all_results, max_results=args.num)


if __name__ == "__main__":
    main()
