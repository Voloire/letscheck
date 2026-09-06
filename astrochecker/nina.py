"""Native NINA Legacy/Simple Sequencer export helpers."""

from __future__ import annotations

from datetime import datetime
import math
import os
from pathlib import Path
import re
import tempfile
import xml.etree.ElementTree as ET


DEFAULT_EXPOSURE_SECONDS = 300


class NinaSequenceError(ValueError):
    """Raised when a target cannot be represented as a NINA legacy sequence."""


def _target_values(target):
    if not isinstance(target, dict):
        raise NinaSequenceError("NINA target must be an object")
    name = target.get("name")
    if not isinstance(name, str) or not name.strip():
        raise NinaSequenceError("NINA target must have a name")
    name = name.strip()
    ra = target.get("ra_deg", target.get("ra"))
    dec = target.get("dec_deg", target.get("dec"))
    if isinstance(ra, bool) or isinstance(dec, bool):
        raise NinaSequenceError("NINA target coordinates are invalid")
    try:
        ra = float(ra)
        dec = float(dec)
    except (TypeError, ValueError) as exc:
        raise NinaSequenceError("NINA target coordinates are invalid") from exc
    if not math.isfinite(ra) or not math.isfinite(dec) or not -90 <= dec <= 90:
        raise NinaSequenceError("NINA target coordinates are invalid")
    return name, ra % 360, dec


def _number(value):
    text = format(float(value), ".12f").rstrip("0").rstrip(".")
    return text or "0"


def _coordinates_attributes(ra_deg, dec_deg):
    ra_hours = (ra_deg / 15.0) % 24.0
    ra_hours_component = int(math.floor(ra_hours))
    ra_minutes_total = (ra_hours - ra_hours_component) * 60
    ra_minutes = int(math.floor(ra_minutes_total))
    ra_seconds = (ra_minutes_total - ra_minutes) * 60

    absolute_dec = abs(dec_deg)
    dec_degrees = int(math.floor(absolute_dec))
    dec_minutes_total = (absolute_dec - dec_degrees) * 60
    dec_minutes = int(math.floor(dec_minutes_total))
    dec_seconds = (dec_minutes_total - dec_minutes) * 60
    # CaptureSequenceList's NegativeDec setter expects the signed degree value.
    if dec_deg < 0:
        dec_degrees = -dec_degrees

    return {
        "RAHours": str(ra_hours_component),
        "RAMinutes": str(ra_minutes),
        "RASeconds": _number(ra_seconds),
        "NegativeDec": "True" if dec_deg < 0 else "False",
        "DecDegrees": str(dec_degrees),
        "DecMinutes": str(dec_minutes),
        "DecSeconds": _number(dec_seconds),
        "PositionAngle": "0",
    }


def _duration_count(duration_seconds, exposure_seconds):
    try:
        duration = float(duration_seconds)
    except (TypeError, ValueError) as exc:
        raise NinaSequenceError("The proposed window duration is invalid") from exc
    if not math.isfinite(duration) or duration < exposure_seconds:
        raise NinaSequenceError(
            f"The proposed window must be at least {exposure_seconds:g} seconds"
        )
    return int(duration // exposure_seconds)


def build_legacy_sequence_xml(
    target,
    *,
    duration_seconds,
    exposure_seconds=DEFAULT_EXPOSURE_SECONDS,
):
    """Build a NINA ``CaptureSequenceList`` XML document.

    Only the selected target and LIGHT exposure are set.  Gain, offset, filter,
    binning, dither and workflow switches use NINA's legacy defaults.
    """
    if exposure_seconds != DEFAULT_EXPOSURE_SECONDS:
        try:
            exposure_seconds = float(exposure_seconds)
        except (TypeError, ValueError) as exc:
            raise NinaSequenceError("Exposure duration is invalid") from exc
    if not math.isfinite(exposure_seconds) or exposure_seconds <= 0:
        raise NinaSequenceError("Exposure duration is invalid")
    name, ra_deg, dec_deg = _target_values(target)
    exposure_count = _duration_count(duration_seconds, exposure_seconds)

    root = ET.Element(
        "CaptureSequenceList",
        {"TargetName": name, "Mode": "STANDARD", **_coordinates_attributes(ra_deg, dec_deg)},
    )
    capture = ET.SubElement(root, "CaptureSequence")
    fields = (
        ("Enabled", "true"),
        ("ExposureTime", _number(exposure_seconds)),
        ("ImageType", "LIGHT"),
    )
    for tag, value in fields:
        ET.SubElement(capture, tag).text = value
    binning = ET.SubElement(capture, "Binning")
    ET.SubElement(binning, "X").text = "1"
    ET.SubElement(binning, "Y").text = "1"
    for tag, value in (
        ("TotalExposureCount", str(exposure_count)),
        ("ProgressExposureCount", "0"),
        ("Gain", "-1"),
        ("Offset", "-1"),
        ("Dither", "false"),
        ("DitherAmount", "1"),
    ):
        ET.SubElement(capture, tag).text = value

    coordinates = ET.SubElement(root, "Coordinates")
    ET.SubElement(coordinates, "RA").text = _number(ra_deg / 15.0)
    ET.SubElement(coordinates, "Dec").text = _number(dec_deg)
    ET.SubElement(coordinates, "Epoch").text = "J2000"

    ET.indent(root, space="  ")
    return ET.tostring(root, encoding="unicode", xml_declaration=True)


def default_downloads_dir():
    """Return the active user's Downloads directory without a hardcoded profile."""
    profile = os.environ.get("USERPROFILE") if os.name == "nt" else None
    return Path(profile).expanduser() / "Downloads" if profile else Path.home() / "Downloads"


def _safe_filename(name):
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", name).strip("-._") or "target"
    return slug[:80]


def export_legacy_sequence(
    target,
    *,
    duration_seconds,
    sequence_name=None,
    downloads_dir=None,
    filename_timestamp=None,
):
    """Write a native NINA Legacy/Simple Sequencer XML file atomically."""
    xml = build_legacy_sequence_xml(target, duration_seconds=duration_seconds)
    name, _ra_deg, _dec_deg = _target_values(target)
    if sequence_name is None:
        sequence_name = f"AstroChecker_{name}"
    elif not isinstance(sequence_name, str) or not sequence_name.strip():
        raise NinaSequenceError("The NINA sequence name is required")
    sequence_name = _safe_filename(sequence_name.strip())
    exposure_count = _duration_count(duration_seconds, DEFAULT_EXPOSURE_SECONDS)
    directory = Path(downloads_dir) if downloads_dir is not None else default_downloads_dir()
    directory.mkdir(parents=True, exist_ok=True)
    stamp = filename_timestamp or datetime.now().strftime("%Y%m%d-%H%M%S")
    base = f"{sequence_name}_{stamp}"
    path = directory / f"{base}.xml"
    suffix = 1
    while path.exists():
        path = directory / f"{base}-{suffix}.xml"
        suffix += 1

    temporary_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=directory,
            prefix=f".{path.name}-",
            suffix=".tmp",
            delete=False,
        ) as temporary:
            temporary_path = Path(temporary.name)
            temporary.write(xml)
            temporary.write("\n")
            temporary.flush()
            os.fsync(temporary.fileno())
        os.replace(temporary_path, path)
        temporary_path = None
    except OSError as exc:
        raise NinaSequenceError("The NINA sequence could not be saved") from exc
    finally:
        if temporary_path is not None:
            try:
                temporary_path.unlink(missing_ok=True)
            except OSError:
                pass
    return {
        "path": str(path),
        "filename": path.name,
        "exposure_seconds": DEFAULT_EXPOSURE_SECONDS,
        "exposure_count": exposure_count,
    }
