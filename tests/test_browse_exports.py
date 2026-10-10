"""Exercise lossless browser retrieval, search projections and bounded file writes."""

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from scripts.analyze import analyze_item
from scripts.browse_exports import (MAX_DETAIL_BYTES, MAX_DETAIL_ITEMS, browse_documents,
                                   verify_browse_exports, write_browse_exports)


def entry(identifier, code=".sample { animation: pulse 1s infinite; }"):
    asset = {"id": identifier, "title": "Pulse " + identifier, "description": "Source description 설명",
             "category": "animation", "kind": "code", "language": "css", "tags": ["source-tag"],
             "sourceName": "Fixture", "sourceUrl": "https://example.org/" + identifier,
             "license": "MIT", "licenseText": "Complete, original permission notice",
             "code": code, "preview": {"type": "css", "variant": "pulse"}, "colors": [],
             "provenance": {"receipt": "source-proof"}, "evidence": {"raw": "untouched"}}
    asset["analysis"] = analyze_item(asset)
    return asset


def catalog(items):
    return {"version": 1, "updatedAt": "2026-10-11", "stats": {"total": len(items)},
            "sources": [{"name": "Fixture"}], "aliases": {}, "items": items}


class BrowserExportTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        (self.root / "dist").mkdir()

    def test_discovery_search_and_original_variants_are_lossless(self):
        first, variant = entry("canonical"), entry("merged")
        variant.update(title="Variant-only title", description="variant-only description",
                       sourceName="Variant-only provider", license="Variant-only license", tags=["variant-only tag"])
        first["analysis"]["properties"] = ["searchable-property"]
        first["analysis"]["evidence"]["signals"] = ["searchable-proof"]
        first.update(variants=[deepcopy(first), variant], aliases=["merged"],
                     consolidation={"variantCount": 1, "variantRoles": {"canonical": "asset", "merged": "component-part"}})
        full = catalog([first])
        full["aliases"] = {"merged": "canonical"}
        write_browse_exports(self.root, full)
        self.assertEqual(verify_browse_exports(self.root, full)["detailShards"], 1)
        browse = json.loads((self.root / "dist/catalog-browse.json").read_bytes())
        projected = browse["items"][0]
        self.assertNotIn("code", projected)
        self.assertNotIn("licenseText", projected)
        for term in ("source-tag", "variant-only description", "Variant-only license",
                     "Variant-only provider", "Variant-only title", "variant-only tag",
                     "searchable-property", "searchable-proof", "merged"):
            self.assertIn(term, projected["searchText"])
        for facet in ("domain", "assetType", "effects", "components", "useCases", "techniques"):
            self.assertEqual(projected["analysis"][facet], first["analysis"][facet])
        self.assertEqual(projected["variantCount"], 1)
        self.assertEqual(browse["aliases"], full["aliases"])
        self.assertEqual(browse["sources"], full["sources"])
        restored = json.loads((self.root / "dist" / projected["detailShard"]).read_bytes())["items"]
        self.assertEqual(restored, [first])

    def test_reference_classification_preview_dependency_and_search_survive(self):
        asset = entry("reference")
        asset.update(kind="reference", language="link", code=None)
        asset["analysis"]["domain"] = None
        review = {"targetDomain": "mixed", "resourceType": "collection", "assetType": "transition",
                  "effects": ["mask"], "components": ["image"], "useCases": ["scene-change"],
                  "evidence": {"basis": "reviewed-source", "confidence": "high", "signals": ["review-proof"],
                               "summaryKO": "검토 검색어", "summaryEN": "Reviewed search term"},
                  "preview": {"mode": "related-asset", "assetId": "related", "notice": "Original preview notice"}}
        asset["referenceReview"] = review
        browse, shards, _ = browse_documents(catalog([asset, entry("related")]))
        projected = json.loads(browse)["items"][0]
        for key in ("targetDomain", "resourceType", "assetType", "effects", "components", "useCases"):
            self.assertEqual(projected["referenceReview"][key], review[key])
        self.assertEqual(projected["referenceReview"]["preview"],
                         {"mode": "related-asset", "assetId": "related", "domain": "design"})
        for term in ("review-proof", "검토 검색어", "Reviewed search term"):
            self.assertIn(term, projected["searchText"])
        self.assertEqual(json.loads(shards[projected["detailShard"]])["items"][0], asset)

    def test_reference_motion_metadata_matches_original_browser_preview(self):
        cases = (("css", "@keyframes breathe {to {opacity:0}}", "motion"),
                 ("css", ".card {transition: opacity 1s}", "motion"),
                 ("css", ".card {animation-duration: 1s}", "motion"),
                 ("css", ".card {background: cyan}", "design"),
                 ("svg", '<svg><animateTransform attributeName="transform"/></svg>', "motion"),
                 ("svg", '<svg><set attributeName="fill" to="cyan"/></svg>', "motion"),
                 ("svg", '<svg><circle r="5"/></svg>', "design"))
        for language, code, domain in cases:
            with self.subTest(language=language, code=code):
                asset = entry("reference")
                asset.update(kind="reference", language="link", code=None)
                asset["analysis"]["domain"] = None
                asset["referenceReview"] = {
                    "targetDomain": "motion", "resourceType": "example", "assetType": "animation",
                    "effects": [], "components": [], "useCases": [],
                    "evidence": {"basis": "reviewed-source", "confidence": "high"},
                    "preview": {"mode": "illustration", "language": language, "code": code}}
                browse, shards, _ = browse_documents(catalog([asset]))
                projected = json.loads(browse)["items"][0]
                self.assertEqual(projected["referenceReview"]["preview"]["domain"], domain)
                self.assertNotIn("code", projected["referenceReview"]["preview"])
                self.assertEqual(json.loads(shards[projected["detailShard"]])["items"][0], asset)
        related = entry("related-static", ".sample {background: cyan}")
        related["analysis"]["domain"] = "design"
        asset["referenceReview"]["preview"] = {"mode": "related-asset", "assetId": "related-static"}
        browse, _, _ = browse_documents(catalog([asset, related]))
        self.assertEqual(json.loads(browse)["items"][0]["referenceReview"]["preview"]["domain"], "design")
        with self.assertRaisesRegex(ValueError, "no classified local asset"):
            browse_documents(catalog([asset]))

    def test_byte_and_record_limits_and_content_addressing(self):
        full = catalog([entry("record-" + str(index)) for index in range(MAX_DETAIL_ITEMS + 1)])
        browse, shards, _ = browse_documents(full)
        manifest = json.loads(browse)["detailShards"]
        self.assertEqual([shard["count"] for shard in manifest], [MAX_DETAIL_ITEMS, 1])
        large = catalog([entry("large-one", "/*" + "x" * 270000 + "*/"),
                         entry("large-two", "/*" + "y" * 270000 + "*/")])
        browse, shards, _ = browse_documents(large)
        self.assertEqual(len(shards), 2)
        for shard in json.loads(browse)["detailShards"]:
            body = shards[shard["path"]]
            self.assertLessEqual(len(body), MAX_DETAIL_BYTES)
            self.assertEqual(shard["bytes"], len(body))
            self.assertEqual(shard["sha256"], hashlib.sha256(body).hexdigest())
            self.assertEqual(Path(shard["path"]).stem, shard["sha256"])
        with self.assertRaisesRegex(ValueError, "exceeds"):
            browse_documents(catalog([entry("too-large", "x" * MAX_DETAIL_BYTES)]))

    def test_home_transition_is_the_complete_source_and_rebuild_removes_only_stale_shards(self):
        transition = entry("gl-transitions-drop-zone-flicker", "original shader source")
        old = catalog([transition, entry("removed")])
        write_browse_exports(self.root, old)
        original_paths = set((self.root / "dist/catalog-details").iterdir())
        self.assertEqual(json.loads((self.root / "dist/home-transition.json").read_bytes())["item"], transition)
        new = catalog([transition])
        write_browse_exports(self.root, new)
        current_paths = set((self.root / "dist/catalog-details").iterdir())
        self.assertFalse(original_paths.intersection(current_paths))
        self.assertEqual(verify_browse_exports(self.root, new)["detailShards"], 1)
        before = {path: path.read_bytes() for path in current_paths}
        write_browse_exports(self.root, new)
        self.assertEqual(before, {path: path.read_bytes() for path in current_paths})

    def test_source_corruption_is_detected_and_unknown_files_are_never_removed(self):
        full = catalog([entry("sample")])
        write_browse_exports(self.root, full)
        shard = next((self.root / "dist/catalog-details").iterdir())
        body = shard.read_text(encoding="utf-8").replace("original permission", "altered permission")
        shard.write_text(body, encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "changed code"):
            verify_browse_exports(self.root, full)
        sentinel = shard.parent / "keep.txt"
        sentinel.write_text("user document", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "unexpected"):
            write_browse_exports(self.root, catalog([]))
        self.assertEqual(sentinel.read_text(), "user document")
        self.assertTrue(shard.exists())

    def test_linked_detail_files_are_rejected_before_writing(self):
        write_browse_exports(self.root, catalog([entry("sample")]))
        outside = self.root / "not-public.json"
        outside.write_text("private", encoding="utf-8")
        linked = self.root / "dist/catalog-details" / ("0" * 64 + ".json")
        try:
            linked.hardlink_to(outside)
        except OSError as error:
            self.skipTest(f"Filesystem does not support hard links: {error}")
        with self.assertRaisesRegex(ValueError, "linked"):
            write_browse_exports(self.root, catalog([]))
        self.assertEqual(outside.read_text(), "private")
        self.assertTrue(linked.exists())


if __name__ == "__main__":
    unittest.main()
