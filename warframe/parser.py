"""Parser for Warframe drop table JSON data.

Extracts items, mission types, and other structured data from the raw API response.
Handles internal caching to avoid recomputing on every request.
"""

from dataclasses import dataclass
from itertools import chain
from typing import Any, Callable

from .fetcher import fetch_drop_data
from .models import DropResult


@dataclass
class DropData:
    """Parsed drop table data.

    Attributes:
        items: Sorted list of unique item names from all sources.
        mission_types: Sorted list of unique mission types (game modes).
    """

    items: list[str]
    mission_types: list[str]


class DropDataParser:
    """Parser for Warframe drop table JSON data.

    Provides caching internally.
    """

    def __init__(self):
        self._cache: DropData | None = None
        self._data: dict[str, Any] | None = None
        # Initial load of data and cache
        self.refresh()

    def refresh(self, force: bool = False) -> None:
        """Refresh cached data from the API.

        Args:
            force: If True, forces a refresh even if cache is still valid.
        """
        # Fetch data (from cache or API)
        self._data, refetched = fetch_drop_data(force_refresh=force)

        # If we got new data, or if cache is empty, re-parse and update cache
        if self._cache is None or refetched:
            self._recache()

    def _recache(self) -> None:
        """Parse raw API data into structured DropData and cache it."""
        self._cache = DropData(
            items=self._extract_items(),
            mission_types=self._extract_mission_types(),
        )

    def get_drop_data(self) -> DropData:
        """Parse raw API data into structured DropData.
        Uses cached result if available.

        Args:
            data: Raw JSON data from the API.

        Returns:
            DropData with extracted items and mission types.
        """
        # If cache is empty, parse and populate it
        if self._cache is None:
            self._recache()

        # Return cached data
        return self._cache

    def _extract_items(self) -> list[str]:
        """Extract all unique item names from drop data.

        Scans all drop sources: missions, relics, mods, blueprints, etc.
        """
        items = set()

        for missions in self._data.get("missionRewards", {}).values():
            for details in missions.values():
                rewards = details.get("rewards", {})
                if isinstance(rewards, dict):
                    for tier_list in rewards.values():
                        for item in tier_list:
                            items.add(item.get("itemName", ""))
                elif isinstance(rewards, list):
                    for item in rewards:
                        items.add(item.get("itemName", ""))

        for relic in self._data.get("relics", []):
            for reward in relic.get("rewards", []):
                items.add(reward.get("itemName", ""))

        for mod_loc in self._data.get("modLocations", []):
            items.add(mod_loc.get("modName", ""))

        for bp_loc in self._data.get("blueprintLocations", []):
            items.add(bp_loc.get("blueprintName", bp_loc.get("itemName", "")))
            items.add(bp_loc.get("itemName", ""))

        for key in self._data.get("keyRewards", []):
            rewards = key.get("rewards", {})
            if isinstance(rewards, dict):
                for tier_list in rewards.values():
                    for item in tier_list:
                        items.add(item.get("itemName", ""))

        for transient in self._data.get("transientRewards", []):
            for reward in transient.get("rewards", []):
                items.add(reward.get("itemName", ""))

        for reward in self._data.get("sortieRewards", []):
            items.add(reward.get("itemName", ""))

        for bounty in self._data.get("cetusBountyRewards", []):
            rewards = bounty.get("rewards", {})
            if isinstance(rewards, dict):
                for tier_list in rewards.values():
                    for item in tier_list:
                        items.add(item.get("itemName", ""))

        return sorted(items)

    def _extract_mission_types(self) -> list[str]:
        """Extract unique mission types (game modes) from drop data."""
        mission_types = set()
        for missions in self._data.get("missionRewards", {}).values():
            for details in missions.values():
                game_mode = details.get("gameMode", "")
                if game_mode:
                    mission_types.add(game_mode)
        return sorted(mission_types)

    def _make_match_fn(self, query: str, exact: bool) -> Callable[[str], bool]:
        return lambda name: query.lower() == name.lower() if exact else query.lower() in name.lower()

    def search_items(self, query: str, exact: bool = False) -> list[DropResult]:
        iterators = [
            self.iter_mission_drops,
            self.iter_relic_drops,
            self.iter_mod_drops,
            self.iter_blueprint_drops,
            self.iter_key_drops,
            self.iter_transient_drops,
            self.iter_sortie_drops,
            self.iter_cetus_drops,
        ]
        results = list(chain.from_iterable(it(query, exact) for it in iterators))
        return sorted(results, key=lambda x: x.chance, reverse=True)

    def iter_mission_drops(self, query: str, exact: bool = False) -> list[DropResult]:
        data = self._data
        results: list[DropResult] = []
        match_fn = self._make_match_fn(query, exact)

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

    def iter_relic_drops(self, query: str, exact: bool = False) -> list[DropResult]:
        data = self._data
        results: list[DropResult] = []
        match_fn = self._make_match_fn(query, exact)

        for relic in data.get("relics", []):
            tier = relic.get("tier", "")
            relic_name = relic.get("relicName", "")
            state = relic.get("state", "Intact")
            for reward in relic.get("rewards", []):
                item_name = reward.get("itemName", "")
                if match_fn(item_name):
                    results.append(DropResult(item_name, reward["chance"], f"Relic: {tier} {relic_name}", "", state))

        return results

    def iter_mod_drops(self, query: str, exact: bool = False) -> list[DropResult]:
        data = self._data
        results: list[DropResult] = []
        match_fn = self._make_match_fn(query, exact)

        for mod_loc in data.get("modLocations", []):
            mod_name = mod_loc.get("modName", "Unknown")
            for enemy in mod_loc.get("enemies", []):
                enemy_name = enemy.get("enemyName", "")
                if match_fn(mod_name):
                    results.append(DropResult(mod_name, enemy["chance"], f"Mod drop: {enemy_name}", "", "-"))

        return results

    def iter_blueprint_drops(self, query: str, exact: bool = False) -> list[DropResult]:
        data = self._data
        results: list[DropResult] = []
        match_fn = self._make_match_fn(query, exact)

        for bp_loc in data.get("blueprintLocations", []):
            bp_name = bp_loc.get("blueprintName", bp_loc.get("itemName", "Unknown"))
            for enemy in bp_loc.get("enemies", []):
                item_name = bp_name
                if match_fn(item_name):
                    results.append(DropResult(item_name, enemy["chance"], f"Blueprint: {enemy['enemyName']}", "", "-"))

        return results

    def iter_key_drops(self, query: str, exact: bool = False) -> list[DropResult]:
        data = self._data
        results: list[DropResult] = []
        match_fn = self._make_match_fn(query, exact)

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

    def iter_transient_drops(self, query: str, exact: bool = False) -> list[DropResult]:
        data = self._data
        results: list[DropResult] = []
        match_fn = self._make_match_fn(query, exact)

        for transient in data.get("transientRewards", []):
            place = transient.get("objectiveName", "Unknown")
            for reward in transient.get("rewards", []):
                item_name = reward.get("itemName", "")
                rotation = reward.get("rotation", "")
                if match_fn(item_name):
                    results.append(DropResult(item_name, reward["chance"], f"Transient: {place}", "", rotation or "-"))

        return results

    def iter_sortie_drops(self, query: str, exact: bool = False) -> list[DropResult]:
        data = self._data
        results: list[DropResult] = []
        match_fn = self._make_match_fn(query, exact)

        for reward in data.get("sortieRewards", []):
            item_name = reward.get("itemName", "")
            if match_fn(item_name):
                results.append(DropResult(item_name, reward["chance"], "Sortie", "", "-"))

        return results

    def iter_cetus_drops(self, query: str, exact: bool = False) -> list[DropResult]:
        data = self._data
        results: list[DropResult] = []
        match_fn = self._make_match_fn(query, exact)

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
