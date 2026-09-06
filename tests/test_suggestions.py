from datetime import datetime

from astrochecker.planner import choose_suggestion, choose_suggestions
from astrochecker.planner import solve_visibility


def test_suggestion_prefers_nearest_same_day_window_and_preserves_duration():
    start = datetime(2026, 9, 5, 22, 0)
    result = choose_suggestion(
        start=start,
        duration_seconds=1800,
        current_intervals=[
            {"start": 0, "end": 900},
            {"start": 2400, "end": 5000},
        ],
        future_windows=[],
    )

    assert result["tier"] == "adjust"
    assert result["start"] == datetime(2026, 9, 5, 22, 40)
    assert result["end"] == datetime(2026, 9, 5, 23, 10)
    assert result["duration_seconds"] == 1800
    assert result["available_duration_seconds"] == 2600


def test_suggestion_uses_earliest_future_complete_window_before_shortest_fallback():
    start = datetime(2026, 9, 5, 22, 0)
    result = choose_suggestion(
        start=start,
        duration_seconds=3600,
        current_intervals=[{"start": 0, "end": 1200}],
        future_windows=[
            {
                "start": datetime(2026, 9, 6, 22, 0),
                "intervals": [{"start": 1800, "end": 5200}],
            },
            {
                "start": datetime(2026, 9, 7, 22, 0),
                "intervals": [{"start": 600, "end": 5000}],
            },
        ],
    )

    assert result["tier"] == "future"
    assert result["start"] == datetime(2026, 9, 7, 22, 10)
    assert result["end"] == datetime(2026, 9, 7, 23, 10)
    assert result["available_duration_seconds"] == 4400


def test_suggestion_falls_back_to_widest_window_and_explains_short_duration():
    start = datetime(2026, 9, 5, 22, 0)
    result = choose_suggestion(
        start=start,
        duration_seconds=3600,
        current_intervals=[{"start": 0, "end": 1200}],
        future_windows=[
            {
                "start": datetime(2026, 9, 6, 22, 0),
                "intervals": [{"start": 1800, "end": 3000}],
            },
        ],
    )

    assert result["tier"] == "widest"
    assert result["start"] == datetime(2026, 9, 5, 22, 0)
    assert result["end"] == datetime(2026, 9, 5, 22, 20)
    assert result["duration_seconds"] == 1200
    assert result["requested_duration_seconds"] == 3600
    assert result["available_duration_seconds"] == 1200


def test_suggestion_is_empty_when_target_has_no_visible_interval():
    assert choose_suggestion(
        start=datetime(2026, 9, 5, 22, 0),
        duration_seconds=3600,
        current_intervals=[],
        future_windows=[
            {
                "start": datetime(2026, 9, 6, 22, 0),
                "intervals": [],
            },
        ],
    ) is None


def test_future_probe_can_use_a_coarser_deterministic_resolution():
    calls = []

    def position_at(offset):
        calls.append(offset)
        return {"alt": 45, "az": 180, "sun_alt": -20}

    result = solve_visibility(
        position_at,
        duration_seconds=10,
        horizon_seconds=10,
        resolution_seconds=5,
        min_alt=0,
        max_alt=90,
        az_start=0,
        az_end=360,
    )

    assert calls == [0, 5, 10]
    assert result["first_window"] == {"start": 0, "end": 10}


def test_choose_suggestions_returns_ranked_real_alternatives_with_bounded_stars():
    start = datetime(2026, 9, 5, 22, 0)
    suggestions = choose_suggestions(
        start=start,
        duration_seconds=3600,
        current_intervals=[
            {"start": 1800, "end": 9000},
            {"start": 18000, "end": 24000},
        ],
        future_windows=[
            {"start": datetime(2026, 9, 6, 22, 0), "intervals": [{"start": 600, "end": 5400}]},
        ],
    )

    assert 1 <= len(suggestions) <= 3
    assert [item["tier"] for item in suggestions] == ["adjust", "adjust", "future"]
    assert all(1 <= item["stars"] <= 5 for item in suggestions)
    assert all(item["score"] >= 0 for item in suggestions)
    assert suggestions[0]["score"] >= suggestions[1]["score"] >= suggestions[2]["score"]
    assert choose_suggestion(
        start=start,
        duration_seconds=3600,
        current_intervals=[
            {"start": 1800, "end": 9000},
            {"start": 18000, "end": 24000},
        ],
        future_windows=[
            {"start": datetime(2026, 9, 6, 22, 0), "intervals": [{"start": 600, "end": 5400}]},
        ],
    ) == suggestions[0]


def test_choose_suggestions_does_not_pad_when_only_one_valid_window_exists():
    suggestions = choose_suggestions(
        start=datetime(2026, 9, 5, 22, 0),
        duration_seconds=3600,
        current_intervals=[{"start": 0, "end": 1800}],
        future_windows=[],
    )

    assert len(suggestions) == 1
    assert suggestions[0]["tier"] == "widest"


def test_choose_suggestions_intersects_candidates_with_astronomical_darkness():
    suggestions = choose_suggestions(
        start=datetime(2026, 9, 5, 12, 0),
        duration_seconds=3600,
        current_intervals=[{"start": 3600, "end": 10800}],
        darkness_intervals=[{"start": 7200, "end": 10800}],
        future_windows=[],
    )

    assert suggestions
    assert all(item["start"] >= datetime(2026, 9, 5, 14, 0) for item in suggestions)
    assert all(item["duration_seconds"] == 3600 for item in suggestions)


def test_choose_suggestions_does_not_present_the_same_window_twice():
    suggestions = choose_suggestions(
        start=datetime(2026, 9, 5, 22, 0),
        duration_seconds=3600,
        current_intervals=[{"start": 1800, "end": 9000}],
        future_windows=[],
    )

    assert len(suggestions) == 1
    assert suggestions[0]["tier"] == "adjust"
    assert suggestions[0]["available_duration_seconds"] == 7200
