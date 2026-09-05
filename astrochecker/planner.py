"""Visibility decisions and civil-time handling for AstroChecker."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone as utc_timezone
import math
from numbers import Real
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


RESOLUTION_SECONDS = 1
SUN_LIMIT_DEGREES = -18.0
MAX_FUTURE_SEARCH_DAYS = 90


def _finite_number(name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError(f"{name} deve essere un numero")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{name} deve essere finito")
    return number


def validate_limits(*, duration_seconds: object, horizon_seconds: object,
                    min_alt: object, max_alt: object,
                    az_start: object, az_end: object) -> dict[str, float]:
    """Validate and normalize planner inputs without contacting SkyChart."""
    duration = _finite_number("La durata", duration_seconds)
    horizon = _finite_number("Il periodo di ricerca", horizon_seconds)
    floor = _finite_number("L'altezza minima", min_alt)
    ceiling = _finite_number("L'altezza massima", max_alt)
    azimuth_start = _finite_number("L'azimut iniziale", az_start)
    azimuth_end = _finite_number("L'azimut finale", az_end)

    if duration <= 0:
        raise ValueError("La durata deve essere maggiore di zero")
    if horizon <= 0:
        raise ValueError("Il periodo di ricerca deve essere maggiore di zero")
    if duration > horizon:
        raise ValueError("La durata non puo superare il periodo di ricerca")
    if not 0 <= floor <= 90 or not 0 <= ceiling <= 90:
        raise ValueError("Le altezze devono essere comprese tra 0 e 90 gradi")
    if ceiling <= floor:
        raise ValueError("L'altezza massima deve superare quella minima")
    if not 0 <= azimuth_start <= 360 or not 0 <= azimuth_end <= 360:
        raise ValueError("Gli azimut devono essere compresi tra 0 e 360 gradi")
    if azimuth_start == azimuth_end or (
        azimuth_start % 360 == azimuth_end % 360
        and not (azimuth_start == 0 and azimuth_end == 360)
    ):
        raise ValueError("Un settore con azimut iniziale e finale uguali e ambiguo")

    return {
        "duration_seconds": duration,
        "horizon_seconds": horizon,
        "min_alt": floor,
        "max_alt": ceiling,
        "az_start": azimuth_start,
        "az_end": azimuth_end,
    }


def azimuth_is_visible(azimuth: object, start: float, end: float) -> bool:
    """Return whether an azimuth lies in the inclusive balcony sector."""
    az = _finite_number("L'azimut calcolato", azimuth) % 360.0
    if start == 0 and end == 360:
        return True
    normalized_start = start % 360.0
    normalized_end = end % 360.0
    if normalized_start < normalized_end:
        return normalized_start <= az <= normalized_end
    return az >= normalized_start or az <= normalized_end


def position_is_visible(position: object, *, min_alt: float, max_alt: float,
                        az_start: float, az_end: float) -> bool:
    if not isinstance(position, dict):
        raise ValueError("SkyChart ha restituito una posizione non valida")
    try:
        altitude = _finite_number("L'altezza calcolata", position["alt"])
        sun_altitude = _finite_number("L'altezza del Sole", position["sun_alt"])
        azimuth = position["az"]
    except KeyError as exc:
        raise ValueError("SkyChart ha restituito una posizione incompleta") from exc
    return (
        min_alt <= altitude <= max_alt
        and azimuth_is_visible(azimuth, az_start, az_end)
        and sun_altitude <= SUN_LIMIT_DEGREES
    )


def solve_visibility(position_at, *, duration_seconds, horizon_seconds=86400,
                     min_alt, max_alt, az_start, az_end,
                     resolution_seconds=RESOLUTION_SECONDS):
    """Search valid continuous intervals using conservative one-second samples."""
    values = validate_limits(
        duration_seconds=duration_seconds,
        horizon_seconds=horizon_seconds,
        min_alt=min_alt,
        max_alt=max_alt,
        az_start=az_start,
        az_end=az_end,
    )
    if not callable(position_at):
        raise ValueError("La sorgente delle posizioni non e valida")
    if isinstance(resolution_seconds, bool) or not isinstance(resolution_seconds, int):
        raise ValueError("La risoluzione deve essere espressa in secondi interi")
    if resolution_seconds <= 0:
        raise ValueError("La risoluzione deve essere maggiore di zero")

    horizon_end = int(math.floor(values["horizon_seconds"]))
    required = values["duration_seconds"]
    intervals: list[dict[str, int]] = []
    current_start: int | None = None
    offsets = list(range(0, horizon_end + 1, resolution_seconds))
    if offsets[-1] != horizon_end:
        offsets.append(horizon_end)
    previous_offset = None

    for elapsed in offsets:
        visible = position_is_visible(
            position_at(elapsed),
            min_alt=values["min_alt"],
            max_alt=values["max_alt"],
            az_start=values["az_start"],
            az_end=values["az_end"],
        )
        if visible and current_start is None:
            current_start = elapsed
        elif not visible and current_start is not None:
            intervals.append({"start": current_start, "end": previous_offset})
            current_start = None
        previous_offset = elapsed
    if current_start is not None:
        intervals.append({"start": current_start, "end": horizon_end})

    requested_visible = sum(
        max(0.0, min(item["end"], required) - max(item["start"], 0))
        for item in intervals
        if item["start"] < required and item["end"] > 0
    )

    longest = max((item["end"] - item["start"] for item in intervals), default=0)
    first_window = None
    for item in intervals:
        if item["end"] - item["start"] >= required:
            first_window = {"start": item["start"], "end": item["start"] + required}
            break

    if intervals and intervals[0]["start"] == 0 and intervals[0]["end"] >= required:
        status = "full"
    elif requested_visible > 0:
        status = "partial"
    else:
        status = "none"

    def tidy(number: float):
        return int(number) if float(number).is_integer() else number

    if first_window is not None:
        first_window = {key: tidy(value) for key, value in first_window.items()}

    return {
        "status": status,
        "requested_visible_seconds": tidy(requested_visible),
        "longest_visible_seconds": longest,
        "first_window": first_window,
        "intervals": intervals,
        "horizon_edges": {
            "start": bool(intervals and intervals[0]["start"] == 0),
            "end": bool(intervals and intervals[-1]["end"] == horizon_end),
        },
        "horizon_seconds": tidy(values["horizon_seconds"]),
        "resolution_seconds": RESOLUTION_SECONDS,
    }


def choose_suggestion(*, start, duration_seconds, current_intervals, future_windows):
    """Choose one deterministic fallback proposal for an invalid request.

    ``future_windows`` contains records with an aware/naive ``start`` and
    intervals expressed as seconds from that start.  The first usable tier is
    a same-period adjustment, then the earliest future complete window, then
    the longest continuous window available in the searched records.
    """
    required = int(duration_seconds)

    def length(item):
        return max(0, int(item["end"]) - int(item["start"]))

    def proposal(tier, window_start, available):
        return {
            "tier": tier,
            "start": window_start,
            "end": window_start + timedelta(seconds=required if tier != "widest" else available),
            "duration_seconds": required if tier != "widest" else available,
            "requested_duration_seconds": required,
        }

    current = list(current_intervals or [])
    if any(int(item["start"]) == 0 and length(item) >= required for item in current):
        return None

    adjustments = [item for item in current if int(item["start"]) > 0 and length(item) >= required]
    if adjustments:
        item = min(adjustments, key=lambda candidate: int(candidate["start"]))
        return proposal("adjust", start + timedelta(seconds=int(item["start"])), required)

    future_complete = []
    all_windows = [(start, item) for item in current]
    for record in future_windows or []:
        period_start = record["start"]
        for item in record.get("intervals", []):
            window_start = period_start + timedelta(seconds=int(item["start"]))
            all_windows.append((window_start, item))
            if length(item) >= required and window_start > start:
                future_complete.append((window_start, item))
    if future_complete:
        window_start, _ = min(future_complete, key=lambda candidate: candidate[0])
        return proposal("future", window_start, required)

    available = [(window_start, length(item)) for window_start, item in all_windows if length(item) > 0]
    if not available:
        return None
    window_start, longest = min(available, key=lambda candidate: (-candidate[1], candidate[0]))
    return proposal("widest", window_start, longest)


def parse_start(value, timezone="Europe/Rome"):
    """Parse an unambiguous local wall time in the selected IANA timezone."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Data e ora di inizio obbligatorie")
    if "T" not in value:
        raise ValueError("Data e ora di inizio devono includere l'orario")
    try:
        parsed = datetime.fromisoformat(value.strip())
    except ValueError as exc:
        raise ValueError("Data e ora di inizio non valide") from exc
    if parsed.tzinfo is not None:
        raise ValueError("Inserire un orario locale senza offset")
    try:
        zone = ZoneInfo(timezone)
    except (ZoneInfoNotFoundError, TypeError) as exc:
        raise ValueError("Fuso orario non disponibile") from exc

    candidates = []
    for fold in (0, 1):
        aware = parsed.replace(tzinfo=zone, fold=fold)
        round_trip = aware.astimezone(utc_timezone.utc).astimezone(zone)
        if round_trip.replace(tzinfo=None) == parsed and round_trip.fold == fold:
            candidates.append(aware)
    if len(candidates) != 1:
        raise ValueError("L'orario locale e inesistente o ambiguo; sceglierne un altro")
    return candidates[0]


def elapsed_end(start, seconds):
    """Add physical elapsed seconds across midnight and daylight-saving changes."""
    if not isinstance(start, datetime) or start.tzinfo is None:
        raise ValueError("L'inizio deve includere il fuso orario")
    elapsed = _finite_number("La durata", seconds)
    if elapsed < 0:
        raise ValueError("La durata non puo essere negativa")
    return (start.astimezone(utc_timezone.utc) + timedelta(seconds=elapsed)).astimezone(start.tzinfo)
