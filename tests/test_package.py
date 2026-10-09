"""Package boundaries and preservation of a previously valid archive."""

import json
from pathlib import Path
import stat
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import zipfile

from scripts import package


PROJECT = Path(__file__).resolve().parents[1]


class PackageTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(dir=PROJECT / "tests")
        self.root = Path(self.temporary.name)
        (self.root / "data").mkdir()
        (self.root / "data" / "notice.txt").write_text("Original fixture license", encoding="utf-8")
        (self.root / "package.json").write_text(json.dumps({"scripts": {"test": "fixture", "start": "fixture"}}), encoding="utf-8")
        self.output = self.root / "Motion-Lab.zip"

    def tearDown(self):
        self.temporary.cleanup()

    def run_package(self):
        with patch.object(package, "ROOT", self.root), patch.object(package, "OUTPUT", self.output):
            package.main()

    def test_regular_sources_and_licenses_survive_packaging(self):
        (self.root / "data" / "ignored.log").write_text("ignored", encoding="utf-8")
        (self.root / "tests").mkdir()
        (self.root / "tests" / "not-shipped.py").write_text("fixture", encoding="utf-8")
        self.run_package()
        with zipfile.ZipFile(self.output) as archive:
            self.assertIsNone(archive.testzip())
            self.assertEqual(archive.read("Motion Lab/data/notice.txt"), b"Original fixture license")
            self.assertNotIn("Motion Lab/data/ignored.log", archive.namelist())
            self.assertFalse(any("/tests/" in name for name in archive.namelist()))
            scripts = json.loads(archive.read("Motion Lab/package.json"))["scripts"]
            self.assertEqual(scripts, {"start": "fixture"})
        self.assertEqual(json.loads((self.root / "package.json").read_text())["scripts"]["test"], "fixture")

    def test_outside_and_parent_traversal_are_rejected(self):
        for path in (self.root.parent / "outside.txt", self.root / "data" / ".." / ".." / "outside.txt"):
            with self.assertRaises(ValueError):
                package.checked_path(path, self.root, missing=True)

    def test_file_symlink_is_rejected_when_platform_allows_creation(self):
        link = self.root / "data" / "linked.txt"
        try:
            link.symlink_to(self.root / "data" / "notice.txt")
        except OSError:
            self.skipTest("Platform does not permit symlink creation; reparse metadata is tested separately")
        try:
            with self.assertRaises(ValueError):
                self.run_package()
            self.assertFalse(self.output.exists())
        finally:
            link.unlink()

    def test_reparse_file_parent_and_output_are_rejected(self):
        real_lstat = Path.lstat
        for linked in (self.root / "data" / "notice.txt", self.root / "data", self.root, self.output):
            with self.subTest(linked=linked.name):
                def lstat(path, _linked=linked):
                    if path == _linked:
                        return SimpleNamespace(st_mode=stat.S_IFDIR if path in (self.root, self.root / "data") else stat.S_IFREG,
                                               st_file_attributes=getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))
                    return real_lstat(path)
                with patch.object(Path, "lstat", lstat), self.assertRaises(ValueError):
                    self.run_package()
                self.assertFalse(self.output.exists())

    def test_failed_write_preserves_old_archive_and_removes_temporary(self):
        self.output.write_bytes(b"Previous archive fixture")
        with patch.object(zipfile.ZipFile, "write", side_effect=OSError("Simulated read failure")):
            with self.assertRaises(OSError):
                self.run_package()
        self.assertEqual(self.output.read_bytes(), b"Previous archive fixture")
        self.assertEqual(list(self.root.glob(".motionlab-package-*.zip")), [])


if __name__ == "__main__":
    unittest.main()
