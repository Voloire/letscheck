"""Build data/catalog.sqlite3 from versioned local source snapshots.

This command is deliberately offline. Downloading or refreshing snapshots is a
separate, reviewed operation; runtime code only opens the resulting SQLite file.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import math
import os
import re
import sqlite3
from pathlib import Path

from astropy.coordinates import FK4, FK5, Galactic, ICRS, SkyCoord
from astropy.time import Time
import astropy.units as u


ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
DEFAULT_OUTPUT = ROOT / "data" / "catalog.sqlite3"
VERSION = "2026.09.06-1"
OPENNGC_COMMIT = "da90466031b0372c896588b85be6016c617e205b"
CATALOG_ORDER = ("messier", "ngc", "ic", "sh2", "vdb", "ldn")
CROSSWALK = RAW / "wikidata-crosswalk.json"

SNAPSHOTS = {
    "openngc-ngc.csv": {
        "source": "OpenNGC",
        "version": OPENNGC_COMMIT,
        "url": f"https://github.com/mattiaverga/OpenNGC/tree/{OPENNGC_COMMIT}",
        "license": "CC-BY-SA-4.0",
        "citation": "OpenNGC by Mattia Verga and contributors",
    },
    "openngc-addendum.csv": {
        "source": "OpenNGC",
        "version": OPENNGC_COMMIT,
        "url": f"https://github.com/mattiaverga/OpenNGC/tree/{OPENNGC_COMMIT}",
        "license": "CC-BY-SA-4.0",
        "citation": "OpenNGC by Mattia Verga and contributors",
    },
    "vizier-vii-20-catalog.dat.gz": {
        "source": "VizieR VII/20",
        "version": "CDS snapshot 1995-01-31",
        "url": "https://cdsarc.cds.unistra.fr/viz-bin/Cat?VII/20",
        "license": "No dataset-specific license stated in ReadMe",
        "citation": "Sharpless, 1959, ApJS 4, 257 (1959ApJS....4..257S)",
    },
    "vizier-vii-7a-ldn.dat": {
        "source": "VizieR VII/7A",
        "version": "CDS snapshot 1996-02-22",
        "url": "https://cdsarc.cds.unistra.fr/viz-bin/Cat?VII/7A",
        "license": "No dataset-specific license stated in ReadMe",
        "citation": "Lynds, 1962, ApJS 7, 1 (1962ApJS....7....1L)",
    },
    "vizier-vii-21-catalog.dat": {
        "source": "VizieR VII/21",
        "version": "corrected 2022-11-13",
        "url": "https://cdsarc.cds.unistra.fr/viz-bin/Cat?VII/21",
        "license": "No dataset-specific license stated in ReadMe",
        "citation": "van den Bergh, 1966, AJ 71, 990 (1966AJ.....71..990V)",
    },
    "vizier-j-aa-399-141-table1.dat": {
        "source": "VizieR J/A+A/399/141",
        "version": "CDS snapshot 2003-11-05",
        "url": "https://cdsarc.cds.unistra.fr/viz-bin/Cat?J/A+A/399/141",
        "license": "No dataset-specific license stated in ReadMe",
        "citation": "Magakian, 2003, A&A 399, 141 (2003A&A...399..141M)",
    },
}


SCHEMA = """
PRAGMA journal_mode = DELETE;
PRAGMA foreign_keys = ON;
CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE catalogs (
    id TEXT PRIMARY KEY,
    position INTEGER NOT NULL UNIQUE,
    object_count INTEGER NOT NULL
);
CREATE TABLE objects (
    id INTEGER PRIMARY KEY,
    canonical_key TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    ra_deg REAL NOT NULL CHECK(ra_deg >= 0 AND ra_deg < 360),
    dec_deg REAL NOT NULL CHECK(dec_deg >= -90 AND dec_deg <= 90),
    object_type TEXT NOT NULL,
    major_axis_arcmin REAL,
    minor_axis_arcmin REAL,
    visual_mag REAL,
    surface_brightness REAL,
    source TEXT NOT NULL,
    original_ra TEXT NOT NULL,
    original_dec TEXT NOT NULL,
    original_frame TEXT NOT NULL
);
CREATE TABLE aliases (
    object_id INTEGER NOT NULL REFERENCES objects(id),
    catalog TEXT NOT NULL,
    display_name TEXT NOT NULL,
    normalized TEXT NOT NULL,
    is_primary INTEGER NOT NULL DEFAULT 0 CHECK(is_primary IN (0, 1)),
    UNIQUE(object_id, normalized)
);
CREATE INDEX aliases_normalized_idx ON aliases(normalized);
CREATE TABLE target_groups (
    group_key TEXT PRIMARY KEY,
    wikidata_qid TEXT UNIQUE,
    source TEXT NOT NULL
);
CREATE TABLE target_group_members (
    group_key TEXT NOT NULL REFERENCES target_groups(group_key),
    object_id INTEGER NOT NULL REFERENCES objects(id),
    canonical_key TEXT NOT NULL,
    UNIQUE(group_key, object_id),
    UNIQUE(group_key, canonical_key)
);
CREATE TABLE target_names (
    group_key TEXT NOT NULL REFERENCES target_groups(group_key),
    display_name TEXT NOT NULL,
    normalized TEXT NOT NULL,
    language TEXT NOT NULL,
    source TEXT NOT NULL,
    priority INTEGER NOT NULL DEFAULT 0,
    UNIQUE(group_key, normalized)
);
CREATE INDEX target_names_normalized_idx ON target_names(normalized);
CREATE INDEX target_group_members_object_idx ON target_group_members(object_id);
"""


def normalize_designation(value: str) -> str:
    compact = re.sub(r"[^A-Z0-9]", "", value.upper())
    match = re.fullmatch(r"(SH2|NGC|IC|VDB|LDN|M)0*(\d+)([A-Z]*)", compact)
    if not match:
        return compact
    prefix, number, suffix = match.groups()
    return f"{prefix}{int(number)}{suffix}"


def display_designation(prefix: str, value: str | int) -> str:
    match = re.fullmatch(r"0*(\d+)(.*)", str(value).strip())
    if not match:
        raise ValueError(f"Invalid {prefix} designation: {value!r}")
    number, suffix = match.groups()
    suffix = suffix.strip()
    if prefix == "SH2":
        return f"Sh 2-{int(number)}{suffix.upper()}"
    if prefix == "VDB":
        return f"vdB {int(number)}{suffix.lower()}"
    separator = " " if suffix and not suffix.isalpha() else ""
    return f"{prefix} {int(number)}{separator}{suffix.upper()}"


def finite_coordinates(coord: SkyCoord) -> tuple[float, float]:
    icrs = coord.transform_to(ICRS())
    ra = float(icrs.ra.deg) % 360.0
    dec = float(icrs.dec.deg)
    if not (math.isfinite(ra) and math.isfinite(dec)):
        raise ValueError("non-finite transformed coordinates")
    return ra, dec


def sexagesimal_coordinate(ra_text: str, dec_text: str, frame) -> SkyCoord:
    """Parse source values numerically, including legal carry values such as 60s."""
    ra_parts = [float(part) for part in ra_text.split(":")]
    if len(ra_parts) == 2:
        ra_parts.append(0.0)
    dec_sign = -1 if dec_text.startswith("-") else 1
    dec_parts = [float(part) for part in dec_text.lstrip("+-").split(":")]
    if len(dec_parts) == 2:
        dec_parts.append(0.0)
    ra_deg = (ra_parts[0] + ra_parts[1] / 60 + ra_parts[2] / 3600) * 15
    dec_deg = dec_sign * (dec_parts[0] + dec_parts[1] / 60 + dec_parts[2] / 3600)
    return SkyCoord(ra=ra_deg * u.deg, dec=dec_deg * u.deg, frame=frame)


class Writer:
    def __init__(self, connection: sqlite3.Connection):
        self.connection = connection
        self.ids: dict[str, int] = {}

    def object(
        self,
        key: str,
        name: str,
        ra: float,
        dec: float,
        object_type: str,
        source: str,
        original_ra: str,
        original_dec: str,
        original_frame: str,
        major_axis_arcmin: float | None = None,
        minor_axis_arcmin: float | None = None,
        visual_mag: float | None = None,
        surface_brightness: float | None = None,
    ) -> int:
        cursor = self.connection.execute(
            """
            INSERT INTO objects(
                canonical_key, name, ra_deg, dec_deg, object_type,
                major_axis_arcmin, minor_axis_arcmin, visual_mag, surface_brightness, source,
                original_ra, original_dec, original_frame
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (key, name, ra, dec, object_type, major_axis_arcmin, minor_axis_arcmin,
             visual_mag, surface_brightness, source, original_ra, original_dec, original_frame),
        )
        object_id = int(cursor.lastrowid)
        self.ids[key] = object_id
        return object_id

    def alias(self, object_id: int, catalog: str, display: str, primary: bool = False) -> None:
        self.connection.execute(
            """
            INSERT OR IGNORE INTO aliases(object_id, catalog, display_name, normalized, is_primary)
            VALUES (?, ?, ?, ?, ?)
            """,
            (object_id, catalog, display, normalize_designation(display), int(primary)),
        )


def j2000_coordinates(ra: str, dec: str) -> tuple[float, float]:
    coord = sexagesimal_coordinate(ra, dec, FK5(equinox=Time("J2000")))
    return finite_coordinates(coord)


def split_numbers(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def split_common_names(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def optional_float(value: object) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def import_openngc(writer: Writer) -> dict[str, int]:
    rows = []
    with (RAW / "openngc-ngc.csv").open(encoding="utf-8", newline="") as source:
        rows.extend(csv.DictReader(source, delimiter=";"))
    with (RAW / "openngc-addendum.csv").open(encoding="utf-8", newline="") as source:
        addendum = list(csv.DictReader(source, delimiter=";"))

    primary_rows = [row for row in rows if row["Type"] not in {"Dup", "NonEx"}]
    for row in primary_rows:
        raw_name = row["Name"]
        prefix = "NGC" if raw_name.startswith("NGC") else "IC"
        name = display_designation(prefix, raw_name[len(prefix) :])
        ra, dec = j2000_coordinates(row["RA"], row["Dec"])
        object_id = writer.object(
            raw_name,
            name,
            ra,
            dec,
            row["Type"] or "Unknown",
            "OpenNGC",
            row["RA"],
            row["Dec"],
            "FK5 J2000",
            major_axis_arcmin=optional_float(row.get("MajAx")),
            minor_axis_arcmin=optional_float(row.get("MinAx")),
            visual_mag=optional_float(row.get("V-Mag")),
            surface_brightness=optional_float(row.get("SurfBr")),
        )
        writer.alias(object_id, prefix.lower(), name, primary=True)
        for number in split_numbers(row["M"]):
            writer.alias(object_id, "messier", display_designation("M", number))
        for alias_prefix in ("NGC", "IC"):
            for number in split_numbers(row[alias_prefix]):
                writer.alias(
                    object_id,
                    alias_prefix.lower(),
                    display_designation(alias_prefix, number),
                )
        # IC 434 carries a disputed Flame Nebula/Orion B label in this
        # snapshot; keep the catalogue designation without propagating it.
        if raw_name != "IC0434":
            for common_name in split_common_names(row.get("Common names", "")):
                writer.alias(object_id, "common", common_name)

    # OpenNGC duplicate rows carry the target designation in NGC or IC.
    unresolved = []
    for row in (row for row in rows if row["Type"] == "Dup"):
        target_keys = []
        for target_prefix in ("NGC", "IC"):
            target_keys.extend(target_prefix + value.zfill(4) for value in split_numbers(row[target_prefix]))
        target = next((writer.ids.get(key) for key in target_keys if key in writer.ids), None)
        if target is None:
            unresolved.append((row["Name"], target_keys))
            continue
        prefix = "NGC" if row["Name"].startswith("NGC") else "IC"
        writer.alias(target, prefix.lower(), display_designation(prefix, row["Name"][len(prefix) :]))
    if unresolved:
        raise ValueError(f"Unresolved OpenNGC duplicate targets: {unresolved[:5]}")

    # M40 and M45 are valid addendum objects rather than NGC/IC aliases.
    for messier_number, row in (
        (40, next(row for row in addendum if row["Name"] == "M040")),
        (45, next(row for row in addendum if row["M"] == "045")),
    ):
        name = display_designation("M", messier_number)
        ra, dec = j2000_coordinates(row["RA"], row["Dec"])
        object_id = writer.object(
            f"M{messier_number:03d}",
            name,
            ra,
            dec,
            row["Type"] or "Unknown",
            "OpenNGC addendum",
            row["RA"],
            row["Dec"],
            "FK5 J2000",
            major_axis_arcmin=optional_float(row.get("MajAx")),
            minor_axis_arcmin=optional_float(row.get("MinAx")),
            visual_mag=optional_float(row.get("V-Mag")),
            surface_brightness=optional_float(row.get("SurfBr")),
        )
        writer.alias(object_id, "messier", name, primary=True)

    # Historical identification is disputed. Preserve both serious candidates.
    m101 = writer.ids["NGC5457"]
    ngc5866 = writer.ids["NGC5866"]
    writer.alias(m101, "messier", "M 102")
    writer.alias(ngc5866, "messier", "M 102")
    return {
        "openngc_rows": len(rows),
        "openngc_addendum_rows": len(addendum),
        "openngc_duplicate_rows": sum(row["Type"] == "Dup" for row in rows),
        "openngc_nonexistent_rows": sum(row["Type"] == "NonEx" for row in rows),
    }


def import_sh2(writer: Writer) -> int:
    with gzip.open(RAW / "vizier-vii-20-catalog.dat.gz", "rt", encoding="ascii") as source:
        lines = source.read().splitlines()
    for line in lines:
        number = int(line[0:4])
        ra_text = f"{int(line[20:22]):02d}:{int(line[22:24]):02d}:{int(line[24:27]) / 10:04.1f}"
        dec_text = f"{line[27]}{int(line[28:30]):02d}:{int(line[30:32]):02d}:{int(line[32:34]):02d}"
        coord = sexagesimal_coordinate(ra_text, dec_text, FK4(equinox=Time("B1900")))
        ra, dec = finite_coordinates(coord)
        name = display_designation("SH2", number)
        object_id = writer.object(
            f"SH2-{number}",
            name,
            ra,
            dec,
            "HII",
            "Sharpless 1959 / VizieR VII/20",
            ra_text,
            dec_text,
            "FK4 B1900",
        )
        writer.alias(object_id, "sh2", name, primary=True)
    return len(lines)


def import_ldn(writer: Writer) -> tuple[int, int]:
    lines = (RAW / "vizier-vii-7a-ldn.dat").read_text(encoding="ascii").splitlines()
    imported = 0
    for line in lines:
        if not line[0:4].strip():
            continue
        number = int(line[0:4])
        ra_text = f"{int(line[5:7]):02d}:{float(line[8:12]):04.1f}"
        sign = line[15] if line[15] in "+-" else "+"
        dec_text = f"{sign}{int(line[16:18]):02d}:{int(line[19:21]):02d}"
        coord = sexagesimal_coordinate(ra_text, dec_text, FK4(equinox=Time("B1950")))
        ra, dec = finite_coordinates(coord)
        name = display_designation("LDN", number)
        object_id = writer.object(
            f"LDN-{number}",
            name,
            ra,
            dec,
            "DrkN",
            "Lynds 1962 / VizieR VII/7A",
            ra_text,
            dec_text,
            "FK4 B1950",
        )
        writer.alias(object_id, "ldn", name, primary=True)
        imported += 1
    return len(lines), imported


def magakian_vdb_coordinates() -> tuple[int, dict[int, list[tuple[str, str, str]]]]:
    matches: dict[int, list[tuple[str, str, str]]] = {}
    lines = (RAW / "vizier-j-aa-399-141-table1.dat").read_text(encoding="ascii").splitlines()
    for line in lines:
        cross_id = line[35:39].strip()
        match = re.match(r"(\d+)", cross_id)
        if not match:
            continue
        number = int(match.group(1))
        ra_text = f"{line[4:6]}:{line[7:9]}:{line[10:12]}"
        dec_text = f"{line[13]}{line[14:16]}:{line[17:19]}:{line[20:22]}"
        matches.setdefault(number, []).append((cross_id, ra_text, dec_text))
    return len(lines), matches


def import_vdb(writer: Writer) -> dict[str, int | list[int]]:
    magakian_rows_total, magakian = magakian_vdb_coordinates()
    lines = (RAW / "vizier-vii-21-catalog.dat").read_text(encoding="ascii").splitlines()
    galactic_fallbacks = []
    for line in lines:
        number = int(line[1:4])
        candidates = magakian.get(number, [])
        exact = next((candidate for candidate in candidates if candidate[0] == str(number)), None)
        selected = exact or (candidates[0] if len(candidates) == 1 else None)
        if selected:
            _cross_id, ra_text, dec_text = selected
            coord = sexagesimal_coordinate(ra_text, dec_text, FK5(equinox=Time("J2000")))
            original_frame = "FK5 J2000"
        else:
            lon_text = line[24:29].strip()
            lat_text = line[29:34].strip()
            coord = SkyCoord(l=float(lon_text) * u.deg, b=float(lat_text) * u.deg, frame=Galactic())
            ra_text, dec_text = lon_text, lat_text
            original_frame = "Galactic IAU"
            galactic_fallbacks.append(number)
        ra, dec = finite_coordinates(coord)
        name = display_designation("VDB", number)
        object_id = writer.object(
            f"VDB-{number}",
            name,
            ra,
            dec,
            "RfN",
            "van den Bergh 1966 / Magakian 2003 via VizieR",
            ra_text,
            dec_text,
            original_frame,
        )
        writer.alias(object_id, "vdb", name, primary=True)
    return {
        "vdb_rows": len(lines),
        "magakian_rows_total": magakian_rows_total,
        "magakian_vdb_crossid_rows": sum(len(values) for values in magakian.values()),
        "vdb_magakian_missing": [number for number in range(1, 159) if number not in magakian],
        "galactic_fallbacks": galactic_fallbacks,
    }


def import_wikidata_crosswalk(connection: sqlite3.Connection) -> dict[str, int]:
    """Import the reviewed, versioned CC0 cross-catalog name crosswalk."""
    payload = json.loads(CROSSWALK.read_text(encoding="utf-8"))
    groups = names = members = 0
    for group in payload.get("groups", []):
        group_key = str(group.get("group_key", "")).strip()
        if not group_key:
            continue
        matched: dict[int, str] = {}
        for identifier in group.get("identifiers", []):
            normalized = normalize_designation(str(identifier))
            row = connection.execute(
                """
                SELECT o.id, o.canonical_key
                FROM aliases AS a JOIN objects AS o ON o.id = a.object_id
                WHERE a.normalized = ?
                ORDER BY o.id
                LIMIT 1
                """,
                (normalized,),
            ).fetchone()
            if row:
                matched[int(row[0])] = str(row[1])
        clean_names = []
        for value in group.get("names", []):
            display = " ".join(str(value).split()).strip()
            if display:
                clean_names.append(display)
        if not matched or not clean_names:
            continue
        connection.execute(
            "INSERT OR IGNORE INTO target_groups(group_key, wikidata_qid, source) VALUES (?, ?, ?)",
            (group_key, group.get("wikidata_qid"), payload.get("source", "Wikidata")),
        )
        for object_id, canonical_key in matched.items():
            connection.execute(
                "INSERT OR IGNORE INTO target_group_members(group_key, object_id, canonical_key) VALUES (?, ?, ?)",
                (group_key, object_id, canonical_key),
            )
            members += 1
        for priority, display in enumerate(dict.fromkeys(clean_names)):
            connection.execute(
                """
                INSERT OR IGNORE INTO target_names(
                    group_key, display_name, normalized, language, source, priority
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (group_key, display, normalize_designation(display), "en", payload.get("source", "Wikidata"), priority),
            )
            names += 1
        groups += 1
    return {"crosswalk_groups": groups, "crosswalk_members": members, "crosswalk_names": names}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def build(output: Path) -> dict:
    missing = [name for name in SNAPSHOTS if not (RAW / name).is_file()]
    if not CROSSWALK.is_file():
        missing.append(CROSSWALK.name)
    if missing:
        raise SystemExit("Missing local snapshots: " + ", ".join(missing))
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".building")
    temporary.unlink(missing_ok=True)
    connection = sqlite3.connect(temporary)
    try:
        connection.executescript(SCHEMA)
        writer = Writer(connection)
        stats: dict[str, object] = {}
        stats.update(import_openngc(writer))
        stats["sh2_rows"] = import_sh2(writer)
        ldn_rows, ldn_imported = import_ldn(writer)
        stats.update({"ldn_rows": ldn_rows, "ldn_imported": ldn_imported})
        stats.update(import_vdb(writer))
        stats.update(import_wikidata_crosswalk(connection))

        for position, catalog_id in enumerate(CATALOG_ORDER):
            count = connection.execute(
                "SELECT count(DISTINCT normalized) FROM aliases WHERE catalog = ?",
                (catalog_id,),
            ).fetchone()[0]
            connection.execute(
                "INSERT INTO catalogs(id, position, object_count) VALUES (?, ?, ?)",
                (catalog_id, position, count),
            )

        source_metadata = {
            name: details | {"sha256": sha256(RAW / name)}
            for name, details in SNAPSHOTS.items()
        }
        crosswalk_payload = json.loads(CROSSWALK.read_text(encoding="utf-8"))
        source_metadata[CROSSWALK.name] = {
            "source": "Wikidata structured data plus project supplement",
            "version": crosswalk_payload.get("retrieved", "unknown"),
            "url": "https://www.wikidata.org/wiki/Wikidata:Licensing",
            "license": "CC0-1.0",
            "citation": "Wikidata entities and labels; project-maintained crosswalk",
            "sha256": sha256(CROSSWALK),
        }
        metadata = {
            "version": VERSION,
            "sources": json.dumps(source_metadata, ensure_ascii=False, sort_keys=True),
            "build_stats": json.dumps(stats, ensure_ascii=False, sort_keys=True),
        }
        connection.executemany("INSERT INTO metadata(key, value) VALUES (?, ?)", metadata.items())
        connection.execute("PRAGMA optimize")
        connection.commit()
        integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity != "ok":
            raise RuntimeError(f"SQLite integrity check failed: {integrity}")
    except BaseException:
        connection.close()
        temporary.unlink(missing_ok=True)
        raise
    connection.close()
    os.replace(temporary, output)
    return stats


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    stats = build(args.output.resolve())
    print(json.dumps({"output": str(args.output.resolve()), "version": VERSION, **stats}, indent=2))


if __name__ == "__main__":
    main()
