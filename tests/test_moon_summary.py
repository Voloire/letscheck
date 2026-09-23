from types import SimpleNamespace

import numpy as np

from astrochecker.local_astronomy import summarize_moon
from astrochecker.sky_mask import SkyMask


def test_moon_summary_reports_rise_window_maximum_and_mask_window():
    ephemeris = SimpleNamespace(
        moon_alt=np.array([-3, 5, 25, 10, -2], dtype=float),
        moon_az=np.array([100, 110, 120, 130, 140], dtype=float),
        moon_illumination=np.array([0.4, 0.5, 0.6, 0.7, 0.8], dtype=float),
        sample_offsets=np.array([0, 300, 600, 900, 1200], dtype=int),
    )
    mask = SkyMask.from_limits(az_start=105, az_end=125, min_alt=0, max_alt=30)

    result = summarize_moon(ephemeris, mask)

    assert result["illumination"] == 0.6
    assert result["maximum_altitude"] == 25
    assert result["above_horizon"] == [{"start": 300, "end": 900}]
    assert result["inside_mask"] == [{"start": 300, "end": 600}]


def test_moon_summary_rejects_incomplete_arrays():
    ephemeris = SimpleNamespace(
        moon_alt=np.array([1, 2]), moon_az=np.array([10]),
        moon_illumination=np.array([0.5, 0.6]), sample_offsets=np.array([0, 1]),
    )

    try:
        summarize_moon(ephemeris)
    except ValueError as exc:
        assert "same" in str(exc)
    else:
        raise AssertionError("incomplete Moon arrays were accepted")
