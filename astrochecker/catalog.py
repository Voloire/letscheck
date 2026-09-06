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
            raise CatalogError(f"Catalogo locale non trovato: {self.path}")
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
            raise CatalogError(f"Catalogo locale non valido: {exc}") from exc

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
                    "message": "Catalogo locale pronto",
                }
        except CatalogError as exc:
            return {"ready": False, "version": "", "catalogs": [], "message": str(exc)}
        except sqlite3.Error as exc:
            return {
                "ready": False,
                "version": "",
                "catalogs": [],
                "message": f"Catalogo locale non valido: {exc}",
            }

    @staticmethod
    def _result(connection: sqlite3.Connection, row: sqlite3.Row) -> dict:
        aliases = [
            alias["display_name"]
            for alias in connection.execute(
                """
                SELECT display_name
                FROM aliases
                WHERE object_id = ?
                ORDER BY is_primary DESC, catalog, display_name
                """,
                (row["id"],),
            )
        ]
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
            "source": row["source"],
        }

    def resolve(self, query: str) -> dict:
        normalized = _normalize(query)
        if not normalized:
            raise ObjectNotFoundError("Indicare una sigla di catalogo")
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
                    raise ObjectNotFoundError(f"Oggetto non trovato nel catalogo locale: {query}")
                if len(rows) > 1:
                    candidates = []
                    for row in rows:
                        result = self._result(connection, row)
                        preferred = "M 101" if "M 101" in result["aliases"] else result["name"]
                        candidates.append(preferred)
                    raise AmbiguousObjectError(
                        f"{query} è una sigla ambigua; scegliere tra "
                        + " e ".join(candidates)
                    )
                return self._result(connection, rows[0])
        except sqlite3.Error as exc:
            raise CatalogError(f"Catalogo locale non valido: {exc}") from exc

    def search(self, query: str, limit: int = 10) -> list[dict]:
        normalized = _normalize(query)
        if not normalized:
            return []
        try:
            bounded_limit = max(1, min(int(limit), MAX_SEARCH_RESULTS))
        except (TypeError, ValueError) as exc:
            raise CatalogError("Il limite di ricerca deve essere un numero intero") from exc
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
                return [self._result(connection, row) for row in rows]
        except sqlite3.Error as exc:
            raise CatalogError(f"Catalogo locale non valido: {exc}") from exc

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
            raise CatalogError(f"Catalogo locale non valido: {exc}") from exc
