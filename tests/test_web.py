import pytest

from warframe.models import DropResult, Mission
from warframe.parser import DropDataParser
from warframe.web import (
    app,
    format_multi_table_html,
    parse_bool,
    parse_int,
    parse_queries,
)


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
            {
                "modName": "Sabot Rounds",
                "enemies": [
                    {"enemyName": "Gyrix", "chance": None},
                    {"enemyName": "Ionix", "chance": 0.15},
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
        "syndicates": {
            "Conclave": [
                {"item": "Ack & Brunt Conclave Skin", "chance": 100, "place": "Conclave, Tempest"},
            ],
        },
        "resourceByAvatar": [
            {
                "source": "Techrot Motherboard Cluster",
                "items": [
                    {"item": "Techrot Motherboard", "chance": 100},
                    {"item": "Null Chance Chip", "chance": None},
                ],
            },
        ],
        "sigilByAvatar": [
            {
                "source": "H-09 Apex",
                "items": [{"item": "Albumchip", "chance": 100}],
            },
        ],
        "additionalItemByAvatar": [
            {
                "source": "Scaldra Harbinger Gas Carrier",
                "items": [{"item": "Gas Can", "chance": 100}],
            },
        ],
    }


@pytest.fixture
def parser(sample_data):
    # Inject data so tests never touch the network or the cache file
    return DropDataParser(data=sample_data)


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as test_client:
        yield test_client


@pytest.fixture
def app_context():
    # format_multi_table_html renders a Jinja template, so it needs an app context
    with app.app_context():
        yield app


class TestParseQueries:
    def test_single_query(self, app_context):
        assert parse_queries("scindo") == ["scindo"]

    def test_multiple_queries_comma_separated(self, app_context):
        assert parse_queries("scindo,neurodes") == ["scindo", "neurodes"]

    def test_space_not_split_delimiter(self, app_context):
        assert parse_queries("scindo neurodes") == ["scindo neurodes"]

    def test_trims_whitespace(self, app_context):
        assert parse_queries("  scindo  ") == ["scindo"]

    def test_ignores_empty_parts(self, app_context):
        assert parse_queries("scindo, ,neurodes") == ["scindo", "neurodes"]


class TestParseInt:
    def test_default_when_empty(self, app_context):
        assert parse_int(None, 5, 0, 10) == 5
        assert parse_int("", 5, 0, 10) == 5

    def test_clamps(self, app_context):
        assert parse_int("999999", 0, 0, 10_000) == 10_000
        assert parse_int("-5", 0, 0, 10_000) == 0

    def test_invalid_raises(self, app_context):
        with pytest.raises(ValueError):
            parse_int("abc", 0, 0, 10_000)


class TestParseBool:
    def test_absent(self, app_context):
        assert parse_bool(None) is False

    def test_flag_style(self, app_context):
        assert parse_bool("") is True

    def test_values(self, app_context):
        for value in ("1", "true", "TRUE", "yes", "on"):
            assert parse_bool(value) is True
        for value in ("0", "false", "no", "partial"):
            assert parse_bool(value) is False


class TestGetUniqueItems:
    def test_extracts_items_from_all_sources(self, parser):
        items = parser.get_drop_data().items
        for item in ("Scindo", "Neurodes", "Forma", "Scindo Prime Handle", "Bite", "Lens", "Credits", "Kuva", "Argon Crystal", "Cetus Wrait"):
            assert item in items

    def test_extracts_syndicate_and_avatar_items(self, parser):
        items = parser.get_drop_data().items
        for item in ("Ack & Brunt Conclave Skin", "Techrot Motherboard", "Albumchip", "Gas Can"):
            assert item in items

    def test_returns_sorted_list(self, parser):
        items = parser.get_drop_data().items
        assert items == sorted(items)

    def test_lowercase_list_is_aligned(self, parser):
        data = parser.get_drop_data()
        assert data.items_lower == [item.lower() for item in data.items]


class TestGetUniqueMissionTypes:
    def test_extracts_mission_types(self, parser):
        mission_types = parser.get_drop_data().mission_types
        assert "Survival" in mission_types
        assert "Exterminate" in mission_types
        assert "Capture" in mission_types

    def test_returns_sorted_list(self, parser):
        mission_types = parser.get_drop_data().mission_types
        assert mission_types == sorted(mission_types)


class TestSearchItems:
    def test_fuzzy_match_returns_results(self, parser):
        assert len(parser.search_items("Scindo")) == 4

    def test_exact_match_on_full_name(self, parser):
        results = parser.search_items("Scindo Prime Handle", exact=True)
        assert len(results) == 1

    def test_exact_match_no_partial(self, parser):
        assert parser.search_items("Scind", exact=True) == []

    def test_case_insensitive(self, parser):
        assert len(parser.search_items("scindo")) == 4

    def test_sorts_by_chance_descending(self, parser):
        chances = [r.chance for r in parser.search_items("Scindo")]
        assert chances == sorted(chances, reverse=True)

    def test_combines_all_sources(self, parser):
        assert len(parser.search_items("Scindo")) >= 4

    def test_empty_query_returns_nothing(self, parser):
        assert parser.search_items("") == []

    def test_deduplicates_identical_results(self, parser):
        results = parser.search_items("Credits")
        assert len(results) == len(set(results))


class TestSearchSources:
    def test_mission_dict_rewards_have_rotation(self, parser):
        rotations = {r.rotation for r in parser.search_items("Scindo")}
        assert {"A", "C"} & rotations

    def test_mission_list_rewards_have_dash_rotation(self, parser):
        results = parser.search_items("Forma", exact=True)
        assert all(r.rotation == "-" for r in results)

    def test_relic_state_is_preserved(self, parser):
        rotations = {r.rotation for r in parser.search_items("Scindo")}
        assert "Intact" in rotations

    def test_mod_location_format(self, parser):
        results = parser.search_items("Bite", exact=True)
        assert results and all("Mod drop:" in r.location for r in results)

    def test_syndicate_location_format(self, parser):
        results = parser.search_items("Ack & Brunt Conclave Skin", exact=True)
        assert len(results) == 1
        assert results[0].location == "Syndicate: Conclave, Tempest"

    def test_avatar_location_formats(self, parser):
        assert parser.search_items("Techrot Motherboard", exact=True)[0].location == "Resource drop: Techrot Motherboard Cluster"
        assert parser.search_items("Albumchip", exact=True)[0].location == "Sigil drop: H-09 Apex"
        assert parser.search_items("Gas Can", exact=True)[0].location == "Bonus drop: Scaldra Harbinger Gas Carrier"


class TestNullChanceData:
    def test_null_chance_entries_are_skipped(self, parser):
        results = parser.search_items("Sabot Rounds", exact=True)
        assert len(results) == 1
        assert results[0].chance == 0.15

    def test_null_chance_entries_do_not_crash_search(self, parser):
        # Regression: sorting results crashed on NoneType chance
        results = parser.search_items("S")
        assert all(isinstance(r.chance, (int, float)) for r in results)

    def test_all_chances_are_numeric(self, parser):
        results = parser.search_items("a")
        assert all(isinstance(r.chance, (int, float)) for r in results)


class TestInjectedData:
    def test_injected_parser_needs_no_refresh(self, sample_data):
        injected = DropDataParser(data=sample_data)
        assert injected.get_drop_data().items

    def test_refresh_is_a_noop_for_injected_data(self, parser):
        parser.refresh(force=True)
        assert parser.get_drop_data().items


class TestWebRoutes:
    def test_index_loads(self, client):
        response = client.get("/")
        assert response.status_code == 200
        assert b"Warframe Drop Locations" in response.data

    def test_index_exposes_exact_checkbox(self, client):
        assert b'name="exact"' in client.get("/").data

    def test_index_search_returns_table(self, client):
        response = client.get("/?q=Target+Acquired&n=0")
        assert response.status_code == 200

    def test_index_invalid_n_param_does_not_crash(self, client):
        response = client.get("/?q=scindo&n=abc")
        assert response.status_code == 200

    def test_index_out_of_range_n_param_is_clamped(self, client):
        assert client.get("/?q=scindo&n=999999999999999999999").status_code == 200

    def test_prefixed_route_is_registered(self, client):
        with app.test_request_context():
            rules = {rule.rule for rule in app.url_map.iter_rules()}
        assert "/" in rules
        if app.config["WEB_ROOT"]:
            assert app.config["WEB_ROOT"] + "/" in rules
            assert app.config["WEB_ROOT"] + "/static/<path:filename>" in rules

    def test_api_drops_requires_query(self, client):
        assert client.get("/api/drops").status_code == 400

    def test_api_drops_returns_json(self, client):
        response = client.get("/api/drops?q=scindo")
        assert response.status_code == 200
        assert response.is_json
        assert isinstance(response.get_json(), list)

    def test_api_drops_invalid_n_returns_400(self, client):
        response = client.get("/api/drops?q=scindo&n=xyz")
        assert response.status_code == 400

    def test_api_drops_exact_param(self, client):
        partial = client.get("/api/drops?q=scindo").get_json()
        exact = client.get("/api/drops?q=scindo&exact=true").get_json()
        assert len(partial) >= len(exact)

    def test_suggest_items(self, client):
        response = client.get("/api/suggest-items?q=scin")
        assert response.status_code == 200
        matches = response.get_json()
        assert matches and all("scin" in match.lower() for match in matches)

    def test_suggest_mission_types(self, client):
        response = client.get("/api/suggest-mission-types?q=surv")
        assert response.status_code == 200
        assert "Survival" in response.get_json()

    def test_suggest_items_limits_to_ten(self, client):
        assert len(client.get("/api/suggest-items?q=").get_json()) <= 10


class TestMissionWeight:
    def test_single_table_returns_sum_of_chances(self, app_context):
        """Single-table missions (rotation='-') should use total drop chance as weight."""
        results = [DropResult("Item1", 5.0, "Earth - TestMission", Mission("Capture"), "-")]
        html = format_multi_table_html(results, 0)
        import re

        weight = float(re.search(r'<tr data-weight="([\d.]+)"', html).group(1))
        # Capture ATPC = 80 → 5 / 80 = 0.0625
        assert abs(weight - 0.0625) < 0.001, f"Expected ~0.0625 for single-table, got {weight}"

    def test_single_table_multi_items(self, app_context):
        """Single-table missions with multiple items should sum all chances."""
        results = [
            DropResult("ItemA", 10.0, "Earth - TestMission", Mission("Capture"), "-"),
            DropResult("ItemB", 5.0, "Earth - TestMission", Mission("Capture"), "-"),
        ]
        html = format_multi_table_html(results, 0)
        import re

        weight = float(re.search(r'<tr data-weight="([\d.]+)"', html).group(1))
        # Capture ATPC = 80 → (10 + 5) / 80 = 0.1875
        assert abs(weight - (10 + 5) / 80) < 0.001, f"Expected ~{15/80:.4f} for single-table multi-item, got {weight}"

    def test_multi_table_returns_max_strategy(self, app_context):
        """Multi-table missions return max across A-only and weighted-average strategies."""
        results = [
            DropResult("Item", 20.0, "Mercury - TestMission", Mission("Survival"), "A"),
            DropResult("Item", 15.0, "Mercury - TestMission", Mission("Survival"), "B"),
        ]
        html = format_multi_table_html(results, 0)
        import re

        weight = float(re.search(r'<tr data-weight="([\d.]+)"', html).group(1))
        # max(a/(matpc+mart), ...) = max(20/260, (40+15)/760) ≈ 0.0769
        assert abs(weight - 20.0 / 260) < 0.001, f"Expected ~{20/260:.6f} for multi-table, got {weight}"

    def test_multi_table_b_only(self, app_context):
        """When only B is available, weighted avg should be used (better than A-only)."""
        results = [DropResult("Item", 5.0, "Mercury - TestMission", Mission("Survival"), "B")]
        html = format_multi_table_html(results, 0)
        import re

        weight = float(re.search(r'<tr data-weight="([\d.]+)"', html).group(1))
        # max(a=0, (2*0+5)/(3*matpc+mart)) = 5/(720+20) ≈ 0.00676
        assert abs(weight - 5.0 / 740) < 0.001, f"Expected ~{5/740:.6f} for B-only multi-table, got {weight}"

    def test_escapes_untrusted_item_names(self, app_context):
        """Item/location names come from an external API and must be escaped."""
        results = [DropResult("<script>alert(1)</script>", 5.0, "Earth - M", Mission("Capture"), "-")]
        html = format_multi_table_html(results, 0)
        assert "<script>alert(1)</script>" not in html
        assert "&lt;script&gt;" in html

    def test_respects_max_results(self, app_context):
        results = [DropResult(f"Item{i}", 5.0, f"Earth - M{i}", Mission("Capture"), "-") for i in range(5)]
        html = format_multi_table_html(results, 2)
        assert html.count("<tr data-weight=") == 2
