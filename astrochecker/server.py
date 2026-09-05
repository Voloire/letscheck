"""Local-only HTTP server and request validation."""

from __future__ import annotations

from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
import math
from numbers import Real
from pathlib import Path
from urllib.parse import urlparse

from .planner import parse_start, validate_limits


STATIC_DIRECTORY = Path(__file__).with_name("static")
MAX_REQUEST_BYTES = 64 * 1024


class ApiError(Exception):
    def __init__(self, message, code="calculation", status=500):
        super().__init__(message)
        self.message = message
        self.code = code
        self.status = status


def _number(payload, name, label):
    value = payload.get(name)
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError(f"La {label} deve essere un numero")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"La {label} deve essere finita")
    return result


def validate_check_request(payload):
    if not isinstance(payload, dict):
        raise ValueError("Il corpo JSON deve essere un oggetto")
    object_name = payload.get("object")
    if not isinstance(object_name, str) or not object_name.strip():
        raise ValueError("Il nome dell'oggetto e obbligatorio")
    object_name = object_name.strip()
    if len(object_name) > 200 or any(c in object_name for c in ('"', "\r", "\n", "\x00")):
        raise ValueError("Il nome dell'oggetto contiene caratteri non ammessi")

    latitude = _number(payload, "latitude", "latitudine")
    longitude = _number(payload, "longitude", "longitudine")
    duration_minutes = _number(payload, "duration_minutes", "durata")
    if not -90 <= latitude <= 90:
        raise ValueError("La latitudine deve essere compresa tra -90 e 90 gradi")
    if not -180 <= longitude <= 180:
        raise ValueError("La longitudine deve essere compresa tra -180 e 180 gradi")

    values = validate_limits(
        duration_seconds=duration_minutes * 60,
        horizon_seconds=86400,
        min_alt=payload.get("min_alt"),
        max_alt=payload.get("max_alt"),
        az_start=payload.get("az_start"),
        az_end=payload.get("az_end"),
    )
    try:
        start = parse_start(payload.get("start"), "Europe/Rome")
    except ValueError as exc:
        raise ValueError(str(exc)) from exc
    return {
        "object": object_name,
        "latitude": latitude,
        "longitude": longitude,
        "start": start,
        **values,
    }


class AstroCheckerHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def make_handler(service):
    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(STATIC_DIRECTORY), **kwargs)

        def log_message(self, _format, *_args):
            pass

        def _json(self, status, payload):
            body = json.dumps(payload, ensure_ascii=False, allow_nan=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _local_request(self):
            if self.client_address[0] not in ("127.0.0.1", "::1"):
                return False
            origin = self.headers.get("Origin")
            if not origin:
                return True
            parsed = urlparse(origin)
            host = urlparse("//" + self.headers.get("Host", ""))
            try:
                origin_port = parsed.port or 80
                host_port = host.port or 80
            except ValueError:
                return False
            return (
                parsed.scheme == "http"
                and parsed.username is None
                and parsed.password is None
                and parsed.hostname is not None
                and host.hostname is not None
                and parsed.hostname.casefold() == host.hostname.casefold()
                and parsed.hostname in ("127.0.0.1", "localhost")
                and origin_port == host_port
            )

        def _reject_nonlocal(self):
            if self._local_request():
                return False
            self._json(403, {"error": "Richiesta non locale rifiutata", "code": "validation"})
            return True

        def do_GET(self):
            if self._reject_nonlocal():
                return
            if self.path == "/api/status":
                try:
                    self._json(200, service.status())
                except ApiError as exc:
                    self._json(exc.status, {"error": exc.message, "code": exc.code})
                except Exception:
                    self._json(500, {"error": "Errore interno durante la verifica di SkyChart", "code": "calculation"})
                return
            super().do_GET()

        def do_POST(self):
            if self._reject_nonlocal():
                return
            if self.path != "/api/check":
                self._json(404, {"error": "Risorsa non trovata", "code": "validation"})
                return
            content_type = self.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
            if content_type != "application/json":
                self._json(415, {"error": "E richiesto un corpo JSON", "code": "validation"})
                return
            try:
                length = int(self.headers.get("Content-Length", ""))
                if length < 0 or length > MAX_REQUEST_BYTES:
                    raise ValueError
                raw = self.rfile.read(length)
                payload = json.loads(raw.decode("utf-8"))
            except (ValueError, UnicodeDecodeError, json.JSONDecodeError):
                self._json(400, {"error": "Corpo JSON non valido", "code": "validation"})
                return
            try:
                self._json(200, service.check(payload))
            except ValueError as exc:
                self._json(400, {"error": str(exc), "code": "validation"})
            except ApiError as exc:
                self._json(exc.status, {"error": exc.message, "code": exc.code})
            except Exception:
                self._json(500, {"error": "Calcolo non riuscito", "code": "calculation"})

    return Handler


def create_server(*, port=0, service=None):
    if service is None:
        from .service import AstroCheckerService
        service = AstroCheckerService()
    return AstroCheckerHTTPServer(("127.0.0.1", port), make_handler(service))
