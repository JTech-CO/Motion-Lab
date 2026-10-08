"""Verify expanded source records across full JSON, compact JSON and read-only SQLite."""

import argparse
from collections import Counter
from contextlib import closing
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from motionlab.catalog import Catalog  # noqa: E402
from scripts.build import read_json, validate_item  # noqa: E402


def verify(root=ROOT, minimum=5000):
    if not isinstance(minimum, int) or not 1 <= minimum <= 100_000:
        raise ValueError("Minimum must be between 1 and 100000")
    root = Path(root).resolve()
    full = read_json(root / "data/catalog.json", {})
    published = read_json(root / "dist/catalog.json", {})
    if full != published:
        raise ValueError("Local and web full catalogs differ")
    entries = full["items"]
    by_id = {entry["id"]: entry for entry in entries}
    if len(entries) < minimum or len(entries) != len(by_id) or full["stats"]["total"] != len(entries):
        raise ValueError("Catalog minimum, unique IDs or recorded count failed")
    for entry in entries:
        validate_item(entry)
    report = read_json(root / "data/expansion-report.json", {})
    excluded = {entry["id"]: entry for entry in report["excluded"]}
    added = 0
    input_counts = {}
    for name in ("css-wave-items.json", "vector-wave-items.json", "color-wave-items.json"):
        inputs = read_json(root / "data" / name, [])
        input_counts[name] = len(inputs)
        for source in inputs:
            if source["id"] in excluded:
                if source["id"] in by_id or excluded[source["id"]]["sameAs"] not in by_id:
                    raise ValueError("Duplicate exclusion does not identify a retained entry")
                continue
            stored = by_id.get(source["id"])
            if stored is None or any(stored.get(key) != value for key, value in source.items() if key != "analysis"):
                raise ValueError(f"Source record changed or missing: {source['id']}")
            if not stored.get("licenseText") or stored["kind"] == "reference":
                raise ValueError("Expansion asset lacks notice or is only a discovery link")
            if stored["kind"] == "palette" and json.loads(stored["code"]) != stored["colors"]:
                raise ValueError("Stored palette code and colors disagree")
            added += 1
    if report["added"] != added or report["baseline"] + added != len(entries):
        raise ValueError("Expansion accounting does not match published records")
    compact = read_json(root / "dist/catalog-index.json", {})
    if compact["stats"] != full["stats"] or {entry["id"] for entry in compact["items"]} != set(by_id):
        raise ValueError("Compact index has stale counts or IDs")
    collections = []
    for path in (root / "dist/collections").glob("*.json"):
        subset = read_json(path, [])
        if any(entry["category"] != path.stem or entry != by_id.get(entry["id"]) for entry in subset):
            raise ValueError("A source category collection is stale")
        collections.extend(entry["id"] for entry in subset)
    if len(collections) != len(entries) or set(collections) != set(by_id):
        raise ValueError("Collections do not partition the catalog")
    catalog = Catalog(root)
    if catalog.stats() != full["stats"]:
        raise ValueError("Read-only SQLite metadata is stale")
    with closing(catalog.connection()) as connection:
        rows = connection.execute("SELECT id,payload FROM items").fetchall()
        if len(rows) != len(entries) or any(json.loads(row["payload"]) != by_id[row["id"]] for row in rows):
            raise ValueError("Read-only SQLite source records are stale")
        if connection.execute("PRAGMA quick_check").fetchone()[0] != "ok":
            raise ValueError("SQLite integrity check failed")
    for kind, count in full["stats"]["kinds"].items():
        result = catalog.search(kind=kind, limit=100, offset=max(0, count - 100))
        if result["total"] != count or not result["items"]:
            raise ValueError("Search filtering or last-page offset failed")
    return {"verifiedAt": full["updatedAt"], "total": len(entries), "added": added,
            "inputCounts": input_counts, "excluded": len(excluded), "kinds": full["stats"]["kinds"],
            "codeLanguages": dict(Counter(entry["language"] for entry in entries if entry["kind"] == "code")),
            "checks": ["minimum", "schema", "unique-ids", "full-source-fields-and-notices",
                       "palette-code-equals-colors", "full-web-json", "compact-index", "all-category-collections",
                       "read-only-sqlite-records", "sqlite-integrity", "search-last-page"],
            "catalogSha256": hashlib.sha256((root / "dist/catalog.json").read_bytes()).hexdigest()}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--minimum", type=int, default=5000)
    options = parser.parse_args()
    try:
        result = verify(options.root, options.minimum)
        (options.root / "data/verification-report.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8", newline="\n")
        print(json.dumps(result))
    except (OSError, ValueError, KeyError) as error:
        print(f"Catalog verification failed: {error}", file=sys.stderr)
        sys.exit(1)
