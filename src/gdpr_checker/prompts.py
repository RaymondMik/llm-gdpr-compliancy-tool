"""System and user prompts for the GDPR assessment."""

from __future__ import annotations

from .scraper import ScanResult

SYSTEM_PROMPT = """\
You are a senior data-protection auditor specialising in the EU General Data Protection Regulation (GDPR) \
and the ePrivacy Directive as applied to websites. You review technical evidence collected by an automated \
scanner and produce a clear, practical compliance assessment.

Ground rules:
- Base every finding on the evidence provided. If evidence is missing or ambiguous, say so instead of guessing.
- Cookies and third-party requests were captured BEFORE any consent interaction. Non-essential cookies or \
trackers loaded at that point indicate a likely consent violation (Art. 6 GDPR, Art. 5(3) ePrivacy).
- Judge the consent banner against the requirements for valid consent (Art. 4(11), Art. 7 GDPR): freely given, \
specific, informed, unambiguous, and as easy to withdraw as to give. A "Reject all" option should be as \
prominent as "Accept all". Pre-ticked boxes or cookie walls are problematic.
- Check the privacy policy for the Art. 13 GDPR information duties: controller identity and contact details, \
DPO contact where applicable, purposes and legal bases, recipients and third-country transfers, retention \
periods, data-subject rights, right to lodge a complaint, and whether provision of data is mandatory.
- Forms collecting personal data need a legal basis and transparency; newsletter sign-ups need unbundled consent.
- Remote-loaded resources (e.g. Google Fonts, embedded videos) transfer the visitor's IP address to third parties \
and should be mentioned when seen.

Output format (Markdown, concise, no preamble):
1. **Overall verdict** - one of: Likely compliant / Partially compliant / Likely non-compliant, with a one-sentence reason.
2. **Key findings** - a bulleted list, each tagged [HIGH], [MEDIUM] or [LOW] risk, citing the relevant article where useful.
3. **What looks good** - brief bullets.
4. **Recommended actions** - prioritised, concrete steps.
5. **Limitations** - what this automated scan could not verify.

Finish with one line noting that this is an automated technical assessment and not legal advice.
"""


def _format_cookies(result: ScanResult) -> str:
    if not result.cookies_before_consent:
        return "None set."
    lines = []
    for c in result.cookies_before_consent:
        lifetime = "session" if c.is_session else "persistent"
        lines.append(
            f"- {c.name} (domain={c.domain}, {lifetime}, secure={c.secure}, httpOnly={c.http_only}, sameSite={c.same_site})"
        )
    return "\n".join(lines)


def _format_forms(result: ScanResult) -> str:
    if not result.forms:
        return "No forms with input fields found."
    lines = []
    for i, f in enumerate(result.forms, 1):
        lines.append(
            f"- Form {i}: method={f.method} action={f.action or '(same page)'} "
            f"fields={', '.join(f.fields)} consent_checkbox={f.has_checkbox}\n"
            f"  Text: {f.nearby_text!r}"
        )
    return "\n".join(lines)


def build_user_prompt(result: ScanResult) -> str:
    trackers = "\n".join(f"- {host} -> {name}" for host, name in result.detected_trackers.items()) or "None recognised."
    third_party = "\n".join(f"- {h}" for h in result.third_party_hosts) or "None."
    policy_links = "\n".join(f"- {label}: {href}" for label, href in result.policy_links.items()) or "None found."
    banner_buttons = ", ".join(result.banner_buttons) or "none"
    warnings = "\n".join(f"- {w}" for w in result.warnings) or "None."

    return f"""\
Assess the GDPR compliance of the website below using only this evidence.

## Page
- Requested URL: {result.requested_url}
- Final URL: {result.final_url}
- Title: {result.title}
- HTTPS: {result.uses_https}

## Cookies set before any consent interaction
{_format_cookies(result)}

## Third-party hosts contacted before any consent interaction
{third_party}

## Recognised trackers / third-party services
{trackers}

## Consent banner (visible elements matching cookie/consent selectors)
Buttons: {banner_buttons}
Text:
{result.banner_text or "No consent banner detected."}

## Privacy / legal links found
{policy_links}

## Forms on the page
{_format_forms(result)}

## Privacy policy text ({result.privacy_policy_url or "not found"})
{result.privacy_policy_text or "Not retrieved."}

## Visible page text (truncated)
{result.page_text}

## Scanner warnings
{warnings}
"""
