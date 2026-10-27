Scans a website with Playwright, collects GDPR-relevant evidence (cookies set before consent,
third-party trackers, consent banner, privacy policy, forms) and asks a local LLM for a
compliance assessment printed straight to the terminal. Nothing leaves your machine.

This tool is designed to work with **[Ollama](https://ollama.com)** and the **`llama3.2`** model.
Ollama must be running on your machine at its default address, `http://localhost:11434`,
before you run the checker.

## Disclaimer: this tool does not provide legal advice
It produces an automated *technical* assessment based on what a browser can observe
(cookies, network requests, page content). It cannot determine whether a website is actually
GDPR compliant, and its output must not be relied upon as a legal opinion. Consult a qualified
data-protection professional or lawyer for any compliance decision.

## Setup

```bash
uv sync
uv run playwright install chromium
```

### Ollama

1. Install Ollama from https://ollama.com.
2. Pull the `llama3.2` model:

   ```bash
   ollama pull llama3.2
   ```

3. Make sure Ollama is running before you start the checker, either via the desktop app
   or with `ollama serve` in a terminal. It must be reachable at the default
   `http://localhost:11434`. You can confirm with:

   ```bash
   curl http://localhost:11434/api/tags
   ```

The checker verifies that Ollama is reachable and that `llama3.2` is pulled before it
starts scanning, and prints what to do if either check fails.

Other Ollama models can be used with `--model`, and a non-default Ollama address with
`--ollama-host`, but `llama3.2` on `localhost:11434` is the supported configuration.

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
