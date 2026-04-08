import pytest

from src.droptables import (
    format_multi_results,
    format_results,
    iter_mission_drops,
    iter_mod_drops,
    iter_relic_drops,
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
        ],
        "blueprintLocations": [],
        "keyRewards": [],
        "transientRewards": [],
        "sortieRewards": [],
        "cetusBountyRewards": [],
    }


class TestIterMissionDrops:
    def test_fuzzy_match_returns_results(self, sample_data):
        results = iter_mission_drops(sample_data, "Scindo")
        assert len(results) == 2
        items = [r[0] for r in results]
        assert "Scindo" in items

    def test_exact_match_returns_results(self, sample_data):
        results = iter_mission_drops(sample_data, "Scindo", exact=True)
        assert len(results) == 2
        items = [r[0] for r in results]
        assert "Scindo" in items

    def test_exact_match_no_partial(self, sample_data):
        results = iter_mission_drops(sample_data, "Scind", exact=True)
        assert len(results) == 0

    def test_no_match_returns_empty(self, sample_data):
        results = iter_mission_drops(sample_data, "NotAnItem")
        assert len(results) == 0

    def test_case_insensitive(self, sample_data):
        results = iter_mission_drops(sample_data, "scindo")
        assert len(results) == 2

    def test_dict_rewards_have_rotation(self, sample_data):
        results = iter_mission_drops(sample_data, "Scindo")
        rotations = [r[4] for r in results]
        assert "C" in rotations
        assert "A" in rotations

    def test_list_rewards_have_dash_rotation(self, sample_data):
        results = iter_mission_drops(sample_data, "Forma")
        assert len(results) == 1
        assert results[0][4] == "-"


class TestIterRelicDrops:
    def test_returns_relic_drops(self, sample_data):
        results = iter_relic_drops(sample_data, "Scindo")
        assert len(results) == 2

    def test_location_contains_relic_info(self, sample_data):
        results = iter_relic_drops(sample_data, "Scindo")
        locations = [r[2] for r in results]
        assert any("Lith" in loc for loc in locations)
        assert any("Meso" in loc for loc in locations)

    def test_state_is_preserved(self, sample_data):
        results = iter_relic_drops(sample_data, "Scindo")
        states = [r[4] for r in results]
        assert "Intact" in states
        assert "Radiant" in states


class TestIterModDrops:
    def test_finds_mod_drops(self, sample_data):
        results = iter_mod_drops(sample_data, "Bite")
        assert len(results) == 2

    def test_mod_location_format(self, sample_data):
        results = iter_mod_drops(sample_data, "Bite")
        locations = [r[2] for r in results]
        assert all("Mod drop:" in loc for loc in locations)


class TestFormatResults:
    def test_no_results_prints_message(self, sample_data, capsys):
        format_results([])
        captured = capsys.readouterr()
        assert "No results found" in captured.out

    def test_single_result(self, sample_data, capsys):
        results = [("Forma", 2.0, "Earth - Tyr", "Exterminate", "-")]
        format_results(results, max_results=20)
        captured = capsys.readouterr()
        assert "Forma" in captured.out
        assert "Earth - Tyr" in captured.out
        assert "Exterminate" in captured.out

    def test_multiple_rotations_consolidated(self, sample_data, capsys):
        results = [
            ("Scindo", 5.0, "Earth - Cervantes", "Survival", "C"),
            ("Scindo", 3.0, "Earth - Cervantes", "Survival", "A"),
        ]
        format_results(results, max_results=20)
        captured = capsys.readouterr()
        assert "C:5.00%" in captured.out
        assert "A:3.00%" in captured.out

    def test_shows_summary_count(self, sample_data, capsys):
        results = [
            ("Scindo", 5.0, "Earth - Cervantes", "Survival", "C"),
            ("Scindo", 3.0, "Mars - War", "Capture", "A"),
        ]
        format_results(results, max_results=20)
        captured = capsys.readouterr()
        assert "2 drops" in captured.out
        assert "2 locations" in captured.out


class TestFormatMultiResults:
    def test_no_results_prints_message(self, sample_data, capsys):
        format_multi_results([], queries=["Scindo"], max_results=20)
        captured = capsys.readouterr()
        assert "No results found" in captured.out

    def test_columns_are_aligned(self, sample_data, capsys):
        results = [
            ("Bite", 0.22, "Mod drop: Tamm", "", "-"),
            ("Bite", 0.22, "Mod drop: Corrupted Drahk", "", "-"),
        ]
        format_multi_results(results, queries=["Bite"], max_results=20)
        captured = capsys.readouterr()
        lines = captured.out.split("\n")
        header_idx = next(i for i, l in enumerate(lines) if l and not l.startswith("-") and not l.startswith("Found"))
        header = lines[header_idx]
        data_line = lines[header_idx + 2]

        header_parts = header.split(" | ")
        data_parts = data_line.split(" | ")
        assert len(header_parts) == len(data_parts)

        for i, (hp, dp) in enumerate(zip(header_parts, data_parts)):
            assert len(hp) == len(dp), f"Column {i} misaligned: header='{hp}' data='{dp}'"

    def test_different_chance_lengths_align(self, sample_data, capsys):
        results = [
            ("Bite", 0.22, "Mod drop: Tamm", "", "-"),
            ("Bite", 15.49, "Eris - Candiru", "Caches", "C"),
        ]
        format_multi_results(results, queries=["Bite"], max_results=20)
        captured = capsys.readouterr()
        lines = captured.out.split("\n")
        header_idx = next(i for i, l in enumerate(lines) if l and not l.startswith("-") and not l.startswith("Found"))
        header = lines[header_idx]
        data_line_1 = lines[header_idx + 2]
        data_line_2 = lines[header_idx + 3]

        parts_1 = data_line_1.split(" | ")
        parts_2 = data_line_2.split(" | ")
        assert len(parts_1) == len(parts_2) == len(header.split(" | "))
        assert len(parts_1[-1]) == len(parts_2[-1])

    def test_strips_relic_suffix(self, sample_data, capsys):
        results = [
            ("Lith A1 Relic", 25.0, "Relic: Lith A1", "Intact", "Intact"),
        ]
        format_multi_results(results, queries=["Lith A1 Relic"], max_results=20)
        captured = capsys.readouterr()
        lines = captured.out.split("\n")
        header_idx = next(i for i, l in enumerate(lines) if l and not l.startswith("-") and not l.startswith("Found"))
        header = lines[header_idx]
        assert "Lith A1" in header
        assert "Relic" not in header.split(" | ")[-1]

    def test_sorted_by_most_items_first(self, sample_data, capsys):
        results = [
            ("Scindo", 5.0, "Earth - Cervantes", "Survival", "C"),
            ("Neurodes", 10.0, "Earth - Cervantes", "Survival", "A"),
            ("Scindo", 3.0, "Mars - War", "Capture", "A"),
        ]
        format_multi_results(results, queries=["Scindo", "Neurodes"], max_results=20)
        captured = capsys.readouterr()
        lines = captured.out.split("\n")
        header_idx = next(i for i, l in enumerate(lines) if l and not l.startswith("-") and not l.startswith("Found"))
        first_data_line = lines[header_idx + 2]
        assert "Earth - Cervantes" in first_data_line

    def test_shows_correct_item_columns(self, sample_data, capsys):
        results = [
            ("Scindo", 5.0, "Earth - Cervantes", "Survival", "C"),
            ("Neurodes", 10.0, "Earth - Cervantes", "Survival", "A"),
        ]
        format_multi_results(results, queries=["Scindo", "Neurodes"], max_results=20)
        captured = capsys.readouterr()
        lines = captured.out.split("\n")
        header_idx = next(i for i, l in enumerate(lines) if l and not l.startswith("-") and not l.startswith("Found"))
        header = lines[header_idx]
        assert "Scindo" in header
        assert "Neurodes" in header


class TestIntegration:
    def test_end_to_end_fuzzy_search(self, sample_data):
        results = iter_mission_drops(sample_data, "scindo")
        assert len(results) == 2
        assert all("Scindo" in r[0] for r in results)

    def test_end_to_end_exact_search(self, sample_data):
        results = iter_mission_drops(sample_data, "Scindo", exact=True)
        assert len(results) == 2

    def test_combines_all_sources(self, sample_data):
        from src.droptables import search_items

        results = search_items(sample_data, "Scindo")
        assert len(results) >= 4

        locations = [r[2] for r in results]
        has_mission = any("Earth" in loc or "Mars" in loc for loc in locations)
        has_relic = any("Relic:" in loc for loc in locations)
        assert has_mission
        assert has_relic
