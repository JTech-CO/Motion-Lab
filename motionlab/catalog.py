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
        return json.loads(row["payload"]) if row else None

    def stats(self):
        with closing(self.connection()) as conn:
            row = conn.execute("SELECT value FROM metadata WHERE key = ?", ("stats",)).fetchone()
        return json.loads(row[0]) if row else {}

    def export(self):
        with closing(self.connection()) as conn:
            rows = conn.execute("SELECT payload FROM items WHERE access = ? ORDER BY id", ("public",)).fetchall()
        return [json.loads(row[0]) for row in rows]
