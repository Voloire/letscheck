import copy
import re
import threading
from contextlib import contextmanager
from urllib.parse import urlparse

import pytest
from playwright.sync_api import expect, sync_playwright

from astrochecker.server import ApiError, create_server
from astrochecker.service import AstroCheckerService


CATALOGS = [
    {"id": "messier", "count": 110},
    {"id": "ngc", "count": 8440},
    {"id": "ic", "count": 5594},
    {"id": "sh2", "count": 313},
    {"id": "vdb", "count": 158},
    {"id": "ldn", "count": 1787},
]

M13 = {
    "name": "NGC 6205",
    "ra_deg": 250.423455,
    "dec_deg": 36.461301,
    "frame": "icrs",
    "type": "GCl",
    "aliases": ["NGC 6205", "M 13"],
    "source": "OpenNGC",
}


def result_fixture(*, object_name="NGC 6205", timezone="Europe/Rome", darkness=None, boundary=False):
    if timezone == "America/New_York":
        start = "2026-11-01T00:30:00-04:00"
        first_window = {"start": 3600, "end": 7200}
    else:
        start = "2026-09-05T23:00:00+02:00"
        first_window = {"start": 0, "end": 1800}
    return {
        "status": "full",
        "requested_visible_seconds": 1800,
        "longest_visible_seconds": 7200,
        "first_window": None if boundary else first_window,
        "intervals": ([{"start": 0, "end": 7200}, {"start": 80000, "end": 86400}] if boundary
                      else [{"start": 0, "end": 7200}]),
        "horizon_edges": {"start": boundary, "end": boundary},
        "horizon_seconds": 86400,
        "resolution_seconds": 1,
        "object": {
            "name": object_name,
            "ra": 250.423455,
            "dec": 36.461301,
            "frame": "icrs",
            "type": "GCl",
            "aliases": [object_name, "M 13"],
            "source": "OpenNGC",
        },
        "start": start,
        "end": start,
        "search_end": start,
        "timezone": timezone,
        "duration_seconds": 1800,
        "samples": [
            {"offset": 0, "alt": 46.4, "az": 280.5, "sun_alt": -29.6, "visible": True},
            {"offset": 86400, "alt": 45.7, "az": 281.0, "sun_alt": -30.0, "visible": True},
        ],
        "darkness": darkness
        or {
            "at_start": True,
            "intervals": [{"start": 0, "end": 7200}, {"start": 80000, "end": 86400}],
            "events": [
                {"kind": "night_end", "offset": 7201},
                {"kind": "night_start", "offset": 80000},
            ],
        },
        "notes": ["Calcolo astronomico locale di prova."],
    }


class UiService(AstroCheckerService):
    def __init__(self, site_path, *, statuses=None):
        super().__init__(site_path=site_path)
        self.statuses = list(
            statuses
            or [
                {
                    "ready": True,
                    "version": "2026.09.06-1",
                    "catalogs": CATALOGS,
                    "message": "Catalogo locale pronto",
                }
            ]
        )
        self.status_calls = 0
        self.check_payloads = []
        self.object_gates = {}
        self.object_started = {}
        self.site_gate = None
        self.fail_site_load = False
        self.fail_site_save = False

    def status(self):
        index = min(self.status_calls, len(self.statuses) - 1)
        self.status_calls += 1
        return copy.deepcopy(self.statuses[index])

    def objects(self, query):
        normalized = "".join(query.upper().split())
        if normalized in self.object_started:
            self.object_started[normalized].set()
        if normalized in self.object_gates:
            self.object_gates[normalized].wait(timeout=5)
        if normalized in {"M", "M1", "M13", "NGC", "NGC6", "NGC62", "NGC6205"}:
            return {"objects": [copy.deepcopy(M13)]}
        if normalized == "M31":
            return {
                "objects": [
                    {
                        **copy.deepcopy(M13),
                        "name": "NGC 224",
                        "aliases": ["NGC 224", "M 31"],
                    }
                ]
            }
        if normalized == "M101":
            return {
                "objects": [
                    {
                        **copy.deepcopy(M13),
                        "name": "NGC 5457",
                        "aliases": ["NGC 5457", "M 101"],
                    },
                    {
                        **copy.deepcopy(M13),
                        "name": "NGC 5458",
                        "aliases": ["NGC 5458", "M 101"],
                    },
                ]
            }
        return {"objects": []}

    def get_site(self):
        if self.site_gate is not None:
            self.site_gate.wait(timeout=5)
        if self.fail_site_load:
            raise ApiError("Saved site could not be read", "site", 500)
        return super().get_site()

    def save_site(self, payload):
        if self.fail_site_save:
            raise ApiError("Saving site failed", "site", 500)
        return super().save_site(payload)

    def check(self, payload):
        self.check_payloads.append(copy.deepcopy(payload))
        normalized = "".join(str(payload.get("object", "")).upper().split())
        if normalized in {"INESISTENTE", "ZZZ"}:
            raise ApiError("Object not found in the local catalog", "object", 404)
        if normalized == "M101":
            raise ApiError("M 101 is ambiguous; choose a result", "object", 409)
        if normalized == "M31":
            result = result_fixture(object_name="NGC 224")
            result["object"]["aliases"] = ["NGC 224", "M 31"]
            return result
        if normalized == "POLARNIGHT":
            darkness = {"at_start": True, "intervals": [{"start": 0, "end": 86400}], "events": []}
            return result_fixture(object_name="Polar Night", darkness=darkness)
        if normalized == "POLARDAY":
            darkness = {"at_start": False, "intervals": [], "events": []}
            result = result_fixture(object_name="Polar Day", darkness=darkness)
            result["status"] = "none"
            result["first_window"] = None
            result["requested_visible_seconds"] = 0
            result["longest_visible_seconds"] = 0
            result["intervals"] = []
            return result
        if normalized == "ONEEVENT":
            darkness = {
                "at_start": True,
                "intervals": [{"start": 0, "end": 7200}],
                "events": [{"kind": "night_end", "offset": 7201}],
            }
            return result_fixture(object_name="One Event", darkness=darkness)
        if normalized == "MULTIEVENT":
            darkness = {
                "at_start": False,
                "intervals": [{"start": 1000, "end": 2000}, {"start": 3000, "end": 4000}],
                "events": [
                    {"kind": "night_start", "offset": 1000},
                    {"kind": "night_end", "offset": 2000},
                    {"kind": "night_start", "offset": 3000},
                    {"kind": "night_end", "offset": 4000},
                ],
            }
            return result_fixture(object_name="Multi Event", darkness=darkness)
        if normalized == "BOUNDARY":
            result = result_fixture(object_name="Boundary", boundary=True)
            result["status"] = "partial"
            result["requested_visible_seconds"] = 0
            result["longest_visible_seconds"] = 7200
            return result
        if normalized == "SUGGESTION":
            result = result_fixture(object_name="Suggestion")
            result["status"] = "partial"
            result["first_window"] = None
            result["suggestions"] = [{
                "tier": "future",
                "start": "2026-09-07T23:10:00+02:00",
                "end": "2026-09-08T00:10:00+02:00",
                "duration_seconds": 3600,
                "requested_duration_seconds": 3600,
            }]
            result["suggestion_note"] = "Prima future date entro 90 days."
            result["suggestion_search_days"] = 90
            return result
        timezone = str(payload.get("timezone", "Europe/Rome"))
        return result_fixture(timezone=timezone)


@contextmanager
def serve_ui(service):
    server = create_server(port=0, service=service)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/"
    finally:
        if service.site_gate is not None:
            service.site_gate.set()
        for gate in service.object_gates.values():
            gate.set()
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


@pytest.fixture(scope="module")
def ui_browser():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        yield browser
        browser.close()


def open_page(browser, url, *, init_script=None, viewport=None):
    page = browser.new_page(viewport=viewport or {"width": 1280, "height": 900})
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    if init_script:
        page.add_init_script(init_script)
    page.goto(url)
    return page, errors


def wait_until_ready(page):
    expect(page.get_by_label("Sky object", exact=True)).to_be_enabled()


def submit_object(page, name):
    field = page.get_by_label("Sky object", exact=True)
    field.fill(name)
    page.get_by_role("button", name="Check visibility", exact=True).click()


def test_catalog_boot_is_automatic_and_failed_status_retries_without_reload(tmp_path, ui_browser):
    delayed = UiService(tmp_path / "delayed-site.json")
    delayed.site_gate = threading.Event()
    with serve_ui(delayed) as url:
        page, errors = open_page(ui_browser, url)
        expect(page.get_by_label("Sky object", exact=True)).to_be_disabled()
        delayed.site_gate.set()
        wait_until_ready(page)
        expect(page.locator("#header-connection")).to_contain_text("Catalogs ready")
        expect(page.locator("#catalog-version")).to_contain_text("2026.09.06-1")
        catalog_text = page.locator("#catalog-summary").inner_text()
        for label in ("M", "NGC", "IC", "Sh2", "vdB", "LDN"):
            assert label in catalog_text
        body = page.locator("body").inner_text()
        assert "SkyChart" not in body
        assert "1–2 minuti" not in body
        assert not errors
        page.close()


def test_header_identifies_the_current_alpha_release(tmp_path, ui_browser):
    service = UiService(tmp_path / "version-site.json")
    with serve_ui(service) as url:
        page, errors = open_page(ui_browser, url)
        expect(page.locator(".eyebrow").first).to_contain_text("0.4.0-alpha.1")
        assert not errors
        page.close()

    unavailable = {
        "ready": False,
        "version": "",
        "catalogs": [],
        "message": "Catalogo locale unavailable",
    }
    ready = {
        "ready": True,
        "version": "2026.09.06-1",
        "catalogs": CATALOGS,
        "message": "Catalogo locale pronto",
    }
    retrying = UiService(tmp_path / "retry-site.json", statuses=[unavailable, ready])
    retrying.fail_site_load = True
    with serve_ui(retrying) as url:
        page, errors = open_page(ui_browser, url)
        expect(page.locator("#header-connection")).to_contain_text("Catalogs unavailable")
        expect(page.get_by_label("Sky object", exact=True)).to_be_disabled()
        expect(page.locator("#site-status")).to_contain_text("could not be read")
        navigation_count = page.evaluate("performance.getEntriesByType('navigation').length")
        page.get_by_role("button", name="Check again", exact=True).click()
        wait_until_ready(page)
        assert page.evaluate("performance.getEntriesByType('navigation').length") == navigation_count
        assert retrying.status_calls == 2
        assert not errors
        page.close()


def test_object_search_requires_selection_and_exact_submit_canonicalizes(tmp_path, ui_browser):
    service = UiService(tmp_path / "search-site.json")
    with serve_ui(service) as url:
        page, errors = open_page(ui_browser, url)
        wait_until_ready(page)
        field = page.get_by_label("Sky object", exact=True)

        field.fill("m 13")
        expect(page.get_by_role("option", name="NGC 6205 GCl M 13")).to_be_visible()
        expect(field).to_have_attribute("aria-expanded", "true")
        field.press("ArrowDown")
        assert field.get_attribute("aria-activedescendant")
        field.press("Enter")
        expect(field).to_have_value("NGC 6205")
        expect(field).to_have_attribute("aria-expanded", "false")

        page.get_by_role("button", name="Check visibility", exact=True).click()
        expect(page.locator("#result-object")).to_have_text("NGC 6205")
        field.fill("NGC 620")
        expect(page.locator("#stale-badge")).to_be_visible()

        field.fill("M 13")
        field.press("Escape")
        page.get_by_role("button", name="Check visibility", exact=True).click()
        expect(page.locator("#result-object")).to_have_text("NGC 6205")
        expect(field).to_have_value("NGC 6205")
        expect(page.locator("#object-search-status")).to_contain_text("M 13")
        assert service.check_payloads[-1]["object"] == "M 13"

        field.fill("inesistente")
        expect(page.locator("#object-search-status")).to_contain_text("No objects found")
        field.press("Escape")
        page.get_by_role("button", name="Check visibility", exact=True).click()
        expect(page.locator("#form-error")).to_contain_text("Object not found")
        assert page.get_by_text("Not visible for the requested period", exact=True).count() == 0

        field.fill("M 101")
        expect(page.get_by_role("option")).to_have_count(2)
        field.press("Escape")
        page.get_by_role("button", name="Check visibility", exact=True).click()
        expect(page.locator("#form-error")).to_contain_text("ambiguous")
        expect(field).to_have_value("M 101")

        field.fill("m 13")
        option = page.get_by_role("option", name="NGC 6205 GCl M 13")
        expect(option).to_be_visible()
        option.click()
        expect(field).to_have_value("NGC 6205")

        replacement_gate = threading.Event()
        replacement_started = threading.Event()
        service.object_gates["M31"] = replacement_gate
        service.object_started["M31"] = replacement_started
        field.fill("m 13")
        expect(page.get_by_role("option", name="NGC 6205 GCl M 13")).to_be_visible()
        field.press("ArrowDown")
        assert field.get_attribute("aria-activedescendant")
        field.fill("M 31")
        assert replacement_started.wait(timeout=2), "M31 search did not start"
        field.press("Enter")
        assert field.input_value() != "NGC 6205"
        expect(page.locator("#result-object")).to_have_text("NGC 224", timeout=3000)
        assert service.check_payloads[-1]["object"] == "M 31"
        replacement_gate.set()
        assert not errors
        page.close()


def test_site_save_reloads_from_real_temporary_backend_on_another_port(tmp_path, ui_browser):
    site_path = tmp_path / "profile" / "site.json"
    first_service = UiService(site_path)
    with serve_ui(first_service) as first_url:
        page, errors = open_page(ui_browser, first_url)
        wait_until_ready(page)
        values = {
            "Site name": "Terrazzo",
            "Latitude": "45.1234",
            "Longitude": "9.5678",
            "Site time zone (IANA)": "Europe/Paris",
            "Minimum altitude": "12",
            "Maximum altitude": "70",
            "Starting azimuth": "330",
            "Ending azimuth": "25",
        }
        for label, value in values.items():
            page.get_by_label(label, exact=True).fill(value)
        page.get_by_role("button", name="Save site", exact=True).click()
        expect(page.locator("#site-status")).to_contain_text("saved")

        second_service = UiService(site_path)
        with serve_ui(second_service) as second_url:
            assert urlparse(first_url).port != urlparse(second_url).port
            second_page, second_errors = open_page(ui_browser, second_url)
            wait_until_ready(second_page)
            for label, value in values.items():
                expect(second_page.get_by_label(label, exact=True)).to_have_value(value)

            second_service.fail_site_save = True
            second_page.get_by_role("button", name="Save site", exact=True).click()
            expect(second_page.locator("#site-status")).to_contain_text("failed")
            second_page.get_by_role("button", name="Check visibility", exact=True).click()
            expect(second_page.locator("#result-content")).to_be_visible()

            latitude = second_page.get_by_label("Latitude", exact=True)
            latitude.fill("91")
            second_page.get_by_role("button", name="Save site", exact=True).click()
            expect(latitude).to_have_attribute("aria-invalid", "true")
            assert second_page.evaluate("document.activeElement.id") == "latitude"

            latitude.fill("45.1234")
            timezone = second_page.get_by_label("Site time zone (IANA)", exact=True)
            timezone.fill("Invalid/Nowhere")
            calls_before = len(second_service.check_payloads)
            second_page.get_by_role("button", name="Check visibility", exact=True).click()
            expect(timezone).to_have_attribute("aria-invalid", "true")
            assert second_page.evaluate("document.activeElement.id") == "timezone"
            assert len(second_service.check_payloads) == calls_before
            assert not second_errors
            second_page.close()
        assert not errors
        page.close()


def test_prioritized_suggestion_is_visible_and_states_90_day_limit(tmp_path, ui_browser):
    service = UiService(tmp_path / "suggestion-site.json")
    with serve_ui(service) as url:
        page, errors = open_page(ui_browser, url)
        wait_until_ready(page)
        submit_object(page, "Suggestion")
        expect(page.locator("#suggestions-card")).to_be_visible()
        expect(page.locator("#suggestion-tier")).to_have_text("2")
        expect(page.locator("#suggestion-label")).to_contain_text("future date")
        expect(page.locator("#suggestion-time")).to_contain_text("Sep 07")
        expect(page.locator("#suggestions-card")).to_contain_text("90 days")
        assert not errors
        page.close()


def test_ideas_button_renders_a_dedicated_complete_night_chain(tmp_path, ui_browser):
    class IdeasUiService(UiService):
        def ideas(self, payload):
            return {
                "status": "full",
                "note": "Complete plan from evening astronomical twilight to morning twilight.",
                "darkness_mode": "astronomical",
                "timezone": "Europe/Rome",
                "night_start": "2026-09-05T21:00:00+02:00",
                "night_end": "2026-09-06T05:00:00+02:00",
                "night_duration_seconds": 28800,
                "covered_duration_seconds": 28800,
                "coverage_percent": 100,
                "preferred_block_seconds": 7200,
                "blocks": [
                    {
                        "target": {"name": "X", "type": "HII", "aliases": [], "ra_deg": 1, "dec_deg": 2},
                        "start": "2026-09-05T21:00:00+02:00", "end": "2026-09-05T23:30:00+02:00",
                        "offset_start": 32400, "offset_end": 41400, "duration_seconds": 9000,
                        "reason": "Nebulosa visibile dal balcone.", "short_fill": False,
                    },
                    {
                        "target": {"name": "Y", "type": "GCl", "aliases": [], "ra_deg": 3, "dec_deg": 4},
                        "start": "2026-09-05T23:30:00+02:00", "end": "2026-09-06T02:30:00+02:00",
                        "offset_start": 41400, "offset_end": 52200, "duration_seconds": 10800,
                        "reason": "Ammasso nella finestra utile.", "short_fill": False,
                    },
                    {
                        "target": {"name": "Z", "type": "OCl", "aliases": [], "ra_deg": 5, "dec_deg": 6},
                        "start": "2026-09-06T02:30:00+02:00", "end": "2026-09-06T05:00:00+02:00",
                        "offset_start": 52200, "offset_end": 61200, "duration_seconds": 9000,
                        "reason": "Complete the night.", "short_fill": False,
                    },
                ],
                "gaps": [],
            }

    service = IdeasUiService(tmp_path / "ideas-site.json")
    with serve_ui(service) as url:
        page, errors = open_page(ui_browser, url)
        wait_until_ready(page)
        page.locator("#object").fill("")
        page.get_by_role("button", name="Need ideas?", exact=True).click()
        expect(page.locator("#night-plan")).to_be_visible()
        assert page.locator("#night-plan").evaluate("element => element.parentElement.classList.contains('results-column')")
        expect(page.locator("#result-content")).to_be_hidden()
        expect(page.locator("#results-title")).to_have_text("Night plan")
        expect(page.get_by_role("heading", name="Complete sequence", exact=True)).to_be_visible()
        expect(page.locator("#night-period")).to_contain_text("21:00")
        expect(page.locator("#night-period")).to_contain_text("05:00")
        expect(page.locator("#night-coverage")).to_have_text("100%")
        expect(page.locator("#night-chain")).to_have_text("X → Y → Z")
        expect(page.locator("#night-blocks li")).to_have_count(3)
        expect(page.locator("#night-timeline .night-segment")).to_have_count(3)
        expect(page.get_by_role("button", name="Export to NINA", exact=True)).to_be_disabled()
        assert not errors
        page.close()


def test_ideas_button_explains_that_date_drives_the_complete_night(tmp_path, ui_browser):
    service = UiService(tmp_path / "ideas-explanation-site.json")
    with serve_ui(service) as url:
        page, errors = open_page(ui_browser, url)
        wait_until_ready(page)
        expect(page.locator("#ideas-explanation")).to_contain_text("selected date")
        expect(page.locator("#ideas-explanation")).to_contain_text("evening astronomical twilight")
        expect(page.locator("#ideas-explanation")).to_contain_text("morning twilight")
        assert not errors
        page.close()


def test_priority_suggestion_acknowledges_selection_without_network_action(tmp_path, ui_browser):
    service = UiService(tmp_path / "suggestion-ack-site.json")
    with serve_ui(service) as url:
        page, errors = open_page(ui_browser, url)
        requests = []
        page.on("request", lambda request: requests.append(request.url))
        wait_until_ready(page)
        submit_object(page, "Suggestion")
        suggestion = page.locator("#suggestion-item")
        expect(page.locator("#suggestion-label")).to_contain_text("future date")
        expect(suggestion).to_have_attribute("aria-pressed", "false")
        calls_before = len(requests)

        suggestion.press("Enter")

        expect(suggestion).to_have_attribute("aria-pressed", "true")
        expect(suggestion).to_have_class(re.compile(r"\bselected\b"))
        expect(page.locator("#result-live")).to_have_text("Suggestion selected")
        assert len(requests) == calls_before
        assert not errors
        page.close()


def test_night_plan_shows_gaps_and_short_fill_without_hiding_them(tmp_path, ui_browser):
    class PartialIdeasUiService(UiService):
        def ideas(self, payload):
            return {
                "status": "partial", "note": "Partial plan.", "darkness_mode": "astronomical",
                "timezone": "Europe/Rome", "night_start": "2026-09-05T21:00:00+02:00",
                "night_end": "2026-09-06T01:00:00+02:00", "night_duration_seconds": 14400,
                "covered_duration_seconds": 10800, "coverage_percent": 75, "preferred_block_seconds": 7200,
                "blocks": [{
                    "target": {"name": "Edge", "type": "HII", "aliases": [], "ra_deg": 1, "dec_deg": 2},
                    "start": "2026-09-05T21:00:00+02:00", "end": "2026-09-05T22:00:00+02:00",
                    "offset_start": 32400, "offset_end": 36000, "duration_seconds": 3600,
                    "reason": "Useful fill.", "short_fill": True,
                }],
                "gaps": [{
                    "start": "2026-09-05T22:00:00+02:00", "end": "2026-09-05T23:00:00+02:00",
                    "offset_start": 36000, "offset_end": 39600, "duration_seconds": 3600,
                }],
            }

    service = PartialIdeasUiService(tmp_path / "partial-ideas-site.json")
    with serve_ui(service) as url:
        page, errors = open_page(ui_browser, url, viewport={"width": 390, "height": 844})
        wait_until_ready(page)
        page.get_by_role("button", name="Need ideas?", exact=True).click()
        expect(page.locator("#night-plan")).to_contain_text("Short block")
        expect(page.locator("#night-gaps")).to_contain_text("Open gap")
        assert page.evaluate("document.documentElement.scrollWidth <= document.documentElement.clientWidth")
        assert not errors
        page.close()


def test_night_plan_shows_an_explicit_no_astronomical_night_state(tmp_path, ui_browser):
    class NoNightUiService(UiService):
        def ideas(self, payload):
            return {
                "status": "none", "note": "In questa data There is no complete astronomical night.",
                "darkness_mode": "astronomical", "timezone": "Europe/Rome",
                "night_start": None, "night_end": None, "night_duration_seconds": 0,
                "covered_duration_seconds": 0, "coverage_percent": 0,
                "preferred_block_seconds": 7200, "blocks": [], "gaps": [],
            }

    service = NoNightUiService(tmp_path / "no-night-site.json")
    with serve_ui(service) as url:
        page, errors = open_page(ui_browser, url)
        wait_until_ready(page)
        page.get_by_role("button", name="Need ideas?", exact=True).click()
        expect(page.locator("#night-period")).to_contain_text("No complete astronomical night")
        expect(page.locator("#night-blocks")).to_contain_text("There is no complete astronomical night")
        expect(page.locator("#night-plan")).to_be_visible()
        assert not errors
        page.close()


def test_geolocation_proposal_confirm_cancel_and_denial_preserve_manual_values(tmp_path, ui_browser):
    success_script = """
        Object.defineProperty(navigator, 'geolocation', {
          configurable: true,
          value: {getCurrentPosition(success) {
            window.completeGeolocation = () => success({coords: {latitude: 45.1234, longitude: 9.5678, accuracy: 42}});
          }}
        });
    """
    service = UiService(tmp_path / "geo-site.json")
    with serve_ui(service) as url:
        page, errors = open_page(ui_browser, url, init_script=success_script)
        requests = []
        page.on("request", lambda request: requests.append(request.url))
        wait_until_ready(page)
        page.get_by_role("button", name="Check visibility", exact=True).click()
        expect(page.locator("#result-content")).to_be_visible()
        latitude = page.get_by_label("Latitude", exact=True)
        longitude = page.get_by_label("Longitude", exact=True)
        timezone = page.get_by_label("Site time zone (IANA)", exact=True)
        manual = (latitude.input_value(), longitude.input_value(), timezone.input_value())

        locate = page.locator("#detect-location")
        locate.click()
        expect(locate).to_have_attribute("aria-busy", "true")
        page.evaluate("window.completeGeolocation()")
        expect(page.locator("#location-proposal")).to_contain_text("Accuracy ± 42 m")
        assert (latitude.input_value(), longitude.input_value(), timezone.input_value()) == manual
        page.get_by_role("button", name="Cancel", exact=True).click()
        expect(page.locator("#location-proposal")).to_be_hidden()
        assert (latitude.input_value(), longitude.input_value(), timezone.input_value()) == manual

        locate.click()
        page.evaluate("window.completeGeolocation()")
        expect(page.locator("#location-proposal")).to_be_visible()
        page.get_by_role("button", name="Use this location", exact=True).click()
        expect(latitude).to_have_value("45.1234")
        expect(longitude).to_have_value("9.5678")
        expect(timezone).to_have_value(manual[2])
        expect(page.locator("#stale-badge")).to_be_visible()
        assert all(urlparse(request_url).hostname == "127.0.0.1" for request_url in requests)
        assert not errors
        page.close()

        denied_script = """
            Object.defineProperty(navigator, 'geolocation', {
              configurable: true,
              value: {getCurrentPosition(_success, error) {
                error({code: 1, PERMISSION_DENIED: 1, POSITION_UNAVAILABLE: 2, TIMEOUT: 3});
              }}
            });
        """
        denied, denied_errors = open_page(ui_browser, url, init_script=denied_script)
        wait_until_ready(denied)
        denied_latitude = denied.get_by_label("Latitude", exact=True).input_value()
        denied.get_by_role("button", name="Use my location", exact=True).click()
        expect(denied.locator("#site-status")).to_contain_text("permission")
        expect(denied.get_by_label("Latitude", exact=True)).to_have_value(denied_latitude)
        assert not denied_errors
        denied.close()

        unavailable_script = "Object.defineProperty(navigator, 'geolocation', {configurable: true, value: undefined});"
        unavailable, unavailable_errors = open_page(ui_browser, url, init_script=unavailable_script)
        wait_until_ready(unavailable)
        unavailable.get_by_role("button", name="Use my location", exact=True).click()
        expect(unavailable.locator("#site-status")).to_contain_text("unavailable")
        assert not unavailable_errors
        unavailable.close()


def test_result_uses_response_timezone_renders_darkness_and_keeps_nina_inert(tmp_path, ui_browser):
    service = UiService(tmp_path / "result-site.json")
    with serve_ui(service) as url:
        page, errors = open_page(ui_browser, url, viewport={"width": 1440, "height": 1100})
        requests = []
        page.on("request", lambda request: requests.append(request.url))
        wait_until_ready(page)
        timezone = page.get_by_label("Site time zone (IANA)", exact=True)
        timezone.fill("America/New_York")
        submit_object(page, "M 13")
        expect(page.locator("#result-content")).to_be_visible()
        first_window = page.locator("#first-window-time").inner_text()
        assert any(zone in first_window for zone in ("EDT", "GMT-4"))
        assert any(zone in first_window for zone in ("EST", "GMT-5"))
        old_period = page.locator("#result-period").inner_text()
        timezone.fill("Europe/Rome")
        expect(page.locator("#stale-badge")).to_be_visible()
        assert page.locator("#result-period").inner_text() == old_period

        submit_object(page, "Polar Night")
        expect(page.locator("#darkness-summary")).to_have_text("Astronomical darkness covers all 24 hours")
        expect(page.locator("#darkness-start")).to_contain_text("Not present in the 24-hour window")
        expect(page.locator("#darkness-end")).to_contain_text("Not present in the 24-hour window")

        submit_object(page, "Polar Day")
        expect(page.locator("#darkness-summary")).to_have_text("No astronomical darkness in the 24-hour window")
        nina = page.get_by_role("button", name="Export TARGET to NINA", exact=True)
        expect(nina).to_be_visible()
        expect(nina).to_be_disabled()
        expect(page.get_by_text("Coming soon", exact=True)).to_be_visible()

        submit_object(page, "One Event")
        expect(page.locator("#darkness-summary")).to_contain_text("starts in astronomical darkness")
        expect(page.locator("#darkness-start")).to_contain_text("Not present in the 24-hour window")
        expect(page.locator("#darkness-end [data-event-kind='night_end']")).to_have_count(1)

        submit_object(page, "Multi Event")
        expect(page.locator("#darkness-start [data-event-kind='night_start']")).to_have_count(2)
        expect(page.locator("#darkness-end [data-event-kind='night_end']")).to_have_count(2)

        darkness_before = page.locator("#darkness-events [data-event-kind]").all_inner_texts()
        page.get_by_label("Minimum altitude", exact=True).fill("5")
        page.get_by_role("button", name="Check visibility", exact=True).click()
        expect(page.locator("#darkness-events [data-event-kind]")).to_have_count(4)
        assert page.locator("#darkness-events [data-event-kind]").all_inner_texts() == darkness_before
        assert service.check_payloads[-1]["timezone"] == "Europe/Rome"

        page.set_viewport_size({"width": 390, "height": 844})
        overflowing = page.locator("body *").evaluate_all(
            """elements => elements.filter(element => {
              const box = element.getBoundingClientRect();
              return box.right > window.innerWidth + 1 || box.left < -1;
            }).map(element => ({tag: element.tagName, id: element.id, className: String(element.className), right: element.getBoundingClientRect().right}))"""
        )
        assert not overflowing, overflowing
        page.get_by_label("Sky object", exact=True).focus()
        assert page.evaluate("document.activeElement.id") == "object"
        assert not any("nina" in request.lower() for request in requests)
        assert not errors
        page.close()


def test_datetime_change_closes_native_picker_focus_and_boundary_hint_is_visible(tmp_path, ui_browser):
    service = UiService(tmp_path / "picker-site.json")
    with serve_ui(service) as url:
        page, errors = open_page(ui_browser, url)
        wait_until_ready(page)
        start = page.locator("#start")
        start.focus()
        page.evaluate(
            """() => {
                const input = document.querySelector('#start');
                input.value = '2026-09-05T23:00';
                input.dispatchEvent(new Event('change', {bubbles: true}));
            }"""
        )
        expect(page.locator("#start")).not_to_be_focused()
        submit_object(page, "Boundary")
        expect(page.locator("#first-window-note")).to_contain_text("may continue beyond")
        assert not errors
        page.close()


def test_datetime_input_closes_after_complete_minutes_but_not_while_incomplete(tmp_path, ui_browser):
    service = UiService(tmp_path / "picker-input-site.json")
    with serve_ui(service) as url:
        page, errors = open_page(ui_browser, url)
        wait_until_ready(page)
        start = page.locator("#start")
        start.focus()
        page.evaluate(
            """() => {
                const input = document.querySelector('#start');
                input.value = '';
                input.dispatchEvent(new Event('input', {bubbles: true}));
            }"""
        )
        expect(start).to_be_focused()
        page.evaluate(
            """() => {
                const input = document.querySelector('#start');
                input.value = '2026-09-05T23:17';
                input.dispatchEvent(new Event('input', {bubbles: true}));
            }"""
        )
        expect(start).not_to_be_focused()
        expect(start).to_have_value("2026-09-05T23:17")
        assert not errors
        page.close()
