"""Local-only HTTP server and request validation."""

from __future__ import annotations

from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
import math
from numbers import Real
from pathlib import Path
import time
from urllib.parse import parse_qs, urlparse
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .planner import parse_start, validate_limits


STATIC_DIRECTORY = Path(__file__).with_name("static")
MAX_REQUEST_BYTES = 64 * 1024
MAX_TIMEZONE_LENGTH = 200
EARLY_BODY_DRAIN_SECONDS = 0.5
INVALID_JSON = object()


class ApiError(Exception):
    def __init__(self, message, code="calculation", status=500):
        super().__init__(message)
        self.message = message
        self.code = code
        self.status = status


def _number(payload, name, label):
    value = payload.get(name)
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError(f"{label} must be a number")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{label} must be finite")
    return result


def _timezone(payload, *, default=None):
    value = payload.get("timezone", default)
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Time zone is required")
    value = value.strip()
    if len(value) > MAX_TIMEZONE_LENGTH:
        raise ValueError("Time zone is too long")
    try:
        ZoneInfo(value)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise ValueError("Time zone is unavailable") from exc
    return value


def validate_check_request(payload):
    if not isinstance(payload, dict):
        raise ValueError("JSON body must be an object")
    object_name = payload.get("object")
    if not isinstance(object_name, str) or not object_name.strip():
        raise ValueError("Object name is required")
    object_name = object_name.strip()
    if len(object_name) > 200 or any(c in object_name for c in ('"', "\r", "\n", "\x00")):
        raise ValueError("Object name contains unsupported characters")

    latitude = _number(payload, "latitude", "latitude")
    longitude = _number(payload, "longitude", "longitude")
    duration_minutes = _number(payload, "duration_minutes", "duration")
    if not -90 <= latitude <= 90:
        raise ValueError("Latitude must be between -90 and 90 degrees")
    if not -180 <= longitude <= 180:
        raise ValueError("Longitude must be between -180 and 180 degrees")

    values = validate_limits(
        duration_seconds=duration_minutes * 60,
        horizon_seconds=86400,
        min_alt=payload.get("min_alt"),
        max_alt=payload.get("max_alt"),
        az_start=payload.get("az_start"),
        az_end=payload.get("az_end"),
    )
    timezone_name = _timezone(payload, default="Europe/Rome")
    try:
        start = parse_start(payload.get("start"), timezone_name)
    except ValueError as exc:
        raise ValueError(str(exc)) from exc
    return {
        "object": object_name,
        "latitude": latitude,
        "longitude": longitude,
        "start": start,
        "timezone": timezone_name,
        **values,
    }


def validate_site_request(payload):
    if not isinstance(payload, dict):
        raise ValueError("Site JSON body must be an object")
    name = payload.get("name")
    if not isinstance(name, str) or not name.strip():
        raise ValueError("Site name is required")
    name = name.strip()
    if len(name) > 80:
        raise ValueError("Site name cannot exceed 80 characters")

    latitude = _number(payload, "latitude", "latitude")
    longitude = _number(payload, "longitude", "longitude")
    if not -90 <= latitude <= 90:
        raise ValueError("Latitude must be between -90 and 90 degrees")
    if not -180 <= longitude <= 180:
        raise ValueError("Longitude must be between -180 and 180 degrees")
    timezone_name = _timezone(payload)
    limits = validate_limits(
        duration_seconds=1,
        horizon_seconds=1,
        min_alt=payload.get("min_alt"),
        max_alt=payload.get("max_alt"),
        az_start=payload.get("az_start"),
        az_end=payload.get("az_end"),
    )
    return {
        "name": name,
        "latitude": latitude,
        "longitude": longitude,
        "timezone": timezone_name,
        "min_alt": limits["min_alt"],
        "max_alt": limits["max_alt"],
        "az_start": limits["az_start"],
        "az_end": limits["az_end"],
    }


def validate_ideas_request(payload):
    """Validate a multi-object ideas request without resolving an object."""
    if not isinstance(payload, dict):
        raise ValueError("JSON body must be an object")
    latitude = _number(payload, "latitude", "latitude")
    longitude = _number(payload, "longitude", "longitude")
    if not -90 <= latitude <= 90:
        raise ValueError("Latitude must be between -90 and 90 degrees")
    if not -180 <= longitude <= 180:
        raise ValueError("Longitude must be between -180 and 180 degrees")
    timezone_name = _timezone(payload, default="Europe/Rome")
    start = parse_start(payload.get("start"), timezone_name)
    values = validate_limits(
        duration_seconds=_number(payload, "duration_minutes", "duration") * 60,
        horizon_seconds=86400,
        min_alt=payload.get("min_alt"),
        max_alt=payload.get("max_alt"),
        az_start=payload.get("az_start"),
        az_end=payload.get("az_end"),
    )
    mode = payload.get("darkness_mode", "astronomical")
    if mode not in ("astronomical", "nautical"):
        raise ValueError("Darkness mode must be astronomical or nautical")
    search_days = payload.get("search_days", 1)
    if isinstance(search_days, bool) or not isinstance(search_days, Real) or not float(search_days).is_integer():
        raise ValueError("Search period must be an integer number of days")
    search_days = int(search_days)
    if not 1 <= search_days <= 90:
        raise ValueError("Search period must be between 1 and 90 days")
    return {
        "latitude": latitude, "longitude": longitude, "start": start,
        "timezone": timezone_name, "darkness_mode": mode,
        "search_days": search_days, **values,
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
            self._early_json(
                403,
                {"error": "Non-local request rejected", "code": "validation"},
            )
            return True

        def _declared_body_length(self):
            try:
                length = int(self.headers.get("Content-Length", ""))
            except ValueError:
                return None
            return length if length >= 0 else None

        def _drain_bounded_body(self):
            if self.command != "POST":
                return
            declared = self._declared_body_length()
            if not declared:
                return
            remaining = min(declared, MAX_REQUEST_BYTES)
            previous_timeout = self.connection.gettimeout()
            deadline = time.monotonic() + EARLY_BODY_DRAIN_SECONDS
            try:
                while remaining:
                    available_time = deadline - time.monotonic()
                    if available_time <= 0:
                        break
                    self.connection.settimeout(available_time)
                    chunk = self.rfile.read1(min(8192, remaining))
                    if not chunk:
                        break
                    remaining -= len(chunk)
            except (OSError, TimeoutError):
                pass
            finally:
                try:
                    self.connection.settimeout(previous_timeout)
                except OSError:
                    self.close_connection = True
            if remaining or declared > MAX_REQUEST_BYTES:
                self.close_connection = True

        def _early_json(self, status, payload):
            self._drain_bounded_body()
            self._json(status, payload)

        def _service_json(self, action, *, generic_message, generic_code="calculation"):
            try:
                self._json(200, action())
            except ValueError as exc:
                self._json(400, {"error": str(exc), "code": "validation"})
            except ApiError as exc:
                self._json(exc.status, {"error": exc.message, "code": exc.code})
            except Exception:
                self._json(500, {"error": generic_message, "code": generic_code})

        def _read_json(self):
            content_type = self.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
            if content_type != "application/json":
                self._early_json(
                    415,
                    {"error": "A JSON body is required", "code": "validation"},
                )
                return INVALID_JSON
            try:
                length = int(self.headers.get("Content-Length", ""))
            except ValueError:
                self._early_json(
                    400,
                    {"error": "Invalid JSON body", "code": "validation"},
                )
                return INVALID_JSON
            if length < 0 or length > MAX_REQUEST_BYTES:
                self._early_json(
                    400,
                    {"error": "Invalid JSON body", "code": "validation"},
                )
                return INVALID_JSON
            try:
                raw = self.rfile.read(length)
                return json.loads(raw.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                self._json(400, {"error": "Invalid JSON body", "code": "validation"})
                return INVALID_JSON

        def do_GET(self):
            if self._reject_nonlocal():
                return
            parsed = urlparse(self.path)
            if parsed.path == "/api/status":
                self._service_json(
                    service.status,
                    generic_message="Internal error while checking the local catalog",
                    generic_code="catalog",
                )
                return
            if parsed.path == "/api/objects":
                parameters = parse_qs(parsed.query, keep_blank_values=True)
                queries = parameters.get("q", [""])
                if len(queries) != 1:
                    self._json(
                        400,
                        {"error": "Specificare una sola ricerca oggetti", "code": "validation"},
                    )
                    return
                self._service_json(
                    lambda: service.objects(queries[0]),
                    generic_message="Local catalog search failed",
                    generic_code="catalog",
                )
                return
            if parsed.path == "/api/site":
                self._service_json(
                    service.get_site,
                    generic_message="Loading the local site failed",
                    generic_code="site",
                )
                return
            if parsed.path.startswith("/api/"):
                self._json(404, {"error": "Resource not found", "code": "validation"})
                return
            super().do_GET()

        def do_POST(self):
            if self._reject_nonlocal():
                return
            parsed = urlparse(self.path)
            if parsed.path not in ("/api/check", "/api/ideas", "/api/site", "/api/nina/legacy-sequence"):
                self._early_json(
                    404,
                    {"error": "Resource not found", "code": "validation"},
                )
                return
            payload = self._read_json()
            if payload is INVALID_JSON:
                return
            if parsed.path == "/api/check":
                self._service_json(
                    lambda: service.check(payload),
                    generic_message="Calculation failed",
                )
            elif parsed.path == "/api/ideas":
                self._service_json(
                    lambda: service.ideas(payload),
                    generic_message="Idea planning failed",
                )
            elif parsed.path == "/api/nina/legacy-sequence":
                self._service_json(
                    lambda: service.export_nina_sequence(payload),
                    generic_message="NINA sequence export failed",
                )
            else:
                self._service_json(
                    lambda: service.save_site(payload),
                    generic_message="Saving the local site failed",
                    generic_code="site",
                )

    return Handler


def create_server(*, port=0, service=None):
    if service is None:
        from .service import AstroCheckerService
        service = AstroCheckerService()
    return AstroCheckerHTTPServer(("127.0.0.1", port), make_handler(service))
