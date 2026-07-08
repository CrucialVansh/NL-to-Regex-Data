"""Shared OpenAI client used by Celery tasks."""

import os

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

_client = None


def get_openai_client() -> OpenAI:
    """Return a process-wide OpenAI client (created once per worker)."""
    global _client
    if _client is None:
        _client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    return _client
