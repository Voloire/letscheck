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


def test_ideas_request_requires_a_two_hour_session_and_known_darkness_mode():
    from astrochecker.server import validate_ideas_request

    result = validate_ideas_request(REQUEST | {"duration_minutes": 120, "darkness_mode": "nautical"})
    assert result["duration_seconds"] == 7200
    assert result["darkness_mode"] == "nautical"
    with pytest.raises(ValueError, match="90"):
        validate_ideas_request(REQUEST | {"search_days": 91})
    with pytest.raises(ValueError, match="buio"):
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


def test_ideas_service_returns_local_plan_with_explicit_partial_note(monkeypatch):
    from astrochecker.service import AstroCheckerService

    class StubCatalog:
        def idea_candidates(self, include_ineligible=False):
            return [{
                "name": "NGC 6205", "type": "GCl", "ra_deg": 10, "dec_deg": 20,
                "aliases": ["M 13"], "source": "test", "profile": {
                    "eligible": True, "priority": 80, "reason": "Ammasso",
                },
            }]

    class Ephemeris:
        uses_prediction = False
        iers_coverage_start = "test"
        iers_coverage_end_exclusive = "test"
        sun_alt = [-20] * 289

        @staticmethod
        def position_at(offset):
            return {"alt": 45 if offset < 10000 else -10, "az": 180, "sun_alt": -20}

    monkeypatch.setattr("astrochecker.service.build_ephemeris", lambda *args, **kwargs: Ephemeris())
    monkeypatch.setattr("astrochecker.service.build_catalog_ephemerides", lambda coordinates, *args, **kwargs: [Ephemeris() for _ in coordinates])
    result = AstroCheckerService(catalog=StubCatalog()).ideas(REQUEST | {"duration_minutes": 360})

    assert result["status"] == "partial"
    assert result["darkness_mode"] == "astronomical"
    assert result["blocks"][0]["object"] == "NGC 6205"
    assert "parziale" in result["note"].lower()


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
