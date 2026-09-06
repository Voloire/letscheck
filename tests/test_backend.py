import io
import json
import socket
import threading
from datetime import datetime, timezone
from http.client import HTTPConnection

import pytest

from astrochecker.astronomy import equatorial_to_horizontal, interpolate_equatorial
from astrochecker.legacy_skychart import AstroCheckerService, target_is_static
from astrochecker.server import ApiError, create_server, validate_check_request
from astrochecker.skychart import (
    SkyChartClient,
    SkyChartObjectError,
    SkyChartProtocolError,
    parse_selected_object,
)


VALID_REQUEST = {
    "object": "Arcturus",
    "latitude": 43.9729,
    "longitude": 7.9944,
    "start": "2026-09-05T17:20",
    "duration_minutes": 30,
    "min_alt": 10,
    "max_alt": 80,
    "az_start": 0,
    "az_end": 360,
}


def test_request_validation_normalizes_before_skychart_access():
    result = validate_check_request(VALID_REQUEST)
    assert result["duration_seconds"] == 1800
    assert result["start"].isoformat() == "2026-09-05T17:20:00+02:00"
    assert result["latitude"] == pytest.approx(43.9729)


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"object": ""}, "[Oo]bject"),
        ({"object": 'M31"\nQUIT'}, "[Oo]bject"),
        ({"latitude": 91}, "[Ll]atitude"),
        ({"longitude": -181}, "[Ll]ongitude"),
        ({"duration_minutes": "molto"}, "duration"),
        ({"az_start": 0, "az_end": 0}, "sector"),
        ({"start": "2026-03-29T02:30"}, "does not exist"),
    ],
)
def test_request_validation_rejects_unsafe_or_invalid_values(change, message):
    with pytest.raises(ValueError, match=message):
        validate_check_request(VALID_REQUEST | change)


def test_geometric_conversion_matches_hand_checked_skychart_example():
    # Apparent coordinates reported by SkyChart for the acceptance timestamp.
    altitude, azimuth = equatorial_to_horizontal(
        214.2125,
        19.0739,
        datetime(2026, 9, 5, 15, 20, tzinfo=timezone.utc),
        43.9729,
        7.9944,
    )
    assert altitude == pytest.approx(64.08, abs=0.15)
    assert azimuth == pytest.approx(198.69, abs=0.15)


def test_unit_vector_interpolation_crosses_zero_ra_without_wrapping_backwards():
    ra, dec = interpolate_equatorial((359.0, 10.0), (1.0, 10.0), 0.5)
    assert min(abs(ra), abs(ra - 360)) < 0.01
    assert dec == pytest.approx(10.0015, abs=0.01)


class FakeSocket:
    def __init__(self, response):
        self.reader = io.BytesIO(response)
        self.sent = []
        self.closed = False

    def settimeout(self, _timeout):
        pass

    def makefile(self, *_args, **_kwargs):
        return self.reader

    def sendall(self, value):
        self.sent.append(value)

    def close(self):
        self.closed = True


def test_skychart_protocol_skips_events_and_reads_terminal_response(monkeypatch):
    fake = FakeSocket(
        b"OK! id=3 chart=Cartina_1\r\n"
        b">\tAstroChecker_x :\tselection\r\n.\r\nOK!\r\n"
        b"OK! 1.25\t-2.5\tStar\tTest\tEquinox:now\r\n"
    )
    monkeypatch.setattr(socket, "create_connection", lambda *_args, **_kwargs: fake)
    with SkyChartClient() as client:
        assert client.command('SEARCH "Test"') == "OK!"
        assert client.command("GETSELECTEDOBJECT").startswith("OK! 1.25\t-2.5")
    assert fake.sent[:2] == [b'SEARCH "Test"\r\n', b"GETSELECTEDOBJECT\r\n"]
    assert fake.closed


def test_skychart_protocol_reads_bare_chart_equinox(monkeypatch):
    fake = FakeSocket(b"OK! id=1 chart=Cartina_1\r\nDate\r\n")
    monkeypatch.setattr(socket, "create_connection", lambda *_args, **_kwargs: fake)
    with SkyChartClient() as client:
        assert client.chart_equinox() == "Date"


def test_skychart_rejects_newlines_and_quotes_in_user_object():
    with pytest.raises(SkyChartProtocolError):
        SkyChartClient.quote('bad"\r\nQUIT')


def test_selected_object_parser_converts_ra_hours_to_degrees():
    result = parse_selected_object(
        "OK! 14.261021\t19.182409\tStar\tArcturus\tEquinox:now"
    )
    assert result == {
        "ra": pytest.approx(213.915315),
        "dec": pytest.approx(19.182409),
        "kind": "Star",
        "name": "Arcturus",
    }


def test_selected_object_parser_accepts_installed_sexagesimal_format():
    result = parse_selected_object(
        "OK!  14h16m52.59s\t+19°02'44.9\"\t  *\t Alp Boo\tEquinox:now"
    )
    assert result["ra"] == pytest.approx(214.219125, abs=0.00001)
    assert result["dec"] == pytest.approx(19.0458056, abs=0.00001)
    assert result["name"] == "Alp Boo"


def test_selected_object_parser_rejects_non_date_frame():
    with pytest.raises(SkyChartProtocolError, match="equinox"):
        parse_selected_object(
            "OK! 14h16m52.59s\t+19°02'44.9\"\t*\tAlp Boo\tEquinox:J2000"
        )


def test_selected_object_parser_does_not_turn_failed_lookup_into_coordinates():
    with pytest.raises(SkyChartObjectError):
        parse_selected_object("Failed!")


class FakeService:
    def status(self):
        return {"connected": True, "message": "SkyChart collegato", "port": 3292}

    def check(self, payload):
        return {"status": "full", "object": {"name": payload["object"]}}


class FakeSkyChart:
    instances = []

    def __init__(self):
        self.finished = False
        self.instant = None
        self.instances.append(self)

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        pass

    def status(self):
        return True

    def start_temporary(self, latitude, longitude):
        assert latitude == pytest.approx(43.9729)
        assert longitude == pytest.approx(7.9944)

    def set_date(self, instant):
        self.instant = instant

    def lookup(self, name, object_class=None):
        if object_class == 8:
            assert name == "Sun"
            return {"name": "Sun", "ra": 180.0, "dec": 0.0, "kind": "Planet"}
        assert name == "Arcturus"
        return {"name": "Arcturus", "ra": 213.9, "dec": 19.18, "kind": "*"}

    def finish_temporary(self):
        self.finished = True


def test_service_builds_complete_api_result_and_always_cleans_temporary_chart():
    FakeSkyChart.instances.clear()
    service = AstroCheckerService(client_factory=FakeSkyChart)
    result = service.check(VALID_REQUEST | {"min_alt": 0, "max_alt": 90})
    assert result["object"] == {"name": "Arcturus", "ra": 213.9, "dec": 19.18}
    assert result["start"] == "2026-09-05T17:20:00+02:00"
    assert result["end"] == "2026-09-05T17:50:00+02:00"
    assert result["search_end"] == "2026-09-06T17:20:00+02:00"
    assert result["timezone"] == "Europe/Rome"
    assert result["duration_seconds"] == 1800
    assert result["resolution_seconds"] == 1
    assert len(result["samples"]) == 289
    assert result["samples"][0]["offset"] == 0
    assert result["samples"][-1]["offset"] == 86400
    assert any("geometrica" in note for note in result["notes"])
    assert FakeSkyChart.instances[0].finished


class PartialSetupSkyChart(FakeSkyChart):
    def start_temporary(self, latitude, longitude):
        self.temporary_chart = "AstroChecker_partial"
        raise SkyChartProtocolError("frame non supportato")


def test_service_cleans_chart_after_partial_setup_failure():
    PartialSetupSkyChart.instances.clear()
    service = AstroCheckerService(client_factory=PartialSetupSkyChart)
    with pytest.raises(ApiError) as caught:
        service.check(VALID_REQUEST)
    assert caught.value.code == "calculation"
    assert PartialSetupSkyChart.instances[0].finished


@pytest.mark.parametrize("kind", ["*", "V*", "D*", "Gx", "OC", "Nb", "Gcl", "DSV*", "DS*"])
def test_source_derived_catalog_kinds_are_static(kind):
    assert target_is_static(kind)


@pytest.mark.parametrize("kind", ["P", "S*", "Ps", "As", "Cm", "Sat", "DSP", "DSAs", "DSCm", "unexpected"])
def test_moving_or_unknown_skychart_kinds_are_not_supported_targets(kind):
    assert not target_is_static(kind)


class MovingTargetSkyChart(FakeSkyChart):
    def lookup(self, name, object_class=None):
        if object_class == 8:
            return super().lookup(name, object_class)
        return {"name": "Mars", "ra": 100.0, "dec": 10.0, "kind": "P"}


def test_service_rejects_moving_user_target_and_cleans_chart():
    MovingTargetSkyChart.instances.clear()
    service = AstroCheckerService(client_factory=MovingTargetSkyChart)
    with pytest.raises(ApiError) as caught:
        service.check(VALID_REQUEST | {"object": "Mars"})
    assert caught.value.code == "object"
    assert "stars" in caught.value.message
    assert MovingTargetSkyChart.instances[0].finished


@pytest.fixture
def running_server():
    server = create_server(port=0, service=FakeService())
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def request(server, method, path, body=None, headers=None):
    connection = HTTPConnection("127.0.0.1", server.server_port, timeout=3)
    connection.request(method, path, body=body, headers=headers or {})
    response = connection.getresponse()
    payload = json.loads(response.read())
    connection.close()
    return response.status, payload, response.getheader("Access-Control-Allow-Origin")


def test_status_endpoint_queries_service_without_cors_wildcard(running_server):
    status, payload, cors = request(running_server, "GET", "/api/status")
    assert status == 200
    assert payload == {"connected": True, "message": "SkyChart collegato", "port": 3292}
    assert cors is None


def test_check_endpoint_reports_malformed_json_readably(running_server):
    status, payload, _ = request(
        running_server,
        "POST",
        "/api/check",
        body=b"{broken",
        headers={"Content-Type": "application/json"},
    )
    assert status == 400
    assert payload["code"] == "validation"
    assert "JSON" in payload["error"]


def test_check_endpoint_rejects_non_local_origin(running_server):
    status, payload, _ = request(
        running_server,
        "POST",
        "/api/check",
        body=json.dumps(VALID_REQUEST),
        headers={"Content-Type": "application/json", "Origin": "https://example.com"},
    )
    assert status == 403
    assert payload["code"] == "validation"


def test_check_endpoint_rejects_different_local_origin_port(running_server):
    status, payload, _ = request(
        running_server,
        "POST",
        "/api/check",
        body=json.dumps(VALID_REQUEST),
        headers={"Content-Type": "application/json", "Origin": "http://127.0.0.1:65534"},
    )
    assert status == 403
    assert payload["code"] == "validation"


def test_trajectory_preserves_negative_altitudes_and_labels_dynamic_axis(running_server):
    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page()
        page.goto(f"http://127.0.0.1:{running_server.server_port}/")
        page.evaluate(
            """renderTrajectory(
                {horizon_seconds: 3600, samples: [{offset: 0, alt: -20}, {offset: 3600, alt: 0}]},
                {min_alt: 10, max_alt: 30}
            )"""
        )
        points = page.locator("#trajectory polyline").get_attribute("points").split()
        negative_y = float(points[0].split(",")[1])
        horizon_y = float(points[1].split(",")[1])
        assert negative_y > horizon_y
        assert "-30°" in page.locator("#trajectory").inner_text()
        browser.close()


def test_ui_defaults_to_supported_objects_and_full_azimuth(running_server):
    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page()
        page.goto(f"http://127.0.0.1:{running_server.server_port}/")
        assert page.locator("#az-start").input_value() == "0"
        assert page.locator("#az-end").input_value() == "360"
        assert "Local catalogs M, NGC, IC, Sh2, vdB and LDN" in page.locator("#object-help").inner_text()
        assert "estimated windows" in page.locator(".criteria-card details").text_content()
        browser.close()


def test_partial_reason_never_claims_all_criteria_passed_from_coarse_samples(running_server):
    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page()
        page.goto(f"http://127.0.0.1:{running_server.server_port}/")
        page.evaluate(
            """renderReasons(
                {status: 'partial', duration_seconds: 120, samples: [{offset: 0, alt: 20, az: 180, sun_alt: -25}]},
                {min_alt: 10, max_alt: 30, az_start: 90, az_end: 270}
            )"""
        )
        reasons = page.locator("#reason-list").inner_text()
        assert "All criteria met" not in reasons
        assert "only partly" in reasons
        browser.close()


def test_detailed_dst_instants_include_distinguishing_zone(running_server):
    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page()
        page.goto(f"http://127.0.0.1:{running_server.server_port}/")
        before, after = page.evaluate(
            """[
                formatInstant('2026-10-25T00:30:00+02:00', 5400),
                formatInstant('2026-10-25T00:30:00+02:00', 9000)
            ]"""
        )
        assert before != after
        assert any(zone in before for zone in ("CEST", "GMT+2"))
        assert any(zone in after for zone in ("CET", "GMT+1"))
        browser.close()
