"""Deterministic, bounded inspection of local assets. Never fetch or execute code.

This is a structural analysis, not a CSS/GLSL/SVG safety validator or renderer.
Effect labels require observable declarations/operations; names are not evidence.
"""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from motionlab.analysis_schema import (ANALYSIS_VERSION, ASSET_TYPES, COMPONENTS, EFFECTS,
    RENDERERS, TECHNIQUES, USE_CASES)  # noqa: E402
from motionlab.image_assets import validate_image  # noqa: E402
SAFE_PROPERTIES = frozenset(("opacity", "transform", "transform-origin", "translate", "rotate", "scale",
    "filter", "clip-path", "mask", "mask-image", "width", "height", "max-height", "min-height",
    "top", "right", "bottom", "left", "inset", "color", "background", "background-color",
    "background-image", "background-position", "background-size", "background-clip", "border",
    "border-radius", "border-color", "border-width", "box-shadow", "text-shadow", "letter-spacing",
    "line-height", "font-size", "content", "display", "overflow", "perspective", "animation",
    "animation-name", "animation-duration", "animation-delay", "animation-iteration-count",
    "animation-timing-function", "transition", "transition-property", "transition-duration",
    "transition-delay", "fill", "stroke", "stroke-width", "stroke-dasharray", "stroke-dashoffset",
    "cx", "cy", "r", "d", "viewBox", "progress", "uv", "texture"))
MAX_CODE = 1_000_000
NUMBER = r"[-+]?(?:\d*\.\d+|\d+)(?:e[-+]?\d+)?"


def _ordered(values, enum):
    return [key for key in enum if key in values]


def _strip_comments(text, *, glsl=False):
    """Preserve string literals while removing comments (including fake signals)."""
    result, index, quote = [], 0, None
    while index < len(text):
        char = text[index]
        if quote:
            result.append(char)
            if char == "\\" and index + 1 < len(text):
                result.append(text[index + 1]); index += 2; continue
            if char == quote:
                quote = None
        elif char in "\"'":
            quote = char; result.append(char)
        elif text[index:index + 2] == "/*":
            end = text.find("*/", index + 2)
            if end < 0:
                return ""  # Incomplete sources cannot supply reliable evidence.
            result.append(" "); index = end + 2; continue
        elif glsl and text[index:index + 2] == "//":
            end = text.find("\n", index + 2)
            index = len(text) if end < 0 else end
            result.append(" "); continue
        else:
            result.append(char)
        index += 1
    return "".join(result)


def _css_blocks(text):
    """Read bounded balanced blocks, ignoring delimiters in quoted values."""
    stack, blocks, quote, boundary, index = [], [], None, 0, 0
    while index < len(text):
        char = text[index]
        if quote:
            if char == "\\":
                index += 2; continue
            if char == quote:
                quote = None
        elif char in "\"'":
            quote = char
        elif char == "{":
            header = text[boundary:index].strip()
            stack.append((header, index + 1))
            if len(stack) > 12 or len(blocks) > 3000:
                return []
            boundary = index + 1
        elif char == "}":
            if not stack:
                return []
            header, start = stack.pop()
            blocks.append((header, text[start:index], tuple(entry[0] for entry in stack)))
            boundary = index + 1
        elif char == ";":
            boundary = index + 1
        index += 1
    return [] if stack or quote else blocks


def _declarations(body):
    result, parts, start, quote, depth, index = [], [], 0, None, 0, 0
    while index < len(body):
        char = body[index]
        if quote:
            if char == "\\":
                index += 2; continue
            if char == quote:
                quote = None
        elif char in "\"'":
            quote = char
        elif char == "(":
            depth += 1
        elif char == ")":
            depth = max(0, depth - 1)
        elif char == ";" and depth == 0:
            parts.append(body[start:index]); start = index + 1
        index += 1
    parts.append(body[start:])
    for part in parts[:300]:
        match = re.fullmatch(r"\s*([a-zA-Z_-][\w-]{0,79})\s*:\s*(.*?)\s*", part, re.S)
        if match and len(match[2]) <= 4000:
            key = re.sub(r"^-(?:webkit|moz|ms|o)-", "", match[1].lower())
            result.append((key, match[2].strip()))
    return result


def _valid_dom(value, depth=0, budget=None):
    budget = [96] if budget is None else budget
    if not isinstance(value, dict) or depth > 5 or budget[0] < 1:
        return None
    if set(value) - {"tag", "className", "children", "text", "variables", "placeholder"}:
        return None
    tag = value.get("tag", "div")
    class_name = value.get("className", "")
    children = value.get("children", [])
    if tag not in ("div", "span", "p", "strong", "em", "h1", "h2", "button", "input", "label") or not isinstance(class_name, str) or len(class_name) > 180:
        return None
    if class_name and not re.fullmatch(r"[A-Za-z_][\w-]*(?: +[A-Za-z_][\w-]*)*", class_name):
        return None
    if not isinstance(children, list) or len(children) > 48:
        return None
    budget[0] -= 1
    result = {"tag": tag}
    if class_name:
        result["className"] = class_name
    if "text" in value:
        if not isinstance(value["text"], str) or len(value["text"]) > 64:
            return None
        result["text"] = value["text"]
    if "placeholder" in value:
        if not isinstance(value["placeholder"], str) or len(value["placeholder"]) > 80:
            return None
        result["placeholder"] = value["placeholder"]
    if "variables" in value:
        variables = value["variables"]
        if not isinstance(variables, dict) or len(variables) > 32:
            return None
        if any(not isinstance(key, str) or not re.fullmatch(r"--[a-z_][a-z0-9_-]{0,70}", key, re.I)
               or not isinstance(val, str) or len(val) > 240
               or not re.fullmatch(r"[a-z0-9#().,%\s_+-]+", val, re.I)
               or re.search(r"(?:url|expression|image-set|attr)\s*\(", val, re.I)
               for key, val in variables.items()):
            return None
        result["variables"] = dict(variables)
    if children:
        parsed = [_valid_dom(child, depth + 1, budget) for child in children]
        if any(child is None for child in parsed):
            return None
        result["children"] = parsed
    return result


def _content_literal(value):
    value = value.strip()
    if len(value) < 2 or value[0] not in "\"'" or value[-1] != value[0]:
        return ""
    text = value[1:-1]
    def escaped(match):
        number = int(match[1], 16)
        return chr(number) if 0 < number <= 0x10FFFF and not 0xD800 <= number <= 0xDFFF else ""
    text = re.sub(r"\\([0-9a-fA-F]{1,6})\s?", escaped, text)
    text = re.sub(r"\\(.)", r"\1", text)
    return text.strip()


def _has_text(value):
    # Emoji, bullets and empty pseudo elements are graphic shapes, not typography.
    return isinstance(value, str) and any(character.isalpha() or character.isdigit() for character in value)


def _dom_text(value):
    if not isinstance(value, dict):
        return False
    if isinstance(value.get("text"), str) and _has_text(value["text"]):
        return True
    children = value.get("children", [])
    return isinstance(children, list) and any(_dom_text(child) for child in children if isinstance(child, dict))


def _css_analysis(item, code):
    text = _strip_comments(code)
    blocks = _css_blocks(text)
    selectors, keyframes, frame_declarations, styles, animations = [], [], [], [], []
    frame_tracks = {}
    pseudo, interactive = False, False
    for header, body, parents in blocks:
        # Accessibility fallback is not the actual moving composition.
        if any("prefers-reduced-motion" in parent for parent in parents):
            continue
        frame = any(re.match(r"@(?:-webkit-)?keyframes\b", parent, re.I) for parent in parents)
        if re.match(r"@(?:-webkit-)?keyframes\b", header, re.I):
            match = re.search(r"keyframes\s+([\w-]+)", header, re.I)
            if match:
                keyframes.append(match[1][:100])
            continue
        if "{" in body or header.startswith("@"):
            continue
        declarations = _declarations(body)
        if frame:
            if not re.fullmatch(r"(?:from|to|\d+(?:\.\d+)?%)(?:\s*,\s*(?:from|to|\d+(?:\.\d+)?%))*", header, re.I):
                continue
            frame_declarations.extend(declarations)
            frame_parent = next(parent for parent in reversed(parents) if re.match(r"@(?:-webkit-)?keyframes\b", parent, re.I))
            frame_name = re.sub(r"^@(?:-webkit-)?keyframes\s+", "", frame_parent, flags=re.I)
            positions = [0.0 if part.strip().lower() == "from" else 100.0 if part.strip().lower() == "to" else float(part.strip().rstrip("%")) for part in header.split(",")]
            for key, value in declarations:
                track = frame_tracks.setdefault((frame_name, key), {})
                for position in positions:
                    track[position] = value
        else:
            for selector in header.split(",")[:24]:
                selector = selector.strip()
                if selector and len(selector) <= 300:
                    selectors.append(selector)
            styles.extend(declarations)
            pseudo |= bool(re.search(r"::?(?:before|after)\b", header))
            if re.search(r":(?:hover|active|focus|focus-visible)\b", header):
                interactive = True; animations.extend(declarations)
    selectors = list(dict.fromkeys(selectors))[:96]
    all_declarations = styles + frame_declarations
    motion = frame_declarations + animations
    tracks = [(key, [positions[position] for position in sorted(positions)]) for (_, key), positions in frame_tracks.items()]
    sequences = {}
    for key, vals in tracks:
        sequences.setdefault(key, []).extend(vals)
    properties = {key for key, _ in all_declarations if key in SAFE_PROPERTIES}
    # A string such as content:"rotate(90deg)" is text, not a transform.
    values = " ".join(value.lower() for key, value in motion if key in ("transform", "translate", "rotate", "scale"))
    effects, components, techniques, cases, signals = set(), set(), set(), set(), []
    if keyframes:
        techniques.add("keyframes"); signals.append("@keyframes:" + ",".join(dict.fromkeys(keyframes))[:240])
    if any(key.startswith("transition") for key, _ in styles):
        techniques.add("transition")
    if any(key in ("transform", "translate", "rotate", "scale") for key, _ in motion):
        techniques.add("transform")
    if any(key == "opacity" for key, _ in motion):
        effects.add("fade")
    if re.search(r"\btranslate(?:[xyz]|3d)?\s*\(", values) or "translate" in dict(motion):
        effects.add("slide")
    if any(key in ("background-position", "top", "right", "bottom", "left", "inset") for key, _ in motion):
        effects.add("slide")
    if re.search(r"\bscale(?:[xyz]|3d)?\s*\(", values) or "scale" in dict(motion):
        effects.add("scale")
    if re.search(r"\brotate(?:[xyz]|3d)?\s*\(", values) or "rotate" in dict(motion):
        effects.add("rotate")
    if re.search(r"\b(?:rotate[xy]|perspective)\s*\(", values):
        effects.add("flip")
    if any(key in ("clip-path", "mask", "mask-image") for key, _ in all_declarations):
        components.add("mask"); techniques.add("clip-path")
        if any(key in ("clip-path", "mask", "mask-image") for key, _ in motion):
            effects.add("mask")
    if any(key == "filter" for key, _ in all_declarations):
        techniques.add("filter")
    if any(key == "filter" and re.search(r"\bblur\s*\(", value, re.I) for key, value in motion):
        effects.add("blur")
    for key, vals in tracks:
        distinct = list(dict.fromkeys(vals))
        if key in ("opacity", "transform", "scale", "box-shadow", "text-shadow", "filter", "height", "width", "background-size") and len(vals) >= 3 and vals[0] == vals[-1] and len(distinct) > 1:
            effects.add("pulse")
    bezier_values = " ".join(value for key, value in all_declarations if key.startswith("animation") or key.startswith("transition"))
    for match in re.finditer(r"cubic-bezier\s*\(([^)]{1,100})\)", bezier_values, re.I):
        nums = re.findall(NUMBER, match[1])
        if len(nums) == 4 and any(float(nums[index]) < 0 or float(nums[index]) > 1 for index in (1, 3)):
            effects.add("spring"); signals.append("easing:overshoot-control-points")
    for key, track_values in tracks:
        if key != "transform":
            continue
        for operation in ("translateX", "translateY", "rotate", "scale", "scaleX", "scaleY"):
            sequence = [float(match[1]) for value in track_values for match in re.finditer(r"\b" + operation + r"\(\s*(" + NUMBER + r")", value, re.I)]
            signs = [1 if val > 0 else -1 for val in sequence if val != 0]
            reversals = sum(left != right for left, right in zip(signs, signs[1:]))
            if reversals >= 2:
                effects.add("shake"); signals.append("transform:alternating-signs")
                if len(sequence) >= 4 and abs(sequence[-2]) < max(abs(val) for val in sequence):
                    effects.add("spring")
            if operation.startswith("scale") and any(val > 1.05 for val in sequence) and sequence and sequence[-1] <= 1:
                effects.add("spring"); signals.append("scale:overshoot-return")
    content_literals = [_content_literal(value) for key, value in all_declarations if key == "content"]
    content_text = any(_has_text(value) for value in content_literals)
    dynamic_content = any(key == "content" and _has_text(_content_literal(value)) for key, value in motion)
    dynamic_metrics = any(key in ("letter-spacing", "font-size", "line-height") and re.search(NUMBER, value) for key, value in motion)
    dynamic_text = dynamic_content or dynamic_metrics
    if dynamic_text:
        effects.add("text"); components.add("text")
    preview_input = item.get("preview", {})
    if content_text or _has_text(preview_input.get("sampleText", "")) or _dom_text(_valid_dom(preview_input.get("dom"))):
        components.add("text")
    if any(value and not _has_text(value) for value in content_literals):
        components.add("shape"); signals.append("content:decorative-graphic-glyphs")
    text_clipping = any(key == "background-clip" and value == "text" for key, value in styles)
    stepped_text_reveal = "text" in components and re.search(r"steps\s*\(", bezier_values, re.I) and any(key in ("clip-path", "width", "max-width") for key, _ in motion)
    if text_clipping or stepped_text_reveal or any(key == "text-shadow" for key, _ in motion):
        effects.add("text"); components.add("text"); dynamic_text = True
    if any(key == "text-shadow" and value.count("#") >= 2 and "," in value for key, value in motion) and re.search(r"steps\s*\(", bezier_values, re.I):
        effects.add("glitch"); components.add("layer"); signals.append("text-shadow:discrete-separated-color-layers")
    if any(key in ("background", "background-image") and re.search(r"\b(?:repeating-)?(?:linear|radial|conic)-gradient\s*\(", value, re.I) for key, value in all_declarations):
        techniques.add("gradient"); components.add("color")
    if any(key in ("color", "background-color", "border-color") for key, _ in styles):
        components.add("color")
    if any(key in ("width", "height", "border-radius", "border") for key, _ in styles):
        components.add("shape")
    if pseudo:
        techniques.add("pseudo-element"); components.add("layer")
    if any("url(" in value.lower() for _, value in styles):
        components.add("image")
    tiled_background = any(key in ("background", "background-image") and ("repeating-" in value or "radial-gradient" in value) for key, value in styles) and any(key == "background-size" or key == "background" and "/" in value for key, value in styles)
    if any(key.startswith("grid-template") for key, _ in styles) or tiled_background:
        components.add("grid")
    if tiled_background and any(key in ("background-position", "background-size") for key, _ in motion):
        effects.add("pixel"); signals.append("background:animated-repeating-tiles")
    if any(key.startswith("border") or key == "stroke" for key, _ in styles):
        components.add("stroke")
    delay_values = {value for key, value in styles if key == "animation-delay"}
    for key, value in styles:
        if key == "animation":
            for animation in value.split(","):
                times = re.findall(r"(?<![\w.-])[-+]?(?:\d*\.\d+|\d+)(?:ms|s)\b", animation)
                delay_values.add(times[1] if len(times) > 1 else "0s")
    if len(delay_values) > 1 or any("calc(" in value and "--" in value for value in delay_values):
        effects.add("stagger")
    if dynamic_text and re.search(r"steps\s*\(", bezier_values, re.I):
        signals.append("timing:discrete-text-steps")
    if interactive:
        cases.add("feedback"); signals.append("selector:interactive-state")
    looping = any(key.startswith("animation") and re.search(r"\binfinite\b", value) for key, value in styles)
    if item.get("category") == "loader" and keyframes:
        cases.add("status")
    elif looping and item.get("category") in ("background", "gradient"):
        cases.add("ambient")
    elif keyframes:
        cases.add("attention" if looping else "intro")
    if item.get("category") == "transition" and motion:
        cases.add("scene-change")
    opacities = sequences.get("opacity", [])
    if len(opacities) >= 2:
        try:
            if float(opacities[0]) == 0 and float(opacities[-1]) > 0:
                cases.add("intro")
            if float(opacities[0]) > 0 and float(opacities[-1]) == 0:
                cases.add("outro")
        except ValueError:
            pass
    if motion:
        signals.append("animated-properties:" + ",".join(sorted({key for key, _ in motion if key in SAFE_PROPERTIES}))[:240])
    asset_type = "interaction" if interactive else "loader" if item.get("category") == "loader" else "typography" if dynamic_text else item.get("category", "animation")
    if asset_type not in ASSET_TYPES or asset_type in ("reference", "palette"):
        asset_type = "animation"
    dom = _valid_dom(item.get("preview", {}).get("dom"))
    if not dom and selectors and all(selector.startswith(".motion-sample") for selector in selectors):
        dom = {"tag": "div", "className": "motion-sample"}
        sample = item.get("preview", {}).get("sampleText")
        if isinstance(sample, str) and len(sample) <= 64:
            dom["text"] = sample
    if dom and dom.get("children"):
        components.add("layer")
    preview = {"renderer": "css", "selectors": selectors, "keyframes": list(dict.fromkeys(keyframes))[:64],
               "limitations": ["CSS analysis does not grant permission to execute arbitrary selectors or URLs."]}
    if dom:
        preview["dom"] = dom
    else:
        preview["limitations"].append("Original DOM structure is not supplied; composition may require manual reconstruction.")
    return asset_type, effects, components, properties, techniques, cases, signals, preview, bool(blocks)


def _glsl_analysis(item, code):
    text = _strip_comments(code, glsl=True)
    operations = set(re.findall(r"\b([A-Za-z_]\w{0,79})\s*\(", text))
    uniforms = re.findall(r"\buniform\s+(float|int|bool|vec[234]|ivec[234]|mat[234]|sampler2D)\s+([A-Za-z_]\w{0,79})\s*;", text)[:64]
    effects, components, techniques = set(), set(), {"glsl"}
    samplers = operations & {"getFromColor", "getToColor", "texture", "texture2D"}
    if samplers:
        components.update(("image", "layer")); techniques.add("texture-sampling")
    if "mix" in operations and {"getFromColor", "getToColor"} <= operations:
        effects.add("fade")
    if operations & {"step", "smoothstep"} and "progress" in text:
        effects.add("mask"); components.add("mask")
    if operations & {"floor", "ceil"} and re.search(r"\b(?:uv|p|texCoord|coord)\b", text):
        effects.add("pixel"); components.add("grid")
    if {"sin", "cos"} <= operations and ("mat2" in operations or re.search(r"\b(?:rotation|angle)\b", text)):
        effects.add("rotate")
    elif "sin" in operations and re.search(r"\b(?:uv|p|coord|texCoord)\b", text):
        effects.add("wave")
    if operations & {"fract", "random", "rand", "noise", "snoise", "fbm"}:
        techniques.add("procedural-noise")
        if operations & {"noise", "snoise", "fbm"}:
            effects.add("glitch")
    # Classify coordinate transformations by actual sampler arguments, not asset names.
    coordinate_samples = re.findall(r"\bget(?:From|To)Color\s*\(([^;\n]{1,300})", text)
    if any(re.search(r"(?:uv|p|coord|texCoord)\s*-\s*(?:vec2\s*\()?\s*0?\.5", arg) and "*" in arg for arg in coordinate_samples):
        effects.add("scale")
    if any(re.search(r"(?:uv|p|coord|texCoord)\s*[+-]\s*(?:progress|direction|vec2)\b", arg) for arg in coordinate_samples):
        effects.add("slide")
    if "blur" in operations or re.search(r"\b(?:blurSize|blurAmount|blurStrength)\b", text):
        effects.add("blur")
    signals = ["operations:" + ",".join(sorted(operations & {"mix", "step", "smoothstep", "floor", "ceil", "sin", "cos", "fract", "length", "distance", "atan", "pow", "mat2", "getFromColor", "getToColor"}))]
    if uniforms:
        signals.append("uniforms:" + ",".join(name for _, name in uniforms)[:240])
    properties = {"progress"} if re.search(r"\bprogress\b", text) else set()
    if samplers:
        properties.update(("uv", "texture"))
    preview = {"renderer": "glsl", "uniforms": [{"type": kind, "name": name} for kind, name in uniforms],
               "limitations": ["Requires a GLSL transition renderer and two input images; compilation is a separate runtime check."]}
    if item.get("preview", {}).get("scene") == "procedural" and not samplers:
        components.add("color")
        preview["scene"] = "procedural"
        preview["limitations"] = ["The original fragment is adapted to the local time host at source defaults; pointer input and parameter controls are fixed. Compilation and multiple-frame playback are checked separately."]
        return "shader", effects, components, properties, techniques, {"ambient"}, signals, preview, bool(re.search(r"\bvec4\s+transition\s*\(", text))
    return "transition", effects, components, properties, techniques, {"scene-change"}, signals, preview, bool(re.search(r"\bvec4\s+transition\s*\(", text))


def _svg_analysis(item, code):
    if re.search(r"<!\s*(?:DOCTYPE|ENTITY)\b", code, re.I):
        return None
    try:
        root = ET.fromstring(code)
    except (ET.ParseError, ValueError):
        return None
    nodes = list(root.iter())
    if len(nodes) > 3000 or root.tag.rsplit("}", 1)[-1] != "svg":
        return None
    names = Counter(element.tag.rsplit("}", 1)[-1] for element in nodes)
    effects, components, techniques, properties = set(), set(), set(), set()
    animations = []
    for element in nodes:
        tag = element.tag.rsplit("}", 1)[-1]
        if tag in ("animate", "animateTransform", "animateMotion", "set"):
            techniques.add("svg-animation")
            attribute = element.attrib.get("attributeName", "")
            if attribute in SAFE_PROPERTIES:
                properties.add(attribute)
            if attribute == "opacity":
                effects.add("fade")
            if tag == "animateMotion":
                effects.add("slide"); properties.add("transform")
            if tag == "animateTransform":
                transform = element.attrib.get("type", "")
                effects.update({"rotate": {"rotate"}, "translate": {"slide"}, "scale": {"scale"}}.get(transform, set()))
                techniques.add("transform"); properties.add("transform")
            if attribute in ("r", "width", "height"):
                effects.add("scale")
            if attribute in ("cx", "cy", "x", "y"):
                effects.add("slide")
            if attribute in ("stroke-dasharray", "stroke-dashoffset"):
                effects.add("mask"); components.add("stroke")
            animations.append({key: element.attrib[key][:240] for key in ("attributeName", "type", "dur", "repeatCount", "values") if key in element.attrib})
        for key in ("stroke", "stroke-width", "stroke-dasharray", "stroke-dashoffset", "fill", "opacity"):
            if key in element.attrib:
                properties.add(key)
        if element.attrib.get("stroke", "none") != "none":
            components.add("stroke")
    if any(names[key] for key in ("circle", "ellipse", "rect", "path", "polygon", "polyline", "line")):
        components.add("shape")
    if names["g"]:
        components.add("layer")
    if names["text"] or names["tspan"]:
        components.add("text")
    if names["image"]:
        components.add("image")
    if names["mask"] or names["clipPath"]:
        components.add("mask"); techniques.add("clip-path")
    if names["linearGradient"] or names["radialGradient"]:
        components.add("color"); techniques.add("gradient")
    if names["pattern"]:
        components.add("grid")
    if not animations and item.get("domain") == "design":
        techniques.update(("svg-geometry", "static-design"))
    cases = {"status"} if item.get("category") == "loader" else {"attention"} if animations else set()
    if not animations and item.get("domain") == "design":
        cases.add("color-system" if item.get("category") in ("palette", "gradient") else "design-kit")
    preview = {"renderer": "svg", "elements": dict(sorted(names.items())), "animations": animations[:64],
               "limitations": ["SVG requires independent sanitization before inserting it into a document."]}
    signals = ["svg-elements:" + ",".join(f"{key}:{value}" for key, value in sorted(names.items()))[:240]]
    return item.get("category", "animation"), effects, components, properties, techniques, cases, signals, preview, True


def analyze_item(item):
    """Return a new analysis object without altering any imported field or notice."""
    if item.get("sourceReview"):
        from motionlab.source_review import reviewed_source_analysis
        return reviewed_source_analysis(item)
    if item.get("kind") == "reference" and item.get("referenceReview"):
        from motionlab.reference_review import reviewed_analysis
        original = {key: value for key, value in item.items() if key != "referenceReview"}
        return reviewed_analysis(item, analyze_item(original))
    language = item.get("language")
    code = item.get("code")
    colors = [value for value in item.get("colors", []) if isinstance(value, str) and re.fullmatch(r"#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})", value)]
    basis, confidence = "metadata", "low"
    asset_type, effects, components, properties, techniques, cases, signals = "reference", set(), set(), set(), {"reference-link"}, {"reference"}, []
    preview = {"renderer": "none", "limitations": ["A discovery link is not a rendered asset and does not grant reuse rights."]}
    summary_ko = "원문 링크와 수집 메타데이터만 확인했습니다. 실제 효과나 구성요소를 추측하지 않습니다."
    summary_en = "Discovery link and collection metadata only. No effects or components are inferred."
    animated_color_asset = language == "css" and isinstance(code, str) and len(code) <= MAX_CODE and re.search(r"@(?:-webkit-)?keyframes\b", _strip_comments(code), re.I)
    if item.get("kind") == "image" and isinstance(item.get("image"), dict):
        image = item["image"]
        try:
            validate_image(image, verify_file=False)
            valid_image = True
        except ValueError:
            valid_image = False
        if valid_image:
            asset_type, basis, confidence = "material", "image", "high"
            components, properties, techniques, cases = {"image"}, {"texture"}, {"image-texture", "static-design"}, {"design-kit"}
            signals = ["image-sha256:" + image["sha256"], f"image-dimensions:{image['width']}x{image['height']}"]
            preview = {"renderer": "image", "limitations": []}
            summary_ko = "저장된 소재 이미지의 형식, 크기와 해시를 확인했습니다. 정적 디자인 소재입니다."
            summary_en = "Verified the stored material image format, dimensions and hash. This is a static design material."
            if item.get("category") == "shape":
                asset_type = "shape"
                components, properties, techniques = {"image", "shape"}, set(), {"static-design"}
                signals.append("reviewed-image-category:shape")
                summary_ko = "저장된 이미지의 형식, 크기와 해시를 확인하고 검토된 형상 분류를 유지합니다. 정적 래스터 일러스트이며 벡터 기하나 애니메이션을 추측하지 않습니다."
                summary_en = "Verified stored image format, dimensions and hash; retains the reviewed shape classification. Static raster illustration, with no inferred vector geometry or animation."
    elif item.get("kind") != "reference" and (item.get("category") in ("palette", "gradient") or item.get("kind") == "palette") and colors and not animated_color_asset:
        asset_type = "gradient" if item.get("category") == "gradient" or item.get("preview", {}).get("type") == "gradient" else "palette"
        basis, confidence = "color-values", "high"
        components, properties, techniques, cases = {"color"}, {"color"}, {"color-values"}, {"color-system"}
        if asset_type == "gradient":
            techniques.add("gradient")
        signals = ["hex-values:" + ",".join(colors[:32])]
        preview = {"renderer": asset_type, "colors": colors[:32], "limitations": []}
        summary_ko = f"카탈로그의 실제 HEX 색상 {len(colors)}개를 분석했습니다."
        summary_en = f"Inspected {len(colors)} actual HEX color values in the catalog."
    elif item.get("kind") != "reference" and isinstance(code, str) and 0 < len(code) <= MAX_CODE:
        result = _css_analysis(item, code) if language == "css" else _glsl_analysis(item, code) if language == "glsl" else _svg_analysis(item, code) if language == "svg" else None
        if result:
            asset_type, effects, components, properties, techniques, cases, signals, preview, valid = result
            if valid:
                basis, confidence = "code", "high"
                summary_ko = "원본 코드의 선택자·선언·키프레임을 분석했습니다." if language == "css" else "원본 GLSL의 함수 호출·uniform·이미지 샘플링을 분석했습니다." if language == "glsl" else "원본 SVG의 요소·속성·선언된 애니메이션을 분석했습니다."
                summary_en = "Inspected source selectors, declarations and keyframes." if language == "css" else "Inspected source GLSL calls, uniforms and image sampling." if language == "glsl" else "Inspected source SVG elements, attributes and declared animations."
                signals.append("code-sha256:" + hashlib.sha256(code.encode("utf-8")).hexdigest())
                if not effects and techniques & {"keyframes", "transition", "glsl", "svg-animation"}:
                    effects.add("other")
            else:
                asset_type, effects, components, properties, techniques, cases = "reference", set(), set(), set(), {"reference-link"}, {"reference"}
                preview = {"renderer": "none", "limitations": ["Source structure could not be analyzed reliably."]}
    if basis == "metadata" and item.get("verification") == "source-and-license-reviewed":
        basis = "reviewed-source"
    if asset_type not in ASSET_TYPES:
        asset_type = "animation" if basis == "code" else "reference"
    explicit_domain = item.get("domain")
    static_code = language in ("css", "svg") and basis == "code" and not techniques.intersection({"keyframes", "transition", "svg-animation"})
    domain = None if item.get("kind") == "reference" else explicit_domain if explicit_domain in ("motion", "design") else "design" if item.get("kind") in ("palette", "image") or static_code or basis == "color-values" else "motion"
    if domain == "design":
        techniques.add("static-design")
        if static_code:
            cases.add("color-system" if asset_type in ("palette", "gradient") else "design-kit")
    return {"version": ANALYSIS_VERSION, "domain": domain, "assetType": asset_type,
            "effects": _ordered(effects, EFFECTS), "components": _ordered(components, COMPONENTS),
            "properties": sorted(properties & SAFE_PROPERTIES), "techniques": _ordered(techniques, TECHNIQUES),
            "useCases": _ordered(cases, USE_CASES),
            "evidence": {"basis": basis, "confidence": confidence, "summaryKO": summary_ko,
                         "summaryEN": summary_en, "signals": list(dict.fromkeys(signals))[:96]},
            "preview": preview}


def analyze_items(items):
    return [{**item, "analysis": analyze_item(item)} for item in items]


def analysis_terms(analysis):
    """Closed IDs and factual signals for bound FTS search; never SQL fragments."""
    terms = [analysis["assetType"], analysis.get("domain") or "reference"]
    for key in ("effects", "components", "properties", "techniques", "useCases"):
        terms.extend(analysis[key])
    terms.extend((analysis["evidence"]["basis"], analysis["evidence"]["summaryKO"], analysis["evidence"]["summaryEN"]))
    terms.extend(analysis["evidence"]["signals"])
    return " ".join(terms)[:20_000]


def analysis_stats(items):
    return {key: dict(sorted(Counter(value for item in items for value in item["analysis"][key]).items()))
            for key in ("effects", "components", "techniques", "useCases")} | {
                "assetTypes": dict(sorted(Counter(item["analysis"]["assetType"] for item in items).items())),
                "basis": dict(sorted(Counter(item["analysis"]["evidence"]["basis"] for item in items).items()))}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.input.stat().st_size > 100 * 1024 * 1024:
        parser.error("Input exceeds 100 MiB")
    original = json.loads(args.input.read_text(encoding="utf-8-sig"))
    records = original.get("items") if isinstance(original, dict) else original
    if not isinstance(records, list):
        parser.error("Input must be an item array or catalog object")
    analyzed = analyze_items(records)
    if isinstance(original, dict):
        original = {**original, "items": analyzed}
    else:
        original = analyzed
    args.output.write_text(json.dumps(original, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(analysis_stats(analyzed), ensure_ascii=False))
