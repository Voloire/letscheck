"""Deterministic suitability profiles for the local ideas planner."""

from __future__ import annotations

import math
import re


IDEA_MIN_BLOCK_SECONDS = 7200
EXTENDED_GALAXY_ARCMIN = 30.0

_STELLAR_TYPES = {"*", "**", "*ASS", "NOVA"}
_CLUSTER_TYPES = {"OCL", "GCL", "CL+N"}
_NEBULA_TYPES = {"EMN", "HI I", "HII", "RFN", "NEB", "SNR", "PN"}
_GALAXY_TYPES = {"G"}
_BEGINNER_NAMES = {
    "M 1", "M 8", "M 13", "M 16", "M 17", "M 20", "M 27", "M 31",
    "M 33", "M 42", "M 45", "M 51", "M 57", "M 81", "M 82", "M 101",
    "NGC 224", "NGC 598", "NGC 1976", "NGC 6611", "NGC 6618", "NGC 7000",
    "IC 434", "SH 2-184", "SH 2-155",
}


def _normalise_type(value: object) -> str:
    return re.sub(r"\s+", "", str(value or "").upper())


def _text_names(record: dict) -> set[str]:
    values = [record.get("name", ""), *(record.get("aliases") or [])]
    return {str(value).strip().upper().replace("  ", " ") for value in values if value}


def _is_beginner(record: dict) -> bool:
    if bool(record.get("beginner")):
        return True
    names = _text_names(record)
    if any(name.startswith("M ") or name.startswith("M") and name[1:].strip().isdigit() for name in names):
        return True
    return any(name in _BEGINNER_NAMES for name in names)


def _extended_galaxy(record: dict) -> bool:
    if bool(record.get("extended")) or bool(record.get("is_extended")):
        return True
    for key in (
        "major_axis_arcmin", "size_arcmin", "angular_size_arcmin", "diameter_arcmin",
        "major_axis", "size", "angular_size", "diameter",
    ):
        value = record.get(key)
        if value is None:
            continue
        try:
            if math.isfinite(float(value)) and float(value) > EXTENDED_GALAXY_ARCMIN:
                return True
        except (TypeError, ValueError):
            continue
    return False


def _galaxy_size_known(record: dict) -> bool:
    for key in (
        "major_axis_arcmin", "size_arcmin", "angular_size_arcmin", "diameter_arcmin",
        "major_axis", "size", "angular_size", "diameter",
    ):
        value = record.get(key)
        try:
            if value is not None and math.isfinite(float(value)) and float(value) > 0:
                return True
        except (TypeError, ValueError):
            continue
    return False


def classify_candidate(record: dict) -> dict:
    """Return a stable, explainable profile for one catalog record.

    The input is treated as read-only.  Catalog type names follow OpenNGC;
    callers may also provide explicit ``duplicate``/``extended`` hints.
    """
    if not isinstance(record, dict):
        return {
            "eligible": False, "category": "unknown", "priority": 0,
            "beginner": False, "minimum_block_seconds": IDEA_MIN_BLOCK_SECONDS,
            "reason": "Catalog record is invalid.",
        }
    object_type = record.get("type", record.get("object_type"))
    required = (record.get("name"), object_type, record.get("ra_deg"), record.get("dec_deg"))
    if not required[0] or not required[1]:
        reason = "Record incompleto: nome o tipo assente."
        return _profile(False, "unknown", 0, False, reason)
    try:
        coordinates_ok = all(math.isfinite(float(value)) for value in required[2:])
    except (TypeError, ValueError):
        coordinates_ok = False
    if not coordinates_ok:
        return _profile(False, "unknown", 0, False, "Incomplete record: coordinates are missing or invalid.")
    if record.get("duplicate") or record.get("is_duplicate") or record.get("duplicate_of"):
        return _profile(False, "duplicate", 0, False, "Record duplicato escluso dalle idee automatiche.")

    object_type = _normalise_type(object_type)
    beginner = _is_beginner(record)
    if object_type in _STELLAR_TYPES:
        return _profile(False, "stellar", 0, beginner, "Oggetto stellare escluso dalle idee DSO.")
    if object_type in _NEBULA_TYPES:
        # Emission/reflection are deliberately equal top tier.  Generic nebulae
        # remain useful when the local catalog has no richer classification.
        base = 100 if object_type in {"EMN", "HII", "RFN"} else 90
        return _profile(True, "nebula", base + (10 if beginner else 0), beginner, "Nebula suited to local DSO imaging.")
    if object_type in _CLUSTER_TYPES:
        return _profile(True, "cluster", 70 + (15 if beginner else 0), beginner, "Ammasso aperto o globulare catalogato.")
    if object_type in _GALAXY_TYPES:
        if not _galaxy_size_known(record):
            return _profile(False, "galaxy", 0, beginner, "Galaxy angular size is unavailable.")
        if _extended_galaxy(record):
            return _profile(False, "galaxy", 0, beginner, "Galassia chiaramente estesa esclusa dalle idee automatiche.")
        return _profile(True, "galaxy", 50 + (15 if beginner else 0), beginner, "Galassia compatta adatta alle idee automatiche.")
    if object_type in {"DRKN", "OTHER"}:
        return _profile(True, "other", 40 + (10 if beginner else 0), beginner, "Altro oggetto DSO catalogato.")
    return _profile(False, "unknown", 0, beginner, "Tipo di oggetto sconosciuto escluso dalle idee automatiche.")


def _profile(eligible: bool, category: str, priority: int, beginner: bool, reason: str) -> dict:
    return {
        "eligible": eligible,
        "category": category,
        "priority": priority,
        "beginner": beginner,
        "minimum_block_seconds": IDEA_MIN_BLOCK_SECONDS,
        "reason": reason,
    }
