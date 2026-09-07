"""Cloud mode: public host binding, stateless service, NINA download.

The desktop program keeps today's loopback behavior. These tests cover the
opt-in mode used inside a container behind an HTTPS proxy such as Cloud Run.
"""

import json
import threading
from http.client import HTTPConnection

import pytest
from playwright.sync_api import expect

from astrochecker.server import create_server
from astrochecker.service import AstroCheckerService
from test_local_backend import SITE
from test_local_ui import UiService, open_page, serve_ui, ui_browser, wait_until_ready  # noqa: F401

PUBLIC_HOST = "astrochecker-262633132420.europe-west1.run.app"
TARGET = {"name": "M 42", "ra": 83.82208, "dec": -5.39111}


class FakeService:
    def status(self):
        return {"ready": True}

    def get_site(self):
        return {"site": None}

    def save_site(self, payload):
        return {"site": payload}

    def export_nina_sequence(self, payload):
        return {
            "xml": '<?xml version="1.0" encoding="utf-8"?>\n<CaptureSequenceList />\n',
            "filename": "AstroChecker_M-42_20260907-210000.xml",
            "exposure_seconds": 300,
            "exposure_count": 3,
        }


def serve(**kwargs):
    server = create_server(port=0, **kwargs)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread


def stop(server, thread):
    server.shutdown()
    server.server_close()
    thread.join(timeout=5)


def request(server, method, path, *, headers, body=None):
    connection = HTTPConnection("127.0.0.1", server.server_port, timeout=3)
    connection.putrequest(method, path, skip_host=True, skip_accept_encoding=True)
    for name, value in headers.items():
        connection.putheader(name, value)
    if body is not None:
        connection.putheader("Content-Length", str(len(body)))
    connection.endheaders(body)
    response = connection.getresponse()
    raw = response.read()
    connection.close()
    return response.status, dict(response.getheaders()), raw


def test_create_server_binds_the_requested_host():
    server = create_server(host="0.0.0.0", port=0, service=FakeService())
    try:
        assert server.server_address[0] == "0.0.0.0"
    finally:
        server.server_close()


def test_default_server_still_binds_loopback_only():
    server = create_server(port=0, service=FakeService())
    try:
        assert server.server_address[0] == "127.0.0.1"
    finally:
        server.server_close()


@pytest.mark.parametrize(
    ("host_header", "origin", "expected_status"),
    [
        (PUBLIC_HOST, None, 200),
        (PUBLIC_HOST, f"https://{PUBLIC_HOST}", 200),
        (PUBLIC_HOST.upper(), f"https://{PUBLIC_HOST}", 200),
        (PUBLIC_HOST, f"http://{PUBLIC_HOST}", 403),
        (PUBLIC_HOST, "https://evil.example", 403),
        (PUBLIC_HOST, f"https://user:pw@{PUBLIC_HOST}", 403),
        ("127.0.0.1", None, 403),
        ("other.example.run.app", None, 403),
    ],
)
def test_public_host_mode_checks_host_and_https_origin(host_header, origin, expected_status):
    server, thread = serve(service=FakeService(), public_host=PUBLIC_HOST)
    try:
        headers = {"Host": host_header, "Content-Type": "application/json"}
        if origin is not None:
            headers["Origin"] = origin
        status, _headers, raw = request(
            server, "POST", "/api/site", headers=headers, body=json.dumps(SITE).encode("utf-8")
        )
        assert status == expected_status
        payload = json.loads(raw)
        if expected_status == 403:
            assert payload == {"error": "Request rejected for this host", "code": "validation"}
        else:
            assert payload == {"site": SITE}
    finally:
        stop(server, thread)


def test_public_host_mode_defaults_to_a_stateless_service():
    server = create_server(port=0, public_host=PUBLIC_HOST)
    try:
        assert server.RequestHandlerClass.service.site_path is None
    finally:
        server.server_close()


def test_stateless_service_keeps_no_site_on_the_server(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("LOCALAPPDATA", raising=False)
    service = AstroCheckerService(stateless=True)
    assert service.get_site() == {"site": None}
    assert service.save_site(SITE) == {"site": SITE}
    assert service.get_site() == {"site": None}
    assert list(tmp_path.rglob("site.json")) == []


def test_stateless_service_renders_nina_xml_instead_of_writing_files(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    service = AstroCheckerService(stateless=True)

    single = service.export_nina_sequence(
        {"object": TARGET, "duration_seconds": 900, "sequence_name": "Orion"}
    )
    assert single["xml"].startswith("<?xml")
    assert "<CaptureSequenceList" in single["xml"]
    assert single["filename"].startswith("Orion_") and single["filename"].endswith(".xml")
    assert single["exposure_count"] == 3
    assert "path" not in single

    target_set = service.export_nina_sequence(
        {
            "targets": [{"target": TARGET, "duration_seconds": 900}],
            "sequence_name": "Night set",
        }
    )
    assert target_set["xml"].startswith("<?xml")
    assert target_set["filename"].startswith("Night-set_")
    assert target_set["target_count"] == 1
    assert "path" not in target_set
    assert list(tmp_path.rglob("*.xml")) == []


def test_nina_endpoint_sends_an_attachment_when_the_service_renders_xml():
    server, thread = serve(service=FakeService())
    try:
        status, headers, raw = request(
            server,
            "POST",
            "/api/nina/legacy-sequence",
            headers={"Host": f"127.0.0.1:{server.server_port}", "Content-Type": "application/json"},
            body=json.dumps({"object": TARGET, "duration_seconds": 900}).encode("utf-8"),
        )
        assert status == 200
        assert headers["Content-Type"] == "application/xml; charset=utf-8"
        assert headers["Content-Disposition"] == (
            'attachment; filename="AstroChecker_M-42_20260907-210000.xml"'
        )
        assert headers["Cache-Control"] == "no-store"
        assert raw.decode("utf-8").startswith("<?xml")
    finally:
        stop(server, thread)


def test_run_arguments_default_to_localhost_and_read_container_environment(monkeypatch):
    import run

    monkeypatch.delenv("PORT", raising=False)
    monkeypatch.delenv("ASTROCHECKER_PUBLIC_HOST", raising=False)
    args = run.parse_args([])
    assert (args.host, args.port, args.public_host) == ("127.0.0.1", 0, None)

    monkeypatch.setenv("PORT", "8080")
    monkeypatch.setenv("ASTROCHECKER_PUBLIC_HOST", PUBLIC_HOST)
    args = run.parse_args(["--host", "0.0.0.0", "--no-browser"])
    assert (args.host, args.port, args.public_host) == ("0.0.0.0", 8080, PUBLIC_HOST)
    assert run.display_url(args.host, 8080) == "http://127.0.0.1:8080/"


class CloudUiService(UiService):
    """UI test service with the real stateless behavior for site and NINA."""

    def __init__(self, tmp_path):
        super().__init__(tmp_path / "unused-site.json")
        self.site_path = None
        self.stateless = True

    export_nina_sequence = AstroCheckerService.export_nina_sequence


SITE_LABELS = {
    "Site name": "Terrazzo",
    "Latitude": "45.1234",
    "Longitude": "9.5678",
    "Site time zone (IANA)": "Europe/Paris",
    "Minimum altitude": "12",
    "Maximum altitude": "70",
    "Starting azimuth": "330",
    "Ending azimuth": "25",
}


def test_site_is_restored_from_browser_storage_when_the_server_keeps_none(tmp_path, ui_browser):
    service = CloudUiService(tmp_path)
    with serve_ui(service) as url:
        page, errors = open_page(ui_browser, url)
        wait_until_ready(page)
        expect(page.locator("#site-status")).to_contain_text("No saved site yet")
        for label, value in SITE_LABELS.items():
            page.get_by_label(label, exact=True).fill(value)
        page.get_by_role("button", name="Save site", exact=True).click()
        expect(page.locator("#site-status")).to_contain_text("saved")

        page.reload()
        wait_until_ready(page)
        expect(page.locator("#site-status")).to_contain_text("restored")
        for label, value in SITE_LABELS.items():
            expect(page.get_by_label(label, exact=True)).to_have_value(value)
        assert not errors
        page.close()


def test_nina_xml_response_is_downloaded_by_the_browser(tmp_path, ui_browser):
    service = CloudUiService(tmp_path)
    with serve_ui(service) as url:
        page, errors = open_page(ui_browser, url)
        wait_until_ready(page)
        with page.expect_download() as download_info:
            outcome = page.evaluate(
                """async () => {
                    const response = await fetch("/api/nina/legacy-sequence", {
                        method: "POST",
                        headers: {"Content-Type": "application/json", Accept: "application/json"},
                        body: JSON.stringify({
                            object: {name: "M 42", ra: 83.82208, dec: -5.39111},
                            duration_seconds: 900,
                            sequence_name: "Orion",
                        }),
                    });
                    return await deliverNinaResponse(response);
                }"""
            )
        download = download_info.value
        assert outcome["downloaded"] is True
        assert outcome["filename"].startswith("Orion_")
        assert download.suggested_filename == outcome["filename"]
        saved = tmp_path / download.suggested_filename
        download.save_as(saved)
        assert saved.read_text(encoding="utf-8").startswith("<?xml")
        assert not errors
        page.close()
