import re
from itertools import chain
from typing import Any, Callable

from .models import DropResult

RELIC_PATTERN = re.compile(r"^(lith|meso|neo|axi)\s+[a-z][1-9][0-9]?$", re.IGNORECASE)


def make_match_fn(query: str, exact: bool) -> Callable[[str], bool]:
    query_lower = query.lower()
    if exact:
        if query_lower.endswith(" relic"):
            return lambda name: name.lower() == query_lower

        paren_idx = query_lower.rfind(" (")
        if paren_idx > 0 and RELIC_PATTERN.match(query_lower[:paren_idx]):
            base = query_lower[:paren_idx]
            relic_variant = f"{base} relic{query_lower[paren_idx:]}"
            return lambda name: name.lower() in (query_lower, relic_variant)

        if RELIC_PATTERN.match(query_lower):
            relic_variant = f"{query_lower} relic"
            return lambda name: name.lower() in (query_lower, relic_variant)

        relic_variant = f"{query_lower} relic"
        radiant_variant = f"{query_lower} relic (radiant)"
        return lambda name: name.lower() in (query_lower, relic_variant, radiant_variant)
    return lambda name: query_lower in name.lower()


def iter_mission_drops(data: dict[str, Any], query: str, exact: bool = False) -> list[DropResult]:
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
    results: list[DropResult] = []
    match_fn = make_match_fn(query, exact)

    for reward in data.get("sortieRewards", []):
        item_name = reward.get("itemName", "")
        if match_fn(item_name):
            results.append(DropResult(item_name, reward["chance"], "Sortie", "", "-"))

    return results


def iter_cetus_drops(data: dict[str, Any], query: str, exact: bool = False) -> list[DropResult]:
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
    results = list(chain.from_iterable(it(data, query, exact) for it in ITERATORS))
    return sorted(results, key=lambda x: x.chance, reverse=True)
