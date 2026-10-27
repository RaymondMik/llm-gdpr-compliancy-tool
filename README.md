# gdpr-checker

Scans a website with Playwright, collects GDPR-relevant evidence (cookies set before consent,
third-party trackers, consent banner, privacy policy, forms) and asks an OpenAI model for a
compliance assessment printed straight to the terminal.

## Setup

```bash
uv sync
uv run playwright install chromium
cp .env.example .env   # then add your OPENAI_API_KEY
```

## Usage

```bash
uv run gdpr-checker https://example.com
```

Options:

| Flag | Purpose |
| --- | --- |
| `--model gpt-4.1` | pick a different OpenAI model (or set `GDPR_CHECKER_MODEL`) |
| `--show-evidence` | print the scraped evidence before the assessment |
| `--dry-run` | scan only, no LLM call |
| `--no-stream` | wait for the full answer instead of streaming |
| `--headful` | watch the browser while it scans |
| `--max-chars N` | cap page/policy text sent to the model (default 12000) |

## Layout

- `src/gdpr_checker/scraper.py` – Playwright evidence collection
- `src/gdpr_checker/prompts.py` – system prompt and user-prompt builder
- `src/gdpr_checker/analyzer.py` – OpenAI call (streaming)
- `src/gdpr_checker/cli.py` – command-line interface

The output is an automated technical assessment, not legal advice.
