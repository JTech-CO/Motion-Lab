"""Stored-image audit bounds and perceptual comparisons; no network requests."""

import io
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

import numpy as np
from PIL import Image

from scripts.duplicate_audit_image import (MAX_IMAGE, audit, compare_image_structure,
                                          decode_image, image_features, image_structure, near_image)


def gray_image(plane):
    return Image.fromarray(np.repeat(np.clip(plane, 0, 255).astype(np.uint8)[:, :, None], 3, axis=2))


def different_coarse_grids(amplitude=8):
    """Identical low-frequency composition; stripes and circular grid differ."""
    n = 128
    yy, xx = np.indices((n, n))
    coefficients = np.random.default_rng(734).uniform(-1, 1, (8, 8))
    coefficients[0, 0] = 0
    basis = np.cos(np.pi * (2 * np.arange(n)[None, :] + 1) * np.arange(8)[:, None] / (2 * n))
    base = 120 + 4 * basis.T @ coefficients @ basis
    stripes = base + amplitude * np.where((xx // 4) % 2, 1, -1)
    circular_grid = base + amplitude * np.where(
        np.cos(xx * 2 * np.pi / 16) + np.cos(yy * 2 * np.pi / 16) > 0.15, 1, -1)
    return gray_image(stripes), gray_image(circular_grid)


def stored_items(root, named_images):
    items = []
    for name, image in named_images:
        output = io.BytesIO()
        image.save(output, "JPEG", quality=100, subsampling=0)
        body = output.getvalue()
        relative = f"assets/materials/{name}.jpg"
        target = Path(root) / "dist" / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(body)
        digest = hashlib.sha256(body).hexdigest()
        items.append({"id": name, "kind": "image", "image": {
            "path": relative, "mime": "image/jpeg", "width": image.width, "height": image.height,
            "sha256": digest, "sourceSha256": digest}})
    return items


class ImageAuditTest(unittest.TestCase):
    def test_image_decode_rejects_html_fake_extensions_and_extreme_dimensions(self):
        for body in (b"<html>not an image</html>", b"\xff\xd8\xffnotvalid"):
            with self.assertRaises((ValueError, OSError)):
                decode_image(body)
        output = io.BytesIO()
        Image.new("RGB", (5000, 50)).save(output, "PNG")
        with self.assertRaises(ValueError):
            decode_image(output.getvalue())
        with self.assertRaises(ValueError):
            decode_image(b"\xff\xd8\xff" + b"a" * MAX_IMAGE)
        output = io.BytesIO()
        Image.new("RGB", (64, 64), "blue").save(output, "JPEG")
        self.assertEqual(decode_image(output.getvalue()).size, (64, 64))

    def test_perceptual_comparison_groups_rotation_and_small_color_change(self):
        rng = np.random.default_rng(31)
        texture = np.asarray(rng.uniform(30, 220, (64, 64, 3)), dtype=np.uint8)
        image = Image.fromarray(texture)
        first = image_features(image)
        rotated = image_features(image.rotate(90))
        shifted = image_features(Image.fromarray(np.clip(texture.astype(int) + 3, 0, 255).astype(np.uint8)))
        self.assertIsNotNone(near_image(first, rotated))
        self.assertIsNotNone(near_image(first, shifted))
        self.assertIsNone(near_image(first, image_features(Image.new("RGB", (64, 64), "red"))))

    def test_structure_confirms_periodic_shift_reflection_and_affine_recolor(self):
        yy, xx = np.indices((128, 128))
        plane = 70 + np.where((xx // 16 + yy // 8) % 2, 60, 0)
        plane += np.where((xx - 43) ** 2 + (yy - 76) ** 2 < 211, 45, 0)
        first = gray_image(plane)
        for shift in ((19, 31), (18, 30)):
            transformed = np.roll(np.fliplr(np.rot90(plane)), shift, axis=(0, 1))
            recolored = Image.fromarray(np.stack(
                [transformed + 30, transformed - 15, transformed], axis=-1).astype(np.uint8))
            result = compare_image_structure(image_structure(first), image_structure(recolored))
            self.assertTrue(result["confirmed"])
            self.assertGreater(result["normalizedCorrelation"], 0.999)
            self.assertEqual(result["orientationCount"], 8)
            self.assertEqual(result["periodicShiftCountPerOrientation"], 16384)
            self.assertTrue(result["leftTransform"]["reflectedHorizontally"])
            if shift == (18, 30):
                self.assertIsNotNone(near_image(image_features(first), image_features(recolored)))
        # Palette inversion preserves authored positions as well.
        inverse = compare_image_structure(image_structure(first), image_structure(gray_image(255 - plane)))
        self.assertTrue(inverse["confirmed"])
        self.assertEqual(inverse["luminancePolarity"], -1)

    def test_blue_low_contrast_loop_variants_do_not_match_gray_noise(self):
        yy, xx = np.indices((128, 128))
        rng = np.random.default_rng(817)
        noise = gray_image(rng.integers(45, 52, (128, 128)))
        for period, radius in ((32, 10), (24, 8), (16, 5)):
            distance = (xx % period - period // 2) ** 2 + (yy % period - period // 2) ** 2
            ring = (distance < radius ** 2) & (distance > (radius - 3) ** 2)
            blue = np.zeros((128, 128, 3), dtype=np.uint8)
            blue[:] = [26, 35, 95]
            blue[ring] += np.asarray([5, 5, 5], dtype=np.uint8)
            loops = Image.fromarray(blue)
            self.assertIsNotNone(near_image(image_features(loops), image_features(noise)))
            result = compare_image_structure(image_structure(loops), image_structure(noise))
            self.assertFalse(result["confirmed"])
            self.assertLess(result["normalizedCorrelation"], 0.90)

    def test_same_low_frequency_hashes_do_not_confirm_different_tile_geometry(self):
        stripes, circles = different_coarse_grids()
        self.assertEqual(near_image(image_features(stripes), image_features(circles)), "perceptual-geometry")
        result = compare_image_structure(image_structure(stripes), image_structure(circles))
        self.assertFalse(result["confirmed"])
        self.assertLess(result["normalizedCorrelation"], 0.90)

    def test_stored_jpeg_audit_preserves_alarms_and_only_confirms_structure(self):
        stripes, circles = different_coarse_grids()
        rotated = np.roll(np.fliplr(np.rot90(np.asarray(stripes))), (16, 24), axis=(0, 1))
        recolored = Image.fromarray(rotated + np.asarray([3, 1, 5], dtype=np.uint8))
        with tempfile.TemporaryDirectory() as directory:
            items = stored_items(directory, [("stripes", stripes), ("transformed", recolored), ("circles", circles)])
            result = audit(items, Path(directory))
        self.assertFalse(result["errors"])
        self.assertEqual(result["coverage"]["pairComparisons"], 3)
        self.assertEqual([entry["ids"] for entry in result["nearGroups"]], [["stripes", "transformed"]])
        self.assertTrue(any(entry["ids"] == ["stripes", "circles"] for entry in result["statisticalAlerts"]))
        self.assertEqual(result["coverage"]["coarseAlarmCount"],
                         len(result["nearGroups"]) + len(result["candidatePairs"]) + len(result["statisticalAlerts"]))
        alert = result["statisticalAlerts"][0]["evidence"]
        self.assertEqual(len(alert["images"][0]["storedImageSha256"]), 64)
        self.assertIn("periodicShiftOfRight", alert["structure"])
        self.assertIn("normalizedLuminanceSha256", result["items"][0]["positionStructure"])
        self.assertNotIn("normalized", result["items"][0]["positionStructure"])
        self.assertLess(len(json.dumps(result)), 30000)

    def test_review_band_and_flat_images_remain_unresolved(self):
        stripes, circles = different_coarse_grids(amplitude=3)
        with tempfile.TemporaryDirectory() as directory:
            result = audit(stored_items(directory, [("stripes", stripes), ("circles", circles)]), Path(directory))
        self.assertFalse(result["nearGroups"])
        self.assertEqual(len(result["candidatePairs"]), 1)
        score = result["candidatePairs"][0]["evidence"]["structure"]["normalizedCorrelation"]
        self.assertGreaterEqual(score, 0.90)
        self.assertLess(score, 0.985)
        with tempfile.TemporaryDirectory() as directory:
            result = audit(stored_items(directory, [("flat-a", Image.new("RGB", (128, 128), (20, 20, 20))),
                                                   ("flat-b", Image.new("RGB", (128, 128), (21, 21, 21)))]), Path(directory))
        self.assertFalse(result["nearGroups"])
        self.assertEqual(len(result["candidatePairs"]), 1)
        self.assertEqual(result["candidatePairs"][0]["evidence"]["structure"]["status"],
                         "insufficient-spatial-variance")

    def test_material_count_bound_precedes_decoding(self):
        with self.assertRaises(ValueError):
            audit([{"kind": "image"}] * 3001)


if __name__ == "__main__":
    unittest.main()
