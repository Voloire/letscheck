"""Deterministic Moon-avoidance rules for urban imaging plans."""

from __future__ import annotations

from dataclasses import dataclass
import math
from numbers import Real


SYNODIC_MONTH_DAYS = 29.530588853


class MoonPolicyError(ValueError):
    """Raised when a Moon policy or ephemeris value is invalid."""


def _finite(name, value):
    if isinstance(value, bool) or not isinstance(value, Real):
        raise MoonPolicyError(f"{name} must be a number")
    value = float(value)
    if not math.isfinite(value):
        raise MoonPolicyError(f"{name} must be finite")
    return value


@dataclass(frozen=True)
class MoonPolicy:
    """A classic Lorentzian Moon-separation policy.

    ``full_moon_separation_deg`` is the required separation at full Moon and
    ``width_days`` is the distance from full Moon at which that separation is
    halved.  The initial profiles are based on the values documented by NINA
    Target Scheduler; they remain explicit data so balcony calibration can
    change them without changing the rule.
    """

    filter: str
    full_moon_separation_deg: float
    width_days: float

    def __post_init__(self):
        if self.filter not in ("broadband", "narrowband"):
            raise MoonPolicyError("Moon filter must be broadband or narrowband")
        separation = _finite("Full-Moon separation", self.full_moon_separation_deg)
        width = _finite("Moon width", self.width_days)
        if not 0 <= separation <= 180:
            raise MoonPolicyError("Full-Moon separation must be between 0 and 180 degrees")
        if width <= 0:
            raise MoonPolicyError("Moon width must be greater than zero")

    def required_separation(self, illumination):
        """Return the classic Lorentzian threshold for illumination 0..1."""
        illumination = _finite("Moon illumination", illumination)
        if not 0 <= illumination <= 1:
            raise MoonPolicyError("Moon illumination must be between 0 and 1")
        # Illumination maps to Sun-Moon elongation: 0° at new Moon and
        # 180° at full Moon.  The absolute distance from full is enough for
        # this symmetric rule and avoids inventing a phase-age direction.
        elongation = math.degrees(math.acos(max(-1.0, min(1.0, 1 - 2 * illumination))))
        days_from_full = abs(180 - elongation) / 360 * SYNODIC_MONTH_DAYS
        return self.full_moon_separation_deg / (
            1 + (days_from_full / self.width_days) ** 2
        )

    def evaluate(self, *, moon_alt, moon_illumination, moon_separation):
        """Evaluate one instant and return stable numeric decision fields."""
        altitude = _finite("Moon altitude", moon_alt)
        separation = _finite("Moon-target separation", moon_separation)
        if not 0 <= separation <= 180:
            raise MoonPolicyError("Moon-target separation must be between 0 and 180 degrees")
        required = self.required_separation(moon_illumination)
        above_horizon = altitude > 0
        proximity = 1.0 if required == 0 else max(0.0, min(1.0, separation / required))
        closed = self.filter == "broadband" and above_horizon and separation < required
        return {
            "filter": self.filter,
            "moon_above_horizon": above_horizon,
            "required_separation_deg": required,
            "separation_deg": separation,
            "moon_factor": 0.0 if closed else (1.0 if self.filter == "broadband" else proximity),
            "closed": closed,
        }


# These are deliberately named constants, rather than hidden defaults.  They
# are the starting calibrations for the first balcony cases and can be changed
# after the owner's full/new-Moon review.
BROADBAND_POLICY = MoonPolicy("broadband", full_moon_separation_deg=120, width_days=14)
NARROWBAND_POLICY = MoonPolicy("narrowband", full_moon_separation_deg=60, width_days=7)


def policy_for_filter(filter_name=None):
    """Return the initial policy, defaulting to honest broadband."""
    filter_name = "broadband" if filter_name is None else filter_name
    if filter_name == "broadband":
        return BROADBAND_POLICY
    if filter_name == "narrowband":
        return NARROWBAND_POLICY
    raise MoonPolicyError("Moon filter must be broadband or narrowband")
