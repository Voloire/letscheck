"""Balcony sky-mask validation and compiled point-in-mask queries."""

from __future__ import annotations

from dataclasses import dataclass
import math
from numbers import Real


AZIMUTH_COLUMNS = 720
AZIMUTH_STEP_DEGREES = 360.0 / AZIMUTH_COLUMNS
MAX_PIECES = 20
MAX_POINTS_PER_PIECE = 200


class SkyMaskError(ValueError):
    """Raised when a sky mask is not a valid version-one payload."""


@dataclass(frozen=True)
class MaskPiece:
    """One validated polygon in azimuth/altitude degrees."""

    points: tuple[tuple[float, float], ...]


def _number(value, label):
    if isinstance(value, bool) or not isinstance(value, Real):
        raise SkyMaskError(f"{label} must be a number")
    value = float(value)
    if not math.isfinite(value):
        raise SkyMaskError(f"{label} must be finite")
    return value


def _azimuth(value, label):
    value = _number(value, label)
    if not 0 <= value <= 360:
        raise SkyMaskError(f"{label} must be between 0 and 360 degrees")
    return value


def _altitude(value, label):
    value = _number(value, label)
    if not 0 <= value <= 90:
        raise SkyMaskError(f"{label} must be between 0 and 90 degrees")
    return value


def _unwrap(points):
    """Unwrap a polygon so an edge crossing north stays a short edge."""
    first_az, first_alt = points[0]
    result = [(first_az, first_alt)]
    previous = first_az
    for azimuth, altitude in points[1:]:
        candidate = azimuth
        while candidate - previous > 180:
            candidate -= 360
        while candidate - previous < -180:
            candidate += 360
        result.append((candidate, altitude))
        previous = candidate
    return result


def _polygon_area(points):
    return abs(sum(
        x1 * y2 - x2 * y1
        for (x1, y1), (x2, y2) in zip(points, points[1:] + points[:1])
    )) / 2


def _intervals_at(points, azimuth):
    """Return the altitude intervals cut by one compiled azimuth column."""
    intersections = []
    for (x1, y1), (x2, y2) in zip(points, points[1:] + points[:1]):
        if x1 == x2:
            continue
        if not (min(x1, x2) <= azimuth < max(x1, x2)):
            continue
        ratio = (azimuth - x1) / (x2 - x1)
        intersections.append(y1 + ratio * (y2 - y1))
    intersections.sort()
    return tuple(
        (max(0.0, start), min(90.0, end))
        for start, end in zip(intersections[::2], intersections[1::2])
        if end > 0 and start < 90 and end > start
    )


class SkyMask:
    """A union of balcony polygons compiled into 0.5-degree columns."""

    version = 1

    def __init__(self, pieces, *, _full_azimuth=False):
        if not isinstance(pieces, (list, tuple)) or not pieces:
            raise SkyMaskError("Sky mask must contain at least one piece")
        if len(pieces) > MAX_PIECES:
            raise SkyMaskError(f"Sky mask cannot contain more than {MAX_PIECES} pieces")

        validated = []
        for piece_index, raw_piece in enumerate(pieces, start=1):
            if not isinstance(raw_piece, (list, tuple)):
                raise SkyMaskError(f"Sky mask piece {piece_index} must be a list of points")
            if not 3 <= len(raw_piece) <= MAX_POINTS_PER_PIECE:
                raise SkyMaskError(
                    f"Sky mask piece {piece_index} must contain between 3 and "
                    f"{MAX_POINTS_PER_PIECE} points"
                )
            points = []
            for point_index, raw_point in enumerate(raw_piece, start=1):
                if not isinstance(raw_point, (list, tuple)) or len(raw_point) != 2:
                    raise SkyMaskError(
                        f"Sky mask piece {piece_index} point {point_index} must be [azimuth, altitude]"
                    )
                points.append((
                    _azimuth(raw_point[0], f"Sky mask piece {piece_index} point {point_index} azimuth"),
                    _altitude(raw_point[1], f"Sky mask piece {piece_index} point {point_index} altitude"),
                ))
            unwrapped = _unwrap(points)
            if _polygon_area(unwrapped) <= 1e-9:
                raise SkyMaskError(f"Sky mask piece {piece_index} is degenerate")
            validated.append(MaskPiece(tuple(points)))

        self.pieces = tuple(validated)
        self._unwrapped_pieces = tuple(_unwrap(piece.points) for piece in self.pieces)
        self._full_azimuth = bool(_full_azimuth)
        self._columns = self._compile()

    @classmethod
    def from_payload(cls, payload):
        if not isinstance(payload, dict):
            raise SkyMaskError("Sky mask must be an object")
        if payload.get("version") != cls.version:
            raise SkyMaskError("Sky mask version must be 1")
        pieces = []
        for piece in payload.get("pieces", []):
            if not isinstance(piece, dict):
                raise SkyMaskError("Each sky mask piece must be an object")
            pieces.append(piece.get("points"))
        return cls(pieces)

    @classmethod
    def from_limits(cls, *, az_start, az_end, min_alt, max_alt):
        az_start = _azimuth(az_start, "Azimuth start")
        az_end = _azimuth(az_end, "Azimuth end")
        min_alt = _altitude(min_alt, "Minimum altitude")
        max_alt = _altitude(max_alt, "Maximum altitude")
        if max_alt <= min_alt:
            raise SkyMaskError("Maximum altitude must exceed minimum altitude")
        if az_start == 0 and az_end == 360:
            points = ((0, min_alt), (359.999999, min_alt), (359.999999, max_alt), (0, max_alt))
            return cls([points], _full_azimuth=True)
        if az_start == az_end:
            raise SkyMaskError("A sector with matching start and end azimuths is ambiguous")
        return cls([(
            (az_start, min_alt),
            (az_end, min_alt),
            (az_end, max_alt),
            (az_start, max_alt),
        )])

    def _compile(self):
        columns = [[] for _ in range(AZIMUTH_COLUMNS)]
        for points in self._unwrapped_pieces:
            minimum = min(x for x, _ in points)
            maximum = max(x for x, _ in points)
            for index in range(AZIMUTH_COLUMNS):
                center = (index + 0.5) * AZIMUTH_STEP_DEGREES
                candidates = [center]
                if minimum <= center + 360 <= maximum:
                    candidates.append(center + 360)
                if minimum <= center - 360 <= maximum:
                    candidates.append(center - 360)
                for candidate in candidates:
                    columns[index].extend(_intervals_at(points, candidate))
        compiled = []
        for intervals in columns:
            intervals.sort()
            merged = []
            for start, end in intervals:
                if merged and start <= merged[-1][1]:
                    merged[-1] = (merged[-1][0], max(merged[-1][1], end))
                else:
                    merged.append((start, end))
            compiled.append(tuple(merged))
        if self._full_azimuth:
            return tuple(
                intervals or ((0.0, 90.0),)
                for intervals in compiled
            )
        return tuple(compiled)

    def intervals_at(self, azimuth):
        azimuth = _azimuth(azimuth, "Azimuth") % 360
        index = min(AZIMUTH_COLUMNS - 1, int(azimuth / AZIMUTH_STEP_DEGREES))
        return self._columns[index]

    def eroded(self, margin_degrees):
        """Return a compiled mask safe for a circular field-of-view margin.

        The margin is the angular radius reserved around the requested
        pointing.  Erosion is conservative: the altitude interval is shrunk
        by the margin and all compiled azimuth columns within the corresponding
        spherical longitude distance must contain that interval.  The source
        polygon and its payload are not changed.
        """
        margin = _number(margin_degrees, "Field-of-view margin")
        if margin < 0:
            raise SkyMaskError("Field-of-view margin must not be negative")
        if margin > 90:
            raise SkyMaskError("Field-of-view margin must not exceed 90 degrees")
        if margin == 0:
            return self

        columns = []
        for index in range(AZIMUTH_COLUMNS):
            safe_pieces = []
            for start, end in self._columns[index]:
                safe = ((start + margin, end - margin),) if end - start > 2 * margin else ()
                if not safe:
                    continue
                # Use the upper end of this local interval: longitude distance
                # grows towards the zenith, so this is conservative without
                # letting a high ceiling erase every lower interval in a column.
                radius = math.ceil(
                    _longitude_margin(margin, end - margin) / AZIMUTH_STEP_DEGREES
                )
                for offset in range(-radius, radius + 1):
                    source = self._columns[(index + offset) % AZIMUTH_COLUMNS]
                    inward = tuple(
                        (source_start + margin, source_end - margin)
                        for source_start, source_end in source
                        if source_end - source_start > 2 * margin
                    )
                    safe = _intersect_intervals(safe, inward)
                    if not safe:
                        break
                safe_pieces.extend(safe)
            safe_pieces.sort()
            merged = []
            for start, end in safe_pieces:
                if merged and start <= merged[-1][1]:
                    merged[-1] = (merged[-1][0], max(merged[-1][1], end))
                else:
                    merged.append((start, end))
            columns.append(tuple(merged))
        return _CompiledSkyMask(self, columns, margin)

    def contains(self, azimuth, altitude):
        azimuth = _azimuth(azimuth, "Azimuth") % 360
        altitude = _altitude(altitude, "Altitude")
        if any(start <= altitude <= end for start, end in self.intervals_at(azimuth)):
            return True
        # The compiled table is intentionally quantised, but exact polygon
        # boundaries must remain inclusive for API callers and legacy limits.
        for points in self._unwrapped_pieces:
            for candidate in (azimuth, azimuth + 360, azimuth - 360):
                for (x1, y1), (x2, y2) in zip(points, points[1:] + points[:1]):
                    cross = (candidate - x1) * (y2 - y1) - (altitude - y1) * (x2 - x1)
                    if abs(cross) > 1e-8:
                        continue
                    if min(x1, x2) - 1e-8 <= candidate <= max(x1, x2) + 1e-8 and (
                        min(y1, y2) - 1e-8 <= altitude <= max(y1, y2) + 1e-8
                    ):
                        return True
        return False

    def lowest_visible_altitude(self, azimuth):
        intervals = self.intervals_at(azimuth)
        if intervals:
            return intervals[0][0]
        azimuth = _azimuth(azimuth, "Azimuth") % 360
        boundary_altitudes = []
        for points in self._unwrapped_pieces:
            for candidate in (azimuth, azimuth + 360, azimuth - 360):
                for (x1, y1), (x2, y2) in zip(points, points[1:] + points[:1]):
                    if abs(candidate - x1) <= 1e-8 and abs(candidate - x2) <= 1e-8:
                        boundary_altitudes.extend((y1, y2))
                    elif abs(candidate - x1) <= 1e-8:
                        boundary_altitudes.append(y1)
                    elif abs(candidate - x2) <= 1e-8:
                        boundary_altitudes.append(y2)
        return min(boundary_altitudes) if boundary_altitudes else None

    def to_nina_horizon(self):
        """Render the lowest visible altitude as NINA custom-horizon text."""
        lines = [
            "# AstroChecker sky mask version 1",
            "# Each row is: azimuth_degrees altitude_degrees",
            "# The upper ceiling of the mask cannot be represented by NINA horizon files.",
        ]
        for index in range(AZIMUTH_COLUMNS):
            azimuth = index * AZIMUTH_STEP_DEGREES
            altitude = self.lowest_visible_altitude(azimuth)
            lines.append(f"{azimuth:g} {90 if altitude is None else altitude:g}")
        return "\n".join(lines) + "\n"

    def to_payload(self):
        return {
            "version": self.version,
            "pieces": [{"points": [list(point) for point in piece.points]} for piece in self.pieces],
        }


def _longitude_margin(margin, altitude):
    """Return a conservative longitude distance for a spherical angular margin."""
    if altitude >= 90 or altitude + margin >= 90:
        return 180.0
    radians_margin = math.radians(margin)
    radians_altitude = math.radians(altitude)
    sine = math.sin(radians_altitude)
    cosine = math.cos(radians_altitude)
    denominator = cosine * cosine
    cosine_delta = (math.cos(radians_margin) - sine * sine) / denominator
    if cosine_delta <= -1:
        return 180.0
    if cosine_delta >= 1:
        return 0.0
    return math.degrees(math.acos(cosine_delta))


def _intersect_intervals(left, right):
    result = []
    right_index = 0
    while right_index < len(right) and left:
        right_start, right_end = right[right_index]
        next_left = []
        for left_start, left_end in left:
            start = max(left_start, right_start)
            end = min(left_end, right_end)
            if end > start:
                next_left.append((start, end))
        result.extend(next_left)
        right_index += 1
    result.sort()
    return tuple(result)


class _CompiledSkyMask:
    """Read-only compiled view used after field-of-view erosion."""

    def __init__(self, source, columns, margin_degrees):
        self.version = source.version
        self.source = source
        self.margin_degrees = margin_degrees
        self._columns = tuple(columns)

    def intervals_at(self, azimuth):
        azimuth = _azimuth(azimuth, "Azimuth") % 360
        index = min(AZIMUTH_COLUMNS - 1, int(azimuth / AZIMUTH_STEP_DEGREES))
        return self._columns[index]

    def contains(self, azimuth, altitude):
        altitude = _altitude(altitude, "Altitude")
        return any(start <= altitude <= end for start, end in self.intervals_at(azimuth))

    def lowest_visible_altitude(self, azimuth):
        intervals = self.intervals_at(azimuth)
        return intervals[0][0] if intervals else None

    def to_nina_horizon(self):
        return self.source.__class__.to_nina_horizon(self)
