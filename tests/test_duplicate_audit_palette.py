import itertools
import unittest

from scripts.duplicate_audit_palette import audit, audit_color_representations, canonical_color, minimum_assignment


def palette(identity, colors, **extra):
    return {"id": identity, "title": identity, "kind": "palette", "colors": colors,
            "sourceName": "test", "sourceUrl": "https://example.com/palette", "code": "[]", **extra}


class PaletteAuditTests(unittest.TestCase):
    def test_exact_normalizes_notation_but_preserves_alpha(self):
        report = audit([palette("a", ["#f00", "#abcdef"]),
                        palette("b", ["#FF0000ff", "#ABCDEF"]),
                        palette("c", ["#ff000000", "#abcdef"])])
        self.assertEqual(report["exactGroups"][0]["ids"], ["a", "b"])
        self.assertEqual(report["coverage"]["comparedPairs"], 3)
        self.assertFalse(report["nearGroups"])
        self.assertEqual(canonical_color("#1234"), "#11223344")

    def test_reverse_and_permutation_are_families_not_ordered_duplicates(self):
        report = audit([palette("a", ["#ff0000", "#00ff00", "#0000ff"]),
                        palette("b", ["#0000ff", "#00ff00", "#ff0000"]),
                        palette("c", ["#00ff00", "#ff0000", "#0000ff"])])
        self.assertFalse(report["exactGroups"])
        self.assertFalse(report["nearGroups"])
        group = report["familyGroups"][0]
        self.assertEqual(group["reason"], "same-rgba-multiset-different-order")
        self.assertEqual(group["ids"], ["a", "b", "c"])

    def test_strict_near_ordered_and_reordered(self):
        report = audit([palette("a", ["#ff0000", "#00ff00", "#0000ff"]),
                        palette("b", ["#fe0000", "#00fe00", "#0000fe"]),
                        palette("c", ["#00fe00", "#fe0000", "#0000fe"])])
        self.assertTrue(any(group["ids"] == ["a", "b"] for group in report["nearGroups"]))
        self.assertTrue(any(group["ids"] == ["a", "c"] for group in report["candidatePairs"]))
        self.assertFalse(report["exactGroups"])

    def test_matching_means_do_not_equate_different_colors(self):
        report = audit([palette("a", ["#ff0000", "#00ff00"]),
                        palette("b", ["#0000ff", "#ffff00"])])
        self.assertFalse(report["nearGroups"])
        self.assertFalse(report["candidatePairs"])

    def test_both_backgrounds_reject_alpha_solid_equivalence(self):
        # The transparent palette can look equal to white on white only.
        report = audit([palette("a", ["#ffffff00", "#ffffff00"]),
                        palette("b", ["#ffffff", "#ffffff"])])
        self.assertFalse(report["nearGroups"])
        self.assertFalse(report["exactGroups"])
        self.assertFalse(report["candidatePairs"])

    def test_multisets_count_repeated_swatches_and_subsets_are_only_families(self):
        report = audit([palette("a", ["#ff0000", "#ff0000", "#0000ff"]),
                        palette("b", ["#ff0000", "#0000ff", "#0000ff"]),
                        palette("c", ["#ff0000", "#0000ff"])])
        self.assertFalse(report["exactGroups"])
        self.assertFalse(report["nearGroups"])
        self.assertEqual(len(report["familyGroups"]), 2)
        self.assertTrue(all(group["reason"] == "exact-palette-multiset-subset"
                            for group in report["familyGroups"]))

    def test_hungarian_matches_bruteforce_and_does_not_greedily_reuse_colors(self):
        costs = [[1, 2, 20], [1, 5, 30], [30, 1, 1]]
        assignment = minimum_assignment(costs)
        result = sum(costs[i][assignment[i]] for i in range(3))
        expected = min(sum(costs[i][order[i]] for i in range(3))
                       for order in itertools.permutations(range(3)))
        self.assertEqual(result, expected)
        self.assertEqual(len(set(assignment)), 3)

    def test_invalid_colors_bounded_and_reported_not_executed(self):
        report = audit([palette("bad", ["url(https://example.com)", "#fff"]),
                        palette("large", ["#fff"]*33), palette("good", ["#fff", "#000"])])
        self.assertEqual(len(report["errors"]), 2)
        self.assertEqual(report["coverage"]["uncomparedPairsDueToInvalidItems"], 3)

    def test_near_pairs_are_not_transitively_collapsed(self):
        report = audit([palette("a", ["#555555", "#ffffff"]),
                        palette("b", ["#595959", "#ffffff"]),
                        palette("c", ["#5d5d5d", "#ffffff"])])
        self.assertEqual([group["ids"] for group in report["nearGroups"]], [["a", "b"], ["b", "c"]])
        self.assertTrue(all(len(group["ids"]) == 2 for group in report["nearGroups"]))

    def test_gradient_color_identity_preserves_css_direction_and_original_kind(self):
        base = {"kind": "code", "language": "css", "colors": ["#ff0000", "#0000ff"],
                "analysis": {"assetType": "gradient", "preview": {"renderer": "gradient"}}}
        originals = [palette("p", ["#ff0000", "#0000ff"]),
                     palette("q", ["#ff0000", "#0000ff"]),
                     {**base, "id": "g1", "code": "a{background:linear-gradient(90deg,#ff0000,#0000ff)}"},
                     {**base, "id": "g2", "code": "a{background:linear-gradient(180deg,#ff0000,#0000ff)}"}]
        report = audit_color_representations(originals)
        group = report["exactGroups"][0]
        self.assertEqual(group["reason"], "cross-kind-related-color-representation")
        self.assertEqual(len(group["evidence"]["gradientCSS"]), 2)
        self.assertNotEqual(group["evidence"]["gradientCSS"][0]["cssBodySha256"],
                            group["evidence"]["gradientCSS"][1]["cssBodySha256"])
        self.assertEqual(report["coverage"]["comparedPairs"], 6)
        self.assertEqual(report["coverage"]["staticCSSGradientItemCount"], 2)
        self.assertEqual(originals[2]["kind"], "code")
        self.assertTrue(group["differences"]["notAutomaticDuplicate"])

    def test_gradient_supplement_excludes_css_motion_renderer(self):
        original = {"id": "motion", "kind": "code", "language": "css", "colors": ["#fff", "#000"],
                    "analysis": {"assetType": "gradient", "preview": {"renderer": "css"}}}
        report = audit_color_representations([original, palette("p", ["#fff", "#000"])])
        self.assertEqual(report["coverage"]["itemCount"], 1)
        self.assertEqual(report["coverage"]["staticCSSGradientItemCount"], 0)
        self.assertFalse(report["exactGroups"])


if __name__ == "__main__":
    unittest.main()
