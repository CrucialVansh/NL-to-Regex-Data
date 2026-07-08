"""Validate and sanitise natural-language job inputs."""

from __future__ import annotations

import re

from django.conf import settings

_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
# Basic prompt-injection phrases to reject before sending text to the LLM.
_PROMPT_INJECTION_PATTERNS = (
    re.compile(r"(?i)ignore\s+(all\s+)?(previous|prior)\s+instructions"),
    re.compile(r"(?i)system\s*:"),
    re.compile(r"(?i)you\s+are\s+now"),
)


class InputValidationError(ValueError):
    pass


def validate_natural_language_prompt(prompt: str) -> str:
    cleaned = _CONTROL_CHARS.sub("", prompt).strip()
    if not cleaned:
        raise InputValidationError("natural_language_prompt cannot be empty")
    if len(cleaned) > settings.MAX_NL_PROMPT_LENGTH:
        raise InputValidationError(
            f"natural_language_prompt exceeds {settings.MAX_NL_PROMPT_LENGTH} characters"
        )
    for pattern in _PROMPT_INJECTION_PATTERNS:
        if pattern.search(cleaned):
            raise InputValidationError("natural_language_prompt contains disallowed instructions")
    return cleaned


def validate_replacement_value(value: str) -> str:
    cleaned = _CONTROL_CHARS.sub("", value).strip()
    if not cleaned:
        raise InputValidationError("replacement_value cannot be empty")
    if len(cleaned) > settings.MAX_REPLACEMENT_LENGTH:
        raise InputValidationError(
            f"replacement_value exceeds {settings.MAX_REPLACEMENT_LENGTH} characters"
        )
    return cleaned
