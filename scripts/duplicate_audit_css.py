"""Offline, conservative CSS duplicate audit; never executes imported code.

The report uses source declarations and preview structure, never source titles.
Canonical identities are intentionally stricter than visual equivalence.
"""

from __future__ import annotations

import argparse
import difflib
import hashlib
import itertools
import json
from pathlib import Path
import re
import tempfile

VERSION = 1
MAX_CODE = 300_000
TOKEN = re.compile(r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|(?:--)?[a-zA-Z_][a-zA-Z0-9_-]*|#[a-zA-Z0-9_-]+|[-+]?(?:\d*\.\d+|\d+)(?:[a-zA-Z]+|%)?|[^\s]')
CLASS = re.compile(r'\.([a-zA-Z_][a-zA-Z0-9_-]*)')
VARIABLE = re.compile(r'var\(\s*(--[a-zA-Z_][a-zA-Z0-9_-]*)')
TIME = re.compile(r'(?<![a-zA-Z0-9_-])[-+]?(?:\d*\.\d+|\d+)(?:ms|s)\b')
EASING = re.compile(r'\b(?:cubic-bezier|steps|linear)\([^()]*\)|\b(?:ease-in-out|ease-in|ease-out|ease|linear|step-start|step-end)\b')
NUMBER = re.compile(r'(?<![a-zA-Z0-9_#-])[-+]?(?:\d*\.\d+|\d+)(?:[a-zA-Z]+|%)?')


def compact(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def digest(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def strip_comments(code):
    """Respect quoted literals, so comment-shaped content is preserved."""
    out, index = [], 0
    while index < len(code):
        character = code[index]
        if character in "\"'":
            start, quote = index, character
            index += 1
            while index < len(code):
                if code[index] == "\\":
                    index += 2
                elif code[index] == quote:
                    index += 1
                    break
                else:
                    index += 1
            out.append(code[start:index])
        elif code.startswith("/*", index):
            end = code.find("*/", index + 2)
            if end < 0:
                raise ValueError("Unterminated CSS comment")
            # CSS comments are removed, rather than creating a new token.
            index = end + 2
        else:
            out.append(character)
            index += 1
    return "".join(out)


def split_top(value, separator):
    parts, start, nesting, quote = [], 0, [], None
    index = 0
    while index < len(value):
        character = value[index]
        if quote:
            if character == "\\":
                index += 2
                continue
            if character == quote:
                quote = None
        elif character in "\"'":
            quote = character
        elif character in "([":
            nesting.append(character)
        elif character in ")]":
            if nesting:
                nesting.pop()
        elif character == separator and not nesting:
            parts.append(value[start:index])
            start = index + 1
        index += 1
    parts.append(value[start:])
    return parts


def parse_declarations(body):
    result = []
    for declaration in split_top(body, ";"):
        if not declaration.strip():
            continue
        parts = split_top(declaration, ":")
        if len(parts) < 2:
            raise ValueError("Unsupported declaration without colon")
        property_name, value = parts[0].strip(), ":".join(parts[1:]).strip()
        if not re.fullmatch(r"(?:--)?[a-zA-Z_-][a-zA-Z0-9_-]*", property_name):
            raise ValueError("Unsupported declaration property")
        result.append((property_name, value))
    return result


def parse_rules(code, depth=0):
    if depth > 12:
        raise ValueError("CSS block depth exceeds audit bound")
    rules, start, index, quote, parens = [], 0, 0, None, 0
    while index < len(code):
        character = code[index]
        if quote:
            if character == "\\":
                index += 2
                continue
            if character == quote:
                quote = None
        elif character in "\"'":
            quote = character
        elif character in "([":
            parens += 1
        elif character in ")]":
            parens -= 1
        elif character == ";" and parens == 0:
            prelude = code[start:index].strip()
            if prelude:
                rules.append({"header": prelude, "statement": True})
            start = index + 1
        elif character == "{" and parens == 0:
            prelude = code[start:index].strip()
            opening, level, inner_quote = index + 1, 1, None
            index += 1
            while index < len(code) and level:
                current = code[index]
                if inner_quote:
                    if current == "\\":
                        index += 2
                        continue
                    if current == inner_quote:
                        inner_quote = None
                elif current in "\"'":
                    inner_quote = current
                elif current == "{":
                    level += 1
                elif current == "}":
                    level -= 1
                index += 1
            if level:
                raise ValueError("Unclosed CSS block")
            body = code[opening:index - 1]
            nested = prelude.startswith("@") and not re.match(r"@(?:font-face|page|property)\b", prelude, re.I)
            rules.append({"header": prelude, "rules": parse_rules(body, depth + 1)} if nested else {"header": prelude, "declarations": parse_declarations(body)})
            start = index
            continue
        elif character == "}" and parens == 0:
            raise ValueError("Unexpected CSS closing brace")
        index += 1
    if code[start:].strip():
        raise ValueError("Unsupported trailing CSS content")
    return rules


def walk_rules(rules):
    for rule in rules:
        yield rule
        yield from walk_rules(rule.get("rules", []))


def value_tokens(value, keyframes=None, timeless=False):
    if timeless:
        value = EASING.sub("<easing>", TIME.sub("<time>", value))
    mapping = keyframes or {}
    tokens = []
    for token in TOKEN.findall(value):
        if token.startswith(("\"", "'")):
            tokens.append(token)
            continue
        if re.fullmatch(r"#[a-fA-F0-9]{3}|#[a-fA-F0-9]{4}|#[a-fA-F0-9]{6}|#[a-fA-F0-9]{8}", token) and not re.search(r"url\s*\(\s*#", value, re.I):
            token = token.lower()
            if len(token) in (4, 5):
                token = "#" + "".join(character * 2 for character in token[1:])
            if len(token) == 9 and token.endswith("ff"):
                token = token[:-2]
        tokens.append(mapping.get(token, token))
    return tuple(tokens)


def selector_value(value, classes):
    # Preserve descendant whitespace and all pseudo-classes/combinators.
    value = CLASS.sub(lambda match: "." + classes.get(match[1], match[1]), value)
    value = re.sub(r"\s+", " ", value.strip())
    return re.sub(r"\s*([>,+~])\s*", r"\1", value)


def effective_dom(item):
    preview, analysis = item.get("preview", {}), item.get("analysis", {})
    if isinstance(preview.get("dom"), dict):
        return {"mode": "source-dom", "dom": preview["dom"]}
    if preview.get("type") == "gradient":
        return {"mode": "gradient", "dom": {"tag": "div", "className": "motion-background"}}
    # The preview host generates different sample geometry for these modes.
    kind = analysis.get("assetType", item.get("category"))
    if kind == "typography" or "text" in analysis.get("components", []):
        mode = "text"
    elif kind in ("transition", "loader", "interaction"):
        mode = kind
    elif preview.get("sampleText"):
        mode = "sample-text"
    else:
        mode = "orb"
    return {"mode": mode, "sampleText": preview.get("sampleText", ""),
            "dom": {"tag": "div", "className": "motion-sample"}}


def dom_nodes(dom):
    yield dom
    for child in dom.get("children", []):
        yield from dom_nodes(child)


def canonical_dom(value, classes, include_text=True):
    if isinstance(value, list):
        return [canonical_dom(entry, classes, include_text) for entry in value]
    if not isinstance(value, dict):
        return value
    result = {}
    for name, entry in sorted(value.items()):
        if not include_text and name in ("text", "placeholder", "sampleText"):
            continue
        if name == "className":
            result[name] = " ".join(classes.get(part, part) for part in entry.split())
        else:
            result[name] = canonical_dom(entry, classes, include_text)
    return result


def frame_offsets(header):
    values = []
    for part in header.split(","):
        part = part.strip().lower()
        if part in ("from", "to"):
            values.append(0.0 if part == "from" else 100.0)
        elif re.fullmatch(r"(?:\d+(?:\.\d+)?|\.\d+)%", part):
            values.append(float(part[:-1]))
        else:
            raise ValueError("Unsupported keyframe offset")
    return tuple(sorted(values))


def record(item):
    code = item.get("code", "")
    if not isinstance(code, str) or len(code) > MAX_CODE or not code.strip():
        raise ValueError("CSS code is absent or exceeds audit size bound")
    clean = strip_comments(code)
    rules = parse_rules(clean)
    dom = effective_dom(item)
    classes = {}
    for node in dom_nodes(dom["dom"]):
        for name in node.get("className", "").split():
            classes.setdefault(name, "c" + str(len(classes)))
    keyframes = {}
    for rule in walk_rules(rules):
        header = rule["header"]
        if "declarations" in rule:
            for name in CLASS.findall(header):
                classes.setdefault(name, "c" + str(len(classes)))
        match = re.match(r"@(?:-[a-z]+-)?keyframes\s+([a-zA-Z_][a-zA-Z0-9_-]*)\s*$", header)
        if match:
            keyframes.setdefault(match[1], "k" + str(len(keyframes)))
    root_values = {}
    used_variables = set()
    for rule in walk_rules(rules):
        for property_name, value in rule.get("declarations", []):
            if property_name.startswith("--"):
                root_values[property_name] = value
            else:
                used_variables.update(VARIABLE.findall(value))
    root_values.update(item.get("preview", {}).get("variables", {}))
    for node in dom_nodes(dom["dom"]):
        root_values.update(node.get("variables", {}))
    pending = list(used_variables)
    while pending:
        name = pending.pop()
        for dependency in VARIABLE.findall(str(root_values.get(name, ""))):
            if dependency not in used_variables:
                used_variables.add(dependency)
                pending.append(dependency)
    timing_values, frame_values, selector_values, controls, wrappers = [], [], [], [], []

    def declaration_values(declarations, timeless=False, motion=False):
        result = []
        plain_present = {name for name, _ in declarations if not name.startswith(("-webkit-", "-moz-", "-o-", "-ms-"))}
        for property_name, value in declarations:
            plain = re.sub(r"^-(?:webkit|moz|o|ms)-", "", property_name)
            if property_name.startswith("--") and property_name not in used_variables:
                continue
            if motion and property_name != plain and plain in plain_present:
                continue
            if motion and plain == "animation-timing-function":
                continue
            is_timing = plain.startswith(("animation", "transition")) or property_name.startswith("--")
            # A keyframe can be named rotateX; never rename the CSS rotateX()
            # transform function merely because it shares that identifier.
            names = keyframes if plain in ("animation", "animation-name") else None
            result.append((plain if motion else property_name,
                           value_tokens(value, names, timeless and is_timing)))
        return tuple(result)

    def canonical_rules(source, timeless=False, inside_frames=False):
        result = []
        for rule in source:
            header = rule["header"]
            match = re.match(r"(@(?:-[a-z]+-)?keyframes)\s+([a-zA-Z_][a-zA-Z0-9_-]*)\s*$", header)
            if match:
                normalized = match[1] + " " + keyframes[match[2]]
                result.append((normalized, canonical_rules(rule.get("rules", []), timeless, True)))
            elif "rules" in rule:
                result.append((value_tokens(header), canonical_rules(rule["rules"], timeless)))
            elif "declarations" in rule:
                if inside_frames:
                    offsets = frame_offsets(header)
                    # Endpoint changes reverse entrance/exit behavior. Retain
                    # 0%/100% anchors while masking interior timing positions.
                    normalized = tuple(value if value in (0.0, 100.0) else "<interior-frame>" for value in offsets) if timeless else offsets
                else:
                    normalized = selector_value(header, classes)
                values = declaration_values(rule["declarations"], timeless)
                if values:
                    result.append((normalized, values))
            else:
                result.append((value_tokens(header), "statement"))
        return tuple(result)

    motion_sequences = []
    for rule in walk_rules(rules):
        if re.match(r"@(?:-[a-z]+-)?keyframes\b", rule["header"]):
            sequence, frames = [], []
            for frame in rule.get("rules", []):
                declarations = declaration_values(frame.get("declarations", []), motion=True)
                offsets = frame_offsets(frame["header"])
                frame_values.append({"keyframe": rule["header"], "offsets": list(offsets),
                                     "declarations": dict(frame.get("declarations", []))})
                for offset in offsets:
                    frames.append((offset, declarations))
            for _, values in sorted(frames, key=lambda frame: frame[0]):
                if not sequence or values != sequence[-1]:
                    sequence.append(values)
            if sequence not in motion_sequences:  # duplicate prefixed definition
                motion_sequences.append(sequence)
        elif "declarations" in rule and not re.fullmatch(r"(?:(?:from|to|\d+(?:\.\d+)?%)\s*,?\s*)+", rule["header"], re.I):
            selector_values.append(selector_value(rule["header"], classes))
            wrappers.append({"selector": rule["header"], "canonicalSelector": selector_value(rule["header"], classes),
                             "declarations": [[name, value] for name, value in rule["declarations"]
                                              if not name.startswith("--") or name in used_variables]})
        for property_name, value in rule.get("declarations", []):
            plain = re.sub(r"^-(?:webkit|moz|o|ms)-", "", property_name)
            if plain.startswith(("animation", "transition")):
                timing_values.append({"selector": rule["header"], "property": property_name, "value": value})
            if plain in ("animation-direction", "animation-iteration-count", "animation-fill-mode", "animation-play-state"):
                controls.append((plain, value_tokens(value)))
            elif plain == "animation":
                # Keep every non-name, non-time, non-easing shorthand token.
                controls.append((plain, value_tokens(value, keyframes, True)))
    exact_dom = canonical_dom(dom, classes)
    shape_dom = canonical_dom(dom, classes, False)
    preview_vars = item.get("preview", {}).get("variables", {})
    actual_variables = {name: value for name, value in preview_vars.items() if name in used_variables}
    exact = (canonical_rules(rules), exact_dom, actual_variables)
    near_vars = {name: value_tokens(value, keyframes, True) for name, value in actual_variables.items()}
    timeless = (canonical_rules(rules, True), exact_dom, near_vars)
    shape_timeless = (canonical_rules(rules, True), shape_dom, near_vars)
    motion = compact(motion_sequences) if motion_sequences else ""
    endpoints = [[tuple(value if value in (0.0, 100.0) else "interior" for value in frame["offsets"])
                  for frame in frame_values if frame["keyframe"] == keyframe]
                 for keyframe in dict.fromkeys(frame["keyframe"] for frame in frame_values)]
    return {"id": item["id"], "sourceName": item.get("sourceName", ""),
            "codeSha256": digest(code), "exact": digest(compact(exact)),
            "timeless": digest(compact(timeless)), "shapeTimeless": digest(compact(shape_timeless)),
            "shapeDom": digest(compact(shape_dom)), "canonical": compact(exact), "endpoints": endpoints,
            "timelessText": compact(shape_timeless), "motion": digest(motion) if motion else "",
            "motionText": motion, "motionSkeleton": NUMBER.sub("<number>", motion) if motion else "",
            "frames": frame_values, "timing": timing_values, "controls": controls, "wrappers": wrappers,
            "selectors": selector_values, "dom": dom, "variables": actual_variables,
            "normalization": {"classes": classes, "keyframes": keyframes}}


def values_difference(left, right):
    fields = ("timing", "frames", "selectors", "dom", "variables", "controls", "wrappers")
    return {name: {left["id"]: left[name], right["id"]: right[name]}
            for name in fields if left[name] != right[name]}


def tiny_numeric_deltas(left, right):
    a, b = NUMBER.findall(left), NUMBER.findall(right)
    if len(a) != len(b):
        return False
    changed = 0
    pattern = re.compile(r"([-+]?(?:\d*\.\d+|\d+))([a-zA-Z]+|%)?")
    for first, second in zip(a, b):
        if first == second:
            continue
        parsed_a, parsed_b = pattern.fullmatch(first), pattern.fullmatch(second)
        if not parsed_a or not parsed_b or parsed_a[2] != parsed_b[2]:
            return False
        va, vb = float(parsed_a[1]), float(parsed_b[1])
        if va * vb < 0 or abs(va - vb) > max(.001, max(abs(va), abs(vb)) * .02):
            return False
        changed += 1
    return 0 < changed <= 10


def groups_for(records, field):
    buckets = {}
    for entry in records:
        key = entry[field]
        if key:
            buckets.setdefault(key, []).append(entry)
    return [bucket for bucket in buckets.values() if len(bucket) > 1]


def audit(items):
    css = sorted((item for item in items if item.get("kind") == "code" and item.get("language") == "css"), key=lambda item: item["id"])
    records, errors = [], []
    for item in css:
        try:
            records.append(record(item))
        except (ValueError, TypeError, KeyError, RecursionError) as exc:
            errors.append({"id": item.get("id"), "error": str(exc), "codeSha256": digest(str(item.get("code", "")))})
    exact_groups, near_groups, families, candidates = [], [], [], []
    exact_pairs, near_pairs = set(), set()
    for bucket in groups_for(records, "exact"):
        ids = [entry["id"] for entry in bucket]
        exact_pairs.update(itertools.combinations(ids, 2))
        exact_groups.append({"ids": ids, "reason": "Same canonical CSS program and preview DOM/used variables; only comments, formatting or consistent names differ.",
                             "confidence": "high-static", "evidence": {"canonicalSha256": bucket[0]["exact"],
                             "normalizations": {entry["id"]: entry["normalization"] for entry in bucket},
                             "codeSha256": {entry["id"]: entry["codeSha256"] for entry in bucket}},
                             "differences": [{"ids": [bucket[0]["id"], entry["id"]], "values": values_difference(bucket[0], entry)} for entry in bucket[1:]]})
    for bucket in groups_for(records, "timeless"):
        identities = {entry["exact"] for entry in bucket}
        if len(identities) < 2:
            continue
        ids = [entry["id"] for entry in bucket]
        near_pairs.update(pair for pair in itertools.combinations(ids, 2) if pair not in exact_pairs)
        near_groups.append({"ids": ids, "reason": "Full CSS/DOM/geometry match after masking only duration, delay, easing and interior frame offsets; endpoint anchors, direction, iteration and triggers remain.",
                            "confidence": "high-static", "evidence": {"timelessSha256": bucket[0]["timeless"],
                            "codeSha256": {entry["id"]: entry["codeSha256"] for entry in bucket}},
                            "differences": [{"ids": [bucket[0]["id"], entry["id"]], "values": values_difference(bucket[0], entry)} for entry in bucket[1:]]})
    deeper = set()
    # Exact geometry sequences with any wrapper variation are families first.
    for bucket in groups_for(records, "motion"):
        ids = [entry["id"] for entry in bucket]
        if all(tuple(pair) in exact_pairs or tuple(pair) in near_pairs for pair in itertools.combinations(ids, 2)):
            continue
        families.append({"ids": ids, "reason": "Identical animated declaration sequence after timing and redundant vendor copies are removed; wrappers/DOM/trigger or playback controls can differ, so this is not a duplicate finding.",
                         "confidence": "high-static-motion-family", "evidence": {"motionSha256": bucket[0]["motion"],
                         "motionDeclarationSequence": json.loads(bucket[0]["motionText"])},
                         "differences": [{"ids": [bucket[0]["id"], entry["id"]], "values": values_difference(bucket[0], entry)} for entry in bucket[1:]]})
        for left, right in itertools.combinations(bucket, 2):
            pair = (left["id"], right["id"])
            if pair in exact_pairs or pair in near_pairs:
                continue
            deeper.add(pair)
            if left["shapeDom"] != right["shapeDom"] or left["controls"] != right["controls"] or left["endpoints"] != right["endpoints"]:
                continue
            similarity = difflib.SequenceMatcher(None, left["timelessText"], right["timelessText"], autojunk=False).ratio()
            if similarity >= .97:
                candidates.append({"ids": list(pair), "reason": "Same animated geometry and DOM shape, with at least 97% full timing-normalized program similarity; sample labels or small wrapper differences require manual review.",
                                   "confidence": "candidate-static", "evidence": {"motionSha256": left["motion"], "programSimilarity": round(similarity, 6)},
                                   "differences": values_difference(left, right)})
    # Numerical skeleton families are checked for tiny geometry deltas only.
    for bucket in groups_for(records, "motionSkeleton"):
        for left, right in itertools.combinations(bucket, 2):
            pair = (left["id"], right["id"])
            if pair in deeper or pair in exact_pairs or pair in near_pairs or left["motion"] == right["motion"]:
                continue
            deeper.add(pair)
            if left["shapeDom"] != right["shapeDom"] or left["controls"] != right["controls"] or left["endpoints"] != right["endpoints"] or not tiny_numeric_deltas(left["motionText"], right["motionText"]):
                continue
            similarity = difflib.SequenceMatcher(None, left["timelessText"], right["timelessText"], autojunk=False).ratio()
            if similarity >= .985:
                candidates.append({"ids": list(pair), "reason": "Same animation declaration/numeric skeleton and DOM shape, at most 10 numeric changes of no more than 2% (or 0.001 at zero), and at least 98.5% full timing-normalized program similarity; actual geometry deltas are preserved in evidence and are not automatically duplicates.",
                                   "confidence": "candidate-static", "evidence": {"programSimilarity": round(similarity, 6), "numericSkeletonSha256": digest(left["motionSkeleton"])},
                                   "differences": values_difference(left, right)})
    count, successful = len(css), len(records)
    universe = count * (count - 1) // 2
    covered = successful * (successful - 1) // 2
    return {"methodology": {"version": VERSION, "execution": "Static offline source analysis only; CSS was not executed or browser rendered.",
            "exact": "Equivalent stored CSS program and preview context only, not necessarily the complete upstream component. Quoted literals and numeric values retained. Hex color case/shorthand/opaque alpha normalized except local URL identifiers. Comments removed; declaration token formatting normalized. Class/keyframe identifiers consistently alpha-renamed in selectors and animation-name references only. Rule/declaration order, descendants, pseudo-class triggers, animation direction/iteration/fill and preview DOM/sample modes retained. Unused custom-property boilerplate excluded from preview-context identities.",
            "near": "Exact full-program identities with only animation/transition time/easing and interior keyframe offsets masked. 0%/100% endpoints and frame block multiplicity retained; no indiscriminate numeric masking for near findings.",
            "families": "Identical animated property/value sequences, sorted by offsets and consecutive equal values coalesced. Redundant vendor declaration copies dropped only when unprefixed declaration exists. Full wrapper difference evidence retained; family membership is not duplication.",
            "candidates": "Motion-signature or motion-numeric-skeleton bucket pairs examined; require equal DOM shape, endpoint anchors and playback controls plus 97% or 98.5% full program similarity. Geometry variants require at most 10 numeric changes, each within 2% of the larger magnitude (or 0.001), with equal unit and no sign reversal. Text similarity alone never establishes a duplicate.",
            "pairCoverage": "All successfully parsed pairs are exhaustively partitioned by exact/timing/motion/numeric-skeleton signature equality. Deep sequence comparisons only within those content-defined buckets. Unrelated signatures are screened out, not visually rendered. Empty motion signatures (static assets) receive exact and timing-normalized full-program comparisons only.",
            "limitations": ["Conservative syntax/program comparison cannot prove perceptual equivalence across arbitrarily different CSS formulas or wrappers.", "No browser/frame screenshots were used. Shared motion families and candidates require review; no entries were removed.", "Custom variables are evaluated as stored source/preview context, not computed browser values. CSS shorthand versus longhand and mathematically equivalent transforms are not fully reduced.", "Sample text is retained for exact/near identities; candidates may ignore text while retaining element/tag/class topology.", "Legacy single-keyframe samples can omit upstream child DOM, pseudo-elements and companion keyframes. Identical stored samples therefore do not establish that their complete original designs are duplicates. SpinKit chase/swing and Three Dots falling source context was specifically inspected in css-review.json."]},
            "coverage": {"itemCount": count, "parsedItemCount": successful, "pairUniverse": universe, "comparedPairs": covered,
                         "unparsedPairCount": universe - covered, "deepComparedPairs": len(deeper),
                         "exactPairCount": len(exact_pairs), "nearPairCountExcludingExact": len(near_pairs),
                         "candidatePairCount": len(candidates), "exactGroupCount": len(exact_groups),
                         "nearGroupCount": len(near_groups), "familyGroupCount": len(families)},
            "items": [{"id": entry["id"], "codeSha256": entry["codeSha256"], "canonicalSha256": entry["exact"],
                       "timelessSha256": entry["timeless"], "motionSha256": entry["motion"],
                       "selectorCount": len(entry["selectors"]), "keyframeBlockCount": len(entry["frames"])} for entry in records],
            "exactGroups": exact_groups, "nearGroups": near_groups, "candidatePairs": candidates,
            "familyGroups": families, "errors": errors}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path, default=Path("data/catalog.json"))
    parser.add_argument("--output", type=Path, default=Path("data/duplicate-audit/css.json"))
    args = parser.parse_args()
    raw = args.catalog.read_bytes()
    catalog = json.loads(raw)
    report = audit(catalog["items"] if isinstance(catalog, dict) else catalog)
    report["catalogSha256"] = hashlib.sha256(raw).hexdigest()
    report["methodology"]["catalogSha256"] = report["catalogSha256"]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="\n", dir=args.output.parent, delete=False) as temporary:
        temporary.write(payload)
        temporary_path = Path(temporary.name)
    temporary_path.replace(args.output)
    print(json.dumps(report["coverage"], sort_keys=True))


if __name__ == "__main__":
    main()
