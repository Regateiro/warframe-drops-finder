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


# frozen=True makes instances immutable (hashable, comparisons work)
@dataclass(frozen=True)
class DropResult:
    """A single drop result from the Warframe drop tables.

    This represents one possible way to obtain an item in the game,
    including where it drops, how likely it is, and what game mode/rotation applies.

    Attributes:
        item_name: Name of the item that can drop.
        chance: Drop chance as a percentage (e.g., 5.0 = 5%).
        location: Where the drop occurs (e.g., "Earth - Cervantes", "Relic: Lith A1").
        mission_type: Game mode or relic state (e.g., "Survival", "Intact", "Radiant").
        rotation: Drop table rotation (e.g., "A", "B", "C" for missions; "-" for others).
    """

    item_name: str
    chance: float
    location: str
    mission_type: str
    rotation: str

    def to_tuple(self) -> tuple[str, float, str, str, str]:
        """Convert this DropResult to a tuple for serialization.

        Useful for caching results or converting to JSON-compatible format.
        The tuple contains: (item_name, chance, location, mission_type, rotation).

        Returns:
            A 5-element tuple with all DropResult fields.
        """
        return (self.item_name, self.chance, self.location, self.mission_type, self.rotation)

    @classmethod
    def from_tuple(cls, t: tuple[str, float, str, str, str]) -> "DropResult":
        """Create a DropResult from a tuple.

        Inverse of to_tuple(). Takes a 5-element tuple and creates a DropResult instance.

        Args:
            t: A tuple of (item_name, chance, location, mission_type, rotation).

        Returns:
            A new DropResult instance with the given values.
        """
        return cls(t[0], t[1], t[2], t[3], t[4])
