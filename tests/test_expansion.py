"""Content and provenance regressions for the source expansion merge."""

import unittest

from scripts.expansion import asset_fingerprint, merge_expansion


def code(identifier, body, language="css"):
    return {"id": identifier, "kind": "code", "language": language, "code": body,
            "licenseText": "Complete source notice", "colors": []}


class ExpansionTest(unittest.TestCase):
    def test_palette_identity_keeps_order_and_normalizes_hex(self):
        def palette(colors):
            return {"kind": "palette", "language": "json", "colors": colors}
        self.assertEqual(asset_fingerprint(palette(["#fff", "#ABCDEF"])),
                         asset_fingerprint(palette(["#ffffff", "#abcdef"])))
        self.assertNotEqual(asset_fingerprint(palette(["#fff", "#000"])),
                            asset_fingerprint(palette(["#000", "#fff"])))

    def test_css_notice_removed_but_literals_and_motion_preserved(self):
        first = code("one", '/* copyright */ .sample{content:"/* text */";opacity:0}')
        second = code("two", '/* different notice */ .sample{content:"/* text */";opacity:0}')
        self.assertEqual(asset_fingerprint(first), asset_fingerprint(second))
        self.assertNotEqual(asset_fingerprint(first), asset_fingerprint(code("three", '.sample{content:"";opacity:0}')))
        self.assertNotEqual(asset_fingerprint(first), asset_fingerprint(code("four", '.sample{content:"/* text */";opacity:1}')))

    def test_svg_formatting_dedup_keeps_animation_values(self):
        first = code("one", '<svg width="24" height="24"><circle r="3"><animate attributeName="r" to="5"/></circle></svg>', "svg")
        second = code("two", '<svg height="24" width="24">\n<circle r="3"><animate to="5" attributeName="r"/></circle>\n</svg>', "svg")
        self.assertEqual(asset_fingerprint(first), asset_fingerprint(second))
        self.assertNotEqual(asset_fingerprint(first), asset_fingerprint(code("three", second["code"].replace('to="5"', 'to="6"'), "svg")))

    def test_merge_keeps_existing_ids_and_explains_duplicate(self):
        base = code("existing", ".sample{opacity:0}")
        duplicate = code("duplicate", ".sample{opacity:0}")
        distinct = code("new", ".sample{opacity:1}")
        result, report = merge_expansion([base], [("wave.json", [duplicate, distinct])], lambda entry: entry)
        self.assertEqual([entry["id"] for entry in result], ["new"])
        self.assertEqual(report["excluded"][0]["sameAs"], "existing")
        self.assertEqual(report["inputs"]["wave.json"], {"input": 2, "accepted": 1, "duplicates": 1})

    def test_merge_rejects_collisions_and_missing_notice(self):
        base = code("existing", ".sample{opacity:0}")
        with self.assertRaises(ValueError):
            merge_expansion([base], [("wave.json", [base])], lambda entry: entry)
        unlicensed = code("new", ".sample{opacity:1}")
        unlicensed.pop("licenseText")
        with self.assertRaises(ValueError):
            merge_expansion([], [("wave.json", [unlicensed])], lambda entry: entry)

    def test_new_assets_are_compared_to_original_variants_and_repair_parts(self):
        original = code("old-alias", ".part{opacity:.4}")
        former = code("former", ".old{opacity:.8}")
        parent = {**code("canonical", ".complete{opacity:1}"),
                  "variants": [original], "repair": {"originalRecord": former}}
        duplicates = [code("new-alias-body", original["code"]), code("new-former-body", former["code"])]
        result, report = merge_expansion([parent], [("phase2.json", duplicates)], lambda entry: entry)
        self.assertEqual(result, [])
        self.assertEqual({entry["sameAs"] for entry in report["excluded"]}, {"old-alias", "former"})
        with self.assertRaises(ValueError):
            merge_expansion([parent], [("phase2.json", [original])], lambda entry: entry)

    def test_image_identity_uses_stored_digest_not_provider_or_path(self):
        first = {"id": "one", "kind": "image", "image": {"sha256": "a" * 64}, "licenseText": "CC0"}
        second = {**first, "id": "two", "sourceName": "Different provider", "image": {"sha256": "a" * 64}}
        self.assertEqual(asset_fingerprint(first), asset_fingerprint(second))
        result, report = merge_expansion([first], [("materials.json", [second])], lambda entry: entry)
        self.assertEqual(result, [])
        self.assertEqual(report["excluded"][0]["sameAs"], "one")
