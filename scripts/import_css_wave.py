"""Collect actual CSS assets from pinned primary sources, never execute source code.

Default operation is offline. --fetch fetches only registered pinned files, after
robots review, with bounded HTTPS requests and immutable Git blob verification.
This importer owns data/upstream/css-wave and data/css-wave-items.json only.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path, PurePosixPath
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser

ROOT = Path(__file__).resolve().parent.parent
LOCAL = ROOT / "data" / "upstream" / "css-wave"
OUTPUT = ROOT / "data" / "css-wave-items.json"
VERIFIED_DATE = "2026-10-09"
UA = "MotionLab/1.0 (bounded public CSS asset research; no scripts or videos)"
MAX_BYTES = 5_000_000
SOURCES = {
    "patterns": {"repository": "Afif13/CSS-Pattern", "commit": "66681684c1ca514328043b8ebd1407fe65830cc7",
        "directory": "afif13-css-pattern", "name": "CSS Pattern / Temani Afif", "license": "MIT", "licenseFile": "LICENCE",
        "files": ["LICENCE", "README.md", "index.html", "style.css"]},
    "animations": {"repository": "yesiamrocks/cssanimation", "commit": "3d71c839b1728fb4e0f1e394e60f1eb0d4f16e3d",
        "directory": "yesiamrocks-cssanimation", "name": "CSS Animation / Shafayetul Islam Pavel", "license": "Apache-2.0 + attribution", "licenseFile": "LICENSE",
        "files": ["LICENSE", "NOTICE", "README.md", "dist/cssanimation.css", "dist/cssanimation.json", "docs/animation-preview.html", "reference/cssanimation-reference.md"]},
}


def digest(body):
    return hashlib.sha256(body if isinstance(body, bytes) else body.encode("utf-8")).hexdigest()


def save_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def safe_path(value):
    path = PurePosixPath(value)
    if path.is_absolute() or len(path.parts) > 5 or any(not re.fullmatch(r"[A-Za-z0-9_.-]+", part) or part in (".", "..") for part in path.parts):
        raise ValueError("Unsafe upstream path")
    return path


def source_url(spec, filename):
    safe_path(filename)
    return f'https://github.com/{spec["repository"]}/blob/{spec["commit"]}/{filename}'


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *_args, **_kwargs):
        return None


class Collector:
    def __init__(self):
        self.opener = urllib.request.build_opener(NoRedirect())
        self.robots = {}
        self.log = []
        self.next_request = 0.0
        self.interval = 1.25
        self.stopped = False

    def request(self, url, *, policy=False):
        parsed = urllib.parse.urlsplit(url)
        if parsed.scheme != "https" or parsed.hostname not in ("raw.githubusercontent.com", "www.apache.org") or parsed.port not in (None, 443) or parsed.username or parsed.password:
            raise ValueError("Unregistered HTTPS host")
        if parsed.query or parsed.fragment:
            raise ValueError("Unexpected source URL query")
        if not policy:
            rules = self.robots.get(parsed.hostname)
            if not rules or rules["status"] == "unavailable" or rules.get("parser") and not rules["parser"].can_fetch(UA, url):
                raise ValueError("robots policy unavailable or disallows source; browser review required")
            if parsed.hostname == "raw.githubusercontent.com":
                valid = any(parsed.path.startswith(f'/{s["repository"]}/{s["commit"]}/') for s in SOURCES.values())
                if not valid:
                    raise ValueError("Raw URL is outside pinned repositories")
            elif parsed.path != "/licenses/LICENSE-2.0.txt":
                raise ValueError("Unregistered Apache path")
        if self.stopped:
            raise ValueError("Stopped after upstream access/rate block")
        delay = max(0.0, self.next_request - time.monotonic())
        if delay:
            time.sleep(delay)
        self.next_request = time.monotonic() + self.interval
        try:
            request = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/plain,application/json;q=0.9"})
            with self.opener.open(request, timeout=25) as response:
                body = response.read(MAX_BYTES + 1)
                if len(body) > MAX_BYTES:
                    raise ValueError("Request exceeds 5 MB bound")
                self.log.append({"url": url, "status": response.status, "bytes": len(body), "sha256": digest(body)})
                return body
        except urllib.error.HTTPError as error:
            self.log.append({"url": url, "status": error.code})
            if error.code in (401, 403, 429):
                self.stopped = True
            raise

    def review_robots(self, host):
        url = f"https://{host}/robots.txt"
        try:
            body = self.request(url, policy=True)
            (LOCAL / f"robots-{host}.txt").write_bytes(body)
            parser = urllib.robotparser.RobotFileParser(url)
            parser.parse(body.decode("utf-8", errors="replace").splitlines())
            delay = parser.crawl_delay(UA) or parser.crawl_delay("*")
            if delay:
                self.interval = max(self.interval, float(delay))
            rate = parser.request_rate(UA) or parser.request_rate("*")
            if rate and rate.requests:
                self.interval = max(self.interval, rate.seconds / rate.requests)
            self.robots[host] = {"status": "reviewed", "url": url, "sha256": digest(body), "parser": parser}
        except urllib.error.HTTPError as error:
            self.robots[host] = {"status": "absent" if error.code in (404, 410) else "unavailable", "url": url, "httpStatus": error.code}


def snapshots(spec):
    directory = LOCAL / spec["directory"]
    reference = json.loads((directory / "git-reference.json").read_text(encoding="utf-8"))
    tree = json.loads((directory / "git-tree.json").read_text(encoding="utf-8"))
    if reference["object"]["sha"] != spec["commit"] or tree["sha"] != spec["commit"] or tree.get("truncated"):
        raise ValueError("Pinned Git metadata mismatch or incomplete tree")
    return directory, {entry["path"]: entry for entry in tree["tree"] if entry.get("type") == "blob"}


def selected_files(spec):
    directory, entries = snapshots(spec)
    files = list(spec["files"])
    if spec is SOURCES["animations"] and (directory / "dist/cssanimation.css").is_file():
        text = (directory / "dist/cssanimation.css").read_text(encoding="utf-8")
        present = set(re.findall(r"\.ca__fx-([\w-]+)", text))
        files += sorted(name for name in entries if name.startswith("dist/animations/") and name.endswith(".css") and "index" not in name and Path(name).stem.removeprefix("ca__") not in present)
    for filename in files:
        safe_path(filename)
        if filename not in entries or entries[filename].get("size", MAX_BYTES + 1) > MAX_BYTES:
            raise ValueError("Selected file missing from pinned tree or too large")
    if len(files) > 100:
        raise ValueError("More than 100 bounded source documents")
    return directory, entries, files


def manifest(spec):
    directory, entries, files = selected_files(spec)
    result = {"repository": spec["repository"], "commit": spec["commit"], "verifiedAt": VERIFIED_DATE, "files": []}
    previous_path = directory / "manifest.json"
    previous = json.loads(previous_path.read_text(encoding="utf-8")) if previous_path.is_file() else None
    previous_hashes = {row["path"]: row["sha256"] for row in previous["files"]} if previous else {}
    for filename in ["git-reference.json", "git-tree.json", *files]:
        body = (directory / filename).read_bytes()
        sha = digest(body)
        if previous and previous_hashes.get(filename) != sha:
            raise ValueError("Cached SHA256 differs from recorded manifest: " + filename)
        blob = hashlib.sha1(b"blob " + str(len(body)).encode("ascii") + b"\0" + body).hexdigest()
        if filename in entries and blob != entries[filename]["sha"]:
            raise ValueError("Original file differs from pinned Git blob: " + filename)
        result["files"].append({"path": filename, "bytes": len(body), "sha256": sha,
            "gitBlobSha1": entries.get(filename, {}).get("sha"), "sourceUrl": source_url(spec, filename) if filename in entries else None})
    save_json(previous_path, result)
    return result


def fetch_sources(collector):
    for host in ("raw.githubusercontent.com", "www.apache.org"):
        collector.review_robots(host)
    if any(r["status"] == "unavailable" for r in collector.robots.values()):
        raise ValueError("Cannot review an upstream robots policy")
    for spec in SOURCES.values():
        directory, entries = snapshots(spec)
        # Fetch the bundle before selecting standalone files missing from it.
        for filename in spec["files"]:
            if not (directory / filename).is_file():
                body = collector.request(f'https://raw.githubusercontent.com/{spec["repository"]}/{spec["commit"]}/{filename}')
                path = directory / safe_path(filename); path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(body)
        _, _, files = selected_files(spec)
        for filename in files:
            if not (directory / filename).is_file():
                body = collector.request(f'https://raw.githubusercontent.com/{spec["repository"]}/{spec["commit"]}/{filename}')
                path = directory / safe_path(filename); path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(body)
    apache = LOCAL / "apache/LICENSE-2.0.txt"
    if not apache.is_file():
        apache.parent.mkdir(parents=True, exist_ok=True)
        apache.write_bytes(collector.request("https://www.apache.org/licenses/LICENSE-2.0.txt"))
    save_json(LOCAL / "robots-manifest.json", [{key: value for key, value in row.items() if key != "parser"} for row in collector.robots.values()])
    save_json(LOCAL / "fetch-log.json", collector.log)


def blocks(css):
    """Return exact top-level block spans, respecting comments and strings."""
    start = 0; depth = 0; quote = None; index = 0; opening = 0; rows = []
    while index < len(css):
        ch = css[index]
        if quote:
            if ch == "\\": index += 2; continue
            if ch == quote: quote = None
        elif css[index:index + 2] == "/*":
            end = css.find("*/", index + 2)
            if end < 0: raise ValueError("Unclosed CSS comment")
            index = end + 2; continue
        elif ch in "\"'": quote = ch
        elif ch == "{":
            if depth == 0: opening = index
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth < 0: raise ValueError("Unbalanced CSS")
            if depth == 0:
                raw = css[start:index + 1]
                header = re.sub(r"/\*[\s\S]*?\*/", "", css[start:opening]).strip()
                rows.append((header, raw.strip(), start, index + 1)); start = index + 1
        elif ch == ";" and depth == 0: start = index + 1
        index += 1
    if quote or depth: raise ValueError("Unbalanced CSS block/string")
    return rows


def normalized(css):
    return re.sub(r"\s+", "", re.sub(r"/\*[\s\S]*?\*/", "", css))


def identity(css, selectors, keyframes):
    clean = re.sub(r"/\*[\s\S]*?\*/", "", css)
    for index, name in enumerate(keyframes):
        # A keyframe called rotateX is NOT the CSS rotateX() transform function.
        # Rename identifiers only in @keyframes headers and animation declarations.
        token = r"(?<![\w-])" + re.escape(name) + r"(?![\w-]|\s*\()"
        replacement = "KEYFRAME" + str(index)
        clean = re.sub(r"(@(?:-webkit-)?keyframes\s+)" + re.escape(name) + r"\b", lambda match: match[1] + replacement, clean)
        clean = re.sub(r"((?:-webkit-)?animation(?:-name)?\s*:\s*)([^;{}]+)", lambda match: match[1] + re.sub(token, replacement, match[2]), clean)
    for selector in sorted(selectors, key=len, reverse=True):
        clean = clean.replace(selector, ".ASSET")
    return digest(normalized(clean))


class PatternReader(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True); self.rows = []; self.current = None; self.in_style = False

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "section" and re.fullmatch(r"g\d+", attrs.get("id", "")):
            self.current = {"id": attrs["id"], "htmlTag": tag, "css": ""}
        if tag == "style" and self.current is not None: self.in_style = True

    def handle_data(self, data):
        if self.in_style and self.current is not None: self.current["css"] += data

    def handle_endtag(self, tag):
        if tag == "style": self.in_style = False
        if tag == "section" and self.current is not None:
            self.rows.append(self.current); self.current = None


def licenses():
    p = LOCAL / SOURCES["patterns"]["directory"]
    a = LOCAL / SOURCES["animations"]["directory"]
    mit = (p / "LICENCE").read_text(encoding="utf-8")
    grant = (a / "LICENSE").read_text(encoding="utf-8")
    notice = (a / "NOTICE").read_text(encoding="utf-8")
    terms = (LOCAL / "apache/LICENSE-2.0.txt").read_text(encoding="utf-8")
    if "MIT License" not in mit or "Permission is hereby granted, free of charge" not in mit or "Copyright (c) 2022 Temani Afif" not in mit:
        raise ValueError("Pattern MIT permission/copyright mismatch")
    if "Apache License" not in grant or "Attribution Requirement" not in grant or "Shafayetul Islam Pavel" not in notice or "END OF TERMS AND CONDITIONS" not in terms:
        raise ValueError("Apache terms/author notice not verified")
    apache_manifest = json.loads((LOCAL / "apache/manifest.json").read_text(encoding="utf-8"))
    if digest((LOCAL / "apache/LICENSE-2.0.txt").read_bytes()) != apache_manifest["sha256"]:
        raise ValueError("Full Apache license hash mismatch")
    return mit, grant + "\n\n" + notice + "\n\n" + terms


def item_base(spec, filename, notice, asset_name, raw_css, css, dom, adaptations, selectors, keyframes):
    source = source_url(spec, filename)
    directory = LOCAL / spec["directory"]
    original = (directory / filename).read_bytes()
    prefix = "ml-css-pattern" if spec is SOURCES["patterns"] else "ml-cssanimation"
    slug = re.sub(r"[^a-z0-9]+", "-", asset_name.casefold()).strip("-")
    attribution = f"/*\n{notice.strip()}\n\nSource: {source}\nMotion Lab extraction: {adaptations}\n*/\n"
    code = attribution + css.strip() + "\n"
    colors = list(dict.fromkeys(re.findall(r"#[0-9a-fA-F]{8}\b|#[0-9a-fA-F]{6}\b|#[0-9a-fA-F]{3}\b", raw_css)))[:32]
    item = {"id": f"{prefix}-{slug}", "title": f"CSS Pattern {asset_name[1:]}" if spec is SOURCES["patterns"] else "CSS Animation · " + asset_name,
        "description": "원본 HTML의 개별 CSS 배경 패턴입니다. 그라디언트·색상·수치를 유지하고 미리보기용 선택자와 요소 태그만 바꿨습니다." if spec is SOURCES["patterns"] else "원본 CSS 클래스와 키프레임을 분리한 개별 효과입니다. 원본 예제의 텍스트 요소를 독립 div로 표시하며 키프레임·타이밍·반복 횟수는 유지합니다. 한 번 실행되는 효과는 다시 재생할 수 있습니다.",
        "category": "background" if spec is SOURCES["patterns"] else "animation", "tags": ["css", "background", "pattern", "배경"] if spec is SOURCES["patterns"] else ["css", "animation", "모션", asset_name[:100]],
        "sourceUrl": source, "sourceName": spec["name"], "license": spec["license"], "licenseUrl": source_url(spec, spec["licenseFile"]),
        "licenseText": notice, "verifiedAt": VERIFIED_DATE, "verification": "source-and-license-reviewed", "kind": "code", "access": "public", "language": "css",
        "colors": colors, "code": code, "upstreamCommit": spec["commit"], "sourceCommit": spec["commit"], "upstreamSha256": digest(original),
        "codePath": str((directory / filename).relative_to(ROOT)).replace("\\", "/"),
        "preview": {"type": "css", "variant": "background" if spec is SOURCES["patterns"] else asset_name[:120], "dom": dom, "adapted": True},
        "evidence": {"scope": "individual-asset", "artifactPath": filename, "sourceCommit": spec["commit"], "artifactSha256": digest(original),
            "assetSourceSha256": digest(raw_css), "storedCodeSha256": digest(code), "identitySha256": identity(css, selectors, keyframes),
            "sourceUrls": [source, source_url(spec, spec["licenseFile"]), source_url(spec, "index.html" if spec is SOURCES["patterns"] else "docs/animation-preview.html")],
            "component": asset_name, "selectors": selectors, "keyframes": keyframes, "adaptations": adaptations,
            "externalResources": bool(re.search(r"url\s*\(|@import", re.sub(r"/\*[\s\S]*?\*/", "", raw_css), re.I)),
            "rights": "Pinned original source license and entire author notice retained"}}
    return item


def import_patterns(notice):
    spec = SOURCES["patterns"]
    reader = PatternReader(); reader.feed((LOCAL / spec["directory"] / "index.html").read_text(encoding="utf-8"))
    items = []
    for row in reader.rows:
        original = row["css"].strip()
        if not original or not any(header.startswith("#" + row["id"]) for header, *_ in blocks(original)):
            raise ValueError("Pattern DOM/style source mismatch")
        target = ".ml-css-pattern-" + row["id"][1:]
        css = re.sub(r"#" + re.escape(row["id"]) + r"\b", target, original)
        # Stage geometry only. The source background declarations stay unchanged.
        css += f"\n{target} {{ width: 100%; height: 100%; }}"
        dom = {"tag": "div", "className": target[1:]}
        item = item_base(spec, "index.html", notice, row["id"], original, css, dom,
            f'Original <section id="{row["id"]}"> becomes <div class="{target[1:]}">; ID selector becomes class; a 100% preview stage is appended. Background values are unchanged.', [target], [])
        item["evidence"]["originalDom"] = {"tag": "section", "id": row["id"]}
        item["evidence"]["rawCodePath"] = f'data/upstream/css-wave/{spec["directory"]}/assets/{row["id"]}.css'
        raw_path = LOCAL / spec["directory"] / "assets" / (row["id"] + ".css")
        raw_path.parent.mkdir(exist_ok=True); raw_path.write_text(original, encoding="utf-8", newline="\n")
        items.append(item)
    return items


def animation_items(spec, filename, notice, documented):
    css = (LOCAL / spec["directory"] / filename).read_text(encoding="utf-8")
    rows = blocks(css)
    keyframes = {}; styles = {}; base = []; reduced = []
    for header, raw, start, _ in rows:
        match = re.fullmatch(r"@(?:-webkit-)?keyframes\s+([\w-]+)", header)
        if match: keyframes[match[1]] = (raw, start); continue
        classes = re.findall(r"\.ca__fx-([\w-]+)", header)
        if classes:
            for name in classes: styles.setdefault(name, []).append((header, raw, start))
        elif header in (".cssanimation", ".cssanimation span", ".infinite"): base.append(raw)
        elif header.startswith("@media") and "prefers-reduced-motion" in header: reduced.append(raw)
    result = []; skipped = []
    for name, rules in styles.items():
        declarations = "\n".join(raw for _, raw, _ in rules)
        animation_values = " ".join(re.findall(r"(?:^|[;{])\s*(?:-webkit-)?animation(?:-name)?\s*:\s*([^;}]+)", re.sub(r"/\*[\s\S]*?\*/", "", declarations), re.M))
        referenced = [key for key in keyframes if re.search(r"(?<![\w-])" + re.escape(key) + r"(?![\w-])", animation_values)]
        interactive = bool(re.search(r":(?:hover|focus|active)\b", " ".join(header for header, *_ in rules)))
        if not referenced and not (interactive and re.search(r"\btransition(?:-property)?\s*:", declarations)):
            skipped.append({"name": name, "file": filename, "reason": "no referenced keyframe in actual animation or animation-name declaration"}); continue
        if any(k not in keyframes for k in referenced):
            skipped.append({"name": name, "file": filename, "reason": "missing referenced keyframe in source artifact"}); continue
        # Keep the actual keyframe bodies, class rules, shared base and reduced-motion conditions.
        raw_css = "\n\n".join([*base, *[raw for _, raw, _ in rules], *[keyframes[k][0] for k in referenced], *reduced])
        dom = {"tag": "div", "className": "cssanimation ca__fx-" + name, "text": "cssanimation"}
        item = item_base(spec, filename, notice, name, raw_css, raw_css, dom,
            "Original animation classes/keyframes/shared duration/fill/reduced-motion rules extracted without value changes. Source example h2 text element becomes div; no upstream JavaScript is executed.", [".ca__fx-" + name], referenced)
        item["sourceUrl"] += "#L" + str(css.count("\n", 0, min(row[2] for row in rules)) + 1)
        item["evidence"]["classInOriginalExample"] = "ca__fx-" + name in documented
        item["evidence"]["originalDom"] = {"tag": "h2", "id": "previewText", "text": "cssanimation", "class": "cssanimation ca__fx-" + name}
        raw_path = LOCAL / spec["directory"] / "assets" / (name + ".css")
        raw_path.parent.mkdir(exist_ok=True)
        raw_path.write_text(raw_css, encoding="utf-8", newline="\n")
        item["evidence"]["rawCodePath"] = str(raw_path.relative_to(ROOT)).replace("\\", "/")
        if interactive:
            item["category"] = "interaction"
            item["preview"]["requiresInteraction"] = True
        result.append(item)
    return result, skipped


def make_items():
    mit, apache = licenses()
    items = import_patterns(mit)
    spec = SOURCES["animations"]
    directory, _, files = selected_files(spec)
    documented = (directory / "docs/animation-preview.html").read_text(encoding="utf-8")
    skipped = []; documents = []
    for filename in ["dist/cssanimation.css", *[path for path in files if path.startswith("dist/animations/")]]:
        extracted, failures = animation_items(spec, filename, apache, documented)
        items.extend(extracted); skipped.extend(failures)
        documents.append({"path": filename, "candidateItems": len(extracted), "rejectedClasses": len(failures),
            "reason": "no ca__fx class declaration in this standalone artifact" if not extracted and not failures else None})
    ids = set(); fingerprints = {}; result = []; duplicates = []
    for item in items:
        identity_hash = item["evidence"]["identitySha256"]
        if item["id"] in ids or identity_hash in fingerprints:
            duplicates.append({"id": item["id"], "retainedId": fingerprints.get(identity_hash), "identitySha256": identity_hash, "reason": "same ID or source CSS after renaming class/keyframe identifiers"}); continue
        ids.add(item["id"]); fingerprints[identity_hash] = item["id"]; result.append(item)
    sys.path.insert(0, str(ROOT))
    from scripts.build import validate_item
    from scripts.analyze import analyze_items
    for item in result: validate_item(item)
    analyzed = analyze_items(result)
    if len(analyzed) != len(result): raise ValueError("Analysis dropped an asset")
    # Audit evidence against cached immutable source files, not just its schema.
    for item in result:
        evidence = item["evidence"]
        artifact = (ROOT / item["codePath"]).read_bytes()
        raw_css = (ROOT / evidence["rawCodePath"]).read_text(encoding="utf-8")
        if digest(artifact) != evidence["artifactSha256"] or digest(raw_css) != evidence["assetSourceSha256"]:
            raise ValueError("Stored source/snippet hash mismatch: " + item["id"])
        if digest(item["code"]) != evidence["storedCodeSha256"] or item["licenseText"].strip() not in item["code"]:
            raise ValueError("Stored code hash or full license notice mismatch: " + item["id"])
        if any(raw.strip() not in artifact.decode("utf-8") for _, raw, *_ in blocks(raw_css)):
            raise ValueError("Extracted CSS block is absent from the original artifact: " + item["id"])
    inspected_css = re.sub(r"/\*[\s\S]*?\*/", "", "\n".join(item["code"] for item in result))
    properties = sorted(set(re.findall(r"(?:^|[;{])\s*([\w-]+)\s*:", inspected_css, re.M)))
    report = {"verifiedAt": VERIFIED_DATE, "generatedAt": datetime.now(timezone.utc).isoformat(), "items": len(result),
        "categories": dict(Counter(item["category"] for item in result)), "licenses": dict(Counter(item["license"] for item in result)),
        "candidateItems": len(items), "duplicates": duplicates, "skipped": skipped, "sourceDocuments": documents, "cssProperties": properties,
        "externalResourceItems": [item["id"] for item in result if item["evidence"]["externalResources"]],
        "validation": {"schema": len(result), "balancedCSS": len(result), "uniqueIds": len(ids), "distinctIdentitySha256": len(fingerprints),
            "sourceSnippetHashes": len(result), "originalBlocksRetained": len(result), "fullLicenseNoticesRetained": len(result), "licensesVerified": True},
        "sources": [{"repository": s["repository"], "commit": s["commit"], "license": s["license"], "name": s["name"]} for s in SOURCES.values()]}
    save_json(OUTPUT, result); save_json(LOCAL / "report.json", report)
    print(json.dumps({key: report[key] for key in ("items", "candidateItems", "categories", "licenses", "validation")}, ensure_ascii=True), flush=True)
    print("duplicates=" + str(len(duplicates)) + " skipped=" + str(len(skipped)), flush=True)
    return result, report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fetch", action="store_true", help="Fetch registered missing pinned artifacts after robots review; otherwise validate/import cached sources only")
    options = parser.parse_args(); LOCAL.mkdir(parents=True, exist_ok=True)
    if options.fetch: fetch_sources(Collector())
    for spec in SOURCES.values(): manifest(spec)
    make_items()


if __name__ == "__main__":
    main()
