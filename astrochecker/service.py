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
from .local_astronomy import (
    AstronomyDataError,
    build_ephemeris,
    summarize_darkness,
)
from .planner import elapsed_end, position_is_visible, solve_visibility
from .server import ApiError, validate_check_request, validate_site_request


HORIZON_SECONDS = 86400
CHART_STEP_SECONDS = 300


def _tidy(number):
    return int(number) if float(number).is_integer() else number


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
            "samples": samples,
            "darkness": summarize_darkness(ephemeris.sun_alt),
            "notes": [
                "Altezza geometrica senza rifrazione atmosferica; azimut da nord verso est.",
                "Coordinate ICRS e Sole builtin trasformati localmente con Astropy, senza accesso alla rete.",
                "Astropy e campionato ogni 30 secondi; vettori orizzontali interpolati alimentano la griglia decisionale conservativa di un secondo. La precisione e verificata dai test, non e un limite universale.",
                f"Orientamento terrestre da tabella IERS-A locale ({iers_kind} per questo intervallo), copertura UTC da {ephemeris.iers_coverage_start} a prima di {ephemeris.iers_coverage_end_exclusive}.",
                "La visibilita considera geometria e Sole a -18 gradi; non include meteo, Luna o qualita fotografica.",
            ],
        }

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
