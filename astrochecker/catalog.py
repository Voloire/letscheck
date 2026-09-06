"""Read-only access to the bundled deep-sky object catalog."""

from __future__ import annotations

import re
import sqlite3
from contextlib import closing
from pathlib import Path


DEFAULT_CATALOG_PATH = Path(__file__).resolve().parent.parent / "data" / "catalog.sqlite3"
MAX_SEARCH_RESULTS = 100


class CatalogError(Exception):
    """Base class for catalog failures that can be shown to the user."""


class ObjectNotFoundError(CatalogError):
    """Raised when a designation is absent from the local catalog."""


class AmbiguousObjectError(CatalogError):
    """Raised when a designation intentionally maps to several candidates."""


def _normalize(query: str) -> str:
    compact = re.sub(r"[^A-Z0-9]", "", str(query).upper())
    match = re.fullmatch(r"(SH2|NGC|IC|VDB|LDN|M)0*(\d+)([A-Z]*)", compact)
    if match:
        prefix, number, suffix = match.groups()
        return f"{prefix}{int(number)}{suffix}"
    return compact


class Catalog:
    def __init__(self, path: str | Path | None = None):
        self.path = Path(path) if path is not None else DEFAULT_CATALOG_PATH

    def _connect(self) -> sqlite3.Connection:
        if not self.path.is_file():
            raise CatalogError(f"Local catalog not found: {self.path}")
        uri = self.path.resolve().as_uri() + "?mode=ro"
        connection = None
        try:
            connection = sqlite3.connect(uri, uri=True)
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA query_only = ON")
            return connection
        except sqlite3.Error as exc:
            if connection is not None:
                connection.close()
            raise CatalogError(f"Local catalog is invalid: {exc}") from exc

    def status(self) -> dict:
        try:
            with closing(self._connect()) as connection:
                version_row = connection.execute(
                    "SELECT value FROM metadata WHERE key = ?", ("version",)
                ).fetchone()
                if version_row is None:
                    raise sqlite3.DatabaseError("versione del catalogo assente")
                catalogs = [
                    {"id": row["id"], "count": row["object_count"]}
                    for row in connection.execute(
                        "SELECT id, object_count FROM catalogs ORDER BY position"
                    )
                ]
                if not catalogs:
                    raise sqlite3.DatabaseError("censimenti del catalogo assenti")
                return {
                    "ready": True,
                    "version": version_row["value"],
                    "catalogs": catalogs,
                    "message": "Local catalog ready.",
                }
        except CatalogError as exc:
            return {"ready": False, "version": "", "catalogs": [], "message": str(exc)}
        except sqlite3.Error as exc:
            return {
                "ready": False,
                "version": "",
                "catalogs": [],
                "message": f"Local catalog is invalid: {exc}",
            }

    @staticmethod
    def _group_for_object(connection: sqlite3.Connection, object_id: int) -> str | None:
        row = connection.execute(
            "SELECT group_key FROM target_group_members WHERE object_id = ? ORDER BY group_key LIMIT 1",
            (object_id,),
        ).fetchone()
        return str(row[0]) if row else None

    @classmethod
    def _group_payload(cls, connection: sqlite3.Connection, group_key: str | None, object_id: int) -> tuple[list[str], list[str], str | None]:
        if not group_key:
            rows = connection.execute(
                "SELECT display_name, catalog FROM aliases WHERE object_id = ? ORDER BY is_primary DESC, catalog, display_name",
                (object_id,),
            ).fetchall()
            return [], [str(row[0]) for row in rows if row[1] != "common"], None
        names = [str(row[0]) for row in connection.execute(
            "SELECT display_name FROM target_names WHERE group_key = ? ORDER BY priority, display_name", (group_key,)
        )]
        related = [str(row[0]) for row in connection.execute(
            """
            SELECT DISTINCT a.display_name
            FROM target_group_members AS m JOIN aliases AS a ON a.object_id = m.object_id
            WHERE m.group_key = ? AND a.catalog != 'common'
            ORDER BY a.display_name
            """, (group_key,)
        )]
        return names, related, group_key

    @classmethod
    def _representative_row(cls, connection: sqlite3.Connection, group_key: str) -> sqlite3.Row:
        return connection.execute(
            """
            SELECT o.*
            FROM target_group_members AS m JOIN objects AS o ON o.id = m.object_id
            WHERE m.group_key = ?
            ORDER BY (o.major_axis_arcmin IS NOT NULL) DESC,
                     (o.visual_mag IS NOT NULL) DESC,
                     (o.source = 'OpenNGC') DESC, o.name, o.id
            LIMIT 1
            """, (group_key,)
        ).fetchone()

    @classmethod
    def _result(cls, connection: sqlite3.Connection, row: sqlite3.Row) -> dict:
        aliases = [
            alias["display_name"]
            for alias in connection.execute(
                """
                SELECT display_name
                FROM aliases
                WHERE object_id = ?
                ORDER BY is_primary DESC, catalog, display_name
                """, (row["id"],)
            )
        ]
        group_key = cls._group_for_object(connection, int(row["id"]))
        common_names, related_ids, group_key = cls._group_payload(connection, group_key, int(row["id"]))
        common_names = list(dict.fromkeys(common_names + [
            str(alias[0]) for alias in connection.execute(
                "SELECT display_name FROM aliases WHERE object_id = ? AND catalog = 'common' ORDER BY display_name",
                (row["id"],),
            )
        ]))
        aliases = list(dict.fromkeys(aliases + common_names))
        return {
            "name": row["name"],
            "ra_deg": row["ra_deg"],
            "dec_deg": row["dec_deg"],
            "frame": "icrs",
            "type": row["object_type"],
            "major_axis_arcmin": row["major_axis_arcmin"],
            "minor_axis_arcmin": row["minor_axis_arcmin"],
            "visual_mag": row["visual_mag"],
            "surface_brightness": row["surface_brightness"],
            "aliases": aliases,
            "common_names": common_names,
            "target_group": group_key,
            "related_ids": related_ids,
            "source": row["source"],
        }

    def resolve(self, query: str) -> dict:
        normalized = _normalize(query)
        if not normalized:
            raise ObjectNotFoundError("Enter a catalog designation.")
        try:
            with closing(self._connect()) as connection:
                rows = connection.execute(
                    """
                    SELECT DISTINCT o.*
                    FROM aliases AS a
                    JOIN objects AS o ON o.id = a.object_id
                    WHERE a.normalized = ?
                    ORDER BY o.name
                    """,
                    (normalized,),
                ).fetchall()
                if not rows:
                    groups = connection.execute(
                        """
                        SELECT n.group_key, count(m.object_id) AS member_count
                        FROM target_names AS n
                        LEFT JOIN target_group_members AS m ON m.group_key = n.group_key
                        WHERE n.normalized LIKE ?
                        GROUP BY n.group_key
                        ORDER BY member_count DESC, n.group_key
                        """, (normalized + "%",),
                    ).fetchall()
                    if groups:
                        if len(groups) > 1 and groups[0][1] == groups[1][1]:
                            raise AmbiguousObjectError(f"{query} matches several targets; use a catalog ID.")
                        representative = self._representative_row(connection, str(groups[0][0]))
                        if representative:
                            return self._result(connection, representative)
                    raise ObjectNotFoundError(f"Target not found in the local catalog: {query}")
                if len(rows) > 1:
                    candidates = []
                    for row in rows:
                        result = self._result(connection, row)
                        preferred = "M 101" if "M 101" in result["aliases"] else result["name"]
                        candidates.append(preferred)
                    raise AmbiguousObjectError(
                        f"{query} is ambiguous; choose between "
                        + " e ".join(candidates)
                    )
                return self._result(connection, rows[0])
        except sqlite3.Error as exc:
            raise CatalogError(f"Local catalog is invalid: {exc}") from exc

    def search(self, query: str, limit: int = 10) -> list[dict]:
        normalized = _normalize(query)
        if not normalized:
            return []
        try:
            bounded_limit = max(1, min(int(limit), MAX_SEARCH_RESULTS))
        except (TypeError, ValueError) as exc:
            raise CatalogError("The search limit must be an integer.") from exc
        try:
            with closing(self._connect()) as connection:
                rows = connection.execute(
                    """
                    SELECT o.*, max(a.normalized = ?) AS exact_match,
                           min(length(a.normalized)) AS alias_length
                    FROM aliases AS a
                    JOIN objects AS o ON o.id = a.object_id
                    WHERE a.normalized LIKE ?
                    GROUP BY o.id
                    ORDER BY exact_match DESC, alias_length, o.name
                    LIMIT ?
                    """,
                    (normalized, normalized + "%", bounded_limit),
                ).fetchall()
                results = [self._result(connection, row) for row in rows]
                seen = {item["target_group"] for item in results if item["target_group"]}
                name_rows = connection.execute(
                    """
                    SELECT group_key FROM (
                        SELECT n.group_key, n.normalized,
                               count(m.object_id) AS member_count,
                               row_number() OVER (
                                   PARTITION BY n.normalized
                                   ORDER BY count(m.object_id) DESC, n.group_key
                               ) AS rank
                        FROM target_names AS n
                        LEFT JOIN target_group_members AS m ON m.group_key = n.group_key
                        WHERE n.normalized LIKE ?
                        GROUP BY n.group_key, n.normalized
                    ) WHERE rank = 1
                    ORDER BY member_count DESC, group_key
                    LIMIT ?
                    """, (normalized + "%", bounded_limit),
                ).fetchall()
                for group_row in name_rows:
                    group_key = str(group_row[0])
                    if group_key in seen:
                        continue
                    representative = self._representative_row(connection, group_key)
                    if representative:
                        results.append(self._result(connection, representative))
                        seen.add(group_key)
                return results[:bounded_limit]
        except sqlite3.Error as exc:
            raise CatalogError(f"Local catalog is invalid: {exc}") from exc

    def idea_candidates(self, *, include_ineligible: bool = False) -> list[dict]:
        """Return deterministic catalog records annotated for the ideas planner."""
        from .idea_profiles import classify_candidate

        try:
            with closing(self._connect()) as connection:
                rows = connection.execute("SELECT * FROM objects ORDER BY name, id").fetchall()
                candidates = []
                for row in rows:
                    result = self._result(connection, row)
                    result["id"] = row["id"]
                    result["canonical_key"] = row["canonical_key"]
                    profile = classify_candidate(result)
                    result["profile"] = profile
                    result["eligible"] = profile["eligible"]
                    if include_ineligible or profile["eligible"]:
                        candidates.append(result)
                candidates.sort(
                    key=lambda item: (
                        -int(item["profile"]["priority"]),
                        item["name"].casefold(),
                        item["canonical_key"],
                    )
                )
                return candidates
        except sqlite3.Error as exc:
            raise CatalogError(f"Local catalog is invalid: {exc}") from exc
