from astrochecker.planner import plan_ideas


def candidate(name, priority, intervals, **profile):
    return {
        "name": name,
        "type": profile.pop("type", "OCl"),
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
