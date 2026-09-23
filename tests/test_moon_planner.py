import pytest

from astrochecker.moon import BROADBAND_POLICY, NARROWBAND_POLICY
from astrochecker.planner import position_is_visible, solve_visibility


def _position(**changes):
    position = {
        "alt": 30,
        "az": 120,
        "sun_alt": -20,
        "moon_alt": 25,
        "moon_illumination": 1,
        "moon_separation": 30,
    }
    position.update(changes)
    return position


def test_broadband_policy_closes_a_visible_target_when_the_moon_is_too_close():
    assert not position_is_visible(
        _position(), min_alt=0, max_alt=90, az_start=0, az_end=360,
        moon_policy=BROADBAND_POLICY,
    )


def test_narrowband_policy_keeps_the_same_target_open():
    assert position_is_visible(
        _position(), min_alt=0, max_alt=90, az_start=0, az_end=360,
        moon_policy=NARROWBAND_POLICY,
    )


def test_visibility_solver_uses_the_moon_policy_without_changing_legacy_defaults():
    result = solve_visibility(
        lambda _offset: _position(),
        duration_seconds=10,
        horizon_seconds=10,
        min_alt=0,
        max_alt=90,
        az_start=0,
        az_end=360,
        resolution_seconds=1,
        moon_policy=BROADBAND_POLICY,
    )

    assert result["status"] == "none"
    assert result["intervals"] == []


def test_moon_policy_requires_moon_fields_when_enabled():
    with pytest.raises(ValueError, match="incomplete Moon"):
        position_is_visible(
            {"alt": 30, "az": 120, "sun_alt": -20},
            min_alt=0, max_alt=90, az_start=0, az_end=360,
            moon_policy=BROADBAND_POLICY,
        )
