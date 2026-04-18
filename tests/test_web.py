import pytest

from warframe.iterators import (
    iter_blueprint_drops,
    iter_cetus_drops,
    iter_key_drops,
    iter_mission_drops,
    iter_mod_drops,
    iter_relic_drops,
    iter_sortie_drops,
    iter_transient_drops,
    search_items,
)
from warframe.models import DropResult
from warframe.web import get_unique_items, get_unique_mission_types, parse_queries


@pytest.fixture
def sample_data():
    return {
        "missionRewards": {
            "Earth": {
                "Cervantes": {
                    "gameMode": "Survival",
                    "rewards": {
                        "C": [{"itemName": "Scindo", "chance": 5.0}],
                        "A": [{"itemName": "Neurodes", "chance": 10.0}],
                    },
                },
                "Tyr": {
                    "gameMode": "Exterminate",
                    "rewards": [
                        {"itemName": "Forma", "chance": 2.0},
                    ],
                },
            },
            "Mars": {
                "War": {
                    "gameMode": "Capture",
                    "rewards": {
                        "A": [{"itemName": "Scindo", "chance": 3.0}],
                    },
                },
            },
        },
        "relics": [
            {
                "tier": "Lith",
                "relicName": "A1",
                "state": "Intact",
                "rewards": [
                    {"itemName": "Scindo Prime Handle", "chance": 25.0},
                    {"itemName": "Forma Blueprint", "chance": 11.0},
                ],
            },
            {
                "tier": "Meso",
                "relicName": "B2",
                "state": "Radiant",
                "rewards": [
                    {"itemName": "Scindo", "chance": 15.0},
                    {"itemName": "Neurodes", "chance": 20.0},
                ],
            },
        ],
        "modLocations": [
            {
                "modName": "Bite",
                "enemies": [
                    {"enemyName": "Tamm", "chance": 0.22},
                    {"enemyName": "Corrupted Drahk", "chance": 0.22},
                ],
            },
        ],
        "blueprintLocations": [
            {
                "blueprintName": "Lens",
                "enemies": [
                    {"enemyName": "Any", "chance": 1.0},
                ],
            },
        ],
        "keyRewards": [
            {
                "keyName": "J3",
                "rewards": {
                    "A": [{"itemName": "Credits", "chance": 100.0}],
                },
            },
        ],
        "transientRewards": [
            {
                "objectiveName": "Defection",
                "rewards": [
                    {"itemName": "Kuva", "chance": 25.0, "rotation": "A"},
                ],
            },
        ],
        "sortieRewards": [
            {"itemName": "Argon Crystal", "chance": 10.0},
        ],
        "cetusBountyRewards": [
            {
                "place": "Fortuna",
                "rewards": {
                    "A": [{"itemName": "Cetus Wrait", "chance": 5.0}],
                },
            },
        ],
    }


class TestParseQueries:
    def test_single_query(self):
        assert parse_queries("scindo") == ["scindo"]

    def test_multiple_queries_comma_separated(self):
        assert parse_queries("scindo,neurodes") == ["scindo", "neurodes"]

    def test_space_not_split_delimiter(self):
        assert parse_queries("scindo neurodes") == ["scindo neurodes"]

    def test_trims_whitespace(self):
        assert parse_queries("  scindo  ") == ["scindo"]

    def test_ignores_empty_parts(self):
        assert parse_queries("scindo, ,neurodes") == ["scindo", "neurodes"]


class TestGetUniqueItems:
    def test_extracts_items_from_mission_rewards_dict(self, sample_data):
        items = get_unique_items(sample_data)
        assert "Scindo" in items
        assert "Neurodes" in items
        assert "Forma" in items

    def test_extracts_items_from_mission_rewards_list(self, sample_data):
        items = get_unique_items(sample_data)
        assert "Forma" in items

    def test_extracts_items_from_relics(self, sample_data):
        items = get_unique_items(sample_data)
        assert "Scindo Prime Handle" in items
        assert "Forma Blueprint" in items

    def test_extracts_items_from_mod_locations(self, sample_data):
        items = get_unique_items(sample_data)
        assert "Bite" in items

    def test_extracts_items_from_blueprint_locations(self, sample_data):
        items = get_unique_items(sample_data)
        assert "Lens" in items

    def test_extracts_items_from_key_rewards(self, sample_data):
        items = get_unique_items(sample_data)
        assert "Credits" in items

    def test_extracts_items_from_transient_rewards(self, sample_data):
        items = get_unique_items(sample_data)
        assert "Kuva" in items

    def test_extracts_items_from_sortie_rewards(self, sample_data):
        items = get_unique_items(sample_data)
        assert "Argon Crystal" in items

    def test_extracts_items_from_cetus_bounty_rewards(self, sample_data):
        items = get_unique_items(sample_data)
        assert "Cetus Wrait" in items

    def test_returns_sorted_list(self, sample_data):
        items = get_unique_items(sample_data)
        assert items == sorted(items)


class TestGetUniqueMissionTypes:
    def test_extracts_mission_types(self, sample_data):
        mission_types = get_unique_mission_types(sample_data)
        assert "Survival" in mission_types
        assert "Exterminate" in mission_types
        assert "Capture" in mission_types

    def test_returns_sorted_list(self, sample_data):
        mission_types = get_unique_mission_types(sample_data)
        assert mission_types == sorted(mission_types)


class TestIterMissionDrops:
    def test_fuzzy_match_returns_results(self, sample_data):
        results = iter_mission_drops(sample_data, "Scindo")
        assert len(results) == 2

    def test_exact_match_returns_results(self, sample_data):
        results = iter_mission_drops(sample_data, "Scindo", exact=True)
        assert len(results) == 2

    def test_exact_match_no_partial(self, sample_data):
        results = iter_mission_drops(sample_data, "Scind", exact=True)
        assert len(results) == 0

    def test_case_insensitive(self, sample_data):
        results = iter_mission_drops(sample_data, "scindo")
        assert len(results) == 2

    def test_dict_rewards_have_rotation(self, sample_data):
        results = iter_mission_drops(sample_data, "Scindo")
        rotations = [r.rotation for r in results]
        assert "C" in rotations
        assert "A" in rotations

    def test_list_rewards_have_dash_rotation(self, sample_data):
        results = iter_mission_drops(sample_data, "Forma")
        assert len(results) == 1
        assert results[0].rotation == "-"


class TestIterRelicDrops:
    def test_returns_relic_drops(self, sample_data):
        results = iter_relic_drops(sample_data, "Scindo")
        assert len(results) == 2

    def test_location_contains_relic_info(self, sample_data):
        results = iter_relic_drops(sample_data, "Scindo")
        locations = [r.location for r in results]
        assert any("Lith" in loc for loc in locations)
        assert any("Meso" in loc for loc in locations)

    def test_state_is_preserved(self, sample_data):
        results = iter_relic_drops(sample_data, "Scindo")
        rotations = [r.rotation for r in results]
        assert "Intact" in rotations
        assert "Radiant" in rotations


class TestIterModDrops:
    def test_finds_mod_drops(self, sample_data):
        results = iter_mod_drops(sample_data, "Bite")
        assert len(results) == 2

    def test_mod_location_format(self, sample_data):
        results = iter_mod_drops(sample_data, "Bite")
        locations = [r.location for r in results]
        assert all("Mod drop:" in loc for loc in locations)


class TestIterBlueprintDrops:
    def test_finds_blueprint_drops(self, sample_data):
        results = iter_blueprint_drops(sample_data, "Lens")
        assert len(results) == 1


class TestIterKeyDrops:
    def test_finds_key_drops(self, sample_data):
        results = iter_key_drops(sample_data, "Credits")
        assert len(results) == 1


class TestIterTransientDrops:
    def test_finds_transient_drops(self, sample_data):
        results = iter_transient_drops(sample_data, "Kuva")
        assert len(results) == 1


class TestIterSortieDrops:
    def test_finds_sortie_drops(self, sample_data):
        results = iter_sortie_drops(sample_data, "Argon Crystal")
        assert len(results) == 1


class TestIterCetusDrops:
    def test_finds_cetus_drops(self, sample_data):
        results = iter_cetus_drops(sample_data, "Cetus Wrait")
        assert len(results) == 1


class TestSearchItems:
    def test_combines_all_sources(self, sample_data):
        results = search_items(sample_data, "Scindo")
        assert len(results) >= 4

    def test_sorts_by_chance_descending(self, sample_data):
        results = search_items(sample_data, "Scindo")
        chances = [r.chance for r in results]
        assert chances == sorted(chances, reverse=True)