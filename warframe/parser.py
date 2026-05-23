"""
Parser for Warframe drop table JSON data.

This module provides the DropDataParser class which handles:
- Fetching drop data from the API (via fetcher module)
- Caching parsed results to avoid recomputation
- Searching across all drop sources
- Extracting unique items and mission types for autocomplete

The parser wraps multiple "iterator" methods that each handle a specific
drop source (missions, relics, mods, blueprints, etc.). Results are
combined and sorted by drop chance.

Public API (methods intended for external use):
- refresh(force=False): Refresh data from API/cache
- get_drop_data(): Get cached DropData (items, mission types)
- search_items(query, exact=False): Search for items across all sources

All other methods are internal (prefixed with underscore).
"""

# dataclass creates the DropData container with minimal boilerplate
from dataclasses import dataclass

# chain.from_iterable flattens results from multiple iterators into one list
from itertools import chain

# Type hints for better IDE support and documentation
from typing import Any, Callable

# Local imports
import os

from .fetcher import CACHE_FILE, fetch_drop_data
from .models import DropResult

# ============== Data Container ==============


@dataclass
class DropData:
    """Parsed drop table data container.

    Holds the extracted unique items and mission types from all drop sources.
    Used for autocomplete suggestions.

    Attributes:
        items: Sorted list of unique item names from all sources.
        mission_types: Sorted list of unique mission types (game modes).
    """

    items: list[str]
    mission_types: list[str]


# ============== Main Parser Class ==============


class DropDataParser:
    """Parser for Warframe drop table JSON data.

    This class handles fetching, caching, and searching drop table data.
    It provides a clean public API while keeping internal implementation
    details (iterators, caching logic) private.

    Public methods:
        refresh(force=False): Refresh data from API or cache
        get_drop_data(): Get cached items and mission types
        search_items(query, exact=False): Search for item drops

    Internal methods (prefixed with _):
        _recache(): Re-parse raw data into cached DropData
        _extract_items(): Extract all unique item names
        _extract_mission_types(): Extract unique mission types
        _make_match_fn(): Create matching function for searches
        _iter_*(): Individual iterators for each drop source

    Caching behavior:
        - Data is fetched on first refresh() call (or at init if using __init__ without override)
        - Parsed results are cached in _cache
        - Expired cache (> 24h) auto-refreshes regardless of force flag
        - After initial load, refresh(force=False) uses in-memory data directly when cache is not expired
    """

    def __init__(self):
        """Initialize parser with empty cache.

        Note: Does NOT automatically fetch data. Call refresh() explicitly
        or the first search operation will trigger data load.
        """
        # Cache for parsed DropData (items + mission types)
        self._cache: DropData | None = None
        # Raw data from API (used by iterators)
        self._data: dict[str, Any] | None = None
        # Trigger initial data load
        self.refresh()

    def refresh(self, force: bool = False) -> None:
        """Refresh cached data from the API or re-parse from local cache.

        Expired cache (> 24h old) auto-refreshes regardless of force flag.
        When force=True and the cache is ≥ 5 minutes old, forces a refetch.
        If the cache is less than 5 minutes old, it always uses cached data
        to prevent misuse (rapid successive API calls).

        Args:
            force: If True, force a refetch when the cache is at least
                   5 minutes old. Expired cache auto-refreshes regardless.
                   If False, use cached data if available.
        """
        # Fetch data if necessary (from cache or API, depending on force flag)
        data, api_fetched = fetch_drop_data(force_refresh=force, force_load=self._data is None)

        # Update data and cache mtime if data was loaded, regardless of source (API or cache)
        if data is not None:
            self._data = data

        # Re-cache if this is first load or if we got fresh data from the API
        if self._cache is None or api_fetched:
            self._recache()

    def _recache(self) -> None:
        """Parse raw API data into structured DropData and cache it.

        Extracts unique items and mission types from the raw dictionary
        and stores in _cache for fast access.
        """
        self._cache = DropData(
            items=self._extract_items(),
            mission_types=self._extract_mission_types(),
        )

    def get_drop_data(self) -> DropData:
        """Get parsed drop data from the cache.

        Returns the cached DropData containing unique items and mission types.
        Used for autocomplete dropdowns.

        Returns:
            DropData with extracted items and mission types.
        """
        # Return cached data
        return self._cache

    # ============== Extraction Methods ==============

    def _extract_items(self) -> list[str]:
        """Extract all unique item names from drop data.

        Scans all drop sources and collects unique item names:
        - Mission rewards (dict and list formats)
        - Relic rewards
        - Mod locations
        - Blueprint locations
        - Key rewards
        - Transient rewards
        - Sortie rewards
        - Cetus/Fortuna bounty rewards

        Returns:
            Sorted list of unique item name strings.
        """
        items = set()  # Use set for automatic deduplication

        # Extract from mission rewards (dict format: {tier: [items]})
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

        # Extract from relic rewards
        for relic in self._data.get("relics", []):
            for reward in relic.get("rewards", []):
                items.add(reward.get("itemName", ""))

        # Extract from mod locations
        for mod_loc in self._data.get("modLocations", []):
            items.add(mod_loc.get("modName", ""))

        # Extract from blueprint locations
        for bp_loc in self._data.get("blueprintLocations", []):
            items.add(bp_loc.get("blueprintName", bp_loc.get("itemName", "")))
            items.add(bp_loc.get("itemName", ""))

        # Extract from key rewards
        for key in self._data.get("keyRewards", []):
            rewards = key.get("rewards", {})
            if isinstance(rewards, dict):
                for tier_list in rewards.values():
                    for item in tier_list:
                        items.add(item.get("itemName", ""))

        # Extract from transient rewards
        for transient in self._data.get("transientRewards", []):
            for reward in transient.get("rewards", []):
                items.add(reward.get("itemName", ""))

        # Extract from sortie rewards
        for reward in self._data.get("sortieRewards", []):
            items.add(reward.get("itemName", ""))

        # Extract from cetus bounty rewards
        for bounty in self._data.get("cetusBountyRewards", []):
            rewards = bounty.get("rewards", {})
            if isinstance(rewards, dict):
                for tier_list in rewards.values():
                    for item in tier_list:
                        items.add(item.get("itemName", ""))

        return sorted(items)  # Return alphabetically sorted

    def _extract_mission_types(self) -> list[str]:
        """Extract unique mission types (game modes) from drop data.

        Scans mission rewards and collects unique game mode strings
        like "Survival", "Exterminate", "Capture", etc.

        Returns:
            Sorted list of unique mission type strings.
        """
        mission_types = set()
        for missions in self._data.get("missionRewards", {}).values():
            for details in missions.values():
                game_mode = details.get("gameMode", "")
                if game_mode:
                    mission_types.add(game_mode)
        return sorted(mission_types)

    # ============== Search Methods ==============

    def _make_match_fn(self, query: str, exact: bool) -> Callable[[str], bool]:
        """Create a case-insensitive matching function for item names.

        Factory function that returns a predicate for testing whether
        an item name matches the query.

        Args:
            query: The search string.
            exact: If True, match exact string. Otherwise substring match.

        Returns:
            A function taking an item name and returning bool.
        """
        # Exact: require full match; Substring: check containment
        # Both compare lowercase for case-insensitivity
        return lambda name: query.lower() == name.lower() if exact else query.lower() in name.lower()

    def search_items(self, query: str, exact: bool = False) -> list[DropResult]:
        """Search for items matching the query across all drop sources.

        This is the main public search method. It runs each internal
        iterator and combines the results, then sorts by drop chance.

        Args:
            query: The search string to match against item names.
            exact: If True, require exact match. Otherwise substring match.

        Returns:
            List of DropResult sorted by drop chance (highest first).
        """
        # List of iterator methods to call
        iterators = [
            self._iter_mission_drops,
            self._iter_relic_drops,
            self._iter_mod_drops,
            self._iter_blueprint_drops,
            self._iter_key_drops,
            self._iter_transient_drops,
            self._iter_sortie_drops,
            self._iter_cetus_drops,
        ]
        # Run each iterator and flatten results
        results = list(chain.from_iterable(it(query, exact) for it in iterators))
        # Sort by chance, highest first
        return sorted(results, key=lambda x: x.chance, reverse=True)

    # ============== Internal Iterators ==============

    def _iter_mission_drops(self, query: str, exact: bool = False) -> list[DropResult]:
        """Internal: iterate mission drop results matching query.

        Searches mission rewards for items matching the query.

        Args:
            query: Search string.
            exact: Exact or substring match.

        Returns:
            List of matching DropResult.
        """
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

    def _iter_relic_drops(self, query: str, exact: bool = False) -> list[DropResult]:
        """Internal: iterate relic drop results matching query.

        Searches relic rewards for items matching the query.

        Args:
            query: Search string.
            exact: Exact or substring match.

        Returns:
            List of matching DropResult.
        """
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

    def _iter_mod_drops(self, query: str, exact: bool = False) -> list[DropResult]:
        """Internal: iterate mod drop results matching query.

        Searches mod locations for items matching the query.

        Args:
            query: Search string.
            exact: Exact or substring match.

        Returns:
            List of matching DropResult.
        """
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

    def _iter_blueprint_drops(self, query: str, exact: bool = False) -> list[DropResult]:
        """Internal: iterate blueprint drop results matching query.

        Searches blueprint locations for items matching the query.

        Args:
            query: Search string.
            exact: Exact or substring match.

        Returns:
            List of matching DropResult.
        """
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

    def _iter_key_drops(self, query: str, exact: bool = False) -> list[DropResult]:
        """Internal: iterate key drop results matching query.

        Searches key rewards for items matching the query.

        Args:
            query: Search string.
            exact: Exact or substring match.

        Returns:
            List of matching DropResult.
        """
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

    def _iter_transient_drops(self, query: str, exact: bool = False) -> list[DropResult]:
        """Internal: iterate transient reward drop results matching query.

        Searches transient rewards for items matching the query.

        Args:
            query: Search string.
            exact: Exact or substring match.

        Returns:
            List of matching DropResult.
        """
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

    def _iter_sortie_drops(self, query: str, exact: bool = False) -> list[DropResult]:
        """Internal: iterate sortie drop results matching query.

        Searches sortie rewards for items matching the query.

        Args:
            query: Search string.
            exact: Exact or substring match.

        Returns:
            List of matching DropResult.
        """
        data = self._data
        results: list[DropResult] = []
        match_fn = self._make_match_fn(query, exact)

        for reward in data.get("sortieRewards", []):
            item_name = reward.get("itemName", "")
            if match_fn(item_name):
                results.append(DropResult(item_name, reward["chance"], "Sortie", "", "-"))

        return results

    def _iter_cetus_drops(self, query: str, exact: bool = False) -> list[DropResult]:
        """Internal: iterate Cetus bounty drop results matching query.

        Searches Cetus/Fortuna bounty rewards for items matching the query.

        Args:
            query: Search string.
            exact: Exact or substring match.

        Returns:
            List of matching DropResult.
        """
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
