"""Application service for the offline local-catalog runtime."""

from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
import threading

from .catalog import (
    AmbiguousObjectError,
    Catalog,
    CatalogError,
    ObjectNotFoundError,
)
from .idea_profiles import IDEA_MIN_BLOCK_SECONDS
from .local_astronomy import (
    AstronomyDataError,
    build_ephemeris,
    build_catalog_ephemerides,
    summarize_darkness,
)
from .planner import (
    MAX_FUTURE_SEARCH_DAYS,
    choose_suggestion,
    elapsed_end,
    parse_start,
    plan_night_sequence,
    position_is_visible,
    select_astronomical_night,
    solve_visibility,
)
from .server import ApiError, validate_check_request, validate_ideas_request, validate_site_request


HORIZON_SECONDS = 86400
CHART_STEP_SECONDS = 300
FUTURE_PROBE_STEP_SECONDS = 300
IDEA_PROBE_STEP_SECONDS = 300


def observing_night_anchor(start, timezone_name):
    """Use the selected civil date as the evening date for a full-night plan."""
    return parse_start(f"{start.date().isoformat()}T12:00", timezone_name)


def _tidy(number):
    return int(number) if float(number).is_integer() else number


def _select_idea_candidates(records, *, limit=120):
    """Keep a fast, deterministic shortlist while preserving profile variety."""
    eligible = [
        item for item in records
        if (item.get("profile") or {}).get("eligible", item.get("eligible", False))
    ]
    if limit is None:
        return eligible
    bounded_limit = max(1, int(limit))
    selected = []
    seen_types = set()
    for item in eligible:
        object_type = str(item.get("type", "")).upper()
        if object_type and object_type not in seen_types:
            selected.append(item)
            seen_types.add(object_type)
        if len(selected) >= bounded_limit:
            return selected[:bounded_limit]
    selected_ids = {id(item) for item in selected}
    selected.extend(item for item in eligible if id(item) not in selected_ids)
    return selected[:bounded_limit]


def default_site_path():
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        return Path(local_app_data) / "AstroChecker" / "site.json"
    return Path.home() / ".astrochecker" / "site.json"


class AstroCheckerService:
    def __init__(self, catalog=None, site_path=None):
        self.catalog = catalog if catalog is not None else Catalog()
        self.site_path = Path(site_path) if site_path is not None else default_site_path()
        self._site_lock = threading.Lock()

    def status(self):
        return self.catalog.status()

    def objects(self, query):
        if not isinstance(query, str):
            raise ValueError("Object search must be text")
        query = query.strip()
        if len(query) > 200:
            raise ValueError("Object search cannot exceed 200 characters")
        try:
            return {"objects": self.catalog.search(query, limit=10)}
        except CatalogError as exc:
            raise ApiError(str(exc), "catalog", 503) from exc

    def _resolve(self, query):
        try:
            return self.catalog.resolve(query)
        except ObjectNotFoundError as exc:
            raise ApiError(str(exc), "object", 404) from exc
        except AmbiguousObjectError as exc:
            raise ApiError(str(exc), "object", 409) from exc
        except CatalogError as exc:
            raise ApiError(str(exc), "catalog", 503) from exc

    def _future_windows(self, selected, request, current_result):
        """Search later dates locally, stopping at the first complete window."""
        records = []
        try:
            probe = build_ephemeris(
                selected["ra_deg"],
                selected["dec_deg"],
                request["start"],
                request["latitude"],
                request["longitude"],
                horizon_seconds=(MAX_FUTURE_SEARCH_DAYS + 1) * HORIZON_SECONDS,
                knot_step_seconds=FUTURE_PROBE_STEP_SECONDS,
                output_step_seconds=FUTURE_PROBE_STEP_SECONDS,
            )
        except AstronomyDataError:
            return records

        for day in range(1, MAX_FUTURE_SEARCH_DAYS + 1):
            future_start = elapsed_end(request["start"], day * HORIZON_SECONDS)
            base_offset = day * HORIZON_SECONDS
            future_result = solve_visibility(
                lambda offset, base_offset=base_offset: probe.position_at(base_offset + offset),
                duration_seconds=request["duration_seconds"],
                horizon_seconds=HORIZON_SECONDS,
                min_alt=request["min_alt"],
                max_alt=request["max_alt"],
                az_start=request["az_start"],
                az_end=request["az_end"],
                resolution_seconds=FUTURE_PROBE_STEP_SECONDS,
            )
            records.append({"start": future_start, "intervals": future_result["intervals"]})
            candidate = choose_suggestion(
                start=request["start"],
                duration_seconds=request["duration_seconds"],
                current_intervals=current_result["intervals"],
                future_windows=records,
            )
            if candidate and candidate["tier"] == "future":
                try:
                    exact_ephemeris = build_ephemeris(
                        selected["ra_deg"],
                        selected["dec_deg"],
                        future_start,
                        request["latitude"],
                        request["longitude"],
                        horizon_seconds=HORIZON_SECONDS,
                    )
                    exact_result = solve_visibility(
                        exact_ephemeris.position_at,
                        duration_seconds=request["duration_seconds"],
                        horizon_seconds=HORIZON_SECONDS,
                        min_alt=request["min_alt"],
                        max_alt=request["max_alt"],
                        az_start=request["az_start"],
                        az_end=request["az_end"],
                    )
                    records[-1]["intervals"] = exact_result["intervals"]
                except AstronomyDataError:
                    continue
                break
        candidate = choose_suggestion(
            start=request["start"],
            duration_seconds=request["duration_seconds"],
            current_intervals=current_result["intervals"],
            future_windows=records,
        )
        if records and (candidate is None or candidate["tier"] != "future"):
            widest_record = max(
                records,
                key=lambda record: max(
                    (item["end"] - item["start"] for item in record["intervals"]),
                    default=0,
                ),
            )
            try:
                exact_ephemeris = build_ephemeris(
                    selected["ra_deg"],
                    selected["dec_deg"],
                    widest_record["start"],
                    request["latitude"],
                    request["longitude"],
                    horizon_seconds=HORIZON_SECONDS,
                )
                exact_result = solve_visibility(
                    exact_ephemeris.position_at,
                    duration_seconds=request["duration_seconds"],
                    horizon_seconds=HORIZON_SECONDS,
                    min_alt=request["min_alt"],
                    max_alt=request["max_alt"],
                    az_start=request["az_start"],
                    az_end=request["az_end"],
                )
                widest_record["intervals"] = exact_result["intervals"]
            except AstronomyDataError:
                pass
        return records

    @staticmethod
    def _suggestion_note(suggestion, *, has_any_window):
        if suggestion is None:
            return (
                "The object is not visible in any continuous window over the next 90 days."
                if not has_any_window
                else "Non esiste una proposta che rispetti i criteri indicati."
            )
        if suggestion["tier"] == "adjust":
            return "Move the time while keeping the requested duration, using the first useful continuous window in the period."
        if suggestion["tier"] == "future":
            return "First future date within 90 days with a continuous window long enough for the requested duration."
        return "The requested duration is unavailable; this is the widest continuous window found over the next 90 days."

    def check(self, payload):
        request = validate_check_request(payload)
        selected = self._resolve(request["object"])
        try:
            ephemeris = build_ephemeris(
                selected["ra_deg"],
                selected["dec_deg"],
                request["start"],
                request["latitude"],
                request["longitude"],
                horizon_seconds=HORIZON_SECONDS,
            )
        except AstronomyDataError as exc:
            raise ApiError(str(exc), "calculation", 502) from exc

        result = solve_visibility(
            ephemeris.position_at,
            duration_seconds=request["duration_seconds"],
            horizon_seconds=HORIZON_SECONDS,
            min_alt=request["min_alt"],
            max_alt=request["max_alt"],
            az_start=request["az_start"],
            az_end=request["az_end"],
        )
        future_windows = []
        suggestion = None
        if result["status"] != "full":
            current_candidate = choose_suggestion(
                start=request["start"],
                duration_seconds=request["duration_seconds"],
                current_intervals=result["intervals"],
                future_windows=[],
            )
            if current_candidate and current_candidate["tier"] == "adjust":
                suggestion = current_candidate
            else:
                future_windows = self._future_windows(selected, request, result)
                suggestion = choose_suggestion(
                    start=request["start"],
                    duration_seconds=request["duration_seconds"],
                    current_intervals=result["intervals"],
                    future_windows=future_windows,
                )
        samples = []
        for offset in range(0, HORIZON_SECONDS + 1, CHART_STEP_SECONDS):
            position = ephemeris.position_at(offset)
            samples.append(
                {
                    "offset": offset,
                    "alt": round(position["alt"], 4),
                    "az": round(position["az"], 4),
                    "sun_alt": round(position["sun_alt"], 4),
                    "visible": position_is_visible(
                        position,
                        min_alt=request["min_alt"],
                        max_alt=request["max_alt"],
                        az_start=request["az_start"],
                        az_end=request["az_end"],
                    ),
                }
            )

        iers_kind = "predittivi" if ephemeris.uses_prediction else "osservati"
        if suggestion is not None:
            suggestion = {
                **suggestion,
                "start": suggestion["start"].isoformat(),
                "end": suggestion["end"].isoformat(),
            }
        has_any_window = bool(
            result["intervals"] or any(record["intervals"] for record in future_windows)
        )
        suggestion_note = (
            ""
            if result["status"] == "full"
            else self._suggestion_note(suggestion, has_any_window=has_any_window)
        )
        return {
            **result,
            "object": {
                "name": selected["name"],
                "ra": round(selected["ra_deg"], 6),
                "dec": round(selected["dec_deg"], 6),
                "frame": selected["frame"],
                "type": selected["type"],
                "aliases": selected["aliases"],
                "common_names": selected.get("common_names", []),
                "target_group": selected.get("target_group"),
                "related_ids": selected.get("related_ids", []),
                "source": selected["source"],
            },
            "start": request["start"].isoformat(),
            "end": elapsed_end(
                request["start"], request["duration_seconds"]
            ).isoformat(),
            "search_end": elapsed_end(request["start"], HORIZON_SECONDS).isoformat(),
            "timezone": request["timezone"],
            "duration_seconds": _tidy(request["duration_seconds"]),
            "suggestions": [suggestion] if suggestion else [],
            "suggestion_note": suggestion_note,
            "suggestion_search_days": MAX_FUTURE_SEARCH_DAYS,
            "samples": samples,
            "darkness": summarize_darkness(ephemeris.sun_alt),
            "notes": [
                "Altezza geometrica senza rifrazione atmosferica; azimut da nord verso est.",
                "Coordinate ICRS e Sole builtin trasformati localmente con Astropy, senza accesso alla rete.",
                "Astropy is sampled every 30 seconds; interpolated horizontal vectors feed a conservative one-second decision grid. Tests verify the precision, but it is not a universal limit.",
                f"Earth orientation from the local IERS-A table ({iers_kind} for this interval), UTC coverage from {ephemeris.iers_coverage_start} to before {ephemeris.iers_coverage_end_exclusive}.",
                "Visibility uses geometry and the Sun at -18 degrees; weather, Moon, and imaging quality are not included.",
                "When the request is incomplete, future alternatives are searched locally for up to 90 days; the first complete window is then checked with the one-second grid.",
            ],
        }

    def ideas(self, payload):
        """Build a complete astronomical-night target chain from local ephemerides."""
        request = validate_ideas_request(payload)
        requested_start = request["start"]
        anchor = observing_night_anchor(requested_start, request["timezone"])
        try:
            records = self.catalog.idea_candidates(include_ineligible=True)
        except CatalogError as exc:
            raise ApiError(str(exc), "catalog", 503) from exc
        eligible = [item for item in records if (item.get("profile") or {}).get("eligible")]
        eligible.sort(key=lambda item: (
            -int((item.get("profile") or {}).get("priority", 0)),
            str(item.get("name", "")).casefold(),
            str(item.get("canonical_key", item.get("id", ""))),
        ))
        selected_records = _select_idea_candidates(eligible, limit=None)
        horizon = HORIZON_SECONDS
        try:
            darkness_ephemeris = build_ephemeris(
                0, 0, anchor, request["latitude"], request["longitude"],
                horizon_seconds=horizon,
                knot_step_seconds=IDEA_PROBE_STEP_SECONDS,
                output_step_seconds=IDEA_PROBE_STEP_SECONDS,
            )
        except AstronomyDataError as exc:
            raise ApiError(str(exc), "calculation", 502) from exc
        astronomical = self._idea_darkness_summary(darkness_ephemeris, -18, horizon)
        nautical = self._idea_darkness_summary(darkness_ephemeris, -12, horizon)
        darkness = {
            "mode": "astronomical",
            "astronomical": astronomical,
            "nautical": nautical,
        }
        night = select_astronomical_night(astronomical["intervals"], horizon)
        common = {
            "start": anchor.isoformat(),
            "end": elapsed_end(anchor, horizon).isoformat(),
            "requested_start": requested_start.isoformat(),
            "timezone": request["timezone"],
            "duration_seconds": _tidy(request["duration_seconds"]),
            "darkness": darkness,
            "darkness_mode": "astronomical",
            "search_days": request["search_days"],
            "search_limit_days": MAX_FUTURE_SEARCH_DAYS,
            "candidate_count": len(eligible),
            "evaluated_candidate_count": 0,
        }
        if night is None:
            return {
                **common,
                "status": "none",
                "night_start": None,
                "night_end": None,
                "night_start_offset": None,
                "night_end_offset": None,
                "night_duration_seconds": 0,
                "covered_duration_seconds": 0,
                "coverage_percent": 0,
                "preferred_block_seconds": IDEA_MIN_BLOCK_SECONDS,
                "blocks": [],
                "gaps": [],
                "object_count": 0,
                "skipped": {
                    "catalog_excluded": max(0, len(records) - len(eligible)),
                    "not_evaluated": len(eligible),
                },
                "note": "There is no complete astronomical night for this date and site.",
                "notes": [
                    "The plan requires the Sun below -18 degrees from evening through morning astronomical twilight.",
                    "Nautical darkness is shown as context and does not replace the astronomical criterion.",
                ],
            }
        candidates = []
        evaluated_count = 0
        result = plan_night_sequence(
            [], night, slot_seconds=IDEA_PROBE_STEP_SECONDS,
            preferred_block_seconds=IDEA_MIN_BLOCK_SECONDS,
        )
        tier_start = 0
        while tier_start < len(selected_records):
            priority = int((selected_records[tier_start].get("profile") or {}).get("priority", 0))
            tier_end = tier_start + 1
            while tier_end < len(selected_records) and int(
                (selected_records[tier_end].get("profile") or {}).get("priority", 0)
            ) == priority:
                tier_end += 1
            tier = selected_records[tier_start:tier_end]
            try:
                ephemerides = build_catalog_ephemerides(
                    [(item["ra_deg"], item["dec_deg"]) for item in tier],
                    anchor, request["latitude"], request["longitude"],
                    horizon_seconds=horizon,
                    knot_step_seconds=IDEA_PROBE_STEP_SECONDS,
                    output_step_seconds=IDEA_PROBE_STEP_SECONDS,
                )
            except AstronomyDataError as exc:
                raise ApiError(str(exc), "calculation", 502) from exc
            for candidate, ephemeris in zip(tier, ephemerides):
                visibility = solve_visibility(
                    ephemeris.position_at,
                    duration_seconds=1,
                    horizon_seconds=horizon,
                    min_alt=request["min_alt"], max_alt=request["max_alt"],
                    az_start=request["az_start"], az_end=request["az_end"],
                    resolution_seconds=IDEA_PROBE_STEP_SECONDS,
                )
                candidates.append({**candidate, "intervals": visibility["intervals"]})
            evaluated_count += len(tier)
            result = plan_night_sequence(
                candidates,
                night,
                slot_seconds=IDEA_PROBE_STEP_SECONDS,
                preferred_block_seconds=IDEA_MIN_BLOCK_SECONDS,
            )
            if result["status"] == "full" and not any(block["short_fill"] for block in result["blocks"]):
                break
            tier_start = tier_end
        for block in result["blocks"]:
            block["offset_start"] = block["start"]
            block["offset_end"] = block["end"]
            block["start"] = elapsed_end(anchor, block["offset_start"]).isoformat()
            block["end"] = elapsed_end(anchor, block["offset_end"]).isoformat()
        for gap in result["gaps"]:
            gap["offset_start"] = gap["start"]
            gap["offset_end"] = gap["end"]
            gap["start"] = elapsed_end(anchor, gap["offset_start"]).isoformat()
            gap["end"] = elapsed_end(anchor, gap["offset_end"]).isoformat()
        night_start_offset = result["night_start"]
        night_end_offset = result["night_end"]
        result.update({
            **common,
            "evaluated_candidate_count": evaluated_count,
            "night_start": elapsed_end(anchor, night_start_offset).isoformat(),
            "night_end": elapsed_end(anchor, night_end_offset).isoformat(),
            "night_start_offset": night_start_offset,
            "night_end_offset": night_end_offset,
            "skipped": {
                "catalog_excluded": max(0, len(records) - len(eligible)),
                "not_evaluated": max(0, len(eligible) - evaluated_count),
            },
            "notes": [
                "Night plan calculated locally from the SQLite catalog and offline ephemerides.",
                "The period runs from evening through morning astronomical twilight (Sun <= -18 degrees).",
                "Two hours is the preferred block per target; shorter fills are marked.",
                "Weather, Moon, equipment, and NINA operating times are not evaluated.",
            ],
        })
        return result

    @staticmethod
    def _idea_darkness_summary(ephemeris, limit, horizon):
        summary = summarize_darkness(ephemeris.sun_alt, limit)
        offsets = getattr(ephemeris, "sample_offsets", None)
        if offsets is None:
            step = horizon / max(1, len(ephemeris.sun_alt) - 1)
            offsets = [index * step for index in range(len(ephemeris.sun_alt))]
        else:
            offsets = list(offsets)
        for interval in summary["intervals"]:
            interval["start"] = int(offsets[interval["start"]])
            interval["end"] = int(offsets[interval["end"]])
        for event in summary["events"]:
            event["offset"] = int(offsets[event["offset"]])
        return summary

    def get_site(self):
        with self._site_lock:
            if not self.site_path.exists():
                return {"site": None}
            try:
                raw = self.site_path.read_text(encoding="utf-8")
                payload = json.loads(raw)
                site = validate_site_request(payload)
            except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
                raise ApiError(
                    "Saved site cannot be read or is invalid",
                    "site",
                    500,
                ) from exc
        return {"site": site}

    def save_site(self, payload):
        site = validate_site_request(payload)
        temporary_path = None
        with self._site_lock:
            try:
                self.site_path.parent.mkdir(parents=True, exist_ok=True)
                with tempfile.NamedTemporaryFile(
                    mode="w",
                    encoding="utf-8",
                    dir=self.site_path.parent,
                    prefix=".site-",
                    suffix=".tmp",
                    delete=False,
                ) as temporary:
                    temporary_path = Path(temporary.name)
                    json.dump(site, temporary, ensure_ascii=False, indent=2)
                    temporary.write("\n")
                    temporary.flush()
                    os.fsync(temporary.fileno())
                os.replace(temporary_path, self.site_path)
                temporary_path = None
            except OSError as exc:
                raise ApiError(
                    "Could not save the local site",
                    "site",
                    500,
                ) from exc
            finally:
                if temporary_path is not None:
                    try:
                        temporary_path.unlink(missing_ok=True)
                    except OSError:
                        pass
        return {"site": site}
