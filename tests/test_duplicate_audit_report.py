"""Coverage and counting checks for the full-catalog audit report."""

import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts import audit_duplicates
from scripts.audit_duplicates import DOMAINS, domain_for, load_decisions, load_quality_notes, merge_exact_components, safe_cell, summarize, validate_reports


class DuplicateReportTest(unittest.TestCase):
    def fixture(self):
        items = [{'id': name, 'kind': 'code', 'language': name, 'code': name} for name in ('css', 'svg', 'glsl')]
        items += [{'id': 'palette', 'kind': 'palette', 'language': 'json', 'code': '[]'},
                  {'id': 'reference', 'kind': 'reference', 'language': 'link', 'code': None}]
        reports = {}
        for domain in DOMAINS:
            entry = next(item for item in items if domain_for(item) == domain)
            reports[domain] = {'catalogSha256': 'catalog', 'items': [{'id': entry['id'], 'codeSha256': hashlib.sha256((entry['code'] or '').encode()).hexdigest()}],
                'coverage': {'itemCount': 1, 'pairUniverse': 0}, 'errors': [],
                'exactGroups': [], 'nearGroups': [], 'candidatePairs': [], 'familyGroups': []}
        return items, reports

    def test_all_item_manifest_required(self):
        items, reports = self.fixture()
        self.assertEqual(len(validate_reports(items, reports, 'catalog')), 5)
        reports['svg']['items'] = []
        with self.assertRaisesRegex(ValueError, 'coverage'):
            validate_reports(items, reports, 'catalog')

    def test_wrong_code_or_catalog_hash_rejected(self):
        items, reports = self.fixture()
        reports['css']['items'][0]['codeSha256'] = 'wrong'
        with self.assertRaisesRegex(ValueError, 'fingerprint'):
            validate_reports(items, reports, 'catalog')
        _, reports = self.fixture()
        reports['glsl']['catalogSha256'] = 'old'
        with self.assertRaisesRegex(ValueError, 'fingerprint'):
            validate_reports(items, reports, 'catalog')

    def test_unknown_finding_id_rejected(self):
        items, reports = self.fixture()
        reports['css']['nearGroups'] = [{'ids': ['css', 'not-in-catalog']}]
        with self.assertRaisesRegex(ValueError, 'membership'):
            validate_reports(items, reports, 'catalog')

    def test_exact_equivalence_uses_existing_order(self):
        groups = [{'ids': ['b', 'a']}, {'ids': ['b', 'c']}]
        self.assertEqual(merge_exact_components(groups, {'a': 0, 'b': 1, 'c': 2}), [['a', 'b', 'c']])

    def test_near_chains_not_counted_as_redundant_assets(self):
        items, reports = self.fixture()
        reports['css']['nearGroups'] = [{'ids': ['css', 'svg']}, {'ids': ['svg', 'glsl']}]
        stats, _, _, exact = summarize(items, reports, {})
        self.assertEqual(stats['nearRelationCount'], 2)
        self.assertEqual(stats['nearAffectedItemCount'], 3)
        self.assertEqual(stats['exactSurplusCount'], 0)
        self.assertEqual(exact, [])

    def test_spreadsheet_formula_metadata_is_neutralized(self):
        for value in ('=WEBSERVICE("https://example.test")', ' +cmd', '-2+3', '@SUM(1)', '\tformula'):
            self.assertTrue(safe_cell(value).startswith("'"))
        self.assertEqual(safe_cell('normal-id'), 'normal-id')

    def test_review_requires_every_member_original_hash(self):
        items, _ = self.fixture()
        items.append({'id': 'css2', 'kind': 'code', 'language': 'css', 'code': 'css2'})
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            value = {'catalogSha256': 'catalog', 'decisions': [{'domain': 'css', 'ids': ['css', 'css2'], 'classification': 'keep-variant', 'codeSha256': {}}]}
            (output / 'review-decisions.json').write_text(json.dumps(value), encoding='utf-8')
            with patch.object(audit_duplicates, 'OUTPUT', output):
                with self.assertRaisesRegex(ValueError, 'fingerprints'):
                    load_decisions({item['id']: item for item in items}, 'catalog')

    def test_quality_evidence_hash_and_path_are_verified(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output = root / 'data/duplicate-audit'
            source = root / 'data/upstream/sample/source.css'
            output.mkdir(parents=True)
            source.parent.mkdir(parents=True)
            source.write_bytes(b'.original{opacity:1}')
            note = {'ids': ['css'], 'sourcePath': 'data/upstream/sample/source.css', 'sourceSha256': hashlib.sha256(source.read_bytes()).hexdigest()}
            value = {'catalogSha256': 'catalog', 'qualityNotes': [note]}
            report = output / 'css-review.json'
            report.write_text(json.dumps(value), encoding='utf-8')
            with patch.object(audit_duplicates, 'ROOT', root), patch.object(audit_duplicates, 'OUTPUT', output):
                self.assertEqual(len(load_quality_notes({'css': {}}, 'catalog')), 1)
                source.write_bytes(b'changed')
                with self.assertRaisesRegex(ValueError, 'hash'):
                    load_quality_notes({'css': {}}, 'catalog')
                note['sourcePath'] = '../outside.css'
                report.write_text(json.dumps(value), encoding='utf-8')
                with self.assertRaisesRegex(ValueError, 'inside'):
                    load_quality_notes({'css': {}}, 'catalog')


if __name__ == '__main__':
    unittest.main()
