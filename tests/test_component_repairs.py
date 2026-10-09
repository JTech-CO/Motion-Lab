"""Static source-composition checks; these do not claim browser playback."""

import copy
from pathlib import Path
import re
import unittest

from scripts.repair_components import ROOT, build_repairs, read_source, verify_overlay


class ComponentRepairTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.overlay = build_repairs(ROOT)
        cls.repairs = {item["id"]: item for item in cls.overlay["repairs"]}

    def test_saved_overlay_is_exact_and_offline_reproducible(self):
        result = verify_overlay(ROOT)
        self.assertEqual(result["repairs"], 3)
        self.assertEqual(result["absorbedDependentKeyframes"], 5)
        self.assertFalse(result["browserExecutionVerified"])

    def test_full_original_fragments_and_notices_remain_exact(self):
        for repair in self.repairs.values():
            source_key = "spinkit" if repair["id"].startswith("spinkit") else "three-dots"
            source, manifest, notice = read_source(ROOT, source_key)
            raw = source.encode("utf-8")
            for evidence in repair["sourceFragments"]:
                fragment = raw[evidence["startUtf8Byte"]:evidence["endUtf8Byte"]].decode("utf-8")
                self.assertIn(fragment, repair["replacement"]["code"])
            self.assertEqual(repair["replacement"]["licenseText"], notice)
            self.assertIn(notice, repair["replacement"]["code"])
            self.assertEqual(repair["originalSourceSha256"], manifest["sha256"])

    def test_distinct_six_dot_chase_and_two_dot_swing(self):
        chase = self.repairs["spinkit-sk-chase"]["replacement"]
        swing = self.repairs["spinkit-sk-swing"]["replacement"]
        self.assertEqual(len(chase["preview"]["dom"]["children"]), 6)
        self.assertEqual(len(swing["preview"]["dom"]["children"]), 2)
        self.assertIn("animation: sk-chase 2.5s infinite linear both;", chase["code"])
        self.assertIn("animation: sk-chase-dot 2.0s infinite ease-in-out both;", chase["code"])
        self.assertIn("animation: sk-swing 1.8s infinite linear;", swing["code"])
        self.assertIn("animation: sk-swing-dot 2s infinite ease-in-out;", swing["code"])
        self.assertNotIn(".motion-sample", chase["code"] + swing["code"])
        self.assertEqual(chase["preview"]["variables"], {"--sk-size": "40px", "--sk-color": "#333"})
        self.assertEqual(swing["preview"]["variables"], chase["preview"]["variables"])
        self.assertNotEqual(chase["code"], swing["code"])

    def test_chase_original_dom_matches_author_sample(self):
        source, _, _ = read_source(ROOT, "spinkit")
        for parent, child, count in (("sk-chase", "sk-chase-dot", 6), ("sk-swing", "sk-swing-dot", 2)):
            sample = re.search(r'<div class="' + parent + r'">([\s\S]*?)\n      </div>', source).group(1)
            self.assertEqual(sample.count(f'<div class="{child}"></div>'), count)

    def test_falling_preserves_three_dots_timing_and_cancels_large_offsets(self):
        repair = self.repairs["three-dots-dot-falling"]
        replacement = repair["replacement"]
        code = replacement["code"]
        self.assertEqual(replacement["preview"]["dom"], {"tag": "div", "className": "dot-falling"})
        self.assertEqual(set(replacement["preview"]["keyframes"]),
                         {"dot-falling", "dot-falling-before", "dot-falling-after"})
        for name in replacement["preview"]["keyframes"]:
            self.assertIn(f"animation: {name} 1s infinite linear;", code)
        for delay in ("0s", "0.1s", "0.2s"):
            self.assertIn(f"animation-delay: {delay};", code)
        self.assertIn("left: -9999px;", code)
        self.assertIn(".dot-falling::before, .dot-falling::after", code)
        evidence = repair["evidence"]
        self.assertEqual([evidence["anchorLeftPx"] + shadow for shadow in evidence["sourceShadowXOffsetsPx"]],
                         evidence["apparentDotXOffsetsPx"])
        self.assertEqual(evidence["hostAdaptations"], [])
        self.assertEqual(set(repair["absorbedIds"]),
                         {"three-dots-dot-falling-before", "three-dots-dot-falling-after"})

    def test_overlay_changes_fail_closed_and_paths_are_allowlisted(self):
        changed = copy.deepcopy(self.overlay)
        changed["repairs"][0]["replacement"]["preview"]["dom"]["children"].pop()
        with self.assertRaisesRegex(ValueError, "differs from exact"):
            verify_overlay(ROOT, changed)
        with self.assertRaisesRegex(ValueError, "Unknown repair source"):
            read_source(Path("."), "../../secret")


if __name__ == "__main__":
    unittest.main()
