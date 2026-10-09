"""Regression checks for conservative source/DOM CSS duplicate findings."""

import unittest

from scripts.duplicate_audit_css import audit, record, strip_comments


def item(identity, css, dom=None, variables=None):
    preview = {"type": "css", "dom": dom or {"tag": "div", "className": "sample"}}
    if variables:
        preview["variables"] = variables
    return {"id": identity, "kind": "code", "language": "css", "code": css,
            "preview": preview, "sourceName": "Source title is irrelevant"}


def css(name="spin", selector=".sample", duration="1s", middle="50%", size="90deg", controls="infinite"):
    return f"@keyframes {name} {{from {{transform:rotate(0deg)}} {middle} {{transform:rotate({size})}} to {{transform:rotate(0deg)}}}} {selector} {{animation:{name} {duration} ease {controls}}}"


class CssDuplicateAuditTests(unittest.TestCase):
    def test_consistent_class_keyframe_renaming_is_exact(self):
        left = item("a", css())
        right = item("b", "/* attribution */\n" + css("turn", ".other"), {"tag": "div", "className": "other"})
        result = audit([left, right])
        self.assertEqual(result["coverage"]["exactPairCount"], 1)
        self.assertEqual(result["errors"], [])

    def test_quoted_comment_and_numeric_literals_are_preserved(self):
        self.assertEqual(strip_comments('content:"/* keep */";/* discard */'), 'content:"/* keep */";')
        left = item("a", '.sample {content:"12";width:12px;}')
        right = item("b", '.sample {content:"13";width:13px;}')
        self.assertNotEqual(record(left)["exact"], record(right)["exact"])

    def test_timing_frame_only_difference_is_near_and_not_exact(self):
        result = audit([item("a", css()), item("b", css(duration="2.1s", middle="51%"))])
        self.assertEqual(result["coverage"]["exactPairCount"], 0)
        self.assertEqual(result["coverage"]["nearPairCountExcludingExact"], 1)
        self.assertIn("frames", result["nearGroups"][0]["differences"][0]["values"])

    def test_geometry_changes_are_not_timing_near(self):
        result = audit([item("a", css(size="90deg")), item("b", css(size="91deg"))])
        self.assertEqual(result["coverage"]["nearPairCountExcludingExact"], 0)

    def test_keyframe_name_never_renames_transform_function(self):
        left = item("a", "@keyframes rotateX {from {transform:rotateX(0deg)} to {transform:rotateX(90deg)}} .sample {animation:rotateX 1s}")
        right = item("b", "@keyframes rotateY {from {transform:rotateY(0deg)} to {transform:rotateY(90deg)}} .sample {animation:rotateY 1s}")
        result = audit([left, right])
        self.assertEqual(result["coverage"]["exactPairCount"], 0)
        self.assertEqual(result["coverage"]["nearPairCountExcludingExact"], 0)

    def test_entrance_exit_endpoint_swap_is_not_near_or_candidate(self):
        left = item("a", "@keyframes move {from {transform:translateY(200%)}} .sample {animation:move 1s}")
        right = item("b", "@keyframes move {to {transform:translateY(200%)}} .sample {animation:move 1s}")
        result = audit([left, right])
        self.assertEqual(result["coverage"]["nearPairCountExcludingExact"], 0)
        self.assertEqual(result["candidatePairs"], [])

    def test_hex_shorthand_case_and_opaque_alpha_equivalence(self):
        first = item("a", ".sample {background:linear-gradient(135deg,#ABC,#ABCDEF)}")
        second = item("b", ".sample {background:linear-gradient(135deg,#aabbccff,#abcdef)}")
        self.assertEqual(record(first)["exact"], record(second)["exact"])
        third = item("c", '.sample {content:"#ABC";background:url(#ABC)}')
        fourth = item("d", '.sample {content:"#aabbcc";background:url(#aabbcc)}')
        self.assertNotEqual(record(third)["exact"], record(fourth)["exact"])

    def test_big_or_reversed_numeric_delta_is_not_small_candidate(self):
        result = audit([item("a", css(size="90deg")), item("b", css(size="900deg")), item("c", css(size="-90deg"))])
        self.assertEqual(result["candidatePairs"], [])

    def test_dom_children_and_interaction_triggers_are_not_collapsed(self):
        result = audit([item("a", css()), item("b", css(selector=".sample:hover")),
                        item("c", css(), {"tag": "button", "className": "sample", "children": [{"tag": "span", "text": "x"}]})])
        self.assertEqual(result["coverage"]["exactPairCount"], 0)
        self.assertEqual(result["coverage"]["nearPairCountExcludingExact"], 0)

    def test_direction_and_iteration_remain_behavioral_differences(self):
        result = audit([item("a", css(controls="infinite")), item("b", css(controls="infinite reverse")),
                        item("c", css(controls="2"))])
        self.assertEqual(result["coverage"]["exactPairCount"], 0)
        self.assertEqual(result["coverage"]["nearPairCountExcludingExact"], 0)
        self.assertEqual(result["candidatePairs"], [])
        self.assertEqual(result["coverage"]["familyGroupCount"], 1)

    def test_descendant_and_compound_selectors_differ(self):
        dom = {"tag": "div", "className": "sample child", "children": [{"tag": "span", "className": "child"}]}
        left = item("a", ".sample .child {opacity:0}", dom)
        right = item("b", ".sample.child {opacity:0}", dom)
        self.assertNotEqual(record(left)["exact"], record(right)["exact"])

    def test_used_variable_values_preserved_unused_boilerplate_ignored(self):
        code = ".sample {width:var(--size);animation:spin 1s infinite}@keyframes spin {to{transform:rotate(1turn)}}"
        left = item("a", code, variables={"--size": "10px", "--unused": "red"})
        right = item("b", code, variables={"--size": "11px", "--unused": "red"})
        other = item("c", code, variables={"--size": "10px", "--unused": "blue"})
        self.assertNotEqual(record(left)["exact"], record(right)["exact"])
        self.assertEqual(record(left)["exact"], record(other)["exact"])

    def test_every_parse_and_failed_parse_has_item_evidence(self):
        result = audit([item("a", css()), item("broken", ".sample {color:red")])
        self.assertEqual([entry["id"] for entry in result["items"]], ["a"])
        self.assertEqual(result["errors"][0]["id"], "broken")
        self.assertEqual(result["coverage"]["unparsedPairCount"], 1)


if __name__ == "__main__":
    unittest.main()
