"""Validate literal find-and-replace values produced by the LLM or API."""

from __future__ import annotations

import re

from django.conf import settings

_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")

MAX_FIND_LENGTH = int(getattr(settings, "MAX_FIND_LENGTH", settings.MAX_REPLACEMENT_LENGTH))


class LiteralValidationError(ValueError):
    pass


def validate_find_value(value: str) -> str:
    cleaned = _CONTROL_CHARS.sub("", value)
    if not cleaned:
        raise LiteralValidationError("find value cannot be empty")
    if len(cleaned) > MAX_FIND_LENGTH:
        raise LiteralValidationError(f"find value exceeds {MAX_FIND_LENGTH} characters")
    return cleaned


def validate_literal_replacement(value: str) -> str:
    cleaned = _CONTROL_CHARS.sub("", value)
    if len(cleaned) > settings.MAX_REPLACEMENT_LENGTH:
        raise LiteralValidationError(
            f"replacement value exceeds {settings.MAX_REPLACEMENT_LENGTH} characters"
        )
    return cleaned


def validate_literal_pair(find_value: str, replacement_value: str) -> tuple[str, str]:
    find_clean = validate_find_value(find_value)
    replace_clean = validate_literal_replacement(replacement_value)
    if find_clean == replace_clean:
        raise LiteralValidationError("find and replacement values must differ")
    return find_clean, replace_clean


def escape_spark_literal_pattern(value: str) -> str:
    """Escape a literal string for use as the pattern in Spark regexp_replace."""
    return re.escape(value)


def escape_spark_replacement(value: str) -> str:
    """Escape replacement text so Spark does not treat $ as a backreference."""
    return value.replace("\\", "\\\\").replace("$", "\\$")
