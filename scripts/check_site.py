from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "static"

def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"FAIL: {message}")

home = (STATIC / "index.html").read_text(encoding="utf-8")
english_home = (STATIC / "en" / "index.html").read_text(encoding="utf-8")
app = (STATIC / "app.js").read_text(encoding="utf-8")
backend = (ROOT / "main.py").read_text(encoding="utf-8")
sitemap = (STATIC / "sitemap-pages.xml").read_text(encoding="utf-8")
api_config = (STATIC / "api-config.js").read_text(encoding="utf-8")

# Every visible homepage tool card must have exactly one registered tool handler.
cards = set(re.findall(r'data-tool="([^"]+)"', home))
meta_match = re.search(r"const toolMeta = \{([\s\S]*?)\n  \};", app)
require(meta_match is not None, "toolMeta registry is missing")
meta_block = meta_match.group(1)
meta = set()
for match in re.finditer(r"(?:^|,)\s*(?:'([^']+)'|([A-Za-z][A-Za-z0-9-]*))\s*:\s*\{", meta_block):
    meta.add(match.group(1) or match.group(2))
require(cards == meta, f"homepage cards and toolMeta differ; cards-only={sorted(cards-meta)}, registry-only={sorted(meta-cards)}")
require(len(cards) == 18, f"expected 18 core PDF tools, found {len(cards)}")

# All browser-side tools listed by the run button must have client-side handlers.
runner = re.search(r"const client=\[([^\]]+)\]", app)
require(runner is not None, "client-side tool dispatch list is missing")
client_tools = set(re.findall(r"'([^']+)'", runner.group(1)))
client_handler = re.search(r"async function runClientTool\(id\)\{([\s\S]*?)\n  async function extractPdfText", app)
require(client_handler is not None, "client-side tool function is missing")
for tool in client_tools:
    require(f"id==='{tool}'" in client_handler.group(1), f"client tool has no implementation branch: {tool}")

# Server-side tools and their corresponding API routes must be present.
server_fn = re.search(r"async function runServerTool\(id\)\{([\s\S]*?)\n  \$\('#runTool'\)", app)
require(server_fn is not None, "server-side tool function is missing")
server_body = server_fn.group(1)
expected_server = {"compress", "pdf-word", "word-pdf", "repair", "protect", "unlock", "translate"}
for tool in expected_server:
    require(f"id==='{tool}'" in server_body, f"server tool has no implementation branch: {tool}")
    require(tool in cards, f"server tool is not represented by a homepage card: {tool}")

for route in (
    "/api/pdf/compress", "/api/pdf/to-word", "/api/word/to-pdf",
    "/api/pdf/protect", "/api/pdf/unlock", "/api/pdf/repair",
    "/api/translate", "/api/translate/docx", "/api/health", "/api/languages",
):
    require(route in backend, f"backend route missing: {route}")

# The public frontend must point to the configured API host, never a secret-bearing URL.
require("https://pdf-globe.onrender.com" in api_config, "public API base URL is missing")
require("API_TOKEN" not in api_config and "SECRET" not in api_config, "a secret-like value must not be placed in api-config.js")

# Check that both homepages declare reciprocal language alternatives and their own canonicals.
for page, locale, canonical in (
    (home, "ar", "https://pdf-globe.pages.dev/"),
    (english_home, "en", "https://pdf-globe.pages.dev/en/"),
):
    require(f'<html lang="{locale}"' in page, f"{locale} homepage has the wrong document language")
    require(f'rel="canonical" href="{canonical}"' in page, f"{locale} homepage canonical is incorrect")
    require('hreflang="ar" href="https://pdf-globe.pages.dev/"' in page, f"{locale} homepage is missing the Arabic alternate")
    require('hreflang="en" href="https://pdf-globe.pages.dev/en/"' in page, f"{locale} homepage is missing the English alternate")
    for match in re.finditer(r'<script\b[^>]*src="([^"]+)"[^>]*>', page):
        tag = match.group(0)
        require('""' not in tag, f"malformed script tag: {tag}")
        require(re.search(r"\sdefer(?:\s|>)", tag) is not None, f"render-blocking external script found: {tag}")

require('id="apiStatus"' in home and 'id="apiStatus"' in english_home, "API availability status is missing from a homepage")
require("https://pdf-globe.pages.dev/en/" in sitemap, "English homepage is missing from sitemap")
require("applyLanguage(document.documentElement.lang || 'ar')" in app, "interface language does not follow the page locale")
require("window.location.assign('/en/')" in app and "window.location.assign('/')" in app, "Arabic/English language selection does not route to its crawlable page")
require("allowAuto&&translationSupportsAuto" in app, "translation auto-detect option is not restricted to supported providers")
require("translationSupportsAuto=String(data.translation_provider||'').startsWith('LibreTranslate')" in app, "translation auto-detect capability is not read from the API")

print(f"PASS: {len(cards)} homepage tools registered; {len(client_tools)} browser tools dispatched; {len(expected_server)} server tools mapped.")
print("PASS: API routes, public API configuration, Arabic/English homepages, hreflang, sitemap and deferred scripts.")
