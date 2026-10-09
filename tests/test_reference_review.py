"""Reference previews cannot silently change source rights or inflate asset counts."""

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from motionlab.catalog import Catalog
from motionlab.reference_review import apply_reference_removals, apply_reference_reviews, source_sha256, validate_review
from scripts.analyze import analyze_items
from scripts.build import build
from scripts.verify_catalog import verify


def source(kind="reference", identifier="reference-fixture"):
    return {"id": identifier, "title": identifier, "description": "Inspected source fixture",
            "category": "reference" if kind == "reference" else "animation",
            "tags": [], "sourceUrl": "https://example.org/" + identifier,
            "sourceName": "Original provider", "license": "reference-only" if kind == "reference" else "MIT",
            "licenseNote": "Original rights remain unchanged", "verifiedAt": "2026-10-09",
            "verification": "source-reviewed", "kind": kind, "access": "public", "colors": [],
            "language": "link" if kind == "reference" else "css",
            "preview": {"type": "reference" if kind == "reference" else "css", "variant": "source"},
            "code": None if kind == "reference" else ".motion-sample{animation:pulse 1s infinite}@keyframes pulse{to{opacity:0}}"}


def annotation(item, artifact):
    return {"id": item["id"], "sourceSha256": source_sha256(item), "targetDomain": "motion", "resourceType": "example",
            "assetType": "typography", "effects": ["fade", "text"], "components": ["text"],
            "useCases": ["intro"], "evidence": {"basis": "reviewed-source", "confidence": "medium",
            "summaryKO": "원문에서 글자 등장 구성을 확인했습니다.", "summaryEN": "Reviewed source text entry construction.",
            "signals": ["source: text entry"], "artifacts": [artifact]},
            "preview": {"mode": "illustration", "language": "css", "code": ".motion-sample{animation:entry 2s infinite}@keyframes entry{from{opacity:0}to{opacity:1}}",
            "dom": {"tag": "span", "className": "motion-sample", "text": "TYPE"}, "license": "CC0-1.0",
            "notice": "Motion Lab independently authored concept illustration, CC0-1.0.", "attribution": "Motion Lab",
            "limitations": ["Independent concept illustration; this is not the original implementation."]}}


class ReferenceReviewTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        path = self.root / "data/upstream/reference-review/evidence.json"
        path.parent.mkdir(parents=True)
        path.write_bytes(b'{"description":"Text entry concept"}\n')
        self.artifact = {"path": path.relative_to(self.root).as_posix(),
                         "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                         "sourceUrl": "https://example.org/source"}
        self.item = source()
        self.review = annotation(self.item, self.artifact)

    def test_source_fields_and_original_rights_survive_separate_illustration(self):
        items = analyze_items([self.item])
        result = apply_reference_reviews(items, [{"version": 1, "reviews": [self.review]}], root=self.root)[0]
        for key, value in self.item.items():
            self.assertEqual(result[key], value)
        self.assertIsNone(result["analysis"]["domain"])
        self.assertEqual(result["analysis"]["assetType"], "typography")
        self.assertEqual(result["analysis"]["evidence"]["basis"], "reviewed-source")
        self.assertEqual(result["referenceReview"]["preview"]["license"], "CC0-1.0")
        self.assertEqual(result["license"], "reference-only")
        self.assertNotIn("referenceReview", items[0])

    def test_changed_original_or_evidence_cannot_retain_approval(self):
        changed = {**self.item, "sourceUrl": "https://example.org/other"}
        with self.assertRaisesRegex(ValueError, "original record"):
            validate_review(self.review, item=changed)
        (self.root / self.artifact["path"]).write_bytes(b"Changed evidence")
        with self.assertRaisesRegex(ValueError, "digest changed"):
            validate_review(self.review, item=self.item, root=self.root)

    def test_reference_coverage_must_be_complete_unique_and_existing(self):
        items = analyze_items([self.item, source(identifier="second-reference")])
        for reviews in [[self.review], [self.review, self.review], [{**self.review, "id": "unknown"}]]:
            with self.assertRaises(ValueError):
                apply_reference_reviews(items, [{"version": 1, "reviews": reviews}], root=self.root)

    def test_local_evidence_path_cannot_traverse_or_use_credentials(self):
        for change in [{"path": "data/upstream/../../outside.json"}, {"path": "https://example.org/source"},
                       {"sourceUrl": "https://name:secret@example.org/source"}]:
            review = deepcopy(self.review)
            review["evidence"]["artifacts"][0].update(change)
            with self.assertRaises(ValueError):
                validate_review(review, root=self.root)

    def test_related_preview_resolves_one_stored_asset_without_reference_recursion(self):
        stored = source("code", "stored-fixture")
        review = deepcopy(self.review)
        review["preview"] = {"mode": "related-asset", "assetId": stored["id"], "limitations": ["Related example, not original source output."]}
        validate_review(review, by_id={stored["id"]: stored}, item=self.item)
        for identifier in [self.item["id"], "missing"]:
            review["preview"]["assetId"] = identifier
            with self.assertRaisesRegex(ValueError, "stored asset"):
                validate_review(review, by_id={self.item["id"]: self.item})

    def test_illustrations_reject_remote_and_active_content_and_missing_rights(self):
        for code, language in [(".x{background:url(https://example.org/image)}", "css"),
                               ("@import 'https://example.org/source.css';", "css"),
                               ('<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>', "svg"),
                               ('<svg xmlns="http://www.w3.org/2000/svg"><use href="https://example.org/x"/></svg>', "svg"),
                               ('<!DOCTYPE svg><svg/>', "svg")]:
            review = deepcopy(self.review)
            review["preview"].update(code=code, language=language)
            review["preview"].pop("dom", None)
            with self.assertRaises(ValueError): validate_review(review)
        review = deepcopy(self.review)
        review["preview"]["license"] = "MIT"
        with self.assertRaises(ValueError): validate_review(review)

    def test_svg_local_quoted_gradient_survives_validation(self):
        review = deepcopy(self.review)
        review["preview"].pop("dom")
        review["preview"].update(language="svg", code='<svg xmlns="http://www.w3.org/2000/svg"><defs><linearGradient id="g"/></defs><rect width="10" height="10" fill="url(&quot;#g&quot;)"/></svg>')
        validate_review(review)

    def test_metadata_only_evidence_cannot_claim_high_confidence(self):
        review = deepcopy(self.review)
        review["evidence"]["basis"] = "metadata"
        with self.assertRaisesRegex(ValueError, "low confidence"):
            validate_review(review)
        review["evidence"]["confidence"] = "low"
        validate_review(review)

    def test_css_dom_cannot_exceed_renderer_children_total_or_ascii_classes(self):
        for dom in [{"tag": "div", "children": [{"tag": "span"}] * 33},
                    {"tag": "div", "children": [{"tag": "div", "children": [{"tag": "span"}] * 32}] * 2},
                    {"tag": "div", "className": "part한국"}]:
            review = deepcopy(self.review)
            review["preview"]["dom"] = dom
            with self.assertRaisesRegex(ValueError, "exact node/class bounds"):
                validate_review(review)

    def test_confirmed_removed_reference_cannot_be_retrieved_or_replace_stored_asset(self):
        stored = source("code", "stored-fixture")
        decision = {"id": self.item["id"], "sourceSha256": source_sha256(self.item),
                    "reason": "Confirmed missing source", "status": "broken-link", "verifiedAt": "2026-10-09",
                    "evidence": [self.artifact]}
        policy = {"version": 1, "removed": [decision]}
        self.assertEqual(apply_reference_removals([self.item, stored], policy, root=self.root), [stored])
        bad = deepcopy(policy)
        bad["removed"][0].update(id=stored["id"], sourceSha256=source_sha256(stored))
        with self.assertRaisesRegex(ValueError, "original link"):
            apply_reference_removals([self.item, stored], bad, root=self.root)
        (self.root / "data/imported-items.json").write_text(json.dumps([self.item, stored]), encoding="utf-8")
        (self.root / "data/reference-removals.json").write_text(json.dumps(policy), encoding="utf-8")
        stats = build(self.root)
        self.assertEqual(stats["storedAssets"], 1)
        self.assertEqual(stats["total"], 1)
        self.assertIsNone(Catalog(self.root).get(self.item["id"]))
        self.assertEqual(Catalog(self.root).search(kind="reference")["total"], 0)
        self.assertEqual(verify(self.root, minimum=1, minimum_stored=1)["total"], 1)

    def test_reference_annotation_never_inflates_stored_assets_and_is_searchable(self):
        (self.root / "data/imported-items.json").write_text(json.dumps([self.item, source("code", "stored-fixture")]), encoding="utf-8")
        (self.root / "data/reference-review-cha.json").write_text(json.dumps({"version": 1, "reviews": [self.review]}), encoding="utf-8")
        stats = build(self.root)
        self.assertEqual(stats["total"], 2)
        self.assertEqual(stats["storedAssets"], 1)
        self.assertEqual(stats["referenceReview"]["localPreviews"], 1)
        result = Catalog(self.root).search(kind="reference", asset_type="typography", effect="fade")
        self.assertEqual(result["total"], 1)
        self.assertIsNone(result["items"][0]["code"])
        self.assertEqual(Catalog(self.root).search(domain="motion")["total"], 1)
        self.assertEqual(verify(self.root, minimum=1, minimum_stored=1)["storedAssets"], 1)


if __name__ == "__main__":
    unittest.main()
