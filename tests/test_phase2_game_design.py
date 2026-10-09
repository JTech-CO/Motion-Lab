"""Security, source attribution, and immutable comparison contract checks."""
import hashlib
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import import_phase2_game_design as importer

class GameDesignTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.items = json.loads((importer.LOCAL / "candidates.json").read_text(encoding="utf-8"))
        cls.tree = json.loads((importer.LOCAL / "tree.json").read_text(encoding="utf-8"))
        cls.entries = {x["path"]: x for x in cls.tree["tree"] if x.get("type") == "blob"}

    def test_archive_member_names_cannot_escape_source_root(self):
        for relative in ("/lorc/a.svg", "lorc/../../.env", "lorc/a.svg:secret", "lorc\\a.svg", "unknown/a.svg", "lorc/a.svg?x=1"):
            with self.subTest(relative=relative), self.assertRaises(ValueError): importer.source_path(relative)
        with patch.object(importer, "SOURCE", ROOT.parent / "outside"):
            with self.assertRaises(ValueError): importer.source_path("lorc/a.svg")

    def test_all_original_bytes_match_the_complete_pinned_tree(self):
        self.assertFalse(self.tree["truncated"])
        self.assertEqual(hashlib.sha256((importer.LOCAL / "tree.json").read_bytes()).hexdigest(), importer.TREE_INVENTORY_SHA)
        self.assertLessEqual(len(self.items), importer.RAW_CANDIDATE_BOUND)
        self.assertEqual(len({x["id"] for x in self.items}), len(self.items))
        for item in self.items:
            relative = Path(item["codePath"]).relative_to(Path("data/upstream/phase2-game-design/game-icons")).as_posix()
            raw = (ROOT / item["codePath"]).read_bytes()
            self.assertLessEqual(len(raw), 65536)
            self.assertEqual(self.entries[relative]["size"], len(raw))
            self.assertEqual(self.entries[relative]["sha"], hashlib.sha1(f"blob {len(raw)}\0".encode() + raw).hexdigest())
            self.assertEqual(item["upstreamSha256"], hashlib.sha256(raw).hexdigest())

    def test_each_export_preserves_its_specific_author_and_complete_license(self):
        terms = (importer.LOCAL / "CC-BY-3.0.txt").read_bytes()
        self.assertEqual(hashlib.sha256(terms).hexdigest(), importer.LICENSE_SHA)
        notice = (importer.LOCAL / "license.txt").read_text(encoding="utf-8")
        for item in self.items:
            raw = (ROOT / item["codePath"]).read_text(encoding="utf-8")
            self.assertTrue(item["code"].endswith(raw))
            self.assertIn("Icons made by " + item["sourceAuthor"], item["licenseText"])
            self.assertIn(notice, item["licenseText"])
            self.assertIn(terms.decode("utf-8"), item["licenseText"])
            self.assertIn(item["sourceUrl"], item["licenseText"])
            self.assertEqual(item["sourceCommit"], importer.COMMIT)
            self.assertFalse(item["preview"]["adapted"])

    def test_sources_are_full_static_svg_trees_with_no_active_content(self):
        for item in self.items:
            original = ET.fromstring((ROOT / item["codePath"]).read_text(encoding="utf-8"))
            exported = ET.fromstring(item["code"])
            self.assertEqual(ET.tostring(original), ET.tostring(exported))
            self.assertLessEqual(len(list(original.iter())), 128)
            self.assertEqual(original.get("viewBox"), "0 0 512 512")
            for node in original.iter():
                self.assertIn(node.tag.split("}")[-1], {"svg", "path"})
                self.assertTrue(set(node.attrib) <= {"viewBox", "d", "fill"})
            self.assertEqual(item["domain"], "design")
            self.assertEqual(item["category"], "shape")

    def test_comparison_does_not_read_the_integrated_catalog(self):
        original = Path.read_bytes
        def guarded(path):
            if path.resolve() == (ROOT / "data/catalog.json").resolve():
                raise AssertionError("Rebuild must not self-exclude after integration")
            return original(path)
        with patch.object(Path, "read_bytes", guarded):
            records, metadata = importer.comparison_records()
        self.assertEqual([x["records"] for x in metadata], [6111, 510, 3157])
        self.assertEqual(len(records), 9778)

    def test_final_selection_has_current_source_bound_decisions(self):
        if not importer.OUTPUT.exists(): self.skipTest("Final independent selection is pending")
        items = json.loads(importer.OUTPUT.read_text(encoding="utf-8"))
        self.assertLessEqual(len(items), importer.ACCEPTED_BOUND)
        candidates = {x["id"]: x for x in self.items}
        review = json.loads((importer.LOCAL / "selection-review.json").read_text(encoding="utf-8"))
        self.assertEqual(review["candidateInputSha256"], hashlib.sha256((importer.LOCAL / "candidates.json").read_bytes()).hexdigest())
        decisions = {x["id"]: x for x in review["decisions"]}
        self.assertEqual(len(importer.selection_decisions(self.items)), len(self.items))
        for item in items:
            self.assertEqual(item["code"], candidates[item["id"]]["code"])
            self.assertEqual(decisions[item["id"]]["decision"], "retain")
            self.assertEqual(item["evidence"]["semanticReviewCodeSha256"], hashlib.sha256(item["code"].encode()).hexdigest())
            self.assertIn(item["evidence"]["componentConcept"], item["tags"])
            self.assertTrue(item["description"].startswith(item["evidence"]["sourceComposition"]))

    def test_stale_or_duplicated_independent_evidence_cannot_approve_sources(self):
        review_path = importer.LOCAL / "selection-review.json"
        if not review_path.exists(): self.skipTest("Final independent selection is pending")
        original = importer.bounded_read
        good = json.loads(original(review_path, 1024 * 1024).decode("utf-8"))
        for mutation in ("independent", "code", "duplicate"):
            bad = json.loads(json.dumps(good))
            if mutation == "independent": bad["independentReviewSha256"] = "0" * 64
            if mutation == "code": bad["decisions"][0]["codeSha256"] = "0" * 64
            if mutation == "duplicate": bad["decisions"][1] = bad["decisions"][0]
            def read(path, maximum=65536):
                return json.dumps(bad).encode() if path == review_path else original(path, maximum)
            with self.subTest(mutation=mutation), patch.object(importer, "bounded_read", read):
                with self.assertRaises(ValueError): importer.selection_decisions(self.items)

if __name__ == "__main__": unittest.main()
