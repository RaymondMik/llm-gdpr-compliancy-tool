"""Send the collected evidence to a local Ollama model and stream back the assessment.

The OpenAI Python SDK is used as the client, pointed at Ollama's OpenAI-compatible
endpoint (http://localhost:11434/v1 by default).
"""

from __future__ import annotations

import json
import os
import sys
from typing import Iterator
from urllib.error import URLError
from urllib.request import urlopen

from openai import OpenAI

from .prompts import SYSTEM_PROMPT, build_user_prompt
from .scraper import ScanResult

DEFAULT_OLLAMA_HOST = "http://localhost:11434"
DEFAULT_MODEL = "llama3.2"


def ollama_host() -> str:
    host = os.environ.get("OLLAMA_HOST", DEFAULT_OLLAMA_HOST).rstrip("/")
    if not host.startswith(("http://", "https://")):
        host = "http://" + host
    return host


def default_model() -> str:
    return os.environ.get("GDPR_CHECKER_MODEL", DEFAULT_MODEL)


def _ollama_models(host: str) -> list[str]:
    with urlopen(f"{host}/api/tags", timeout=5) as resp:  # noqa: S310 - local, user-configured host
        return [m["name"] for m in json.load(resp).get("models", [])]


def check_ollama(model: str) -> None:
    """Exit early with a helpful message if Ollama is not running or the model is missing."""
    host = ollama_host()
    try:
        models = _ollama_models(host)
    except (URLError, OSError, ValueError) as exc:
        sys.exit(
            f"Cannot reach Ollama at {host} ({exc}).\n"
            "Make sure Ollama is running (`ollama serve`, or start the desktop app), "
            "or set OLLAMA_HOST / --ollama-host to the right address."
        )
    if not any(name == model or name.split(":")[0] == model for name in models):
        available = ", ".join(models) or "none"
        sys.exit(
            f"Model '{model}' is not available in Ollama at {host}.\n"
            f"Pull it with `ollama pull {model}` or pick one with --model. Available: {available}"
        )


def _client() -> OpenAI:
    # Ollama ignores the API key but the SDK requires a non-empty value.
    return OpenAI(base_url=f"{ollama_host()}/v1", api_key="ollama", timeout=600)


def analyze(result: ScanResult, *, model: str | None = None, stream: bool = True) -> Iterator[str]:
    """Yield chunks of the assessment text as they arrive."""
    model = model or default_model()
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
