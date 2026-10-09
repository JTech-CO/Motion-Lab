"""Recheck canonical records without replacing the historical full-catalog audit."""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from motionlab.validation import validate_id  # noqa: E402
from scripts.duplicate_audit_css import audit as audit_css  # noqa: E402
from scripts.duplicate_audit_svg import audit as audit_svg  # noqa: E402
from scripts.duplicate_audit_palette import audit as audit_palette  # noqa: E402
from scripts.duplicate_audit_other import audit_glsl, audit_references  # noqa: E402


MAX_JSON = 128 * 1024 * 1024
DOMAIN_AUDITS = (("css", audit_css), ("svg", audit_svg), ("palette", audit_palette),
                 ("glsl", audit_glsl), ("reference", audit_references))


def read_json(path):
    if path.stat().st_size > MAX_JSON:
        raise ValueError("Recheck input exceeds 128 MiB: " + path.name)
    raw = path.read_bytes()
    if len(raw) > MAX_JSON:
        raise ValueError("Recheck input exceeds 128 MiB: " + path.name)
    return json.loads(raw), raw


def sha(value):
    return hashlib.sha256(value).hexdigest()


def domain_for(item):
    if item.get("kind") == "image":
        return "image"
    if item.get("kind") in ("palette", "reference"):
        return item["kind"]
    if item.get("kind") == "code" and item.get("language") in ("css", "svg", "glsl"):
        return item["language"]
    raise ValueError("Unsupported canonical item domain: " + str(item.get("id")))


def history(root):
    """Bind prior reviews to their catalog, actual report bytes and context hashes."""
    directory = root / "data" / "duplicate-audit"
    decisions, signatures, sources, catalog_hashes = {}, {}, {}, set()
    for name in ("review-decisions.json", "css-review.json"):
        path = directory / name
        if not path.is_file():
            continue
        document, raw = read_json(path)
        fingerprint = document.get("catalogSha256")
        if not isinstance(fingerprint, str) or len(fingerprint) != 64:
            raise ValueError("Invalid historical review fingerprint: " + name)
        catalog_hashes.add(fingerprint)
        sources[name] = sha(raw)
        for decision in document.get("decisions", []):
            ids = decision.get("ids", [])
            if (not isinstance(ids, list) or len(ids) != 2 or len(set(ids)) != 2
                    or set(decision.get("codeSha256", {})) != set(ids)):
                raise ValueError("Invalid historical review membership")
            for identifier in ids:
                validate_id(identifier)
            key = (decision.get("domain"), tuple(sorted(ids)))
            if key in decisions:
                raise ValueError("Repeated historical review decision")
            decisions[key] = {**decision, "reviewFile": name}
        if name == "css-review.json":
            css_path = directory / "css.json"
            if not css_path.is_file():
                raise ValueError("Historical CSS review source report is missing")
            _, css_raw = read_json(css_path)
            if sha(css_raw) != document.get("cssAuditSha256"):
                raise ValueError("Historical CSS review source report changed")
    if len(catalog_hashes) > 1:
        raise ValueError("Historical reviews refer to different catalogs")
    for domain in ("css", "glsl"):
        path = directory / (domain + ".json")
        if not path.is_file():
            continue
        document, raw = read_json(path)
        if catalog_hashes and document.get("catalogSha256") not in catalog_hashes:
            raise ValueError("Historical source-context report has a different catalog")
        sources[path.name] = sha(raw)
        for record in document.get("items", []):
            signatures[(domain, record["id"])] = record.get("canonicalSha256")
    # New reviews remain bound to the complete authoritative input and both
    # source/DOM signatures. They never alter the historical review evidence.
    review_path = root / "data/upstream/phase2-motion/css-review-decisions.json"
    if review_path.is_file():
        document, raw = read_json(review_path)
        input_path = root / "data/phase2-motion-items.json"
        if (not input_path.is_file() or
                document.get("phase2MotionInputSha256") != sha(input_path.read_bytes())):
            raise ValueError("Phase 2 motion review input changed")
        review_file = "upstream/phase2-motion/css-review-decisions.json"
        sources[review_file] = sha(raw)
        for decision in document.get("decisions", []):
            ids = decision.get("ids", [])
            if (decision.get("domain") != "css" or not isinstance(ids, list)
                    or len(ids) != 2 or len(set(ids)) != 2
                    or set(decision.get("codeSha256", {})) != set(ids)
                    or set(decision.get("canonicalSha256", {})) != set(ids)):
                raise ValueError("Invalid Phase 2 review membership")
            for identifier in ids:
                validate_id(identifier)
                signatures[("css", identifier)] = decision["canonicalSha256"][identifier]
            key = ("css", tuple(sorted(ids)))
            if key in decisions:
                raise ValueError("Repeated source review decision")
            decisions[key] = {**decision, "reviewFile": review_file, "reviewScope": "phase2"}
    return decisions, signatures, sources, next(iter(catalog_hashes), None)


def candidate_review(domain, finding, manifests, by_id, decisions, old_signatures):
    decision = decisions.get((domain, tuple(sorted(finding["ids"]))))
    unchanged = decision is not None and all(
        sha((by_id[identifier].get("code") or "").encode("utf-8")) == decision["codeSha256"].get(identifier)
        and manifests.get(identifier, {}).get("canonicalSha256") is not None
        and manifests[identifier]["canonicalSha256"] == old_signatures.get((domain, identifier))
        for identifier in finding["ids"])
    if not unchanged:
        return {"status": "requires-current-source-review"}
    return {"status": "current-code-and-context-review-valid" if decision.get("reviewScope") == "phase2"
            else "previous-code-and-context-review-still-valid",
            "classification": decision["classification"], "basis": decision["basis"],
            "reasonEN": decision.get("reasonEN"), "reviewFile": decision["reviewFile"],
            "codeSha256": decision["codeSha256"],
            "canonicalSha256": {identifier: manifests[identifier]["canonicalSha256"] for identifier in finding["ids"]}}


def recheck(root=ROOT, progress=print):
    root = Path(root).resolve()
    catalog_path = root / "data" / "catalog.json"
    catalog, raw = read_json(catalog_path)
    items = catalog.get("items")
    if not isinstance(items, list):
        raise ValueError("Catalog must contain an item array")
    by_id = {validate_id(item.get("id")): item for item in items}
    if len(by_id) != len(items):
        raise ValueError("Repeated canonical catalog IDs")
    counts = Counter(domain_for(item) for item in items)
    decisions, old_signatures, review_sources, historical_sha = history(root)
    report = {
        "version": 1, "catalogUpdatedAt": catalog.get("updatedAt"), "catalogSha256": sha(raw),
        "scope": "Current canonical top-level entries only; preserved variants are intentionally related and are not counted as separate duplicates.",
        "itemCount": len(items), "storedAssetCount": sum(item["kind"] != "reference" for item in items),
        "browserVerified": False, "sourceExecution": False,
        "historicalReviewCatalogSha256": historical_sha, "historicalReviewFileSha256": review_sources,
        "domains": {},
        "limitations": [
            "Static source structure and numeric color comparisons only; no browser frames, source snippet execution, or proof of perceptual uniqueness.",
            "Reference entries receive identity/metadata checks only; remote motion similarity is unassessed.",
            "Families and candidates are not duplicate findings. Prior candidate judgments apply only when both code and canonical source/preview-context signatures remain unchanged.",
        ],
    }
    domain_audits = DOMAIN_AUDITS
    if counts["image"]:
        from scripts.duplicate_audit_image import audit as audit_images
        domain_audits += (("image", lambda entries: audit_images(entries, root)),)
    for domain, audit in domain_audits:
        progress("Rechecking " + domain + " canonical records...")
        result = audit(items)
        manifests = {record["id"]: record for record in result.get("items", result.get("inspectionManifest", []))}
        expected = {item["id"] for item in items if domain_for(item) == domain}
        errors = result.get("errors", [])
        parsed = set(manifests)
        if result["coverage"]["itemCount"] != counts[domain] or parsed | {error["id"] for error in errors} != expected:
            raise ValueError("Incomplete canonical inspection coverage: " + domain)
        candidates = []
        for finding in result.get("candidatePairs", []):
            candidate = {key: finding[key] for key in ("ids", "reason", "confidence", "evidence") if key in finding}
            candidate["review"] = candidate_review(domain, finding, manifests, by_id, decisions, old_signatures)
            candidates.append(candidate)
        report["domains"][domain] = {
            "coverage": result["coverage"],
            "methodology": {key: value for key, value in result["methodology"].items()
                            if key in ("version", "exact", "near", "metric", "nearThresholds", "nearMatching", "pairCoverage", "candidate", "candidates", "limitations")},
            "exactGroups": result.get("exactGroups", []), "nearGroups": result.get("nearGroups", []),
            "candidatePairs": candidates, "familyGroupCount": len(result.get("familyGroups", [])), "errors": errors,
        }
        progress(f"{domain}: {len(result.get('exactGroups', []))} exact, {len(result.get('nearGroups', []))} near, {len(candidates)} candidates")
    report["summary"] = {
        "exactGroupCount": sum(len(value["exactGroups"]) for value in report["domains"].values()),
        "nearGroupCount": sum(len(value["nearGroups"]) for value in report["domains"].values()),
        "candidatePairCount": sum(len(value["candidatePairs"]) for value in report["domains"].values()),
        "unreviewedCandidatePairCount": sum(candidate["review"]["status"] == "requires-current-source-review"
                                            for value in report["domains"].values() for candidate in value["candidatePairs"]),
        "errorItemCount": sum(len(value["errors"]) for value in report["domains"].values()),
    }
    report["passed"] = not any(report["summary"][key] for key in (
        "exactGroupCount", "nearGroupCount", "unreviewedCandidatePairCount", "errorItemCount"))
    if sha(catalog_path.read_bytes()) != report["catalogSha256"]:
        raise ValueError("Catalog changed during recheck; refusing a mismatched result")
    destination = root / "data" / "consolidation-recheck.json"
    # Only this dedicated output is replaced. Historical audit files remain read-only.
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="\n", dir=destination.parent,
                                         prefix="consolidation-recheck-", suffix=".tmp", delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
        temporary.replace(destination)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT, help="Motion Lab project root")
    arguments = parser.parse_args()
    try:
        report = recheck(arguments.root)
    except (ValueError, TypeError, KeyError, OSError, RecursionError) as error:
        print("Consolidation recheck failed: " + str(error), file=sys.stderr)
        return 2
    print(json.dumps({"passed": report["passed"], "catalogSha256": report["catalogSha256"],
                      "summary": report["summary"]}, ensure_ascii=False))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
