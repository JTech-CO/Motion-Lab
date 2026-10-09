"""Bounded, pinned read-only preflight. No catalog input is created."""
from collections import Counter
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import re
import tarfile
import time
import urllib.error
import urllib.request
import urllib.robotparser
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[4]
LOCAL = Path(__file__).resolve().parent
PIN = json.loads((LOCAL / "pin.json").read_text(encoding="utf-8"))
TREE = json.loads((LOCAL / "tree.json").read_text(encoding="utf-8"))
assert TREE["sha"] == PIN["tree"] and not TREE.get("truncated")
ENTRIES = {x["path"]: x for x in TREE["tree"] if x.get("type") == "blob"}
PATHS = json.loads((LOCAL / "sample-paths.json").read_text(encoding="utf-8"))
assert len(PATHS) <= 120 and len(set(PATHS)) == len(PATHS)
assert all(re.fullmatch(r"(?:lorc|delapouite)/[a-z0-9-]+\.svg", x) and ENTRIES[x]["mode"] == "100644" and ENTRIES[x]["size"] <= 65536 for x in PATHS)
UA = "MotionLabSourcePreflight/1.0 (+https://github.com/JTech-CO/Motion-Lab)"
URL = f"https://codeload.github.com/game-icons/icons/tar.gz/{PIN['commit']}"
LOG = []
class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *_args, **_kwargs):
        return None
OPENER = urllib.request.build_opener(NoRedirect())
def request(url, bound):
    if url not in (URL, "https://codeload.github.com/robots.txt", "https://game-icons.net/robots.txt"):
        raise ValueError("Unregistered HTTPS URL")
    try:
        with OPENER.open(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=40) as response:
            body = response.read(bound + 1)
            if len(body) > bound: raise ValueError("Response byte limit")
            LOG.append({"url": url, "status": response.status, "bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()})
            return body
    except urllib.error.HTTPError as error:
        LOG.append({"url": url, "status": error.code})
        raise

robots_report = {}
interval = 1.25
try:
    body = request("https://codeload.github.com/robots.txt", 65536)
    (LOCAL / "robots-codeload.github.com.txt").write_bytes(body)
    rules = urllib.robotparser.RobotFileParser("https://codeload.github.com/robots.txt")
    rules.parse(body.decode("utf-8", "replace").splitlines())
    assert rules.can_fetch(UA, URL), "Robots disallows pinned archive"
    delay = rules.crawl_delay(UA) or rules.crawl_delay("*")
    rate = rules.request_rate(UA) or rules.request_rate("*")
    interval = max(interval, float(delay or 0), (rate.seconds / rate.requests) if rate and rate.requests else 0)
    robots_report["repositoryArchive"] = {"status": "reviewed", "allowed": True, "intervalSeconds": interval}
except urllib.error.HTTPError as error:
    if error.code not in (404, 410): raise
    robots_report["repositoryArchive"] = {"status": "absent", "httpStatus": error.code, "allowed": True, "intervalSeconds": interval}
time.sleep(interval)
archive = request(URL, 32 * 1024 * 1024)
samples = {}
with tarfile.open(fileobj=io.BytesIO(archive), mode="r:gz") as tar:
    members = tar.getmembers()
    assert len(members) <= 5000 and sum(max(0, x.size) for x in members) <= 80 * 1024 * 1024
    for member in members:
        path = PurePosixPath(member.name)
        if path.is_absolute() or ".." in path.parts: raise ValueError("Unsafe archive path")
        relative = PurePosixPath(*path.parts[1:]).as_posix()
        if relative not in set(PATHS + ["README.md", "license.txt"]): continue
        assert member.isfile() and not member.issym() and not member.islnk() and member.size <= 65536
        body = tar.extractfile(member).read(65537)
        blob = hashlib.sha1(f"blob {len(body)}\0".encode() + body).hexdigest()
        assert len(body) == ENTRIES[relative]["size"] and blob == ENTRIES[relative]["sha"], relative
        if relative in ("README.md", "license.txt"):
            (LOCAL / relative).write_bytes(body)
        else:
            target = (LOCAL / "sample" / relative).resolve()
            target.relative_to((LOCAL / "sample").resolve())
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(body)
            samples[relative] = body
assert len(samples) == len(PATHS)
safe_tags = {"svg", "g", "path", "rect", "circle", "ellipse", "line", "polyline", "polygon", "title", "defs", "linearGradient", "radialGradient", "stop"}
safe_attrs = {"viewBox", "width", "height", "x", "y", "x1", "x2", "y1", "y2", "cx", "cy", "r", "rx", "ry", "d", "points", "fill", "stroke", "stroke-width", "stroke-linecap", "stroke-linejoin", "stroke-miterlimit", "fill-rule", "opacity", "transform", "id", "class", "fill-opacity", "stroke-opacity", "preserveAspectRatio", "style"}
records = []
for relative, body in samples.items():
    code = body.decode("utf-8")
    assert not re.search(r"<!DOCTYPE|<!ENTITY", code, re.I)
    tree = ET.fromstring(code)
    nodes = list(tree.iter())
    tags = Counter(node.tag.rsplit("}", 1)[-1] for node in nodes)
    attributes = Counter(name.rsplit("}", 1)[-1] for node in nodes for name in node.attrib)
    unsafe = []
    for node in nodes:
        for name, value in node.attrib.items():
            if name.rsplit("}", 1)[-1] not in safe_attrs or re.search(r"(?:url|expression|image-set)\s*\(|javascript:|https?:|data:", value, re.I): unsafe.append({"name": name, "value": value[:150]})
    geometry = sum(len(node.get("d", "")) + len(node.get("points", "")) for node in nodes)
    author_slug = relative.split("/")[0]
    records.append({"path": relative, "concept": Path(relative).stem, "author": "Lorc" if author_slug == "lorc" else "Delapouite", "license": "CC-BY-3.0", "sourceUrl": f"https://github.com/game-icons/icons/blob/{PIN['commit']}/{relative}", "gitBlobSha1": ENTRIES[relative]["sha"], "sha256": hashlib.sha256(body).hexdigest(), "bytes": len(body), "nodes": len(nodes), "tags": dict(tags), "attributes": dict(attributes), "geometryCharacters": geometry, "safeProfile": not unsafe and set(tags) <= safe_tags and len(nodes) <= 128 and geometry <= 30000, "unsafeAttributes": unsafe})
try:
    time.sleep(interval)
    website_robots = request("https://game-icons.net/robots.txt", 65536)
    (LOCAL / "robots-game-icons.net.txt").write_bytes(website_robots)
    robots_report["website"] = {"status": "read", "sha256": hashlib.sha256(website_robots).hexdigest(), "collectionUsed": False}
except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as error:
    robots_report["website"] = {"status": "unavailable", "reason": str(error)[:150], "collectionUsed": False}
result = {"pin": PIN, "inventory": {"svgFiles": sum(x["path"].endswith(".svg") for x in ENTRIES.values()), "maximumSvgBytes": max(x["size"] for x in ENTRIES.values() if x["path"].endswith(".svg")), "completeTree": True}, "sampleCount": len(records), "safeSamples": sum(x["safeProfile"] for x in records), "sample": records, "robots": robots_report, "networkRequests": LOG, "sourceJavaScriptExecuted": False, "catalogItemsAdded": 0}
(LOCAL / "source-inspection.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"sampleCount": result["sampleCount"], "safeSamples": result["safeSamples"], "robots": robots_report, "catalogItemsAdded": 0}))
