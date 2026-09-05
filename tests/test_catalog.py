import math
import json
import sqlite3
import gc
import warnings

import pytest

from astrochecker.catalog import (
    DEFAULT_CATALOG_PATH,
    AmbiguousObjectError,
    Catalog,
    ObjectNotFoundError,
)


def test_missing_database_is_reported_without_creating_an_empty_file(tmp_path):
    path = tmp_path / "missing.sqlite3"

    status = Catalog(path).status()

    assert status["ready"] is False
    assert "non trovato" in status["message"].lower()
    assert not path.exists()


def test_corrupt_database_is_reported_as_unavailable(tmp_path):
    path = tmp_path / "catalog.sqlite3"
    path.write_bytes(b"not a sqlite database")

    status = Catalog(path).status()

    assert status["ready"] is False
    assert "non valido" in status["message"].lower()


def test_default_catalog_is_ready_and_declares_all_six_dso_catalogs():
    assert DEFAULT_CATALOG_PATH.name == "catalog.sqlite3"
    status = Catalog().status()

    assert status["ready"] is True
    assert status["version"]
    assert [item["id"] for item in status["catalogs"]] == [
        "messier",
        "ngc",
        "ic",
        "sh2",
        "vdb",
        "ldn",
    ]
    assert all(item["count"] > 0 for item in status["catalogs"])


def test_catalog_censuses_match_the_versioned_source_snapshots():
    assert Catalog().status()["catalogs"] == [
        {"id": "messier", "count": 110},
        {"id": "ngc", "count": 8440},
        {"id": "ic", "count": 5594},
        {"id": "sh2", "count": 313},
        {"id": "vdb", "count": 158},
        {"id": "ldn", "count": 1787},
    ]


@pytest.mark.parametrize("query", ["M13", "m 13", "  m   13  "])
def test_messier_alias_normalization_resolves_to_ngc_6205(query):
    result = Catalog().resolve(query)

    assert result["name"] == "NGC 6205"
    assert "M 13" in result["aliases"]
    assert result["ra_deg"] == pytest.approx(250.42346, abs=0.00003)
    assert result["dec_deg"] == pytest.approx(36.46131, abs=0.00003)


def test_common_name_alias_resolves_and_is_searchable():
    catalog = Catalog()

    result = catalog.resolve("Andromeda Galaxy")

    assert result["name"] == "NGC 224"
    assert "Andromeda Galaxy" in result["aliases"]
    assert catalog.search("andromeda galaxy")[0]["name"] == "NGC 224"


@pytest.mark.parametrize(
    ("query", "name"),
    [
        ("NGC7000", "NGC 7000"),
        ("ngc 7000", "NGC 7000"),
        ("IC434", "IC 434"),
        ("i c 0434", "IC 434"),
        ("Sh2-155", "Sh 2-155"),
        ("sh 2 155", "Sh 2-155"),
        ("VDB 1", "vdB 1"),
        ("v d b001", "vdB 1"),
        ("LDN1", "LDN 1"),
        ("ldn 0001", "LDN 1"),
    ],
)
def test_supported_designations_ignore_case_spacing_and_leading_zeroes(query, name):
    assert Catalog().resolve(query)["name"] == name


def test_m102_is_explicitly_ambiguous_instead_of_silently_picking_a_galaxy():
    with pytest.raises(AmbiguousObjectError) as caught:
        Catalog().resolve("M 102")

    message = str(caught.value)
    assert "M 101" in message
    assert "NGC 5866" in message


def test_unknown_and_sql_injection_shaped_queries_are_not_found():
    catalog = Catalog()
    with pytest.raises(ObjectNotFoundError):
        catalog.resolve("object that is not in any catalog")
    with pytest.raises(ObjectNotFoundError):
        catalog.resolve("M 13' OR 1=1 --")
    assert catalog.status()["ready"] is True


def test_search_ranks_exact_alias_before_prefix_matches_and_bounds_limit():
    catalog = Catalog()

    results = catalog.search("NGC 7", limit=2)

    assert len(results) == 2
    assert results[0]["name"] == "NGC 7"
    assert catalog.search("NGC", limit=100_000)
    assert len(catalog.search("NGC", limit=100_000)) <= 100


@pytest.mark.parametrize(
    ("query", "expected_name"),
    [
        ("M 1", "NGC 1952"),
        ("M 110", "NGC 205"),
        ("NGC 1", "NGC 1"),
        ("NGC 7840", "NGC 7840"),
        ("IC 1", "IC 1"),
        ("IC 5386", "NGC 7832"),
        ("Sh 2-1", "Sh 2-1"),
        ("Sh 2-313", "Sh 2-313"),
        ("vdB 1", "vdB 1"),
        ("vdB 158", "vdB 158"),
        ("LDN 1", "LDN 1"),
        ("LDN 1802", "LDN 1802"),
    ],
)
def test_each_catalog_includes_low_and_high_designations(query, expected_name):
    result = Catalog().resolve(query)

    assert result["name"] == expected_name
    assert query.replace("Sh 2", "Sh 2").replace("VDB", "vdB") in result["aliases"]
    assert math.isfinite(result["ra_deg"])
    assert math.isfinite(result["dec_deg"])
    assert result["frame"] == "icrs"
    assert result["source"]


def test_all_included_coordinates_are_finite_and_in_icrs_ranges():
    connection = sqlite3.connect(DEFAULT_CATALOG_PATH)
    try:
        total, invalid = connection.execute(
            """
            SELECT count(*), sum(
                ra_deg IS NULL OR dec_deg IS NULL
                OR ra_deg < 0 OR ra_deg >= 360
                OR dec_deg < -90 OR dec_deg > 90
            )
            FROM objects
            """
        ).fetchone()
    finally:
        connection.close()

    assert total > 10_000
    assert invalid == 0


@pytest.mark.parametrize(
    ("query", "ra_deg", "dec_deg"),
    [
        ("Sh 2-155", 344.18240, 62.61771),  # FK4 B1900 source position
        ("LDN 1251", 339.01307, 75.25963),  # FK4 B1950 source position
        ("vdB 152", 333.35415, 70.25111),  # Magakian FK5 J2000 cross-id
        ("vdB 127", 296.87961, 18.55454),  # VII/21 Galactic fallback
    ],
)
def test_legacy_source_frames_are_transformed_to_checked_icrs_positions(
    query, ra_deg, dec_deg
):
    result = Catalog().resolve(query)
    assert result["ra_deg"] == pytest.approx(ra_deg, abs=0.00002)
    assert result["dec_deg"] == pytest.approx(dec_deg, abs=0.00002)


def test_build_metadata_accounts_for_source_exclusions_and_vdb_fallbacks():
    connection = sqlite3.connect(DEFAULT_CATALOG_PATH)
    try:
        stats = json.loads(
            connection.execute(
                "SELECT value FROM metadata WHERE key = 'build_stats'"
            ).fetchone()[0]
        )
    finally:
        connection.close()

    assert stats["openngc_duplicate_rows"] == 651
    assert stats["openngc_nonexistent_rows"] == 10
    assert stats["ldn_rows"] == 1791
    assert stats["ldn_imported"] == 1787
    assert stats["magakian_rows_total"] == 913
    assert stats["magakian_vdb_crossid_rows"] == 163
    assert stats["vdb_magakian_missing"] == [127]
    assert stats["galactic_fallbacks"] == [64, 90, 127]


def test_runtime_resolution_does_not_need_network(monkeypatch):
    def network_forbidden(*_args, **_kwargs):
        raise AssertionError("runtime network access")

    monkeypatch.setattr("socket.create_connection", network_forbidden)

    assert Catalog().resolve("M31")["name"] == "NGC 224"


def test_repeated_queries_close_sqlite_connections_cleanly():
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", ResourceWarning)
        catalog = Catalog()
        for _ in range(3):
            catalog.status()
            catalog.resolve("M 13")
            catalog.search("NGC 7")
        gc.collect()

    assert not [warning for warning in caught if warning.category is ResourceWarning]
