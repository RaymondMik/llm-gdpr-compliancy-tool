"""Send the collected evidence to the LLM and stream back the assessment."""

from __future__ import annotations

import os
import sys
from typing import Iterator

from openai import OpenAI

from .prompts import SYSTEM_PROMPT, build_user_prompt
from .scraper import ScanResult

DEFAULT_MODEL = os.environ.get("GDPR_CHECKER_MODEL", "gpt-4.1-mini")


def require_api_key() -> None:
    if not os.environ.get("OPENAI_API_KEY"):
        sys.exit("OPENAI_API_KEY is not set. Put it in a .env file or export it in your shell.")


def _client() -> OpenAI:
    require_api_key()
    return OpenAI()


def analyze(result: ScanResult, *, model: str = DEFAULT_MODEL, stream: bool = True) -> Iterator[str]:
    """Yield chunks of the assessment text as they arrive."""
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": build_user_prompt(result)},
    ]
    client = _client()

    if stream:
        with client.chat.completions.stream(model=model, messages=messages, temperature=0.2) as events:
            for event in events:
                if event.type == "content.delta":
                    yield event.delta
    else:
        response = client.chat.completions.create(model=model, messages=messages, temperature=0.2)
        yield response.choices[0].message.content or ""
