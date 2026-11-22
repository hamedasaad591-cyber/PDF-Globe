"""Live availability and SEO-route monitor for the public PDF Globe site.

Runs with the Python standard library only. It checks every URL currently
listed in the production sitemap, critical frontend assets, robots.txt, and
the deployed API health/capability manifest.
"""
from __future__ import annotations

import concurrent.futures
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

SITE_URL = "https://pdf-globe.pages.dev"
API_URL = "https://pdf-globe.onrender.com"
USER_AGENT = "PDF-Globe-Live-Monitor/1.0 (+https://github.com/hamedasaad591-cyber/PDF-Globe)"
TIMEOUT = 30
RETRIES = 4
RETRYABLE_STATUS = {429, 500, 502, 503, 504}
REQUIRED_CAPABILITIES = (
    "compress_pdf",
    "pdf_to_word",
    "pdf_to_excel",
    "pdf_to_powerpoint",
    "word_to_pdf",
    "excel_to_pdf",
    "powerpoint_to_pdf",
    "dicom_to_pdf",
    "image_conversion",
    "dwg_to_pdf",
    "protect_pdf",
    "unlock_pdf",
)


def fetch(url: str, timeout: int = TIMEOUT) -> tuple[int, bytes, str, float, str]:
    """GET a URL with bounded retries for transient CDN/server responses."""
    last_error = "unknown network error"
    for attempt in range(RETRIES):
        started = time.monotonic()
        request = urllib.request.Request(
            url,
            headers={
                "User-Agent": USER_AGENT,
                "Accept": "text/html,application/xml,text/plain,application/json,*/*",
                "Cache-Control": "no-cache",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                body = response.read(5 * 1024 * 1024 + 1)
                if len(body) > 5 * 1024 * 1024:
                    raise RuntimeError(f"Response exceeds 5 MB safety limit: {url}")
                elapsed = time.monotonic() - started
                return (
                    response.status,
                    body,
                    response.headers.get("Content-Type", "").lower(),
                    elapsed,
                    response.geturl(),
                )
        except urllib.error.HTTPError as exc:
            body = exc.read(2048)
            last_error = f"HTTP {exc.code}: {body[:200]!r}"
            if exc.code not in RETRYABLE_STATUS:
                return exc.code, body, exc.headers.get("Content-Type", "").lower(), time.monotonic() - started, exc.geturl()
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last_error = str(exc)[:250]
        if attempt < RETRIES - 1:
            time.sleep(min(2 ** attempt, 8))
    raise RuntimeError(f"Request failed after {RETRIES} attempts: {url} ({last_error})")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def check_page(url: str) -> tuple[str, float, int]:
    status, body, content_type, elapsed, final_url = fetch(url)
    require(status == 200, f"{url}: expected HTTP 200, received {status}")
    require("text/html" in content_type, f"{url}: expected HTML, received {content_type or 'unknown content type'}")
    require(body.strip(), f"{url}: empty response body")
    return url, elapsed, len(body)


def main() -> int:
    failures: list[str] = []
    checked_pages: list[tuple[str, float, int]] = []

    # Public homepage: language, title, canonical and indexability.
    for path, expected_lang, expected_canonical in (
        ("/", "ar", SITE_URL + "/"),
        ("/en/", "en", SITE_URL + "/en/"),
    ):
        url = SITE_URL + path
        try:
            status, body, content_type, elapsed, final_url = fetch(url)
            html = body.decode("utf-8", errors="replace")
            require(status == 200, f"{url}: expected HTTP 200, received {status}")
            require("text/html" in content_type, f"{url}: expected HTML, received {content_type}")
            require(re.search(r"<html\b[^>]*\blang=[\"']" + re.escape(expected_lang) + r"[\"']", html, re.I),
                    f"{url}: expected html lang={expected_lang}")
            require(re.search(r"<title>.*?PDF Globe.*?</title>", html, re.I | re.S),
                    f"{url}: PDF Globe title is missing")
            require(re.search(r'<link\b[^>]*rel=["\']canonical["\'][^>]*href=["\']' + re.escape(expected_canonical), html, re.I),
                    f"{url}: canonical URL is missing or incorrect")
            require(re.search(r'<meta\b[^>]*name=["\']robots["\'][^>]*content=["\']index,follow', html, re.I),
                    f"{url}: index/follow robots directive is missing")
            checked_pages.append((url, elapsed, len(body)))
            print(f"PASS homepage {expected_lang}: HTTP 200, title, canonical, language and indexability ({elapsed:.2f}s)")
        except Exception as exc:
            failures.append(str(exc))

    # robots.txt and the sitemap must be reachable through the public rewrite rules.
    try:
        status, body, content_type, elapsed, final_url = fetch(SITE_URL + "/robots.txt")
        robots = body.decode("utf-8", errors="replace")
        require(status == 200, f"/robots.txt: HTTP {status}")
        require("Sitemap: " + SITE_URL + "/sitemap.xml" in robots, "/robots.txt does not point to the public sitemap")
        print(f"PASS robots.txt rewrite and sitemap declaration ({elapsed:.2f}s)")
    except Exception as exc:
        failures.append(str(exc))

    urls: list[str] = []
    try:
        status, body, content_type, elapsed, final_url = fetch(SITE_URL + "/sitemap.xml")
        require(status == 200, f"/sitemap.xml: HTTP {status}")
        root = ET.fromstring(body)
        namespace = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        urls = [node.text.strip() for node in root.findall(".//sm:loc", namespace) if node.text and node.text.strip()]
        require(len(urls) >= 30, f"Sitemap unexpectedly contains only {len(urls)} URLs (expected at least 30)")
        require(len(urls) == len(set(urls)), "Sitemap contains duplicate URLs")
        require(SITE_URL + "/" in urls and SITE_URL + "/en/" in urls, "Sitemap is missing Arabic or English homepage")
        for item in urls:
            parsed = urllib.parse.urlparse(item)
            require(parsed.scheme == "https" and parsed.netloc == "pdf-globe.pages.dev",
                    f"Sitemap contains an off-domain or non-HTTPS URL: {item}")
        print(f"PASS public sitemap: {len(urls)} unique HTTPS URLs on the correct domain ({elapsed:.2f}s)")
    except Exception as exc:
        failures.append(str(exc))

    # Every public route advertised to search engines must resolve successfully.
    if urls:
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            futures = {pool.submit(check_page, url): url for url in urls}
            for future in concurrent.futures.as_completed(futures):
                url = futures[future]
                try:
                    checked_pages.append(future.result())
                except Exception as exc:
                    failures.append(str(exc))

    # Critical frontend files referenced by both language versions.
    for path, expected_type in (
        ("/style.css", "text/css"),
        ("/app.js", "javascript"),
        ("/api-config.js", "javascript"),
    ):
        url = SITE_URL + path
        try:
            status, body, content_type, elapsed, final_url = fetch(url)
            require(status == 200, f"{path}: HTTP {status}")
            require(expected_type in content_type, f"{path}: unexpected content type {content_type}")
            require(body, f"{path}: empty asset")
            checked_pages.append((url, elapsed, len(body)))
            print(f"PASS frontend asset {path}: HTTP 200, {content_type} ({elapsed:.2f}s)")
        except Exception as exc:
            failures.append(str(exc))

    # Public API health and feature manifest. Render's free instance may need a cold start.
    try:
        status, body, content_type, elapsed, final_url = fetch(API_URL + "/api/health", timeout=60)
        require(status == 200, f"API health: HTTP {status}")
        health = json.loads(body.decode("utf-8"))
        require(health.get("ok") is True, "API health did not report ok=true")
        capabilities = health.get("capabilities") or {}
        missing = [name for name in REQUIRED_CAPABILITIES if capabilities.get(name) is not True]
        require(not missing, "API is missing required capabilities: " + ", ".join(missing))
        print(f"PASS deployed API health and {len(REQUIRED_CAPABILITIES)} required capabilities ({elapsed:.2f}s)")
    except Exception as exc:
        failures.append(str(exc))

    if checked_pages:
        slowest = sorted(checked_pages, key=lambda item: item[1], reverse=True)[:5]
        print("SLOWEST CHECKED URLS:")
        for url, elapsed, size in slowest:
            print(f"  {elapsed:.2f}s  {size:>8} bytes  {url}")

    print(f"SUMMARY: {len(checked_pages)} page/asset URLs checked; {len(urls)} sitemap URLs discovered; {len(failures)} failure(s)")
    if failures:
        for failure in failures:
            print("FAIL:", failure, file=sys.stderr)
        return 1
    print("PASS ALL LIVE SITE MONITOR CHECKS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
