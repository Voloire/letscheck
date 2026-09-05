"""Visibility decisions and civil-time handling for AstroChecker."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone as utc_timezone
import math
from numbers import Real
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .idea_profiles import IDEA_MIN_BLOCK_SECONDS


RESOLUTION_SECONDS = 1
SUN_LIMIT_DEGREES = -18.0
MAX_FUTURE_SEARCH_DAYS = 90


def select_astronomical_night(intervals, horizon_seconds=86400):
    """Return the first darkness interval bounded inside the noon-to-noon horizon."""
    normalised = _normalise_intervals(intervals, 0, horizon_seconds)
    for start, end in normalised:
        if start > 0 and end < horizon_seconds:
            return {"start": start, "end": end}
    return None


def plan_night_sequence(
    candidates,
    night_interval,
    *,
    slot_seconds=300,
    preferred_block_seconds=7200,
):
    """Build a deterministic coverage-first target chain for one complete night."""
    def integer(name, value):
        if isinstance(value, bool) or not isinstance(value, Real) or not float(value).is_integer():
            raise ValueError(f"{name} deve essere un intero")
        return int(value)

    try:
        night_start = integer("L'inizio della notte", night_interval["start"])
        night_end = integer("La fine della notte", night_interval["end"])
        slot = integer("La granularita", slot_seconds)
        preferred = integer("Il blocco preferito", preferred_block_seconds)
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("Intervallo notturno e granularita devono essere interi") from exc
    if night_end <= night_start or slot <= 0 or preferred <= 0:
        raise ValueError("Intervallo notturno e granularita devono essere positivi")

    prepared = []
    candidate_keys = set()
    for item in candidates or []:
        if not isinstance(item, dict):
            raise ValueError("Ogni candidato del piano deve essere una mappa")
        profile = item.get("profile") or {}
        if not isinstance(profile, dict):
            raise ValueError("Il profilo del candidato deve essere una mappa")
        if profile.get("eligible", item.get("eligible", True)) is False:
            continue
        raw_intervals = item.get("intervals") or []
        if not isinstance(raw_intervals, (list, tuple)):
            raise ValueError("Gli intervalli del candidato devono essere una sequenza")
        validated_intervals = []
        for interval in raw_intervals:
            if not isinstance(interval, dict) or "start" not in interval or "end" not in interval:
                raise ValueError("Gli intervalli del candidato devono avere inizio e fine interi")
            try:
                start = integer("L'inizio degli intervalli", interval["start"])
                end = integer("La fine degli intervalli", interval["end"])
            except ValueError as exc:
                raise ValueError("Gli intervalli del candidato devono avere inizio e fine interi") from exc
            validated_intervals.append({"start": start, "end": end})
        intervals = _normalise_intervals(validated_intervals, night_start, night_end)
        if not intervals:
            continue
        name = str(item.get("name", item.get("object", ""))).strip()
        if not name:
            continue
        key = str(item.get("id") or name).casefold()
        if key in candidate_keys:
            raise ValueError("I candidati del piano devono avere identificativi univoci")
        candidate_keys.add(key)
        merged = []
        for start, end in intervals:
            if merged and start <= merged[-1][1]:
                merged[-1] = (merged[-1][0], max(merged[-1][1], end))
            else:
                merged.append((start, end))
        prepared.append({
            "key": key,
            "priority": integer("La priorita", profile.get("priority", item.get("priority", 0)) or 0),
            "intervals": merged,
            "target": {
                "name": name,
                "type": item.get("type", profile.get("category", "DSO")),
                "ra_deg": item.get("ra_deg"),
                "dec_deg": item.get("dec_deg"),
                "aliases": list(item.get("aliases") or []),
            },
            "reason": profile.get("reason", item.get("reason", "Finestra continua disponibile.")),
        })
    prepared.sort(key=lambda item: (-item["priority"], item["key"]))

    slots = []
    cursor = night_start
    while cursor < night_end:
        right = min(night_end, cursor + slot)
        slots.append((cursor, right))
        cursor = right
    boundaries = [slots[0][0], *(right for _, right in slots)] if slots else [night_start]

    # Candidates with identical slot availability are interchangeable.  Keeping
    # only the highest-priority canonical one is a correctness-preserving
    # reduction that matters for the full local catalogue.
    representatives = {}
    for item in prepared:
        visible_slots = tuple(
            index for index, (left, right) in enumerate(slots)
            if any(start <= left and end >= right for start, end in item["intervals"])
        )
        if not visible_slots:
            continue
        fingerprint = visible_slots
        current = representatives.get(fingerprint)
        if current is None or item["priority"] > current["priority"] or (
            item["priority"] == current["priority"] and item["key"] < current["key"]
        ):
            representatives[fingerprint] = item
    prepared = sorted(representatives.values(), key=lambda item: (-item["priority"], item["key"]))
    by_key = {item["key"]: item for item in prepared}

    options_by_end = [[] for _ in boundaries]
    for item in prepared:
        visible = [
            any(start <= left and end >= right for start, end in item["intervals"])
            for left, right in slots
        ]
        run_start = None
        runs = []
        for index, is_visible in enumerate([*visible, False]):
            if is_visible and run_start is None:
                run_start = index
            elif not is_visible and run_start is not None:
                runs.append((run_start, index))
                run_start = None
        for left_index, right_index in runs:
            run_duration = boundaries[right_index] - boundaries[left_index]
            if run_duration < preferred:
                for start_index in range(left_index, right_index):
                    for end_index in range(start_index + 1, right_index + 1):
                        options_by_end[end_index].append((start_index, item["key"], True))
                continue
            for start_index in range(left_index, right_index):
                for end_index in range(start_index + 1, right_index + 1):
                    if boundaries[end_index] - boundaries[start_index] >= preferred:
                        options_by_end[end_index].append((start_index, item["key"], False))

    def path_rank(path):
        return (
            path["covered_seconds"],
            -path["short_blocks"],
            path["priority_seconds"],
            -len(path["blocks"]),
        )

    def is_better(candidate_path, existing_path):
        if existing_path is None:
            return True
        candidate_rank = path_rank(candidate_path)
        existing_rank = path_rank(existing_path)
        if candidate_rank != existing_rank:
            return candidate_rank > existing_rank
        return candidate_path["signature"] < existing_path["signature"]

    empty_path = {
        "covered_seconds": 0,
        "priority_seconds": 0,
        "short_blocks": 0,
        "blocks": (),
        "signature": (),
    }
    best_at = [empty_path]
    for end_index in range(1, len(boundaries)):
        best = best_at[end_index - 1]
        for start_index, key, short_fill in options_by_end[end_index]:
            previous = best_at[start_index]
            start = boundaries[start_index]
            end = boundaries[end_index]
            duration = end - start
            candidate_path = {
                "covered_seconds": previous["covered_seconds"] + duration,
                "priority_seconds": previous["priority_seconds"] + by_key[key]["priority"] * duration,
                "short_blocks": previous["short_blocks"] + int(short_fill),
                "blocks": (*previous["blocks"], (start, end, key, short_fill)),
                "signature": (*previous["signature"], (start, end, key)),
            }
            if is_better(candidate_path, best):
                best = candidate_path
        best_at.append(best)

    winner = best_at[-1]
    blocks = []
    for start, end, key, short_fill in winner["blocks"]:
        duration = end - start
        item = by_key[key]
        blocks.append({
            "target": item["target"],
            "start": start,
            "end": end,
            "duration_seconds": duration,
            "priority": item["priority"],
            "reason": item["reason"],
            "short_fill": short_fill,
        })

    gaps = []
    cursor = night_start
    for block in blocks:
        if block["start"] > cursor:
            gaps.append({
                "start": cursor,
                "end": block["start"],
                "duration_seconds": block["start"] - cursor,
            })
        cursor = block["end"]
    if cursor < night_end:
        gaps.append({"start": cursor, "end": night_end, "duration_seconds": night_end - cursor})

    night_duration = night_end - night_start
    covered = sum(block["duration_seconds"] for block in blocks)
    percentage = round(100 * covered / night_duration, 1)
    if percentage.is_integer():
        percentage = int(percentage)
    status = "full" if covered == night_duration else ("partial" if covered else "none")
    return {
        "status": status,
        "night_start": night_start,
        "night_end": night_end,
        "night_duration_seconds": night_duration,
        "covered_duration_seconds": covered,
        "coverage_percent": percentage,
        "preferred_block_seconds": preferred,
        "blocks": blocks,
        "gaps": gaps,
        "object_count": len(blocks),
        "note": (
            "Piano completo dal crepuscolo astronomico serale a quello mattutino."
            if status == "full" else
            "Piano parziale: alcuni tratti della notte non hanno bersagli visibili compatibili."
            if status == "partial" else
            "Nessun bersaglio compatibile e visibile durante la notte astronomica."
        ),
    }


def plan_ideas(candidates, darkness_intervals, total_seconds, minimum_block_seconds=7200):
    """Choose deterministic, non-overlapping DSO blocks from supplied intervals.

    Visibility and darkness intervals are offsets from the requested start.  No
    astronomical calls are made here; callers may therefore test and reuse the
    planner with cached or precomputed intervals.
    """
    try:
        total = int(total_seconds)
        minimum = int(minimum_block_seconds)
    except (TypeError, ValueError) as exc:
        raise ValueError("La durata del piano deve essere espressa in secondi interi") from exc
    if total <= 0 or minimum <= 0:
        raise ValueError("La durata del piano e il blocco minimo devono essere positivi")

    if isinstance(darkness_intervals, dict):
        darkness_intervals = darkness_intervals.get("intervals", [])
    dark = _normalise_intervals(darkness_intervals, 0, max(total, 90 * 86400))
    options = []
    skipped = {"ineligible": 0, "short": 0, "no_window": 0}
    for candidate in candidates or []:
        profile = candidate.get("profile") or {}
        if profile.get("eligible", candidate.get("eligible", True)) is False:
            skipped["ineligible"] += 1
            continue
        visibility = candidate.get("intervals") or candidate.get("visibility_intervals") or []
        visibility = _normalise_intervals(visibility, 0, max(total, 90 * 86400))
        clipped = []
        for start, end in visibility:
            for dark_start, dark_end in dark:
                left, right = max(start, dark_start), min(end, dark_end)
                if right > left:
                    clipped.append((left, right))
        if not clipped:
            skipped["no_window"] += 1
            continue
        usable = [interval for interval in clipped if interval[1] - interval[0] >= minimum]
        if not usable:
            skipped["short"] += 1
            continue
        # One target gets one continuous block.  Separate source intervals are
        # never joined; select its longest deterministic interval.
        start, end = min(usable, key=lambda item: (-(item[1] - item[0]), item[0], item[1]))
        priority = int(profile.get("priority", candidate.get("priority", 0)) or 0)
        name = str(candidate.get("name", candidate.get("object", "")))
        options.append({
            "object": name,
            "type": candidate.get("type", profile.get("category", "DSO")),
            "start": start,
            "end": end,
            "priority": priority,
            "reason": profile.get("reason", candidate.get("reason", "Finestra continua disponibile.")),
        })

    options.sort(key=lambda item: (item["end"], item["start"], -item["priority"], item["object"].casefold()))
    previous = []
    for index, item in enumerate(options):
        previous.append(max((j for j in range(index) if options[j]["end"] <= item["start"]), default=-1))

    def score(blocks):
        return (
            min(total, sum(item["end"] - item["start"] for item in blocks)),
            sum(item["priority"] for item in blocks),
            -len(blocks),
        )

    best = [[] for _ in options]
    for index, item in enumerate(options):
        include = (best[previous[index]] if previous[index] >= 0 else []) + [item]
        exclude = best[index - 1] if index else []
        best[index] = include if score(include) > score(exclude) else exclude
    selected = list(best[-1]) if best else []
    selected.sort(key=lambda item: (item["start"], item["end"], -item["priority"], item["object"].casefold()))
    blocks = []
    remaining = total
    for item in selected:
        if remaining <= 0:
            break
        duration = min(item["end"] - item["start"], remaining)
        if duration < minimum:
            continue
        block = {**item, "end": item["start"] + duration, "duration_seconds": duration}
        blocks.append(block)
        remaining -= duration
    covered = total - remaining
    return {
        "status": "full" if covered >= total else ("partial" if covered else "none"),
        "requested_duration_seconds": total,
        "covered_duration_seconds": covered,
        "darkness_mode": "astronomical",
        "blocks": blocks,
        "object_count": len(blocks),
        "skipped": skipped,
        "note": (
            "Piano completo con blocchi continui di almeno due ore."
            if covered >= total else
            "Piano parziale: le finestre continue disponibili non coprono tutta la durata richiesta."
            if covered else
            "Nessun oggetto dispone di una finestra continua di almeno due ore nel buio richiesto."
        ),
    }


def _normalise_intervals(intervals, lower, upper):
    result = []
    for item in intervals or []:
        if not isinstance(item, dict):
            continue
        try:
            start, end = int(item["start"]), int(item["end"])
        except (KeyError, TypeError, ValueError):
            continue
        start, end = max(lower, start), min(upper, end)
        if end > start:
            result.append((start, end))
    return sorted(set(result))


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
