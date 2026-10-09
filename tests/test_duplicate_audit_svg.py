import copy
import unittest

from scripts.duplicate_audit_svg import audit


def item(identifier, body, attrs='width="24" height="24" viewBox="0 0 24 24"'):
    return {"id": identifier, "kind": "code", "language": "svg", "sourceName": "Fixture",
            "code": '<svg xmlns="http://www.w3.org/2000/svg" ' + attrs + '>' + body + '</svg>'}


def motion(values="0;10", duration="1s", other=""):
    return '<path d="M1 2L3 4" fill="none" stroke="currentColor"><animate attributeName="stroke-dashoffset" dur="' + duration + '" values="' + values + '" ' + other + '/></path>'


class SVGDuplicateAuditTests(unittest.TestCase):
    def test_numeric_attribute_and_namespace_spelling_and_comments_are_exact(self):
        a = item("a", '<!-- license --><title>Unreferenced</title><path d="M1,2L3,4" opacity="1.0"/>')
        b = {**a, "id": "b", "code": '<s:svg xmlns:s="http://www.w3.org/2000/svg" viewBox="0,0,24,24" height="24" width="24"><s:path opacity="1" d="M 1 2 L 3 4"/></s:svg>'}
        report = audit([a, b])
        self.assertEqual(report["exactGroups"][0]["ids"], ["a", "b"])
        self.assertEqual(report["coverage"]["comparedPairs"], 1)

    def test_ids_references_and_begin_syncbase_are_normalized_together(self):
        a = item("a", '<defs><mask id="m"><rect width="24" height="24" fill="white"/></mask></defs><path d="M1 2L3 4" mask="url(#m)"><animate id="step" attributeName="opacity" begin="0;step.end+1s" dur="1s" values="0;1"/></path>')
        b = {**a, "id": "b", "code": a["code"].replace('id="m"', 'id="mask_b"').replace('url(#m)', 'url(#mask_b)').replace('id="step"', 'id="animation_b"').replace('step.end', 'animation_b.end')}
        self.assertEqual(len(audit([a, b])["exactGroups"]), 1)

    def test_namespace_uri_is_semantic_and_only_prefix_spelling_is_normalized(self):
        a = item("a", '<path d="M1 2L3 4"/>')
        b = item("b", '<path xmlns="" d="M1 2L3 4"/>')
        report = audit([a, b])
        self.assertFalse(report["exactGroups"])
        self.assertFalse(report["nearGroups"])
        self.assertFalse(report["candidatePairs"])

    def test_id_prefix_does_not_rewrite_different_reference(self):
        a = item("a", '<circle id="a" r="1"><animate attributeName="r" begin="a.end" dur="1s" values="1;2"/></circle>')
        b = item("b", '<circle id="a" r="1"><animate attributeName="r" begin="aa.end" dur="1s" values="1;2"/></circle>')
        self.assertFalse(audit([a, b])["exactGroups"])

    def test_redundant_linear_samples_have_exact_rational_proof(self):
        report = audit([item("a", motion("0;5;10")), item("b", motion("0;10"))])
        self.assertEqual(len(report["exactGroups"]), 1)
        self.assertTrue(any(d["location"].endswith("/@values") for d in report["exactGroups"][0]["differences"][0]["attributes"]))

    def test_nonuniform_keytimes_and_noncollinear_frames_are_not_exact(self):
        for body in [motion("0;5;10", other='keyTimes="0;.3;1"'), motion("0;8;10")]:
            report = audit([item("a", body), item("b", motion())])
            self.assertFalse(report["exactGroups"])
            self.assertFalse(report["nearGroups"])

    def test_discrete_frames_are_not_collapsed(self):
        report = audit([item("a", motion("0;5;10", other='calcMode="discrete"')), item("b", motion("0;10", other='calcMode="discrete"'))])
        self.assertFalse(report["exactGroups"])

    def test_timing_only_is_near_not_exact_with_concrete_values(self):
        report = audit([item("a", motion(duration="1s")), item("b", motion(duration="1.5s"))])
        self.assertFalse(report["exactGroups"])
        self.assertEqual(report["nearGroups"][0]["differences"], [{"location": "svg/0/0/@dur", "left": "1s", "right": "1.5s"}])

    def test_clock_unit_equivalence_is_exact(self):
        report = audit([item("a", motion(duration="1000ms")), item("b", motion(duration="1s"))])
        self.assertEqual(len(report["exactGroups"]), 1)

    def test_large_speed_difference_is_only_candidate(self):
        report = audit([item("a", motion(duration=".1s")), item("b", motion(duration="10s"))])
        self.assertFalse(report["nearGroups"])
        self.assertEqual(report["candidatePairs"][0]["evidence"]["maxDurationRatio"], 100)

    def test_near_pair_threshold_is_not_transitive(self):
        report = audit([item("a", motion(duration="1s")), item("b", motion(duration="2s")), item("c", motion(duration="4s"))])
        self.assertEqual([g["ids"] for g in report["nearGroups"]], [["a", "b"], ["b", "c"]])
        self.assertEqual(report["candidatePairs"][0]["ids"], ["a", "c"])

    def test_reverse_values_loop_and_easing_changes_are_family_only(self):
        a = item("a", motion())
        variants = [motion("10;0"), motion(other='repeatCount="indefinite"'), motion(other='calcMode="discrete"')]
        for variant in variants:
            report = audit([a, item("b", variant)])
            self.assertFalse(report["exactGroups"])
            self.assertFalse(report["nearGroups"])
            self.assertFalse(report["candidatePairs"])
            self.assertEqual(len(report["familyGroups"]), 1)

    def test_fill_outline_and_stroke_changes_are_not_near(self):
        a = item("a", '<path d="M1 2L3 4" fill="none" stroke="red"/>')
        for body in ['<path d="M1 2L3 4" fill="red" stroke="red"/>', '<path d="M1 2L3 4" fill="none" stroke="blue"/>']:
            report = audit([a, item("b", body)])
            self.assertFalse(report["exactGroups"])
            self.assertFalse(report["nearGroups"])
            self.assertFalse(report["candidatePairs"])

    def test_initial_state_and_viewbox_are_preserved(self):
        a = item("a", '<circle r="2" opacity="0"><animate attributeName="opacity" dur="1s" to="1"/></circle>')
        for b in [item("b", '<circle r="2" opacity="1"><animate attributeName="opacity" dur="1s" to="1"/></circle>'), item("b", '<circle r="2" opacity="0"><animate attributeName="opacity" dur="1s" to="1"/></circle>', attrs='width="24" height="24" viewBox="0 0 48 48"')]:
            report = audit([a, b])
            self.assertFalse(report["exactGroups"])
            self.assertFalse(report["nearGroups"])

    def test_semantic_extra_shape_and_direction_do_not_match(self):
        a = item("a", motion())
        for body in [motion() + '<path d="M10 10h1"/>', motion().replace("M1 2L3 4", "M23 2L21 4")]:
            report = audit([a, item("b", body)])
            self.assertFalse(report["exactGroups"])
            self.assertFalse(report["nearGroups"])
            self.assertFalse(report["candidatePairs"])

    def test_only_tiny_coordinate_change_is_candidate_with_measured_delta(self):
        a = item("a", '<path d="M1 2L3 4" fill="none"/>')
        b = item("b", '<path d="M1.05 2L3 4" fill="none"/>')
        report = audit([a, b])
        self.assertFalse(report["nearGroups"])
        evidence = report["candidatePairs"][0]["evidence"]
        self.assertEqual(evidence["maxCoordinateDelta"], .05)
        self.assertEqual(evidence["comparedNumericCoordinates"], 4)

    def test_arc_flags_are_discrete_even_at_large_viewbox(self):
        a = item("a", '<path d="M1 2A3 4 0 0 0 5 6"/>', attrs='viewBox="0 0 1000 1000"')
        b = item("b", '<path d="M1 2A3 4 0 1 0 5 6"/>', attrs='viewBox="0 0 1000 1000"')
        report = audit([a, b])
        self.assertFalse(report["candidatePairs"])

    def test_paint_order_is_not_an_exact_duplicate(self):
        a = item("a", '<circle r="2" fill="red"/><circle r="3" fill="blue"/>')
        b = item("b", '<circle r="3" fill="blue"/><circle r="2" fill="red"/>')
        report = audit([a, b])
        self.assertFalse(report["exactGroups"])
        self.assertFalse(report["nearGroups"])

    def test_referenced_metadata_and_text_remain_distinct(self):
        a = item("a", '<title id="label">A</title><use href="#label"/>')
        b = item("b", '<title id="label">B</title><use href="#label"/>')
        self.assertFalse(audit([a, b])["exactGroups"])
        report = audit([item("a", '<text> A </text>'), item("b", '<text>A</text>')])
        self.assertFalse(report["exactGroups"])
        self.assertFalse(report["familyGroups"])

    def test_entities_active_content_external_references_and_bounds_are_errors(self):
        fixtures = [
            {**item("a", ""), "code": '<!DOCTYPE svg [<!ENTITY x "evil">]><svg>&x;</svg>'},
            item("a", '<script>alert(1)</script>'),
            item("a", '<path onclick="alert(1)"/>'),
            item("a", '<use href="https://example.com/icon.svg#x"/>'),
            item("a", '<g>' * 33 + '</g>' * 33),
            item("a", '<path/>' * 701),
            item("a", " " * (128 * 1024)),
            item("a", '<circle r="1e-100000"/>'),
            item("a", '<circle r="1e100000"/>'),
        ]
        for fixture in fixtures:
            report = audit([fixture, item("b", motion())])
            self.assertEqual(report["coverage"]["parsedItems"], 1)
            self.assertEqual(report["coverage"]["skippedPairsForParseErrors"], 1)
            self.assertEqual(len(report["errors"]), 1)

    def test_deterministic_order_inspection_manifest_and_no_mutation(self):
        records = [item("z", motion()), item("a", motion(duration="2s")), item("m", '<circle r="4"/>')]
        before = copy.deepcopy(records)
        first = audit(records)
        self.assertEqual(first, audit(list(reversed(records))))
        self.assertEqual(records, before)
        self.assertEqual(first["coverage"]["pairUniverse"], 3)
        self.assertEqual(sum(first["coverage"]["pairClassificationCounts"].values()), 3)
        self.assertEqual([x["id"] for x in first["inspectionManifest"]], ["a", "m", "z"])


if __name__ == "__main__":
    unittest.main()
