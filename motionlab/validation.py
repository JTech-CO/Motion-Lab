"""Shared bounded validation for CLI, HTTP, and MCP arguments."""

import re
import unicodedata
from .analysis_schema import ANALYSIS_FILTERS

CATEGORIES = ("animation", "transition", "typography", "interaction", "background",
              "loader", "palette", "gradient", "shader", "reference", "pattern", "shape", "material")
KINDS = ("code", "palette", "reference", "image")
SEARCH_KEYS = frozenset({"query", "category", "license", "kind", "limit", "offset", *ANALYSIS_FILTERS})
ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,159}\Z")


class ValidationError(ValueError):
    """An invalid public argument; safe to return to the caller."""


def text_value(value, name, maximum, *, allow_empty=True):
    if not isinstance(value, str):
        raise ValidationError(f"{name} must be a string")
    value = unicodedata.normalize("NFC", value).strip()
    if len(value) > maximum or any(ord(c) < 32 for c in value):
        raise ValidationError(f"{name} exceeds its length limit or contains control characters")
    if not allow_empty and not value:
        raise ValidationError(f"{name} cannot be empty")
    return value


def bounded_int(value, name, lower, upper):
    if isinstance(value, bool) or not isinstance(value, int) or not lower <= value <= upper:
        raise ValidationError(f"{name} must be an integer from {lower} to {upper}")
    return value


def validate_search(arguments):
    if not isinstance(arguments, dict) or set(arguments) - SEARCH_KEYS:
        raise ValidationError("Search contains unsupported arguments")
    result = {
        "query": text_value(arguments.get("query", ""), "query", 240),
        "category": text_value(arguments.get("category", ""), "category", 32),
        "license": text_value(arguments.get("license", ""), "license", 120),
        "kind": text_value(arguments.get("kind", ""), "kind", 20),
        "limit": bounded_int(arguments.get("limit", 24), "limit", 1, 100),
        "offset": bounded_int(arguments.get("offset", 0), "offset", 0, 100_000),
    }
    if result["category"] and result["category"] not in CATEGORIES:
        raise ValidationError("category is not supported")
    if result["kind"] and result["kind"] not in KINDS:
        raise ValidationError("kind is not supported")
    for field, allowed in ANALYSIS_FILTERS.items():
        result[field] = text_value(arguments.get(field, ""), field, 32)
        if result[field] and result[field] not in allowed:
            raise ValidationError(f"{field} is not supported")
    return result


def validate_id(value):
    value = text_value(value, "id", 160, allow_empty=False)
    if not ID_RE.fullmatch(value):
        raise ValidationError("id has an unsupported format")
    return value
