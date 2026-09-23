import pytest

from astrochecker.moon import (
    BROADBAND_POLICY,
    NARROWBAND_POLICY,
    MoonPolicy,
    MoonPolicyError,
)


def test_lorentzian_threshold_is_highest_at_full_moon_and_halves_at_width():
    policy = MoonPolicy("broadband", full_moon_separation_deg=120, width_days=14)

    assert policy.required_separation(1) == pytest.approx(120)
    quarter = policy.required_separation(0.5)
    assert quarter == pytest.approx(120 / (1 + (7.382647 / 14) ** 2), rel=1e-5)
    assert policy.required_separation(0) < quarter


def test_broadband_moon_is_a_wall_only_when_above_horizon_and_too_close():
    blocked = BROADBAND_POLICY.evaluate(
        moon_alt=25, moon_illumination=1, moon_separation=30
    )
    down = BROADBAND_POLICY.evaluate(
        moon_alt=-2, moon_illumination=1, moon_separation=30
    )

    assert blocked["closed"] is True
    assert blocked["moon_factor"] == 0
    assert down["closed"] is False
    assert down["moon_factor"] == 1


def test_narrowband_moon_never_closes_an_interval_and_reports_a_factor():
    result = NARROWBAND_POLICY.evaluate(
        moon_alt=35, moon_illumination=1, moon_separation=10
    )

    assert result["closed"] is False
    assert 0 <= result["moon_factor"] < 1


@pytest.mark.parametrize("policy", [BROADBAND_POLICY, NARROWBAND_POLICY])
def test_policy_rejects_invalid_ephemeris_values(policy):
    with pytest.raises(MoonPolicyError, match="between 0 and 1"):
        policy.required_separation(2)
    with pytest.raises(MoonPolicyError, match="between 0 and 180"):
        policy.evaluate(moon_alt=20, moon_illumination=0.5, moon_separation=181)
