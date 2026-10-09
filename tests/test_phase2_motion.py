"""Integrity and composition tests for immutable phase-two motion artifacts."""
import copy
import json
from pathlib import Path
import re
import unittest
import xml.etree.ElementTree as ET

from scripts.import_phase2_motion import (ROOT, LOCAL, OUTPUT, safe_path, selected,
    source_url, original_baseline, filter_duplicates, sha, blob_sha, entries, fixed_baseline)


class Phase2MotionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.items = json.loads(OUTPUT.read_text(encoding='utf-8'))
        cls.report = json.loads((LOCAL / 'report.json').read_text(encoding='utf-8'))

    def test_paths_and_source_registry_are_bounded(self):
        for path in ('../LICENSE', '/tmp/source', 'src/../source', 'src\\source', 'src/a:b', 'a' * 241):
            with self.assertRaises(ValueError):
                safe_path(path)
        self.assertFalse(selected('meteocons', 'production/fill/svg/clear-day.svg'))
        self.assertFalse(selected('meteocons', 'production/line/svg-static/clear-day.svg'))
        self.assertFalse(selected('css-loaders', 'video.mp4'))
        self.assertFalse(selected('css-loaders', 'src/../loader.css'))
        self.assertIn('0ccc40fcff96ac10e325b53d138fed27c4d18afa', source_url('meteocons', 'LICENSE'))

    def test_every_artifact_matches_pinned_git_tree(self):
        for slug in ('css-loaders', 'meteocons', 'paper-shaders', 'p5-shaders'):
            for path, entry in entries(slug).items():
                body = (LOCAL / slug / path).read_bytes()
                self.assertEqual(len(body), entry['size'])
                self.assertEqual(blob_sha(body), entry['sha'])

    def test_stored_code_contains_full_license_and_original_composition(self):
        for item in self.items:
            self.assertEqual(item['domain'], 'motion')
            self.assertEqual(sha(item['code']), item['evidence']['storedCodeSha256'])
            self.assertIn(item['licenseText'].strip(), item['code'])
            body = (ROOT / item['codePath']).read_bytes()
            self.assertEqual(sha(body), item['upstreamSha256'])
            if item['evidence'].get('cssLiteralEscapesDecoded'):
                expected = body.decode('utf-8').replace("'L \\00a0\\00a0 ading'", "'L \u00a0\u00a0ading'")
                self.assertIn(expected, item['code'])
                self.assertTrue(item['preview']['adapted'])
                self.assertNotIn('\\00a0', item['code'])
            else:
                self.assertIn(body.decode('utf-8'), item['code'])
            self.assertTrue(item['evidence']['fullDOMPreserved'])
            self.assertFalse(item['evidence']['sourceExecution'])

    def test_css_text_and_actual_span_are_preserved(self):
        annotated = 0
        for item in self.items:
            if item['language'] != 'css':
                continue
            raw = (ROOT / item['codePath']).read_text(encoding='utf-8')
            dom = item['preview']['dom']
            self.assertEqual(dom['tag'], 'span')
            self.assertEqual(dom['className'], 'loader')
            content = re.search(r'/\*\s*@content:\s*"([^"]+)"\s*\*/', raw)
            self.assertEqual(dom.get('text', ''), content[1] if content else '')
            annotated += bool(content)
            self.assertRegex(raw, r'@keyframes\s+')
            self.assertFalse(re.search(r'url\s*\(|@import|expression\s*\(', raw, re.I))
        self.assertEqual(annotated, 18)

    def test_every_svg_has_animation_and_only_local_references(self):
        allowed = {'svg', 'g', 'path', 'circle', 'ellipse', 'rect', 'defs', 'symbol', 'use', 'clipPath', 'linearGradient', 'stop', 'animate', 'animateTransform'}
        for item in self.items:
            if item['language'] != 'svg':
                continue
            root = ET.fromstring(item['code'])
            nodes = list(root.iter())
            self.assertTrue(any(n.tag.split('}')[-1] in ('animate', 'animateTransform') for n in nodes))
            for node in nodes:
                self.assertIn(node.tag.split('}')[-1], allowed)
                for key, value in node.attrib.items():
                    self.assertFalse(key.split('}')[-1].lower().startswith('on'))
                    if key.split('}')[-1] == 'href':
                        self.assertTrue(value.startswith('#'))

    def test_repair_original_body_is_included_with_current_body(self):
        old = {'id': 'original', 'code': 'old', 'kind': 'code', 'language': 'css'}
        canonical = {**old, 'code': 'fixed', 'variants': [copy.deepcopy(old)], 'repair': {'originalRecord': copy.deepcopy(old)}}
        all_bodies = original_baseline({'items': [canonical]})
        self.assertEqual(len(all_bodies), 2)
        self.assertEqual({x['code'] for x in all_bodies}, {'old', 'fixed'})

    def test_rebuild_uses_pre_expansion_baseline_not_current_catalog(self):
        baseline = fixed_baseline()
        self.assertEqual(baseline['canonicalCount'], 6074)
        self.assertEqual(baseline['originalAndRepairedCount'], 6111)
        self.assertFalse(any(x['baselineOriginalId'].startswith('phase2-') for x in baseline['codeBodies']))
        for name in ('spinkit-sk-chase', 'spinkit-sk-swing', 'three-dots-dot-falling'):
            self.assertEqual(len([x for x in baseline['codeBodies'] if x['baselineOriginalId'] == name]), 2)

    def test_paint_timing_and_frame_variants_do_not_inflate_count(self):
        code = '.a{color:#fff;animation:turn 1s linear infinite}@keyframes turn{0%{transform:rotate(0deg)}100%{transform:rotate(360deg)}}'
        item = {'id': 'one', 'sourceUrl': 'https://example.org/one.css', 'code': code, 'kind': 'code', 'language': 'css', 'preview': {'type': 'css', 'dom': {'tag': 'span', 'className': 'a'}}}
        other = copy.deepcopy(item); other['id'] = 'two'; other['code'] = code.replace('#fff', '#00ffff').replace('1s linear', '2s ease-in')
        kept, removed, errors = filter_duplicates([item, other], [])
        self.assertEqual(len(kept), 1)
        self.assertEqual(removed[0]['reason'], 'paint-or-timing-only')
        self.assertFalse(errors)

    def test_counts_are_actual_code_assets_only(self):
        self.assertEqual(len(self.items), self.report['retainedCount'])
        self.assertEqual(len({x['id'] for x in self.items}), len(self.items))
        self.assertEqual(len(self.items) + len(self.report['duplicatesExcluded']), self.report['candidateCount'])
        self.assertFalse(self.report['baselineParseErrors'])
        self.assertTrue(all(x['kind'] == 'code' and x['language'] in ('css', 'svg') for x in self.items))
        self.assertFalse(any('static' in x['codePath'] or '/fill/svg/' in x['codePath'] for x in self.items))


if __name__ == '__main__':
    unittest.main()
