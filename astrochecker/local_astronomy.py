"""Offline Astropy transformations for the local AstroChecker runtime."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from functools import lru_cache
import operator
import threading
import warnings

import astropy.units as u
import numpy as np
from astropy.coordinates import (
    AltAz,
    EarthLocation,
    NonRotationTransformationWarning,
    SkyCoord,
    get_body,
    get_sun,
)
from astropy.time import Time, TimeDelta
from astropy.utils import iers

from .planner import SUN_LIMIT_DEGREES


DEFAULT_HORIZON_SECONDS = 86400
DEFAULT_KNOT_STEP_SECONDS = 30

# Runtime calculations must remain offline even when Astropy defaults change.
iers.conf.auto_download = False

_ASTROPY_LOCK = threading.Lock()


class AstronomyDataError(Exception):
    """Raised when bundled astronomy data cannot support a calculation."""


@dataclass(frozen=True)
class LocalEphemeris:
    target_alt: np.ndarray
    target_az: np.ndarray
    sun_alt: np.ndarray
    uses_prediction: bool
    iers_coverage_start: str
    iers_coverage_end_exclusive: str
    sample_offsets: np.ndarray | None = None
    moon_alt: np.ndarray | None = None
    moon_az: np.ndarray | None = None
    moon_illumination: np.ndarray | None = None
    moon_separation: np.ndarray | None = None

    def position_at(self, offset):
        try:
            index = operator.index(offset)
        except TypeError as exc:
            raise ValueError("Astronomical offset must be an integer number of seconds") from exc
        if self.sample_offsets is None:
            if not 0 <= index < len(self.target_alt):
                raise ValueError("Astronomical offset is outside the calculated period")
            sample_index = index
        else:
            if not 0 <= index <= int(self.sample_offsets[-1]):
                raise ValueError("Astronomical offset is outside the calculated period")
            sample_index = int(np.searchsorted(self.sample_offsets, index))
            if sample_index >= len(self.sample_offsets) or int(self.sample_offsets[sample_index]) != index:
                raise ValueError("Astronomical offset does not match the calculated grid")
        result = {
            "alt": float(self.target_alt[sample_index]),
            "az": float(self.target_az[sample_index]),
            "sun_alt": float(self.sun_alt[sample_index]),
        }
        optional = (
            ("moon_alt", self.moon_alt),
            ("moon_az", self.moon_az),
            ("moon_illumination", self.moon_illumination),
            ("moon_separation", self.moon_separation),
        )
        for name, values in optional:
            if values is not None:
                result[name] = float(values[sample_index])
        return result


@lru_cache(maxsize=1)
def _bundled_iers_table():
    try:
        return iers.IERS_A.open(iers.IERS_A_FILE)
    except (OSError, ValueError) as exc:
        raise AstronomyDataError(
            "The local IERS-A table is unavailable or invalid"
        ) from exc


def _time_metadata(table, start, horizon_seconds):
    start_utc = start.astimezone(timezone.utc)
    end_utc = start_utc + timedelta(seconds=horizon_seconds)
    endpoints = Time([start_utc, end_utc], scale="utc")
    try:
        _, ut1_status = table.ut1_utc(endpoints, return_status=True)
        _, _, polar_status = table.pm_xy(endpoints, return_status=True)
    except (IndexError, ValueError) as exc:
        raise AstronomyDataError(
            "The requested interval cannot be checked with local IERS data"
        ) from exc

    statuses = np.concatenate(
        (np.atleast_1d(ut1_status), np.atleast_1d(polar_status))
    )
    if np.any(statuses < 0):
        raise AstronomyDataError(
            "The full requested interval must fit within the local IERS-A table coverage"
        )

    first_mjd = float(table["MJD"][0].value)
    last_mjd = float(table["MJD"][-1].value)
    coverage_start = Time(first_mjd, format="mjd", scale="utc").isot
    coverage_end = Time(last_mjd, format="mjd", scale="utc").isot
    return (
        start_utc,
        bool(np.any(statuses == iers.FROM_IERS_A_PREDICTION)),
        coverage_start,
        coverage_end,
    )


def _horizontal_vectors(coordinates):
    altitude = np.asarray(coordinates.alt.to_value(u.rad), dtype=float)
    azimuth = np.asarray(coordinates.az.to_value(u.rad), dtype=float)
    horizontal = np.cos(altitude)
    return np.column_stack(
        (
            horizontal * np.cos(azimuth),
            horizontal * np.sin(azimuth),
            np.sin(altitude),
        )
    )


def _interpolate_vectors(knot_offsets, knot_vectors, offsets):
    vectors = np.column_stack(
        [
            np.interp(offsets, knot_offsets, knot_vectors[:, component])
            for component in range(3)
        ]
    )
    lengths = np.linalg.norm(vectors, axis=1)
    if not np.all(np.isfinite(vectors)) or np.any(lengths <= 0):
        raise AstronomyDataError("Calculated astronomical coordinates are invalid")
    return vectors / lengths[:, np.newaxis]


def _altitude_azimuth(vectors):
    altitude = np.degrees(np.arcsin(np.clip(vectors[:, 2], -1.0, 1.0)))
    azimuth = np.degrees(np.arctan2(vectors[:, 1], vectors[:, 0])) % 360.0
    return altitude, azimuth


def build_ephemeris(
    ra_deg,
    dec_deg,
    start,
    latitude,
    longitude,
    *,
    horizon_seconds=DEFAULT_HORIZON_SECONDS,
    knot_step_seconds=DEFAULT_KNOT_STEP_SECONDS,
    output_step_seconds=1,
):
    """Build one-second local positions from vectorized Astropy knots."""
    if not isinstance(start, datetime) or start.tzinfo is None:
        raise ValueError("Astronomical start must include a time zone")
    if isinstance(horizon_seconds, bool) or not isinstance(horizon_seconds, int):
        raise ValueError("Astronomical period must be an integer number of seconds")
    if horizon_seconds <= 0:
        raise ValueError("Astronomical period must be greater than zero")
    if isinstance(knot_step_seconds, bool) or not isinstance(knot_step_seconds, int):
        raise ValueError("Astronomical step must be an integer number of seconds")
    if knot_step_seconds <= 0:
        raise ValueError("Astronomical step must be greater than zero")
    if isinstance(output_step_seconds, bool) or not isinstance(output_step_seconds, int):
        raise ValueError("Astronomical output step must be an integer number of seconds")
    if output_step_seconds <= 0:
        raise ValueError("Astronomical output step must be greater than zero")

    table = _bundled_iers_table()
    start_utc, uses_prediction, coverage_start, coverage_end = _time_metadata(
        table, start, horizon_seconds
    )
    knot_offsets = np.arange(
        0, horizon_seconds + 1, knot_step_seconds, dtype=float
    )
    if knot_offsets[-1] != horizon_seconds:
        knot_offsets = np.append(knot_offsets, float(horizon_seconds))
    offsets = np.arange(0, horizon_seconds + 1, output_step_seconds, dtype=float)
    if offsets[-1] != horizon_seconds:
        offsets = np.append(offsets, float(horizon_seconds))

    try:
        times = Time(start_utc, scale="utc") + TimeDelta(knot_offsets, format="sec")
        location = EarthLocation.from_geodetic(
            lon=float(longitude) * u.deg,
            lat=float(latitude) * u.deg,
            height=0 * u.m,
        )
        target = SkyCoord(
            ra=float(ra_deg) * u.deg,
            dec=float(dec_deg) * u.deg,
            frame="icrs",
        )
        frame = AltAz(obstime=times, location=location, pressure=0 * u.hPa)
        with _ASTROPY_LOCK, warnings.catch_warnings(), iers.earth_orientation_table.set(
            table
        ):
            warnings.simplefilter("error", iers.IERSWarning)
            warnings.simplefilter("ignore", NonRotationTransformationWarning)
            moon = get_body("moon", times, location=location)
            sun_icrs = get_sun(times)
            target_knots = _horizontal_vectors(target.transform_to(frame))
            sun_knots = _horizontal_vectors(sun_icrs.transform_to(frame))
            moon_knots = _horizontal_vectors(moon.transform_to(frame))
            moon_separation_knots = target.transform_to(moon.frame).separation(moon).to_value(u.deg)
            moon_illumination_knots = 0.5 * (
                1 - np.cos(np.deg2rad(sun_icrs.separation(moon).to_value(u.deg)))
            )
    except iers.IERSWarning as exc:
        raise AstronomyDataError(
            "Astropy ha segnalato un limite nei dati IERS locali"
        ) from exc
    except AstronomyDataError:
        raise
    except (IndexError, TypeError, ValueError) as exc:
        raise AstronomyDataError("Local astronomy calculation failed") from exc

    target_vectors = _interpolate_vectors(knot_offsets, target_knots, offsets)
    sun_vectors = _interpolate_vectors(knot_offsets, sun_knots, offsets)
    moon_vectors = _interpolate_vectors(knot_offsets, moon_knots, offsets)
    target_alt, target_az = _altitude_azimuth(target_vectors)
    sun_alt, _ = _altitude_azimuth(sun_vectors)
    moon_alt, moon_az = _altitude_azimuth(moon_vectors)
    moon_illumination = np.interp(offsets, knot_offsets, moon_illumination_knots)
    moon_separation = np.interp(offsets, knot_offsets, moon_separation_knots)
    if not (
        np.all(np.isfinite(target_alt))
        and np.all(np.isfinite(target_az))
        and np.all(np.isfinite(sun_alt))
        and np.all(np.isfinite(moon_alt))
        and np.all(np.isfinite(moon_az))
        and np.all(np.isfinite(moon_illumination))
        and np.all(np.isfinite(moon_separation))
    ):
        raise AstronomyDataError("Calculated astronomical coordinates are not finite")

    return LocalEphemeris(
        target_alt=target_alt,
        target_az=target_az,
        sun_alt=sun_alt,
        uses_prediction=uses_prediction,
        iers_coverage_start=coverage_start,
        iers_coverage_end_exclusive=coverage_end,
        sample_offsets=offsets.astype(int),
        moon_alt=moon_alt,
        moon_az=moon_az,
        moon_illumination=moon_illumination,
        moon_separation=moon_separation,
    )


def build_catalog_ephemerides(
    coordinates,
    start,
    latitude,
    longitude,
    *,
    horizon_seconds=DEFAULT_HORIZON_SECONDS,
    knot_step_seconds=DEFAULT_KNOT_STEP_SECONDS,
    output_step_seconds=300,
):
    """Build coarse local ephemerides for many targets in one Astropy pass."""
    if not coordinates:
        return []
    if not isinstance(start, datetime) or start.tzinfo is None:
        raise ValueError("Astronomical start must include a time zone")
    try:
        ras = np.asarray([float(item[0]) for item in coordinates], dtype=float)
        decs = np.asarray([float(item[1]) for item in coordinates], dtype=float)
    except (TypeError, ValueError, IndexError) as exc:
        raise ValueError("Catalog coordinates are invalid") from exc
    if not np.all(np.isfinite(ras)) or not np.all(np.isfinite(decs)):
        raise ValueError("Catalog coordinates are not finite")
    if isinstance(horizon_seconds, bool) or not isinstance(horizon_seconds, int) or horizon_seconds <= 0:
        raise ValueError("Astronomical period must be an integer number of seconds")
    if isinstance(knot_step_seconds, bool) or not isinstance(knot_step_seconds, int) or knot_step_seconds <= 0:
        raise ValueError("Astronomical step must be an integer number of seconds")
    if isinstance(output_step_seconds, bool) or not isinstance(output_step_seconds, int) or output_step_seconds <= 0:
        raise ValueError("Astronomical output step must be an integer number of seconds")

    table = _bundled_iers_table()
    start_utc, uses_prediction, coverage_start, coverage_end = _time_metadata(
        table, start, horizon_seconds
    )
    knot_offsets = np.arange(0, horizon_seconds + 1, knot_step_seconds, dtype=float)
    if knot_offsets[-1] != horizon_seconds:
        knot_offsets = np.append(knot_offsets, float(horizon_seconds))
    offsets = np.arange(0, horizon_seconds + 1, output_step_seconds, dtype=float)
    if offsets[-1] != horizon_seconds:
        offsets = np.append(offsets, float(horizon_seconds))
    try:
        times = Time(start_utc, scale="utc") + TimeDelta(knot_offsets, format="sec")
        location = EarthLocation.from_geodetic(
            lon=float(longitude) * u.deg, lat=float(latitude) * u.deg, height=0 * u.m
        )
        targets = SkyCoord(ra=ras[:, None] * u.deg, dec=decs[:, None] * u.deg, frame="icrs")
        frame = AltAz(obstime=times, location=location, pressure=0 * u.hPa)
        with _ASTROPY_LOCK, warnings.catch_warnings(), iers.earth_orientation_table.set(table):
            warnings.simplefilter("error", iers.IERSWarning)
            warnings.simplefilter("ignore", NonRotationTransformationWarning)
            moon = get_body("moon", times, location=location)
            sun_icrs = get_sun(times)
            horizontal = targets.transform_to(frame)
            sun = sun_icrs.transform_to(frame)
            moon_horizontal = moon.transform_to(frame)
            moon_separation_knots = targets.transform_to(moon.frame).separation(moon).to_value(u.deg)
            moon_illumination_knots = 0.5 * (
                1 - np.cos(np.deg2rad(sun_icrs.separation(moon).to_value(u.deg)))
            )
    except iers.IERSWarning as exc:
        raise AstronomyDataError("Astropy ha segnalato un limite nei dati IERS locali") from exc
    except (IndexError, TypeError, ValueError) as exc:
        raise AstronomyDataError("Local astronomy calculation failed") from exc

    target_alt_knots = horizontal.alt.to_value(u.rad)
    target_az_knots = horizontal.az.to_value(u.rad)
    target_vectors = np.stack(
        (
            np.cos(target_alt_knots) * np.cos(target_az_knots),
            np.cos(target_alt_knots) * np.sin(target_az_knots),
            np.sin(target_alt_knots),
        ),
        axis=-1,
    )
    sun_vectors = _horizontal_vectors(sun)
    moon_vectors = _horizontal_vectors(moon_horizontal)

    def interpolate_rows(values):
        return np.vstack([np.interp(offsets, knot_offsets, row) for row in values])

    target_vectors = np.stack(
        [interpolate_rows(target_vectors[:, :, component]) for component in range(3)], axis=-1
    )
    lengths = np.linalg.norm(target_vectors, axis=2)
    if not np.all(np.isfinite(target_vectors)) or np.any(lengths <= 0):
        raise AstronomyDataError("Calculated astronomical coordinates are invalid")
    target_vectors /= lengths[:, :, None]
    target_alt = np.degrees(np.arcsin(np.clip(target_vectors[:, :, 2], -1.0, 1.0)))
    target_az = np.degrees(np.arctan2(target_vectors[:, :, 1], target_vectors[:, :, 0])) % 360.0
    sun_vectors = _interpolate_vectors(knot_offsets, sun_vectors, offsets)
    sun_alt, _ = _altitude_azimuth(sun_vectors)
    moon_vectors = _interpolate_vectors(knot_offsets, moon_vectors, offsets)
    moon_alt, moon_az = _altitude_azimuth(moon_vectors)
    moon_illumination = np.interp(offsets, knot_offsets, moon_illumination_knots)
    moon_separation = np.vstack([
        np.interp(offsets, knot_offsets, row) for row in moon_separation_knots
    ])
    grid = offsets.astype(int)
    return [
        LocalEphemeris(
            target_alt=target_alt[index],
            target_az=target_az[index],
            sun_alt=sun_alt,
            uses_prediction=uses_prediction,
            iers_coverage_start=coverage_start,
            iers_coverage_end_exclusive=coverage_end,
            sample_offsets=grid,
            moon_alt=moon_alt,
            moon_az=moon_az,
            moon_illumination=moon_illumination,
            moon_separation=moon_separation[index],
        )
        for index in range(len(ras))
    ]


def summarize_darkness(sun_altitudes, limit=SUN_LIMIT_DEGREES):
    """Describe a darkness envelope without inventing clipped-edge events."""
    values = np.asarray(sun_altitudes, dtype=float)
    if values.ndim != 1 or values.size == 0 or not np.all(np.isfinite(values)):
        raise ValueError("Le altezze del Sole devono essere una sequenza finita")
    dark = values <= float(limit)
    horizon = len(dark) - 1
    intervals = []
    events = []
    current_start = 0 if bool(dark[0]) else None

    for offset in range(1, len(dark)):
        now_dark = bool(dark[offset])
        before_dark = bool(dark[offset - 1])
        if before_dark and not now_dark:
            intervals.append({"start": current_start, "end": offset - 1})
            current_start = None
            if offset < horizon:
                events.append({"kind": "night_end", "offset": offset})
        elif not before_dark and now_dark:
            current_start = offset
            if offset < horizon:
                events.append({"kind": "night_start", "offset": offset})

    if current_start is not None:
        intervals.append({"start": current_start, "end": horizon})
    return {
        "at_start": bool(dark[0]),
        "intervals": intervals,
        "events": events,
    }


def summarize_moon(ephemeris, mask=None):
    """Summarize Moon altitude, illumination and mask occupancy on a grid."""
    values = (
        getattr(ephemeris, "moon_alt", None),
        getattr(ephemeris, "moon_az", None),
        getattr(ephemeris, "moon_illumination", None),
    )
    if any(value is None for value in values):
        raise ValueError("Moon ephemeris is incomplete")
    moon_alt, moon_az, illumination = (
        np.asarray(value, dtype=float) for value in values
    )
    if any(value.ndim != 1 for value in (moon_alt, moon_az, illumination)):
        raise ValueError("Moon ephemeris must be one-dimensional")
    if not (len(moon_alt) == len(moon_az) == len(illumination)) or not len(moon_alt):
        raise ValueError("Moon ephemeris arrays must have the same non-zero length")
    if not all(np.all(np.isfinite(value)) for value in (moon_alt, moon_az, illumination)):
        raise ValueError("Moon ephemeris must contain finite values")
    if np.any((illumination < 0) | (illumination > 1)):
        raise ValueError("Moon illumination must be between 0 and 1")

    offsets = getattr(ephemeris, "sample_offsets", None)
    if offsets is None:
        offsets = np.arange(len(moon_alt), dtype=int)
    else:
        offsets = np.asarray(offsets, dtype=int)
    if len(offsets) != len(moon_alt):
        raise ValueError("Moon sample offsets must match the ephemeris")

    def intervals_for(visible):
        intervals = []
        start = None
        for index, is_visible in enumerate([*visible, False]):
            if is_visible and start is None:
                start = index
            elif not is_visible and start is not None:
                intervals.append({
                    "start": int(offsets[start]),
                    "end": int(offsets[index - 1]),
                })
                start = None
        return intervals

    above = moon_alt > 0
    inside = np.array(
        [altitude >= 0 and mask.contains(azimuth, altitude)
         for azimuth, altitude in zip(moon_az, moon_alt)],
        dtype=bool,
    ) if mask is not None else np.zeros(len(moon_alt), dtype=bool)
    highest = int(np.argmax(moon_alt))
    return {
        "illumination": float(illumination[highest]),
        "maximum_altitude": float(moon_alt[highest]),
        "above_horizon": intervals_for(above),
        "inside_mask": intervals_for(inside) if mask is not None else [],
        "above_horizon_at_start": bool(above[0]),
        "above_horizon_at_end": bool(above[-1]),
    }
