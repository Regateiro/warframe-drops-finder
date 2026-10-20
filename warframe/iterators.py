"""
Drop table iterators for Warframe drop table data.

Each iterator yields every DropResult from one data source of the API.
They take only the raw data dictionary (no query): the parser flattens
their output once per data load into a per-item index, making searches
fast regardless of dataset size.

The iterators work on the raw dictionary data structure from the API.
Entries with a null drop chance (present in upstream data for a few mods
and resources) are skipped, as they carry no information.

Data sources not iterated on purpose:
- enemyModTables / enemyBlueprintTables: per-enemy rollups of the same
  mods/blueprints already covered by modLocations/blueprintLocations, so
  they add no new item names or locations.
- resourceByAvatar / sigilByAvatar / additionalItemByAvatar ARE covered
  (see iter_avatar_drops).
"""

import re
from collections.abc import Iterator
from typing import Any

from .models import DropResult, Mission


def _chance(entry: dict[str, Any]) -> float | None:
    """Return the drop chance of an entry, or None if it is null/missing.

    Upstream data occasionally has `"chance": null` (e.g. legendary mods
    with no per-enemy chance). Such entries are skipped by all iterators.
    """
    chance = entry.get("chance")
    return chance if isinstance(chance, (int, float)) else None


# ============== Mission Drop Tables ==============


def iter_mission_drops(data: dict[str, Any]) -> Iterator[DropResult]:
    """Yield mission drop results.

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
    """
    for planet, missions in data.get("missionRewards", {}).items():
        for mission_name, details in missions.items():
            game_mode = details.get("gameMode", "")
            rewards = details.get("rewards", {})
            # Location format: "Planet - Mission Name"
            location = f"{planet} - {mission_name}"
            mission = Mission(game_mode)

            # Rewards can be a dict {tier: [items]} or list [items]
            if isinstance(rewards, dict):
                for tier, items in rewards.items():
                    for item in items:
                        chance = _chance(item)
                        if chance is not None:
                            yield DropResult(item.get("itemName", ""), chance, location, mission, tier)
            elif isinstance(rewards, list):
                for item in rewards:
                    chance = _chance(item)
                    if chance is not None:
                        yield DropResult(item.get("itemName", ""), chance, location, mission, "-")


# ============== Relic Drop Tables ==============


def iter_relic_drops(data: dict[str, Any]) -> Iterator[DropResult]:
    """Yield vaulted relic drop results.

    Relic drops come from opening Void Relics in the Refinery.
    Each relic has a tier (Lith, Meso, Neo, Axi), a name, and a state.
    The state affects the drop chances (Intact, Exceptional, Radiant, etc.)

    Source data structure:
        data["relics"] = [
            {
                tier: "Lith" | "Meso" | "Neo" | "Axi",
                relicName: "A1" | "B2" | ...,
                state: "Intact" | "Exceptional" | "Radiant",
                rewards: [{itemName, chance}]
            }
        ]
    """
    for relic in data.get("relics", []):
        tier = relic.get("tier", "")
        relic_name = relic.get("relicName", "")
        state = relic.get("state", "Intact")
        for reward in relic.get("rewards", []):
            chance = _chance(reward)
            if chance is not None:
                # Location format: "Relic: TIER NAME" (e.g., "Relic: Lith A1")
                # Rotation field stores the relic state
                yield DropResult(reward.get("itemName", ""), chance, f"Relic: {tier} {relic_name}", Mission(""), state)


# ============== Mod Drop Tables ==============


def iter_mod_drops(data: dict[str, Any]) -> Iterator[DropResult]:
    """Yield enemy drop mod locations.

    Certain mods drop from specific enemy types. This iterates over
    mod locations which list which enemies can drop each mod.

    Source data structure:
        data["modLocations"] = [
            {
                modName: "Steel Charge" | ...,
                enemies: [{enemyName, chance}]
            }
        ]
    """
    for mod_loc in data.get("modLocations", []):
        mod_name = mod_loc.get("modName", "Unknown")
        for enemy in mod_loc.get("enemies", []):
            chance = _chance(enemy)
            if chance is not None:
                # Location format: "Mod drop: Enemy Name"
                yield DropResult(mod_name, chance, f"Mod drop: {enemy.get('enemyName', '')}", Mission(""), "-")


# ============== Blueprint Drop Tables ==============


def iter_blueprint_drops(data: dict[str, Any]) -> Iterator[DropResult]:
    """Yield enemy drop blueprint locations.

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
    """
    for bp_loc in data.get("blueprintLocations", []):
        # Use blueprintName if available, fall back to itemName
        bp_name = bp_loc.get("blueprintName", bp_loc.get("itemName", "Unknown"))
        for enemy in bp_loc.get("enemies", []):
            chance = _chance(enemy)
            if chance is not None:
                # Location format: "Blueprint: Enemy Name"
                yield DropResult(bp_name, chance, f"Blueprint: {enemy.get('enemyName', '')}", Mission(""), "-")


# ============== Key Drop Tables ==============


def iter_key_drops(data: dict[str, Any]) -> Iterator[DropResult]:
    """Yield mission key reward tables.

    Mission keys (Junction keys, Orokin keys, etc.) unlock specific missions.
    Each key has rewards organized by tier.

    Source data structure:
        data["keyRewards"] = [
            {
                keyName: "J3" | ...,
                rewards: {tier: [items]}
            }
        ]
    """
    for key in data.get("keyRewards", []):
        key_name = key.get("keyName", "Unknown")
        rewards = key.get("rewards", {})
        if isinstance(rewards, dict):
            for tier, items in rewards.items():
                for item in items:
                    chance = _chance(item)
                    if chance is not None:
                        # Location format: "Key: Key Name"
                        yield DropResult(item.get("itemName", ""), chance, f"Key: {key_name}", Mission(""), tier)


# ============== Transient Drop Tables ==============


def iter_transient_drops(data: dict[str, Any]) -> Iterator[DropResult]:
    """Yield transient mission rewards (Rush, Defection, etc.).

    Transient missions are special game modes that appear periodically.
    They reward items with specific rotations (A, B, C) that affect drop chances.

    Source data structure:
        data["transientRewards"] = [
            {
                objectiveName: "Defection" | "Rush" | ...,
                rewards: [{itemName, chance, rotation}]
            }
        ]
    """
    for transient in data.get("transientRewards", []):
        place = transient.get("objectiveName", "Unknown")
        for reward in transient.get("rewards", []):
            chance = _chance(reward)
            if chance is not None:
                rotation = reward.get("rotation", "")
                # Location format: "Transient: Mission Name"
                # Use "-" as placeholder if no rotation specified
                yield DropResult(reward.get("itemName", ""), chance, f"Transient: {place}", Mission(""), rotation or "-")


# ============== Sortie Drop Tables ==============


def iter_sortie_drops(data: dict[str, Any]) -> Iterator[DropResult]:
    """Yield Sortie reward tables.

    Sorties are daily special missions with three stages. Each day has
    random mission types and a single reward table.

    Source data structure:
        data["sortieRewards"] = [
            {itemName, chance}
        ]
    """
    for reward in data.get("sortieRewards", []):
        chance = _chance(reward)
        if chance is not None:
            yield DropResult(reward.get("itemName", ""), chance, "Sortie", Mission(""), "-")


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


def iter_bounty_drops(data: dict[str, Any]) -> Iterator[DropResult]:
    """Yield all bounty reward tables.

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
    """
    for key in _find_bounty_keys(data):
        location_prefix = _camel_to_title(key)
        for bounty in data[key]:
            place = bounty.get("bountyLevel", f"{location_prefix} Bounty")
            rewards = bounty.get("rewards", {})
            if isinstance(rewards, dict):
                for tier, items in rewards.items():
                    for item in items:
                        chance = _chance(item)
                        if chance is not None:
                            yield DropResult(item.get("itemName", ""), chance, f"{location_prefix}: {place}", Mission(""), tier)


# ============== Syndicate Offerings ==============

# Not previously searched: ~216 extra items (Conclave skins, syndicate augments,
# etc.)


def iter_syndicate_drops(data: dict[str, Any]) -> Iterator[DropResult]:
    """Yield syndicate offering rewards.

    Each syndicate maps to a list of standing offerings with a fixed
    purchase chance.

    Source data structure:
        data["syndicates"] = {
            syndicateName: [
                {item, chance, rarity, place, standing, cost}
            ]
        }
    """
    for syndicate, entries in data.get("syndicates", {}).items():
        if not isinstance(entries, list):
            continue
        for entry in entries:
            chance = _chance(entry)
            if chance is not None:
                place = entry.get("place") or syndicate
                # Location format: "Syndicate: Cephalon Suda, Neutral"
                yield DropResult(entry.get("item", ""), chance, f"Syndicate: {place}", Mission(""), "-")


# ============== Avatar (per-enemy source) Drop Tables ==============

# Table key -> location prefix. These tables share the shape
#   data[key] = [{source: "Enemy Name", items: [{item, chance, rarity}]}]
AVATAR_TABLES: dict[str, str] = {
    "resourceByAvatar": "Resource drop",
    "sigilByAvatar": "Sigil drop",
    "additionalItemByAvatar": "Bonus drop",
}


def iter_avatar_drops(data: dict[str, Any]) -> Iterator[DropResult]:
    """Yield per-source (avatar) drop tables.

    Covers resource, sigil, and additional item drops by enemy source,
    discovered from AVATAR_TABLES.

    Not previously searched: ~107 extra items.
    """
    for key, label in AVATAR_TABLES.items():
        for entry in data.get(key, []):
            source = entry.get("source", "")
            for item in entry.get("items", []):
                chance = _chance(item)
                if chance is not None:
                    # Location format: "Resource drop: Techrot Motherboard Cluster"
                    yield DropResult(item.get("item", ""), chance, f"{label}: {source}", Mission(""), "-")


# ============== Combined Collection ==============

# All iterators combined - used by DropDataParser._recache()
# This list makes it easy to iterate over all data sources at once
ITERATORS = [
    iter_mission_drops,
    iter_relic_drops,
    iter_mod_drops,
    iter_blueprint_drops,
    iter_key_drops,
    iter_transient_drops,
    iter_sortie_drops,
    iter_bounty_drops,
    iter_syndicate_drops,
    iter_avatar_drops,
]


def collect_all_drops(data: dict[str, Any]) -> Iterator[DropResult]:
    """Yield every drop result from every data source.

    This is the main entry point for flattening the drop tables.

    Args:
        data: Full drop table data dictionary from the API.

    Yields:
        DropResult objects from all data sources.
    """
    for iterator in ITERATORS:
        yield from iterator(data)
