"""Restore three original loader compositions from pinned local CSS only.

This creates an overlay; it never edits source imports or published catalogs.
The original selectors, keyframes, durations, delays and root tokens are kept.
Downloaded code is parsed as text and is never executed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile

ROOT = Path(__file__).resolve().parent.parent
MAX_SOURCE = 1_000_000
SOURCE_PATHS = {
    "spinkit": "data/upstream/spinkit/source.css",
    "three-dots": "data/upstream/three-dots/source.css",
}
SPECS = (
    ("spinkit-sk-chase", "spinkit", "sk-chase", "sk-chase-dot", 6,
     ("spinkit-sk-chase-dot", "spinkit-sk-chase-dot-before")),
    ("spinkit-sk-swing", "spinkit", "sk-swing", "sk-swing-dot", 2,
     ("spinkit-sk-swing-dot",)),
    ("three-dots-dot-falling", "three-dots", "dot-falling", None, 0,
     ("three-dots-dot-falling-before", "three-dots-dot-falling-after")),
)


def sha256(value: bytes | str) -> str:
    return hashlib.sha256(value.encode("utf-8") if isinstance(value, str) else value).hexdigest()


def _read_bounded(path: Path, maximum: int = MAX_SOURCE) -> bytes:
    if not path.is_file() or path.stat().st_size > maximum:
        raise ValueError(f"Missing or oversized repair input: {path.name}")
    value = path.read_bytes()
    if len(value) > maximum or b"\x00" in value:
        raise ValueError(f"Invalid repair input: {path.name}")
    return value


def read_source(root: Path, source_key: str) -> tuple[str, dict, str]:
    """Resolve only two fixed source paths; never accept arbitrary overlay paths."""
    if source_key not in SOURCE_PATHS:
        raise ValueError("Unknown repair source")
    directory = root / Path(SOURCE_PATHS[source_key]).parent
    raw = _read_bounded(directory / "source.css")
    manifest = json.loads(_read_bounded(directory / "manifest.json").decode("utf-8"))
    license_raw = _read_bounded(directory / "LICENSE.txt")
    if sha256(raw) != manifest["sha256"] or sha256(license_raw) != manifest["licenseSha256"]:
        raise ValueError(f"Pinned source or full notice changed: {source_key}")
    return raw.decode("utf-8"), manifest, license_raw.decode("utf-8")


def exact_component(source: str, class_name: str) -> tuple[str, dict]:
    """Keep the full contiguous rule/keyframe section until its next comment."""
    match = re.search(r"(?m)^\." + re.escape(class_name) + r" \{", source)
    if not match:
        raise ValueError(f"Original component selector not found: {class_name}")
    end = source.find("/*", match.end())
    if end < 0:
        end = len(source)
    # Preserve all original whitespace inside the fragment, including its suffix.
    fragment = source[match.start():end]
    return fragment, fragment_evidence(source, match.start(), end)


def fragment_evidence(source: str, start: int, end: int) -> dict:
    return {
        "startUtf8Byte": len(source[:start].encode("utf-8")),
        "endUtf8Byte": len(source[:end].encode("utf-8")),
        "sha256": sha256(source[start:end]),
    }


def source_tokens(source: str) -> tuple[str, dict[str, str], dict]:
    match = re.search(r"(?m)^:root \{[^{}]*\}", source)
    if not match:
        raise ValueError("Original root variables not found")
    variables = dict(re.findall(r"(--sk-(?:size|color)):\s*([^;]+);", match.group()))
    if variables != {"--sk-size": "40px", "--sk-color": "#333"}:
        raise ValueError("Unexpected original SpinKit tokens")
    return match.group(), variables, fragment_evidence(source, match.start(), match.end())


def build_repairs(root: Path = ROOT) -> dict:
    imported = json.loads(_read_bounded(root / "data/imported-items.json", 100_000_000).decode("utf-8"))
    items = {item["id"]: item for item in imported}
    repairs = []
    for identity, source_key, parent_class, child_class, children_count, absorbed in SPECS:
        old = items[identity]
        source, manifest, license_text = read_source(root, source_key)
        if old["upstreamSha256"] != manifest["sha256"] or old["upstreamCommit"] != manifest["commit"]:
            raise ValueError(f"Imported record does not match its pinned source: {identity}")
        component, evidence = exact_component(source, parent_class)
        fragments = [evidence]
        variables = {}
        prefix = ""
        if source_key == "spinkit":
            prefix, variables, root_evidence = source_tokens(source)
            prefix += "\n\n"
            fragments.insert(0, root_evidence)
        dom = {"tag": "div", "className": parent_class}
        if children_count:
            dom["children"] = [{"tag": "div", "className": child_class} for _ in range(children_count)]
        preview = {"type": "css", "variant": parent_class, "adapted": False, "dom": dom}
        if variables:
            preview["variables"] = variables
        keyframes = re.findall(r"@keyframes\s+([\w-]+)", component)
        preview["keyframes"] = keyframes
        comment = (
            f"/* {old['sourceName']} / {manifest['license']}\n{license_text}"
            f"\nSource: {manifest['sourceUrl']}\n"
            "Motion Lab repair: complete original component CSS and composition; "
            "selectors, timing, keyframes and source values are unchanged.\n*/\n"
        )
        description = (
            f"SpinKit의 원본 {parent_class} 구성입니다. {children_count}개 점, "
            "부모·자식 애니메이션, 원본 지연 값과 CSS 변수를 함께 보존했습니다."
            if source_key == "spinkit" else
            "Three Dots의 원본 Dot Falling 구성입니다. 중앙 점과 before/after 점, "
            "원본 1초 주기와 0/0.1/0.2초 지연 값을 함께 보존했습니다. "
            "left -9999px와 원본 box-shadow 오프셋이 서로 상쇄되어 세 점이 나란히 표시됩니다."
        )
        repairs.append({
            "id": identity,
            "expectedCodeSha256": sha256(old["code"]),
            "originalSourcePath": SOURCE_PATHS[source_key],
            "originalSourceSha256": manifest["sha256"],
            "originalLicensePath": f"data/upstream/{source_key}/LICENSE.txt",
            "originalLicenseSha256": manifest["licenseSha256"],
            "replacement": {
                "code": comment + prefix + component,
                "preview": preview,
                "description": description,
                "licenseText": license_text,
                "colors": ["#333"] if source_key == "spinkit" else ["#9880ff"],
            },
            "absorbedIds": list(absorbed),
            "expectedAbsorbedCodeSha256": {item_id: sha256(items[item_id]["code"]) for item_id in absorbed},
            "sourceFragments": fragments,
            "reason": (
                "Single-keyframe extraction omitted original child/pseudo-element geometry and timing. "
                "Restore the complete original component and absorb its separately indexed dependent keyframes."
            ),
            "evidence": {
                "basis": "pinned-source-static-composition-review",
                "sourceDom": dom,
                "keyframes": keyframes,
                "hostAdaptations": [],
                "browserExecutionVerified": False,
                **({"apparentDotXOffsetsPx": [0, -15, 15], "anchorLeftPx": -9999,
                    "sourceShadowXOffsetsPx": [9999, 9984, 10014]}
                   if source_key == "three-dots" else {"originalRootVariables": variables}),
            },
        })
    return {"version": 1, "repairs": repairs}


def verify_overlay(root: Path = ROOT, overlay: dict | None = None) -> dict:
    actual = overlay
    if actual is None:
        actual = json.loads(_read_bounded(root / "data/component-repairs.json").decode("utf-8"))
    expected = build_repairs(root)
    if actual != expected:
        raise ValueError("Component repair overlay differs from exact pinned-source reconstruction")
    return {"repairs": len(expected["repairs"]),
            "absorbedDependentKeyframes": sum(len(item["absorbedIds"]) for item in expected["repairs"]),
            "originalSourceHashesVerified": True, "fullLicenseHashesVerified": True,
            "browserExecutionVerified": False}


def write_overlay(path: Path, value: dict) -> None:
    handle, temporary = tempfile.mkstemp(prefix=".component-repairs-", suffix=".json", dir=path.parent)
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify", action="store_true", help="Verify the saved overlay without rewriting it")
    args = parser.parse_args()
    if not args.verify:
        write_overlay(ROOT / "data/component-repairs.json", build_repairs(ROOT))
    print(json.dumps(verify_overlay(ROOT), ensure_ascii=False))


if __name__ == "__main__":
    main()
