"""README composition follows canonical catalog counts on each build."""

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
import tempfile
import unittest
import xml.etree.ElementTree as ET

from scripts.build import build
from scripts.consolidate import record_sha
from scripts.readme_assets import write_readme_assets


PROJECT = Path(__file__).resolve().parent.parent
START = "<!-- motionlab:catalog-summary:start -->"
END = "<!-- motionlab:catalog-summary:end -->"
CHART = Path("docs/assets/catalog-composition.svg")


def record(identifier, domain="motion"):
    reference = domain == "reference"
    design = domain == "design"
    colors = ["#102030", "#ffffff"] if design else []
    result = {
        "id": identifier, "title": identifier, "description": "Canonical asset fixture",
        "category": "reference" if reference else "palette" if design else "animation",
        "tags": ["fixture"], "sourceUrl": "https://example.org/" + identifier,
        "sourceName": "Fixture " + identifier, "license": "Unknown" if reference else "MIT",
        "licenseText": "Original permission notice", "verifiedAt": "2026-10-10",
        "verification": "fixture", "kind": "reference" if reference else "palette" if design else "code",
        "preview": {"type": "reference" if reference else "palette" if design else "css", "variant": identifier},
        "code": None if reference else json.dumps(colors) if design else ".dot {animation: pulse 1s ease}",
        "colors": colors, "language": "link" if reference else "json" if design else "css", "access": "public",
    }
    if not reference:
        result["domain"] = domain
    return result


def stats(motion=2, design=3, reference=1):
    return {"domains": {"motion": motion, "design": design}, "kinds": {"reference": reference},
            "total": motion + design + reference, "storedAssets": motion + design,
            "sources": 4, "updatedAt": "2026-10-10", "aliases": 70, "variantRecords": 90}


class ReadmeAssetsTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(dir=PROJECT / "tests")
        self.root = Path(self.temporary.name)

    def tearDown(self):
        self.temporary.cleanup()

    def readmes(self):
        originals = {}
        for name, prefix in (("README.md", "English introduction"), ("README-KO.md", "한국어 소개")):
            content = (f"# {prefix}\n\n{START}\nOld generated counts\n{END}\n\n"
                       f"![Catalog composition]({CHART.as_posix()})\n\nKeep this footer {prefix}.\n")
            (self.root / name).write_text(content, encoding="utf-8")
            originals[name] = content
        return originals

    def assert_summary(self, expected):
        for name in ("README.md", "README-KO.md"):
            text = (self.root / name).read_text(encoding="utf-8")
            self.assertEqual(text.count(START), 1)
            self.assertEqual(text.count(END), 1)
            self.assertIn(CHART.as_posix(), text)
            labels = ("모션", "디자인", "레퍼런스") if name == "README-KO.md" else ("Motion", "Design", "References")
            for label, count in zip(labels, expected):
                self.assertRegex(text, rf"\|\s*{label}\s*\|\s*{count:,}\s*\|")
        namespace = {"svg": "http://www.w3.org/2000/svg"}
        chart = ET.parse(self.root / CHART).getroot()
        total = sum(expected)
        for key, count in zip(("motion", "design", "references"), expected):
            percent = count * 100 / total if total else 0
            legend = chart.find(f".//svg:g[@id='legend-{key}']", namespace)
            self.assertIsNotNone(legend)
            labels = [entry.text for entry in legend.findall("svg:text", namespace)]
            self.assertIn(f"{count:,} entries", labels)
            self.assertIn(f"{percent:.1f}%", labels)
            arc = chart.find(f".//svg:circle[@data-collection='{key}']", namespace)
            if count:
                self.assertIsNotNone(arc)
                self.assertEqual(arc.get("pathLength"), "100")
                self.assertAlmostEqual(float(arc.get("stroke-dasharray").split()[0]), percent, places=7)
            else:
                self.assertIsNone(arc)

    def test_build_refreshes_both_languages_and_counts_canonical_assets_once(self):
        originals = self.readmes()
        (self.root / "data").mkdir()
        (self.root / "dist").mkdir()
        entries = [record("motion"), record("design", "design"), record("design-variant", "design"),
                   record("reference", "reference")]
        members = entries[1:3]
        policy = {"version": 1, "groups": [{
            "id": "design", "ids": [entry["id"] for entry in members], "mode": "palette",
            "expectedCodeSha256": {entry["id"]: hashlib.sha256(entry["code"].encode()).hexdigest() for entry in members},
            "expectedRecordSha256": {entry["id"]: record_sha(entry) for entry in members},
            "relations": [{"basis": "reviewed-source-structure"}],
        }]}
        (self.root / "data/consolidation-policy.json").write_text(json.dumps(policy), encoding="utf-8")
        input_path = self.root / "data/imported-items.json"
        input_path.write_text(json.dumps(entries), encoding="utf-8")
        first = build(self.root)
        self.assertEqual((first["total"], first["aliases"], first["variantRecords"]), (3, 1, 2))
        self.assert_summary((1, 1, 1))
        initial_svg = (self.root / CHART).read_bytes()

        entries.extend([record("motion-two"), record("design-two", "design"), record("reference-two", "reference")])
        input_path.write_text(json.dumps(entries), encoding="utf-8")
        latest = build(self.root)
        published = json.loads((self.root / "dist/catalog-index.json").read_text(encoding="utf-8"))["stats"]
        self.assertEqual(latest, published)
        self.assertEqual((latest["total"], latest["storedAssets"], latest["aliases"]), (6, 4, 1))
        self.assert_summary((2, 2, 2))
        self.assertNotEqual((self.root / CHART).read_bytes(), initial_svg)
        for name, original in originals.items():
            current = (self.root / name).read_text(encoding="utf-8")
            self.assertEqual(current.split(START)[0], original.split(START)[0])
            self.assertEqual(current.split(END)[1], original.split(END)[1])
        snapshot = {name: (self.root / name).read_bytes() for name in (*originals, CHART)}
        build(self.root)
        self.assertEqual({name: (self.root / name).read_bytes() for name in snapshot}, snapshot)

    def test_empty_and_single_category_charts_have_valid_geometry(self):
        self.readmes()
        for counts in ((0, 0, 0), (7, 0, 0), (0, 7, 0), (0, 0, 7)):
            with self.subTest(counts=counts):
                write_readme_assets(self.root, stats(*counts))
                self.assert_summary(counts)
                svg = (self.root / CHART).read_text(encoding="utf-8")
                ET.fromstring(svg)
                self.assertNotRegex(svg, r"(?i)\b(?:nan|infinity|inf)\b")
                self.assertIn("0.0%", svg)
                if any(counts):
                    self.assertIn("100.0%", svg)

    def test_chart_does_not_create_missing_readmes_or_replace_unmarked_prose(self):
        path = self.root / "README.md"
        path.write_text("Unmarked introduction remains.\n", encoding="utf-8")
        write_readme_assets(self.root, stats())
        self.assertEqual(path.read_text(encoding="utf-8"), "Unmarked introduction remains.\n")
        self.assertFalse((self.root / "README-KO.md").exists())
        self.assertTrue((self.root / CHART).is_file())

    def test_invalid_counts_totals_and_dates_are_rejected(self):
        self.readmes()
        invalid = []
        for value in (-1, True, 1.5, "2", None):
            value_stats = stats()
            value_stats["domains"]["motion"] = value
            invalid.append(value_stats)
        for field, value in (("total", 7), ("storedAssets", 6), ("sources", -1),
                             ("updatedAt", "2026-02-30"), ("updatedAt", "2026-10-10<script>")):
            value_stats = stats()
            value_stats[field] = value
            invalid.append(value_stats)
        invalid.extend([None, [], {**stats(), "domains": []}, {**stats(), "kinds": []}])
        before = (self.root / "README.md").read_bytes()
        for value in invalid:
            with self.subTest(value=value), self.assertRaises(ValueError):
                write_readme_assets(self.root, deepcopy(value))
            self.assertEqual((self.root / "README.md").read_bytes(), before)

    def test_malformed_or_duplicate_markers_are_rejected_without_erasing_prose(self):
        for content in (f"Prefix\n{START}\nMissing end\n", f"Prefix\n{END}\nMissing start\n",
                        f"{END}\nProse\n{START}\n", f"{START}\n{START}\n{END}\n",
                        f"{START}\n{END}\n{START}\n{END}\n"):
            with self.subTest(content=content):
                path = self.root / "README.md"
                path.write_text(content, encoding="utf-8")
                with self.assertRaises(ValueError):
                    write_readme_assets(self.root, stats())
                self.assertEqual(path.read_text(encoding="utf-8"), content)

    def test_svg_has_only_passive_local_elements_and_attributes(self):
        write_readme_assets(self.root, stats())
        svg = (self.root / CHART).read_text(encoding="utf-8")
        parsed = ET.fromstring(svg)
        allowed = {"svg", "title", "desc", "g", "circle", "path", "rect", "text", "line"}
        for element in parsed.iter():
            self.assertIn(element.tag.rsplit("}", 1)[-1], allowed)
            for name, value in element.attrib.items():
                self.assertFalse(name.lower().startswith("on"))
                self.assertNotIn(name.rsplit("}", 1)[-1].lower(), {"href", "src"})
                self.assertNotRegex(value, r"(?i)(?:https?:|javascript:|data:|url\s*\()")
        self.assertNotRegex(svg, r"(?i)<!DOCTYPE|<!ENTITY")


if __name__ == "__main__":
    unittest.main()
