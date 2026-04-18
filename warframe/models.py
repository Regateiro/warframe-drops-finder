"""Data models for Warframe drop table search results."""

from dataclasses import dataclass


@dataclass(frozen=True)
class DropResult:
    """A single drop result from the Warframe drop tables.

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
        return (self.item_name, self.chance, self.location, self.mission_type, self.rotation)

    @classmethod
    def from_tuple(cls, t: tuple[str, float, str, str, str]) -> "DropResult":
        return cls(t[0], t[1], t[2], t[3], t[4])
