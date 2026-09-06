import json
import math
import socket
import threading
from datetime import timezone
from http.client import HTTPConnection

import pytest


CHECK_REQUEST = {
    "object": "M13",
    "latitude": 43.9729,
    "longitude": 7.9944,
    "start": "2026-09-05T23:00",
    "timezone": "Europe/Rome",
    "duration_minutes": 30,
    "min_alt": 0,
    "max_alt": 90,
    "az_start": 0,
    "az_end": 360,
}

SITE = {
    "name": "Balcone",
    "latitude": 43.9729,
    "longitude": 7.9944,
    "timezone": "Europe/Rome",
    "min_alt": 10,
    "max_alt": 75,
    "az_start": 350,
    "az_end": 20,
}


def astronomy_module():
    try:
        from astrochecker import local_astronomy
    except ImportError:
        pytest.fail("Il motore astronomico locale non esiste")
    return local_astronomy


def horizontal_vector(position):
    altitude = math.radians(position["alt"])
    azimuth = math.radians(position["az"])
    return (
        math.cos(altitude) * math.cos(azimuth),
        math.cos(altitude) * math.sin(azimuth),
        math.sin(altitude),
    )


def angular_separation_degrees(first, second):
    dot = sum(left * right for left, right in zip(first, second))
    return math.degrees(math.acos(max(-1.0, min(1.0, dot))))


@pytest.mark.parametrize(
    ("start_text", "ra", "dec", "latitude", "longitude", "horizon", "offsets"),
    [
        (
            "2026-09-05T21:00",
            250.423455,
            36.461301,
            43.9729,
            7.9944,
            120,
            (7, 17, 43, 77, 113),
        ),
        (
            "2026-09-06T00:29",
            0,
            43.9729,
            43.9729,
            7.9944,
            120,
            (13, 37, 61, 89, 107),
        ),
        (
            "2026-09-06T05:09",
            250.423455,
            36.461301,
            43.9729,
            7.9944,
            60,
            (7, 23, 25, 43, 59),
        ),
        (
            "2026-06-21T12:00",
            250.423455,
            36.461301,
            89,
            0,
            120,
            (7, 29, 47, 83, 113),
        ),
    ],
)
def test_cartesian_interpolation_stays_close_in_high_risk_geometry(
    start_text, ra, dec, latitude, longitude, horizon, offsets
):
    astronomy = astronomy_module()
    from astrochecker.planner import parse_start

    start = parse_start(start_text, "UTC")
    interpolated = astronomy.build_ephemeris(
        ra,
        dec,
        start,
        latitude,
        longitude,
        horizon_seconds=horizon,
        knot_step_seconds=30,
    )
    direct = astronomy.build_ephemeris(
        ra,
        dec,
        start,
        latitude,
        longitude,
        horizon_seconds=horizon,
        knot_step_seconds=1,
    )

    for offset in offsets:
        estimated = interpolated.position_at(offset)
        reference = direct.position_at(offset)
        assert angular_separation_degrees(
            horizontal_vector(estimated), horizontal_vector(reference)
        ) < 0.001
        assert estimated["sun_alt"] == pytest.approx(reference["sun_alt"], abs=0.001)


def test_solar_threshold_transition_matches_direct_astropy():
    astronomy = astronomy_module()
    from astrochecker.planner import parse_start

    arguments = (
        250.423455,
        36.461301,
        parse_start("2026-09-06T03:15", "UTC"),
        43.9729,
        7.9944,
    )
    interpolated = astronomy.build_ephemeris(
        *arguments, horizon_seconds=60, knot_step_seconds=30
    )
    direct = astronomy.build_ephemeris(
        *arguments, horizon_seconds=60, knot_step_seconds=1
    )

    expected = {
        "at_start": True,
        "intervals": [{"start": 0, "end": 24}],
        "events": [{"kind": "night_end", "offset": 25}],
    }
    assert astronomy.summarize_darkness(interpolated.sun_alt) == expected
    assert astronomy.summarize_darkness(direct.sun_alt) == expected


def test_coarse_ephemeris_exposes_only_requested_probe_grid():
    astronomy = astronomy_module()
    from astrochecker.planner import parse_start

    ephemeris = astronomy.build_ephemeris(
        250.423455,
        36.461301,
        parse_start("2026-09-06T03:15", "UTC"),
        43.9729,
        7.9944,
        horizon_seconds=60,
        knot_step_seconds=30,
        output_step_seconds=30,
    )

    assert len(ephemeris.target_alt) == 3
    assert ephemeris.position_at(30)["alt"] == pytest.approx(ephemeris.target_alt[1])
    with pytest.raises(ValueError, match="griglia"):
        ephemeris.position_at(15)


def test_catalog_ephemerides_transform_multiple_targets_in_one_grid():
    astronomy = astronomy_module()
    from astrochecker.planner import parse_start

    ephemerides = astronomy.build_catalog_ephemerides(
        [(250.423455, 36.461301), (10.0, 20.0)],
        parse_start("2026-09-06T03:15", "UTC"),
        43.9729,
        7.9944,
        horizon_seconds=60,
        knot_step_seconds=30,
        output_step_seconds=30,
    )

    assert len(ephemerides) == 2
    assert ephemerides[0].position_at(30)["alt"] != ephemerides[1].position_at(30)["alt"]


def test_iers_coverage_checks_the_search_end_as_well_as_the_start():
    astronomy = astronomy_module()
    from astropy.time import Time
    from astropy.utils import iers

    table = iers.IERS_A.open(iers.IERS_A_FILE)
    start = Time(float(table["MJD"][-1].value) - 0.5, format="mjd").to_datetime(
        timezone=timezone.utc
    )

    with pytest.raises(astronomy.AstronomyDataError, match="IERS"):
        astronomy.build_ephemeris(
            250.42183,
            36.45986,
            start,
            43.9729,
            7.9944,
            horizon_seconds=86400,
        )


@pytest.mark.parametrize(
    ("sun_altitudes", "expected"),
    [
        (
            [-20, -20, -20],
            {"at_start": True, "intervals": [{"start": 0, "end": 2}], "events": []},
        ),
        (
            [-10, -10, -10],
            {"at_start": False, "intervals": [], "events": []},
        ),
        (
            [-20, -20, -10, -10, -20, -20, -10],
            {
                "at_start": True,
                "intervals": [{"start": 0, "end": 1}, {"start": 4, "end": 5}],
                "events": [
                    {"kind": "night_end", "offset": 2},
                    {"kind": "night_start", "offset": 4},
                ],
            },
        ),
    ],
)
def test_darkness_summary_does_not_invent_events_at_horizon_edges(
    sun_altitudes, expected
):
    assert astronomy_module().summarize_darkness(sun_altitudes) == expected


def test_visibility_marks_horizon_edges_without_joining_separate_intervals():
    from astrochecker.planner import solve_visibility

    def position_at(offset):
        visible = offset <= 2 or offset >= 8
        return {"alt": 45 if visible else 5, "az": 180, "sun_alt": -20}

    result = solve_visibility(
        position_at,
        duration_seconds=3,
        horizon_seconds=10,
        min_alt=10,
        max_alt=90,
        az_start=0,
        az_end=360,
    )

    assert result["intervals"] == [{"start": 0, "end": 2}, {"start": 8, "end": 10}]
    assert result["horizon_edges"] == {"start": True, "end": True}


def test_check_validation_preserves_fractional_duration_and_requested_timezone():
    from astrochecker.server import validate_check_request

    result = validate_check_request(
        CHECK_REQUEST
        | {
            "duration_minutes": 1.251,
            "timezone": "America/New_York",
            "start": "2026-09-05T17:00",
        }
    )

    assert result["duration_seconds"] == pytest.approx(75.06)
    assert result["timezone"] == "America/New_York"
    assert result["start"].isoformat() == "2026-09-05T17:00:00-04:00"


def test_service_response_preserves_a_truly_fractional_duration():
    from astrochecker.service import AstroCheckerService

    result = AstroCheckerService().check(
        CHECK_REQUEST | {"duration_minutes": 1.251}
    )

    assert result["duration_seconds"] == pytest.approx(75.06)
    assert result["end"] == "2026-09-05T23:01:15.060000+02:00"
    assert result["first_window"] == {"start": 0, "end": pytest.approx(75.06)}


@pytest.mark.parametrize("timezone_name", [None, 4, "", "A" * 201, "Planet/Tatooine"])
def test_check_validation_rejects_invalid_timezone_values(timezone_name):
    from astrochecker.server import validate_check_request

    with pytest.raises(ValueError, match="Fuso"):
        validate_check_request(CHECK_REQUEST | {"timezone": timezone_name})


def test_polar_winter_is_a_clipped_all_dark_interval_without_events():
    astronomy = astronomy_module()
    from astrochecker.planner import parse_start

    ephemeris = astronomy.build_ephemeris(
        250.42183,
        36.45986,
        parse_start("2026-12-21T12:00", "UTC"),
        89,
        0,
    )

    assert astronomy.summarize_darkness(ephemeris.sun_alt) == {
        "at_start": True,
        "intervals": [{"start": 0, "end": 86400}],
        "events": [],
    }


def test_site_is_atomically_persisted_and_whitelists_fields(tmp_path):
    from astrochecker.service import AstroCheckerService

    path = tmp_path / "nested" / "site.json"
    saved = AstroCheckerService(site_path=path).save_site(
        SITE
        | {
            "object": "M13",
            "start": "2026-09-05T23:00",
            "duration_minutes": 30,
        }
    )

    assert saved == {"site": SITE}
    assert AstroCheckerService(site_path=path).get_site() == {"site": SITE}
    assert json.loads(path.read_text(encoding="utf-8")) == SITE
    assert list(path.parent.glob("*.tmp")) == []


@pytest.mark.parametrize(
    "change",
    [
        {"name": ""},
        {"name": "X" * 81},
        {"latitude": float("nan")},
        {"longitude": 181},
        {"timezone": "Planet/Tatooine"},
        {"min_alt": 80, "max_alt": 20},
        {"az_start": 0, "az_end": 0},
    ],
)
def test_site_validation_rejects_values_that_cannot_be_reused(change):
    from astrochecker.server import validate_site_request

    with pytest.raises(ValueError):
        validate_site_request(SITE | change)


def test_corrupt_site_file_does_not_block_catalog_status(tmp_path):
    from astrochecker.service import AstroCheckerService
    from astrochecker.server import ApiError

    path = tmp_path / "site.json"
    path.write_text("{broken", encoding="utf-8")
    service = AstroCheckerService(site_path=path)

    with pytest.raises(ApiError) as caught:
        service.get_site()
    assert caught.value.code == "site"
    assert service.status()["ready"] is True


def test_missing_catalog_maps_search_to_a_service_unavailable_error(tmp_path):
    from astrochecker.catalog import Catalog
    from astrochecker.service import AstroCheckerService
    from astrochecker.server import ApiError

    service = AstroCheckerService(catalog=Catalog(tmp_path / "missing.sqlite3"))

    assert service.status()["ready"] is False
    with pytest.raises(ApiError) as caught:
        service.objects("M13")
    assert caught.value.code == "catalog"
    assert caught.value.status == 503


class FakeLocalService:
    def status(self):
        return {
            "ready": True,
            "version": "test",
            "catalogs": [{"id": "messier", "count": 110}],
            "message": "Catalogo locale pronto",
        }

    def objects(self, query):
        if query == "broken":
            from astrochecker.server import ApiError

            raise ApiError("Catalogo guasto", "catalog", 503)
        return {
            "objects": [
                {
                    "name": "NGC 6205",
                    "ra_deg": 250.42183,
                    "dec_deg": 36.45986,
                    "frame": "icrs",
                    "type": "Gb",
                    "aliases": ["M 13", "NGC 6205"],
                    "source": "test",
                }
            ]
            if query
            else []
        }

    def get_site(self):
        return {"site": None}

    def save_site(self, payload):
        from astrochecker.server import validate_site_request

        return {"site": validate_site_request(payload)}

    def check(self, payload):
        return {"status": "full", "object": {"name": payload["object"]}}


@pytest.fixture
def local_api_server():
    from astrochecker.server import create_server

    server = create_server(port=0, service=FakeLocalService())
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def api_request(server, method, path, payload=None):
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    headers = {} if body is None else {"Content-Type": "application/json"}
    connection = HTTPConnection("127.0.0.1", server.server_port, timeout=3)
    connection.request(method, path, body=body, headers=headers)
    response = connection.getresponse()
    raw = response.read()
    connection.close()
    try:
        parsed = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError):
        parsed = None
    return response.status, parsed


def test_local_catalog_and_site_routes_return_json(local_api_server):
    status, objects = api_request(local_api_server, "GET", "/api/objects?q=M13")
    assert status == 200
    assert objects["objects"][0]["name"] == "NGC 6205"

    status, site = api_request(local_api_server, "GET", "/api/site")
    assert status == 200
    assert site == {"site": None}

    status, saved = api_request(local_api_server, "POST", "/api/site", SITE)
    assert status == 200
    assert saved == {"site": SITE}


def test_objects_route_maps_catalog_failure_to_503(local_api_server):
    status, payload = api_request(local_api_server, "GET", "/api/objects?q=broken")

    assert status == 503
    assert payload == {"error": "Catalogo guasto", "code": "catalog"}


def test_json_null_is_rejected_as_a_non_object_payload(local_api_server):
    connection = HTTPConnection("127.0.0.1", local_api_server.server_port, timeout=3)
    connection.request(
        "POST",
        "/api/site",
        body=b"null",
        headers={"Content-Type": "application/json"},
    )

    response = connection.getresponse()
    payload = json.loads(response.read())
    connection.close()
    assert response.status == 400
    assert payload["code"] == "validation"


@pytest.mark.parametrize(
    ("path", "content_type", "origin", "expected_status", "expected_payload"),
    [
        (
            "/api/check",
            "application/json",
            "https://example.com",
            403,
            {"error": "Richiesta non locale rifiutata", "code": "validation"},
        ),
        (
            "/api/missing",
            "application/json",
            None,
            404,
            {"error": "Risorsa non trovata", "code": "validation"},
        ),
        (
            "/api/check",
            "text/plain",
            None,
            415,
            {"error": "E richiesto un corpo JSON", "code": "validation"},
        ),
    ],
)
def test_early_post_rejections_drain_body_before_returning_json(
    local_api_server, path, content_type, origin, expected_status, expected_payload
):
    body = b'{"padding":"' + (b"x" * 4_000) + b'"}'
    header_lines = [
        f"POST {path} HTTP/1.0",
        f"Host: 127.0.0.1:{local_api_server.server_port}",
        f"Content-Type: {content_type}",
        f"Content-Length: {len(body)}",
    ]
    if origin is not None:
        header_lines.append(f"Origin: {origin}")
    headers = ("\r\n".join(header_lines) + "\r\n\r\n").encode("ascii")
    connection = socket.create_connection(
        ("127.0.0.1", local_api_server.server_port), timeout=3
    )
    connection.sendall(headers + body[:100])

    connection.settimeout(0.2)
    with pytest.raises(TimeoutError):
        connection.recv(1)
    connection.sendall(body[100:])
    connection.settimeout(3)
    response = b""
    while True:
        chunk = connection.recv(8192)
        if not chunk:
            break
        response += chunk
    connection.close()

    status_line, remainder = response.split(b"\r\n", 1)
    payload = json.loads(remainder.split(b"\r\n\r\n", 1)[1])
    assert f" {expected_status} ".encode("ascii") in status_line
    assert payload == expected_payload
