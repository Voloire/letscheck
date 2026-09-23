import pytest

from astrochecker.server import validate_v1_check_request


def test_v1_check_accepts_site_profile_and_date_context():
    result = validate_v1_check_request({
        "object": "M31",
        "site": {
            "latitude": 45.46,
            "longitude": 9.19,
            "timezone": "Europe/Rome",
        },
        "date": "2026-09-23",
        "duration_minutes": 60,
        "profile": {"filter": "narrowband", "ready_at": "21:30"},
    })

    assert result["start"].isoformat() == "2026-09-23T21:30:00+02:00"
    assert result["duration_seconds"] == 3600
    assert result["filter"] == "narrowband"


@pytest.mark.parametrize("payload, message", [
    ({"object": "M31"}, "Site is required"),
    ({"object": "M31", "site": {}, "duration_minutes": 60}, "latitude must be a number"),
    ({"object": "M31", "site": {"latitude": 1, "longitude": 2, "timezone": "Europe/Rome"}, "duration_minutes": 60, "profile": {"filter": "infrared"}}, "broadband or narrowband"),
])
def test_v1_check_rejects_incomplete_context(payload, message):
    with pytest.raises(ValueError, match=message):
        validate_v1_check_request(payload)
