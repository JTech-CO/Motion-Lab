"""Deterministic, offline structural comparison of every catalog SVG pair.

This is an evidence report, not an automatic deletion policy or a rendered-video
comparison. XML is parsed as bounded data; source scripts and network resources
are never executed or fetched.
"""
from __future__ import annotations

import argparse
import copy
from collections import Counter, defaultdict
from decimal import Decimal, InvalidOperation
from fractions import Fraction
from hashlib import sha256
import itertools
import json
import math
import os
from pathlib import Path
import re
import tempfile
import xml.etree.ElementTree as ET
from urllib.parse import unquote


SVG_NS = "http://www.w3.org/2000/svg"
XLINK_NS = "http://www.w3.org/1999/xlink"
MAX_BYTES = 128 * 1024
MAX_NODES = 700
MAX_DEPTH = 32
MAX_ITEMS = 20_000
ANIMATIONS = frozenset({"animate", "animateTransform", "animateMotion", "set"})
METADATA = frozenset({"title", "desc", "metadata"})
DRAWABLES = frozenset({"path", "rect", "circle", "ellipse", "line", "polyline", "polygon"})
TIMING = frozenset({"begin", "end", "dur", "min", "max", "keyTimes"})
GEOMETRY = frozenset({"x", "y", "x1", "y1", "x2", "y2", "cx", "cy", "r", "rx", "ry", "width", "height", "d", "points"})
SCALAR_NUMBERS = GEOMETRY - {"d", "points"} | frozenset({"stroke-width", "stroke-dashoffset", "opacity", "fill-opacity", "stroke-opacity", "offset", "stdDeviation"})
LIST_NUMBERS = frozenset({"viewBox", "stroke-dasharray", "points", "keyTimes", "keySplines", "values", "from", "to", "by"})
NUMERIC_ANIMATED = GEOMETRY - {"d", "points"} | frozenset({"transform", "stroke-width", "stroke-dashoffset", "opacity", "fill-opacity", "stroke-opacity"})
NUMBER = re.compile(r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?")
PATH_TOKEN = re.compile(r"[MmZzLlHhVvCcSsQqTtAa]|[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?")
CLOCK = re.compile(r"^([-+]?(?:\d+(?:\.\d*)?|\.\d+))(ms|s)?$")


def _json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _hash(value):
    return sha256(_json(value).encode("utf-8")).hexdigest()


def _local(name):
    if name.startswith("{" + SVG_NS + "}"):
        return name[len(SVG_NS) + 2:]
    if name.startswith("{" + XLINK_NS + "}"):
        return "xlink:" + name[len(XLINK_NS) + 2:]
    return name


def _number(value):
    number = Decimal(value)
    parts = number.as_tuple()
    if not number.is_finite() or number.copy_abs() > Decimal("1e12") or len(parts.digits) > 256 or not isinstance(parts.exponent, int) or abs(parts.exponent) > 256:
        raise ValueError("numeric SVG token out of supported finite bounds")
    if not number:
        return "0"
    return format(number, "f").rstrip("0").rstrip(".") if "." in format(number, "f") else format(number, "f")


def _numeric_list(value):
    tokens = NUMBER.findall(value)
    residue = NUMBER.sub("", value)
    if not tokens or residue.strip(" ,;\t\r\n"):
        return None
    return [list(map(_number, NUMBER.findall(part))) for part in value.split(";")]


def _value(name, value, tag):
    # Lexical numeric normalization preserves commands, units, order and signs.
    value = value.replace("\r\n", "\n").replace("\r", "\n")
    if name == "d":
        tokens = PATH_TOKEN.findall(value)
        if not PATH_TOKEN.sub("", value).strip(" ,\t\r\n"):
            return " ".join(t if len(t) == 1 and t.isalpha() else _number(t) for t in tokens)
    if name in SCALAR_NUMBERS:
        if NUMBER.fullmatch(value.strip()):
            return _number(value.strip())
    if name in LIST_NUMBERS:
        parsed = _numeric_list(value)
        if parsed is not None:
            return ";".join(" ".join(part) for part in parsed)
    if tag in ANIMATIONS and name in {"begin", "dur", "end", "min", "max"}:
        clock = CLOCK.fullmatch(value.strip())
        if clock:
            seconds = Decimal(clock.group(1)) / (1000 if clock.group(2) == "ms" else 1)
            return _number(str(seconds)) + "s"
    return value


def _replace_refs(name, value, id_map):
    for old, new in id_map.items():
        value = re.sub(r"url\(\s*#" + re.escape(old) + r"\s*\)", "url(#" + new + ")", value)
        if name in {"href", "xlink:href"} and value == "#" + old:
            value = "#" + new
        if name in {"begin", "end"}:
            value = re.sub(r"(?<![\w:.-])" + re.escape(old) + r"(?=\.(?:begin|end|repeat(?:\(\d+\))?|click|mouseover|mouseout)(?:\b|[+;-]))", new, value)
    return value


def _trajectory(attrs):
    """Exact rational proof for redundant samples of linear numeric SMIL values."""
    if attrs.get("attributeName") not in NUMERIC_ANIMATED:
        return None
    if attrs.get("calcMode", "linear") != "linear" or "keySplines" in attrs:
        return None
    if attrs.get("type", "") not in {"", "translate", "scale", "rotate", "skewX", "skewY"}:
        return None
    if "values" not in attrs:
        return None
    values = _numeric_list(attrs["values"])
    if values is None or len(values) < 2 or len({len(v) for v in values}) != 1 or not values[0]:
        return None
    if "keyTimes" in attrs:
        times = _numeric_list(attrs["keyTimes"])
        if times is None or len(times) != len(values) or any(len(t) != 1 for t in times):
            return None
        times = [Fraction(t[0]) for t in times]
    else:
        times = [Fraction(i, len(values) - 1) for i in range(len(values))]
    if times[0] != 0 or times[-1] != 1 or any(a >= b for a, b in zip(times, times[1:])):
        return None
    samples = [(time, [Fraction(v) for v in vector]) for time, vector in zip(times, values)]
    reduced = []
    for sample in samples:
        reduced.append(sample)
        while len(reduced) >= 3:
            (ta, va), (tb, vb), (tc, vc) = reduced[-3:]
            if all((vb[i] - va[i]) * (tc - ta) == (vc[i] - va[i]) * (tb - ta) for i in range(len(va))):
                reduced.pop(-2)
            else:
                break
    return [[str(time), [str(v) for v in vector]] for time, vector in reduced]


def _canonical(root, id_map, mode="exact", raw=False):
    def walk(node):
        tag = _local(node.tag)
        # Namespace prefixes are lexical, namespace URIs are semantic. An
        # unqualified XML path is not equated to a path in the SVG namespace.
        stored_tag = tag if node.tag.startswith("{" + SVG_NS + "}") else (node.tag if node.tag.startswith("{") else "unqualified:" + tag)
        if tag in METADATA:
            # Referenced metadata is retained; it may be the target of a use/animation.
            if node.attrib.get("id") not in id_map:
                return None
        attrs = {}
        for key, value in node.attrib.items():
            name = _local(key)
            if name == "id":
                value = id_map.get(value, value)
            else:
                value = _replace_refs(name, value, id_map)
            attrs[name] = value if raw else _value(name, value, tag)
        if mode == "timing" and tag in ANIMATIONS:
            attrs = {k: v for k, v in attrs.items() if k not in TIMING}
        if mode == "exact" and not raw and tag in {"animate", "animateTransform"}:
            trajectory = _trajectory(attrs)
            if trajectory is not None:
                attrs.pop("values", None)
                attrs.pop("keyTimes", None)
                attrs["calcMode"] = "linear"
                attrs["__linearTrajectory"] = trajectory
        text = node.text or ""
        # Whitespace is visual in text elements, but not indentation in shapes/groups.
        if tag not in {"text", "tspan", "textPath"} and not text.strip():
            text = ""
        children = [value for child in node if (value := walk(child)) is not None]
        tail = node.tail or ""
        if not tail.strip():
            tail = ""
        return [stored_tag, dict(sorted(attrs.items())), text, children, tail]
    return walk(root)


def _flatten(tree):
    result = {}
    def walk(node, path):
        result[path + "/tag"] = node[0]
        for key, value in node[1].items():
            result[path + "/@" + key] = value
        if node[2]:
            result[path + "/text"] = node[2]
        if node[4]:
            result[path + "/tail"] = node[4]
        for index, child in enumerate(node[3]):
            walk(child, path + "/" + str(index))
    walk(tree, "svg")
    return result


def _differences(a, b):
    left, right = a["flat"], b["flat"]
    return [{"location": key, "left": left.get(key), "right": right.get(key)}
            for key in sorted(left.keys() | right.keys()) if left.get(key) != right.get(key)]


def _geometry(tree):
    shapes = []
    def walk(node, transforms, context):
        tag, attrs = node[:2]
        transforms = transforms + ([attrs["transform"]] if "transform" in attrs else [])
        context = context + ([tag] if tag in {"mask", "defs", "clipPath", "pattern", "symbol"} else [])
        if tag in DRAWABLES:
            shapes.append([tag, {k: v for k, v in attrs.items() if k in GEOMETRY}, transforms, context])
        for child in node[3]:
            if child[0] not in ANIMATIONS:
                walk(child, transforms, context)
    walk(tree, [], [])
    attrs = tree[1]
    return [dict((k, attrs[k]) for k in ("viewBox", "width", "height", "preserveAspectRatio") if k in attrs),
            sorted(shapes, key=_json)]


def _numeric_geometry(tree):
    skeleton = copy.deepcopy(tree)
    vector = []
    def walk(node, is_root=False):
        tag, attrs = node[:2]
        for key in sorted(attrs):
            if key not in GEOMETRY or is_root:
                continue
            value = attrs[key]
            if not isinstance(value, str):
                continue
            if key == "d":
                # Arc flags are discrete and relative/absolute commands are not conflated.
                if re.search("[Aa]", value):
                    continue
                tokens = PATH_TOKEN.findall(value)
                if PATH_TOKEN.sub("", value).strip(" ,\t\r\n"):
                    continue
                rewritten = []
                for token in tokens:
                    if len(token) == 1 and token.isalpha():
                        rewritten.append(token)
                    else:
                        vector.append(float(Decimal(token)))
                        rewritten.append("#")
                attrs[key] = " ".join(rewritten)
            else:
                parsed = _numeric_list(value)
                if parsed is not None:
                    vector.extend(float(Decimal(token)) for part in parsed for token in part)
                    attrs[key] = ";".join(" ".join("#" for token in part) for part in parsed)
        for child in node[3]:
            if child[0] not in ANIMATIONS:
                walk(child)
    walk(skeleton, True)
    return skeleton, vector


def _parse(item):
    code = item.get("code")
    if not isinstance(code, str) or len(code.encode("utf-8")) > MAX_BYTES:
        raise ValueError("SVG code must be UTF-8 text of at most 128 KiB")
    if re.search(r"<!\s*(?:DOCTYPE|ENTITY)\b", code, re.I):
        raise ValueError("DTD/entity declarations are forbidden")
    root = ET.fromstring(code)
    if _local(root.tag) != "svg":
        raise ValueError("root is not an SVG element")
    nodes = list(root.iter())
    if len(nodes) > MAX_NODES:
        raise ValueError("SVG node count exceeds 700")
    def check(node, depth):
        if depth > MAX_DEPTH:
            raise ValueError("SVG nesting exceeds 32")
        tag = _local(node.tag)
        if tag in {"script", "foreignObject", "style", "image", "feImage"}:
            raise ValueError("active/CSS/external-image SVG is outside this structural audit")
        for key, value in node.attrib.items():
            name = _local(key)
            if name.lower().startswith("on"):
                raise ValueError("event-handler SVG is outside this structural audit")
            if name in {"href", "xlink:href"} and value and not value.startswith("#"):
                raise ValueError("external references are outside this structural audit")
        for child in node:
            check(child, depth + 1)
    check(root, 1)
    original_ids = [node.attrib["id"] for node in nodes if "id" in node.attrib]
    duplicate_ids = {ident for ident, count in Counter(original_ids).items() if count > 1}
    # Nonvisual title/desc/metadata can be discarded only when not referenced.
    referenced = set()
    for node in nodes:
        for key, value in node.attrib.items():
            if _local(key) == "id":
                continue
            if duplicate_ids and "\\" in value and _local(key) in {"href", "xlink:href", "style", "fill", "stroke", "mask", "clip-path", "filter"}:
                raise ValueError("escaped references with duplicate IDs are outside safe normalization")
            for ident in set(original_ids):
                # Local URL/href, token-list attributes and SMIL event/syncbase
                # references all make a repeated ID ambiguous. Match whole ID
                # tokens; an ID prefix is not a reference to the shorter ID.
                reference = r"(?:#|(?<![\w:.-]))" + re.escape(ident) + r"(?:\.[a-zA-Z_][\w:-]*|(?=[\s)\"']|$))"
                if any(re.search(reference, spelling) for spelling in (value, unquote(value))):
                    referenced.add(ident)
    if duplicate_ids & referenced:
        raise ValueError("duplicate element IDs make SVG reference normalization ambiguous")
    # Unreferenced repeated labels do not affect SVG geometry or paint. Remove
    # only those labels from the parsed in-memory tree, preserving original code,
    # byte hash, child order and all other attributes. Referenced IDs remain strict.
    for node in nodes:
        if node.attrib.get("id") in duplicate_ids:
            del node.attrib["id"]
    retained_ids = [ident for ident in original_ids if any(n.attrib.get("id") == ident and (_local(n.tag) not in METADATA or ident in referenced) for n in nodes)]
    id_map = {ident: "svg_id_" + str(index) for index, ident in enumerate(retained_ids)}
    exact = _canonical(root, id_map)
    timing = _canonical(root, id_map, "timing")
    ordinary = _canonical(root, id_map, "plain")
    raw = _canonical(root, id_map, "plain", raw=True)
    skeleton, vector = _numeric_geometry(timing)
    view = _numeric_list(root.attrib.get("viewBox", ""))
    unit = min(float(view[0][2]), float(view[0][3])) if view and len(view[0]) == 4 and float(view[0][2]) > 0 and float(view[0][3]) > 0 else 24.0
    animation_inventory = []
    for node in nodes:
        tag = _local(node.tag)
        if tag in ANIMATIONS:
            animation_inventory.append({"tag": tag, "attributeName": node.attrib.get("attributeName"), "type": node.attrib.get("type"), "repeatCount": node.attrib.get("repeatCount", "1")})
    geometry = _geometry(ordinary)
    return {"id": item["id"], "sourceName": item.get("sourceName", "unknown"), "codeSha256": sha256(code.encode("utf-8")).hexdigest(),
            "nodeCount": len(nodes), "tags": dict(sorted(Counter(_local(n.tag) for n in nodes).items())),
            "animations": animation_inventory, "exact": _hash(exact), "timing": _hash(timing),
            "family": _hash(geometry) if geometry[1] else None, "skeleton": _hash(skeleton), "vector": vector,
            "unit": unit, "flat": _flatten(ordinary), "rawFlat": _flatten(raw),
            "originalIds": original_ids, "ignoredUnreferencedDuplicateIds": sorted(duplicate_ids)}


def _timing_pair(a, b):
    differences = _differences(a, b)
    ratios = []
    for diff in differences:
        if diff["location"].endswith("/@dur"):
            left, right = CLOCK.fullmatch(diff["left"] or ""), CLOCK.fullmatch(diff["right"] or "")
            if left and right:
                x, y = abs(float(left.group(1))), abs(float(right.group(1)))
                if x and y:
                    ratios.append(max(x, y) / min(x, y))
    large = bool(ratios and max(ratios) > 2)
    return {"ids": [a["id"], b["id"]],
            "reason": "Identical geometry, paint, initial state, animation targets and value sequences; only SVG timing parameters differ. Event-based begin/end changes can alter restart, overlap and rhythm; the timelines are not identical.",
            "confidence": "medium" if large else "high",
            "evidence": {"timingIndependentSha256": a["timing"], "codeSha256": [a["codeSha256"], b["codeSha256"]],
                         "maxDurationRatio": round(max(ratios), 8) if ratios else None,
                         "largeSpeedDifference": large, "renderedComparison": False,
                         "confidenceScope": "Structural equality after timing removal; not perceptual equality.",
                         "reviewJudgment": "Retain as a timing/rhythm variant; optionally group for exploration. No automatic removal."},
            "differences": differences}


def _geometry_pair(a, b):
    if len(a["vector"]) != len(b["vector"]) or not a["vector"]:
        return None
    deltas = [abs(x - y) for x, y in zip(a["vector"], b["vector"])]
    maximum = max(deltas)
    rms = math.sqrt(sum(x * x for x in deltas) / len(deltas))
    unit = min(a["unit"], b["unit"])
    if maximum == 0 or maximum > unit * 0.015 or rms > unit * 0.006:
        return None
    return {"ids": [a["id"], b["id"]],
            "reason": "Same SVG tree, paint, path commands, static transforms and animation values; geometry coordinates differ by a small bounded amount. Human visual review is required.",
            "confidence": "medium", "differences": _differences(a, b),
            "evidence": {"geometrySkeletonSha256": a["skeleton"], "codeSha256": [a["codeSha256"], b["codeSha256"]],
                         "comparedNumericCoordinates": len(deltas), "maxCoordinateDelta": round(maximum, 8),
                         "rmsCoordinateDelta": round(rms, 8), "viewBoxUnit": unit,
                         "maxRelativeCoordinateDelta": round(maximum / unit, 8),
                         "rmsRelativeCoordinateDelta": round(rms / unit, 8), "renderedComparison": False}}


def audit(items):
    """Return a deterministic JSON-serializable report; do not mutate input records."""
    if not isinstance(items, list) or len(items) > MAX_ITEMS:
        raise ValueError("catalog input must be a list of at most 20,000 records")
    selected = [item for item in items if isinstance(item, dict) and item.get("kind") == "code" and str(item.get("language", "")).lower() == "svg"]
    identifiers = [item.get("id") for item in selected]
    if any(not isinstance(x, str) or not x or len(x) > 240 for x in identifiers) or len(set(identifiers)) != len(identifiers):
        raise ValueError("SVG item IDs must be unique nonempty strings of at most 240 characters")
    records, errors = [], []
    for item in sorted(selected, key=lambda x: x["id"]):
        try:
            records.append(_parse(item))
        except (ValueError, ET.ParseError, InvalidOperation, OverflowError, RecursionError) as exc:
            errors.append({"id": item["id"], "error": str(exc), "codeSha256": sha256(str(item.get("code", "")).encode("utf-8")).hexdigest()})
    exact_buckets, family_buckets = defaultdict(list), defaultdict(list)
    for record in records:
        exact_buckets[record["exact"]].append(record)
        if record["family"] is not None:
            family_buckets[record["family"]].append(record)
    exact_groups = []
    for digest, bucket in sorted(exact_buckets.items()):
        if len(bucket) > 1:
            exact_groups.append({"ids": [x["id"] for x in bucket], "reason": "Same SVG output structure after comments/unreferenced metadata, numeric spelling and ID/reference normalization, including exact linear interpolation proof for redundant numeric samples.",
                                 "confidence": "high", "evidence": {"canonicalSha256": digest, "codeSha256": {x["id"]: x["codeSha256"] for x in bucket}, "renderedComparison": False},
                                 "differences": [{"ids": [bucket[0]["id"], member["id"]], "attributes": _differences(bucket[0], member)} for member in bucket[1:]]})
    near_pairs, candidate_pairs, pair_counts = [], [], Counter()
    # Every valid pair is checked, including pairs across upstream projects.
    for a, b in itertools.combinations(records, 2):
        if a["exact"] == b["exact"]:
            pair_counts["exact"] += 1
        elif a["timing"] == b["timing"]:
            pair = _timing_pair(a, b)
            if pair["evidence"]["largeSpeedDifference"]:
                candidate_pairs.append(pair)
                pair_counts["large-timing-candidate"] += 1
            else:
                near_pairs.append(pair)
                pair_counts["timing-only-near"] += 1
        elif a["skeleton"] == b["skeleton"] and (pair := _geometry_pair(a, b)) is not None:
            candidate_pairs.append(pair)
            pair_counts["small-geometry-candidate"] += 1
        elif a["family"] is not None and a["family"] == b["family"]:
            pair_counts["family-only"] += 1
        else:
            pair_counts["different-under-defined-model"] += 1
    # Pair groups deliberately stay two-member cliques: fuzzy similarities are not
    # made transitive (A~B and B~C does not prove A~C).
    near_groups = sorted(near_pairs, key=lambda x: x["ids"])
    family_groups = []
    for digest, bucket in sorted(family_buckets.items()):
        if len(bucket) < 2:
            continue
        if len({x["exact"] for x in bucket}) == 1:
            continue
        family_groups.append({"ids": [x["id"] for x in bucket],
                              "reason": "Same initial geometric footprint and static transform chains. Paint, layering, one-shot/loop modes, animated properties or endpoints can differ; family membership is not a duplicate verdict.",
                              "confidence": "high", "evidence": {"initialGeometrySha256": digest, "renderedComparison": False,
                                  "animationInventory": {x["id"]: x["animations"] for x in bucket}},
                              "differences": [{"ids": [bucket[0]["id"], member["id"]], "attributes": _differences(bucket[0], member)} for member in bucket[1:]]})
    count = len(records)
    indexed = {record["id"]: record for record in records}
    examples = []
    for left, right, explanation in [
        ("vector-svg-spinners-pulse-3", "vector-svg-spinners-pulse-multiple", "Both use three circles at (12,12), r=0, radius values 0;11 and opacity values 1;0 with 1.2s spline animations. Stagger is 0.4/0.8s versus 0.2/0.4s; the restart depends on the third begin+0.4s versus the third end. This is a rhythm variant of the same effect, not an identical timeline."),
        ("vector-svg-spinners-pulse-rings-3", "vector-svg-spinners-pulse-rings-multiple", "The same three concentric outlined circles retain identical radius/opacity/stroke-width values. Only stagger and syncbase restart times differ; both are same-effect rhythm variants."),
        ("vector-line-md-heart-filled", "vector-line-md-heart-twotone", "The final fill-opacity is 1 versus 0.3, with fill duration 0.4s versus 0.15s. Filled and twotone styles are useful distinct outputs and are family-only."),
        ("vector-line-md-circle-to-confirm-circle-transition", "vector-line-md-confirm-circle-to-circle-transition", "Same circle/check geometry, but stroke-dashoffset values are 14;0 versus 0;14. One reveals the check; the other removes it. Reversed transitions are family-only."),
        ("vector-line-md-download", "vector-line-md-download-loop", "The loop variant adds a repeating motion. A one-shot reveal and ongoing loop are distinct behaviors, not a trivial frame difference."),
        ("vector-line-md-download", "vector-line-md-download-outline", "The original fills the arrow to fill-opacity=1 while the outline variant has no fill-opacity animation and retains fill=none. This style distinction is family-only."),
        ("vector-line-md-arrow-left", "vector-line-md-arrow-right", "Horizontal path direction and arrowhead geometry differ. Opposite directional meanings are not classified as near duplicates."),
        ("vector-line-md-account", "vector-line-md-account-add", "The add variant contains an additional plus-sign component. A semantic addition is not a duplicate of the plain account icon."),
        ("vector-svg-spinners-wifi", "vector-svg-spinners-wifi-fade", "Wifi uses discrete appearance and a 0.001s reset; Wifi Fade uses linear appearance and a 0.1s reset. These preserve the same initial geometry but visibly distinct fade behavior is family-only."),
    ]:
        if left in indexed and right in indexed:
            a, b = indexed[left], indexed[right]
            examples.append({"ids": [left, right], "reviewType": "manual-original-code-inspection", "explanation": explanation,
                             "sameCanonical": a["exact"] == b["exact"], "sameTimingIndependentStructure": a["timing"] == b["timing"],
                             "sameInitialGeometry": a["family"] is not None and a["family"] == b["family"],
                             "differences": _differences(a, b), "renderedComparison": False})
    exact_ids = {ident for group in exact_groups for ident in group["ids"]}
    near_ids = {ident for group in near_groups for ident in group["ids"]}
    candidate_ids = {ident for pair in candidate_pairs for ident in pair["ids"]}
    family_ids = {ident for group in family_groups for ident in group["ids"]}
    return {"methodology": {"name": "svg-structural-pair-audit", "version": 1,
                "exact": "XML namespace/attribute-order/indentation normalization; comments and unreferenced title/desc/metadata removed; only unreferenced duplicate ID labels omitted in memory; referenced duplicate IDs rejected; remaining IDs renamed with local URL/href/SMIL references retained; numeric lexical equivalents normalized; linear numeric values samples reduced only by exact rational collinearity. Child paint order, root dimensions/viewBox, initial state, paint, transforms, timing, repeat/fill/easing and actual animation values otherwise retained.",
                "near": "Same complete XML tree and all non-timing attributes after safe numeric normalization. Only begin/end/dur/min/max/keyTimes may differ; duration ratios over 2 are review candidates, not high-confidence near groups.",
                "candidate": "All valid pairs are compared. Small-coordinate candidates require identical tree/paint/path commands/static transforms/animation values and max delta <=1.5% of the smaller viewBox extent plus RMS <=0.6%. Arc paths keep exact numeric geometry to preserve discrete arc flags. No perceptual or name-based verdict is used.",
                "family": "Exact multiset of initial drawable geometry with root size/viewBox, ancestor transform chains and mask/defs context. A family may intentionally differ in fill/outline, loop behavior, layering or endpoints and is not a redundancy recommendation.",
                "limits": ["No browser rendering or temporal image/video comparison was performed.", "Relative versus absolute path command representations, Bézier versus equivalent arc/circle representations, flattening of inherited paint, and general matrix/geometry equivalence are not proven.", "Families describe initial geometry; animation may subsequently create different geometry or semantics.", "Unsupported active SVG/CSS/external resources are reported as errors rather than silently compared.", "Directional/reversed paths, distinct semantic shapes, repeat counts and filled/outlined variants are never merged by near matching.", "Absence of a match means no match under this defined static model, not proof of perceptual uniqueness."],
                "bounds": {"maxCodeBytes": MAX_BYTES, "maxNodes": MAX_NODES, "maxDepth": MAX_DEPTH},
                "doesNotModifyCatalog": True},
            "coverage": {"itemCount": len(selected), "parsedItems": count, "errorItems": len(errors),
                "pairUniverse": len(selected) * (len(selected) - 1) // 2,
                "comparedPairs": count * (count - 1) // 2, "skippedPairsForParseErrors": len(selected) * (len(selected) - 1) // 2 - count * (count - 1) // 2,
                "pairClassificationCounts": dict(sorted(pair_counts.items())), "sources": dict(sorted(Counter(x["sourceName"] for x in records).items())),
                "elementCounts": dict(sorted(sum((Counter(x["tags"]) for x in records), Counter()).items())),
                "animationElementCounts": dict(sorted(Counter(anim["tag"] for x in records for anim in x["animations"]).items()))},
            "distribution": {"exactGroups": len(exact_groups), "exactMembers": len(exact_ids),
                "nearGroups": len(near_groups), "nearMembers": len(near_ids), "candidatePairs": len(candidate_pairs), "candidateMembers": len(candidate_ids),
                "familyGroups": len(family_groups), "familyMembers": len(family_ids), "itemsOutsideInitialGeometryFamilies": count - len(family_ids),
                "membershipCountsMayOverlap": True},
            "input": {"orderedItemCodeManifestSha256": _hash([[x["id"], x["codeSha256"]] for x in records]),
                      "itemCodeSha256": {x["id"]: x["codeSha256"] for x in records}},
            "inspectionManifest": [{"id": x["id"], "sourceName": x["sourceName"], "codeSha256": x["codeSha256"],
                "canonicalSha256": x["exact"], "timingIndependentSha256": x["timing"],
                "initialGeometrySha256": x["family"], "geometrySkeletonSha256": x["skeleton"],
                "nodeCount": x["nodeCount"], "elementCounts": x["tags"], "animationCount": len(x["animations"]),
                "ignoredUnreferencedDuplicateIds": x["ignoredUnreferencedDuplicateIds"]} for x in records],
            "exactGroups": sorted(exact_groups, key=lambda x: x["ids"]), "nearGroups": near_groups,
            "candidatePairs": sorted(candidate_pairs, key=lambda x: x["ids"]),
            "familyGroups": sorted(family_groups, key=lambda x: x["ids"]), "manualReviewExamples": examples, "errors": errors}


def _write_atomic(path, result):
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = (json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")
    with tempfile.NamedTemporaryFile(prefix=path.name + ".", suffix=".tmp", dir=path.parent, delete=False) as handle:
        temporary = Path(handle.name)
        handle.write(encoded)
        handle.flush()
        os.fsync(handle.fileno())
    try:
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    root = Path(__file__).resolve().parents[1]
    parser.add_argument("--catalog", type=Path, default=root / "data/catalog.json")
    parser.add_argument("--output", type=Path, default=root / "data/duplicate-audit/svg.json")
    args = parser.parse_args()
    if args.catalog.stat().st_size > 256 * 1024 * 1024:
        parser.error("catalog exceeds 256 MiB")
    raw = args.catalog.read_bytes()
    catalog = json.loads(raw.decode("utf-8"))
    result = audit(catalog["items"])
    result["input"]["catalogSha256"] = sha256(raw).hexdigest()
    result["input"]["catalogBytes"] = len(raw)
    _write_atomic(args.output, result)
    print(json.dumps({"coverage": result["coverage"], "exactGroups": len(result["exactGroups"]),
                      "nearGroups": len(result["nearGroups"]), "candidatePairs": len(result["candidatePairs"]),
                      "familyGroups": len(result["familyGroups"]), "errors": len(result["errors"]), "output": str(args.output)}, ensure_ascii=True))


if __name__ == "__main__":
    main()
