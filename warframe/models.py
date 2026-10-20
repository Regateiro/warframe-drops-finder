"""
Data models for Warframe drop table search results.

This module defines the Mission and DropResult dataclasses which represent
a mission type and a single item drop from the Warframe game. DropResult
includes the item name, drop chance, location, mission type (game mode),
and rotation.

DropResult is used throughout the application to return search results
to users via the web interface or API.
"""

# Logging instead of printing unknown mission types to stdout
import logging
from dataclasses import dataclass
from typing import ClassVar

logger = logging.getLogger(__name__)


# frozen=True makes instances immutable (hashable, comparisons work)
# slots=True keeps memory low when millions of instances are created for the index
@dataclass(frozen=True, slots=True)
class Mission:
    """Represents a mission type with its average cycle time.

    Attributes:
        name: The mission type name (e.g., "Survival", "Defense").
    """

    MISSION_ATPC: ClassVar[dict[str, int]] = {
        "Survival": 240,
        "Defense": 180,
        "Interception": 300,
        "Mobile Defense": 300,
        "Sabotage": 300,
        "Rescue": 150,
        "Spy": 450,
        "Exterminate": 180,
        "Capture": 80,
        "Disruption": 240,
        "Excavation": 180,
        "Rush": 120,
        "Infested Salvage": 210,
        "Legacyte Harvest": 180,
        "Alchemy": 180,
        "Arena": 240,
        "Ascension": 240,
        "Assassination": 180,
        "Caches": 240,
        "Conclave": 300,
        "Defection": 180,
        "Follie's Hunt": 240,
        "Hard": 120,
        "Normal": 120,
        "Pursuit": 240,
        "Sanctuary Onslaught": 180,
        "Shrine Defense": 300,
        "Skirmish": 300,
        "The Circuit": 300,
        "The Perita Rebellion": 720,
        "Void Armageddon": 240,
        "Void Cascade": 240,
        "Void Flood": 240,
    }

    # Fallback used for unknown mission types (also used for non-mission drops)
    DEFAULT_ATPC: ClassVar[int] = 120

    name: str

    def get_name(self) -> str:
        """Return the mission type name."""
        return self.name

    def get_average_time_per_cycle(self) -> int:
        """Return the average time per cycle in seconds.

        Unknown mission types fall back to DEFAULT_ATPC and are logged
        once per name (not once per call, which used to flood the logs).
        An empty name (relics, mods, bounties, ...) is expected and silent.
        """
        if self.name in Mission.MISSION_ATPC:
            return Mission.MISSION_ATPC[self.name]
        if self.name and self.name not in _warned_unknown_missions:
            _warned_unknown_missions.add(self.name)
            logger.warning("Mission type %r not found in MISSION_ATPC; using default %ds", self.name, Mission.DEFAULT_ATPC)
        return Mission.DEFAULT_ATPC

    @staticmethod
    def get_average_restart_time() -> int:
        """Return the average restart time in seconds."""
        return 20


# Names of unknown mission types already logged (avoids log spam per request)
_warned_unknown_missions: set[str] = set()


@dataclass(frozen=True, slots=True)
class DropResult:
    """A single drop result from the Warframe drop tables.

    This represents one possible way to obtain an item in the game,
    including drop location, chance, game mode (mission type),
    and rotation.

    Attributes:
        item_name: Name of the item that can drop.
        chance: Drop chance as a percentage (e.g., 5.0 = 5%).
        location: Where it drops (e.g., "Earth - Cervantes",
            "Relic: Lith A1").
        mission_type: Mission object with name and average cycle time.
        rotation: Rotation (e.g., "A", "B", "C";
            "-" for non-missions).
    """

    item_name: str
    chance: float
    location: str
    mission_type: Mission
    rotation: str
