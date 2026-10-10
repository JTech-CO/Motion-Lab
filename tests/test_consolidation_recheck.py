"""New source reviews cannot approve changed code, DOM context, or input files."""

import hashlib
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

from scripts.build import build, project_url
from scripts.recheck_consolidation import audit_javascript, candidate_review, domain_for, history, recheck
from scripts.verify_catalog import verify


def digest(value):
    return hashlib.sha256(value).hexdigest()


def javascript_asset(root, index):
    upstream = root / "data/upstream/expansion12-fixture"
    upstream.mkdir(parents=True, exist_ok=True)
    code = f"function component_{index}(mesh, time) {{\n  mesh.position.x = time * {index + 1};\n}}\n"
    source = upstream / f"component-{index}.js"
    source.write_bytes(code.encode("utf-8"))
    notice = upstream / "LICENSE"
    notice.write_bytes(b"Complete MIT fixture notice")
    code_digest = digest(code.encode("utf-8"))
    return {"id": f"javascript-{index}", "kind": "code", "language": "javascript", "domain": "motion",
            "code": code, "license": "MIT", "licenseText": notice.read_text(),
            "sourceName": "Fixture", "sourceUrl": f"https://example.org/component-{index}.js",
            "preview": {"type": "reference", "variant": "stored-javascript"},
            "collectionEvidence": {"version": 1, "storedSha256": code_digest,
                "original": {"path": source.relative_to(root).as_posix(), "sha256": digest(source.read_bytes())},
                "notice": {"path": notice.relative_to(root).as_posix(), "sha256": digest(notice.read_bytes())}},
            "sourceReview": {"version": 1, "sourceSha256": code_digest, "revision": "1" * 40,
                "sourceRange": {"startLine": 1, "endLine": 3},
                "classification": {"domain": "motion", "assetType": "animation", "effects": ["slide"],
                    "components": ["shape"], "useCases": ["intro"], "techniques": ["transform"]},
                "evidence": {"basis": "reviewed-source", "confidence": "high", "summaryKO": "검토된 위치 이동",
                    "summaryEN": "Reviewed time-driven position assignment", "signals": ["mesh.position.x uses time"]},
                "dependencies": ["caller supplied mesh and time"], "limitations": ["Caller provides the update loop."],
                "preview": {"mode": "illustration", "language": "svg", "code": '<svg viewBox="0 0 80 60"><circle cx="10" cy="30" r="5"/></svg>',
                    "license": "CC0-1.0", "notice": "Independent CC0 fixture illustration", "attribution": "Motion Lab",
                    "limitations": ["Independent diagram; original JavaScript is not executed."]}}}


class ConsolidationReviewTests(unittest.TestCase):
    def test_javascript_recheck_includes_all_40_sources_without_claiming_near_similarity(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            items = [javascript_asset(root, index) for index in range(40)]
            self.assertTrue(all(domain_for(item) == "javascript" for item in items))
            (root / "data/catalog.json").write_text(json.dumps({"items": items, "updatedAt": "2026-10-11"}), encoding="utf-8")
            result = recheck(root, progress=lambda _message: None)
            javascript = result["domains"]["javascript"]
            self.assertEqual(javascript["coverage"]["itemCount"], 40)
            self.assertEqual(javascript["coverage"]["sourceEvidenceVerifiedItems"], 40)
            self.assertEqual(javascript["coverage"]["identityComparedPairs"], 780)
            self.assertEqual(javascript["coverage"]["visualComparedPairs"], 0)
            self.assertEqual(javascript["coverage"]["behavioralComparedPairs"], 0)
            self.assertEqual(javascript["methodology"]["near"], "unassessed")
            self.assertEqual(javascript["exactGroups"], [])
            self.assertEqual(javascript["errors"], [])
            self.assertFalse(result["sourceExecution"])
            self.assertTrue(result["passed"])

    def test_exact_javascript_bodies_keep_source_and_independent_preview_rights_context(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            original = javascript_asset(root, 0)
            variant = deepcopy(original)
            variant["id"] = "same-body-other-preview"
            variant["sourceReview"]["preview"]["code"] = '<svg viewBox="0 0 80 60"><rect width="30" height="20"/></svg>'
            variant["sourceReview"]["preview"]["notice"] += " with a separate illustration notice"
            variant["licenseText"] += "\nAdditional source attribution context"
            report = audit_javascript([original, variant], root)
            self.assertEqual(len(report["exactGroups"]), 1)
            first, second = report["items"]
            self.assertEqual(first["codeSha256"], second["codeSha256"])
            for field in ("sourceContextSha256", "canonicalSha256", "previewCodeSha256", "originalRightsSha256", "previewRightsSha256"):
                self.assertNotEqual(first[field], second[field])
            self.assertEqual(report["exactGroups"][0]["evidence"]["sourceContextSha256"][first["id"]], first["sourceContextSha256"])
            self.assertFalse(report["sourceExecution"])

    def test_javascript_inspection_rejects_stale_source_ranges_and_unlicensed_previews(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            item = javascript_asset(root, 0)
            for change in (lambda entry: entry["sourceReview"]["sourceRange"].update(endLine=2),
                           lambda entry: entry["sourceReview"]["preview"].update(license="MIT"),
                           lambda entry: entry["sourceReview"].update(sourceSha256="0" * 64)):
                mutated = deepcopy(item)
                change(mutated)
                report = audit_javascript([mutated], root)
                self.assertEqual(report["coverage"]["itemCount"], 1)
                self.assertEqual(report["coverage"]["sourceEvidenceVerifiedItems"], 0)
                self.assertEqual(report["errors"][0]["id"], item["id"])
                self.assertEqual(report["items"], [])

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
