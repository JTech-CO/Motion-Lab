"""Runtime image validation and interfaces, using a fixed local JPEG fixture."""

import base64
import hashlib
import http.client
import json
from pathlib import Path
import tempfile
import threading
import unittest

from motionlab.__main__ import parser, render_export
from motionlab.catalog import Catalog
from motionlab.image_assets import validate_image
from motionlab.mcp import TOOLS, MCPServer
from motionlab.server import make_server
from motionlab.validation import ValidationError, validate_search
from scripts.build import build

JPEG_FIXTURE = base64.b64decode(
    "/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8UHRofHh0aHBwgJC4nICIs"
    "IxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/2wBDAQkJCQwLDBgNDRgyIRwhMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIy"
    "MjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjL/wAARCABAAEADASIAAhEBAxEB/8QAHwAAAQUBAQEBAQEAAAAAAAAA"
    "AAECAwQFBgcICQoL/8QAtRAAAgEDAwIEAwUFBAQAAAF9AQIDAAQRBRIhMUEGE1FhByJxFDKBkaEII0KxwRVS0fAk"
    "M2JyggkKFhcYGRolJicoKSo0NTY3ODk6Q0RFRkdISUpTVFVWV1hZWmNkZWZnaGlqc3R1dnd4eXqDhIWGh4iJipKT"
    "lJWWl5iZmqKjpKWmp6ipqrKztLW2t7i5usLDxMXGx8jJytLT1NXW19jZ2uHi4+Tl5ufo6erx8vP09fb3+Pn6/8QA"
    "HwEAAwEBAQEBAQEBAQAAAAAAAAECAwQFBgcICQoL/8QAtREAAgECBAQDBAcFBAQAAQJ3AAECAxEEBSExBhJBUQdh"
    "cRMiMoEIFEKRobHBCSMzUvAVYnLRChYkNOEl8RcYGRomJygpKjU2Nzg5OkNERUZHSElKU1RVVldYWVpjZGVmZ2hp"
    "anN0dXZ3eHl6goOEhYaHiImKkpOUlZaXmJmaoqOkpaanqKmqsrO0tba3uLm6wsPExcbHyMnK0tPU1dbX2Nna4uPk"
    "5ebn6Onq8vP09fb3+Pn6/9oADAMBAAIRAxEAPwAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAo"
    "oooAKKKKACiiigAooooAKKKKACiiigAooooA/9k="
)


class ImageAssetsTest(unittest.TestCase):
    def test_local_descriptor_blocks_traversal_tampering_and_non_jpeg(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = root / "assets/materials/example.jpg"
            path.parent.mkdir(parents=True)
            body = JPEG_FIXTURE
            path.write_bytes(body)
            descriptor = {"path": "assets/materials/example.jpg", "mime": "image/jpeg", "width": 64,
                          "height": 64, "sha256": hashlib.sha256(body).hexdigest(), "sourceSha256": "0" * 64}
            validate_image(descriptor, root)
            for changes in ({"path": "../example.jpg"}, {"path": "assets/materials/a/b.jpg"}, {"mime": "text/html"},
                            {"width": True}, {"sha256": "1" * 64}, {"unexpected": 1}):
                with self.assertRaises(ValidationError):
                    validate_image({**descriptor, **changes}, root)
            path.write_bytes(b"<script>alert(1)</script>")
            with self.assertRaises(ValidationError):
                validate_image(descriptor, root)

    def test_cli_http_validation_and_mcp_schema_share_design_filters(self):
        args = validate_search({"domain": "design", "category": "material", "kind": "image", "basis": "image"})
        self.assertEqual(args["domain"], "design")
        with self.assertRaises(ValidationError):
            validate_search({"domain": "design' OR 1=1"})
        cli = parser().parse_args(["search", "--domain", "design", "--category", "material", "--kind", "image"])
        self.assertEqual(cli.domain, "design")
        schema = next(tool for tool in TOOLS if tool["name"] == "search_motion")["inputSchema"]["properties"]
        self.assertEqual(schema["domain"]["enum"], ["motion", "design"])
        self.assertIn("material", schema["category"]["enum"])
        csv = render_export([{"id": "texture", "domain": "design", "image": {"path": "assets/materials/example.jpg"}}], "csv")
        self.assertIn("image", csv.splitlines()[0])
        self.assertIn("assets/materials/example.jpg", csv)

    def test_design_domain_and_image_reach_sqlite_http_and_mcp(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "data").mkdir()
            path = root / "dist/assets/materials/texture.jpg"
            path.parent.mkdir(parents=True)
            body = JPEG_FIXTURE
            path.write_bytes(body)
            shared = {"description": "Original licensed source fixture", "sourceName": "Fixture",
                      "license": "CC0-1.0", "licenseText": "Fixture license", "verifiedAt": "2026-10-09",
                      "verification": "fixture", "access": "public", "tags": [], "colors": []}
            motion = {**shared, "id": "motion", "title": "Pulse", "sourceUrl": "https://example.org/motion",
                      "category": "animation", "kind": "code", "language": "css",
                      "code": ".motion-sample{animation:pulse 1s infinite}@keyframes pulse{0%,100%{opacity:1}50%{opacity:.3}}",
                      "preview": {"type": "css", "variant": "source"}}
            material = {**shared, "id": "texture", "title": "Texture", "sourceUrl": "https://example.org/texture",
                        "category": "material", "domain": "design", "kind": "image", "language": "image", "code": None,
                        "preview": {"type": "image", "variant": "material"},
                        "image": {"path": "assets/materials/texture.jpg", "mime": "image/jpeg", "width": 64,
                                  "height": 64, "sha256": hashlib.sha256(body).hexdigest(), "sourceSha256": "0" * 64}}
            (root / "data/imported-items.json").write_text(json.dumps([motion]), encoding="utf-8")
            (root / "data/phase2-material-items.json").write_text(json.dumps([material]), encoding="utf-8")
            build(root)
            catalog = Catalog(root)
            self.assertEqual([item["id"] for item in catalog.search(domain="design", kind="image")["items"]], ["texture"])
            self.assertEqual(catalog.search(domain="motion")["total"], 1)
            mcp = MCPServer(catalog).call_tool("search_motion", {"domain": "design", "category": "material"})
            self.assertEqual(mcp["structuredContent"]["items"][0]["image"]["path"], material["image"]["path"])
            server = make_server(root, 0)
            worker = threading.Thread(target=server.serve_forever, daemon=True)
            worker.start()
            try:
                connection = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=5)
                connection.request("GET", "/api/search?domain=design&kind=image&category=material")
                response = connection.getresponse()
                self.assertEqual(response.status, 200)
                self.assertEqual(json.loads(response.read())["total"], 1)
                connection.request("GET", "/assets/materials/texture.jpg")
                response = connection.getresponse()
                self.assertEqual(response.getheader("Content-Type"), "image/jpeg")
                self.assertEqual(response.read(), body)
                connection.close()
            finally:
                server.shutdown()
                server.server_close()
                worker.join(timeout=5)


if __name__ == "__main__":
    unittest.main()
