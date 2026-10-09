"""Bounded SQLite payload compression; old TEXT catalogs remain readable."""

import json
import math
import zlib

MAGIC = b"MLZ1\0"
MAX_DECODED_BYTES = 8 * 1024 * 1024
MAX_PACKED_BYTES = 8 * 1024 * 1024


class PayloadError(ValueError):
    """Invalid stored catalog payload; no raw data is included in errors."""


def _duplicate_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise PayloadError("Stored payload has duplicate keys")
        result[key] = value
    return result


def _invalid_constant(_value):
    raise PayloadError("Stored payload has a non-finite number")


def _finite_float(value):
    result = float(value)
    if not math.isfinite(result):
        raise PayloadError("Stored payload has a non-finite number")
    return result


def encode_payload(item):
    if not isinstance(item, dict):
        raise PayloadError("Stored payload must be an object")
    try:
        body = json.dumps(item, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")
    except (ValueError, TypeError, UnicodeError, RecursionError) as error:
        raise PayloadError("Stored payload cannot be encoded") from error
    if len(body) > MAX_DECODED_BYTES:
        raise PayloadError("Stored payload exceeds 8 MiB")
    packed = MAGIC + zlib.compress(body, level=6)
    if len(packed) > MAX_PACKED_BYTES:
        raise PayloadError("Packed payload exceeds 8 MiB")
    return packed


def decode_payload(value):
    try:
        if isinstance(value, str):
            body = value.encode("utf-8")
            if len(body) > MAX_DECODED_BYTES:
                raise PayloadError("Stored payload exceeds 8 MiB")
        elif isinstance(value, (bytes, bytearray, memoryview)):
            if len(value) > MAX_PACKED_BYTES or len(value) <= len(MAGIC):
                raise PayloadError("Packed payload has an invalid size")
            packed = bytes(value)
            if not packed.startswith(MAGIC):
                raise PayloadError("Packed payload has an unknown format")
            decoder = zlib.decompressobj()
            body = decoder.decompress(packed[len(MAGIC):], MAX_DECODED_BYTES + 1)
            if (len(body) > MAX_DECODED_BYTES or not decoder.eof
                    or decoder.unconsumed_tail or decoder.unused_data):
                raise PayloadError("Packed payload is truncated, oversized or has trailing data")
        else:
            raise PayloadError("Stored payload has an unsupported type")
        result = json.loads(body.decode("utf-8"), object_pairs_hook=_duplicate_keys,
                            parse_constant=_invalid_constant, parse_float=_finite_float)
        if not isinstance(result, dict):
            raise PayloadError("Stored payload must be an object")
        return result
    except PayloadError:
        raise
    except (zlib.error, ValueError, TypeError, UnicodeError, RecursionError) as error:
        raise PayloadError("Stored payload cannot be decoded") from error
