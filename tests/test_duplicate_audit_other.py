"""False-positive checks for the offline duplicate review."""

import unittest

from scripts.duplicate_audit_other import audit_glsl, audit_references, canonical_glsl


def shader(identifier, code):
    return {'id': identifier, 'kind': 'code', 'language': 'glsl', 'code': code}


class DuplicateOtherTest(unittest.TestCase):
    def test_identifier_renaming_keeps_equivalent_program(self):
        a = shader('a', 'vec4 transition(vec2 uv){float amount=progress;return mix(getFromColor(uv),getToColor(uv),amount);}')
        b = shader('b', '/*notice*/ vec4 transition(vec2 point) { float level = progress; return mix(getFromColor(point),getToColor(point),level); }')
        self.assertEqual(canonical_glsl(a)['exact'], canonical_glsl(b)['exact'])

    def test_uniform_comment_defaults_are_behavior(self):
        body = 'uniform float size; // = %s\nvec4 transition(vec2 uv){return getFromColor(uv*size);}'
        a = shader('a', body % '0.5')
        b = shader('b', body % '0.8')
        self.assertNotEqual(canonical_glsl(a)['exact'], canonical_glsl(b)['exact'])
        self.assertEqual(len(audit_glsl([a, b])['familyGroups']), 1)

    def test_axis_and_literal_types_cannot_be_exact(self):
        body = 'vec4 transition(vec2 uv){return mix(getFromColor(uv),getToColor(uv),step(uv.%s,%s-progress));}'
        a = canonical_glsl(shader('a', body % ('x', '1.0')))
        b = canonical_glsl(shader('b', body % ('y', '1.0')))
        c = canonical_glsl(shader('c', body % ('x', '1')))
        self.assertNotEqual(a['exact'], b['exact'])
        self.assertNotEqual(a['exact'], c['exact'])

    def test_shared_page_is_not_a_duplicate_card(self):
        entries = [{'id': name, 'kind': 'reference', 'sourceUrl': 'https://example.test/collection', 'sourceCardId': name} for name in ('one', 'two')]
        report = audit_references(entries)
        self.assertEqual(report['exactGroups'], [])
        self.assertEqual(len(report['familyGroups']), 1)
        self.assertEqual(report['coverage']['visualComparedPairs'], 0)

    def test_reference_queries_and_fragments_remain_distinct(self):
        entries = [{'id': str(index), 'kind': 'reference', 'sourceUrl': url} for index, url in enumerate(('https://example.test/?asset=a', 'https://example.test/?asset=b', 'https://example.test/#a'))]
        self.assertEqual(audit_references(entries)['exactGroups'], [])

    def test_invalid_sources_fail_closed(self):
        self.assertEqual(len(audit_glsl([shader('bad', '')])['errors']), 1)
        report = audit_references([{'id': 'bad', 'kind': 'reference', 'sourceUrl': 'javascript:alert(1)'}])
        self.assertEqual(len(report['errors']), 1)


if __name__ == '__main__':
    unittest.main()
