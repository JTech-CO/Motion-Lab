"""New source reviews cannot approve changed code, DOM context, or input files."""

import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from scripts.build import build, project_url
from scripts.recheck_consolidation import candidate_review, history
from scripts.verify_catalog import verify


def digest(value):
    return hashlib.sha256(value).hexdigest()


class Phase2ReviewTests(unittest.TestCase):
    def test_review_requires_unchanged_code_and_preview_context(self):
        ids = ["phase2-motion-a", "phase2-motion-b"]
        entries = {identifier: {"code": identifier} for identifier in ids}
        contexts = {identifier: {"canonicalSha256": digest((identifier + "dom").encode())}
                    for identifier in ids}
        decision = {"ids": ids, "domain": "css", "classification": "distinct-composition",
                    "basis": "manual-code-and-DOM-review", "reviewScope": "phase2",
                    "reviewFile": "upstream/phase2-motion/css-review-decisions.json",
                    "codeSha256": {identifier: digest(identifier.encode()) for identifier in ids}}
        decisions = {("css", tuple(sorted(ids))): decision}
        signatures = {("css", identifier): contexts[identifier]["canonicalSha256"] for identifier in ids}
        result = candidate_review("css", {"ids": ids}, contexts, entries, decisions, signatures)
        self.assertEqual(result["status"], "current-code-and-context-review-valid")
        entries[ids[0]]["code"] += " changed"
        self.assertEqual(candidate_review("css", {"ids": ids}, contexts, entries, decisions, signatures)
                         ["status"], "requires-current-source-review")
        entries[ids[0]]["code"] = ids[0]
        contexts[ids[0]]["canonicalSha256"] = digest(b"different DOM")
        self.assertEqual(candidate_review("css", {"ids": ids}, contexts, entries, decisions, signatures)
                         ["status"], "requires-current-source-review")

    def test_phase2_review_rejects_changed_authoritative_input(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            upstream = root / "data/upstream/phase2-motion"
            upstream.mkdir(parents=True)
            (root / "data/phase2-motion-items.json").write_bytes(b"[]\n")
            (upstream / "css-review-decisions.json").write_text(json.dumps({
                "phase2MotionInputSha256": digest(b"different input"), "decisions": []}), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "input changed"):
                history(root)

    def test_material_assets_count_as_two_projects(self):
        self.assertEqual(project_url("https://ambientcg.com/view?id=Bricks001"), "https://ambientcg.com")
        self.assertEqual(project_url("https://polyhaven.com/a/wood_floor"), "https://polyhaven.com")
        self.assertNotEqual(project_url("https://example.org/a"), project_url("https://example.org/b"))

    def test_missing_empty_domain_export_cannot_pass_verification(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "data").mkdir()
            item = {"id": "fixture", "title": "Fixture", "description": "Stored source",
                    "category": "animation", "kind": "code", "language": "css", "access": "public",
                    "tags": [], "colors": [], "sourceName": "Fixture", "sourceUrl": "https://example.org/fixture",
                    "license": "MIT", "licenseText": "Complete fixture notice", "verifiedAt": "2026-10-09",
                    "verification": "fixture", "code": ".motion-sample{animation:wave 1s infinite}@keyframes wave{to{opacity:0}}",
                    "preview": {"type": "css", "variant": "source"}}
            (root / "data/imported-items.json").write_text(json.dumps([item]), encoding="utf-8")
            build(root)
            self.assertEqual(verify(root, minimum=1, minimum_stored=1)["storedAssets"], 1)
            (root / "dist/collections/domain-design.json").unlink()
            with self.assertRaisesRegex(ValueError, "required domain collection is missing"):
                verify(root, minimum=1, minimum_stored=1)


if __name__ == "__main__":
    unittest.main()
