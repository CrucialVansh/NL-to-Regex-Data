"""Validate LLM-generated regex patterns before Spark execution."""

from __future__ import annotations

import re

MAX_REGEX_LENGTH = 500
_NESTED_QUANTIFIERS = re.compile(r"\([^)]*[+*][^)]*\)[+*{]")
# Spark regexp_replace does not support lookaround assertions.
_DANGEROUS_LOOKAROUNDS = re.compile(r"\(\?[<=!]")


class RegexValidationError(ValueError):
    pass


def validate_regex_pattern(pattern: str) -> str:
    cleaned = pattern.strip()
    if not cleaned:
        raise RegexValidationError("Generated regex pattern is empty")
    if len(cleaned) > MAX_REGEX_LENGTH:
        raise RegexValidationError(
            f"Generated regex exceeds maximum length of {MAX_REGEX_LENGTH} characters"
        )
    if cleaned.startswith("(") and cleaned.endswith(")") and cleaned.count("(") == 1:
        # Drop a single outer capturing group wrapper from the model output.
        cleaned = cleaned[1:-1]

    try:
        re.compile(cleaned)
    except re.error as exc:
        raise RegexValidationError(f"Invalid regex syntax: {exc}") from exc

    if _NESTED_QUANTIFIERS.search(cleaned):
        raise RegexValidationError(
            "Regex contains nested quantifiers that may cause catastrophic backtracking"
        )
    if _DANGEROUS_LOOKAROUNDS.search(cleaned):
        raise RegexValidationError("Regex lookaround assertions are not supported")

    return cleaned
