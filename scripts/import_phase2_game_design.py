"""Import a bounded set of licensed, commit-pinned static compositions offline.

No upstream programs or SVG active content execute. Existing canonical records,
every merged variant, repaired originals, and both prior expansion inputs are
immutable comparison dependencies, so re-importing after integration is stable.
"""
from __future__ import annotations
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import shutil
import io
import tarfile
import time
import urllib.error
import urllib.request
import urllib.robotparser
import xml.etree.ElementTree as ET

from import_phase2_design import geometry_rasters, geometry_signature, icon_family, icon_name, raster_near, svg_root
from duplicate_audit_svg import _parse, _timing_pair, _geometry_pair

ROOT = Path(__file__).resolve().parents[1]
LOCAL = ROOT / "data/upstream/phase2-game-design"
SOURCE = LOCAL / "game-icons"
OUTPUT = ROOT / "data/phase2-game-design-items.json"
PREFLIGHT = ROOT / "data/upstream/phase2-motion/game-icons-preflight"
COMMIT = "82d948812bfe3f269ef8f731dcdb07b08160edc4"
TREE_SHA = "819b975fa234b1ef75cc345b9a2856bed8f2a5a4"
TREE_INVENTORY_SHA = "7d01ddec198de9a284faf69b46d543561237e8b245b5db31bcde4698c93e7b8f"
LICENSE_SHA = "e6bc9e9c474700b708f568bac9e5a8a9bcb2b1dad53442f5ba449fcb848b8e76"
BASELINE_SHA = "783e3d88c8aff5bde9e7fcca9206eaf79e151500c548d1af4d063f4de9d2827b"
MOTION_SHA = "9076417e392a6439ec32defa258bce5a84f6fb018e827169e861e30547a68bea"
DESIGN_SHA = "c03896b1177c79d16a8fb03a5687c44121cd8e9b48eae833da0fafa69bfba23d"
AUTHORS = {"lorc": {"name": "Lorc", "url": "http://lorcblog.blogspot.com"}, "delapouite": {"name": "Delapouite", "url": "http://delapouite.com"}}
DATE = "2026-10-09"
RAW_CANDIDATE_BOUND = 199
ACCEPTED_BOUND = 120

def digest(raw):
    return hashlib.sha256(raw).hexdigest()

def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")

def bounded_read(path, maximum=65536):
    path = Path(path)
    if path.is_symlink() or not path.is_file() or path.stat().st_size > maximum:
        raise ValueError("File outside regular-file byte bound: " + str(path))
    return path.read_bytes()

def source_path(relative):
    if not isinstance(relative, str) or not re.fullmatch(r"(?:lorc|delapouite)/[a-z0-9-]+\.svg", relative):
        raise ValueError("Source member outside pinned allowlist")
    safe_root = SOURCE.resolve()
    safe_root.relative_to(ROOT.resolve())
    target = (safe_root / relative).resolve()
    target.relative_to(safe_root)
    return target

def bootstrap():
    """Copy only already verified preflight artifacts into the separate source cache."""
    LOCAL.mkdir(parents=True, exist_ok=True)
    for name in ("pin.json", "tree.json", "sample-paths.json", "source-inspection.json", "license.txt", "README.md", "robots-game-icons.net.txt"):
        shutil.copyfile(PREFLIGHT / name, LOCAL / name)
    paths = json.loads(bounded_read(LOCAL / "sample-paths.json").decode("utf-8"))
    for relative in paths:
        target = source_path(relative)
        target.parent.mkdir(parents=True, exist_ok=True)
        body = bounded_read(PREFLIGHT / "sample" / relative)
        target.write_bytes(body)

def fetch_registered_sources():
    """Download only the approved exact commit, read only registered SVG members."""
    paths = json.loads(bounded_read(LOCAL / "sample-paths.json").decode("utf-8"))
    if not isinstance(paths, list) or len(paths) > RAW_CANDIDATE_BOUND or len(set(paths)) != len(paths):
        raise ValueError("Raw candidate limit exceeded")
    for relative in paths: source_path(relative)
    url = f"https://codeload.github.com/game-icons/icons/tar.gz/{COMMIT}"
    robots_url = "https://codeload.github.com/robots.txt"
    agent = "MotionLab/1.0 (licensed static composition review; no source execution)"
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *_args, **_kwargs): return None
    opener = urllib.request.build_opener(NoRedirect())
    requests = []
    def read(registered_url, maximum):
        if registered_url not in {url, robots_url}: raise ValueError("Unregistered HTTPS URL")
        try:
            with opener.open(urllib.request.Request(registered_url, headers={"User-Agent": agent}), timeout=35) as response:
                body = response.read(maximum + 1)
                if len(body) > maximum: raise ValueError("Response byte limit exceeded")
                requests.append({"url": registered_url, "httpStatus": response.status, "bytes": len(body), "sha256": digest(body)})
                return body
        except urllib.error.HTTPError as error:
            requests.append({"url": registered_url, "httpStatus": error.code})
            raise
    interval = 1.25
    try:
        robots = read(robots_url, 65536)
        rules = urllib.robotparser.RobotFileParser(robots_url)
        rules.parse(robots.decode("utf-8", "replace").splitlines())
        if not rules.can_fetch(agent, url): raise ValueError("Robots disallows pinned archive")
        delay = rules.crawl_delay(agent) or rules.crawl_delay("*") or 0
        rate = rules.request_rate(agent) or rules.request_rate("*")
        interval = max(interval, float(delay), rate.seconds / rate.requests if rate and rate.requests else 0)
        (LOCAL / "robots-codeload.github.com.txt").write_bytes(robots)
        robot_review = {"status": "reviewed", "allowed": True, "sha256": digest(robots)}
    except urllib.error.HTTPError as error:
        if error.code not in {404, 410}: raise
        robot_review = {"status": "absent", "httpStatus": error.code, "allowed": True}
    time.sleep(interval)
    body = read(url, 32 * 1024 * 1024)
    inventory = bounded_read(LOCAL / "tree.json", 4 * 1024 * 1024)
    if digest(inventory) != TREE_INVENTORY_SHA: raise ValueError("Pinned inventory hash mismatch")
    entries = {x["path"]: x for x in json.loads(inventory)["tree"] if x.get("type") == "blob"}
    found = set()
    with tarfile.open(fileobj=io.BytesIO(body), mode="r:gz") as archive:
        members = archive.getmembers()
        if len(members) > 5000 or sum(max(0, member.size) for member in members) > 80 * 1024 * 1024:
            raise ValueError("Expanded archive bounds exceeded")
        for member in members:
            components = Path(member.name).as_posix().split("/")
            if member.name.startswith("/") or ".." in components: raise ValueError("Archive path boundary violation")
            relative = "/".join(components[1:])
            if relative not in paths: continue
            if not member.isfile() or member.issym() or member.islnk() or member.size > 65536: raise ValueError("Unsafe selected archive member")
            raw = archive.extractfile(member).read(65537)
            entry = entries[relative]
            if entry["mode"] != "100644" or len(raw) != entry["size"] or hashlib.sha1(f"blob {len(raw)}\0".encode() + raw).hexdigest() != entry["sha"]:
                raise ValueError("Selected source Git blob mismatch")
            target = source_path(relative)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(raw)
            found.add(relative)
    if found != set(paths): raise ValueError("Not every registered source member exists")
    save(LOCAL / "fetch-log.json", {"requests": requests, "robots": robot_review, "intervalSeconds": interval, "maximumArchiveBytes": 32 * 1024 * 1024, "maximumExpandedBytes": 80 * 1024 * 1024, "maximumEntries": 5000, "maximumSvgBytes": 65536, "rawCandidateLimit": RAW_CANDIDATE_BOUND, "acceptedLimit": ACCEPTED_BOUND, "verifiedMembers": len(found), "sourceJavaScriptExecuted": False})

def verify_sources():
    pin = json.loads(bounded_read(LOCAL / "pin.json").decode("utf-8"))
    tree_bytes = bounded_read(LOCAL / "tree.json", 4 * 1024 * 1024)
    if digest(tree_bytes) != TREE_INVENTORY_SHA:
        raise ValueError("Complete pinned inventory content integrity mismatch")
    tree = json.loads(tree_bytes.decode("utf-8"))
    if pin["commit"] != COMMIT or pin["tree"] != TREE_SHA or tree["sha"] != TREE_SHA or tree.get("truncated"):
        raise ValueError("Exact complete pinned tree required")
    entries = {x["path"]: x for x in tree["tree"] if x.get("type") == "blob"}
    notice = bounded_read(LOCAL / "license.txt")
    expected = entries["license.txt"]
    if hashlib.sha1(f"blob {len(notice)}\0".encode() + notice).hexdigest() != expected["sha"]:
        raise ValueError("Pinned author notice integrity mismatch")
    text = notice.decode("utf-8")
    if "Creative Commons 3.0 BY" not in text or 'Icons made by {author}' not in text or not all(author["name"] + ", " + author["url"] in text for author in AUTHORS.values()):
        raise ValueError("Official per-author license assignment missing")
    terms = bounded_read(LOCAL / "CC-BY-3.0.txt")
    if digest(terms) != LICENSE_SHA:
        raise ValueError("Complete attribution license integrity mismatch")
    paths = json.loads(bounded_read(LOCAL / "sample-paths.json").decode("utf-8"))
    if not isinstance(paths, list) or len(paths) > RAW_CANDIDATE_BOUND or len(set(paths)) != len(paths):
        raise ValueError("Reviewed raw candidate or accepted bound exceeded")
    artifacts = []
    for relative in paths:
        body = bounded_read(source_path(relative))
        expected = entries[relative]
        if expected["mode"] != "100644" or len(body) != expected["size"] or hashlib.sha1(f"blob {len(body)}\0".encode() + body).hexdigest() != expected["sha"]:
            raise ValueError("Pinned source artifact integrity mismatch: " + relative)
        code = body.decode("utf-8")
        root = svg_root(code)
        if len(list(root.iter())) > 128 or root.get("viewBox") != "0 0 512 512" or any(node.tag.split("}")[-1] not in {"svg", "path"} or any(name not in {"viewBox", "d", "fill"} for name in node.attrib) for node in root.iter()):
            raise ValueError("Source outside the reviewed SVG profile")
        if sum(len(node.get("d", "")) for node in root.iter()) > 30000:
            raise ValueError("Source geometry exceeds bounded profile")
        artifacts.append({"path": relative, "artifactPath": source_path(relative).relative_to(ROOT).as_posix(), "sha256": digest(body), "gitBlobSha1": expected["sha"], "bytes": len(body), "url": f"https://github.com/game-icons/icons/blob/{COMMIT}/{relative}"})
    manifest = {"repo": "game-icons/icons", "commit": COMMIT, "tree": TREE_SHA, "artifacts": artifacts, "licenseTextSha256": LICENSE_SHA, "authorNoticeSha256": digest(notice), "sourceJavaScriptExecuted": False, "rawCandidateBound": RAW_CANDIDATE_BOUND, "acceptedBound": ACCEPTED_BOUND, "preflightCollection": json.loads(bounded_read(LOCAL / "source-inspection.json", 1024 * 1024).decode("utf-8")), "licenseCollection": json.loads(bounded_read(LOCAL / "license-manifest.json").decode("utf-8"))}
    if (LOCAL / "fetch-log.json").exists(): manifest["collection"] = json.loads(bounded_read(LOCAL / "fetch-log.json").decode("utf-8"))
    save(LOCAL / "manifest.json", manifest)
    return manifest, notice.decode("utf-8"), terms.decode("utf-8")

def candidates(manifest, notice, terms):
    result = []
    for artifact in manifest["artifacts"]:
        relative = artifact["path"]
        author = AUTHORS[relative.split("/")[0]]
        name = Path(relative).stem
        title = name.replace("-", " ").title()
        credit = f"Icons made by {author['name']}. {title}. {author['url']}. Source: {artifact['url']}. Licensed under CC BY 3.0: https://creativecommons.org/licenses/by/3.0/. Original geometry and colors unchanged."
        license_text = credit + "\n\n" + notice + "\n\n" + terms
        original = bounded_read(source_path(relative)).decode("utf-8")
        # Metadata-only XML comment. The unmodified original SVG follows it.
        code = "<!--\n" + license_text.replace("--", "- -") + "\n-->\n" + original
        item = {"id": "phase2-game-design-" + relative.split("/")[0] + "-" + name, "title": title, "description": "원본 512x512 단색 형상 구성입니다. 각 실루엣과 내부 음영 공간을 원본 SVG path로 보존합니다. " + credit,
                "category": "shape", "domain": "design", "kind": "code", "access": "public", "language": "svg", "tags": ["svg", "static-design", "shape", "silhouette", "negative-space"], "colors": ["#000000", "#ffffff"], "code": code, "codePath": artifact["artifactPath"], "sourceUrl": artifact["url"], "sourceName": "Game Icons", "sourceAuthor": author["name"], "sourceAuthorUrl": author["url"], "license": "CC BY 3.0", "licenseUrl": "https://creativecommons.org/licenses/by/3.0/", "licenseText": license_text, "verifiedAt": DATE, "verification": "source-and-license-reviewed", "sourceCommit": COMMIT, "upstreamCommit": COMMIT, "upstreamSha256": artifact["sha256"],
                "preview": {"type": "svg", "variant": name, "adapted": False}, "evidence": {"scope": "individual-complete-static-composition", "sourceCommit": COMMIT, "artifactPath": artifact["artifactPath"], "artifactSha256": artifact["sha256"], "originalBytesSha256": artifact["sha256"], "storedCodeSha256": digest(code.encode()), "sourceUrls": [artifact["url"], f"https://github.com/game-icons/icons/blob/{COMMIT}/license.txt", "https://creativecommons.org/licenses/by/3.0/legalcode.txt"], "sourceJavaScriptExecuted": False, "externalResources": False, "staticDesign": True, "fullDOMPreserved": True, "fullGeometryPreserved": True, "attribution": credit, "rights": "Pinned official per-author assignment plus full CC BY 3.0 legal code are retained in each record and exported SVG.", "adaptations": "Only license attribution XML comment inserted; original SVG bytes follow unchanged."}}
        result.append(item)
    return result

def comparison_records():
    dependencies = [(ROOT / "data/upstream/phase2-design/baseline-comparison.json", BASELINE_SHA), (ROOT / "data/phase2-motion-items.json", MOTION_SHA), (ROOT / "data/phase2-design-items.json", DESIGN_SHA)]
    records, metadata = [], []
    for path, expected in dependencies:
        raw = bounded_read(path, 64 * 1024 * 1024)
        if digest(raw) != expected:
            raise ValueError("Immutable comparison input changed: " + str(path))
        current = json.loads(raw.decode("utf-8"))
        records.extend(current)
        metadata.append({"path": path.relative_to(ROOT).as_posix(), "sha256": expected, "records": len(current)})
    return records, metadata

def selection_decisions(items):
    """Every decision binds to the exact reviewed original, including rejections."""
    reviewed = json.loads(bounded_read(LOCAL / "selection-review.json", 1024 * 1024).decode("utf-8"))
    candidate_sha = digest((LOCAL / "candidates.json").read_bytes())
    if reviewed.get("candidateInputSha256") != candidate_sha:
        raise ValueError("Source selection decisions are not bound to current candidates")
    independent_raw = bounded_read(LOCAL / "independent-review.json", 1024 * 1024)
    independent = json.loads(independent_raw.decode("utf-8"))
    if reviewed.get("independentReviewSha256") != digest(independent_raw) or not independent.get("reviewComplete") or independent.get("candidateInput", {}).get("sha256") != candidate_sha:
        raise ValueError("Final source selection requires the current complete independent review")
    independent_rows = {row["id"]: row for row in independent["decisions"]}
    rows = reviewed.get("decisions")
    if not isinstance(rows, list) or len(rows) != len(items):
        raise ValueError("Exactly one source-bound decision is required for every candidate")
    expected = {item["id"]: item for item in items}
    decisions = {}
    for row in rows:
        item = expected.get(row.get("id"))
        if item is None or row["id"] in decisions or row.get("codeSha256") != item["evidence"]["storedCodeSha256"]:
            raise ValueError("Missing, duplicate, extra or stale source selection decision")
        if row.get("decision") not in {"retain", "reject"} or not isinstance(row.get("reason"), str) or not 20 <= len(row["reason"]) <= 3000:
            raise ValueError("Explicit composition review and valid retain/reject decision required")
        peer = independent_rows.get(row["id"])
        if peer is None or peer.get("storedCodeSha256") != row["codeSha256"] or peer.get("decision") != row["decision"] or peer.get("reason") != row["reason"]:
            raise ValueError("Selection and independent source-bound review disagree")
        if row.get("existingConceptDifference") != peer.get("existingConceptDifference"):
            raise ValueError("Name classifier exceptions require matching independent counterpart evidence")
        if row.get("componentConcept") != peer.get("family") or row.get("sourceComposition") != peer.get("sourceComposition"):
            raise ValueError("Construction classification must match the independently reviewed original")
        if row["decision"] == "retain":
            if not isinstance(row.get("componentConcept"), str) or not re.fullmatch(r"[a-z][a-z0-9-]{1,119}", row["componentConcept"]):
                raise ValueError("Retained sources need an actual construction concept, not only the upstream name")
            if not isinstance(row.get("sourceComposition"), str) or not 20 <= len(row["sourceComposition"]) <= 1500:
                raise ValueError("Actual original component arrangement must be described")
        decisions[row["id"]] = row
    return decisions

def rebuild(items):
    records, dependencies = comparison_records()
    decisions = selection_decisions(items)
    comparison = []
    existing_families, existing_family_records, exact, signature, rasters = {}, {}, {}, {}, []
    deferred = []
    for item in records:
        if item.get("language") != "svg" or item.get("kind") != "code": continue
        old_family = icon_family(icon_name(item))
        existing_families.setdefault(old_family, item["id"])
        existing_family_records.setdefault(old_family, item)
        try:
            parsed = _parse(item)
            comparison.append(parsed)
            exact.setdefault(parsed["timing"], item["id"])
        except (ValueError, ET.ParseError, KeyError) as error:
            deferred.append({"id": item["id"], "scope": "structural", "reason": str(error)})
        try:
            root = svg_root(item["code"], allow_animation=True)
            signature.setdefault(geometry_signature(root), item["id"])
            rasters.append((geometry_rasters(root), item["id"]))
        except (ValueError, ET.ParseError, KeyError) as error:
            deferred.append({"id": item["id"], "scope": "contour", "reason": str(error)})
    retained, rejected, name_exceptions = [], [], []
    retained_concepts = {}
    for item in items:
        decision = decisions.get(item["id"])
        if decision["decision"] == "reject":
            rejected.append({"id": item["id"], "reason": decision["reason"]}); continue
        family = icon_family(item["title"])
        if family in existing_families:
            distinct = decision.get("existingConceptDifference")
            old = existing_family_records.get(family)
            if not distinct or old is None or distinct.get("id") != old["id"] or distinct.get("codeSha256") != digest(old["code"].encode()) or not isinstance(distinct.get("reason"), str) or not 80 <= len(distinct["reason"]) <= 3000:
                rejected.append({"id": item["id"], "reason": "existing-concept-family", "matches": existing_families[family]}); continue
            # This source-bound exception corrects a name classifier overreach
            # (e.g. an anatomical heart vs a heart symbol). Every exact/numeric/
            # contour check below still applies, and the actual concept is unique.
            name_exceptions.append({"id": item["id"], "sourceCodeSha256": item["evidence"]["storedCodeSha256"], "namedFamily": family, "reviewedConcept": decision["componentConcept"], "existingId": distinct["id"], "existingCodeSha256": distinct["codeSha256"], "reason": distinct["reason"]})
        if decision["componentConcept"] in retained_concepts:
            rejected.append({"id": item["id"], "reason": "same-reviewed-construction-concept", "matches": retained_concepts[decision["componentConcept"]]}); continue
        parsed = _parse(item)
        root = svg_root(item["code"])
        geometric = geometry_signature(root)
        if parsed["timing"] in exact or geometric in signature:
            rejected.append({"id": item["id"], "reason": "existing-paint-independent-geometry", "matches": exact.get(parsed["timing"], signature.get(geometric))}); continue
        close = next((old for old in comparison if old["skeleton"] == parsed["skeleton"] and (_geometry_pair(parsed, old) or _timing_pair(parsed, old))), None)
        if close:
            rejected.append({"id": item["id"], "reason": "existing-timing-or-small-coordinate-variant", "matches": close["id"]}); continue
        raster = geometry_rasters(root)
        near = next((old_id for old, old_id in rasters if raster_near(raster, old)), None)
        if near:
            rejected.append({"id": item["id"], "reason": "near-contour-under-rotation-or-reflection", "matches": near}); continue
        item["description"] = decision["sourceComposition"] + " " + item["evidence"]["attribution"]
        item["tags"].append(decision["componentConcept"])
        item["evidence"].update(semanticReview=decision["reason"], sourceComposition=decision["sourceComposition"], componentConcept=decision["componentConcept"], semanticReviewCodeSha256=decision["codeSha256"], geometrySha256=geometric, comparison="Frozen canonical/variant/repair plus 510 motion and 3157 design source concepts, paint-independent SVG structure and D4-normalized contours. No claim of universal visual uniqueness.")
        if decision.get("existingConceptDifference"): item["evidence"]["existingConceptDifference"] = decision["existingConceptDifference"]
        retained.append(item)
        existing_families[family] = item["id"]
        existing_family_records[family] = item
        retained_concepts[decision["componentConcept"]] = item["id"]
        exact[parsed["timing"]] = item["id"]
        signature[geometric] = item["id"]
        comparison.append(parsed)
        rasters.append((raster, item["id"]))
    if len(retained) > ACCEPTED_BOUND: raise ValueError("Accepted candidate bound exceeded")
    report = {"candidateCount": len(items), "retainedCount": len(retained), "rejectedCount": len(rejected), "sources": dict(Counter(x["sourceAuthor"] for x in retained)), "category": "design/shape", "dependencies": dependencies, "comparisonRecords": len(records), "structuralSvgRecords": len(comparison) - len(retained), "contourSvgRecords": len(rasters) - len(retained), "deferredComparisons": deferred, "rejections": rejected, "reviewedNameClassifierExceptions": name_exceptions, "sourceJavaScriptExecuted": False, "temporalFramesCompared": False, "methodology": "Manual original-composition semantic gate; one representative per construction concept. Name classifier exceptions bind to the exact existing code and specific component differences; a name alone does not establish visual equivalence. Exact/timing SVG and numeric-coordinate checks plus centerline Jaccard>=0.90 at 64x64 across D4 rotations/reflections. Complex original comparators remain in structural/concept checks; deferred contour list retained.", "limitations": ["Static graphic compositions are design assets, not new motion mechanisms.", "Structural/contour/concept review is not proof of universal perceptual uniqueness."]}
    report["provenance"] = {"repo": "game-icons/icons", "commit": COMMIT, "tree": TREE_SHA, "candidateInputSha256": digest((LOCAL / "candidates.json").read_bytes()), "selectionReviewSha256": digest((LOCAL / "selection-review.json").read_bytes()), "independentReviewSha256": digest((LOCAL / "independent-review.json").read_bytes()), "manifestSha256": digest((LOCAL / "manifest.json").read_bytes()), "fullLegalCodeSha256": LICENSE_SHA, "completeTreeInventorySha256": TREE_INVENTORY_SHA}
    save(OUTPUT, retained)
    report["outputSha256"] = digest(OUTPUT.read_bytes())
    save(LOCAL / "report.json", report)
    print(json.dumps({key: report[key] for key in ("candidateCount", "retainedCount", "rejectedCount", "outputSha256")}))

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bootstrap", action="store_true")
    parser.add_argument("--fetch", action="store_true")
    parser.add_argument("--candidates-only", action="store_true")
    options = parser.parse_args()
    if options.bootstrap: bootstrap()
    if options.fetch: fetch_registered_sources()
    manifest, notice, terms = verify_sources()
    items = candidates(manifest, notice, terms)
    save(LOCAL / "candidates.json", items)
    if options.candidates_only:
        print(json.dumps({"candidates": len(items), "sha256": digest((LOCAL / "candidates.json").read_bytes()), "catalogItemsAdded": 0}))
    else:
        rebuild(items)

if __name__ == "__main__":
    main()
