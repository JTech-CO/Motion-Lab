"""Check that static deployment publishes the rebuilt library without repository data."""

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts.build_pages import REQUIRED_FILES, build_pages


class PagesDeploymentTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.dist = self.root / "dist"
        self.dist.mkdir()
        for name in REQUIRED_FILES:
            (self.dist / name).write_text("public", encoding="utf-8")

    def test_preserves_dist_urls_and_excludes_repository_files(self):
        for folder in ("data", ".git", ".vsf"):
            path = self.root / folder
            path.mkdir()
            (path / "private.txt").write_text("private", encoding="utf-8")
        assets = self.dist / "assets"
        assets.mkdir()
        (assets / "sample.svg").write_text("<svg/>", encoding="utf-8")
        result = build_pages(self.root)
        site = self.root / "_site"
        self.assertEqual(result["entry"], "dist/index.html")
        self.assertEqual((site / "dist/assets/sample.svg").read_text(), "<svg/>")
        self.assertEqual({path.name for path in site.iterdir()},
                         {"dist", "index.html", "redirect.js", ".nojekyll"})
        redirect = (site / "redirect.js").read_text()
        self.assertIn("destination.hash = location.hash", redirect)
        self.assertIn("destination.search = location.search", redirect)

    def test_missing_catalog_fails_before_creating_site(self):
        (self.dist / "catalog.json").unlink()
        with self.assertRaisesRegex(ValueError, "Rebuild"):
            build_pages(self.root)
        self.assertFalse((self.root / "_site").exists())

    def test_size_limit_fails_before_creating_site(self):
        with patch("scripts.build_pages.MAX_SITE_BYTES", 1):
            with self.assertRaisesRegex(ValueError, "1 GB"):
                build_pages(self.root)
        self.assertFalse((self.root / "_site").exists())

    def test_existing_staging_is_never_replaced(self):
        output = self.root / "_site"
        output.mkdir()
        sentinel = output / "keep.txt"
        sentinel.write_text("keep", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "already exists"):
            build_pages(self.root)
        self.assertEqual(sentinel.read_text(), "keep")

    def test_hidden_source_is_not_published(self):
        (self.dist / ".env").write_text("private", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "Hidden"):
            build_pages(self.root)
        self.assertFalse((self.root / "_site").exists())

    def test_linked_source_is_not_published(self):
        original = self.root / "not-public.txt"
        original.write_text("private", encoding="utf-8")
        try:
            (self.dist / "linked.txt").hardlink_to(original)
        except OSError as error:
            self.skipTest(f"Filesystem does not support hard links: {error}")
        with self.assertRaisesRegex(ValueError, "without links"):
            build_pages(self.root)
        self.assertFalse((self.root / "_site").exists())


if __name__ == "__main__":
    unittest.main()
