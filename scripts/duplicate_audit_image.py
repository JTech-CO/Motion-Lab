"""Offline, bounded inspection of stored image materials and all image pairs."""

from collections import defaultdict
import hashlib
from pathlib import Path

from motionlab.image_assets import validate_image
from scripts.import_phase2_materials import decode_image, image_features, near_image

ROOT = Path(__file__).resolve().parents[1]


def audit(items, root=ROOT):
    selected = [item for item in items if item.get("kind") == "image"]
    if len(selected) > 3000:
        raise ValueError("Image audit exceeds 3000 stored materials")
    manifest, errors, parsed = [], [], []
    for item in selected:
        try:
            descriptor = validate_image(item.get("image"), Path(root) / "dist")
            body = (Path(root) / "dist" / descriptor["path"]).read_bytes()
            feature = image_features(decode_image(body))
            signature = hashlib.sha256(body).hexdigest()
            manifest.append({"id": item["id"], "canonicalSha256": signature,
                             "storedImageSha256": signature,
                             "originalImageSha256": descriptor["sourceSha256"],
                             "width": descriptor["width"], "height": descriptor["height"],
                             "features": feature})
            parsed.append((item, feature))
        except (ValueError, OSError, KeyError) as error:
            errors.append({"id": item.get("id"), "reason": str(error)[:300]})
    groups = defaultdict(list)
    for item, _ in parsed:
        groups[item["image"]["sha256"]].append(item["id"])
    exact = [{"ids": ids, "reason": "identical-stored-image", "confidence": "high"}
             for ids in groups.values() if len(ids) > 1]
    near, comparisons = [], 0
    for index, (left, left_features) in enumerate(parsed):
        for right, right_features in parsed[index + 1:]:
            comparisons += 1
            if left["image"]["sha256"] == right["image"]["sha256"]:
                continue
            reason = near_image(left_features, right_features)
            if reason:
                near.append({"ids": [left["id"], right["id"]], "reason": reason,
                             "confidence": "high",
                             "evidence": "All rotation/reflection hashes and color/texture statistics were compared on stored local images."})
    return {"coverage": {"itemCount": len(selected), "pairUniverse": len(selected) * (len(selected) - 1) // 2,
                         "pairComparisons": comparisons},
            "methodology": {"version": 1,
                "exact": "SHA-256 of the actual stored JPEG after descriptor/file validation.",
                "near": "8 rotation/reflection pHashes plus color quantiles, radial frequency, edge and low-contrast surface comparisons.",
                "pairCoverage": "Every successfully decoded local image pair.",
                "limitations": "Conservative surface-family similarity, not a guarantee of universal perceptual uniqueness."},
            "items": manifest, "errors": errors, "exactGroups": exact,
            "nearGroups": near, "candidatePairs": [], "familyGroups": []}
