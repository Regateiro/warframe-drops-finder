"""Parser for Warframe drop table JSON data.

Extracts items, mission types, and other structured data from the raw API response.
Handles internal caching to avoid recomputing on every request.
"""

from dataclasses import dataclass
from typing import Any


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

    Provides caching internally - call clear() to force reparse.
    """

    def __init__(self):
        self._cache: DropData | None = None

    def parse(self, data: dict[str, Any]) -> DropData:
        """Parse raw API data into structured DropData.
        Uses cached result if available.

        Args:
            data: Raw JSON data from the API.

        Returns:
            DropData with extracted items and mission types.
        """
        if self._cache is None:
            self._cache = DropData(
                items=self._extract_items(data),
                mission_types=self._extract_mission_types(data),
            )
        return self._cache

    def clear(self):
        """Clear the internal cache."""
        self._cache = None

    def _extract_items(self, data: dict[str, Any]) -> list[str]:
        """Extract all unique item names from drop data.

        Scans all drop sources: missions, relics, mods, blueprints, etc.
        """
        items = set()

        # Mission rewards
        for missions in data.get("missionRewards", {}).values():
            for details in missions.values():
                rewards = details.get("rewards", {})
                if isinstance(rewards, dict):
                    for tier_list in rewards.values():
                        for item in tier_list:
                            items.add(item.get("itemName", ""))
                elif isinstance(rewards, list):
                    for item in rewards:
                        items.add(item.get("itemName", ""))

        # Vaulted relics
        for relic in data.get("relics", []):
            for reward in relic.get("rewards", []):
                items.add(reward.get("itemName", ""))

        # Mod locations
        for mod_loc in data.get("modLocations", []):
            items.add(mod_loc.get("modName", ""))

        # Blueprint locations
        for bp_loc in data.get("blueprintLocations", []):
            items.add(bp_loc.get("blueprintName", bp_loc.get("itemName", "")))
            items.add(bp_loc.get("itemName", ""))

        # Key rewards
        for key in data.get("keyRewards", []):
            rewards = key.get("rewards", {})
            if isinstance(rewards, dict):
                for tier_list in rewards.values():
                    for item in tier_list:
                        items.add(item.get("itemName", ""))

        # Transient rewards
        for transient in data.get("transientRewards", []):
            for reward in transient.get("rewards", []):
                items.add(reward.get("itemName", ""))

        # Sortie rewards
        for reward in data.get("sortieRewards", []):
            items.add(reward.get("itemName", ""))

        # Cetus bounty rewards
        for bounty in data.get("cetusBountyRewards", []):
            rewards = bounty.get("rewards", {})
            if isinstance(rewards, dict):
                for tier_list in rewards.values():
                    for item in tier_list:
                        items.add(item.get("itemName", ""))

        return sorted(items)

    def _extract_mission_types(self, data: dict[str, Any]) -> list[str]:
        """Extract unique mission types (game modes) from drop data.

        Example: ["Capture", "Defense", "Survival", "Excavation"]
        """
        mission_types = set()
        for missions in data.get("missionRewards", {}).values():
            for details in missions.values():
                game_mode = details.get("gameMode", "")
                if game_mode:
                    mission_types.add(game_mode)
        return sorted(mission_types)
