"""Stored-image audit bounds and perceptual comparisons; no network requests."""

import io
import unittest

import numpy as np
from PIL import Image

from scripts.duplicate_audit_image import decode_image, image_features, near_image


class ImageAuditTest(unittest.TestCase):
    def test_image_decode_rejects_html_fake_extensions_and_extreme_dimensions(self):
        for body in (b"<html>not an image</html>", b"\xff\xd8\xffnotvalid"):
            with self.assertRaises((ValueError, OSError)):
                decode_image(body)
        output = io.BytesIO()
        Image.new("RGB", (5000, 50)).save(output, "PNG")
        with self.assertRaises(ValueError):
            decode_image(output.getvalue())
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


if __name__ == "__main__":
    unittest.main()
