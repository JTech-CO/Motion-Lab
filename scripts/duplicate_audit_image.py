"""Offline, bounded inspection of stored image materials and all image pairs."""

from collections import defaultdict
import hashlib
import io
import warnings

import numpy as np
from PIL import Image, ImageOps
from pathlib import Path

from motionlab.image_assets import validate_image

ROOT = Path(__file__).resolve().parents[1]
MAX_IMAGE = 4 * 1024 * 1024


def decode_image(body):
    if len(body) > MAX_IMAGE or not (body.startswith(b"\xff\xd8\xff") or body.startswith(b"\x89PNG\r\n\x1a\n")
                                   or body[:4] == b"RIFF" and body[8:12] == b"WEBP"):
        raise ValueError("Color map has unsupported image magic or size")
    with warnings.catch_warnings():
        warnings.simplefilter("error", Image.DecompressionBombWarning)
        with Image.open(io.BytesIO(body)) as image:
            if image.format not in ("JPEG", "PNG", "WEBP") or getattr(image, "n_frames", 1) != 1:
                raise ValueError("Only one static color map is supported")
            if not 32 <= image.width <= 4096 or not 32 <= image.height <= 4096 or image.width * image.height > 4_194_304:
                raise ValueError("Color map exceeds pixel bounds")
            image.load()
            return ImageOps.exif_transpose(image).convert("RGB")


def image_features(image):
    """Geometry hashes plus color/texture statistics, including tile rotations."""
    small = np.asarray(image.resize((64, 64), Image.Resampling.LANCZOS), dtype=np.float64) / 255.0
    gray = np.dot(small, [0.299, 0.587, 0.114])
    n = 32
    transform = np.cos(np.pi * (2 * np.arange(n)[None, :] + 1) * np.arange(8)[:, None] / (2 * n))
    hashes = []
    for mirrored in (gray, np.fliplr(gray)):
        for rotation in range(4):
            thumb = np.asarray(Image.fromarray((np.rot90(mirrored, rotation) * 255).astype(np.uint8)).resize((n, n)), dtype=np.float64)
            coefficients = (transform @ thumb @ transform.T).flatten()[1:]
            bits = coefficients > np.median(coefficients)
            hashes.append(sum(int(value) << index for index, value in enumerate(bits)))
    quantiles = np.quantile(small.reshape(-1, 3), [0.05, 0.25, 0.5, 0.75, 0.95], axis=0).ravel()
    power = np.abs(np.fft.fftshift(np.fft.fft2(gray - gray.mean()))) ** 2
    yy, xx = np.indices(power.shape)
    radius = np.sqrt((xx - 32) ** 2 + (yy - 32) ** 2)
    spectrum = np.asarray([power[(radius >= low) & (radius < high)].sum()
                           for low, high in zip([1, 2, 4, 8, 12, 18, 26], [2, 4, 8, 12, 18, 26, 46])])
    spectrum = spectrum / max(spectrum.sum(), 1e-12)
    edge = float(np.mean(np.abs(np.diff(gray, axis=0))) + np.mean(np.abs(np.diff(gray, axis=1))))
    gray_quantiles = np.quantile(gray, [0.05, 0.25, 0.5, 0.75, 0.95])
    return {"hashes": hashes, "quantiles": quantiles.tolist(), "grayQuantiles": (gray_quantiles - gray_quantiles[2]).tolist(), "spectrum": spectrum.tolist(), "edge": edge,
            "mean": small.mean(axis=(0, 1)).tolist()}


def near_image(left, right):
    color = float(np.max(np.abs(np.asarray(left["quantiles"]) - right["quantiles"])))
    contrast = float(np.max(np.abs(np.asarray(left["grayQuantiles"]) - right["grayQuantiles"])))
    if color > 0.075 and contrast > 0.04:
        return None
    spectrum = float(np.sum(np.abs(np.asarray(left["spectrum"]) - right["spectrum"])))
    hamming = min((a ^ b).bit_count() for a in left["hashes"] for b in right["hashes"])
    if hamming <= 8 and (color <= 0.075 or contrast <= 0.04):
        return "perceptual-geometry"
    if (np.ptp(left["grayQuantiles"]) <= 0.08 and np.ptp(right["grayQuantiles"]) <= 0.08
            and contrast <= 0.025 and abs(left["edge"] - right["edge"]) <= 0.018):
        return "low-contrast-surface-family"
    # Catches near-isotropic texture crops whose positional hashes differ.
    if ((color <= 0.045 or contrast <= 0.035) and spectrum <= 0.18 and abs(left["edge"] - right["edge"]) <= 0.018
            and max(left["edge"], right["edge"]) <= 0.23):
        return "texture-statistics"
    return None


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
