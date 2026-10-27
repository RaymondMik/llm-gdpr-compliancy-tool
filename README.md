# gdpr-checker

Scans a website with Playwright, collects GDPR-relevant evidence (cookies set before consent,
third-party trackers, consent banner, privacy policy, forms) and asks a **local LLM running in
Ollama** for a compliance assessment printed straight to the terminal. Nothing leaves your machine.

## Setup

```bash
uv sync
uv run playwright install chromium
```

### Ollama

1. Install Ollama from https://ollama.com and make sure it is running
   (the desktop app, or `ollama serve` in a terminal). It listens on
   `http://localhost:11434` by default.
2. Pull a model, for example:

   ```bash
   ollama pull llama3.2
   ```

The tool checks that Ollama is reachable and the model is pulled before it starts scanning,
and tells you what to do if not.

## Usage

```bash
uv run gdpr-checker https://example.com
```

Options:

| Flag | Purpose |
| --- | --- |
| `--model NAME` | Ollama model to use (default `llama3.2`, or set `GDPR_CHECKER_MODEL`) |
| `--ollama-host URL` | Ollama base URL if not on the default port (or set `OLLAMA_HOST`) |
| `--show-evidence` | print the scraped evidence before the assessment |
| `--dry-run` | scan only, no LLM call |
| `--no-stream` | wait for the full answer instead of streaming |
| `--headful` | watch the browser while it scans |
| `--max-chars N` | cap page/policy text sent to the model (default 12000) |

Examples:

```bash
uv run gdpr-checker https://example.com --model phi3
uv run gdpr-checker https://example.com --model llama3.1:8b --no-stream
uv run gdpr-checker https://example.com --dry-run --show-evidence
```

## Layout

- `src/gdpr_checker/scraper.py` – Playwright evidence collection
- `src/gdpr_checker/prompts.py` – system prompt and user-prompt builder
- `src/gdpr_checker/analyzer.py` – Ollama pre-flight check and streamed Chat Completions call (OpenAI SDK pointed at Ollama)
- `src/gdpr_checker/cli.py` – command-line interface

Small local models can produce inconsistent verdicts (e.g. "likely compliant" next to a HIGH-risk finding).
A larger model such as `llama3.1:8b` gives more reliable results.

The output is an automated technical assessment, not legal advice.
