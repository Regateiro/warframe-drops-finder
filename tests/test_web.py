import pytest

from warframe.models import DropResult, Mission
from warframe.parser import DropDataParser
from warframe.web import format_multi_table_html, parse_queries


def get_unique_items(parser, data):
    parser._data = data
    parser._recache()
    return parser.get_drop_data().items


def get_unique_mission_types(parser, data):
    parser._data = data
    parser._recache()
    return parser.get_drop_data().mission_types


def iter_mission_drops(parser, data, query, exact=False):
    parser._data = data
    parser._recache()
    return parser._iter_mission_drops(query, exact)


def iter_relic_drops(parser, data, query, exact=False):
    parser._data = data
    parser._recache()
    return parser._iter_relic_drops(query, exact)


def iter_mod_drops(parser, data, query, exact=False):
    parser._data = data
    parser._recache()
    return parser._iter_mod_drops(query, exact)


def iter_blueprint_drops(parser, data, query, exact=False):
    parser._data = data
    parser._recache()
    return parser._iter_blueprint_drops(query, exact)


def iter_key_drops(parser, data, query, exact=False):
    parser._data = data
    parser._recache()
    return parser._iter_key_drops(query, exact)


def iter_transient_drops(parser, data, query, exact=False):
    parser._data = data
    parser._recache()
    return parser._iter_transient_drops(query, exact)


def iter_sortie_drops(parser, data, query, exact=False):
    parser._data = data
    parser._recache()
    return parser._iter_sortie_drops(query, exact)


def iter_bounty_drops(parser, data, query, exact=False):
    parser._data = data
    parser._recache()
    return parser._iter_bounty_drops(query, exact)


def search_items(parser, data, query, exact=False):
    parser._data = data
    parser._recache()
    return parser.search_items(query, exact)


@pytest.fixture
def parser():
    return DropDataParser()


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
                "bountyLevel": "Level 1 - 10 Cetus Bounty",
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
    def test_extracts_items_from_mission_rewards_dict(self, parser, sample_data):
        items = get_unique_items(parser, sample_data)
        assert "Scindo" in items
        assert "Neurodes" in items
        assert "Forma" in items

    def test_extracts_items_from_mission_rewards_list(self, parser, sample_data):
        items = get_unique_items(parser, sample_data)
        assert "Forma" in items

    def test_extracts_items_from_relics(self, parser, sample_data):
        items = get_unique_items(parser, sample_data)
        assert "Scindo Prime Handle" in items
        assert "Forma Blueprint" in items

    def test_extracts_items_from_mod_locations(self, parser, sample_data):
        items = get_unique_items(parser, sample_data)
        assert "Bite" in items

    def test_extracts_items_from_blueprint_locations(self, parser, sample_data):
        items = get_unique_items(parser, sample_data)
        assert "Lens" in items

    def test_extracts_items_from_key_rewards(self, parser, sample_data):
        items = get_unique_items(parser, sample_data)
        assert "Credits" in items

    def test_extracts_items_from_transient_rewards(self, parser, sample_data):
        items = get_unique_items(parser, sample_data)
        assert "Kuva" in items

    def test_extracts_items_from_sortie_rewards(self, parser, sample_data):
        items = get_unique_items(parser, sample_data)
        assert "Argon Crystal" in items

    def test_extracts_items_from_cetus_bounty_rewards(self, parser, sample_data):
        items = get_unique_items(parser, sample_data)
        assert "Cetus Wrait" in items

    def test_returns_sorted_list(self, parser, sample_data):
        items = get_unique_items(parser, sample_data)
        assert items == sorted(items)


class TestGetUniqueMissionTypes:
    def test_extracts_mission_types(self, parser, sample_data):
        mission_types = get_unique_mission_types(parser, sample_data)
        assert "Survival" in mission_types
        assert "Exterminate" in mission_types
        assert "Capture" in mission_types

    def test_returns_sorted_list(self, parser, sample_data):
        mission_types = get_unique_mission_types(parser, sample_data)
        assert mission_types == sorted(mission_types)


class TestIterMissionDrops:
    def test_fuzzy_match_returns_results(self, parser, sample_data):
        results = iter_mission_drops(parser, sample_data, "Scindo")
        assert len(results) == 2

    def test_exact_match_returns_results(self, parser, sample_data):
        results = iter_mission_drops(parser, sample_data, "Scindo", exact=True)
        assert len(results) == 2

    def test_exact_match_no_partial(self, parser, sample_data):
        results = iter_mission_drops(parser, sample_data, "Scind", exact=True)
        assert len(results) == 0

    def test_case_insensitive(self, parser, sample_data):
        results = iter_mission_drops(parser, sample_data, "scindo")
        assert len(results) == 2

    def test_dict_rewards_have_rotation(self, parser, sample_data):
        results = iter_mission_drops(parser, sample_data, "Scindo")
        rotations = [r.rotation for r in results]
        assert "C" in rotations
        assert "A" in rotations

    def test_list_rewards_have_dash_rotation(self, parser, sample_data):
        results = iter_mission_drops(parser, sample_data, "Forma")
        assert len(results) == 1
        assert results[0].rotation == "-"


class TestIterRelicDrops:
    def test_returns_relic_drops(self, parser, sample_data):
        results = iter_relic_drops(parser, sample_data, "Scindo")
        assert len(results) == 2

    def test_location_contains_relic_info(self, parser, sample_data):
        results = iter_relic_drops(parser, sample_data, "Scindo")
        locations = [r.location for r in results]
        assert any("Lith" in loc for loc in locations)
        assert any("Meso" in loc for loc in locations)

    def test_state_is_preserved(self, parser, sample_data):
        results = iter_relic_drops(parser, sample_data, "Scindo")
        rotations = [r.rotation for r in results]
        assert "Intact" in rotations
        assert "Radiant" in rotations


class TestIterModDrops:
    def test_finds_mod_drops(self, parser, sample_data):
        results = iter_mod_drops(parser, sample_data, "Bite")
        assert len(results) == 2

    def test_mod_location_format(self, parser, sample_data):
        results = iter_mod_drops(parser, sample_data, "Bite")
        locations = [r.location for r in results]
        assert all("Mod drop:" in loc for loc in locations)


class TestIterBlueprintDrops:
    def test_finds_blueprint_drops(self, parser, sample_data):
        results = iter_blueprint_drops(parser, sample_data, "Lens")
        assert len(results) == 1


class TestIterKeyDrops:
    def test_finds_key_drops(self, parser, sample_data):
        results = iter_key_drops(parser, sample_data, "Credits")
        assert len(results) == 1


class TestIterTransientDrops:
    def test_finds_transient_drops(self, parser, sample_data):
        results = iter_transient_drops(parser, sample_data, "Kuva")
        assert len(results) == 1


class TestIterSortieDrops:
    def test_finds_sortie_drops(self, parser, sample_data):
        results = iter_sortie_drops(parser, sample_data, "Argon Crystal")
        assert len(results) == 1


class TestIterBountyDrops:
    def test_finds_bounty_drops(self, parser, sample_data):
        results = iter_bounty_drops(parser, sample_data, "Cetus Wrait")
        assert len(results) == 1


class TestSearchItems:
    def test_combines_all_sources(self, parser, sample_data):
        results = search_items(parser, sample_data, "Scindo")
        assert len(results) >= 4

    def test_sorts_by_chance_descending(self, parser, sample_data):
        results = search_items(parser, sample_data, "Scindo")
        chances = [r.chance for r in results]
        assert chances == sorted(chances, reverse=True)


class TestMissionWeight:
    def test_single_table_returns_sum_of_chances(self):
        """Single-table missions (rotation='-') should use total drop chance as weight."""
        results = [
            DropResult("Item1", 5.0, "Earth - TestMission", Mission("Capture"), "-")
        ]
        html = format_multi_table_html(results, ["Item1"], 0)
        import re

        match = re.search(r'<tr data-weight="([\d.]+)"', html)
        assert match is not None
        weight = float(match.group(1))
        # Capture ATPC = 80 → 5 / 80 = 0.0625
        assert (
            abs(weight - 0.0625) < 0.001
        ), f"Expected ~0.0625 for single-table, got {weight}"

    def test_single_table_multi_items(self):
        """Single-table missions with multiple items should sum all chances."""
        results = [
            DropResult(
                "ItemA", 10.0, "Earth - TestMission", Mission("Capture"), "-"
            ),
            DropResult(
                "ItemB", 5.0, "Earth - TestMission", Mission("Capture"), "-"
            ),
        ]
        html = format_multi_table_html(results, ["ItemA", "ItemB"], 0)
        import re

        match = re.search(r'<tr data-weight="([\d.]+)"', html)
        assert match is not None
        weight = float(match.group(1))
        # Capture ATPC = 80 → (10 + 5) / 80 = 0.1875
        assert (
            abs(weight - (10 + 5) / 80) < 0.001
        ), f"Expected ~{15/80:.4f} for single-table multi-item, got {weight}"

    def test_multi_table_returns_max_strategy(self):
        """Multi-table missions return max across A-only and weighted-average strategies."""
        results = [
            DropResult(
                "Item", 20.0, "Mercury - TestMission", Mission("Survival"), "A"
            ),
            DropResult(
                "Item", 15.0, "Mercury - TestMission", Mission("Survival"), "B"
            ),
        ]
        html = format_multi_table_html(results, ["Item"], 0)
        import re

        match = re.search(r'<tr data-weight="([\d.]+)"', html)
        assert match is not None
        weight = float(match.group(1))
        # max(a/(matpc+mart), ...) = max(20/260, (40+15)/760) ≈ 0.0769
        assert (
            abs(weight - 20.0 / 260) < 0.001
        ), f"Expected ~{20/260:.6f} for multi-table, got {weight}"

    def test_multi_table_b_only(self):
        """When only B is available, weighted avg should be used (better than A-only)."""
        results = [
            DropResult(
                "Item", 5.0, "Mercury - TestMission", Mission("Survival"), "B"
            )
        ]
        html = format_multi_table_html(results, ["Item"], 0)
        import re

        match = re.search(r'<tr data-weight="([\d.]+)"', html)
        assert match is not None
        weight = float(match.group(1))
        # max(a=0, (2*0+5)/(3*matpc+mart)) = 5/(720+20) ≈ 0.00676
        assert (
            abs(weight - 5.0 / 740) < 0.001
        ), f"Expected ~{5/740:.6f} for B-only multi-table, got {weight}"
