"""Offline, bounded inspection of stored image materials and all image pairs."""

from collections import Counter, defaultdict
import hashlib
import io
import warnings

import numpy as np
from PIL import Image, ImageOps
from pathlib import Path

from motionlab.image_assets import validate_image

ROOT = Path(__file__).resolve().parents[1]
MAX_IMAGE = 4 * 1024 * 1024
STRUCTURE_SIZE = 128
STRUCTURE_THRESHOLD = 0.985
STRUCTURE_REVIEW_THRESHOLD = 0.90


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
    """Unchanged coarse candidate screen, not a confirmed near-duplicate gate."""
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


def image_structure(image):
    """Bounded positional luminance, independent of mean color and contrast.

    Keep one normalized plane and one FFT per image, not all eight D4 FFTs.
    The arrays are local working data and are never serialized into reports.
    """
    rgb = np.asarray(image.resize((STRUCTURE_SIZE, STRUCTURE_SIZE), Image.Resampling.LANCZOS),
                     dtype=np.float32) / 255.0
    gray = rgb @ np.asarray([0.299, 0.587, 0.114], dtype=np.float32)
    centered = gray - gray.mean(dtype=np.float64)
    norm = float(np.linalg.norm(centered))
    standard_deviation = float(centered.std())
    if standard_deviation <= 1e-7:
        return {"normalized": None, "fft": None, "spatialStd": standard_deviation,
                "normalizedLuminanceSha256": None}
    normalized = np.asarray(centered / norm, dtype=np.float32)
    return {"normalized": normalized,
            "fft": np.asarray(np.fft.rfft2(normalized), dtype=np.complex64),
            "spatialStd": standard_deviation,
            "normalizedLuminanceSha256": hashlib.sha256(normalized.astype("<f4").tobytes()).hexdigest()}


def structure_orientations(structure):
    """Generate one left image's D4 spectra, reused across its coarse pairs."""
    if structure["normalized"] is None:
        return []
    return [(mirrored, rotation,
             np.asarray(np.fft.rfft2(np.rot90(np.fliplr(structure["normalized"]) if mirrored
                                             else structure["normalized"], rotation)), dtype=np.complex64))
            for mirrored in (False, True) for rotation in range(4)]


def compare_image_structure(left, right, *, orientations=None):
    """Maximum normalized correlation over D4 and every integer periodic shift.

    Absolute correlation permits an affine luminance inversion after recoloring.
    It does not claim to identify arbitrary crops, scale changes or random textures.
    """
    evidence = {"resolution": [STRUCTURE_SIZE, STRUCTURE_SIZE],
                "threshold": STRUCTURE_THRESHOLD,
                "leftSpatialStd": left["spatialStd"], "rightSpatialStd": right["spatialStd"],
                "periodicShiftCountPerOrientation": STRUCTURE_SIZE ** 2,
                "orientationCount": 8}
    if left["fft"] is None or right["fft"] is None:
        return {**evidence, "status": "insufficient-spatial-variance", "confirmed": False,
                "normalizedCorrelation": None}
    best = None
    for mirrored, rotation, spectrum in (orientations if orientations is not None
                                        else structure_orientations(left)):
        correlation = np.fft.irfft2(spectrum * np.conj(right["fft"]),
                                   s=(STRUCTURE_SIZE, STRUCTURE_SIZE))
        peak = np.unravel_index(np.argmax(np.abs(correlation)), correlation.shape)
        signed_score = float(correlation[peak])
        score = min(1.0, abs(signed_score))
        if best is None or score > best["normalizedCorrelation"]:
            best = {"normalizedCorrelation": score,
                    "leftTransform": {"reflectedHorizontally": mirrored,
                                      "counterclockwiseQuarterTurns": rotation},
                    "periodicShiftOfRight": {"y": int(peak[0]), "x": int(peak[1])},
                    "luminancePolarity": 1 if signed_score >= 0 else -1}
    confirmed = best["normalizedCorrelation"] >= STRUCTURE_THRESHOLD
    return {**evidence, **best, "status": "confirmed" if confirmed else "below-structure-threshold",
            "confirmed": confirmed}


def audit(items, root=ROOT):
    selected = [item for item in items if item.get("kind") == "image"]
    if len(selected) > 3000:
        raise ValueError("Image audit exceeds 3000 stored materials")
    manifest, errors, parsed = [], [], []
    for item in selected:
        try:
            descriptor = validate_image(item.get("image"), Path(root) / "dist")
            body = (Path(root) / "dist" / descriptor["path"]).read_bytes()
            decoded = decode_image(body)
            feature = image_features(decoded)
            structure = image_structure(decoded)
            signature = hashlib.sha256(body).hexdigest()
            manifest.append({"id": item["id"], "canonicalSha256": signature,
                             "storedImageSha256": signature,
                             "originalImageSha256": descriptor["sourceSha256"],
                             "width": descriptor["width"], "height": descriptor["height"],
                             "features": feature,
                             "positionStructure": {"resolution": [STRUCTURE_SIZE, STRUCTURE_SIZE],
                                                   "spatialStd": structure["spatialStd"],
                                                   "normalizedLuminanceSha256": structure["normalizedLuminanceSha256"]}})
            parsed.append((item, feature, structure))
        except (ValueError, OSError, KeyError) as error:
            errors.append({"id": item.get("id"), "reason": str(error)[:300]})
    groups = defaultdict(list)
    for item, _, _ in parsed:
        groups[item["image"]["sha256"]].append(item["id"])
    exact = [{"ids": ids, "reason": "identical-stored-image", "confidence": "high"}
             for ids in groups.values() if len(ids) > 1]
    near, candidates, statistical_alerts, comparisons = [], [], [], 0
    coarse_counts, confirmed_counts, unresolved_counts, statistical_counts = Counter(), Counter(), Counter(), Counter()
    score_distribution = Counter()
    insufficient = 0
    for index, (left, left_features, left_structure) in enumerate(parsed):
        orientations = None
        for right, right_features, right_structure in parsed[index + 1:]:
            comparisons += 1
            if left["image"]["sha256"] == right["image"]["sha256"]:
                continue
            reason = near_image(left_features, right_features)
            if reason:
                coarse_counts[reason] += 1
                if orientations is None:
                    orientations = structure_orientations(left_structure)
                structure_result = compare_image_structure(left_structure, right_structure,
                                                           orientations=orientations)
                evidence = {"coarseReason": reason, "structure": structure_result,
                            "source": "Actual descriptor-validated stored JPEG pixels, resized to 128x128; no name/category comparison.",
                            "images": [{"id": entry["id"], "path": entry["image"]["path"],
                                        "storedImageSha256": entry["image"]["sha256"],
                                        "originalImageSha256": entry["image"]["sourceSha256"]}
                                       for entry in (left, right)],
                            "interpretation": "Coarse statistics nominate pairs; only positional structure confirms a high-confidence near relation. Below-threshold scores do not certify uniqueness."}
                score = structure_result["normalizedCorrelation"]
                band = "insufficient-spatial-variance" if score is None else next(
                    label for ceiling, label in ((0.5, "below-0.5"), (0.8, "0.5-to-0.8"),
                                                 (0.9, "0.8-to-0.9"), (0.97, "0.9-to-0.97"),
                                                 (0.985, "0.97-to-0.985"), (2, "0.985-and-above"))
                    if score < ceiling)
                score_distribution[band] += 1
                if structure_result["confirmed"]:
                    confirmed_counts[reason] += 1
                    near.append({"ids": [left["id"], right["id"]],
                                 "reason": "confirmed-periodic-image-structure", "confidence": "high",
                                 "evidence": evidence})
                elif score is None or score >= STRUCTURE_REVIEW_THRESHOLD:
                    unresolved_counts[reason] += 1
                    insufficient += structure_result["status"] == "insufficient-spatial-variance"
                    candidates.append({"ids": [left["id"], right["id"]],
                                       "reason": "coarse-image-similarity-without-structure-confirmation",
                                       "confidence": "low", "evidence": evidence})
                else:
                    statistical_counts[reason] += 1
                    statistical_alerts.append({"ids": [left["id"], right["id"]],
                                               "reason": "coarse-statistics-position-model-disagreement",
                                               "confidence": "low", "evidence": evidence})
    return {"coverage": {"itemCount": len(selected), "pairUniverse": len(selected) * (len(selected) - 1) // 2,
                         "successfullyDecodedImageCount": len(parsed),
                         "decodedPairUniverse": len(parsed) * (len(parsed) - 1) // 2,
                         "pairComparisons": comparisons,
                         "coarseAlarmCount": sum(coarse_counts.values()),
                         "coarseAlarmCountsByReason": dict(sorted(coarse_counts.items())),
                         "structureRecheckPairCount": sum(coarse_counts.values()),
                         "confirmedStructurePairCount": len(near),
                         "confirmedCountsByCoarseReason": dict(sorted(confirmed_counts.items())),
                         "unresolvedCoarsePairCount": len(candidates),
                         "unresolvedCountsByCoarseReason": dict(sorted(unresolved_counts.items())),
                         "statisticalAlertCount": len(statistical_alerts),
                         "statisticalAlertCountsByCoarseReason": dict(sorted(statistical_counts.items())),
                         "structureScoreDistribution": dict(sorted(score_distribution.items())),
                         "insufficientSpatialVariancePairCount": insufficient},
            "methodology": {"version": 2,
                "exact": "SHA-256 of the actual stored JPEG after descriptor/file validation.",
                "candidate": "Unchanged coarse screen: 8 rotation/reflection pHashes plus color quantiles, radial frequency, edge and low-contrast surface comparisons. Every alarm and original reason is retained: confirmed structure in nearGroups; 0.90-to-0.985 or insufficient structure in candidatePairs; below-0.90 model disagreements in statisticalAlerts. No alarm is declared unique.",
                "near": "Coarse alarms require positional mean-centered, unit-L2 luminance correlation on actual 128x128 JPEG pixels. FFT checks all 16384 periodic integer shifts in each of 8 D4 orientations. Affine recoloring and luminance inversion are allowed; maximum absolute correlation must be >=0.985.",
                "nearThresholds": {"normalizedPositionCorrelation": STRUCTURE_THRESHOLD,
                                   "unresolvedReviewBandMinimum": STRUCTURE_REVIEW_THRESHOLD},
                "metric": {"structureResolution": [STRUCTURE_SIZE, STRUCTURE_SIZE],
                           "normalization": "Mean-centered luminance divided by spatial L2 norm; QA measurement only, source pixels unchanged.",
                           "workingArrays": "One float32 plane and one complex64 rFFT per decoded image; eight left spectra reused within that image's pair loop. No all-pairs matrix or pixel arrays in JSON.",
                           "workingArrayBytesPerImage": STRUCTURE_SIZE ** 2 * 4 + STRUCTURE_SIZE * (STRUCTURE_SIZE // 2 + 1) * 8,
                           "maximumDecodedImages": 3000},
                "nearMatching": "Only confirmed structure pairs enter nearGroups. Candidate and model-disagreement reports retain scores, orientation, shift and file SHA evidence. The 0.90 review band is a conservative operational uncertainty band, not a calibrated perceptual probability; actual score distribution is recorded in coverage. Statistics alone never confirm a duplicate.",
                "pairCoverage": "Every successfully decoded local image pair.",
                "limitations": "Two-stage stored-pixel comparison, not universal perceptual uniqueness. No arbitrary crop, subpixel shift, scale, perspective or stochastic material-family guarantee; the structure gate only rechecks coarse alarms. Equal grayscale structure can preserve palette variants; flat images cannot establish positional structure. No asset is deleted or merged by this audit."},
            "items": manifest, "errors": errors, "exactGroups": exact,
            "nearGroups": near, "candidatePairs": candidates, "statisticalAlerts": statistical_alerts,
            "familyGroups": []}
