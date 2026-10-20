"""
Parser for Warframe drop table JSON data.

This module provides the DropDataParser class which handles:
- Fetching drop data from the API (via fetcher module)
- Flattening all drop sources into a per-item index once per data load
- Searching across all drop sources via that index
- Extracting unique items and mission types for autocomplete

The parser wraps the iterators module, whose functions yield every
DropResult from one data source. Results are indexed by lowercased
item name so searches (exact or substring) are fast regardless of
dataset size.

Public API (methods intended for external use):
- refresh(force=False): Refresh data from API/cache
- get_drop_data(): Get cached DropData (items, mission types)
- search_items(query, exact=False): Search for items across all sources

All other methods are internal (prefixed with underscore).
"""

# defaultdict creates the item-name -> results index automatically
from collections import defaultdict

# Dataclass decorator for creating immutable data containers
from dataclasses import dataclass
from typing import Any

from .fetcher import fetch_drop_data
from .iterators import collect_all_drops
from .models import DropResult


class DataUnavailableError(RuntimeError):
    """Raised when no drop data is available (cache missing and API down)."""


# ============== Data Container ==============


@dataclass
class DropData:
    """Parsed drop table data container.

    Holds the extracted unique items and mission types from all drop sources.
    Used for autocomplete suggestions. The *_lower fields are aligned with
    their display counterparts so matching avoids re-lowercasing per request.

    Attributes:
        items: Sorted list of unique item names from all sources.
        items_lower: Lowercase item names, aligned with items.
        mission_types: Sorted list of unique mission types (game modes).
        mission_types_lower: Lowercase mission types, aligned with mission_types.
    """

    items: list[str]
    items_lower: list[str]
    mission_types: list[str]
    mission_types_lower: list[str]


# ============== Main Parser Class ==============


class DropDataParser:
    """Parser for Warframe drop table JSON data.

    This class handles fetching, indexing, and searching drop table data.
    Data is loaded lazily on the first operation (or immediately when
    data is injected via the constructor, which keeps tests hermetic).

    Caching behavior:
        - Data is fetched on the first refresh()/search/get_drop_data call
        - Parsed results are indexed in _index (item name -> results)
        - Expired cache (> 24h) auto-refreshes regardless of force flag
        - After initial load, refresh(force=False) only stats the cache file
    """

    def __init__(self, data: dict[str, Any] | None = None):
        """Initialize parser, optionally with injected raw data.

        Args:
            data: Raw drop data dictionary. When provided (tests), the
                parser never touches the network or the cache file.
        """
        # Cached parsed DropData (items + mission types)
        self._cache: DropData | None = None
        # Raw data from API (used to build the index)
        self._data: dict[str, Any] | None = data
        # Index of drop results by lowercased item name
        self._index: dict[str, list[DropResult]] = {}
        # Timestamp of last successful API fetch
        self._cache_timestamp: float | None = None
        # Injected data must never trigger a network fetch
        self._injected = data is not None
        if data is not None:
            self._recache()

    def refresh(self, force: bool = False) -> None:
        """Refresh cached data from the API or re-parse from local cache.

        Expired cache (> 24h old) auto-refreshes regardless of force flag.
        When force=True and the cache is >= 5 minutes old, forces a refetch.
        If the cache is less than 5 minutes old, it always uses cached data
        to prevent misuse (rapid successive API calls).

        Args:
            force: If True, force a refetch when the cache is at least
                   5 minutes old. Expired cache auto-refreshes regardless.
                   If False, use cached data if available.

        Raises:
            DataUnavailableError: If no data could be loaded at all.
        """
        if self._injected:
            if self._cache is None:
                self._recache()
            return

        # Fetch data if necessary (from cache or API, depending on force flag).
        # Returns (data dict | None, cache timestamp, boolean indicating fresh data was fetched).
        data, self._cache_timestamp, api_fetched = fetch_drop_data(force_refresh=force, force_load=self._data is None)

        # Update data and cache mtime if data was loaded, regardless of source (API or cache)
        if data is not None:
            self._data = data

        # If we have no data at all, the API request failed and there's no cache.
        if self._data is None:
            raise DataUnavailableError("No drop data available (API unreachable and no cache on disk).")

        # Re-index if this is first load or if we got fresh data from the API
        if self._cache is None or api_fetched:
            self._recache()

    def _ensure_loaded(self) -> None:
        """Load data on first use, raising DataUnavailableError on failure."""
        if self._cache is None:
            self.refresh()

    def _recache(self) -> None:
        """Flatten raw API data into the item index and DropData cache.

        Builds a dict of lowercased item name -> list of DropResult across
        all data sources, plus the sorted unique item and mission type lists
        used for autocomplete.
        """
        index: dict[str, list[DropResult]] = defaultdict(list)
        for result in collect_all_drops(self._data):
            index[result.item_name.lower()].append(result)
        self._index = dict(index)

        items = sorted({result.item_name for results in self._index.values() for result in results if result.item_name})
        mission_types = self._extract_mission_types()
        self._cache = DropData(
            items=items,
            items_lower=[item.lower() for item in items],
            mission_types=mission_types,
            mission_types_lower=[mt.lower() for mt in mission_types],
        )

    def get_drop_data(self) -> DropData:
        """Get parsed drop data from the cache.

        Returns:
            DropData with extracted items and mission types.
        Used for autocomplete dropdowns.

        Raises:
            DataUnavailableError: If no data could be loaded at all.
        """
        self._ensure_loaded()
        return self._cache

    def get_cache_timestamp(self) -> float | None:
        """Get the timestamp of the last successful API fetch.

        Returns:
            Timestamp (in seconds since epoch) of last API fetch, or None if never fetched.
        """
        return self._cache_timestamp

    # ============== Extraction Methods ==============

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

    def search_items(self, query: str, exact: bool = False) -> list[DropResult]:
        """Search for items matching the query across all drop sources.

        Looks up the prebuilt per-item index: a dict lookup for exact
        matches, or a scan over unique item names (not dataset entries)
        for substring matches.

        Args:
            query: The search string to match against item names.
            exact: If True, require exact match. Otherwise substring match.

        Returns:
            Deduplicated list of DropResult sorted by drop chance (highest first).

        Raises:
            DataUnavailableError: If no data could be loaded at all.
        """
        self._ensure_loaded()
        needle = query.lower()
        if not needle:
            return []
        if exact:
            matches = self._index.get(needle, [])
        else:
            matches = [result for key, results in self._index.items() if needle in key for result in results]
        # Dedupe (identical drops can appear via overlapping data entries)
        unique = list(dict.fromkeys(matches))
        # Sort by chance (highest first)
        return sorted(unique, key=lambda r: r.chance, reverse=True)
