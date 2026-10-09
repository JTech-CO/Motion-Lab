"""SQLite search with FTS5 and bound parameters, never writable at runtime."""

import json
from contextlib import closing
from pathlib import Path
import re
import sqlite3

from .validation import validate_id, validate_search
from .analysis_schema import ANALYSIS_FILTERS


class CatalogUnavailable(RuntimeError):
    pass


class Catalog:
    def __init__(self, root=None):
        self.root = Path(root or Path(__file__).resolve().parent.parent).resolve()
        self.database = self.root / "data" / "motionlab.sqlite"

    def connection(self):
        if not self.database.is_file():
            raise CatalogUnavailable("Catalog unavailable. Run python scripts/build.py first.")
        connection = sqlite3.connect(self.database.as_uri() + "?mode=ro", uri=True)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA query_only = ON")
        return connection

    def search(self, **arguments):
        args = validate_search(arguments)
        # Quote each literal word: callers cannot supply FTS operators or column syntax.
        words = re.findall(r"\w+", args["query"], re.UNICODE)[:32]
        match = " AND ".join('"' + word.replace('"', '""') + '"*' for word in words)
        if args["query"] and not words:
            return {"items": [], "total": 0, "limit": args["limit"], "offset": args["offset"]}
        values = ["public", args["category"], args["category"], args["license"], args["license"],
                  args["kind"], args["kind"]]
        # The clause is constant SQL. Both facet names and values use bindings.
        facet_clause = ""
        for field in ANALYSIS_FILTERS:
            if args[field]:
                facet_clause += " AND EXISTS (SELECT 1 FROM facets WHERE facets.item_id = items.id AND facets.field = ? AND facets.value = ?)"
                values.extend((field, args[field]))
        with closing(self.connection()) as conn:
            if match:
                total = conn.execute("""
                    SELECT COUNT(*) FROM items JOIN item_search ON items.rowid = item_search.rowid
                    WHERE items.access = ? AND (? = '' OR items.category = ?)
                    AND (? = '' OR items.license = ?) AND (? = '' OR items.kind = ?)
                """ + facet_clause + " AND item_search MATCH ?", values + [match]).fetchone()[0]
                rows = conn.execute("""
                    SELECT items.payload FROM items JOIN item_search ON items.rowid = item_search.rowid
                    WHERE items.access = ? AND (? = '' OR items.category = ?)
                    AND (? = '' OR items.license = ?) AND (? = '' OR items.kind = ?)
                """ + facet_clause + " AND item_search MATCH ? ORDER BY bm25(item_search), items.title COLLATE NOCASE, items.id LIMIT ? OFFSET ?",
                    values + [match, args["limit"], args["offset"]]).fetchall()
            else:
                total = conn.execute("""
                    SELECT COUNT(*) FROM items WHERE access = ? AND (? = '' OR category = ?)
                    AND (? = '' OR license = ?) AND (? = '' OR kind = ?)
                """ + facet_clause, values).fetchone()[0]
                rows = conn.execute("""
                    SELECT payload FROM items WHERE access = ? AND (? = '' OR category = ?)
                    AND (? = '' OR license = ?) AND (? = '' OR kind = ?)
                """ + facet_clause + " ORDER BY title COLLATE NOCASE, id LIMIT ? OFFSET ?",
                    values + [args["limit"], args["offset"]]).fetchall()
        return {"items": [json.loads(row["payload"]) for row in rows], "total": total,
                "limit": args["limit"], "offset": args["offset"]}

    def get(self, item_id):
        item_id = validate_id(item_id)
        with closing(self.connection()) as conn:
            row = conn.execute("SELECT payload FROM items WHERE id = ? AND access = ?",
                               (item_id, "public")).fetchone()
            if row:
                return json.loads(row["payload"])
            # Older local databases have no alias table. Do not hide other SQL
            # errors, and never follow an alias recursively to another alias.
            if not conn.execute("SELECT 1 FROM sqlite_master WHERE type = ? AND name = ?",
                                ("table", "aliases")).fetchone():
                return None
            alias = conn.execute("""
                SELECT aliases.item_id, aliases.variant_id, items.payload
                FROM aliases JOIN items ON items.id = aliases.item_id
                WHERE aliases.alias = ? AND items.access = ?
            """, (item_id, "public")).fetchone()
        if alias is None:
            return None
        parent = json.loads(alias["payload"])
        variants = parent.get("variants") if isinstance(parent, dict) else None
        if (alias["variant_id"] != item_id or alias["item_id"] == item_id
                or not isinstance(parent, dict) or parent.get("id") != alias["item_id"]
                or not isinstance(variants, list)):
            raise CatalogUnavailable("Catalog alias data is inconsistent. Rebuild the catalog.")
        matches = [variant for variant in variants
                   if isinstance(variant, dict) and variant.get("id") == item_id]
        if len(matches) != 1 or matches[0].get("access") != "public":
            raise CatalogUnavailable("Catalog alias data is inconsistent. Rebuild the catalog.")
        # Keep the original ID, code, colors, license and provenance. In
        # particular, an old ID must not silently return its parent's code.
        result = {**matches[0], "canonicalId": alias["item_id"]}
        consolidation = parent.get("consolidation", {})
        roles = consolidation.get("variantRoles", {}) if isinstance(consolidation, dict) else {}
        role = roles.get(item_id) if isinstance(roles, dict) else None
        if role in ("component-part", "exact-source", "motion-variant", "palette-variant"):
            result["variantRole"] = role
        return result

    def stats(self):
        with closing(self.connection()) as conn:
            row = conn.execute("SELECT value FROM metadata WHERE key = ?", ("stats",)).fetchone()
        return json.loads(row[0]) if row else {}

    def export(self):
        with closing(self.connection()) as conn:
            rows = conn.execute("SELECT payload FROM items WHERE access = ? ORDER BY id", ("public",)).fetchall()
        return [json.loads(row[0]) for row in rows]
