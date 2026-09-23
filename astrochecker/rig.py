"""Imaging-rig validation and field-of-view calculations for A1."""

from __future__ import annotations

import math
from numbers import Real


DEFAULT_RIG = {
    "focal_length_mm": 400.0,
    "sensor_mm": [23.5, 15.6],
}


class RigError(ValueError):
    """Raised when a rig profile cannot define a field of view."""


def _positive_number(value, label):
    if isinstance(value, bool) or not isinstance(value, Real):
        raise RigError(f"{label} must be a number")
    value = float(value)
    if not math.isfinite(value) or value <= 0:
        raise RigError(f"{label} must be finite and greater than zero")
    return value


def validate_rig(payload=None):
    """Return a normalized rig profile with angular fields in degrees."""
    if payload is None:
        payload = DEFAULT_RIG
    if not isinstance(payload, dict):
        raise RigError("Rig must be an object")
    focal_length = _positive_number(payload.get("focal_length_mm"), "Focal length")
    sensor = payload.get("sensor_mm")
    if not isinstance(sensor, (list, tuple)) or len(sensor) != 2:
        raise RigError("Sensor must contain width and height")
    sensor_width = _positive_number(sensor[0], "Sensor width")
    sensor_height = _positive_number(sensor[1], "Sensor height")

    def field_of_view(size):
        return math.degrees(2 * math.atan(size / (2 * focal_length)))

    horizontal = field_of_view(sensor_width)
    vertical = field_of_view(sensor_height)
    diagonal = field_of_view(math.hypot(sensor_width, sensor_height))
    return {
        "focal_length_mm": focal_length,
        "sensor_mm": [sensor_width, sensor_height],
        "field_of_view_deg": {
            "horizontal": horizontal,
            "vertical": vertical,
            "diagonal": diagonal,
        },
        "mask_margin_deg": diagonal / 2,
    }
