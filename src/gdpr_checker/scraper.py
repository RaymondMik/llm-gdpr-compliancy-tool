"""Collect GDPR-relevant evidence from a website using Playwright."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from urllib.parse import urljoin, urlparse

from playwright.sync_api import Browser, Page, Request, TimeoutError as PlaywrightTimeoutError, sync_playwright

# Patterns used to spot policy links, consent banners and well-known trackers.
POLICY_LINK_PATTERN = re.compile(
    r"\b(privacy|cookies?|gdpr|dsgvo|datenschutz|impressum|imprint|legal|terms|data[- ]?protection)\b",
    re.IGNORECASE,
)
MAX_POLICY_LINK_TEXT = 60  # longer anchor texts are headlines, not footer links
BANNER_SELECTOR = (
    "[id*='cookie' i], [class*='cookie' i], [id*='consent' i], [class*='consent' i], "
    "[id*='gdpr' i], [class*='gdpr' i], [aria-label*='cookie' i], [role='dialog']"
)
KNOWN_TRACKERS = {
    "google-analytics.com": "Google Analytics",
    "googletagmanager.com": "Google Tag Manager",
    "doubleclick.net": "Google Ads / DoubleClick",
    "googlesyndication.com": "Google AdSense",
    "facebook.net": "Meta Pixel",
    "facebook.com": "Meta",
    "connect.facebook.net": "Meta Pixel",
    "hotjar.com": "Hotjar",
    "clarity.ms": "Microsoft Clarity",
    "linkedin.com": "LinkedIn Insight",
    "licdn.com": "LinkedIn",
    "twitter.com": "X / Twitter",
    "ads-twitter.com": "X Ads",
    "tiktok.com": "TikTok Pixel",
    "segment.com": "Segment",
    "segment.io": "Segment",
    "mixpanel.com": "Mixpanel",
    "amplitude.com": "Amplitude",
    "hubspot.com": "HubSpot",
    "hs-scripts.com": "HubSpot",
    "intercom.io": "Intercom",
    "youtube.com": "YouTube embed",
    "fonts.googleapis.com": "Google Fonts (remote)",
    "fonts.gstatic.com": "Google Fonts (remote)",
    "cloudflareinsights.com": "Cloudflare Analytics",
    "matomo.cloud": "Matomo",
    "plausible.io": "Plausible",
    "chartbeat.com": "Chartbeat",
    "chartbeat.net": "Chartbeat",
    "optimizely.com": "Optimizely",
    "dotmetrics.net": "Dotmetrics",
    "tinypass.com": "Piano",
    "piano.io": "Piano",
    "privacy-mgmt.com": "Sourcepoint CMP",
    "cookielaw.org": "OneTrust CMP",
    "onetrust.com": "OneTrust CMP",
    "cookiebot.com": "Cookiebot CMP",
    "usercentrics.eu": "Usercentrics CMP",
    "adobedtm.com": "Adobe Launch",
    "demdex.net": "Adobe Audience Manager",
    "omtrdc.net": "Adobe Analytics",
    "criteo.com": "Criteo",
    "taboola.com": "Taboola",
    "outbrain.com": "Outbrain",
    "newrelic.com": "New Relic",
    "sentry.io": "Sentry",
}


@dataclass
class Cookie:
    name: str
    domain: str
    expires: float
    secure: bool
    http_only: bool
    same_site: str

    @property
    def is_session(self) -> bool:
        return self.expires in (-1, 0)


@dataclass
class Form:
    action: str
    method: str
    fields: list[str]
    has_checkbox: bool
    nearby_text: str


@dataclass
class ScanResult:
    requested_url: str
    final_url: str
    title: str
    uses_https: bool
    page_text: str
    cookies_before_consent: list[Cookie] = field(default_factory=list)
    third_party_hosts: list[str] = field(default_factory=list)
    detected_trackers: dict[str, str] = field(default_factory=dict)
    policy_links: dict[str, str] = field(default_factory=dict)
    banner_text: str = ""
    banner_buttons: list[str] = field(default_factory=list)
    forms: list[Form] = field(default_factory=list)
    privacy_policy_text: str = ""
    privacy_policy_url: str = ""
    warnings: list[str] = field(default_factory=list)


def _registrable_host(hostname: str) -> str:
    """Rough eTLD+1 so sub.example.co.uk and www.example.co.uk compare equal."""
    parts = hostname.lower().split(".")
    if len(parts) >= 3 and parts[-2] in {"co", "com", "org", "net", "gov", "ac", "edu"} and len(parts[-1]) == 2:
        return ".".join(parts[-3:])
    return ".".join(parts[-2:])


def _match_tracker(host: str) -> str | None:
    for domain, name in KNOWN_TRACKERS.items():
        if host == domain or host.endswith("." + domain):
            return name
    return None


def _collapse(text: str, limit: int) -> str:
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n", text).strip()
    if len(text) > limit:
        return text[:limit] + f"\n[... truncated, {len(text) - limit} more characters]"
    return text


def _extract_banner(page: Page) -> tuple[str, list[str]]:
    try:
        return page.evaluate(
            """(selector) => {
                const seen = new Set();
                let text = "";
                const buttons = [];
                for (const el of document.querySelectorAll(selector)) {
                    const style = getComputedStyle(el);
                    const rect = el.getBoundingClientRect();
                    const visible = style.display !== "none" && style.visibility !== "hidden"
                        && rect.width > 0 && rect.height > 0;
                    if (!visible) continue;
                    const t = (el.innerText || "").trim();
                    if (!t || seen.has(t) || t.length > 4000) continue;
                    // Skip the element if an ancestor is already captured.
                    let ancestorCaptured = false;
                    for (const s of seen) if (s.includes(t)) { ancestorCaptured = true; break; }
                    if (ancestorCaptured) continue;
                    seen.add(t);
                    text += t + "\\n---\\n";
                    for (const b of el.querySelectorAll("button, a, input[type=submit], input[type=button]")) {
                        const label = (b.innerText || b.value || b.getAttribute("aria-label") || "").trim();
                        if (label && !buttons.includes(label)) buttons.push(label);
                    }
                }
                return [text, buttons];
            }""",
            BANNER_SELECTOR,
        )
    except Exception:  # noqa: BLE001 - evaluation failures are non-fatal
        return "", []


def _extract_policy_links(page: Page, base_url: str) -> dict[str, str]:
    links: dict[str, str] = {}
    try:
        anchors = page.evaluate(
            "() => Array.from(document.querySelectorAll('a[href]')).map(a => [a.innerText.trim(), a.getAttribute('href')])"
        )
    except Exception:  # noqa: BLE001
        return links
    for text, href in anchors:
        if not href or href.startswith(("javascript:", "mailto:", "tel:", "#")):
            continue
        text = (text or "").split("\n", 1)[0].strip()
        text_matches = len(text) <= MAX_POLICY_LINK_TEXT and POLICY_LINK_PATTERN.search(text)
        href_matches = POLICY_LINK_PATTERN.search(urlparse(href).path.replace("-", " ").replace("_", " "))
        if text_matches or href_matches:
            label = text or href
            links.setdefault(label[:80], urljoin(base_url, href))
    return links


def _extract_forms(page: Page) -> list[Form]:
    try:
        raw = page.evaluate(
            """() => Array.from(document.querySelectorAll("form")).map(f => {
                const fields = Array.from(f.querySelectorAll("input, textarea, select"))
                    .filter(i => !["hidden", "submit", "button"].includes(i.type))
                    .map(i => `${i.type || i.tagName.toLowerCase()}:${i.name || i.id || i.placeholder || "?"}`);
                return {
                    action: f.getAttribute("action") || "",
                    method: (f.getAttribute("method") || "get").toLowerCase(),
                    fields,
                    has_checkbox: !!f.querySelector("input[type=checkbox]"),
                    nearby_text: (f.innerText || "").trim().slice(0, 400),
                };
            }).filter(f => f.fields.length > 0)"""
        )
    except Exception:  # noqa: BLE001
        return []
    return [Form(**item) for item in raw]


def _pick_privacy_policy_url(links: dict[str, str]) -> str:
    priority = ["privacy", "datenschutz", "data protection", "cookie", "legal"]
    for keyword in priority:
        for label, href in links.items():
            if keyword in label.lower() or keyword in href.lower():
                return href
    return ""


def _fetch_policy_text(browser: Browser, url: str, limit: int, warnings: list[str]) -> str:
    page = browser.new_page()
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=20_000)
        return _collapse(page.evaluate("() => document.body ? document.body.innerText : ''"), limit)
    except PlaywrightTimeoutError:
        warnings.append(f"Timed out loading privacy policy at {url}")
    except Exception as exc:  # noqa: BLE001
        warnings.append(f"Could not load privacy policy at {url}: {exc}")
    finally:
        page.close()
    return ""


def scan_website(url: str, *, max_chars: int = 12_000, headless: bool = True, timeout_ms: int = 30_000) -> ScanResult:
    """Load the URL in Chromium without interacting with any consent UI and gather evidence."""
    warnings: list[str] = []
    third_party_hosts: set[str] = set()
    site_host = _registrable_host(urlparse(url).hostname or "")

    def on_request(request: Request) -> None:
        host = urlparse(request.url).hostname
        if host and _registrable_host(host) != site_host:
            third_party_hosts.add(host)

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=headless)
        context = browser.new_context(
            locale="en-GB",
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
            ),
        )
        page = context.new_page()
        page.on("request", on_request)

        try:
            page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
        except PlaywrightTimeoutError:
            warnings.append("Page load hit the timeout; evidence may be incomplete.")
        try:
            page.wait_for_load_state("networkidle", timeout=10_000)
        except PlaywrightTimeoutError:
            warnings.append("Network never went idle; some requests may still be missing.")
        page.wait_for_timeout(1_500)  # let late-firing tag managers run

        final_url = page.url
        title = page.title()
        page_text = _collapse(page.evaluate("() => document.body ? document.body.innerText : ''"), max_chars)
        banner_text, banner_buttons = _extract_banner(page)
        policy_links = _extract_policy_links(page, final_url)
        forms = _extract_forms(page)

        cookies = [
            Cookie(
                name=c["name"],
                domain=c["domain"],
                expires=c.get("expires", -1),
                secure=c.get("secure", False),
                http_only=c.get("httpOnly", False),
                same_site=c.get("sameSite", "None"),
            )
            for c in context.cookies()
        ]

        privacy_url = _pick_privacy_policy_url(policy_links)
        privacy_text = _fetch_policy_text(browser, privacy_url, max_chars, warnings) if privacy_url else ""

        context.close()
        browser.close()

    trackers = {host: name for host in sorted(third_party_hosts) if (name := _match_tracker(host))}

    return ScanResult(
        requested_url=url,
        final_url=final_url,
        title=title,
        uses_https=final_url.startswith("https://"),
        page_text=page_text,
        cookies_before_consent=cookies,
        third_party_hosts=sorted(third_party_hosts),
        detected_trackers=trackers,
        policy_links=policy_links,
        banner_text=_collapse(banner_text, 3_000),
        banner_buttons=banner_buttons,
        forms=forms,
        privacy_policy_text=privacy_text,
        privacy_policy_url=privacy_url,
        warnings=warnings,
    )
