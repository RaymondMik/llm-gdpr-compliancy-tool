"""Command-line entry point: `gdpr-checker https://example.com`."""

from __future__ import annotations

import argparse
import sys
from urllib.parse import urlparse

from dotenv import load_dotenv

from .analyzer import DEFAULT_MODEL, analyze, require_api_key
from .prompts import build_user_prompt
from .scraper import scan_website


def _normalise_url(raw: str) -> str:
    url = raw.strip()
    if not urlparse(url).scheme:
        url = "https://" + url
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        sys.exit(f"'{raw}' does not look like a valid website URL.")
    return url


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="gdpr-checker",
        description="Scan a website with Playwright and ask an LLM to assess its GDPR compliance.",
    )
    parser.add_argument("url", help="Full website URL, e.g. https://example.com")
    parser.add_argument("--model", default=DEFAULT_MODEL, help=f"OpenAI model to use (default: {DEFAULT_MODEL})")
    parser.add_argument("--max-chars", type=int, default=12_000, help="Max characters of page/policy text sent to the LLM")
    parser.add_argument("--no-stream", action="store_true", help="Wait for the full answer instead of streaming")
    parser.add_argument("--headful", action="store_true", help="Show the browser window while scanning")
    parser.add_argument("--show-evidence", action="store_true", help="Print the collected evidence before the assessment")
    parser.add_argument("--dry-run", action="store_true", help="Only scan and print the evidence; skip the LLM call")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    load_dotenv()
    args = _parse_args(argv)
    url = _normalise_url(args.url)
    if not args.dry_run:
        require_api_key()  # fail fast before spending time on the browser

    print(f"Scanning {url} ...", file=sys.stderr)
    try:
        result = scan_website(url, max_chars=args.max_chars, headless=not args.headful)
    except Exception as exc:  # noqa: BLE001
        sys.exit(f"Scan failed: {exc}")

    summary = (
        f"Scan done: {len(result.cookies_before_consent)} cookies, "
        f"{len(result.third_party_hosts)} third-party hosts, "
        f"{len(result.detected_trackers)} known trackers, "
        f"{len(result.forms)} forms, banner={'yes' if result.banner_text else 'no'}, "
        f"privacy policy={'found' if result.privacy_policy_text else 'not found'}"
    )
    print(summary, file=sys.stderr)
    for warning in result.warnings:
        print(f"  warning: {warning}", file=sys.stderr)

    if args.show_evidence or args.dry_run:
        print(build_user_prompt(result))
        if args.dry_run:
            return
        print("=" * 80)

    print(f"Asking {args.model} for an assessment ...\n", file=sys.stderr)
    try:
        for chunk in analyze(result, model=args.model, stream=not args.no_stream):
            print(chunk, end="", flush=True)
    except KeyboardInterrupt:
        sys.exit("\nInterrupted.")
    print()


if __name__ == "__main__":
    main()
