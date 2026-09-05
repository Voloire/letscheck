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
    position_is_visible,
    solve_visibility,
    plan_ideas,
)
from .server import ApiError, validate_check_request, validate_ideas_request, validate_site_request


HORIZON_SECONDS = 86400
CHART_STEP_SECONDS = 300
FUTURE_PROBE_STEP_SECONDS = 300
IDEA_PROBE_STEP_SECONDS = 300


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
            raise ValueError("La ricerca oggetti deve essere testo")
        query = query.strip()
        if len(query) > 200:
            raise ValueError("La ricerca oggetti non puo superare 200 caratteri")
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
                "L'oggetto non e visibile in alcuna finestra continua nei 90 giorni analizzati."
                if not has_any_window
                else "Non esiste una proposta che rispetti i criteri indicati."
            )
        if suggestion["tier"] == "adjust":
            return "Sposta l'orario mantenendo la durata richiesta, nella prima finestra continua utile del periodo analizzato."
        if suggestion["tier"] == "future":
            return "Prima data futura entro 90 giorni con una finestra continua sufficiente per tutta la durata richiesta."
        return "La durata richiesta non e disponibile: questa e la finestra continua piu ampia trovata nei 90 giorni analizzati."

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
                "Astropy e campionato ogni 30 secondi; vettori orizzontali interpolati alimentano la griglia decisionale conservativa di un secondo. La precisione e verificata dai test, non e un limite universale.",
                f"Orientamento terrestre da tabella IERS-A locale ({iers_kind} per questo intervallo), copertura UTC da {ephemeris.iers_coverage_start} a prima di {ephemeris.iers_coverage_end_exclusive}.",
                "La visibilita considera geometria e Sole a -18 gradi; non include meteo, Luna o qualita fotografica.",
                "Se la richiesta non e completa, le alternative future vengono cercate localmente fino a 90 giorni; la prima finestra completa viene poi verificata con la griglia di un secondo.",
            ],
        }

    def ideas(self, payload):
        """Build one deterministic multi-object plan from local ephemerides."""
        request = validate_ideas_request(payload)
        try:
            records = self.catalog.idea_candidates(include_ineligible=True)
        except CatalogError as exc:
            raise ApiError(str(exc), "catalog", 503) from exc
        eligible = [item for item in records if (item.get("profile") or {}).get("eligible")]
        selected_records = _select_idea_candidates(eligible, limit=None)
        horizon = HORIZON_SECONDS
        try:
            darkness_ephemeris = build_ephemeris(
                0, 0, request["start"], request["latitude"], request["longitude"],
                horizon_seconds=horizon,
                knot_step_seconds=IDEA_PROBE_STEP_SECONDS,
                output_step_seconds=IDEA_PROBE_STEP_SECONDS,
            )
        except AstronomyDataError as exc:
            raise ApiError(str(exc), "calculation", 502) from exc
        astronomical = self._idea_darkness_summary(darkness_ephemeris, -18, horizon)
        nautical = self._idea_darkness_summary(darkness_ephemeris, -12, horizon)
        darkness = {
            "mode": request["darkness_mode"],
            "astronomical": astronomical,
            "nautical": nautical,
        }
        selected_darkness = darkness[request["darkness_mode"]]["intervals"]
        candidates = []
        try:
            ephemerides = build_catalog_ephemerides(
                [(item["ra_deg"], item["dec_deg"]) for item in selected_records],
                request["start"], request["latitude"], request["longitude"],
                horizon_seconds=horizon,
                knot_step_seconds=IDEA_PROBE_STEP_SECONDS,
                output_step_seconds=IDEA_PROBE_STEP_SECONDS,
            )
        except AstronomyDataError as exc:
            raise ApiError(str(exc), "calculation", 502) from exc
        for candidate, ephemeris in zip(selected_records, ephemerides):
            visibility = solve_visibility(
                ephemeris.position_at,
                duration_seconds=1,
                horizon_seconds=horizon,
                min_alt=request["min_alt"], max_alt=request["max_alt"],
                az_start=request["az_start"], az_end=request["az_end"],
                resolution_seconds=IDEA_PROBE_STEP_SECONDS,
            )
            candidates.append({**candidate, "intervals": visibility["intervals"]})
        result = plan_ideas(
            candidates, selected_darkness, request["duration_seconds"],
            minimum_block_seconds=IDEA_MIN_BLOCK_SECONDS,
        )
        for block in result["blocks"]:
            block["offset_start"] = block["start"]
            block["offset_end"] = block["end"]
            block["start"] = elapsed_end(request["start"], block["offset_start"]).isoformat()
            block["end"] = elapsed_end(request["start"], block["offset_end"]).isoformat()
        result.update({
            "start": request["start"].isoformat(),
            "end": elapsed_end(request["start"], request["duration_seconds"]).isoformat(),
            "timezone": request["timezone"],
            "duration_seconds": _tidy(request["duration_seconds"]),
            "darkness": darkness,
            "darkness_mode": request["darkness_mode"],
            "search_days": request["search_days"],
            "search_limit_days": MAX_FUTURE_SEARCH_DAYS,
            "candidate_count": len(eligible),
            "evaluated_candidate_count": len(selected_records),
            "skipped": {
                **result["skipped"],
                "catalog_excluded": max(0, len(records) - len(eligible)),
                "not_evaluated": max(0, len(eligible) - len(selected_records)),
            },
            "notes": [
                "Piano calcolato localmente dal catalogo SQLite e da effemeridi offline.",
                "Il buio astronomico (Sole <= -18 gradi) e il criterio predefinito; il buio nautico usa -12 gradi.",
                "Ogni oggetto richiede un blocco continuo di almeno due ore; meteo, Luna e attrezzatura non sono valutati.",
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
                    "La postazione salvata non e leggibile o non e valida",
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
                    "Non e stato possibile salvare la postazione locale",
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
