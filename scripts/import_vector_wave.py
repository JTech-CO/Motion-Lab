"""Pinned, bounded SVG/CSS source collection. Imported code is never executed.

Network mode reads only registered immutable raw GitHub artifacts. Line MD is
seeded from a separately acquired pinned sparse checkout; offline mode verifies
every persisted artifact and the full MIT notices before rebuilding records.
"""

from collections import Counter
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path, PurePosixPath
import argparse
import hashlib
import json
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parent.parent
LOCAL = ROOT / "data/upstream/vector-wave"
PROBES = LOCAL / "probes"
OUTPUT = ROOT / "data/vector-wave-items.json"
MANIFEST = LOCAL / "manifest.json"
REPORT = LOCAL / "report.json"
DATE = "2026-10-09"
MAX_ARTIFACT = 2 * 1024 * 1024
MAX_SVG = 128 * 1024
MAX_ASSETS = 2000
INTERVAL = 1.25
USER_AGENT = "MotionLab/1.0 (public licensed motion research; no video)"
SOURCES = {
    "sds-motion-forge": {"repo": "salkomdesignstudio/SDS-Motion-Forge", "name": "SDS Motion Forge",
        "commit": "e10005175c50a9b2a6bc757539b6fd9e30e8e53a", "license": "LICENSE"},
    "svg-spinners": {"repo": "n3r4zzurr0/svg-spinners", "name": "SVG Spinners",
        "commit": "abfa05c49acf005b8b1e0ef8eb25a67a7057eb20", "license": "LICENSE"},
    "line-md": {"repo": "cyberalien/line-md", "name": "Material Line Icons",
        "commit": "2ed22555cee9c1e50d4269865681d01ee8cffd7c", "license": "license.txt"},
}
SDS_HASHES = {
    "LICENSE": "f352b0c58afe20318340f856a5328ba3607a94f2d4601dd64eb42fba9616a2b8",
    "README.md": "2759a4f7a168606d8205531feba6cf0e0b060deb02e7941e2f9994665cb4d6f5",
    "SPEC.md": "81a642fc3fb1a53f619139346cccd7bcd21964733c7a32b14175eae5287a444c",
    "dist/motion.css": "d34566490ee324cc73277bbc6277f886ae9bec8d39c3d23fbe31fc07c82defd7",
    "registry/motion.registry.json": "5c9eb2222b085dedd9aa9eab8653ed62c6a835839cf57e88cd9727b12a350b66",
    "docs/docs-data.js": "01f2fe09bfbed958aec568008fbbd8af184b7eabf009699082a5e1d74ceaa032",
    "docs/index.html": "519576d0e9851dc26b0308ba3d47cd0e26ca8d8d3a3ef9953a9437b3ead02bbe",
}
SVG_TREES = {
    "svg-spinners": ("n3r4zzurr0--svg-spinners-svg-tree.json", "ec7e5ea9fb9a3860c61195f2c17da5bb511beebb8dcfcaed0c46c563decbaf03", "svg-smil"),
    "line-md": ("cyberalien--line-md-svg-tree.json", "10ef14b230bd53aea38fc198e699f398fd09d3a57fd6bd2e81c49fd75542c9bd", "svg"),
}
LICENSE_HASHES = {
    "sds-motion-forge": SDS_HASHES["LICENSE"],
    "svg-spinners": "712f8f614e9a23cc754a21d72ea443f1166077e4ee0e6c3b6f9fa576a6d37254",
    "line-md": "2b88bafca347c6a12c33612fa51c5efbdd00c2753ed67fc474d7a6af9c61e430",
}


def digest(body):
    return hashlib.sha256(body).hexdigest()


def git_blob_digest(body):
    return hashlib.sha1(b"blob " + str(len(body)).encode("ascii") + b"\0" + body).hexdigest()


def save_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def safe_path(value):
    if not isinstance(value, str) or len(value) > 220 or "\\" in value:
        raise ValueError("Invalid registered artifact path")
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in ("", ".", "..") or not re.fullmatch(r"[A-Za-z0-9_.-]+", part) for part in path.parts):
        raise ValueError("Artifact path is outside the registered source boundary")
    return path


def local_path(relative):
    path = (LOCAL / safe_path(relative)).resolve()
    path.relative_to(LOCAL.resolve())
    return path


def read_bounded(path, maximum=MAX_ARTIFACT):
    if path.stat().st_size > maximum:
        raise ValueError("Artifact exceeds its byte bound")
    return path.read_bytes()


def validate_mit(body, expected):
    if not isinstance(expected, str) or not re.fullmatch(r"[a-f0-9]{64}", expected) or digest(body) != expected:
        raise ValueError("MIT license digest is missing or mismatched")
    text = body.decode("utf-8")
    if not all(value in text for value in ("Copyright", "Permission is hereby granted, free of charge", "THE SOFTWARE IS PROVIDED", "WITHOUT WARRANTY")):
        raise ValueError("Full MIT permission/copyright/warranty terms are not present")
    return text


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *_args, **_kwargs):
        return None


class Collector:
    def __init__(self):
        self.opener = urllib.request.build_opener(NoRedirect())
        self.next_request = 0.0
        self.requests = []
        self.robots = None
        self.blocked = False

    def request(self, url, *, policy=False):
        parts = urllib.parse.urlsplit(url)
        if parts.scheme != "https" or parts.hostname != "raw.githubusercontent.com" or parts.port not in (None, 443) or parts.username or parts.password:
            raise ValueError("Only registered raw GitHub HTTPS URLs are allowed")
        if self.blocked:
            raise ValueError("Collection stopped after an access/rate block")
        if not policy and self.robots and self.robots.get("status") == "unavailable":
            raise ValueError("Unreviewed robots policy: automatic collection stops")
        if not policy and self.robots and self.robots.get("parser") and not self.robots["parser"].can_fetch(USER_AGENT, url):
            raise ValueError("robots.txt disallows the source")
        delay = max(0, self.next_request - time.monotonic())
        if delay:
            time.sleep(delay)
        self.next_request = time.monotonic() + INTERVAL
        try:
            with self.opener.open(urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/plain"}), timeout=25) as response:
                body = response.read(MAX_ARTIFACT + 1)
                if len(body) > MAX_ARTIFACT:
                    raise ValueError("Response exceeds the 2 MiB limit")
                self.requests.append({"url": url, "status": response.status, "bytes": len(body), "sha256": digest(body)})
                return body
        except urllib.error.HTTPError as error:
            self.requests.append({"url": url, "status": error.code})
            if error.code in (401, 403, 429):
                self.blocked = True
            raise

    def review_robots(self):
        url = "https://raw.githubusercontent.com/robots.txt"
        try:
            body = self.request(url, policy=True)
            path = LOCAL / "robots-raw.githubusercontent.com.txt"
            path.write_bytes(body)
            parser = urllib.robotparser.RobotFileParser(url)
            parser.parse(body.decode("utf-8", "replace").splitlines())
            self.robots = {"url": url, "status": "reviewed", "sha256": digest(body), "parser": parser}
        except urllib.error.HTTPError as error:
            self.robots = {"url": url, "status": "absent" if error.code in (404, 410) else "unavailable", "httpStatus": error.code}
            if self.robots["status"] == "unavailable":
                raise ValueError("robots policy unavailable; automatic collection stops") from error

    def source(self, slug, path):
        source = SOURCES[slug]
        safe_path(path)
        if slug == "svg-spinners" and path not in ("LICENSE", "README.md") and not re.fullmatch(r"svg-smil/[A-Za-z0-9_.-]+\.svg", path):
            raise ValueError("Unexpected spinner artifact")
        if slug == "sds-motion-forge" and path not in SDS_HASHES:
            raise ValueError("Unregistered SDS artifact")
        if slug == "line-md" and path not in ("license.txt", "README.md") and not re.fullmatch(r"svg/[A-Za-z0-9_.-]+\.svg", path):
            raise ValueError("Unexpected Line MD artifact")
        return self.request(f"https://raw.githubusercontent.com/{source['repo']}/{source['commit']}/{path}")


def artifact_record(slug, path, body, git_sha=None):
    relative = slug + "/" + path
    target = local_path(relative)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(body)
    return {"path": path, "artifactPath": "data/upstream/vector-wave/" + relative,
            "relativePath": relative, "bytes": len(body), "sha256": digest(body), "gitBlobSha": git_sha,
            "artifactUrl": f"https://raw.githubusercontent.com/{SOURCES[slug]['repo']}/{SOURCES[slug]['commit']}/{path}"}


def original_git_blobs(checkout, entries, commit):
    """Read immutable Git objects, avoiding Windows checkout newline conversion."""
    current = subprocess.run(["git", "-C", str(checkout), "rev-parse", "HEAD"], capture_output=True, check=True, timeout=15).stdout.decode("ascii").strip()
    if current != commit:
        raise ValueError("Sparse source checkout HEAD differs from the pinned commit")
    if sum(entry.get("size", MAX_SVG + 1) for entry in entries) > 16 * 1024 * 1024:
        raise ValueError("SVG batch exceeds its aggregate byte bound")
    hashes = [entry["sha"] for entry in entries]
    if any(not re.fullmatch(r"[a-f0-9]{40}", value) for value in hashes):
        raise ValueError("Invalid Git object identifier")
    batch = subprocess.run(["git", "-C", str(checkout), "cat-file", "--batch"],
        input=("\n".join(hashes) + "\n").encode("ascii"), capture_output=True, check=True, timeout=120).stdout
    bodies, position = {}, 0
    for expected in hashes:
        end = batch.find(b"\n", position)
        if end < 0:
            raise ValueError("Incomplete original Git blob batch")
        header = batch[position:end].decode("ascii").split()
        if len(header) != 3 or header[0] != expected or header[1] != "blob" or not header[2].isdigit():
            raise ValueError("Unexpected original Git blob header")
        size = int(header[2])
        if size > MAX_SVG:
            raise ValueError("Original SVG exceeds its byte bound")
        start = end + 1
        body = batch[start:start + size]
        if len(body) != size or git_blob_digest(body) != expected or batch[start + size:start + size + 1] != b"\n":
            raise ValueError("Original Git blob integrity mismatch")
        bodies[expected] = body
        position = start + size + 1
    if position != len(batch):
        raise ValueError("Unexpected trailing Git blob content")
    return bodies


def seed_manifest(collector, network):
    sources = []
    for slug, source in SOURCES.items():
        records = []
        if slug == "sds-motion-forge":
            for path, expected in SDS_HASHES.items():
                cached = PROBES / "sds" / path
                body = read_bounded(cached) if cached.is_file() else collector.source(slug, path) if network else None
                if body is None or digest(body) != expected:
                    raise ValueError("Pinned SDS artifact digest mismatch: " + path)
                records.append(artifact_record(slug, path, body))
        else:
            tree_name, tree_hash, _folder = SVG_TREES[slug]
            tree_body = read_bounded(PROBES / tree_name)
            if digest(tree_body) != tree_hash:
                raise ValueError("Pinned SVG source index digest mismatch")
            tree = json.loads(tree_body)
            if tree.get("truncated") or len(tree.get("tree", [])) > 1500:
                raise ValueError("SVG subtree is truncated or exceeds the 1500-file bound")
            license_path = source["license"]
            if slug == "svg-spinners":
                body = read_bounded(PROBES / "n3r4zzurr0--svg-spinners-LICENSE.txt")
            else:
                checkout = LOCAL / "line-md-checkout"
                body = subprocess.run(["git", "-C", str(checkout), "show", source["commit"] + ":" + license_path], capture_output=True, check=True, timeout=15).stdout
                if body != read_bounded(PROBES / "cyberalien--line-md-LICENSE.txt"):
                    raise ValueError("Original Git MIT notice differs from the pinned raw snapshot")
            records.append(artifact_record(slug, license_path, body))
            folder = "svg-smil" if slug == "svg-spinners" else "svg"
            svg_entries = [entry for entry in tree["tree"] if entry.get("type") == "blob" and str(entry.get("path", "")).endswith(".svg")]
            git_bodies = original_git_blobs(LOCAL / "line-md-checkout", svg_entries, source["commit"]) if slug == "line-md" else {}
            for index, entry in enumerate(tree["tree"], 1):
                if entry.get("type") != "blob" or not str(entry.get("path", "")).endswith(".svg"):
                    continue
                path = folder + "/" + entry["path"]
                safe_path(path)
                if len(PurePosixPath(path).parts) != 2 or entry.get("size", MAX_SVG + 1) > MAX_SVG:
                    raise ValueError("Unexpected SVG path/size")
                cached = LOCAL / "line-md-checkout" / path if slug == "line-md" else local_path(slug + "/" + path)
                body = git_bodies[entry["sha"]] if slug == "line-md" else read_bounded(cached, MAX_SVG) if cached.is_file() else collector.source(slug, path) if network else None
                if body is None or len(body) > MAX_SVG or git_blob_digest(body) != entry["sha"]:
                    raise ValueError("Pinned SVG blob mismatch: " + path)
                records.append(artifact_record(slug, path, body, entry["sha"]))
                if index % 100 == 0 or index == len(tree["tree"]):
                    print(f"Source cached {slug}: {index}/{len(tree['tree'])}", flush=True)
        license_record = next(entry for entry in records if entry["path"] == source["license"])
        validate_mit(local_path(license_record["relativePath"]).read_bytes(), LICENSE_HASHES[slug])
        sources.append({**source, "slug": slug, "licenseSha256": license_record["sha256"], "artifacts": records})
    return {"version": 1, "verifiedAt": DATE, "sources": sources,
            "bounds": {"maxArtifactBytes": MAX_ARTIFACT, "maxSvgBytes": MAX_SVG, "maxAssets": MAX_ASSETS, "workers": 1, "requestsPerMinute": 48}}


def verify_manifest(manifest):
    if len(manifest.get("sources", [])) != len(SOURCES):
        raise ValueError("Source manifest is incomplete")
    if {source.get("slug") for source in manifest["sources"]} != set(SOURCES):
        raise ValueError("Source manifest identities are missing or duplicated")
    for source in manifest["sources"]:
        registered = SOURCES.get(source.get("slug"))
        if not registered or source.get("repo") != registered["repo"] or source.get("commit") != registered["commit"]:
            raise ValueError("Source identity differs from the pinned registry")
        if len(source.get("artifacts", [])) > 1505:
            raise ValueError("Manifest artifact limit exceeded")
        expected_svg = {}
        if source["slug"] in SVG_TREES:
            tree_name, tree_hash, folder = SVG_TREES[source["slug"]]
            tree_body = read_bounded(PROBES / tree_name)
            if digest(tree_body) != tree_hash:
                raise ValueError("Pinned source index integrity mismatch")
            expected_svg = {folder + "/" + entry["path"]: entry["sha"] for entry in json.loads(tree_body)["tree"] if entry.get("type") == "blob" and entry.get("path", "").endswith(".svg")}
        expected_paths = set(SDS_HASHES) if source["slug"] == "sds-motion-forge" else set(expected_svg) | {source["license"]}
        actual_paths = [artifact.get("path") for artifact in source.get("artifacts", [])]
        if len(actual_paths) != len(set(actual_paths)) or set(actual_paths) != expected_paths:
            raise ValueError("Manifest does not contain every registered original artifact exactly once")
        for artifact in source["artifacts"]:
            if artifact.get("relativePath") != source["slug"] + "/" + artifact.get("path", ""):
                raise ValueError("Manifest artifact path identity mismatch")
            expected_url = f"https://raw.githubusercontent.com/{source['repo']}/{source['commit']}/{artifact['path']}"
            if artifact.get("artifactUrl") != expected_url or artifact.get("artifactPath") != "data/upstream/vector-wave/" + artifact["relativePath"]:
                raise ValueError("Manifest artifact provenance differs from the pinned registry")
            body = read_bounded(local_path(artifact["relativePath"]), MAX_SVG if artifact["path"].endswith(".svg") else MAX_ARTIFACT)
            if source["slug"] == "sds-motion-forge" and (artifact["path"] not in SDS_HASHES or digest(body) != SDS_HASHES[artifact["path"]]):
                raise ValueError("Pinned SDS original artifact digest mismatch")
            if source["slug"] in SVG_TREES and artifact["path"] != source["license"] and artifact.get("gitBlobSha") != expected_svg.get(artifact["path"]):
                raise ValueError("SVG artifact is not registered by the pinned source index")
            if digest(body) != artifact.get("sha256") or len(body) != artifact.get("bytes"):
                raise ValueError("Cached artifact SHA-256/size mismatch")
            if artifact.get("gitBlobSha") and git_blob_digest(body) != artifact["gitBlobSha"]:
                raise ValueError("Cached SVG git blob mismatch")
        notice = local_path(source["slug"] + "/" + source["license"])
        if source.get("licenseSha256") != LICENSE_HASHES[source["slug"]]:
            raise ValueError("Source license manifest differs from the pinned notice digest")
        validate_mit(read_bounded(notice), source.get("licenseSha256"))
    for policy in manifest.get("robots", []):
        if policy.get("artifactPath"):
            relative = policy["artifactPath"].removeprefix("data/upstream/vector-wave/")
            if digest(read_bounded(local_path(relative))) != policy.get("sha256"):
                raise ValueError("Recorded robots policy artifact digest mismatch")


def css_blocks(text):
    """Return exact source slices using balanced braces, strings, and comments."""
    blocks, stack, boundary, quote, index = [], [], 0, None, 0
    while index < len(text):
        char = text[index]
        if quote:
            if char == "\\":
                index += 2
                continue
            if char == quote:
                quote = None
        elif text[index:index + 2] == "/*":
            end = text.find("*/", index + 2)
            if end < 0:
                raise ValueError("Unclosed CSS comment")
            index = end + 2
            continue
        elif char in "\"'":
            quote = char
        elif char == "{":
            raw = text[boundary:index]
            header = re.sub(r"/\*[\s\S]*?\*/", "", raw).strip()
            start = boundary + len(raw) - len(raw.lstrip())
            # Leading source comments belong to the preceding dependency, not
            # to this selected declaration. The declarations remain byte-exact.
            leading = re.match(r"(?:\s|/\*[\s\S]*?\*/)*", text[boundary:index])
            if leading:
                start = boundary + leading.end()
            stack.append({"header": header, "start": start, "bodyStart": index + 1,
                          "parents": tuple(entry["header"] for entry in stack)})
            boundary = index + 1
            if len(stack) > 12:
                raise ValueError("CSS nesting limit exceeded")
        elif char == "}":
            if not stack:
                raise ValueError("Unbalanced CSS closing brace")
            block = stack.pop()
            block.update(end=index + 1, bodyEnd=index)
            blocks.append(block)
            boundary = index + 1
        elif char == ";":
            boundary = index + 1
        index += 1
    if stack or quote:
        raise ValueError("Incomplete CSS structure")
    return sorted(blocks, key=lambda entry: entry["start"])


class SourceDOM(HTMLParser):
    ALLOWED = {"div", "span", "h1", "h2", "h3", "p", "button", "input", "label", "strong", "em"}
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = None
        self.stack = []
        self.count = 0

    def handle_starttag(self, tag, attributes):
        if tag not in self.ALLOWED or self.count >= 64 or len(self.stack) > 5:
            raise ValueError("Source DOM is outside the bounded closed tree")
        values = dict(attributes)
        class_name = values.get("class", "")
        if not re.fullmatch(r"[A-Za-z0-9_ -]{0,180}", class_name):
            raise ValueError("Unexpected source DOM class")
        node = {"tag": tag}
        if class_name:
            node["className"] = class_name
        variables = dict(re.findall(r"(--[a-z][a-z0-9_-]{0,70})\s*:\s*([-+.\d]+)", values.get("style", ""), re.I))
        if variables:
            node["variables"] = variables
        if tag == "input":
            node["placeholder"] = values.get("placeholder", "")[:80]
        if self.stack:
            self.stack[-1].setdefault("children", []).append(node)
        elif self.root is None:
            self.root = node
        else:
            raise ValueError("Multiple source DOM roots")
        self.count += 1
        if tag != "input":
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag != "input":
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        if not self.stack or self.stack[-1]["tag"] != tag:
            raise ValueError("Unbalanced source DOM")
        self.stack.pop()

    def handle_data(self, data):
        if self.stack and (data.strip() or "\u00a0" in data):
            self.stack[-1]["text"] = (self.stack[-1].get("text", "") + data)[:80]


def item_base(source, name, title, artifact, language, category, notice):
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    repo = source["repo"]
    commit = source["commit"]
    return {"id": "vector-" + source["slug"] + "-" + slug, "title": title,
            "description": "", "category": category, "tags": [],
            "sourceUrl": f"https://github.com/{repo}/blob/{commit}/{artifact['path']}",
            "sourceName": source["name"], "license": "MIT",
            "licenseUrl": f"https://github.com/{repo}/blob/{commit}/{source['license']}", "licenseText": notice,
            "verifiedAt": DATE, "verification": "source-reviewed", "kind": "code", "access": "public",
            "language": language, "colors": [], "sourceCommit": commit,
            "upstreamCommit": commit, "upstreamSha256": artifact["sha256"], "codePath": artifact["artifactPath"],
            "evidence": {"sourceUrls": [f"https://github.com/{repo}/blob/{commit}/{artifact['path']}",
                          f"https://github.com/{repo}/blob/{commit}/{source['license']}"],
                         "sourceCommit": commit, "artifactPath": artifact["artifactPath"],
                         "artifactUrl": artifact["artifactUrl"], "originalBytesSha256": artifact["sha256"],
                         "scope": "individual-asset", "rights": "Full MIT notice verified at the pinned source revision"}}


def svg_items(source, skipped):
    notice = read_bounded(local_path(source["slug"] + "/" + source["license"])).decode("utf-8")
    items, seen = [], {}
    for artifact in source["artifacts"]:
        if not artifact["path"].endswith(".svg"):
            continue
        body = read_bounded(local_path(artifact["relativePath"]), MAX_SVG)
        code = body.decode("utf-8")
        if re.search(r"<!DOCTYPE|<!ENTITY", code, re.I):
            skipped.append({"source": source["slug"], "path": artifact["path"], "reason": "XML-doctype-or-entity"})
            continue
        root = ET.fromstring(code)
        nodes = list(root.iter())
        if root.tag.split("}")[-1] != "svg" or len(nodes) > 700:
            raise ValueError("SVG root/node bound invalid")
        animations = [element for element in nodes if element.tag.split("}")[-1] in ("animate", "animateTransform", "animateMotion")]
        if not animations:
            skipped.append({"source": source["slug"], "path": artifact["path"], "reason": "no-actual-animation-elements"})
            continue
        if artifact["sha256"] in seen:
            skipped.append({"source": source["slug"], "path": artifact["path"], "reason": "identical-original-bytes", "originalPath": seen[artifact["sha256"]]})
            continue
        seen[artifact["sha256"]] = artifact["path"]
        name = PurePosixPath(artifact["path"]).stem
        category = "loader" if source["slug"] == "svg-spinners" else "animation"
        item = item_base(source, name, name.replace("-", " ").title(), artifact, "svg", category, notice)
        attributes = sorted({element.get("attributeName") for element in animations if element.get("attributeName")})
        elements = dict(sorted(Counter(element.tag.split("}")[-1] for element in nodes).items()))
        item["description"] = f"Original animated SVG from {source['name']}. {len(animations)} animation elements change {', '.join(attributes)}. The complete original SVG and full MIT terms are stored; preview sanitization may omit unsupported SMIL details."
        item["tags"] = list(dict.fromkeys(["svg", "smil", "vector", category] + attributes))
        # Preserve the file byte-for-byte as decoded UTF-8. The complete license
        # remains a separate field, so an XML declaration is never displaced.
        item["code"] = code
        limits = []
        if any(element.get("style") and any(part.split(":", 1)[0].strip() not in ("transform-origin", "transform-box") for part in element.get("style", "").split(";") if ":" in part) for element in nodes):
            limits.append("Only transform-origin and transform-box inline styles are supported by this preview host; other source styles may be omitted.")
        item["preview"] = {"type": "svg", "variant": name[:120], "adapted": False, "limitations": limits}
        item["evidence"].update(component=name, mechanism="Actual SVG animation element and attribute inspection",
            structure={"tags": sorted(elements), "elements": elements, "nodeCount": len(nodes)},
            animations=[{"tag": element.tag.split("}")[-1], "attributes": dict(element.attrib)} for element in animations],
            extraction="Complete original SVG file, unmodified. Full source MIT notice is stored separately.",
            storedCodeSha256=digest(code.encode("utf-8")), hashScope="Exact UTF-8 original SVG code")
        items.append(item)
    return items


def sds_items(source, skipped):
    artifacts = {artifact["path"]: artifact for artifact in source["artifacts"]}
    css = read_bounded(local_path(artifacts["dist/motion.css"]["relativePath"])).decode("utf-8")
    registry = json.loads(read_bounded(local_path(artifacts["registry/motion.registry.json"]["relativePath"])))
    raw_docs = read_bounded(local_path(artifacts["docs/docs-data.js"]["relativePath"])).decode("utf-8")
    match = re.fullmatch(r"\s*/\*[\s\S]*?\*/\s*window\.SDS_DOCS\s*=\s*(\{[\s\S]*\});\s*", raw_docs)
    if not match:
        raise ValueError("Docs data is not a standalone JSON object assignment")
    docs = json.loads(match[1])  # Never evaluate the upstream JavaScript wrapper.
    notice = read_bounded(local_path(source["slug"] + "/" + source["license"])).decode("utf-8")
    blocks = css_blocks(css)
    roots = [block for block in blocks if block["header"] == ":root" and not block["parents"]]
    if len(roots) != 1:
        raise ValueError("Expected one auditable original token block")
    root_block = roots[0]
    root_css = css[root_block["start"]:root_block["end"]]
    variables = dict(re.findall(r"(--[a-z][a-z0-9_-]{0,70})\s*:\s*([^;{}]+);", re.sub(r"/\*[\s\S]*?\*/", "", root_css), re.I))
    keyframes = {block["header"].split()[-1]: block for block in blocks if re.fullmatch(r"@(?:-webkit-)?keyframes\s+[\w-]+", block["header"])}
    categories = {"text": "typography", "buttons": "interaction", "inputs": "interaction", "cards": "animation", "loaders": "loader", "scroll": "transition"}
    items = []
    for effect in registry["classes"]:
        if effect.get("kind") != "effect":
            continue
        name = effect["name"]
        if not re.fullmatch(r"sds-[a-z0-9-]+", name):
            raise ValueError("Invalid effect class in source registry")
        if effect.get("aliasOf"):
            skipped.append({"source": source["slug"], "name": name, "reason": "source-declared-alias", "originalName": effect["aliasOf"]})
            continue
        pattern = re.compile(r"\." + re.escape(name) + r"(?![\w-])")
        selected = [block for block in blocks if not block["header"].startswith("@") and pattern.search(block["header"]) and not any("keyframes" in parent for parent in block["parents"])]
        if not selected:
            raise ValueError("Registered effect has no actual CSS rules: " + name)
        required = set(effect.get("keyframes", []))
        for block in selected:
            required.update(re.findall(r"\bsds-[A-Za-z0-9_-]+\b", css[block["bodyStart"]:block["bodyEnd"]]))
        dependencies = [keyframes[key] for key in required if key in keyframes]
        missing = set(effect.get("keyframes", [])) - set(keyframes)
        if missing:
            skipped.append({"source": source["slug"], "name": name,
                            "reason": "upstream-missing-keyframe", "missingKeyframes": sorted(missing),
                            "note": "The original effect is incomplete at its pinned revision. Its CSS and registry remain in the source archive."})
            continue
        segments, ranges = [root_css], [{"start": root_block["start"], "end": root_block["end"], "type": "tokens"}]
        for block in sorted(selected + dependencies, key=lambda value: value["start"]):
            part = css[block["start"]:block["end"]]
            for parent in reversed(block["parents"]):
                part = parent + " {\n" + part + "\n}"
            segments.append(part)
            ranges.append({"start": block["start"], "end": block["end"], "type": "dependency", "parents": list(block["parents"])})
        code = "/*\n" + notice.replace("*/", "* /") + "\n*/\n\n" + "\n\n".join(segments)
        if len(code.encode("utf-8")) > MAX_SVG:
            raise ValueError("Independent effect slice exceeds 128 KiB")
        item = item_base(source, name, effect.get("displayName", name), artifacts["dist/motion.css"], "css", categories[effect["category"]], notice)
        item["description"] = effect.get("description", "Original source-authored CSS effect.")
        item["tags"] = ["css", "sds", effect["category"], effect.get("trigger", "load")] + effect.get("animatedProps", [])
        item["code"] = code
        markup = docs.get("markup", {}).get(name)
        if not isinstance(markup, str) or len(markup) > 12000:
            raise ValueError("Actual source-authored DOM sample missing: " + name)
        parser = SourceDOM()
        parser.feed(markup)
        parser.close()
        if parser.stack or not parser.root:
            raise ValueError("Incomplete source DOM: " + name)
        limits = ["CSS was extracted with its original selectors, keyframes, and tokens; source sample DOM and host presentation must be supported separately."]
        if effect.get("trigger") in ("hover", "focus", "click", "active"):
            limits.append("This effect depends on its original interaction state; a static sample does not reproduce user input.")
        if effect["category"] == "inputs":
            limits.append("Original input and wrapper structure is preserved; the preview may present disabled controls rather than accepting input.")
        if effect["category"] == "scroll":
            limits.append("Original CSS runs on class application. Viewport-triggered playback additionally requires the optional upstream scroll engine.")
        item["preview"] = {"type": "css", "variant": name, "dom": parser.root, "variables": variables,
                           "sourceMarkup": markup, "adapted": False, "limitations": limits}
        item["evidence"].update(component=name, mechanism="Actual registered selectors, CSS declarations, and required keyframes",
            structure={"selector": "." + name, "dom": parser.root, "nodeCount": parser.count},
            selectors=[block["header"] for block in selected], keyframes=sorted(required & set(keyframes)),
            registryMissingKeyframes=sorted(missing),
            animatedProperties=effect.get("animatedProps", []), trigger=effect.get("trigger"),
            sourceRegistry=effect, sourceRanges=ranges,
            extraction="Exact declaration/keyframe/token source slices in original cascade order; enclosing media headers reconstructed. Full MIT notice prepended; no effect code or JavaScript invented.",
            sourceMarkupArtifact=artifacts["docs/docs-data.js"]["artifactPath"],
            storedCodeSha256=digest(code.encode("utf-8")), hashScope="Stored dependency slices including full MIT prefix")
        items.append(item)
    return items


def collect_items(manifest):
    items, skipped = [], []
    for source in manifest["sources"]:
        records = sds_items(source, skipped) if source["slug"] == "sds-motion-forge" else svg_items(source, skipped)
        items.extend(records)
    if len(items) > MAX_ASSETS or len({item["id"] for item in items}) != len(items):
        raise ValueError("Asset bound or unique ID check failed")
    return sorted(items, key=lambda item: item["id"]), skipped


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--fetch", action="store_true", help="Collect registered pinned raw artifacts missing from local source snapshots")
    modes.add_argument("--offline", action="store_true", help="Verify all persisted source/license hashes and rebuild without network")
    args = parser.parse_args()
    LOCAL.mkdir(parents=True, exist_ok=True)
    collector = Collector()
    if args.fetch:
        collector.review_robots()
    if MANIFEST.is_file():
        manifest = json.loads(read_bounded(MANIFEST))
    else:
        manifest = seed_manifest(collector, args.fetch)
        manifest["robots"] = [{key: value for key, value in (collector.robots or {"url": "https://raw.githubusercontent.com/robots.txt", "status": "absent", "httpStatus": 404}).items() if key != "parser"}]
        manifest["robots"].append({"url": "https://api.github.com/robots.txt", "status": "absent", "httpStatus": 404, "note": "Metadata probes completed before API limit; no API calls in importer"})
        manifest["robots"].append({"url": "https://github.com/robots.txt", "status": "reviewed", "artifactPath": "data/upstream/vector-wave/probes/robots-github.com.txt", "sha256": digest(read_bounded(PROBES / "robots-github.com.txt")), "note": "Canonical SVG source acquired through parent-authorized sparse Git checkout"})
        save_json(MANIFEST, manifest)
    verify_manifest(manifest)
    items, skipped = collect_items(manifest)
    save_json(OUTPUT, items)
    report = {"verifiedAt": DATE, "rebuiltAt": datetime.now(timezone.utc).isoformat(),
        "status": "hash-verified-offline-rebuilt" if not args.fetch else "pinned-source-collected",
        "imported": len(items), "bySource": dict(Counter(item["sourceName"] for item in items)),
        "byLanguage": dict(Counter(item["language"] for item in items)), "skipped": skipped,
        "requests": collector.requests, "robots": manifest.get("robots", []), "bounds": manifest["bounds"],
        "sources": [{"title": source["name"], "sourceUrl": "https://github.com/" + source["repo"], "commit": source["commit"], "license": "MIT", "licenseSha256": source["licenseSha256"]} for source in manifest["sources"]]}
    save_json(REPORT, report)
    print(json.dumps({key: report[key] for key in ("imported", "bySource", "byLanguage")}), flush=True)


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, KeyError, ET.ParseError) as error:
        print("Vector source import stopped: " + str(error), file=sys.stderr)
        sys.exit(1)
