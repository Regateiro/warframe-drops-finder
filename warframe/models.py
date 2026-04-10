from dataclasses import dataclass


@dataclass(frozen=True)
class DropResult:
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
