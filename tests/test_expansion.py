"""Content and provenance regressions for the source expansion merge."""

import hashlib
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts.expansion import asset_fingerprint, merge_expansion, verify_collection_evidence
from scripts.build import MAX_INPUT_JSON_BYTES, MAX_GENERATED_CATALOG_BYTES, read_json


def code(identifier, body, language="css"):
    return {"id": identifier, "kind": "code", "language": language, "code": body,
            "licenseText": "Complete source notice", "colors": []}


class ExpansionTest(unittest.TestCase):
    def test_json_byte_budget_preserves_source_default_and_bounds_actual_read(self):
        self.assertEqual(MAX_INPUT_JSON_BYTES, 100 * 1024 * 1024)
        self.assertEqual(MAX_GENERATED_CATALOG_BYTES, 128 * 1024 * 1024)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "input.json"
            path.write_bytes(b'\xef\xbb\xbf{"ok":true}')
            self.assertEqual(read_json(path, {}, maximum_bytes=32), {"ok": True})
            # The file can grow after stat; bound the bytes actually consumed.
            with patch.object(Path, "open", return_value=io.BytesIO(b" " * 33)):
                with self.assertRaisesRegex(ValueError, "byte limit"):
                    read_json(path, {}, maximum_bytes=32)
            path.write_bytes(b" " * 33)
            with self.assertRaisesRegex(ValueError, "byte limit"):
                read_json(path, {}, maximum_bytes=32)
            for invalid in (True, 0, -1, MAX_GENERATED_CATALOG_BYTES + 1):
                with self.assertRaisesRegex(ValueError, "Invalid JSON byte limit"):
                    read_json(path, {}, maximum_bytes=invalid)

    def test_collection_receipt_binds_original_notice_and_stored_body(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "data/upstream/expansion12-test/original.svg"
            path.parent.mkdir(parents=True)
            path.write_bytes(b"<svg/>")
            notice = path.with_name("LICENSE")
            notice.write_bytes(b"Complete source notice")
            entry = code("new", "<svg/>", "svg")
            entry["licenseText"] = "Complete source notice"
            entry["collectionEvidence"] = {"version":1,"original":{"path":path.relative_to(root).as_posix(),"sha256":hashlib.sha256(path.read_bytes()).hexdigest()},"notice":{"path":notice.relative_to(root).as_posix(),"sha256":hashlib.sha256(notice.read_bytes()).hexdigest()},"storedSha256":hashlib.sha256(entry["code"].encode()).hexdigest()}
            self.assertTrue(verify_collection_evidence(entry, root))
            result, _ = merge_expansion([], [("expansion12-test-items.json", [entry])], lambda v:v, root=root)
            self.assertEqual(len(result), 1)
            entry["code"] = "<svg><path/></svg>"
            with self.assertRaisesRegex(ValueError, "Stored collection body"):
                verify_collection_evidence(entry, root)
            entry["code"] = "<svg/>"
            path.write_bytes(b"<svg>changed</svg>")
            with self.assertRaisesRegex(ValueError, "file digest"):
                verify_collection_evidence(entry, root)
            entry["collectionEvidence"]["original"]["path"] = "data/upstream/expansion12-test/../../../../outside.svg"
            with self.assertRaisesRegex(ValueError, "Invalid collection path"):
                verify_collection_evidence(entry, root)

    def test_new_collection_batch_requires_receipt(self):
        with self.assertRaisesRegex(ValueError, "workspace root"):
            merge_expansion([], [("expansion12-test-items.json", [code("new", "<svg/>", "svg")])], lambda v:v)
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "Missing collection receipt"):
                merge_expansion([], [("expansion12-test-items.json", [code("new", "<svg/>", "svg")])], lambda v:v, root=directory)
    def test_palette_identity_keeps_order_and_normalizes_hex(self):
        def palette(colors):
            return {"kind": "palette", "language": "json", "colors": colors}
        self.assertEqual(asset_fingerprint(palette(["#fff", "#ABCDEF"])),
                         asset_fingerprint(palette(["#ffffff", "#abcdef"])))
        self.assertNotEqual(asset_fingerprint(palette(["#fff", "#000"])),
                            asset_fingerprint(palette(["#000", "#fff"])))

    def test_css_notice_removed_but_literals_and_motion_preserved(self):
        first = code("one", '/* copyright */ .sample{content:"/* text */";opacity:0}')
        second = code("two", '/* different notice */ .sample{content:"/* text */";opacity:0}')
        self.assertEqual(asset_fingerprint(first), asset_fingerprint(second))
        self.assertNotEqual(asset_fingerprint(first), asset_fingerprint(code("three", '.sample{content:"";opacity:0}')))
        self.assertNotEqual(asset_fingerprint(first), asset_fingerprint(code("four", '.sample{content:"/* text */";opacity:1}')))

    def test_svg_formatting_dedup_keeps_animation_values(self):
        first = code("one", '<svg width="24" height="24"><circle r="3"><animate attributeName="r" to="5"/></circle></svg>', "svg")
        second = code("two", '<svg height="24" width="24">\n<circle r="3"><animate to="5" attributeName="r"/></circle>\n</svg>', "svg")
        self.assertEqual(asset_fingerprint(first), asset_fingerprint(second))
        self.assertNotEqual(asset_fingerprint(first), asset_fingerprint(code("three", second["code"].replace('to="5"', 'to="6"'), "svg")))

    def test_merge_keeps_existing_ids_and_explains_duplicate(self):
        base = code("existing", ".sample{opacity:0}")
        duplicate = code("duplicate", ".sample{opacity:0}")
        distinct = code("new", ".sample{opacity:1}")
        result, report = merge_expansion([base], [("wave.json", [duplicate, distinct])], lambda entry: entry)
        self.assertEqual([entry["id"] for entry in result], ["new"])
        self.assertEqual(report["excluded"][0]["sameAs"], "existing")
        self.assertEqual(report["inputs"]["wave.json"], {"input": 2, "accepted": 1, "duplicates": 1})

    def test_merge_rejects_collisions_and_missing_notice(self):
        base = code("existing", ".sample{opacity:0}")
        with self.assertRaises(ValueError):
            merge_expansion([base], [("wave.json", [base])], lambda entry: entry)
        unlicensed = code("new", ".sample{opacity:1}")
        unlicensed.pop("licenseText")
        with self.assertRaises(ValueError):
            merge_expansion([], [("wave.json", [unlicensed])], lambda entry: entry)

    def test_new_assets_are_compared_to_original_variants_and_repair_parts(self):
        original = code("old-alias", ".part{opacity:.4}")
        former = code("former", ".old{opacity:.8}")
        parent = {**code("canonical", ".complete{opacity:1}"),
                  "variants": [original], "repair": {"originalRecord": former}}
        duplicates = [code("new-alias-body", original["code"]), code("new-former-body", former["code"])]
        result, report = merge_expansion([parent], [("phase2.json", duplicates)], lambda entry: entry)
        self.assertEqual(result, [])
        self.assertEqual({entry["sameAs"] for entry in report["excluded"]}, {"old-alias", "former"})
        with self.assertRaises(ValueError):
            merge_expansion([parent], [("phase2.json", [original])], lambda entry: entry)

    def test_image_identity_uses_stored_digest_not_provider_or_path(self):
        first = {"id": "one", "kind": "image", "image": {"sha256": "a" * 64}, "licenseText": "CC0"}
        second = {**first, "id": "two", "sourceName": "Different provider", "image": {"sha256": "a" * 64}}
        self.assertEqual(asset_fingerprint(first), asset_fingerprint(second))
        result, report = merge_expansion([first], [("materials.json", [second])], lambda entry: entry)
        self.assertEqual(result, [])
        self.assertEqual(report["excluded"][0]["sameAs"], "one")
