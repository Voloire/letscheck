import xml.etree.ElementTree as ET

import pytest

from astrochecker.nina import (
    NinaSequenceError,
    build_legacy_sequence_set_xml,
    build_legacy_sequence_xml,
    export_legacy_sequence,
    export_legacy_sequence_set,
)


TARGET = {
    "name": "M 42",
    "ra": 83.82208,
    "dec": -5.39111,
}

TARGET_2 = {
    "name": "M 31",
    "ra": 10.6847,
    "dec": 41.269,
}


def test_build_legacy_sequence_set_xml_uses_ninas_native_target_set_shape():
    xml = build_legacy_sequence_set_xml([
        {"target": TARGET, "duration_seconds": 901},
        {"target": TARGET_2, "duration_seconds": 1200},
    ])

    root = ET.fromstring(xml)
    assert root.tag == "ArrayOfCaptureSequenceList"
    targets = root.findall("CaptureSequenceList")
    assert [item.attrib["TargetName"] for item in targets] == ["M 42", "M 31"]
    assert [item.findtext("CaptureSequence/TotalExposureCount") for item in targets] == ["3", "4"]


def test_export_legacy_sequence_set_uses_the_sequence_name_for_the_file(tmp_path):
    result = export_legacy_sequence_set(
        [{"target": TARGET, "duration_seconds": 901}],
        sequence_name="Rome night plan",
        downloads_dir=tmp_path,
        filename_timestamp="20260906-130215",
    )

    assert result["filename"] == "Rome-night-plan_20260906-130215.xml"
    root = ET.parse(result["path"]).getroot()
    assert root.tag == "ArrayOfCaptureSequenceList"
    assert root.find("CaptureSequenceList").attrib["TargetName"] == "M 42"


def test_build_legacy_sequence_xml_matches_nina_capture_sequence_shape():
    xml = build_legacy_sequence_xml(TARGET, duration_seconds=2 * 3600)

    root = ET.fromstring(xml)
    assert root.tag == "CaptureSequenceList"
    assert root.attrib["TargetName"] == "M 42"
    assert root.attrib["Mode"] == "STANDARD"
    assert root.attrib["NegativeDec"] == "True"
    assert root.attrib["RAHours"] == "5"
    assert root.attrib["DecDegrees"] == "-5"

    coordinates = root.find("Coordinates")
    assert coordinates is not None
    assert coordinates.findtext("Epoch") == "J2000"
    assert float(coordinates.findtext("RA")) == pytest.approx(83.82208 / 15)
    assert float(coordinates.findtext("Dec")) == pytest.approx(-5.39111)

    capture = root.find("CaptureSequence")
    assert capture is not None
    assert capture.findtext("Enabled") == "true"
    assert capture.findtext("ExposureTime") == "300"
    assert capture.findtext("ImageType") == "LIGHT"
    assert capture.findtext("TotalExposureCount") == "24"
    assert capture.findtext("ProgressExposureCount") == "0"
    assert capture.findtext("Gain") == "-1"
    assert capture.findtext("Offset") == "-1"
    assert capture.findtext("Dither") == "false"
    assert capture.findtext("DitherAmount") == "1"
    assert capture.find("Binning/X").text == "1"
    assert capture.find("Binning/Y").text == "1"


def test_export_legacy_sequence_writes_to_requested_download_directory(tmp_path):
    result = export_legacy_sequence(
        TARGET,
        duration_seconds=901,
        downloads_dir=tmp_path,
        filename_timestamp="20260906-130215",
    )

    assert result["path"] == str(tmp_path / "AstroChecker_M-42_20260906-130215.xml")
    assert result["exposure_seconds"] == 300
    assert result["exposure_count"] == 3
    assert (tmp_path / "AstroChecker_M-42_20260906-130215.xml").is_file()


def test_export_legacy_sequence_uses_a_user_supplied_safe_sequence_name(tmp_path):
    result = export_legacy_sequence(
        TARGET,
        duration_seconds=901,
        sequence_name="M 42 / balcony: night?",
        downloads_dir=tmp_path,
        filename_timestamp="20260906-130215",
    )

    assert result["filename"] == "M-42-balcony-night_20260906-130215.xml"
    assert (tmp_path / result["filename"]).is_file()


def test_legacy_sequence_rejects_a_window_shorter_than_one_default_exposure():
    with pytest.raises(NinaSequenceError, match="at least 300 seconds"):
        build_legacy_sequence_xml(TARGET, duration_seconds=299)
