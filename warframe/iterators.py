"""
Search iterators for Warframe drop table data.

This module provides functions for iterating over different sources
of drop table data from the Warframe game. Each iterator searches
a specific data source (missions, relics, mods, etc.) and returns
matching DropResult objects sorted by drop chance (descending).

The iterators work on the raw dictionary data structure from the API.
Each function takes the data dictionary, a query string, and an optional
exact flag to control substring vs exact matching.
"""

import re
from itertools import chain
from typing import Any, Callable

from .models import DropResult, Mission


def make_match_fn(query: str, exact: bool) -> Callable[[str], bool]:
    """Create a case-insensitive match function for item names.

    This factory function creates a predicate function that tests whether
    an item name matches the given query. The matching is always case-insensitive.

    Args:
        query: The search query string.
        exact: If True, match item names exactly (case-insensitive).
               If False, match as substring (query must be contained in item name).

    Returns:
        A callable that takes an item name string and returns True if it matches the query.
    """
    return lambda name: (query.lower() == name.lower() if exact else query.lower() in name.lower())


# ============== Mission Drop Tables ==============


def iter_mission_drops(data: dict[str, Any], query: str, exact: bool = False) -> list[DropResult]:
    """Search mission drop tables for matching items.

    Mission drops come from regular gameplay missions on different planets.
    Each planet has multiple missions, each with a game mode and rewards.
    Rewards can be structured as a dict {tier: [items]} or a flat list [items].

    Source data structure:
        data["missionRewards"] = {
            planet: {
                mission: {
                    gameMode: "Survival" | "Exterminate" | ...,
                    rewards: {tier: [items]}  OR  [items]
                }
            }
        }

    Args:
        data: Full drop table data dictionary from the API.
        query: Search string to match against item names.
        exact: If True, require exact match. If False, substring match.

    Returns:
        List of DropResult for items matching the query.
    """
    results: list[DropResult] = []
    match_fn = make_match_fn(query, exact)

    # Iterate over each planet (Earth, Mars, Venus, etc.)
    for planet, missions in data.get("missionRewards", {}).items():
        # Iterate over each mission on this planet
        for mission, details in missions.items():
            game_mode = details.get("gameMode", "")
            rewards = details.get("rewards", {})
            # Location format: "Planet - Mission Name"
            location = f"{planet} - {mission}"

            # Rewards can be a dict {tier: [items]} or list [items]
            if isinstance(rewards, dict):
                # Dict format: rewards have rotation tiers (A, B, C)
                for tier, items in rewards.items():
                    for item in items:
                        item_name = item.get("itemName", "")
                        if match_fn(item_name):
                            results.append(DropResult(item_name, item["chance"], location, Mission(game_mode), tier))
            elif isinstance(rewards, list):
                # List format: no rotation tier, use "-" as placeholder
                for item in rewards:
                    item_name = item.get("itemName", "")
                    if match_fn(item_name):
                        results.append(DropResult(item_name, item["chance"], location, Mission(game_mode), "-"))

    return results


# ============== Relic Drop Tables ==============


def iter_relic_drops(data: dict[str, Any], query: str, exact: bool = False) -> list[DropResult]:
    """Search vaulted relic drops for matching items.

    Relic drops come from opening Void Relics in the Refinery.
    Each relic has a tier (Lith, Meso, Neo, Axi), a name, and a state.
    The state affects the drop chances (Intact, Exceptional, Radiant, etc.).

    Source data structure:
        data["relics"] = [
            {
                tier: "Lith" | "Meso" | "Neo" | "Axi",
                relicName: "A1" | "B2" | ...,
                state: "Intact" | "Exceptional" | "Radiant",
                rewards: [{itemName, chance}]
            }
        ]

    Args:
        data: Full drop table data dictionary from the API.
        query: Search string to match against item names.
        exact: If True, require exact match. If False, substring match.

    Returns:
        List of DropResult for items matching the query.
    """
    results: list[DropResult] = []
    match_fn = make_match_fn(query, exact)

    # Iterate over each relic
    for relic in data.get("relics", []):
        tier = relic.get("tier", "")
        relic_name = relic.get("relicName", "")
        state = relic.get("state", "Intact")
        for reward in relic.get("rewards", []):
            item_name = reward.get("itemName", "")
            if match_fn(item_name):
                # Location format: "Relic: TIER NAME" (e.g., "Relic: Lith A1")
                # Rotation field stores the relic state
                results.append(
                    DropResult(
                        item_name,
                        reward["chance"],
                        f"Relic: {tier} {relic_name}",
                        Mission(""),
                        state,
                    )
                )

    return results


# ============== Mod Drop Tables ==============


def iter_mod_drops(data: dict[str, Any], query: str, exact: bool = False) -> list[DropResult]:
    """Search enemy drop mod locations.

    Certain mods drop from specific enemy types. This iterates over
    mod locations which list which enemies can drop each mod.

    Source data structure:
        data["modLocations"] = [
            {
                modName: "Steel Charge" | ...,
                enemies: [{enemyName, chance}]
            }
        ]

    Args:
        data: Full drop table data dictionary from the API.
        query: Search string to match against item names.
        exact: If True, require exact match. If False, substring match.

    Returns:
        List of DropResult for items matching the query.
    """
    results: list[DropResult] = []
    match_fn = make_match_fn(query, exact)

    # Iterate over each mod location
    for mod_loc in data.get("modLocations", []):
        mod_name = mod_loc.get("modName", "Unknown")
        for enemy in mod_loc.get("enemies", []):
            enemy_name = enemy.get("enemyName", "")
            if match_fn(mod_name):
                # Location format: "Mod drop: Enemy Name"
                results.append(DropResult(mod_name, enemy["chance"], f"Mod drop: {enemy_name}", Mission(""), "-"))

    return results


# ============== Blueprint Drop Tables ==============


def iter_blueprint_drops(data: dict[str, Any], query: str, exact: bool = False) -> list[DropResult]:
    """Search enemy drop blueprint locations.

    Blueprints (component parts for Warframes and weapons) drop from enemies.
    This iterates over blueprint locations which list which enemies drop each blueprint.

    Source data structure:
        data["blueprintLocations"] = [
            {
                blueprintName: "Chassis" | ...,
                itemName: "Rhino Chassis" | ...,  # fallback if no blueprintName
                enemies: [{enemyName, chance}]
            }
        ]

    Args:
        data: Full drop table data dictionary from the API.
        query: Search string to match against item names.
        exact: If True, require exact match. If False, substring match.

    Returns:
        List of DropResult for items matching the query.
    """
    results: list[DropResult] = []
    match_fn = make_match_fn(query, exact)

    # Iterate over each blueprint location
    for bp_loc in data.get("blueprintLocations", []):
        # Use blueprintName if available, fall back to itemName
        bp_name = bp_loc.get("blueprintName", bp_loc.get("itemName", "Unknown"))
        for enemy in bp_loc.get("enemies", []):
            item_name = bp_name
            if match_fn(item_name):
                # Location format: "Blueprint: Enemy Name"
                results.append(
                    DropResult(
                        item_name,
                        enemy["chance"],
                        f"Blueprint: {enemy['enemyName']}",
                        Mission(""),
                        "-",
                    )
                )

    return results


# ============== Key Drop Tables ==============


def iter_key_drops(data: dict[str, Any], query: str, exact: bool = False) -> list[DropResult]:
    """Search mission key reward tables.

    Mission keys (Junction keys, Orokin keys, etc.) unlock specific missions.
    Each key has rewards organized by tier.

    Source data structure:
        data["keyRewards"] = [
            {
                keyName: "J3" | ...,
                rewards: {tier: [items]}
            }
        ]

    Args:
        data: Full drop table data dictionary from the API.
        query: Search string to match against item names.
        exact: If True, require exact match. If False, substring match.

    Returns:
        List of DropResult for items matching the query.
    """
    results: list[DropResult] = []
    match_fn = make_match_fn(query, exact)

    # Iterate over each key
    for key in data.get("keyRewards", []):
        key_name = key.get("keyName", "Unknown")
        rewards = key.get("rewards", {})
        if isinstance(rewards, dict):
            for tier, items in rewards.items():
                for item in items:
                    item_name = item.get("itemName", "")
                    if match_fn(item_name):
                        # Location format: "Key: Key Name"
                        results.append(DropResult(item_name, item["chance"], f"Key: {key_name}", Mission(""), tier))

    return results


# ============== Transient Drop Tables ==============


def iter_transient_drops(data: dict[str, Any], query: str, exact: bool = False) -> list[DropResult]:
    """Search transient mission rewards (Rush, Defection, etc.).

    Transient missions are special game modes that appear periodically.
    They reward items with specific rotations (A, B, C) that affect drop chances.

    Source data structure:
        data["transientRewards"] = [
            {
                objectiveName: "Defection" | "Rush" | ...,
                rewards: [{itemName, chance, rotation}]
            }
        ]

    Args:
        data: Full drop table data dictionary from the API.
        query: Search string to match against item names.
        exact: If True, require exact match. If False, substring match.

    Returns:
        List of DropResult for items matching the query.
    """
    results: list[DropResult] = []
    match_fn = make_match_fn(query, exact)

    # Iterate over each transient mission type
    for transient in data.get("transientRewards", []):
        place = transient.get("objectiveName", "Unknown")
        for reward in transient.get("rewards", []):
            item_name = reward.get("itemName", "")
            rotation = reward.get("rotation", "")
            if match_fn(item_name):
                # Location format: "Transient: Mission Name"
                # Use "-" as placeholder if no rotation specified
                results.append(
                    DropResult(
                        item_name,
                        reward["chance"],
                        f"Transient: {place}",
                        Mission(""),
                        rotation or "-",
                    )
                )

    return results


# ============== Sortie Drop Tables ==============


def iter_sortie_drops(data: dict[str, Any], query: str, exact: bool = False) -> list[DropResult]:
    """Search Sortie reward tables.

    Sorties are daily special missions with three stages. Each day has
    random mission types and a single reward table.

    Source data structure:
        data["sortieRewards"] = [
            {itemName, chance}
        ]

    Args:
        data: Full drop table data dictionary from the API.
        query: Search string to match against item names.
        exact: If True, require exact match. If False, substring match.

    Returns:
        List of DropResult for items matching the query.
    """
    results: list[DropResult] = []
    match_fn = make_match_fn(query, exact)

    # Iterate over each sortie reward
    for reward in data.get("sortieRewards", []):
        item_name = reward.get("itemName", "")
        if match_fn(item_name):
            # Location is always "Sortie"
            results.append(DropResult(item_name, reward["chance"], "Sortie", Mission(""), "-"))

    return results


# ============== Bounty Drop Tables (Dynamic) ==============


def _find_bounty_keys(data: dict[str, Any]) -> list[str]:
    """Detect bounty reward keys by structure.

    Scans all top-level keys in the data dict and returns those whose
    values are lists of dicts containing both 'bountyLevel' and 'rewards'.

    Args:
        data: Full drop table data dictionary from the API.

    Returns:
        List of key names that match the bounty table structure.
    """
    bounty_keys: list[str] = []
    for key, value in data.items():
        if isinstance(value, list) and value and isinstance(value[0], dict):
            if "bountyLevel" in value[0] and "rewards" in value[0]:
                bounty_keys.append(key)
    return bounty_keys


def _camel_to_title(name: str) -> str:
    """Convert a camelCase key to a title-case location name.

    Examples:
        "cetusBountyRewards" -> "Cetus"
        "deimosRewards" -> "Deimos"
        "solarisBountyRewards" -> "Solaris"
        "entratiLabRewards" -> "Entrati Lab"
        "hexRewards" -> "Hex"

    Strips common suffixes ('Rewards', 'BountyRewards') then splits
    camelCase boundaries into words.

    Args:
        name: A camelCase string.

    Returns:
        Title-cased location name.
    """
    # Strip suffixes that don't contribute to the location name
    stripped = re.sub(r"(?:Bounty)?Rewards$", "", name)
    # Insert space before uppercase letters that follow lowercase letters
    words = re.sub(r"([a-z])([A-Z])", r"\1 \2", stripped)
    return words.title()


def iter_bounty_drops(data: dict[str, Any], query: str, exact: bool = False) -> list[DropResult]:
    """Search all bounty reward tables for matching items.

    Automatically discovers bounty tables by scanning for top-level keys
    whose values are lists of dicts with 'bountyLevel' and 'rewards' fields.
    New bounty sources added to the API are picked up without code changes.

    Source data structure (all bounty tables share this shape):
        data[key] = [
            {
                bountyLevel: "Level 5 - 15 Cambion Drift Bounty",
                rewards: {tier: [items]}
            }
        ]

    Args:
        data: Full drop table data dictionary from the API.
        query: Search string to match against item names.
        exact: If True, require exact match. If False, substring match.

    Returns:
        List of DropResult for items matching the query.
    """
    results: list[DropResult] = []
    match_fn = make_match_fn(query, exact)

    for key in _find_bounty_keys(data):
        location_prefix = _camel_to_title(key)
        for bounty in data[key]:
            place = bounty.get("bountyLevel", f"{location_prefix} Bounty")
            rewards = bounty.get("rewards", {})
            if isinstance(rewards, dict):
                for tier, items in rewards.items():
                    for item in items:
                        item_name = item.get("itemName", "")
                        if match_fn(item_name):
                            results.append(DropResult(item_name, item["chance"], f"{location_prefix}: {place}", Mission(""), tier))

    return results


# ============== Combined Search ==============

# All iterators combined - used by search_items()
# This list makes it easy to iterate over all data sources at once
ITERATORS: list[Callable[[dict[str, Any], str, bool], list[DropResult]]] = [
    iter_mission_drops,
    iter_relic_drops,
    iter_mod_drops,
    iter_blueprint_drops,
    iter_key_drops,
    iter_transient_drops,
    iter_sortie_drops,
    iter_bounty_drops,
]


def search_items(data: dict[str, Any], query: str, exact: bool = False) -> list[DropResult]:
    """Search all drop sources for matching items.

    This is the main entry point for searching across all data sources.
    It runs each iterator function and combines the results,
    then sorts by drop chance (highest first).

    Args:
        data: Full drop table data dictionary from the API.
        query: Search string to match against item names.
        exact: If True, require exact match. If False, substring match.

    Returns:
        All matching DropResult objects sorted by chance descending.
    """
    # Chain results from all iterators together into one flat list
    results = list(chain.from_iterable(it(data, query, exact) for it in ITERATORS))
    # Sort by chance (highest first)
    return sorted(results, key=lambda x: x.chance, reverse=True)
