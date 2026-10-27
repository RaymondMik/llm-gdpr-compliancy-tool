# gdpr-checker

Scans a website with Playwright, collects GDPR-relevant evidence (cookies set before consent,
third-party trackers, consent banner, privacy policy, forms) and asks an LLM for a
compliance assessment printed straight to the terminal.

By default it uses a **local model through Ollama**, so nothing leaves your machine.
The hosted OpenAI API is available as an alternative backend.

## Setup

```bash
uv sync
uv run playwright install chromium
```

### Option A: local model with Ollama (default)

1. Install Ollama from https://ollama.com and make sure it is running
   (the desktop app, or `ollama serve` in a terminal). It listens on
   `http://localhost:11434` by default.
2. Pull a model, for example:

   ```bash
   ollama pull llama3.2
   ```

The tool checks that Ollama is reachable and the model is pulled before it starts scanning,
and tells you what to do if not.

### Option B: OpenAI API

```bash
cp .env.example .env   # set GDPR_CHECKER_PROVIDER=openai and your OPENAI_API_KEY
```

## Usage

```bash
uv run gdpr-checker https://example.com
```

Options:

| Flag | Purpose |
| --- | --- |
| `--provider ollama\|openai` | LLM backend (default `ollama`, or set `GDPR_CHECKER_PROVIDER`) |
| `--model NAME` | model to use; defaults to `llama3.2` for Ollama and `gpt-4.1-mini` for OpenAI (or set `GDPR_CHECKER_MODEL`) |
| `--ollama-host URL` | Ollama base URL if not on the default port (or set `OLLAMA_HOST`) |
| `--show-evidence` | print the scraped evidence before the assessment |
| `--dry-run` | scan only, no LLM call |
| `--no-stream` | wait for the full answer instead of streaming |
| `--headful` | watch the browser while it scans |
| `--max-chars N` | cap page/policy text sent to the model (default 12000) |

Examples:

```bash
uv run gdpr-checker https://example.com --model phi3
uv run gdpr-checker https://example.com --provider openai --model gpt-4.1
uv run gdpr-checker https://example.com --dry-run --show-evidence
```

## Layout

- `src/gdpr_checker/scraper.py` – Playwright evidence collection
- `src/gdpr_checker/prompts.py` – system prompt and user-prompt builder
- `src/gdpr_checker/analyzer.py` – provider selection, Ollama pre-flight check, streamed Chat Completions call
- `src/gdpr_checker/cli.py` – command-line interface

Small local models can produce inconsistent verdicts (e.g. "likely compliant" next to a HIGH-risk finding).
A larger model such as `llama3.1:8b` or an OpenAI model gives more reliable results.

The output is an automated technical assessment, not legal advice.
