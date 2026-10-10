"""Reviewed grouping preserves licensed originals and rejects stale policies."""

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from scripts.analyze import analyze_items
from scripts.consolidate import apply_consolidation, record_sha
from scripts.repair_components import ROOT, build_repairs
from scripts.build import build, write_static_exports
from scripts.verify_catalog import original_record_views, verify


def item(identifier, code=None, colors=None, notice="Complete original MIT notice"):
    kind = "palette" if colors is not None else "code"
    return {"id": identifier, "title": identifier, "description": "Original stored asset",
            "sourceName": "Original " + identifier, "sourceUrl": "https://example.org/" + identifier,
            "license": "MIT", "licenseUrl": "https://example.org/" + identifier + "/LICENSE",
            "licenseText": notice, "verifiedAt": "2026-10-08", "verification": "fixture",
            "category": "palette" if kind == "palette" else "animation", "kind": kind,
            "language": "json" if kind == "palette" else "css", "access": "public", "tags": ["fixture"],
            "preview": {"type": "palette" if kind == "palette" else "css", "variant": identifier},
            "code": json.dumps(colors) if kind == "palette" else code or ".sample {opacity: .5}",
            "colors": colors or []}


def group(items, mode="exact", canonical=None):
    return {"id": canonical or items[0]["id"], "ids": [entry["id"] for entry in items], "mode": mode,
            "expectedCodeSha256": {entry["id"]: hashlib.sha256((entry.get("code") or "").encode("utf-8")).hexdigest()
                                   for entry in items},
            "expectedRecordSha256": {entry["id"]: record_sha(entry) for entry in items},
            "relations": [{"basis": "reviewed-source-structure"}]}


def policy(*groups):
    return {"version": 1, "groups": list(groups)}


class ConsolidationTests(unittest.TestCase):
    def test_empty_policy_preserves_unmerged_fixture(self):
        entries = analyze_items([item("one"), item("two", ".sample {opacity:1}")])
        before = deepcopy(entries)
        output, aliases, report = apply_consolidation(entries, policy())
        self.assertEqual(output, before)
        self.assertEqual(aliases, {})
        self.assertEqual(report["before"], report["after"])
        self.assertEqual(entries, before)

    def test_exact_group_keeps_every_original_notice_and_provenance(self):
        entries = analyze_items([item("one", "/* one */ .a {opacity:.5}", notice="Original holder one"),
                                 item("two", "/* two */ .b {opacity:.5}", notice="Original holder two"),
                                 item("three", ".c {opacity:1}")])
        originals = deepcopy(entries)
        output, aliases, report = apply_consolidation(entries, policy(group(entries[:2])))
        self.assertEqual([entry["id"] for entry in output], ["one", "three"])
        self.assertEqual(aliases, {"two": "one"})
        self.assertEqual(output[0]["variants"], originals[:2])
        self.assertEqual(output[0]["consolidation"]["variantRoles"], {"one": "exact-source", "two": "exact-source"})
        self.assertEqual(report["originalIdentitiesPreserved"], 3)
        self.assertEqual(report["removedByMode"], {"exact": 1})
        self.assertFalse(report["browserExecutionVerified"])
        self.assertEqual(entries, originals)
        recovered, parents = original_record_views(output, aliases)
        self.assertEqual(recovered["two"], originals[1])
        self.assertEqual(len(parents), 1)

    def test_motion_variants_keep_different_durations_and_frames(self):
        entries = analyze_items([item("one", "@keyframes pulse {50% {opacity:0}} .a {animation:pulse 1s}"),
                                 item("two", "@keyframes pulse {51% {opacity:0}} .a {animation:pulse 2s}")])
        output, _, _ = apply_consolidation(entries, policy(group(entries, "motion")))
        self.assertEqual([variant["code"] for variant in output[0]["variants"]], [entry["code"] for entry in entries])
        self.assertEqual(output[0]["consolidation"]["variantCount"], 2)
        self.assertFalse(output[0]["consolidation"]["allMembersPairwiseEquivalent"])

    def test_palette_family_keeps_order_alpha_and_original_arrays(self):
        arrays = [["#ff0000", "#00000000"], ["#00000000", "#ff0000"], ["#ff0100", "#00000080"]]
        entries = analyze_items([item(identity, colors=colors, notice="Notice " + identity)
                                 for identity, colors in zip(("one", "two", "three"), arrays)])
        output, aliases, report = apply_consolidation(entries, policy(group(entries, "palette")))
        self.assertEqual(len(output), 1)
        self.assertEqual(aliases, {"two": "one", "three": "one"})
        self.assertEqual([variant["colors"] for variant in output[0]["variants"]], arrays)
        self.assertEqual([json.loads(variant["code"]) for variant in output[0]["variants"]], arrays)
        self.assertEqual([variant["licenseText"] for variant in output[0]["variants"]], ["Notice one", "Notice two", "Notice three"])
        self.assertEqual(output[0]["consolidation"]["groupingBasis"], "reviewed-connected-family")
        self.assertTrue(report["originalPaletteArraysPreserved"])

    def test_stale_incomplete_hashes_and_overlapping_groups_fail_closed(self):
        entries = analyze_items([item("one"), item("two"), item("three")])
        stale = group(entries[:2])
        stale["expectedCodeSha256"]["two"] = "0" * 64
        for rejected in (policy(stale), policy(group(entries[:2]), group(entries[1:])),
                         policy(group(entries[:2], canonical="two"))):
            with self.assertRaises(ValueError):
                apply_consolidation(entries, rejected)
        missing_hash = group(entries[:2])
        missing_hash["expectedCodeSha256"].pop("two")
        with self.assertRaises(ValueError):
            apply_consolidation(entries, policy(missing_hash))
        for field, value in (("preview", {"type": "css", "variant": "changed-dom"}),
                             ("licenseText", "Changed copyright holder")):
            reviewed = policy(group(entries[:2]))
            changed = deepcopy(entries)
            changed[1][field] = value
            with self.assertRaisesRegex(ValueError, "context or notice changed"):
                apply_consolidation(changed, reviewed)
        self.assertNotIn("variants", entries[0])

    def test_policy_bounds_kinds_and_recursive_groups_are_rejected(self):
        entries = analyze_items([item("one"), item("two", colors=["#ffffff", "#000000"])])
        for rejected in (policy(group(entries, "palette")), policy(group(entries, "unknown")),
                         policy(group(entries[:1])), {"version": 2, "groups": []}):
            with self.assertRaises(ValueError):
                apply_consolidation(entries, rejected)
        many = [item(f"item-{number}") for number in range(65)]
        with self.assertRaises(ValueError):
            apply_consolidation(many, policy(group(many)))
        recursive = deepcopy(entries)
        recursive[0]["variants"] = []
        with self.assertRaises(ValueError):
            apply_consolidation(recursive, policy())

    def test_real_complete_component_repairs_keep_old_records_as_parts(self):
        repairs = build_repairs(ROOT)
        required = {identity for repair in repairs["repairs"] for identity in [repair["id"], *repair["absorbedIds"]]}
        imported = json.loads((ROOT / "data/imported-items.json").read_text(encoding="utf-8"))
        entries = analyze_items([entry for entry in imported if entry["id"] in required])
        groups = []
        for repair in repairs["repairs"]:
            members = [entry for entry in entries if entry["id"] in {repair["id"], *repair["absorbedIds"]}]
            groups.append(group(members, "component", repair["id"]))
        output, aliases, report = apply_consolidation(entries, policy(*groups), repairs)
        self.assertEqual(len(output), 3)
        self.assertEqual(len(aliases), 5)
        self.assertEqual(report["repairedCompositions"], 3)
        self.assertEqual(report["variantRecords"], 8)
        self.assertEqual(report["renderableVariants"], 3)
        recovered, _ = original_record_views(output, aliases)
        self.assertEqual(recovered, {entry["id"]: entry for entry in entries})
        old = {entry["id"]: entry for entry in entries}
        repair_by_id = {repair["id"]: repair for repair in repairs["repairs"]}
        for parent in output:
            self.assertEqual(parent["repair"]["originalRecord"], old[parent["id"]])
            self.assertEqual(parent["code"], repair_by_id[parent["id"]]["replacement"]["code"])
            self.assertEqual(parent["consolidation"]["variantCount"], 1)
            self.assertNotIn("repair", parent["variants"][0])
            for alias in parent["aliases"]:
                self.assertEqual(parent["consolidation"]["variantRoles"][alias], "component-part")

    def test_missing_unused_or_unapproved_component_repair_is_rejected(self):
        entries = analyze_items([item("one"), item("two")])
        reviewed = policy(group(entries, "component"))
        with self.assertRaisesRegex(ValueError, "must be an object"):
            apply_consolidation(entries, reviewed, {"version": 1, "repairs": [None]})
        with self.assertRaises(ValueError):
            apply_consolidation(entries, reviewed)
        repair = {"id": "one", "expectedCodeSha256": group(entries)["expectedCodeSha256"]["one"],
                  "absorbedIds": ["two"], "expectedAbsorbedCodeSha256": {"two": group(entries)["expectedCodeSha256"]["two"]},
                  "replacement": {"code": ".a {opacity:1}", "preview": {"type": "css", "variant": "one"},
                                  "description": "Complete source", "licenseText": "Original notice", "colors": []}}
        unused = {"version": 1, "repairs": [repair]}
        with self.assertRaises(ValueError):
            apply_consolidation(entries, policy(), unused)
        unapproved = deepcopy(unused)
        unapproved["repairs"][0]["replacement"]["sourceUrl"] = "https://unexpected.example.org"
        with self.assertRaises(ValueError):
            apply_consolidation(entries, reviewed, unapproved)
        stale_part = deepcopy(unused)
        stale_part["repairs"][0]["expectedAbsorbedCodeSha256"]["two"] = "0" * 64
        with self.assertRaises(ValueError):
            apply_consolidation(entries, reviewed, stale_part)

    def test_record_views_reject_changed_code_counts_and_nested_metadata(self):
        entries = analyze_items([item("one", colors=["#ffffff", "#000000"]),
                                 item("two", colors=["#fffffe", "#000000"])])
        output, aliases, _ = apply_consolidation(entries, policy(group(entries, "palette")))
        for mutate in (lambda data: data[0]["variants"][1].update(code='["#ff0000"]'),
                       lambda data: data[0]["variants"][1].update(variants=[]),
                       lambda data: data[0]["consolidation"].update(variantCount=1)):
            changed = deepcopy(output)
            mutate(changed)
            with self.assertRaises(ValueError):
                original_record_views(changed, aliases)
        with self.assertRaises(ValueError):
            original_record_views(output, {"two": "missing"})

    def test_verifier_keeps_unmerged_build_fixture_compatible(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "tests") as directory:
            fixture = Path(directory)
            (fixture / "data").mkdir()
            (fixture / "dist").mkdir()
            originals = [item("one"), item("two", ".sample {opacity:1}")]
            (fixture / "data/imported-items.json").write_text(json.dumps(originals), encoding="utf-8")
            build(fixture)
            result = verify(fixture, minimum=1)
            self.assertEqual(result["total"], 2)
            self.assertEqual(result["originalIdentities"], 2)
            self.assertEqual(result["aliases"], 0)

    def test_full_verifier_checks_merged_alias_original_notices(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "tests") as directory:
            fixture = Path(directory)
            (fixture / "data").mkdir()
            (fixture / "dist").mkdir()
            originals = [item("one", colors=["#ffffff", "#00000000"], notice="Holder one"),
                         item("two", colors=["#fffffe", "#00000080"], notice="Holder two")]
            (fixture / "data/imported-items.json").write_text(json.dumps(originals), encoding="utf-8")
            (fixture / "data/consolidation-policy.json").write_text(
                json.dumps(policy(group(originals, "palette"))), encoding="utf-8")
            build(fixture)
            result = verify(fixture, minimum=1)
            self.assertEqual(result["total"], 1)
            self.assertEqual(result["originalIdentities"], 2)
            self.assertEqual(result["aliases"], 1)
            self.assertEqual(result["variantRecords"], 2)
            first_output = (fixture / "data/catalog.json").read_bytes()
            build(fixture)
            self.assertEqual((fixture / "data/catalog.json").read_bytes(), first_output)
            self.assertEqual(verify(fixture, minimum=1)["total"], 1)
            # License text is not part of the code hash; full-source comparison
            # must still catch an accidentally lost notice in a preserved alias.
            path = fixture / "data/catalog.json"
            catalog = json.loads(path.read_text(encoding="utf-8"))
            catalog["items"][0]["variants"][1]["licenseText"] = "Lost notice"
            path.write_text(json.dumps(catalog), encoding="utf-8")
            # Keep browser exports consistent so this exercises source-provenance
            # validation even when every published copy loses the same notice.
            write_static_exports(fixture, catalog)
            with self.assertRaisesRegex(ValueError, "Original input fields or notices changed"):
                verify(fixture, minimum=1)



if __name__ == "__main__":
    unittest.main()
