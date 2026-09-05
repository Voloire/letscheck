import pytest

from astrochecker.planner import plan_ideas, plan_night_sequence, select_astronomical_night


def candidate(name, priority, intervals, **profile):
    return {
        "name": name,
        "type": profile.pop("type", "OCl"),
        "ra_deg": profile.pop("ra_deg", float(priority)),
        "dec_deg": profile.pop("dec_deg", 20.0),
        "aliases": profile.pop("aliases", [name]),
        "profile": {"priority": priority, "eligible": True, **profile},
        "intervals": intervals,
    }


def test_plan_ideas_filters_short_blocks_and_reports_partial_status():
    result = plan_ideas(
        [candidate("short", 100, [{"start": 0, "end": 7199}]), candidate("long", 10, [{"start": 7200, "end": 16000}])],
        [{"start": 0, "end": 20000}],
        14400,
    )

    assert result["status"] == "partial"
    assert result["requested_duration_seconds"] == 14400
    assert result["covered_duration_seconds"] == 8800
    assert [block["object"] for block in result["blocks"]] == ["long"]


def test_plan_ideas_uses_darkness_intersection_and_deterministic_priority_ties():
    candidates = [
        candidate("B", 50, [{"start": 0, "end": 9000}]),
        candidate("A", 50, [{"start": 0, "end": 9000}]),
    ]
    result = plan_ideas(candidates, [{"start": 1000, "end": 9000}], 7200)

    assert result["status"] == "full"
    assert result["blocks"][0]["object"] == "A"
    assert result["blocks"][0]["start"] == 1000
    assert result["blocks"][0]["end"] == 8200


def test_plan_ideas_never_merges_separate_intervals():
    result = plan_ideas(
        [candidate("target", 80, [{"start": 0, "end": 4000}, {"start": 5000, "end": 9000}])],
        [{"start": 0, "end": 9000}],
        9000,
    )

    assert result["status"] == "none"
    assert result["blocks"] == []


def test_plan_ideas_caps_coverage_score_at_requested_duration_before_priority():
    result = plan_ideas(
        [
            candidate("high-priority", 100, [{"start": 0, "end": 7200}]),
            candidate("low-priority", 1, [{"start": 0, "end": 100000}]),
        ],
        [{"start": 0, "end": 100000}],
        7200,
    )

    assert [block["object"] for block in result["blocks"]] == ["high-priority"]


def test_select_astronomical_night_uses_complete_evening_to_morning_interval():
    intervals = [{"start": 22000, "end": 51000}]

    assert select_astronomical_night(intervals) == {"start": 22000, "end": 51000}


def test_select_astronomical_night_rejects_horizon_edge_fragments():
    intervals = [
        {"start": 0, "end": 5000},
        {"start": 22000, "end": 51000},
        {"start": 82000, "end": 86400},
    ]

    assert select_astronomical_night(intervals) == {"start": 22000, "end": 51000}


def test_select_astronomical_night_returns_none_without_complete_darkness():
    assert select_astronomical_night([]) is None
    assert select_astronomical_night([{"start": 0, "end": 4000}]) is None


def test_night_sequence_chains_complementary_targets_across_the_whole_night():
    candidates = [
        candidate("X", 30, [{"start": 0, "end": 10800}]),
        candidate("Y", 20, [{"start": 10800, "end": 21600}]),
        candidate("Z", 10, [{"start": 21600, "end": 28800}]),
    ]

    result = plan_night_sequence(candidates, {"start": 0, "end": 28800})

    assert [block["target"]["name"] for block in result["blocks"]] == ["X", "Y", "Z"]
    assert result["status"] == "full"
    assert result["covered_duration_seconds"] == 28800
    assert result["coverage_percent"] == 100
    assert result["gaps"] == []


def test_night_sequence_reports_unavoidable_gaps_and_preserves_offsets():
    result = plan_night_sequence(
        [
            candidate("X", 30, [{"start": 1000, "end": 8200}]),
            candidate("Y", 20, [{"start": 10000, "end": 17200}]),
        ],
        {"start": 1000, "end": 17200},
        slot_seconds=300,
    )

    assert result["status"] == "partial"
    assert result["gaps"] == [{"start": 8200, "end": 10000, "duration_seconds": 1800}]
    assert result["night_start"] == 1000
    assert result["night_end"] == 17200


def test_night_sequence_prefers_priority_without_sacrificing_coverage():
    result = plan_night_sequence(
        [
            candidate("Always low", 1, [{"start": 0, "end": 14400}]),
            candidate("Early high", 50, [{"start": 0, "end": 7200}]),
            candidate("Late high", 40, [{"start": 7200, "end": 14400}]),
        ],
        {"start": 0, "end": 14400},
    )

    assert [block["target"]["name"] for block in result["blocks"]] == ["Early high", "Late high"]
    assert result["covered_duration_seconds"] == 14400


def test_night_sequence_ties_are_deterministic_and_prefer_fewer_changes():
    candidates = [
        candidate("B", 20, [{"start": 0, "end": 14400}]),
        candidate("A", 20, [{"start": 0, "end": 14400}]),
    ]

    first = plan_night_sequence(candidates, {"start": 0, "end": 14400})
    second = plan_night_sequence(list(reversed(candidates)), {"start": 0, "end": 14400})

    assert [block["target"]["name"] for block in first["blocks"]] == ["A"]
    assert first == second


def test_night_sequence_labels_a_short_edge_fill_that_increases_coverage():
    result = plan_night_sequence(
        [
            candidate("Short edge", 30, [{"start": 0, "end": 3600}]),
            candidate("Main", 20, [{"start": 3600, "end": 10800}]),
        ],
        {"start": 0, "end": 10800},
    )

    assert result["status"] == "full"
    assert result["blocks"][0]["target"]["name"] == "Short edge"
    assert result["blocks"][0]["short_fill"] is True
    assert result["blocks"][1]["short_fill"] is False


def test_night_sequence_returns_none_when_no_target_is_usable():
    result = plan_night_sequence([], {"start": 22000, "end": 51000})

    assert result["status"] == "none"
    assert result["blocks"] == []
    assert result["gaps"] == [{"start": 22000, "end": 51000, "duration_seconds": 29000}]


def test_night_sequence_does_not_drop_the_thirteenth_visible_candidate():
    candidates = [
        candidate(chr(ord("A") + index), 100 - index, [{"start": 0, "end": 300}])
        for index in range(12)
    ]
    candidates.append(candidate("M", 1, [{"start": 0, "end": 7200}]))

    result = plan_night_sequence(candidates, {"start": 0, "end": 7200})

    assert [(block["target"]["name"], block["duration_seconds"]) for block in result["blocks"]] == [
        ("M", 7200),
    ]
    assert result["blocks"][0]["short_fill"] is False


def test_night_sequence_never_shortens_a_target_that_has_a_two_hour_window():
    result = plan_night_sequence(
        [
            candidate("C", 30, [{"start": 0, "end": 7200}]),
            candidate("A", 20, [{"start": 3600, "end": 10800}]),
        ],
        {"start": 0, "end": 10800},
    )

    assert result["status"] == "partial"
    assert [block["target"]["name"] for block in result["blocks"]] == ["C"]
    assert result["blocks"][0]["duration_seconds"] == 7200
    assert result["blocks"][0]["short_fill"] is False
    assert result["gaps"] == [{"start": 7200, "end": 10800, "duration_seconds": 3600}]


def test_night_sequence_rejects_fractional_boolean_and_duplicate_identifiers():
    with pytest.raises(ValueError, match="interi"):
        plan_night_sequence([], {"start": 0, "end": 7200}, slot_seconds=300.5)
    with pytest.raises(ValueError, match="interi"):
        plan_night_sequence([], {"start": False, "end": 7200})
    with pytest.raises(ValueError, match="univoci"):
        plan_night_sequence(
            [
                candidate("Same", 10, [{"start": 0, "end": 7200}]),
                candidate("same", 20, [{"start": 0, "end": 7200}]),
            ],
            {"start": 0, "end": 7200},
        )
    with pytest.raises(ValueError, match="candidato"):
        plan_night_sequence(["not-a-candidate"], {"start": 0, "end": 7200})
    with pytest.raises(ValueError, match="intervalli"):
        plan_night_sequence(
            [candidate("Fractional", 10, [{"start": 0.5, "end": 7200}])],
            {"start": 0, "end": 7200},
        )
    with pytest.raises(ValueError, match="priorita"):
        plan_night_sequence(
            [candidate("Fractional priority", 10.5, [{"start": 0, "end": 7200}])],
            {"start": 0, "end": 7200},
        )


def test_night_sequence_can_trim_a_short_bridge_to_avoid_overlap_and_cover_all_time():
    result = plan_night_sequence(
        [
            candidate("A", 30, [{"start": 0, "end": 7200}]),
            candidate("S", 20, [{"start": 7200, "end": 7800}]),
            candidate("B", 10, [{"start": 7500, "end": 14700}]),
        ],
        {"start": 0, "end": 14700},
    )

    assert result["status"] == "full"
    assert [(block["target"]["name"], block["start"], block["end"]) for block in result["blocks"]] == [
        ("A", 0, 7200),
        ("S", 7200, 7500),
        ("B", 7500, 14700),
    ]
    assert result["blocks"][1]["short_fill"] is True
    assert result["gaps"] == []
