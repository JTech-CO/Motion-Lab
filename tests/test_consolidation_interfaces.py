"""Consolidation preserves original records through every read-only interface."""

from contextlib import closing
import csv
import http.client
import io
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import threading
import unittest

from motionlab.__main__ import render_export
from motionlab.catalog import Catalog, CatalogUnavailable
from motionlab.mcp import run_stdio
from motionlab.server import make_server
from motionlab.validation import ValidationError
from scripts.build import build


PROJECT = Path(__file__).resolve().parent.parent


def original(identifier, title, colors, notice):
    return {"id": identifier, "title": title, "description": "Source palette fixture",
            "category": "palette", "tags": ["palette"],
            "sourceUrl": "https://example.org/palettes/" + identifier,
            "sourceName": "Original " + identifier, "license": "MIT",
            "licenseText": notice, "verifiedAt": "2026-10-09", "verification": "fixture",
            "kind": "palette", "preview": {"type": "palette", "variant": "source"},
            "code": json.dumps(colors), "colors": colors, "language": "json", "access": "public"}


class ConsolidationInterfacesTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(dir=PROJECT / "tests")
        self.root = Path(self.temporary.name)
        (self.root / "data").mkdir()
        (self.root / "dist").mkdir()
        (self.root / "dist" / "index.html").write_text("<h1>Fixture</h1>", encoding="utf-8")
        self.first = original("family", "Original Family", ["#102030", "#ffffff"], "First complete MIT notice")
        self.second = original("old-variant", "Alternate Color Family", ["#112131", "#fefefe"], "Second complete MIT notice")
        self.third = original("unrelated", "Different Palette", ["#ff0000", "#00ff00"], "Third complete MIT notice")
        (self.root / "data" / "imported-items.json").write_text(json.dumps([self.first, self.third]), encoding="utf-8")
        build(self.root)
        self.catalog = Catalog(self.root)
        self.parent = {**self.catalog.get("family"), "aliases": ["old-variant"],
                       "consolidation": {"mode": "palette", "memberIds": ["family", "old-variant"], "variantCount": 2},
                       "variants": [self.first, self.second]}
        with closing(sqlite3.connect(self.catalog.database)) as connection:
            connection.execute("CREATE TABLE IF NOT EXISTS aliases (alias TEXT PRIMARY KEY, item_id TEXT NOT NULL, variant_id TEXT NOT NULL)")
            connection.execute("UPDATE items SET payload = ? WHERE id = ?", (json.dumps(self.parent), "family"))
            connection.execute("INSERT INTO aliases(alias, item_id, variant_id) VALUES (?, ?, ?)",
                               ("old-variant", "family", "old-variant"))
            connection.commit()

    def tearDown(self):
        self.temporary.cleanup()

    def expected_variant(self):
        return {**self.second, "canonicalId": "family"}

    def rewrite_parent(self, parent):
        with closing(sqlite3.connect(self.catalog.database)) as connection:
            connection.execute("UPDATE items SET payload = ? WHERE id = ?", (json.dumps(parent), "family"))
            connection.commit()

    def test_canonical_and_alias_preserve_exact_original_source(self):
        self.assertEqual(self.catalog.get("family"), self.parent)
        self.assertEqual(self.catalog.get("old-variant"), self.expected_variant())
        self.assertEqual(self.catalog.get("old-variant")["code"], json.dumps(self.second["colors"]))
        self.assertNotEqual(self.catalog.get("old-variant")["licenseText"], self.parent["licenseText"])
        self.assertEqual(self.catalog.get("unrelated")["sourceUrl"], self.third["sourceUrl"])
        self.assertIsNone(self.catalog.get("missing"))
        with self.assertRaises(ValidationError):
            self.catalog.get("old-variant' OR 1=1 --")

    def test_search_stats_and_export_count_only_canonical_entries(self):
        result = self.catalog.search()
        self.assertEqual(result["total"], 2)
        self.assertEqual({entry["id"] for entry in result["items"]}, {"family", "unrelated"})
        self.assertEqual(self.catalog.stats()["total"], 2)
        exported = self.catalog.export()
        self.assertEqual(len(exported), 2)
        self.assertEqual(next(entry for entry in exported if entry["id"] == "family")["variants"], [self.first, self.second])
        rows = list(csv.DictReader(io.StringIO(render_export(exported, "csv"))))
        row = next(entry for entry in rows if entry["id"] == "family")
        self.assertEqual(json.loads(row["variants"]), [self.first, self.second])
        self.assertEqual(json.loads(row["aliases"]), ["old-variant"])
        with closing(self.catalog.connection()) as connection:
            with self.assertRaises(sqlite3.OperationalError):
                connection.execute("DELETE FROM aliases")

    def test_old_database_without_alias_table_remains_compatible(self):
        with closing(sqlite3.connect(self.catalog.database)) as connection:
            connection.execute("DROP TABLE aliases")
            connection.commit()
        self.assertEqual(self.catalog.get("family"), self.parent)
        self.assertIsNone(self.catalog.get("old-variant"))

    def test_alias_does_not_substitute_wrong_variant_or_follow_chains(self):
        with closing(sqlite3.connect(self.catalog.database)) as connection:
            connection.execute("UPDATE aliases SET variant_id = ? WHERE alias = ?", ("family", "old-variant"))
            connection.commit()
        with self.assertRaises(CatalogUnavailable):
            self.catalog.get("old-variant")
        with closing(sqlite3.connect(self.catalog.database)) as connection:
            connection.execute("UPDATE aliases SET item_id = ?, variant_id = ? WHERE alias = ?",
                               ("another-alias", "old-variant", "old-variant"))
            connection.execute("INSERT INTO aliases VALUES (?, ?, ?)", ("another-alias", "old-variant", "another-alias"))
            connection.commit()
        self.assertIsNone(self.catalog.get("old-variant"))
        self.assertIsNone(self.catalog.get("another-alias"))

    def test_corrupt_or_nonpublic_original_cannot_be_returned(self):
        for variants in ([], [self.second, self.second], [dict(self.second, access="private")]):
            with self.subTest(variants=variants):
                self.rewrite_parent(dict(self.parent, variants=variants))
                with self.assertRaises(CatalogUnavailable):
                    self.catalog.get("old-variant")
        self.rewrite_parent(self.parent)
        with closing(sqlite3.connect(self.catalog.database)) as connection:
            connection.execute("UPDATE items SET access = ? WHERE id = ?", ("private", "family"))
            connection.commit()
        self.assertIsNone(self.catalog.get("old-variant"))

    def test_component_part_alias_identifies_complete_composition(self):
        parent = dict(self.parent, consolidation={**self.parent["consolidation"],
                     "variantRoles": {"old-variant": "component-part"}})
        self.rewrite_parent(parent)
        result = self.catalog.get("old-variant")
        self.assertEqual(result, {**self.expected_variant(), "variantRole": "component-part"})
        self.assertEqual(self.catalog.get(result["canonicalId"]), parent)

    def test_http_alias_and_parent_share_catalog_contract(self):
        server = make_server(self.root, 0)
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        try:
            for identifier, expected in (("old-variant", self.expected_variant()), ("family", self.parent)):
                connection = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=5)
                try:
                    connection.request("GET", "/api/items/" + identifier)
                    response = connection.getresponse()
                    self.assertEqual(response.status, 200)
                    self.assertEqual(json.loads(response.read()), expected)
                    self.assertEqual(response.getheader("X-Content-Type-Options"), "nosniff")
                finally:
                    connection.close()
        finally:
            server.shutdown()
            server.server_close()
            worker.join(timeout=5)

    def test_mcp_alias_preserves_original_record_and_protocol(self):
        requests = [
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
                "protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "fixture", "version": "1"}}},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {
                "name": "get_motion", "arguments": {"id": "old-variant"}}},
            {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {
                "name": "get_motion", "arguments": {"id": "family"}}},
        ]
        output = io.BytesIO()
        run_stdio(self.catalog, io.BytesIO(("\n".join(json.dumps(request) for request in requests) + "\n").encode()), output)
        replies = [json.loads(line) for line in output.getvalue().splitlines()]
        for reply, expected in ((replies[1], self.expected_variant()), (replies[2], self.parent)):
            self.assertFalse(reply["result"]["isError"])
            self.assertEqual(reply["result"]["structuredContent"], expected)
            self.assertEqual(json.loads(reply["result"]["content"][0]["text"]), expected)

    def test_cli_alias_and_json_export_preserve_full_variants(self):
        command = [sys.executable, "-m", "motionlab", "--root", str(self.root)]
        result = subprocess.run(command + ["get", "old-variant", "--json"], cwd=PROJECT,
                                capture_output=True, text=True, encoding="utf-8", check=True)
        self.assertEqual(json.loads(result.stdout), self.expected_variant())
        self.assertEqual(result.stderr, "")
        result = subprocess.run(command + ["export"], cwd=PROJECT, capture_output=True,
                                text=True, encoding="utf-8", check=True)
        items = json.loads(result.stdout)
        self.assertEqual(len(items), 2)
        self.assertEqual(next(entry for entry in items if entry["id"] == "family"), self.parent)


if __name__ == "__main__":
    unittest.main()
