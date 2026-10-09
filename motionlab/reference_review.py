"""Validated reference annotations, kept separate from original assets and rights."""

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
from urllib.parse import urlsplit
import xml.etree.ElementTree as ET

from .analysis_schema import ASSET_TYPES, COMPONENTS, EFFECTS, USE_CASES
from .validation import validate_id

REVIEW_INPUTS = ("reference-review-cha.json", "reference-review-sources.json")
REMOVAL_INPUT = "reference-removals.json"
TARGET_DOMAINS = ("motion", "design", "mixed", "tooling")
RESOURCE_TYPES = ("example", "library", "tool", "design-system", "case-study", "collection", "learning", "portfolio")
HASH = re.compile(r"[a-f0-9]{64}\Z")
MAX_CODE = 100_000


def source_sha256(item):
    original = {key: value for key, value in item.items()
                if key not in ("analysis", "referenceReview")}
    body = json.dumps(original, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")
    return hashlib.sha256(body).hexdigest()


def _text(value, maximum, *, empty=False):
    if (not isinstance(value, str) or len(value) > maximum or "\x00" in value
            or not empty and not value.strip()):
        raise ValueError("Invalid reference annotation text")
    return value


def _enum_list(value, vocabulary):
    if (not isinstance(value, list) or len(value) > len(vocabulary)
            or any(not isinstance(entry, str) or entry not in vocabulary for entry in value)
            or len(set(value)) != len(value)):
        raise ValueError("Invalid reference classification")
    return value


def _url(value):
    parts = urlsplit(_text(value, 4000))
    if parts.scheme not in ("https", "http") or not parts.hostname or parts.username or parts.password:
        raise ValueError("Invalid reference evidence URL")


def _limitations(value):
    if not isinstance(value, list) or not 1 <= len(value) <= 12:
        raise ValueError("Reference previews require explicit limitations")
    for entry in value:
        _text(entry, 1200)


def _artifact(artifact, root=None, cache=None):
    if (not isinstance(artifact, dict) or not {"path", "sha256"} <= set(artifact)
            or set(artifact) - {"path", "sha256", "sourceUrl"}
            or not isinstance(artifact["sha256"], str) or not HASH.fullmatch(artifact["sha256"])):
        raise ValueError("Invalid reference evidence artifact")
    path_text = _text(artifact["path"], 500)
    if (not path_text.startswith("data/upstream/") or "\\" in path_text
            or any(part in ("", ".", "..") for part in path_text.split("/"))):
        raise ValueError("Reference evidence must stay in the upstream directory")
    if "sourceUrl" in artifact:
        _url(artifact["sourceUrl"])
    if root is not None:
        project = Path(root).resolve()
        path = (project / path_text).resolve()
        try:
            path.relative_to((project / "data/upstream").resolve())
        except ValueError as error:
            raise ValueError("Reference evidence escaped the upstream directory") from error
        if not path.is_file() or not 0 < path.stat().st_size <= 16 * 1024 * 1024:
            raise ValueError("Reference evidence is missing or oversized")
        cache = cache if cache is not None else {}
        if path_text not in cache:
            cache[path_text] = hashlib.sha256(path.read_bytes()).hexdigest()
        if cache[path_text] != artifact["sha256"]:
            raise ValueError("Reference evidence digest changed")


def _illustration_dom(value):
    from scripts.analyze import _valid_dom
    if _valid_dom(value) is None:
        raise ValueError("Invalid bounded reference illustration DOM")
    budget = 0
    stack = [value]
    while stack:
        node = stack.pop()
        budget += 1
        children = node.get("children", [])
        classes = node.get("className", "")
        if (budget > 64 or len(children) > 32
                or classes and not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_-]*(?: +[A-Za-z_][A-Za-z0-9_-]*)*", classes)):
            raise ValueError("Reference DOM exceeds the renderer's exact node/class bounds")
        stack.extend(children)


def validate_review(review, *, root=None, item=None, by_id=None, artifact_cache=None):
    allowed = {"id", "sourceSha256", "targetDomain", "resourceType", "assetType", "effects", "components",
               "useCases", "evidence", "preview"}
    if not isinstance(review, dict) or set(review) != allowed:
        raise ValueError("Invalid reference annotation fields")
    validate_id(review["id"])
    if not isinstance(review["sourceSha256"], str) or not HASH.fullmatch(review["sourceSha256"]):
        raise ValueError("Invalid reference source digest")
    if item is not None and (item.get("kind") != "reference" or item["id"] != review["id"]
                            or source_sha256(item) != review["sourceSha256"]):
        raise ValueError("Reference annotation no longer matches its original record")
    if review["targetDomain"] not in TARGET_DOMAINS or review["assetType"] not in ASSET_TYPES:
        raise ValueError("Invalid reference target domain or asset type")
    if review["resourceType"] not in RESOURCE_TYPES:
        raise ValueError("Invalid reference resource type")
    _enum_list(review["effects"], EFFECTS)
    _enum_list(review["components"], COMPONENTS)
    _enum_list(review["useCases"], USE_CASES)
    evidence = review["evidence"]
    required = {"basis", "confidence", "summaryKO", "summaryEN", "signals", "artifacts"}
    if (not isinstance(evidence, dict) or not required <= set(evidence)
            or set(evidence) - required - {"status"}
            or evidence["basis"] not in ("reviewed-source", "metadata")
            or evidence["confidence"] not in ("high", "medium", "low")):
        raise ValueError("Invalid reference evidence")
    if "status" in evidence and evidence["status"] not in ("source-reviewed", "metadata-reviewed", "source-unavailable"):
        raise ValueError("Invalid reference review status")
    if evidence["basis"] == "metadata" and evidence["confidence"] != "low":
        raise ValueError("Metadata-only reference classifications must declare low confidence")
    for key in ("summaryKO", "summaryEN"):
        _text(evidence[key], 3000)
    if not isinstance(evidence["signals"], list) or len(evidence["signals"]) > 48:
        raise ValueError("Too many reference evidence signals")
    for signal in evidence["signals"]:
        _text(signal, 1000)
    artifacts = evidence["artifacts"]
    if not isinstance(artifacts, list) or not 1 <= len(artifacts) <= 8:
        raise ValueError("Reference classification needs bounded local evidence")
    for artifact in artifacts:
        _artifact(artifact, root, artifact_cache)
    preview = review["preview"]
    if not isinstance(preview, dict):
        raise ValueError("Invalid local reference preview")
    _limitations(preview.get("limitations"))
    if preview.get("mode") == "related-asset":
        if set(preview) != {"mode", "assetId", "limitations"}:
            raise ValueError("Invalid related-asset preview fields")
        validate_id(preview["assetId"])
        if by_id is not None:
            related = by_id.get(preview["assetId"])
            if not related or related.get("kind") == "reference" or related.get("referenceReview"):
                raise ValueError("Related preview must resolve directly to a stored asset")
    elif preview.get("mode") == "illustration":
        required_preview = {"mode", "language", "code", "license", "notice", "attribution", "limitations"}
        if not required_preview <= set(preview) or set(preview) - required_preview - {"dom"}:
            raise ValueError("Invalid illustration fields")
        if preview["language"] not in ("css", "svg") or preview["license"] != "CC0-1.0" or preview["attribution"] != "Motion Lab":
            raise ValueError("Illustrations need explicit independent Motion Lab rights")
        _text(preview["notice"], 4000)
        code = _text(preview["code"], MAX_CODE)
        if preview["language"] == "css":
            if re.search(r"(?:url|image-set|expression)\s*\(|@import|</?script\b", code, re.I):
                raise ValueError("Reference CSS cannot load or execute external content")
            if "dom" in preview:
                _illustration_dom(preview["dom"])
        else:
            if "dom" in preview or re.search(r"<!DOCTYPE|<!ENTITY", code, re.I):
                raise ValueError("Invalid reference SVG")
            try:
                svg = ET.fromstring(code)
            except ET.ParseError as error:
                raise ValueError("Malformed reference SVG") from error
            if svg.tag.rsplit("}", 1)[-1] != "svg" or sum(1 for _ in svg.iter()) > 700:
                raise ValueError("Reference SVG root or node budget is invalid")
            for element in svg.iter():
                if element.tag.rsplit("}", 1)[-1] in ("script", "foreignObject", "style", "iframe", "image"):
                    raise ValueError("Active or external reference SVG content is forbidden")
                for key, value in element.attrib.items():
                    key = key.rsplit("}", 1)[-1]
                    if key.lower().startswith("on") or key == "style" or key == "href" and not value.startswith("#"):
                        raise ValueError("Unsafe reference SVG attribute")
                    for _quote, target in re.findall(r"url\(\s*(['\"]?)(.*?)\1\s*\)", value, re.I):
                        if not target.strip().startswith("#"):
                            raise ValueError("Reference SVG resources must be local fragments")
    else:
        raise ValueError("Unsupported reference preview mode")
    return review


def reviewed_analysis(item, base):
    """Classify the reviewed source without pretending the illustration is its code."""
    review = validate_review(item["referenceReview"], item=item)
    result = deepcopy(base)
    result.update(domain=None, assetType=review["assetType"], effects=list(review["effects"]),
                  components=list(review["components"]), useCases=list(review["useCases"]),
                  evidence={key: deepcopy(value) for key, value in review["evidence"].items()
                            if key in ("basis", "confidence", "summaryKO", "summaryEN", "signals")})
    result["evidence"]["signals"].append("reference-source-sha256:" + review["sourceSha256"])
    result["preview"] = {"renderer": "none", "referenceMode": review["preview"]["mode"],
                         "limitations": deepcopy(review["preview"]["limitations"])}
    return result


def apply_reference_removals(items, document, *, root=None):
    """Remove confirmed inaccessible links from every published interface."""
    if document is None:
        return items
    if (not isinstance(document, dict) or set(document) != {"version", "removed"}
            or document["version"] != 1 or not isinstance(document["removed"], list)
            or len(document["removed"]) > 500):
        raise ValueError("Invalid reference removal policy")
    by_id = {item["id"]: item for item in items}
    removed, cache = set(), {}
    for decision in document["removed"]:
        required = {"id", "sourceSha256", "reason", "status", "verifiedAt", "evidence"}
        if not isinstance(decision, dict) or set(decision) != required:
            raise ValueError("Invalid reference removal decision")
        identifier = validate_id(decision["id"])
        item = by_id.get(identifier)
        if (identifier in removed or not item or item["kind"] != "reference"
                or source_sha256(item) != decision["sourceSha256"]):
            raise ValueError("Reference removal no longer matches its original link")
        _text(decision["reason"], 3000)
        if decision["status"] not in ("broken-link", "private", "unavailable"):
            raise ValueError("Invalid inaccessible-reference status")
        if not isinstance(decision["verifiedAt"], str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", decision["verifiedAt"]):
            raise ValueError("Invalid reference removal date")
        if not isinstance(decision["evidence"], list) or not 1 <= len(decision["evidence"]) <= 8:
            raise ValueError("Reference removal requires bounded evidence")
        for artifact in decision["evidence"]:
            _artifact(artifact, root, cache)
        removed.add(identifier)
    return [item for item in items if item["id"] not in removed]


def apply_reference_reviews(items, documents, *, root=None, require_complete=True):
    """Add annotations after consolidation, never replace imported source fields."""
    if not documents:
        return items
    by_id = {item["id"]: item for item in items}
    reviews, cache = {}, {}
    for document in documents:
        if (not isinstance(document, dict) or set(document) != {"version", "reviews"}
                or document["version"] != 1 or not isinstance(document["reviews"], list)
                or len(document["reviews"]) > 500):
            raise ValueError("Invalid reference review input")
        for review in document["reviews"]:
            identifier = review.get("id") if isinstance(review, dict) else None
            if identifier in reviews or identifier not in by_id:
                raise ValueError("Duplicate or unknown reviewed reference")
            validate_review(review, root=root, item=by_id[identifier], by_id=by_id, artifact_cache=cache)
            reviews[identifier] = review
    reference_ids = {item["id"] for item in items if item["kind"] == "reference"}
    if require_complete and set(reviews) != reference_ids:
        raise ValueError("Reference annotations must cover every existing reference exactly once")
    result = []
    for item in items:
        if item["id"] not in reviews:
            result.append(item)
            continue
        updated = {**item, "referenceReview": deepcopy(reviews[item["id"]])}
        updated["analysis"] = reviewed_analysis(updated, item["analysis"])
        result.append(updated)
    return result
