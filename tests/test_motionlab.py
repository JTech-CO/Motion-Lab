import http.client
from contextlib import closing
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest

from motionlab.__main__ import render_export
from motionlab.catalog import Catalog
from motionlab.mcp import MAX_LINE_BYTES, run_stdio
from motionlab.server import RateLimiter, make_server
from motionlab.validation import ValidationError
from scripts.build import build

PROJECT = Path(__file__).resolve().parent.parent


def item(identifier, title, category="animation", kind="code", license_name="MIT"):
    return {"id": identifier, "title": title, "description": "Accessible motion CSS example 모션",
            "category": category, "tags": ["css", "motion"], "sourceUrl": "https://example.org/" + identifier,
            "sourceName": "Fixture", "license": license_name, "verifiedAt": "2026-10-08",
            "verification": "fixture", "kind": kind,
            "preview": {"type": "reference" if kind == "reference" else "css", "variant": "pulse"},
            "code": None if kind == "reference" else ".dot { animation: pulse 1s ease; }",
            "colors": ["#ffffff", "#000"], "language": "link" if kind == "reference" else "css", "access": "public"}


class LibraryTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(dir=PROJECT / "tests")
        self.root = Path(self.temporary.name)
        (self.root / "data").mkdir()
        (self.root / "dist").mkdir()
        self.items = [item("pulse", "Pulse Motion"), item("wipe", "Wipe Motion", "transition"),
                      item("inspiration", "Editorial Inspiration", "reference", "reference", "Unknown")]
        (self.root / "data" / "imported-items.json").write_text(json.dumps(self.items), encoding="utf-8")
        (self.root / "dist" / "index.html").write_text("<h1>Motion Lab</h1>", encoding="utf-8")
        build(self.root)
        self.catalog = Catalog(self.root)

    def tearDown(self):
        self.temporary.cleanup()

    def test_search_filters_paging_and_binding(self):
        result = self.catalog.search(query="motion", category="transition", license="MIT", limit=1)
        self.assertEqual([entry["id"] for entry in result["items"]], ["wipe"])
        self.assertEqual(result["total"], 1)
        self.assertEqual(self.catalog.search(query="'; DROP TABLE items; --")["total"], 0)
        self.assertEqual(self.catalog.search(license="MIT' OR 1=1 --")["total"], 0)
        self.assertEqual(self.catalog.stats()["total"], 3)
        self.assertEqual(self.catalog.search(query="모션")["total"], 3)
        self.assertEqual(len(self.catalog.search(limit=1, offset=1)["items"]), 1)
        with closing(self.catalog.connection()) as connection:
            with self.assertRaises(Exception):
                connection.execute("DELETE FROM items")

    def test_validation_and_reference(self):
        for arguments in ({"limit": True}, {"limit": 101}, {"offset": -1}, {"category": "unknown"},
                          {"query": "x" * 241}, {"sort": "title"}, {"query": ["motion"]}):
            with self.assertRaises(ValidationError):
                self.catalog.search(**arguments)
        self.assertIsNone(self.catalog.get("missing"))
        self.assertIsNone(self.catalog.get("inspiration")["code"])
        with self.assertRaises(ValidationError):
            self.catalog.get("../data/catalog.json")

    def test_build_deduplicates_and_preserves_frontend(self):
        duplicate = dict(self.items[0], id="pulse-duplicate", sourceUrl="https://example.org/pulse?utm_source=fixture")
        (self.root / "data" / "imported-items.json").write_text(json.dumps(self.items + [duplicate]), encoding="utf-8")
        self.assertEqual(build(self.root)["total"], 3)
        self.assertEqual((self.root / "dist" / "index.html").read_text(), "<h1>Motion Lab</h1>")
        self.assertEqual(json.loads((self.root / "dist" / "catalog.json").read_text(encoding="utf-8"))["stats"]["total"], 3)
        compact = json.loads((self.root / "dist" / "catalog-index.json").read_text(encoding="utf-8"))
        self.assertEqual(len(compact["items"]), 3)
        self.assertNotIn("code", compact["items"][0])
        self.assertIn("3 entries", (self.root / "dist" / "llms.txt").read_text(encoding="utf-8"))

    def test_build_authoritative_inputs_and_source_repository_dedup(self):
        first = dict(self.items[0], sourceUrl="https://github.com/example/motion/blob/abc/demo.css")
        second = dict(self.items[1], sourceUrl="https://github.com/example/motion")
        (self.root / "data" / "imported-items.json").write_text(json.dumps([first]), encoding="utf-8")
        (self.root / "data" / "research-sources.json").write_text(json.dumps([second]), encoding="utf-8")
        stats = build(self.root)
        self.assertEqual(stats["total"], 2)
        self.assertEqual(stats["sources"], 1)
        self.assertIsNone(self.catalog.get("inspiration"))

    def test_http_paths_headers_arguments_and_read_only(self):
        server = make_server(self.root, 0)
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        try:
            def request(path, method="GET", headers=None):
                connection = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=5)
                connection.request(method, path, headers=headers or {})
                response = connection.getresponse()
                body = response.read()
                result = (response.status, dict(response.getheaders()), body)
                connection.close()
                return result
            status, headers, body = request("/api/search?q=motion&category=transition&limit=1")
            self.assertEqual(status, 200)
            self.assertEqual(json.loads(body)["items"][0]["id"], "wipe")
            status, _, body = request("/api/search?asset_type=transition&basis=code")
            self.assertEqual(status, 200)
            self.assertEqual(json.loads(body)["items"][0]["analysis"]["assetType"], "transition")
            self.assertEqual(headers["X-Content-Type-Options"], "nosniff")
            self.assertIn("script-src 'self'", headers["Content-Security-Policy"])
            self.assertNotIn("Access-Control-Allow-Origin", headers)
            for path in ("/../data/catalog.json", "/%2e%2e/data/catalog.json", "/%5c..%5cdata/catalog.json",
                         "/.git/config", "/motionlab.sqlite"):
                self.assertIn(request(path)[0], (400, 404))
            for path in ("/api/search?limit=9999", "/api/search?q=x&q=y", "/api/search?sort=title", "/api/search?effect=unknown",
                         "/api/stats?x=y", "/api/items/pulse?x=y"):
                self.assertEqual(request(path)[0], 400)
            self.assertEqual(request("/", headers={"Host": "evil.example"})[0], 403)
            self.assertEqual(request("/api/stats", headers={"Origin": "https://evil.example"})[0], 403)
            self.assertEqual(request("/api/search", "POST")[0], 405)
            self.assertEqual(request("/")[0], 200)
            self.assertEqual(request("/", "HEAD")[2], b"")
        finally:
            server.shutdown()
            server.server_close()
            worker.join(timeout=5)

    def test_rate_limit(self):
        limiter = RateLimiter(limit=2)
        self.assertTrue(limiter.allow("loopback"))
        self.assertTrue(limiter.allow("loopback"))
        self.assertFalse(limiter.allow("loopback"))

    def test_mcp_normal_and_malformed_protocol(self):
        requests = [
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
                "protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "fixture", "version": "1"}}},
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
            {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {
                "name": "search_motion", "arguments": {"query": "pulse", "limit": 1}}},
            {"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {
                "name": "get_motion", "arguments": {"id": "pulse", "unexpected": True}}},
            {"jsonrpc": "2.0", "id": 5, "method": "tools/call", "params": {
                "name": "search_motion", "arguments": {"limit": True}}},
            {"jsonrpc": "2.0", "id": 6, "method": "tools/call", "params": {"name": "motion_stats"}},
        ]
        wire = "\n".join(json.dumps(request) for request in requests).encode() + b"\n{invalid\n"
        output = io.BytesIO()
        run_stdio(self.catalog, io.BytesIO(wire), output)
        replies = [json.loads(line) for line in output.getvalue().splitlines()]
        self.assertEqual(len(replies), 7)
        self.assertEqual(replies[0]["result"]["protocolVersion"], "2025-06-18")
        self.assertEqual(len(replies[1]["result"]["tools"]), 3)
        self.assertEqual(replies[2]["result"]["structuredContent"]["items"][0]["id"], "pulse")
        self.assertEqual(replies[3]["error"]["code"], -32602)
        self.assertEqual(replies[4]["error"]["code"], -32602)
        self.assertEqual(replies[5]["result"]["structuredContent"]["total"], 3)
        self.assertEqual(replies[6]["error"]["code"], -32700)

    def test_mcp_size_bound_and_recovery(self):
        output = io.BytesIO()
        run_stdio(self.catalog, io.BytesIO(b"x" * (MAX_LINE_BYTES + 10) +
                  b'\n{"jsonrpc":"2.0","id":9,"method":"ping"}\n'), output)
        replies = [json.loads(line) for line in output.getvalue().splitlines()]
        self.assertEqual(replies[0]["error"]["code"], -32700)
        self.assertEqual(replies[1]["id"], 9)
        self.assertEqual(replies[1]["result"], {})

    def test_cli_subprocess_and_clean_mcp_stdout(self):
        command = [sys.executable, "-m", "motionlab", "--root", str(self.root)]
        result = subprocess.run(command + ["search", "pulse", "--json"], cwd=PROJECT,
                                capture_output=True, text=True, encoding="utf-8", check=True)
        self.assertEqual(json.loads(result.stdout)["total"], 1)
        result = subprocess.run(command + ["mcp"], input='{"jsonrpc":"2.0","id":1,"method":"ping"}\n',
                                cwd=PROJECT, capture_output=True, text=True, encoding="utf-8", check=True)
        self.assertEqual(json.loads(result.stdout)["id"], 1)
        self.assertEqual(result.stderr, "")

    def test_csv_formula_escaping(self):
        rendered = render_export([dict(self.items[0], title="=1+1")], "csv")
        self.assertIn("'=1+1", rendered)


if __name__ == "__main__":
    unittest.main()
