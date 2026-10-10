"""Stage only the rebuilt static website for GitHub Pages, retaining /dist/ URLs."""

import argparse
import json
from pathlib import Path
import shutil
import stat
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.package import checked_path  # noqa: E402

MAX_SITE_BYTES = 1_000_000_000
REQUIRED_FILES = ("index.html", "library.html", "app.js", "home.js", "home.css",
                  "preview.js", "catalog.json", "catalog-index.json", "catalog-stats.json")
REDIRECT_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <meta name="referrer" content="strict-origin-when-cross-origin">
  <meta http-equiv="Content-Security-Policy" content="default-src 'none'; script-src 'self'; base-uri 'none'; form-action 'none'">
  <meta http-equiv="refresh" content="0;url=./dist/index.html">
  <title>Motion Lab</title>
  <script src="./redirect.js"></script>
</head>
<body><a href="./dist/index.html">Open Motion Lab</a></body>
</html>
"""
REDIRECT_JS = """'use strict';
const destination = new URL('./dist/index.html', location.href);
destination.search = location.search;
destination.hash = location.hash;
location.replace(destination.href);
"""


def collect_dist_files(root):
    """Reject links and special files before publishing the public dist tree."""
    root = Path(root).absolute()
    base = root / "dist"
    if not stat.S_ISDIR(checked_path(base, root).st_mode):
        raise ValueError("The static website directory is missing")
    files, pending = [], [base]
    while pending:
        current = pending.pop()
        info = checked_path(current, root)
        if stat.S_ISDIR(info.st_mode):
            pending.extend(current.iterdir())
        elif stat.S_ISREG(info.st_mode) and info.st_nlink == 1:
            files.append(current)
        else:
            raise ValueError("Pages source must contain ordinary files without links")
        if current != base and current.name.startswith("."):
            raise ValueError("Hidden files and directories are not published")
    return sorted(files)


def build_pages(root=ROOT):
    root = Path(root).absolute()
    output = root / "_site"
    if checked_path(output, root, missing=True) is not None:
        raise ValueError("The _site directory already exists; use a clean staging directory")
    files = collect_dist_files(root)
    relative_files = {path.relative_to(root / "dist").as_posix() for path in files}
    if set(REQUIRED_FILES) - relative_files:
        raise ValueError("Rebuild the complete catalog before staging GitHub Pages")
    expected_bytes = sum(path.stat().st_size for path in files) + len(
        (REDIRECT_HTML + REDIRECT_JS).encode("utf-8"))
    if expected_bytes > MAX_SITE_BYTES:
        raise ValueError("The static website exceeds the 1 GB GitHub Pages limit")
    output.mkdir()
    for path in files:
        info = checked_path(path, root)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise ValueError("Pages source changed during staging")
        target = output / path.relative_to(root)
        target.parent.mkdir(parents=True, exist_ok=True)
        checked_path(target.parent, root)
        shutil.copyfile(path, target)
    (output / "index.html").write_text(REDIRECT_HTML, encoding="utf-8", newline="\n")
    (output / "redirect.js").write_text(REDIRECT_JS, encoding="utf-8", newline="\n")
    (output / ".nojekyll").touch()
    return {"files": len(files) + 3, "bytes": expected_bytes, "entry": "dist/index.html"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    options = parser.parse_args()
    try:
        print(json.dumps(build_pages(options.root)))
    except (OSError, ValueError) as error:
        print(f"Pages staging failed: {error}", file=sys.stderr)
        sys.exit(1)
