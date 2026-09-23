import pytest

from astrochecker.rig import RigError, validate_rig


def test_default_rig_matches_the_balcony_setup_in_a1():
    rig = validate_rig()

    assert rig["focal_length_mm"] == 400
    assert rig["sensor_mm"] == [23.5, 15.6]
    assert rig["field_of_view_deg"]["horizontal"] == pytest.approx(3.36, abs=0.02)
    assert rig["field_of_view_deg"]["vertical"] == pytest.approx(2.23, abs=0.02)
    assert rig["mask_margin_deg"] == pytest.approx(2.02, abs=0.03)


def test_custom_rig_is_normalized_and_has_a_deterministic_margin():
    rig = validate_rig({"focal_length_mm": 200, "sensor_mm": [36, 24]})

    assert rig["sensor_mm"] == [36, 24]
    assert rig["field_of_view_deg"]["horizontal"] > rig["field_of_view_deg"]["vertical"]
    assert rig["mask_margin_deg"] == pytest.approx(
        rig["field_of_view_deg"]["diagonal"] / 2
    )


@pytest.mark.parametrize("payload, message", [
    ({"focal_length_mm": 0, "sensor_mm": [23.5, 15.6]}, "greater than zero"),
    ({"focal_length_mm": 400, "sensor_mm": [23.5]}, "width and height"),
    ({"focal_length_mm": 400, "sensor_mm": [23.5, "wide"]}, "must be a number"),
])
def test_invalid_rig_profiles_are_rejected(payload, message):
    with pytest.raises(RigError, match=message):
        validate_rig(payload)
