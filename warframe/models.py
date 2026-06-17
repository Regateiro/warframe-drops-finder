"""
Data models for Warframe drop table search results.

This module defines the DropResult dataclass which represents a single
item drop from the Warframe game. It includes the item name, drop chance,
location, mission type (game mode), and rotation.

DropResult is used throughout the application to return search results
to users via the web interface or API.
"""

# Import dataclass decorator for creating immutable data containers
from dataclasses import dataclass

# ClassVar: class-level constant, not an instance field
from typing import ClassVar


# frozen=True makes instances immutable (hashable, comparisons work)
@dataclass(frozen=True)
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

    name: str

    def get_name(self) -> str:
        """Return the mission type name."""
        return self.name

    def get_average_time_per_cycle(self) -> int:
        """Return the average time per cycle in seconds."""
        # Warn if the mission type is not found in the MISSION_ATPC dictionary
        if self.name not in Mission.MISSION_ATPC:
            print(f"WARNING: Mission '{self.name}' not found in MISSION_ATPC.")
        # Return the average time per cycle for this mission type, or 120 seconds as a default
        return Mission.MISSION_ATPC.get(self.name, 120)

    @staticmethod
    def get_average_restart_time() -> int:
        """Return the average restart time in seconds."""
        return 20


@dataclass(frozen=True)
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

    def to_tuple(self) -> tuple[str, float, str, str, int, str]:
        """Convert this DropResult to a tuple for serialization.

        Useful for caching results or converting to JSON-compatible format.
        Tuple order:
        ``(item_name, chance, location, mission_type_name,
        average_time_per_cycle, rotation)``.

        Returns:
            A 6-element tuple with all DropResult fields.
        """
        return (
            self.item_name,
            self.chance,
            self.location,
            self.mission_type.get_name(),
            self.mission_type.get_average_time_per_cycle(),
            self.rotation,
        )

    @classmethod
    def from_tuple(
        cls,
        t: tuple[str, float, str, str, int, str],
    ) -> "DropResult":
        """Create a DropResult from a tuple.

        Inverse of ``to_tuple()``. Creates an instance from
            a 5-element tuple.

        Args:
            t: Tuple of ``(item_name, chance, location,
               mission_type_name, avg_time_per_cycle, rotation)``.

        Returns:
            A new DropResult instance with the given values.
        """
        return cls(
            t[0],
            t[1],
            t[2],
            Mission(t[3]),
            t[5],
        )
