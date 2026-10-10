"""Stored script provenance, reviewed classification and non-executable previews."""

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from motionlab.catalog import Catalog
from motionlab.source_review import (ILLUSTRATION_LIMITATION, UNEXECUTED_LIMITATION,
                                    validate_source_review)
from scripts.analyze import analyze_item
from scripts.browse_exports import browse_documents
from scripts.build import build, validate_item
from scripts.verify_catalog import verify


def fixture(root):
    original = root / "data/upstream/expansion12-promptfilm/engine.js"
    original.parent.mkdir(parents=True, exist_ok=True)
    source = "// header\r\nfunction move(mesh, t) {\r\n  mesh.position.x = t;\r\n}\r\n// end\r\n"
    original.write_bytes(source.encode("utf-8"))
    code = "".join(source.splitlines(keepends=True)[1:4])
    notice = original.with_name("LICENSE")
    notice.write_bytes(b"Complete MIT fixture notice\nCopyright source author")
    digest = hashlib.sha256(code.encode("utf-8")).hexdigest()
    item = {"id": "promptfilm-move", "title": "Position interpolation",
            "description": "A reviewed motion function; THREE object input is required.",
            "sourceName": "Promptfilm", "sourceUrl": "https://github.com/Seokwoooo/promptfilm/blob/" + "1" * 40 + "/engine.js",
            "license": "MIT", "licenseText": notice.read_text(),
            "verifiedAt": "2026-10-11", "verification": "source-and-license-reviewed",
            "access": "public", "domain": "motion", "category": "animation", "kind": "code",
            "language": "javascript", "code": code, "tags": ["threejs"], "colors": [],
            "preview": {"type": "reference", "variant": "stored-javascript"},
            "collectionEvidence": {"version": 1,
                "original": {"path": original.relative_to(root).as_posix(), "sha256": hashlib.sha256(original.read_bytes()).hexdigest()},
                "notice": {"path": notice.relative_to(root).as_posix(), "sha256": hashlib.sha256(notice.read_bytes()).hexdigest()},
                "storedSha256": digest},
            "sourceReview": {"version": 1, "sourceSha256": digest, "revision": "1" * 40,
                "sourceRange": {"startLine": 2, "endLine": 4},
                "classification": {"domain": "motion", "assetType": "animation", "effects": ["slide"],
                    "components": ["shape"], "useCases": ["intro"], "techniques": ["transform"]},
                "evidence": {"basis": "reviewed-source", "confidence": "high",
                    "summaryKO": "원문에서 위치 보간을 확인했습니다.", "summaryEN": "Reviewed positional interpolation in source.",
                    "signals": ["mesh.position.x assignment uses the time input"]},
                "dependencies": ["THREE.Object3D", "caller-supplied time"],
                "limitations": ["Caller supplies the scene and update loop."],
                "preview": {"mode": "illustration", "language": "svg",
                    "code": '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 80 60"><circle cx="10" cy="30" r="5"><animate attributeName="cx" values="10;70;10" dur="3s" repeatCount="indefinite"/></circle></svg>',
                    "license": "CC0-1.0", "notice": "Independent Motion Lab illustration dedicated under CC0 1.0.",
                    "attribution": "Motion Lab", "limitations": ["Independent 2D illustration; no imported script execution."]}}}
    return item


class SourceReviewTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.item = fixture(self.root)

    def test_exact_crlf_source_and_separate_rights_survive_review(self):
        before = deepcopy(self.item)
        self.assertIs(validate_source_review(self.item, root=self.root), self.item["sourceReview"])
        self.assertIs(validate_item(self.item), self.item)
        result = analyze_item(self.item)
        self.assertEqual(self.item, before)
        self.assertEqual(result["domain"], "motion")
        self.assertEqual(result["effects"], ["slide"])
        self.assertEqual(result["evidence"]["basis"], "reviewed-source")
        self.assertEqual(result["preview"]["renderer"], "none")
        self.assertIn(UNEXECUTED_LIMITATION, result["preview"]["limitations"])
        self.assertIn(ILLUSTRATION_LIMITATION, result["preview"]["limitations"])
        self.assertEqual(self.item["license"], "MIT")
        self.assertEqual(self.item["sourceReview"]["preview"]["license"], "CC0-1.0")

    def test_original_hash_line_range_and_exact_newlines_are_bound(self):
        for changed in (
            lambda item: item["sourceReview"]["sourceRange"].update(startLine=1),
            lambda item: item["sourceReview"]["sourceRange"].update(endLine=3),
            lambda item: item["sourceReview"].update(sourceSha256="0" * 64),
        ):
            item = deepcopy(self.item)
            changed(item)
            with self.subTest(item=item["sourceReview"]), self.assertRaises(ValueError):
                validate_source_review(item, root=self.root)
        item = deepcopy(self.item)
        item["code"] = item["code"].replace("\r\n", "\n")
        digest = hashlib.sha256(item["code"].encode()).hexdigest()
        item["sourceReview"]["sourceSha256"] = digest
        item["collectionEvidence"]["storedSha256"] = digest
        with self.assertRaisesRegex(ValueError, "range does not exactly"):
            validate_source_review(item, root=self.root)
        original = self.root / item["collectionEvidence"]["original"]["path"]
        original.write_bytes(original.read_bytes().replace(b"mesh.position.x", b"mesh.position.y"))
        with self.assertRaisesRegex(ValueError, "file digest"):
            validate_source_review(self.item, root=self.root)

    def test_source_shape_limits_vocabularies_and_safe_receipt_paths(self):
        mutations = [
            lambda item: item.pop("sourceReview"),
            lambda item: item.update(language="css"),
            lambda item: item.update(kind="reference"),
            lambda item: item["preview"].update(type="css"),
            lambda item: item["sourceReview"].update(version=True),
            lambda item: item["sourceReview"].update(revision="main"),
            lambda item: item["sourceReview"].update(unexpected=True),
            lambda item: item["sourceReview"]["sourceRange"].update(startLine=True),
            lambda item: item["sourceReview"]["sourceRange"].update(endLine=100001),
            lambda item: item["sourceReview"]["classification"].update(domain="tooling"),
            lambda item: item["sourceReview"]["classification"].update(effects=["arbitrary-js"]),
            lambda item: item["sourceReview"]["classification"].update(techniques=["eval"]),
            lambda item: item["sourceReview"]["evidence"].update(basis="code"),
            lambda item: item["sourceReview"]["evidence"].update(confidence="low"),
            lambda item: item["sourceReview"].update(dependencies=[str(i) for i in range(33)]),
            lambda item: item["sourceReview"].update(limitations=[]),
            lambda item: item["sourceReview"]["preview"].update(limitations=[]),
            lambda item: item["collectionEvidence"]["original"].update(path="data/upstream/expansion12-promptfilm/../../outside.js"),
            lambda item: item["collectionEvidence"]["original"].update(path="C:/outside.js"),
            lambda item: item["collectionEvidence"]["original"].update(path="data\\upstream\\engine.js"),
            lambda item: item["collectionEvidence"]["original"].update(sha256="x" * 64),
        ]
        for index, mutate in enumerate(mutations):
            item = deepcopy(self.item)
            mutate(item)
            with self.subTest(mutation=index), self.assertRaises(ValueError):
                validate_source_review(item)
        missing = deepcopy(self.item)
        missing.pop("sourceReview")
        with self.assertRaises(ValueError):
            validate_item(missing)

    def test_shared_illustration_validator_rejects_active_content_and_wrong_rights(self):
        previews = [
            {"language": "javascript"}, {"mode": "source"}, {"license": "MIT"},
            {"attribution": "Promptfilm"}, {"notice": ""}, {"code": "x" * 100001},
            {"code": '<svg><script>alert(1)</script></svg>'},
            {"code": '<svg><image href="https://example.org/image.png"/></svg>'},
            {"code": '<svg><rect onclick="alert(1)"/></svg>'},
            {"language": "css", "code": '.x{background:url(https://example.org/image.png)}'},
            {"language": "css", "code": '@import "https://example.org/style.css";'},
            {"language": "css", "code": '.x{opacity:1}', "dom": {"tag": "script"}},
        ]
        for index, changes in enumerate(previews):
            item = deepcopy(self.item)
            item["sourceReview"]["preview"].update(changes)
            with self.subTest(preview=index), self.assertRaises(ValueError):
                validate_source_review(item)

    def test_originals_and_notices_fit_lossless_browser_utf16_limits(self):
        for field, value in (("code", "a" * 300001), ("code", "\U0001f600" * 150001),
                             ("licenseText", "n" * 120001),
                             ("licenseText", "\U0001f600" * 60001), ("code", "\ud800")):
            item = deepcopy(self.item)
            item[field] = value
            with self.subTest(field=field, size=len(value)), self.assertRaises(ValueError):
                validate_source_review(item)

    def test_notice_file_change_and_missing_license_fail_closed(self):
        item = deepcopy(self.item)
        item["licenseText"] = "Different license"
        with self.assertRaisesRegex(ValueError, "license notice"):
            validate_source_review(item, root=self.root)
        item["licenseText"] = ""
        with self.assertRaises(ValueError):
            validate_source_review(item)
        notice = self.root / self.item["collectionEvidence"]["notice"]["path"]
        notice.write_bytes(b"A changed notice")
        with self.assertRaisesRegex(ValueError, "file digest"):
            validate_source_review(self.item, root=self.root)

    def test_browser_projection_keeps_discovery_and_lossless_source_separate(self):
        full = {**self.item, "analysis": analyze_item(self.item)}
        browse, shards, _ = browse_documents({"version": 1, "updatedAt": "2026-10-11", "stats": {"total": 1},
                                              "sources": [], "aliases": {}, "items": [full]})
        projected = json.loads(browse)["items"][0]
        self.assertEqual(projected["analysis"]["domain"], full["analysis"]["domain"])
        self.assertEqual(projected["analysis"]["effects"], full["analysis"]["effects"])
        self.assertEqual(projected["sourceReview"], {"preview": {"mode": "illustration", "domain": "motion"}})
        for term in ("THREE.Object3D", "caller-supplied time", "Caller supplies the scene", "위치 보간", "positional interpolation"):
            self.assertIn(term, projected["searchText"])
        self.assertNotIn("code", projected)
        self.assertNotIn("licenseText", projected)
        self.assertNotIn(self.item["sourceReview"]["preview"]["code"], browse.decode())
        self.assertEqual(json.loads(shards[projected["detailShard"]])["items"], [full])

    def test_build_sqlite_and_full_verifier_keep_original_notices_and_reviewed_facets(self):
        (self.root / "data/expansion12-promptfilm-items.json").write_text(json.dumps([self.item]), encoding="utf-8")
        self.assertEqual(build(self.root)["total"], 1)
        catalog = Catalog(self.root)
        saved = catalog.get(self.item["id"])
        self.assertEqual(saved["code"], self.item["code"])
        self.assertEqual(saved["sourceReview"], self.item["sourceReview"])
        self.assertEqual(saved["licenseText"], self.item["licenseText"])
        self.assertEqual(catalog.search(effect="slide", component="shape", basis="reviewed-source")["total"], 1)
        self.assertEqual(catalog.search(query="caller-supplied time")["total"], 1)
        self.assertEqual(verify(self.root, minimum=1)["codeLanguages"], {"javascript": 1})
        original = self.root / self.item["collectionEvidence"]["original"]["path"]
        original.write_bytes(original.read_bytes().replace(b"mesh.position.x", b"mesh.position.y"))
        with self.assertRaises(ValueError):
            build(self.root)


if __name__ == "__main__":
    unittest.main()
