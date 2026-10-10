"""Merge licensed source assets without counting repeated bodies or color arrays."""

import hashlib
from pathlib import Path
import re
import stat
import xml.etree.ElementTree as ET

CSS_PARTS = re.compile(r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|/\*[\s\S]*?\*/|\s+')


def asset_fingerprint(item):
    """Conservative identities: preserve color order and CSS identifiers/literals."""
    if item.get("kind") == "reference":
        return None
    language = item.get("language")
    if item.get("kind") == "image":
        image = item.get("image")
        if not isinstance(image, dict) or not re.fullmatch(r"[a-f0-9]{64}", str(image.get("sha256", ""))):
            return None
        return "image", image["sha256"]
    if item.get("kind") == "palette":
        colors = item.get("colors", [])
        if not colors:
            return None
        def hex_color(value):
            value = value.lstrip("#").lower()
            return "".join(character * 2 for character in value) if len(value) == 3 else value
        content = ",".join(hex_color(value) for value in colors)
        language = "palette"
    else:
        content = item.get("code")
        if not isinstance(content, str) or not content.strip():
            return None
        if language == "css":
            def canonical(match):
                value = match.group()
                return " " if value.isspace() or value.startswith("/*") else value
            content = CSS_PARTS.sub(canonical, content).strip()
        elif language == "svg" and not re.search(r"<!DOCTYPE|<!ENTITY", content, re.I):
            try:
                root = ET.fromstring(content)
                for node in root.iter():
                    attributes = sorted(node.attrib.items())
                    node.attrib.clear()
                    node.attrib.update(attributes)
                    # SVG geometry/animation has no meaningful indentation text.
                    if node.text is not None and not node.text.strip():
                        node.text = None
                    if node.tail is not None and not node.tail.strip():
                        node.tail = None
                content = ET.tostring(root, encoding="unicode")
            except (ET.ParseError, ValueError):
                pass
    return language, hashlib.sha256(content.encode("utf-8")).hexdigest()


def verify_collection_evidence(entry, root):
    """Bind each new batch record to bounded, regular offline source files."""
    evidence = entry.get("collectionEvidence")
    expected = {"version", "original", "notice", "storedSha256"}
    if not isinstance(evidence, dict) or set(evidence) != expected or type(evidence["version"]) is not int or evidence["version"] != 1:
        raise ValueError(f"Missing collection receipt: {entry['id']}")
    workspace = Path(root).resolve()
    bodies = {}
    for role in ("original", "notice"):
        descriptor = evidence[role]
        if not isinstance(descriptor, dict) or set(descriptor) != {"path", "sha256"}:
            raise ValueError("Invalid collection file descriptor")
        relative, digest = descriptor["path"], descriptor["sha256"]
        if (not isinstance(relative, str) or len(relative) > 800
                or not re.fullmatch(r"data/upstream/expansion12-[a-z-]+/[A-Za-z0-9._/-]+", relative)
                or any(part in ("", ".", "..") for part in relative.split("/"))
                or not isinstance(digest, str) or not re.fullmatch(r"[a-f0-9]{64}", digest)):
            raise ValueError("Invalid collection path or digest")
        candidate = workspace / relative
        resolved = candidate.resolve()
        if not resolved.is_relative_to(workspace):
            raise ValueError("Collection file escaped the workspace")
        for node in (candidate, *candidate.parents):
            if node == workspace:
                break
            info = node.lstat()
            if node.is_symlink() or getattr(info, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400):
                raise ValueError("Linked collection files are not supported")
        limit = 1_048_576 if role == "notice" else 16_777_216
        if not resolved.is_file() or not 1 <= resolved.stat().st_size <= limit:
            raise ValueError("Collection file is missing or exceeds its byte limit")
        with resolved.open("rb") as stream:
            body = stream.read(limit + 1)
        if len(body) > limit or hashlib.sha256(body).hexdigest() != digest:
            raise ValueError("Collection file digest differs")
        bodies[role] = body
    notice = bodies["notice"].decode("utf-8-sig").replace("\r\n", "\n").strip()
    if notice not in entry["licenseText"].replace("\r\n", "\n"):
        raise ValueError("Collection license notice is missing from the record")
    stored = evidence["storedSha256"]
    if not isinstance(stored, str) or not re.fullmatch(r"[a-f0-9]{64}", stored):
        raise ValueError("Invalid stored body digest")
    actual = entry.get("image", {}).get("sha256") if entry.get("kind") == "image" else hashlib.sha256((entry.get("code") or "").encode("utf-8")).hexdigest()
    if actual != stored:
        raise ValueError("Stored collection body differs from its receipt")
    if entry.get("kind") == "image" and entry["image"]["sourceSha256"] != evidence["original"]["sha256"]:
        raise ValueError("Image origin differs from its collection receipt")
    return True


def merge_expansion(existing, inputs, validate, *, root=None):
    """Existing IDs remain stable; all new records require full license notices."""
    originals = []
    for entry in existing:
        originals.append(entry)
        originals.extend(entry.get("variants", []))
        repaired = entry.get("repair", {}).get("originalRecord")
        if isinstance(repaired, dict):
            originals.append(repaired)
    ids = {entry["id"] for entry in originals}
    known = {}
    for entry in originals:
        fingerprint = asset_fingerprint(entry)
        if fingerprint is not None:
            known.setdefault(fingerprint, entry["id"])
    result, excluded, sources = [], [], {}
    for filename, entries in inputs:
        accepted = 0
        for entry in entries:
            validate(entry)
            if entry["id"] in ids:
                raise ValueError(f"Expansion ID collides: {entry['id']}")
            ids.add(entry["id"])
            if entry["kind"] == "reference":
                raise ValueError("Expansion inputs must contain stored assets, not discovery links")
            if not isinstance(entry.get("licenseText"), str) or not entry["licenseText"].strip():
                raise ValueError(f"Expansion asset lacks its license notice: {entry['id']}")
            if filename.startswith("expansion12-"):
                if root is None:
                    raise ValueError("Collection verification needs a workspace root")
                verify_collection_evidence(entry, root)
            fingerprint = asset_fingerprint(entry)
            if fingerprint is None:
                raise ValueError(f"Expansion asset has no stored body: {entry['id']}")
            if fingerprint in known:
                excluded.append({"id": entry["id"], "sameAs": known[fingerprint],
                                 "input": filename, "reason": "same-stored-asset"})
                continue
            known[fingerprint] = entry["id"]
            result.append(entry)
            accepted += 1
        sources[filename] = {"input": len(entries), "accepted": accepted,
                             "duplicates": len(entries) - accepted}
    return result, {"baseline": len(existing), "added": len(result), "inputs": sources,
                    "duplicatePolicy": "Ordered hex arrays, CSS bodies with comments/whitespace normalized, and canonical SVG XML; existing IDs are retained.",
                    "excluded": excluded}
