"""Merge licensed source assets without counting repeated bodies or color arrays."""

import hashlib
import re
import xml.etree.ElementTree as ET

CSS_PARTS = re.compile(r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|/\*[\s\S]*?\*/|\s+')


def asset_fingerprint(item):
    """Conservative identities: preserve color order and CSS identifiers/literals."""
    if item.get("kind") == "reference":
        return None
    language = item.get("language")
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


def merge_expansion(existing, inputs, validate):
    """Existing IDs remain stable; all new records require full license notices."""
    ids = {entry["id"] for entry in existing}
    known = {}
    for entry in existing:
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
