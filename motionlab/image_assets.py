"""Validate local image asset descriptors without trusting catalog paths."""

import hashlib
from pathlib import Path
import re

from .validation import ValidationError

PATH_RE = re.compile(r"assets/materials/[a-z0-9][a-z0-9-]{0,139}\.jpg\Z")
HASH_RE = re.compile(r"[a-f0-9]{64}\Z")
MAX_IMAGE_BYTES = 4 * 1024 * 1024


def jpeg_dimensions(body):
    """Read bounded JPEG marker segments, without decoding or running plugins."""
    position = 2
    while position + 4 <= len(body):
        if body[position] != 0xff:
            raise ValidationError("image has an invalid JPEG header")
        while position < len(body) and body[position] == 0xff:
            position += 1
        if position >= len(body):
            break
        marker = body[position]
        position += 1
        if marker in (0xd8, 0xd9, 0xda):
            break
        if position + 2 > len(body):
            break
        length = int.from_bytes(body[position:position + 2], "big")
        if length < 2 or position + length > len(body):
            raise ValidationError("image has an invalid JPEG segment")
        if marker in (0xc0, 0xc1, 0xc2):
            if length < 8 or body[position + 2] != 8:
                raise ValidationError("image JPEG format is not supported")
            return (int.from_bytes(body[position + 5:position + 7], "big"),
                    int.from_bytes(body[position + 3:position + 5], "big"))
        position += length
    raise ValidationError("image has no supported JPEG size header")


def validate_image(image, dist_root=None, *, verify_file=True):
    if not isinstance(image, dict):
        raise ValidationError("image must be a descriptor")
    required = {"path", "mime", "width", "height", "sha256", "sourceSha256"}
    if not required <= set(image) or set(image) - required:
        raise ValidationError("image has unsupported fields")
    if not isinstance(image["path"], str) or not PATH_RE.fullmatch(image["path"]):
        raise ValidationError("image path is not supported")
    if image["mime"] != "image/jpeg":
        raise ValidationError("image MIME is not supported")
    if any(type(image[key]) is not int or not 32 <= image[key] <= 1024
           for key in ("width", "height")):
        raise ValidationError("image dimensions must be from 32 to 1024")
    if any(not isinstance(image[key], str) or not HASH_RE.fullmatch(image[key])
           for key in ("sha256", "sourceSha256")):
        raise ValidationError("image digest is not supported")
    if not verify_file:
        return image
    root = Path(dist_root or Path(__file__).resolve().parent.parent / "dist").resolve()
    path = (root / image["path"]).resolve()
    try:
        path.relative_to(root)
    except ValueError as error:
        raise ValidationError("image is outside the asset directory") from error
    if not path.is_file() or not 4 <= path.stat().st_size <= MAX_IMAGE_BYTES:
        raise ValidationError("image file is missing or exceeds the size limit")
    body = path.read_bytes()
    if not body.startswith(b"\xff\xd8\xff") or not body.endswith(b"\xff\xd9"):
        raise ValidationError("image is not a JPEG")
    if jpeg_dimensions(body) != (image["width"], image["height"]):
        raise ValidationError("image dimensions do not match its JPEG header")
    if hashlib.sha256(body).hexdigest() != image["sha256"]:
        raise ValidationError("image digest does not match")
    return image
