"""Offline, bounded and exhaustive pair audit of stored palette color arrays.

The color distance is Euclidean OKLab * 100, not CIE DeltaE2000.  Each RGBA
swatch is composited in encoded sRGB over BOTH black and white before conversion.
Order-sensitive matches and order-free color-set matches are reported separately.
"""

import argparse
from collections import Counter, defaultdict
from functools import lru_cache
import hashlib
import json
import math
import os
from pathlib import Path
import re
import tempfile

MAX_COLORS = 32
MEAN_LIMIT = 1.0
MAX_LIMIT = 2.0
HEX = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$")


def canonical_color(value):
    """Canonical RGBA preserves alpha; opaque 6/8-digit notation is equivalent."""
    if not isinstance(value, str) or not HEX.fullmatch(value):
        raise ValueError("Expected a bounded HEX RGB or RGBA color")
    value = value[1:].lower()
    if len(value) in (3, 4):
        value = "".join(ch * 2 for ch in value)
    if len(value) == 6:
        value += "ff"
    return "#" + value


def _linear_srgb(value):
    return value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4


def _oklab(rgb):
    r, g, b = [_linear_srgb(value) for value in rgb]
    l = (0.4122214708*r + 0.5363325363*g + 0.0514459929*b) ** (1/3)
    m = (0.2119034982*r + 0.6806995451*g + 0.1073969566*b) ** (1/3)
    s = (0.0883024619*r + 0.2817188376*g + 0.6299787005*b) ** (1/3)
    return (100*(0.2104542553*l + 0.7936177850*m - 0.0040720468*s),
            100*(1.9779984951*l - 2.4285922050*m + 0.4505937099*s),
            100*(0.0259040371*l + 0.7827717662*m - 0.8086757660*s))


@lru_cache(maxsize=65536)
def color_vector(color):
    rgba = tuple(int(color[pos:pos+2], 16) / 255 for pos in (1, 3, 5, 7))
    alpha = rgba[3]
    black = _oklab(tuple(channel * alpha for channel in rgba[:3]))
    white = _oklab(tuple(channel * alpha + 1-alpha for channel in rgba[:3]))
    return black + white


def _distance_squared(a, b, offset):
    return sum((a[index] - b[index]) ** 2 for index in range(offset, offset+3))


def _distances(a, b):
    return (math.sqrt(_distance_squared(a, b, 0)),
            math.sqrt(_distance_squared(a, b, 3)))


def _metrics(left, right, assignment):
    black, white, worst = [], [], []
    for index, matched in enumerate(assignment):
        b, w = _distances(left[index], right[matched])
        black.append(b)
        white.append(w)
        worst.append(max(b, w))
    return {"metric": "Euclidean OKLab * 100",
            "meanWorstBackground": sum(worst)/len(worst),
            "maxWorstBackground": max(worst),
            "blackMean": sum(black)/len(black),
            "blackMax": max(black),
            "whiteMean": sum(white)/len(white),
            "whiteMax": max(white),
            "matchingRightIndices": list(assignment),
            "perColorWorstBackground": worst}


def _close(metrics):
    return (metrics["meanWorstBackground"] <= MEAN_LIMIT and
            metrics["maxWorstBackground"] <= MAX_LIMIT)


def minimum_assignment(costs):
    """Hungarian algorithm: exact minimum sum, square bounded matrix <= 32."""
    n = len(costs)
    if not 1 <= n <= MAX_COLORS or any(len(row) != n for row in costs):
        raise ValueError("Assignment needs a bounded square matrix")
    u, v, p, way = [0.0]*(n+1), [0.0]*(n+1), [0]*(n+1), [0]*(n+1)
    for i in range(1, n+1):
        p[0], j0 = i, 0
        minv, used = [float("inf")]*(n+1), [False]*(n+1)
        while True:
            used[j0], i0, delta, j1 = True, p[j0], float("inf"), 0
            for j in range(1, n+1):
                if not used[j]:
                    cur = costs[i0-1][j-1] - u[i0] - v[j]
                    if cur < minv[j]:
                        minv[j], way[j] = cur, j0
                    if minv[j] < delta:
                        delta, j1 = minv[j], j
            for j in range(n+1):
                if used[j]:
                    u[p[j]] += delta
                    v[j] -= delta
                else:
                    minv[j] -= delta
            j0 = j1
            if not p[j0]:
                break
        while True:
            j1 = way[j0]
            p[j0] = p[j1]
            j0 = j1
            if not j0:
                break
    result = [0]*n
    for j in range(1, n+1):
        result[p[j]-1] = j-1
    return result


def _sha(value):
    encoded = json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _record(item, colors):
    return {"id": item["id"], "title": item.get("title", ""),
            "sourceName": item.get("sourceName", ""),
            "sourceUrl": item.get("sourceUrl", ""),
            "sourceCommit": item.get("upstreamCommit") or item.get("evidence", {}).get("sourceCommit"),
            "originalColors": item["colors"], "canonicalRGBA": list(colors),
            "orderedColorSha256": _sha(colors),
            "unorderedMultisetSha256": _sha(sorted(colors)),
            "storedCodeSha256": hashlib.sha256(item.get("code", "").encode("utf-8")).hexdigest()}


def _pair(a, b, reason, evidence, confidence, differences):
    return {"ids": [a["id"], b["id"]], "reason": reason,
            "evidence": {**evidence, "palettes": [
                {key: record[key] for key in ("id", "sourceName", "sourceUrl", "originalColors",
                                             "canonicalRGBA", "orderedColorSha256")}
                for record in (a, b)]}, "confidence": confidence, "differences": differences}


def audit(items):
    """Analyze every palette pair; never mutate items or infer removal decisions."""
    inputs = sorted((item for item in items if item.get("kind") == "palette"), key=lambda item: item["id"])
    records, values, vectors, centroids, counters, valid_items, errors = [], [], [], [], [], [], []
    exact_buckets, set_buckets = defaultdict(list), defaultdict(list)
    for item in inputs:
        try:
            raw = item.get("colors")
            if not isinstance(raw, list) or not 2 <= len(raw) <= MAX_COLORS:
                raise ValueError("Palette size must be between 2 and 32")
            colors = tuple(canonical_color(color) for color in raw)
            vector = tuple(color_vector(color) for color in colors)
            centroid = tuple(sum(color[pos] for color in vector)/len(vector) for pos in range(6))
            index = len(records)
            records.append(_record(item, colors))
            valid_items.append(item)
            values.append(colors)
            vectors.append(vector)
            centroids.append(centroid)
            counters.append(Counter(colors))
            exact_buckets[colors].append(index)
            set_buckets[tuple(sorted(colors))].append(index)
        except (TypeError, ValueError, KeyError) as exc:
            errors.append({"id": item.get("id"), "error": str(exc)})

    exact_groups, near_groups, candidate_pairs, family_groups = [], [], [], []
    for signature, indices in exact_buckets.items():
        if len(indices) > 1:
            exact_groups.append({"ids": [records[index]["id"] for index in indices],
                                 "reason": "same-ordered-rgba-array", "confidence": "high",
                                 "evidence": {"canonicalRGBA": list(signature), "sha256": _sha(signature)},
                                 "differences": {"notationOrSourceMayDiffer": True}})
    for signature, indices in set_buckets.items():
        if len(indices) > 1 and len({values[index] for index in indices}) > 1:
            family_groups.append({"ids": [records[index]["id"] for index in indices],
                                  "reason": "same-rgba-multiset-different-order", "confidence": "high",
                                  "evidence": {"sortedCanonicalRGBA": list(signature), "sha256": _sha(signature)},
                                  "differences": {"orderIsSemanticallySignificant": True,
                                                  "duplicatesInsideArraysCounted": True}})

    # These are original author-declared count variants, not inferred duplicates.
    declared = defaultdict(list)
    for index, item in enumerate(valid_items):
        definition = item.get("evidence", {}).get("definition", {})
        if (item.get("sourceName", "").startswith(("ColorBrewer /", "CARTOColors /")) and
                isinstance(definition.get("name"), str)):
            declared[(item["sourceName"], definition["name"])].append(index)
    for (source, name), indices in sorted(declared.items()):
        sizes = sorted({len(values[index]) for index in indices})
        if len(indices) > 1 and len(sizes) > 1:
            common = set(values[indices[0]])
            for index in indices[1:]:
                common.intersection_update(values[index])
            family_groups.append({"ids": [records[index]["id"] for index in indices],
                                  "reason": "author-declared-palette-size-variants", "confidence": "high",
                                  "evidence": {"sourceName": source, "definitionName": name,
                                               "actualColorCounts": sizes, "sharedCanonicalColors": sorted(common),
                                               "basis": "original stored definition name AND actual array sizes/colors"},
                                  "differences": {"distinctClassCountsArePurposeful": True,
                                                  "notClassifiedAsDuplicates": True}})

    counts = Counter({key: 0 for key in (
        "comparedPairs", "sameCountPairs", "differentCountPairs", "exactOrderedPairs",
        "exactReorderedPairs", "exactSubsetPairs", "centroidBoundRejectedPairs",
        "perceptualCandidatePairs", "nearOrderedPairs", "nearReversedPairs", "nearPermutedPairs",
        "symmetricNearestBoundRejectedPairs", "optimalAssignmentPairs", "optimalAssignmentRejectedPairs")})
    max_squared, mean_squared = MAX_LIMIT**2, MEAN_LIMIT**2
    for i in range(len(records)):
        for j in range(i+1, len(records)):
            counts["comparedPairs"] += 1
            left, right = values[i], values[j]
            if len(left) != len(right):
                counts["differentCountPairs"] += 1
                # Exact multiset containment is a family relation, never duplicate.
                small, large = (i, j) if len(left) < len(right) else (j, i)
                if all(counters[small][color] <= counters[large][color] for color in counters[small]):
                    counts["exactSubsetPairs"] += 1
                    family_groups.append(_pair(records[small], records[large], "exact-palette-multiset-subset",
                                               {"subsetColors": list(values[small]),
                                                "supersetColorCount": len(values[large]),
                                                "subsetColorCount": len(values[small])}, "high",
                                               {"extraColorsChangePalette": True,
                                                "notClassifiedAsDuplicates": True}))
                continue
            counts["sameCountPairs"] += 1
            if left == right:
                counts["exactOrderedPairs"] += 1
                continue
            if counters[i] == counters[j]:
                counts["exactReorderedPairs"] += 1
                continue

            # Norm of mean displacement cannot exceed mean norm under ANY matching.
            # This lower bound safely rejects impossible near pairs, without sampling.
            if (_distance_squared(centroids[i], centroids[j], 0) > mean_squared + 1e-12 or
                    _distance_squared(centroids[i], centroids[j], 3) > mean_squared + 1e-12):
                counts["centroidBoundRejectedPairs"] += 1
                continue
            counts["perceptualCandidatePairs"] += 1
            n = len(left)
            ordered = _metrics(vectors[i], vectors[j], range(n))
            if _close(ordered):
                counts["nearOrderedPairs"] += 1
                near_groups.append(_pair(records[i], records[j], "strict-perceptual-near-ordered-colors",
                                         ordered, "high",
                                         {"orderPreserved": True, "alphaPreserved": True,
                                          "notIdenticalColorValues": True}))
                continue
            reverse = _metrics(vectors[i], vectors[j], range(n-1, -1, -1))
            if _close(reverse):
                counts["nearReversedPairs"] += 1
                candidate_pairs.append(_pair(records[i], records[j], "strict-perceptual-near-reversed-colors",
                                             reverse, "high",
                                             {"orderReversed": True, "orderIsSemanticallySignificant": True,
                                              "notAutomaticDuplicate": True}))
                continue

            costs = [[max(_distances(a, b)) for b in vectors[j]] for a in vectors[i]]
            row_nearest = [min(row) for row in costs]
            col_nearest = [min(row[col] for row in costs) for col in range(n)]
            if (max(row_nearest + col_nearest) > MAX_LIMIT + 1e-12 or
                    max(sum(row_nearest), sum(col_nearest))/n > MEAN_LIMIT + 1e-12):
                counts["symmetricNearestBoundRejectedPairs"] += 1
                continue
            counts["optimalAssignmentPairs"] += 1
            # Forbid per-color max violations, then find the exact minimum mean.
            assignment = minimum_assignment([[cost if cost <= MAX_LIMIT + 1e-12 else 1e9
                                              for cost in row] for row in costs])
            metrics = _metrics(vectors[i], vectors[j], assignment)
            if _close(metrics):
                counts["nearPermutedPairs"] += 1
                candidate_pairs.append(_pair(records[i], records[j], "strict-perceptual-near-permuted-colors",
                                             {**metrics, "assignment": "optimal minimum sum worst-background distance"},
                                             "high", {"orderChanged": True, "orderIsSemanticallySignificant": True,
                                                      "notAutomaticDuplicate": True}))
            else:
                counts["optimalAssignmentRejectedPairs"] += 1

    n, total = len(inputs), len(inputs)*(len(inputs)-1)//2
    return {"methodology": {
                "version": 1, "scope": "all stored palette assets, no network or catalog mutation",
                "exact": "Canonical RGBA array; preserve alpha and order, normalize HEX case/shorthand/opaque ff notation",
                "metric": "Euclidean OKLab * 100 (NOT CIE DeltaE2000)",
                "precision": "IEEE-754 double values; no rounding before threshold decisions",
                "compositing": "encoded sRGB source-over opaque #000000 and #ffffff; convert each resulting sRGB composite to OKLab",
                "nearThresholds": {"meanWorstBackground": MEAN_LIMIT, "maxWorstBackground": MAX_LIMIT},
                "nearMatching": "all same-count pairs: order and reverse, then optimal one-to-one assignment with maximum-edge constraint",
                "safeLowerBounds": "black/white centroid norm and symmetric nearest-color distance; never arbitrary top-N or sampled comparisons",
                "grouping": "near results are pairs only; no transitive closure or chain collapsing",
                "confidenceScope": "High confidence describes the measured relation, not a human claim of visual indistinguishability or permission to delete distinct author tokens",
                "limits": {"maxColors": MAX_COLORS, "actualMaxColors": max(map(len, values), default=0)},
                "interpretation": "Same multiset/reverse/permutation, subsets and author size variants retain order/count semantics and are not automatic removals",
                "limitations": ["Palette-only numeric audit; no perceptual browser or human color-judgment claim",
                                "Different-size arrays use exact containment and original author family evidence, not interpolated resampling",
                                "Strict thresholds intentionally exclude broadly similar colors and may miss other useful family relations"]},
            "coverage": {"itemCount": n, "validItemCount": len(records), "pairUniverse": total,
                         **dict(counts), "invalidItemCount": len(errors),
                         "uncomparedPairsDueToInvalidItems": total - counts["comparedPairs"],
                         "exactGroupCount": len(exact_groups), "nearOrderedPairCount": len(near_groups),
                         "nearReorderedCandidatePairCount": len(candidate_pairs),
                         "familyGroupCount": len(family_groups)},
            "items": records, "exactGroups": exact_groups, "nearGroups": near_groups,
            "candidatePairs": candidate_pairs, "familyGroups": family_groups, "errors": errors}


def audit_color_representations(items):
    """Supplement: stored static CSS gradient colors vs palettes and gradients.

    An identical color array is only a relationship: CSS direction, stop placement
    and palette order have distinct semantics. The exact original CSS is retained.
    """
    selected, originals, gradients = [], {}, set()
    for item in items:
        is_gradient = (item.get("kind") == "code" and item.get("language") == "css" and
                       item.get("analysis", {}).get("assetType") == "gradient" and
                       item.get("analysis", {}).get("preview", {}).get("renderer") == "gradient" and
                       isinstance(item.get("colors"), list))
        if item.get("kind") == "palette" or is_gradient:
            originals[item["id"]] = item
            selected.append({**item, "kind": "palette"})
            if is_gradient:
                gradients.add(item["id"])
    report = audit(selected)
    for record in report["items"]:
        original = originals[record["id"]]
        record["originalKind"] = original["kind"]
        record["representationRole"] = "static-css-gradient" if record["id"] in gradients else "palette-array"
        if record["id"] in gradients:
            record["storedCSS"] = original.get("code", "")
            # Display/evidence only, never parsed into executable CSS by this audit.
            record["cssBodyWithoutComments"] = re.sub(r"/\*[\s\S]*?\*/", "", record["storedCSS"]).strip()
            record["cssBodySha256"] = hashlib.sha256(record["cssBodyWithoutComments"].encode("utf-8")).hexdigest()
    by_id = {record["id"]: record for record in report["items"]}
    retained = {}
    for section in ("exactGroups", "nearGroups", "candidatePairs", "familyGroups"):
        relevant = []
        for finding in report[section]:
            gradient_ids = [identity for identity in finding["ids"] if identity in gradients]
            if not gradient_ids:
                continue
            relation = finding["reason"]
            mixed_kinds = any(identity not in gradients for identity in finding["ids"])
            finding["reason"] = ("cross-kind-related-color-representation" if mixed_kinds else
                                 {"exactGroups": "gradient-color-array-exact-relation",
                                  "nearGroups": "gradient-color-array-near-relation",
                                  "candidatePairs": "gradient-color-array-reordered-near-relation",
                                  "familyGroups": "gradient-color-array-family-relation"}[section])
            finding["evidence"]["numericColorRelation"] = relation
            finding["evidence"]["gradientCSS"] = [
                {"id": identity, "sourceName": by_id[identity]["sourceName"],
                 "sourceUrl": by_id[identity]["sourceUrl"],
                 "storedCodeSha256": by_id[identity]["storedCodeSha256"],
                 "cssBody": by_id[identity]["cssBodyWithoutComments"],
                 "cssBodySha256": by_id[identity]["cssBodySha256"]}
                for identity in gradient_ids]
            finding["differences"] = {**finding.get("differences", {}),
                                      "originalKinds": {identity: originals[identity]["kind"] for identity in finding["ids"]},
                                      "gradientDirectionStopsAndPaletteRoleRetained": True,
                                      "notAutomaticDuplicate": True}
            relevant.append(finding)
        report[section] = relevant
        retained["retained" + section[0].upper() + section[1:] + "Count"] = len(relevant)
    report["coverage"].update({"paletteItemCount": len(selected)-len(gradients),
                               "staticCSSGradientItemCount": len(gradients), **retained})
    report["methodology"].update({
        "scope": "all palettes plus stored static CSS gradients with actual colors and gradient preview renderer",
        "findingFilter": "retain only groups/pairs with at least one static CSS gradient; palette-only findings remain in palette.json",
        "confidenceScope": "High confidence concerns numeric color relationships only; no CSS rendering equivalence or automatic deletion claim",
        "interpretation": "Color-identical palette arrays and CSS gradients are related representations; CSS directions, stop positions and original roles remain inspectable",
        "limitations": report["methodology"]["limitations"] + [
            "Colors of CSS effects rendered by the CSS motion renderer are outside this static gradient supplement",
            "Exact color arrays do not establish equal gradient geometry or rendering"]})
    return report


def atomic_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="\n", delete=False,
                                     dir=path.parent, prefix="palette-audit-", suffix=".tmp") as handle:
        temporary = Path(handle.name)
        json.dump(value, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    try:
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def main():
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path, default=root / "data/catalog.json")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--include-gradients", action="store_true", help="Generate the supplemental static gradient color representation report")
    args = parser.parse_args()
    raw = args.catalog.read_bytes()
    if len(raw) > 128*1024*1024:
        raise ValueError("Catalog exceeds 128 MiB audit bound")
    document = json.loads(raw)
    report = (audit_color_representations if args.include_gradients else audit)(document["items"])
    report["catalogSha256"] = hashlib.sha256(raw).hexdigest()
    output = args.output or root / "data/duplicate-audit" / ("color-representations.json" if args.include_gradients else "palette.json")
    atomic_json(output, report)
    print(json.dumps(report["coverage"], ensure_ascii=False))
    if report["errors"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
