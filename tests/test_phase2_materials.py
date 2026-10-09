"""Source-boundary and material-family behavior, with no test network calls."""

import hashlib
import http.client
import io
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
import zipfile

import numpy as np
from PIL import Image

from motionlab.__main__ import parser, render_export
from motionlab.catalog import Catalog
from motionlab.image_assets import validate_image
from motionlab.mcp import TOOLS, MCPServer
from motionlab.server import make_server
from motionlab.validation import ValidationError, validate_search
from scripts.import_phase2_materials import checked_url, decode_image, extract_color_map, image_features, material_families, near_image
from scripts import import_phase2_materials as importer
from scripts.build import build


class MaterialsTest(unittest.TestCase):
    def test_import_paths_stay_within_owned_workspace_even_if_root_is_redirected(self):
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary) / "workspace"
            with patch.object(importer, "ROOT", workspace), patch.object(importer, "LOCAL", workspace / "artifacts"):
                self.assertEqual(importer.local_path("originals/polyhaven/stone.jpg"),
                                 (workspace / "artifacts/originals/polyhaven/stone.jpg").resolve())
                for value in ("../private.jpg", "/absolute.jpg", "C:/private.jpg", "originals/../private.jpg"):
                    with self.assertRaises(ValueError):
                        importer.local_path(value)
                path = importer.local_path("originals/polyhaven/stone.jpg")
                path.parent.mkdir(parents=True)
                path.write_bytes(b"pinned source")
                with patch.object(importer, "MANIFEST", workspace / "missing-manifest.json"):
                    collector = importer.Collector(offline=True)
                    collector.artifacts["originals/polyhaven/stone.jpg"] = {
                        "url": "https://evil.test/material.jpg", "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
                    with self.assertRaises(ValueError):
                        collector.artifact("originals/polyhaven/stone.jpg", "https://evil.test/material.jpg", 100)
            with patch.object(importer, "ROOT", workspace), patch.object(importer, "LOCAL", Path(temporary) / "outside"):
                with self.assertRaises(ValueError):
                    importer.local_path("originals/polyhaven/stone.jpg")

    def test_source_url_boundary_blocks_arbitrary_hosts_credentials_and_paths(self):
        checked_url("https://dl.polyhaven.org/file/ph-assets/Textures/jpg/1k/stone/stone_diff_1k.jpg")
        for value in ("http://ambientcg.com/api/v3/assets", "https://ambientcg.com.evil.test/get",
                      "https://localhost/api/v3/assets", "https://x@ambientcg.com/get", "https://ambientcg.com:444/get",
                      "https://ambientcg.com/api/v3/assets/evil", "https://ambientcg.com/api/v3/../assets",
                      "https://dl.polyhaven.org/file/ph-assets/Textures/%2e%2e/private"):
            with self.assertRaises(ValueError, msg=value):
                checked_url(value)

    def test_material_variations_and_generators_are_one_family(self):
        ambient = [{"id": "Wood001A", "relations": {"variations": ["Wood001B"], "parents": []}},
                   {"id": "Wood001B", "relations": {"variations": [], "parents": []}},
                   {"id": "Tile001", "relations": {"variations": [], "parents": ["TileSubstance001"]}},
                   {"id": "Tile002", "relations": {"variations": [], "parents": ["TileSubstance001"]}},
                   {"id": "Metal001", "relations": {"variations": [], "parents": []}}]
        poly = {"brick_wall_01": {"name": "First"}, "brick_wall_02": {"name": "Neighbor"}, "lichen_rock": {"name": "Rock"}}
        families = material_families(ambient, poly)
        self.assertEqual(len(families), 5)
        self.assertEqual(sorted(len(family["members"]) for family in families), [1, 1, 2, 2, 2])
        reviewed = material_families(
            [{"id": name, "relations": {}} for name in ("Tiles003", "Tiles004", "Tiles132A", "Tiles099")],
            {name: {"name": name} for name in ("brick_4", "factory_brick", "large_red_bricks", "mixed_brick_wall")})
        self.assertEqual(len(reviewed), 4)
        self.assertEqual(sorted(len(family["members"]) for family in reviewed), [1, 1, 3, 3])

    def test_archive_reads_only_registered_color_without_extraction(self):
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, "w") as archive:
            archive.writestr("Wood001_1K_Color.jpg", b"color")
            archive.writestr("Wood001_1K_NormalGL.jpg", b"normal")
            archive.writestr("../../execute.py", b"untrusted")
        self.assertEqual(extract_color_map(stream.getvalue(), "Wood001"), ("Wood001_1K_Color.jpg", b"color"))
        with self.assertRaises(ValueError):
            extract_color_map(stream.getvalue(), "Wood002")
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("Wood001_1K_Color.jpg", b"0" * 2_000_000)
        with self.assertRaises(ValueError):
            extract_color_map(stream.getvalue(), "Wood001")

    def test_image_decode_rejects_html_fake_extensions_and_extreme_dimensions(self):
        for body in (b"<html>not an image</html>", b"\xff\xd8\xffnotvalid"):
            with self.assertRaises((ValueError, OSError)):
                decode_image(body)
        output = io.BytesIO()
        Image.new("RGB", (5000, 50)).save(output, "PNG")
        with self.assertRaises(ValueError):
            decode_image(output.getvalue())
        output = io.BytesIO()
        Image.new("RGB", (64, 64), "blue").save(output, "JPEG")
        self.assertEqual(decode_image(output.getvalue()).size, (64, 64))

    def test_perceptual_comparison_groups_rotation_and_small_color_change(self):
        rng = np.random.default_rng(31)
        texture = np.asarray(rng.uniform(30, 220, (64, 64, 3)), dtype=np.uint8)
        image = Image.fromarray(texture)
        first = image_features(image)
        rotated = image_features(image.rotate(90))
        shifted = image_features(Image.fromarray(np.clip(texture.astype(int) + 3, 0, 255).astype(np.uint8)))
        self.assertIsNotNone(near_image(first, rotated))
        self.assertIsNotNone(near_image(first, shifted))
        self.assertIsNone(near_image(first, image_features(Image.new("RGB", (64, 64), "red"))))

    def test_local_descriptor_blocks_traversal_tampering_and_non_jpeg(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = root / "assets/materials/example.jpg"
            path.parent.mkdir(parents=True)
            stream = io.BytesIO()
            Image.new("RGB", (64, 64)).save(stream, "JPEG")
            body = stream.getvalue()
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
            output = io.BytesIO()
            Image.new("RGB", (64, 64), "gray").save(output, "JPEG")
            body = output.getvalue()
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
