"""Acceptance examples. Synthetic sky paths isolate the balcony/time decision.

Real SkyChart integration is tested separately; these paths are not ephemerides.
"""
import importlib
from datetime import datetime

import pytest


@pytest.fixture
def checker():
    try:
        return importlib.import_module('astrochecker.planner')
    except ModuleNotFoundError:
        pytest.fail('Missing observable feature: visibility planner is not implemented')


LIMITS = dict(min_alt=10, max_alt=30, az_start=90, az_end=270)


def sky(alt=20, az=180, sun_alt=-25):
    return dict(alt=alt, az=az, sun_alt=sun_alt)


def solve(checker, path, duration=120, horizon=600, **limits):
    return checker.solve_visibility(path, duration_seconds=duration,
        horizon_seconds=horizon, **(LIMITS | limits))


def test_full_requested_duration_and_first_window(checker):
    result = solve(checker, lambda t: sky())
    assert result['status'] == 'full'
    assert result['requested_visible_seconds'] == 120
    assert result['first_window'] == {'start': 0, 'end': 120}


def test_ceiling_exit_makes_request_partial(checker):
    result = solve(checker, lambda t: sky(alt=20 if t < 60 else 40))
    assert result['status'] == 'partial'
    assert 58 <= result['requested_visible_seconds'] <= 60
    assert result['first_window'] is None


def test_first_later_complete_window(checker):
    result = solve(checker, lambda t: sky(alt=20 if 180 <= t <= 420 else 40))
    assert result['status'] == 'none'
    assert 180 <= result['first_window']['start'] <= 181
    assert result['first_window']['end'] - result['first_window']['start'] == 120


def test_enters_during_requested_period_is_partial_not_none(checker):
    result = solve(checker, lambda t: sky(alt=20 if t >= 60 else 40))
    assert result['status'] == 'partial'
    assert 59 <= result['requested_visible_seconds'] <= 60
    assert result['first_window'] == {'start': 60, 'end': 180}


def test_requested_available_time_includes_all_overlaps_without_joining_windows(checker):
    result = solve(checker, lambda t: sky(alt=20 if t < 30 or 60 <= t < 90 else 40))
    assert result['status'] == 'partial'
    assert 56 <= result['requested_visible_seconds'] <= 60
    assert result['first_window'] is None


def test_separate_short_intervals_cannot_be_combined(checker):
    result = solve(checker, lambda t: sky(alt=20 if t < 60 or 180 <= t < 240 else 40))
    assert result['first_window'] is None
    assert result['longest_visible_seconds'] <= 60


def test_ceiling_and_floor_both_exclude(checker):
    for altitude in (5, 35):
        result = solve(checker, lambda t: sky(alt=altitude))
        assert result['status'] == 'none'
        assert result['first_window'] is None


def test_north_crossing_sector(checker):
    for azimuth in (355, 0, 15):
        assert solve(checker, lambda t: sky(az=azimuth), az_start=350, az_end=20)['status'] == 'full'
    assert solve(checker, lambda t: sky(az=180), az_start=350, az_end=20)['status'] == 'none'


def test_daylight_excludes_otherwise_visible_target(checker):
    result = solve(checker, lambda t: sky(sun_alt=-10))
    assert result['status'] == 'none'
    assert result['first_window'] is None


def test_sunset_transition_opens_next_window(checker):
    result = solve(checker, lambda t: sky(sun_alt=-25 if t >= 240 else -10))
    assert 240 <= result['first_window']['start'] <= 241


def test_window_must_finish_inside_search_horizon(checker):
    result = solve(checker, lambda t: sky(alt=20 if t >= 540 else 40))
    assert result['first_window'] is None


def test_end_of_requested_interval_is_checked(checker):
    result = solve(checker, lambda t: sky(alt=20 if t < 119 else 40))
    assert result['status'] == 'partial'


def test_midnight_preserves_elapsed_duration(checker):
    start = checker.parse_start('2026-09-05T23:30', 'Europe/Rome')
    end = checker.elapsed_end(start, 7200)
    assert end.isoformat() == '2026-09-06T01:30:00+02:00'


def test_dst_elapsed_duration_and_invalid_wall_times(checker):
    start = checker.parse_start('2026-03-29T01:30', 'Europe/Rome')
    assert checker.elapsed_end(start, 7200).isoformat() == '2026-03-29T04:30:00+02:00'
    for wall_time in ('2026-03-29T02:30', '2026-10-25T02:30'):
        with pytest.raises(ValueError):
            checker.parse_start(wall_time, 'Europe/Rome')


@pytest.mark.parametrize('duration', [0, -1, float('nan'), float('inf')])
def test_invalid_duration_is_rejected(checker, duration):
    with pytest.raises(ValueError):
        solve(checker, lambda t: sky(), duration=duration)


@pytest.mark.parametrize('limits', [dict(min_alt=40, max_alt=30), dict(max_alt=91),
    dict(min_alt=float('nan')), dict(az_start=-1), dict(az_end=361)])
def test_invalid_balcony_is_rejected(checker, limits):
    with pytest.raises(ValueError):
        solve(checker, lambda t: sky(), **limits)


def test_reversed_full_circle_endpoints_are_not_a_hidden_full_horizon(checker):
    with pytest.raises(ValueError):
        solve(checker, lambda t: sky(), az_start=360, az_end=0)


def test_duration_cannot_exceed_search_period(checker):
    with pytest.raises(ValueError):
        solve(checker, lambda t: sky(), duration=601, horizon=600)


def test_start_requires_time_as_well_as_date(checker):
    with pytest.raises(ValueError):
        checker.parse_start('2026-09-05', 'Europe/Rome')
