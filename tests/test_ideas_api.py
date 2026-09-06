import json
import threading
from http.client import HTTPConnection

import pytest


REQUEST = {
    "latitude": 43.9729, "longitude": 7.9944,
    "start": "2026-09-05T23:00", "timezone": "Europe/Rome",
    "duration_minutes": 240, "min_alt": 0, "max_alt": 90,
    "az_start": 0, "az_end": 360,
}


def test_ideas_request_keeps_shared_duration_but_accepts_short_single_target_value():
    from astrochecker.server import validate_ideas_request

    result = validate_ideas_request(REQUEST | {"duration_minutes": 1, "darkness_mode": "nautical"})
    assert result["duration_seconds"] == 60
    assert result["darkness_mode"] == "nautical"
    with pytest.raises(ValueError, match="90"):
        validate_ideas_request(REQUEST | {"search_days": 91})
    with pytest.raises(ValueError, match="[Dd]arkness"):
        validate_ideas_request(REQUEST | {"darkness_mode": "civil"})


def test_idea_candidate_selection_keeps_each_catalogued_type_before_filling_priority():
    from astrochecker.service import _select_idea_candidates

    records = [
        {"name": "nebula", "type": "HII", "profile": {"eligible": True, "priority": 100}},
        {"name": "open", "type": "OCl", "profile": {"eligible": True, "priority": 70}},
        {"name": "globular", "type": "GCl", "profile": {"eligible": True, "priority": 70}},
        {"name": "cluster-nebula", "type": "Cl+N", "profile": {"eligible": True, "priority": 70}},
    ]
    records.extend(
        {"name": f"extra-{index:02d}", "type": "HII", "profile": {"eligible": True, "priority": 100}}
        for index in range(20)
    )

    selected = _select_idea_candidates(records, limit=5)

    assert {item["type"] for item in selected} >= {"HII", "OCl", "GCl", "Cl+N"}
    assert len(selected) == 5


def test_ideas_service_returns_complete_twilight_bounded_target_chain(monkeypatch):
    from astrochecker.service import AstroCheckerService

    class StubCatalog:
        def idea_candidates(self, include_ineligible=False):
            return [
                {
                    "name": name, "type": "GCl", "ra_deg": ra, "dec_deg": 20,
                    "aliases": [f"Alias {name}"], "source": "test", "profile": {
                        "eligible": True, "priority": priority, "reason": f"Motivo {name}",
                    },
                }
                for name, ra, priority in [("X", 10, 80), ("Y", 20, 70), ("Z", 30, 60)]
            ]

    class DarknessEphemeris:
        uses_prediction = False
        iers_coverage_start = "test"
        iers_coverage_end_exclusive = "test"
        sample_offsets = list(range(0, 86401, 300))
        sun_alt = [10] * 72 + [-20] * 97 + [10] * 120

        @staticmethod
        def position_at(offset):
            return {"alt": 0, "az": 180, "sun_alt": 10}

    def target_ephemeris(left, right):
        class TargetEphemeris(DarknessEphemeris):
            @staticmethod
            def position_at(offset):
                return {"alt": 45 if left <= offset < right else -10, "az": 180, "sun_alt": -20}
        return TargetEphemeris()

    monkeypatch.setattr("astrochecker.service.build_ephemeris", lambda *args, **kwargs: DarknessEphemeris())
    monkeypatch.setattr(
        "astrochecker.service.build_catalog_ephemerides",
        lambda coordinates, *args, **kwargs: [target_ephemeris(*{
            10: (21600, 31500),
            20: (30900, 41100),
            30: (40500, 50700),
        }[ra]) for ra, _dec in coordinates],
    )
    result = AstroCheckerService(catalog=StubCatalog()).ideas(REQUEST | {"duration_minutes": 1})

    assert result["status"] == "full"
    assert result["darkness_mode"] == "astronomical"
    assert result["start"] == "2026-09-05T12:00:00+02:00"
    assert result["night_start"] == "2026-09-05T18:00:00+02:00"
    assert result["night_end"] == "2026-09-06T02:00:00+02:00"
    assert [block["target"]["name"] for block in result["blocks"]] == ["X", "Y", "Z"]
    assert result["blocks"][0]["target"]["aliases"] == ["Alias X"]
    assert result["blocks"][0]["offset_start"] == 21600
    assert result["blocks"][0]["start"] == "2026-09-05T18:00:00+02:00"
    assert result["coverage_percent"] == 100
    assert result["duration_seconds"] == 60

    balcony_filtered = AstroCheckerService(catalog=StubCatalog()).ideas(
        REQUEST | {"duration_minutes": 1, "max_alt": 30}
    )
    assert balcony_filtered["status"] == "none"
    assert balcony_filtered["blocks"] == []


def test_ideas_service_converts_unavoidable_gap_offsets_to_absolute_times(monkeypatch):
    from astrochecker.service import AstroCheckerService

    class StubCatalog:
        def idea_candidates(self, include_ineligible=False):
            return [{
                "id": 1, "name": "X", "type": "GCl", "ra_deg": 10, "dec_deg": 20,
                "aliases": [], "profile": {"eligible": True, "priority": 80, "reason": "Motivo X"},
            }]

    class DarknessEphemeris:
        uses_prediction = False
        iers_coverage_start = "test"
        iers_coverage_end_exclusive = "test"
        sample_offsets = list(range(0, 86401, 300))
        sun_alt = [10] * 72 + [-20] * 97 + [10] * 120

        @staticmethod
        def position_at(offset):
            return {"alt": 0, "az": 180, "sun_alt": 10}

    class TargetEphemeris(DarknessEphemeris):
        @staticmethod
        def position_at(offset):
            return {"alt": 45 if 21600 <= offset < 28800 else -10, "az": 180, "sun_alt": -20}

    monkeypatch.setattr("astrochecker.service.build_ephemeris", lambda *args, **kwargs: DarknessEphemeris())
    monkeypatch.setattr("astrochecker.service.build_catalog_ephemerides", lambda *args, **kwargs: [TargetEphemeris()])

    result = AstroCheckerService(catalog=StubCatalog()).ideas(REQUEST)

    assert result["status"] == "partial"
    assert result["gaps"] == [{
        "start": "2026-09-05T19:55:00+02:00",
        "end": "2026-09-06T02:00:00+02:00",
        "duration_seconds": 21900,
        "offset_start": 28500,
        "offset_end": 50400,
    }]


def test_ideas_service_stops_before_lower_priority_tiers_after_complete_plan(monkeypatch):
    from astrochecker.service import AstroCheckerService

    class StubCatalog:
        def idea_candidates(self, include_ineligible=False):
            return [
                {"id": 1, "name": "High", "type": "HII", "ra_deg": 10, "dec_deg": 20,
                 "aliases": [], "profile": {"eligible": True, "priority": 100, "reason": "High"}},
                {"id": 2, "name": "Low", "type": "GCl", "ra_deg": 20, "dec_deg": 20,
                 "aliases": [], "profile": {"eligible": True, "priority": 50, "reason": "Low"}},
            ]

    class DarknessEphemeris:
        uses_prediction = False
        iers_coverage_start = "test"
        iers_coverage_end_exclusive = "test"
        sample_offsets = list(range(0, 86401, 300))
        sun_alt = [10] * 72 + [-20] * 97 + [10] * 120

        @staticmethod
        def position_at(offset):
            return {"alt": 0, "az": 180, "sun_alt": 10}

    class TargetEphemeris(DarknessEphemeris):
        @staticmethod
        def position_at(offset):
            return {"alt": 45, "az": 180, "sun_alt": -20}

    evaluated = []
    monkeypatch.setattr("astrochecker.service.build_ephemeris", lambda *args, **kwargs: DarknessEphemeris())

    def build_targets(coordinates, *args, **kwargs):
        evaluated.extend(coordinates)
        return [TargetEphemeris() for _ in coordinates]

    monkeypatch.setattr("astrochecker.service.build_catalog_ephemerides", build_targets)

    result = AstroCheckerService(catalog=StubCatalog()).ideas(REQUEST)

    assert result["status"] == "full"
    assert evaluated == [(10, 20)]
    assert result["evaluated_candidate_count"] == 1
    assert result["skipped"]["not_evaluated"] == 1


def test_ideas_service_sorts_unsorted_catalog_records_before_tier_early_stop(monkeypatch):
    from astrochecker.service import AstroCheckerService

    class StubCatalog:
        def idea_candidates(self, include_ineligible=False):
            return [
                {"id": 1, "name": "Low", "type": "GCl", "ra_deg": 20, "dec_deg": 20,
                 "aliases": [], "profile": {"eligible": True, "priority": 50, "reason": "Low"}},
                {"id": 2, "name": "High", "type": "HII", "ra_deg": 10, "dec_deg": 20,
                 "aliases": [], "profile": {"eligible": True, "priority": 100, "reason": "High"}},
            ]

    class DarknessEphemeris:
        uses_prediction = False
        iers_coverage_start = "test"
        iers_coverage_end_exclusive = "test"
        sample_offsets = list(range(0, 86401, 300))
        sun_alt = [10] * 72 + [-20] * 97 + [10] * 120

        @staticmethod
        def position_at(offset):
            return {"alt": 45, "az": 180, "sun_alt": -20}

    evaluated = []
    monkeypatch.setattr("astrochecker.service.build_ephemeris", lambda *args, **kwargs: DarknessEphemeris())

    def build_targets(coordinates, *args, **kwargs):
        evaluated.extend(coordinates)
        return [DarknessEphemeris() for _ in coordinates]

    monkeypatch.setattr("astrochecker.service.build_catalog_ephemerides", build_targets)

    result = AstroCheckerService(catalog=StubCatalog()).ideas(REQUEST)

    assert evaluated == [(10, 20)]
    assert [block["target"]["name"] for block in result["blocks"]] == ["High"]


def test_ideas_service_reports_when_no_complete_astronomical_night_exists(monkeypatch):
    from astrochecker.service import AstroCheckerService

    class StubCatalog:
        def idea_candidates(self, include_ineligible=False):
            return []

    class DayEphemeris:
        uses_prediction = False
        iers_coverage_start = "test"
        iers_coverage_end_exclusive = "test"
        sample_offsets = list(range(0, 86401, 300))
        sun_alt = [10] * 289

    monkeypatch.setattr("astrochecker.service.build_ephemeris", lambda *args, **kwargs: DayEphemeris())
    monkeypatch.setattr("astrochecker.service.build_catalog_ephemerides", lambda *args, **kwargs: [])

    result = AstroCheckerService(catalog=StubCatalog()).ideas(REQUEST)

    assert result["status"] == "none"
    assert result["night_start"] is None
    assert result["night_end"] is None
    assert result["blocks"] == []
    assert "astronomical night" in result["note"].lower()


def test_ideas_route_is_local_json_and_rejects_invalid_payload():
    from astrochecker.server import create_server

    class Service:
        def ideas(self, payload):
            return {"status": "none", "payload": payload}

    server = create_server(port=0, service=Service())
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        body = json.dumps(REQUEST).encode()
        connection = HTTPConnection("127.0.0.1", server.server_port, timeout=3)
        connection.request("POST", "/api/ideas", body=body, headers={"Content-Type": "application/json"})
        response = connection.getresponse()
        assert response.status == 200
        assert json.loads(response.read())["status"] == "none"
        connection.close()
    finally:
        server.shutdown(); server.server_close(); thread.join()


def test_observing_night_uses_local_noon_of_selected_civil_date():
    from astrochecker.planner import parse_start
    from astrochecker.service import observing_night_anchor

    supplied = parse_start("2026-09-06T02:27", "Europe/Rome")

    assert observing_night_anchor(supplied, "Europe/Rome").isoformat() == "2026-09-06T12:00:00+02:00"
    assert supplied.isoformat() == "2026-09-06T02:27:00+02:00"
