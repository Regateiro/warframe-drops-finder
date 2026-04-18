"""Search iterators for Warframe drop table data.

Each iterator searches a specific data source (missions, relics, mods, etc.) and returns
matching DropResult objects sorted by drop chance (descending).
"""

from itertools import chain
from typing import Any, Callable

from .models import DropResult


def make_match_fn(query: str, exact: bool) -> Callable[[str], bool]:
    """Create a case-insensitive match function for item names.

    Args:
        query: The search query string.
        exact: If True, match item names exactly (case-insensitive).
               If False, match as substring.

    Returns:
        A callable that returns True if an item name matches the query.
    """
    return lambda name: query.lower() == name.lower() if exact else query.lower() in name.lower()


def iter_mission_drops(data: dict[str, Any], query: str, exact: bool = False) -> list[DropResult]:
    """Search mission drop tables for matching items.

    Source: data["missionRewards"] - {planet: {mission: {gameMode, rewards}}}
    Rewards can be dict {tier: [items]} or list [items].
    """
    results: list[DropResult] = []
    match_fn = make_match_fn(query, exact)

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
                            results.append(DropResult(item_name, item["chance"], location, game_mode, tier))
            elif isinstance(rewards, list):
                for item in rewards:
                    item_name = item.get("itemName", "")
                    if match_fn(item_name):
                        results.append(DropResult(item_name, item["chance"], location, game_mode, "-"))

    return results


def iter_relic_drops(data: dict[str, Any], query: str, exact: bool = False) -> list[DropResult]:
    """Search vaulted relic drops for matching items.

    Source: data["relics"] - [{tier, relicName, state, rewards}]
    """
    results: list[DropResult] = []
    match_fn = make_match_fn(query, exact)

    for relic in data.get("relics", []):
        tier = relic.get("tier", "")
        relic_name = relic.get("relicName", "")
        state = relic.get("state", "Intact")
        for reward in relic.get("rewards", []):
            item_name = reward.get("itemName", "")
            if match_fn(item_name):
                results.append(DropResult(item_name, reward["chance"], f"Relic: {tier} {relic_name}", "", state))

    return results


def iter_mod_drops(data: dict[str, Any], query: str, exact: bool = False) -> list[DropResult]:
    """Search enemy drop mod locations.

    Source: data["modLocations"] - [{modName, enemies: [{enemyName, chance}]}]
    """
    results: list[DropResult] = []
    match_fn = make_match_fn(query, exact)

    for mod_loc in data.get("modLocations", []):
        mod_name = mod_loc.get("modName", "Unknown")
        for enemy in mod_loc.get("enemies", []):
            enemy_name = enemy.get("enemyName", "")
            if match_fn(mod_name):
                results.append(DropResult(mod_name, enemy["chance"], f"Mod drop: {enemy_name}", "", "-"))

    return results


def iter_blueprint_drops(data: dict[str, Any], query: str, exact: bool = False) -> list[DropResult]:
    """Search enemy drop blueprint locations.

    Source: data["blueprintLocations"] - [{blueprintName, enemies: [{enemyName, chance}]}]
    """
    results: list[DropResult] = []
    match_fn = make_match_fn(query, exact)

    for bp_loc in data.get("blueprintLocations", []):
        bp_name = bp_loc.get("blueprintName", bp_loc.get("itemName", "Unknown"))
        for enemy in bp_loc.get("enemies", []):
            item_name = bp_name
            if match_fn(item_name):
                results.append(DropResult(item_name, enemy["chance"], f"Blueprint: {enemy['enemyName']}", "", "-"))

    return results


def iter_key_drops(data: dict[str, Any], query: str, exact: bool = False) -> list[DropResult]:
    """Search mission key reward tables.

    Source: data["keyRewards"] - [{keyName, rewards: {tier: [items]}}]
    """
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
                        results.append(DropResult(item_name, item["chance"], f"Key: {key_name}", "", tier))

    return results


def iter_transient_drops(data: dict[str, Any], query: str, exact: bool = False) -> list[DropResult]:
    """Search transient mission rewards (Rush, Defection, etc.).

    Source: data["transientRewards"] - [{objectiveName, rewards: [{itemName, chance, rotation}]}]
    """
    results: list[DropResult] = []
    match_fn = make_match_fn(query, exact)

    for transient in data.get("transientRewards", []):
        place = transient.get("objectiveName", "Unknown")
        for reward in transient.get("rewards", []):
            item_name = reward.get("itemName", "")
            rotation = reward.get("rotation", "")
            if match_fn(item_name):
                results.append(DropResult(item_name, reward["chance"], f"Transient: {place}", "", rotation or "-"))

    return results


def iter_sortie_drops(data: dict[str, Any], query: str, exact: bool = False) -> list[DropResult]:
    """Search Sortie reward tables.

    Source: data["sortieRewards"] - [{itemName, chance}]
    """
    results: list[DropResult] = []
    match_fn = make_match_fn(query, exact)

    for reward in data.get("sortieRewards", []):
        item_name = reward.get("itemName", "")
        if match_fn(item_name):
            results.append(DropResult(item_name, reward["chance"], "Sortie", "", "-"))

    return results


def iter_cetus_drops(data: dict[str, Any], query: str, exact: bool = False) -> list[DropResult]:
    """Search Cetus/Fortuna bounty rewards.

    Source: data["cetusBountyRewards"] - [{place, rewards: {tier: [items]}}]
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
                        results.append(DropResult(item_name, item["chance"], f"Cetus: {place}", "", tier))

    return results


# All iterators combined - used by search_items()
ITERATORS: list[Callable[[dict[str, Any], str, bool], list[DropResult]]] = [
    iter_mission_drops,
    iter_relic_drops,
    iter_mod_drops,
    iter_blueprint_drops,
    iter_key_drops,
    iter_transient_drops,
    iter_sortie_drops,
    iter_cetus_drops,
]


def search_items(data: dict[str, Any], query: str, exact: bool = False) -> list[DropResult]:
    """Search all drop sources for matching items.

    Args:
        data: Full drop table data from the API.
        query: Search string.
        exact: If True, match exact item names. If False, substring match.

    Returns:
        All matching DropResult objects sorted by chance descending.
    """
    results = list(chain.from_iterable(it(data, query, exact) for it in ITERATORS))
    return sorted(results, key=lambda x: x.chance, reverse=True)
