import pytest

from astrochecker.planner import position_is_visible, solve_visibility
from astrochecker.sky_mask import SkyMask, SkyMaskError


def test_rectangle_matches_balcony_limits_and_preserves_the_ceiling():
    mask = SkyMask.from_limits(az_start=90, az_end=180, min_alt=20, max_alt=45)

    assert mask.contains(90.1, 20)
    assert mask.contains(135, 45)
    assert not mask.contains(135, 19.9)
    assert not mask.contains(135, 45.1)
    assert not mask.contains(89.9, 30)
    assert not mask.contains(180.1, 30)


def test_rectangle_can_cross_north_without_becoming_the_opposite_sector():
    mask = SkyMask.from_limits(az_start=350, az_end=10, min_alt=15, max_alt=50)

    assert mask.contains(359.75, 30)
    assert mask.contains(0.25, 30)
    assert mask.contains(10, 30)
    assert not mask.contains(30, 30)
    assert not mask.contains(340, 30)


def test_multiple_pieces_are_unioned_in_the_compiled_columns():
    mask = SkyMask.from_payload({
        "version": 1,
        "pieces": [
            {"points": [[20, 10], [40, 10], [40, 30], [20, 30]]},
            {"points": [[100, 40], [120, 40], [120, 60], [100, 60]]},
        ],
    })

    assert mask.contains(30, 20)
    assert mask.contains(110, 50)
    assert not mask.contains(30, 40)
    assert not mask.contains(70, 50)


@pytest.mark.parametrize("payload, message", [
    ({"version": 2, "pieces": []}, "version"),
    ({"version": 1, "pieces": []}, "at least one"),
    ({"version": 1, "pieces": [{"points": [[0, 0], [1, 1]]}]}, "between 3"),
    ({"version": 1, "pieces": [{"points": [[0, 10], [1, 10], [2, 10]]}]}, "degenerate"),
    ({"version": 1, "pieces": [{"points": [[0, 10], [1, 10], [2, 100]]}]}, "between 0 and 90"),
])
def test_invalid_masks_are_rejected_with_a_specific_reason(payload, message):
    with pytest.raises(SkyMaskError, match=message):
        SkyMask.from_payload(payload)


def test_payload_round_trip_keeps_original_polygon_coordinates():
    payload = {
        "version": 1,
        "pieces": [{"points": [[350, 12], [10, 12], [10, 42], [350, 42]]}],
    }

    assert SkyMask.from_payload(payload).to_payload() == payload


def test_visibility_solver_can_use_a_mask_without_changing_the_legacy_limits_contract():
    mask = SkyMask.from_limits(az_start=350, az_end=10, min_alt=20, max_alt=40)

    def position_at(offset):
        return {
            "alt": 30,
            "az": 359 if offset == 0 else 30,
            "sun_alt": -20,
        }

    assert position_is_visible(
        position_at(0), min_alt=0, max_alt=90, az_start=0, az_end=360, mask=mask
    )
    result = solve_visibility(
        position_at,
        duration_seconds=1,
        horizon_seconds=1,
        min_alt=0,
        max_alt=90,
        az_start=0,
        az_end=360,
        resolution_seconds=1,
        mask=mask,
    )

    assert result["intervals"] == [{"start": 0, "end": 0}]


def test_mask_erosion_removes_the_field_of_view_margin_from_floor_ceiling_and_edges():
    mask = SkyMask.from_limits(az_start=90, az_end=180, min_alt=20, max_alt=45)

    safe = mask.eroded(2)

    assert safe.contains(100, 22)
    assert safe.contains(170, 43)
    assert not safe.contains(100, 21.9)
    assert not safe.contains(100, 43.1)
    assert not safe.contains(91, 30)
    assert not safe.contains(179, 30)


def test_zero_field_of_view_margin_reuses_the_original_compiled_mask():
    mask = SkyMask.from_limits(az_start=90, az_end=180, min_alt=20, max_alt=45)

    assert mask.eroded(0) is mask


def test_mask_erosion_rejects_negative_or_non_finite_margins():
    with pytest.raises(SkyMaskError, match="margin"):
        SkyMask.from_limits(az_start=90, az_end=180, min_alt=20, max_alt=45).eroded(-1)
    with pytest.raises(SkyMaskError, match="finite"):
        SkyMask.from_limits(az_start=90, az_end=180, min_alt=20, max_alt=45).eroded(float("nan"))
