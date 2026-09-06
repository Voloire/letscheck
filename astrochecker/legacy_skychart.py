"""Historical SkyChart-backed service retained for regression checks."""

from __future__ import annotations

import threading

from .astronomy import equatorial_to_horizontal, interpolate_equatorial
from .planner import elapsed_end, position_is_visible, solve_visibility
from .server import ApiError, validate_check_request
from .skychart import (
    SkyChartClient,
    SkyChartConnectionError,
    SkyChartObjectError,
    SkyChartProtocolError,
)


HORIZON_SECONDS = 86400
EPHEMERIS_STEP_SECONDS = 3600
CHART_STEP_SECONDS = 300
STATIC_TARGET_KINDS = frozenset({
    "-", "?", "Gx", "OC", "Gb", "Pl", "Nb", "C+N", "*", "V*", "D*",
    "***", "Ast", "Kt", "Gcl", "Drk", "Cat", "Dup", "DSV*", "DS*",
})


def target_is_static(kind):
    return isinstance(kind, str) and kind.strip() in STATIC_TARGET_KINDS


class EquatorialTrack:
    def __init__(self, knots):
        self.knots = knots

    def at(self, offset):
        bounded = max(0.0, min(float(offset), self.knots[-1][0]))
        index = min(int(bounded // EPHEMERIS_STEP_SECONDS), len(self.knots) - 2)
        left_offset, left = self.knots[index]
        right_offset, right = self.knots[index + 1]
        fraction = (bounded - left_offset) / (right_offset - left_offset)
        return interpolate_equatorial(left, right, fraction)


def _tidy(number):
    return int(number) if float(number).is_integer() else number


class AstroCheckerService:
    def __init__(self, client_factory=SkyChartClient):
        self.client_factory = client_factory or SkyChartClient
        self._skychart_lock = threading.Lock()

    def status(self):
        try:
            with self._skychart_lock, self.client_factory() as client:
                connected = bool(client.status())
        except (SkyChartConnectionError, SkyChartProtocolError):
            connected = False
        message = (
            "SkyChart collegato e pronto"
            if connected
            else "SkyChart non raggiungibile. Avviarlo e abilitare il server su 127.0.0.1:3292, poi riprovare."
        )
        return {"connected": connected, "message": message, "port": 3292}

    def _collect_tracks(self, client, request):
        target_knots = []
        sun_knots = []
        selected = None
        for offset in range(0, HORIZON_SECONDS + 1, EPHEMERIS_STEP_SECONDS):
            client.set_date(elapsed_end(request["start"], offset))
            target = client.lookup(request["object"])
            if not target_is_static(target.get("kind")):
                raise SkyChartObjectError(
                    "Questa alfa supporta solo stelle e oggetti del cielo profondo; gli oggetti in movimento non sono ancora supportati"
                )
            sun = client.lookup("Sun", object_class=8)
            if selected is None:
                selected = target
            target_knots.append((offset, (target["ra"], target["dec"])))
            sun_knots.append((offset, (sun["ra"], sun["dec"])))
        return selected, EquatorialTrack(target_knots), EquatorialTrack(sun_knots)

    def check(self, payload):
        request = validate_check_request(payload)
        try:
            with self._skychart_lock, self.client_factory() as client:
                try:
                    client.start_temporary(request["latitude"], request["longitude"])
                    selected, target_track, sun_track = self._collect_tracks(client, request)
                finally:
                    client.finish_temporary()
        except SkyChartConnectionError as exc:
            raise ApiError(
                "Connessione a SkyChart non disponibile o interrotta. Verificare il server su 127.0.0.1:3292 e riprovare.",
                "connection",
                503,
            ) from exc
        except SkyChartObjectError as exc:
            raise ApiError(str(exc), "object", 404) from exc
        except SkyChartProtocolError as exc:
            raise ApiError(str(exc), "calculation", 502) from exc

        def position_at(offset):
            instant = elapsed_end(request["start"], offset)
            target_ra, target_dec = target_track.at(offset)
            sun_ra, sun_dec = sun_track.at(offset)
            altitude, azimuth = equatorial_to_horizontal(
                target_ra,
                target_dec,
                instant,
                request["latitude"],
                request["longitude"],
            )
            sun_altitude, _ = equatorial_to_horizontal(
                sun_ra,
                sun_dec,
                instant,
                request["latitude"],
                request["longitude"],
            )
            return {"alt": altitude, "az": azimuth, "sun_alt": sun_altitude}

        result = solve_visibility(
            position_at,
            duration_seconds=request["duration_seconds"],
            horizon_seconds=HORIZON_SECONDS,
            min_alt=request["min_alt"],
            max_alt=request["max_alt"],
            az_start=request["az_start"],
            az_end=request["az_end"],
        )
        samples = []
        for offset in range(0, HORIZON_SECONDS + 1, CHART_STEP_SECONDS):
            position = position_at(offset)
            samples.append({
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
            })
        return {
            **result,
            "object": {
                "name": selected["name"] or request["object"],
                "ra": round(selected["ra"], 6),
                "dec": round(selected["dec"], 6),
            },
            "start": request["start"].isoformat(),
            "end": elapsed_end(request["start"], request["duration_seconds"]).isoformat(),
            "search_end": elapsed_end(request["start"], HORIZON_SECONDS).isoformat(),
            "timezone": "Europe/Rome",
            "duration_seconds": _tidy(request["duration_seconds"]),
            "samples": samples,
            "resolution_seconds": 1,
            "notes": [
                "Altezza geometrica senza rifrazione atmosferica; azimut da nord verso est.",
                "Coordinate apparenti fornite da SkyChart e interpolate tra effemeridi orarie.",
                "Nel confronto dei 24 punti intermedi del 5 settembre 2026, l'errore osservato nell'interpolazione del Sole e stato inferiore a 0,00005 gradi; e una verifica locale, non un limite garantito per ogni data.",
                "Decisione su griglia conservativa di un secondo: tutti gli estremi campionati risultano validi, senza pretesa di esattezza astronomica al secondo.",
                "La visibilita considera geometria e Sole a -18 gradi; non include meteo o qualita fotografica.",
            ],
        }
