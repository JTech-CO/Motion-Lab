"""Hash-bound reviews of stored JavaScript, never an imported script runner."""

from copy import deepcopy
import hashlib
from pathlib import Path
import re

from .analysis_schema import (ANALYSIS_VERSION, ASSET_TYPES, COMPONENTS, DOMAINS,
                              EFFECTS, TECHNIQUES, USE_CASES)
from .reference_review import validate_review
from .validation import validate_id

HASH = re.compile(r"[a-f0-9]{64}\Z")
REVISION = re.compile(r"[a-f0-9]{40}\Z")
ORIGINAL_PATH = re.compile(r"data/upstream/expansion12-[a-z-]+/[A-Za-z0-9._/-]+\Z")
MAX_SOURCE_CODE = 300_000
MAX_SOURCE_NOTICE = 120_000
MAX_ORIGINAL_BYTES = 16_777_216
UNEXECUTED_LIMITATION = "Original JavaScript is preserved as text and is never executed by Motion Lab."
ILLUSTRATION_LIMITATION = "The independent CSS/SVG illustration explains the reviewed mechanism; it is not the original Three.js rendering."


def _text(value, maximum):
    if (not isinstance(value, str) or not value.strip() or len(value) > maximum
            or any(ord(character) < 32 and character not in "\t\r\n" for character in value)):
        raise ValueError("Invalid stored source review text")
    return value


def _browser_text(value, maximum):
    # JavaScript slices UTF-16 code units. Bound accepted originals to exactly
    # what the source/notice tabs can display and copy without truncation.
    value = _text(value, maximum)
    try:
        units = len(value.encode("utf-16-le")) // 2
    except UnicodeEncodeError as error:
        raise ValueError("Invalid stored source Unicode") from error
    if units > maximum:
        raise ValueError("Stored source exceeds the lossless browser text limit")
    return value


def _enum_list(value, vocabulary):
    if (not isinstance(value, list) or len(value) > len(vocabulary)
            or any(not isinstance(entry, str) or entry not in vocabulary for entry in value)
            or len(set(value)) != len(value)):
        raise ValueError("Invalid stored source classification")


def _text_list(value, maximum_items, maximum_text, *, required=False):
    if (not isinstance(value, list) or len(value) > maximum_items
            or required and not value):
        raise ValueError("Invalid bounded stored source review list")
    for entry in value:
        _text(entry, maximum_text)
    if len(set(value)) != len(value):
        raise ValueError("Repeated stored source review values")


def _receipt(item, code_digest):
    receipt = item.get("collectionEvidence")
    if (not isinstance(receipt, dict) or set(receipt) != {"version", "original", "notice", "storedSha256"}
            or type(receipt["version"]) is not int or receipt["version"] != 1
            or receipt["storedSha256"] != code_digest):
        raise ValueError("Stored source review needs a matching collection receipt")
    for role in ("original", "notice"):
        descriptor = receipt[role]
        if (not isinstance(descriptor, dict) or set(descriptor) != {"path", "sha256"}
                or not isinstance(descriptor["path"], str) or len(descriptor["path"]) > 800
                or not ORIGINAL_PATH.fullmatch(descriptor["path"])
                or any(part in ("", ".", "..") for part in descriptor["path"].split("/"))
                or not isinstance(descriptor["sha256"], str) or not HASH.fullmatch(descriptor["sha256"])):
            raise ValueError("Invalid stored source original path or digest")
    return receipt


def validate_source_review(item, *, root=None):
    """Check annotation, exact source body and independent illustration rights.

    With a workspace root, verify ordinary offline evidence files and the exact
    inclusive line range, including original line endings. No network or eval.
    """
    if (not isinstance(item, dict) or item.get("kind") != "code"
            or item.get("language") != "javascript" or "referenceReview" in item):
        raise ValueError("Stored source reviews require JavaScript code assets")
    validate_id(item.get("id"))
    code = _browser_text(item.get("code"), MAX_SOURCE_CODE)
    _browser_text(item.get("licenseText"), MAX_SOURCE_NOTICE)
    if not isinstance(item.get("preview"), dict) or item["preview"].get("type") != "reference":
        raise ValueError("Original JavaScript cannot request an executable preview")
    review = item.get("sourceReview")
    fields = {"version", "sourceSha256", "revision", "sourceRange", "classification",
              "evidence", "dependencies", "limitations", "preview"}
    if (not isinstance(review, dict) or set(review) != fields
            or type(review["version"]) is not int or review["version"] != 1
            or not isinstance(review["sourceSha256"], str) or not HASH.fullmatch(review["sourceSha256"])
            or not isinstance(review["revision"], str) or not REVISION.fullmatch(review["revision"])):
        raise ValueError("Invalid stored source review fields, hash or revision")
    digest = hashlib.sha256(code.encode("utf-8")).hexdigest()
    if review["sourceSha256"] != digest:
        raise ValueError("Stored source review no longer matches its original code")
    receipt = _receipt(item, digest)
    span = review["sourceRange"]
    if (not isinstance(span, dict) or set(span) != {"startLine", "endLine"}
            or type(span["startLine"]) is not int or type(span["endLine"]) is not int
            or not 1 <= span["startLine"] <= span["endLine"] <= 100_000):
        raise ValueError("Invalid bounded stored source line range")
    classification = review["classification"]
    if (not isinstance(classification, dict)
            or set(classification) != {"domain", "assetType", "effects", "components", "useCases", "techniques"}
            or classification["domain"] not in DOMAINS or classification["assetType"] not in ASSET_TYPES
            or classification["assetType"] == "reference"
            or item.get("domain", classification["domain"]) != classification["domain"]):
        raise ValueError("Invalid stored source classification fields or domain")
    for key, vocabulary in (("effects", EFFECTS), ("components", COMPONENTS),
                            ("useCases", USE_CASES), ("techniques", TECHNIQUES)):
        _enum_list(classification[key], vocabulary)
    evidence = review["evidence"]
    if (not isinstance(evidence, dict)
            or set(evidence) != {"basis", "confidence", "summaryKO", "summaryEN", "signals"}
            or evidence["basis"] != "reviewed-source" or evidence["confidence"] != "high"):
        raise ValueError("Invalid stored source review evidence")
    _text(evidence["summaryKO"], 3000)
    _text(evidence["summaryEN"], 3000)
    _text_list(evidence["signals"], 48, 1000, required=True)
    _text_list(review["dependencies"], 32, 300)
    _text_list(review["limitations"], 12, 1200, required=True)
    preview = review["preview"]
    required_preview = {"mode", "language", "code", "license", "notice", "attribution", "limitations"}
    if (not isinstance(preview, dict) or not required_preview <= set(preview)
            or set(preview) - required_preview - {"dom"} or preview["mode"] != "illustration"):
        raise ValueError("Stored source previews must be independent illustrations")
    # Reuse the established bounded CSS/SVG and CC0 validator without changing
    # the actual asset's kind, original code, upstream rights or classification.
    validate_review({"id": item["id"], "sourceSha256": digest,
                     "targetDomain": classification["domain"], "resourceType": "example",
                     "assetType": classification["assetType"],
                     **{key: classification[key] for key in ("effects", "components", "useCases")},
                     "evidence": {**evidence, "artifacts": [receipt["original"]]},
                     "preview": preview})
    if root is not None:
        from scripts.expansion import verify_collection_evidence
        verify_collection_evidence(item, root)
        original = Path(root).resolve() / receipt["original"]["path"]
        # verify_collection_evidence rejects escapes, symlinks and reparse points.
        with original.open("rb") as stream:
            body = stream.read(MAX_ORIGINAL_BYTES + 1)
        if len(body) > MAX_ORIGINAL_BYTES or hashlib.sha256(body).hexdigest() != receipt["original"]["sha256"]:
            raise ValueError("Stored source original differs from its collection digest")
        try:
            lines = body.decode("utf-8").splitlines(keepends=True)
        except UnicodeDecodeError as error:
            raise ValueError("Stored source original is not UTF-8") from error
        if span["endLine"] > len(lines) or "".join(lines[span["startLine"] - 1:span["endLine"]]) != code:
            raise ValueError("Stored source range does not exactly reproduce its code")
    return review


def reviewed_source_analysis(item):
    """Use reviewed classifications without calling them parsed JavaScript."""
    review = validate_source_review(item)
    classification = review["classification"]
    evidence = deepcopy(review["evidence"])
    evidence["signals"].extend(("stored-source-code-sha256:" + review["sourceSha256"],
                               "upstream-revision:" + review["revision"],
                               "original-javascript-execution:disabled"))
    evidence["signals"].extend("source-dependency:" + value for value in review["dependencies"])
    evidence["signals"].extend("source-limitation:" + value for value in review["limitations"])
    return {"version": ANALYSIS_VERSION, "domain": classification["domain"],
            **{key: deepcopy(classification[key]) for key in
               ("assetType", "effects", "components", "useCases", "techniques")},
            "properties": [], "evidence": evidence,
            "preview": {"renderer": "none", "sourceMode": "illustration",
                        "limitations": [UNEXECUTED_LIMITATION, ILLUSTRATION_LIMITATION,
                                        *deepcopy(review["limitations"]),
                                        *deepcopy(review["preview"]["limitations"])]}}
