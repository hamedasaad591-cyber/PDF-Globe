from pathlib import Path
import re
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "static"

def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"FAIL: {message}")

home = (STATIC / "index.html").read_text(encoding="utf-8")
english_home = (STATIC / "en" / "index.html").read_text(encoding="utf-8")
app = (STATIC / "app.js").read_text(encoding="utf-8")
backend = (ROOT / "main.py").read_text(encoding="utf-8")
sitemap = (STATIC / "sitemap.xml").read_text(encoding="utf-8")
robots = (STATIC / "robots.txt").read_text(encoding="utf-8")
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
require(len(cards) == 22, f"expected 22 registered homepage tools, found {len(cards)}")

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
expected_server = {"compress", "pdf-word", "word-pdf", "image-pdf", "repair", "protect", "unlock", "translate", "excel-pdf", "powerpoint-pdf", "dicom-pdf", "dwg-pdf"}
for tool in expected_server:
    require(f"id==='{tool}'" in server_body, f"server tool has no implementation branch: {tool}")
    require(tool in cards, f"server tool is not represented by a homepage card: {tool}")

require("X-PDF-Globe-Compression-Result" in backend and "X-PDF-Globe-Original-Bytes" in backend and "X-PDF-Globe-Output-Bytes" in backend, "PDF compression result and size headers are missing")
require("pdfGlobeCompression" in app and "compress_unchanged" in app, "PDF compression result is not explained in the UI")
require("app.js?v=20261123-api-wake-retry-1" in home and "app.js?v=20261123-api-wake-retry-1" in english_home, "PDF compression UI cache tag is stale")

office_backend = (ROOT / "office_conversion.py").read_text(encoding="utf-8")
image_backend = (ROOT / "image_conversion.py").read_text(encoding="utf-8")
dicom_backend = (ROOT / "dicom_conversion.py").read_text(encoding="utf-8")
dwg_backend = (ROOT / "dwg_conversion.py").read_text(encoding="utf-8")
for route in (
    "/api/pdf/compress", "/api/pdf/to-word", "/api/word/to-pdf",
    "/api/pdf/protect", "/api/pdf/unlock", "/api/pdf/repair",
    "/api/translate", "/api/translate/docx", "/api/health", "/api/languages",
):
    require(route in backend, f"backend route missing: {route}")
for route, source in (
    ("/api/office/excel-to-pdf", office_backend),
    ("/api/office/powerpoint-to-pdf", office_backend),
    ("/api/image/convert", image_backend),
    ("/api/dicom/to-pdf", dicom_backend),
    ("/api/cad/dwg-to-pdf", dwg_backend),
):
    require(route in source, f"specialized converter route missing: {route}")
require("register_office_routes(app" in backend and "register_image_routes(app" in backend, "converter route registration is missing")
require("register_dicom_routes(app" in backend and "register_dwg_routes(app" in backend, "specialized route registration is missing")
require("--disable-bindings --disable-docs --disable-write --disable-json" in (ROOT / "Dockerfile").read_text(encoding="utf-8"), "DWG builder still compiles unused bindings/docs/write/JSON support")
require("BackgroundPolicy.WHITE" in dwg_backend, "DWG PDF export is not configured for a white print background")

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
sitemap_root = ET.fromstring(sitemap)
sitemap_urls = [
    element.text.strip()
    for element in sitemap_root.iter()
    if element.tag.endswith("loc") and element.text
]
require(sitemap_root.tag.endswith("urlset"), "Public sitemap root element is not urlset")
require(len(sitemap_urls) >= 30, f"Expected at least 30 sitemap URLs, found {len(sitemap_urls)}")
require(len(sitemap_urls) == len(set(sitemap_urls)), "Public sitemap contains duplicate URLs")
require(all(url.startswith("https://pdf-globe.pages.dev/") for url in sitemap_urls),
        "Public sitemap contains a URL outside the canonical site origin")
require("Sitemap: https://pdf-globe.pages.dev/sitemap.xml" in robots,
        "robots.txt does not reference the direct public sitemap URL")
require("Disallow: /" not in robots, "robots.txt blocks the entire site")
require("applyLanguage(document.documentElement.lang || 'ar')" in app, "interface language does not follow the page locale")
require("window.location.assign('/en/')" in app and "window.location.assign('/')" in app, "Arabic/English language selection does not route to its crawlable page")
require("incoming.find" in app, "upload extension validation is missing")
require("function refreshTranslationOptions()" in app and "selectedSource=" in app, "translation option refresh does not preserve selected source language")
require("capabilities" in backend, "API health does not expose backend capabilities")
require("translation_provider" in backend, "API health does not expose the active translation provider")
require("allowAuto&&translationSupportsAuto" in app, "translation auto-detect option is not restricted to supported providers")
require("translationSupportsAuto=String(data.translation_provider||'').startsWith('LibreTranslate')" in app, "translation auto-detect capability is not read from the API")

# The independent unit-conversion tool must be discoverable, localized and local-only.
unit_ar = (STATIC / "unit-converter.html").read_text(encoding="utf-8")
unit_en = (STATIC / "en" / "unit-converter.html").read_text(encoding="utf-8")
unit_js = (STATIC / "unit-converter.js").read_text(encoding="utf-8")
unit_css = (STATIC / "unit-converter.css").read_text(encoding="utf-8")
sitemap_all = (STATIC / "sitemap.xml").read_text(encoding="utf-8")
require('data-static-tool="true"' in home and 'href="/unit-converter.html"' in home, "Arabic homepage unit converter card is missing")
require('data-static-tool="true"' in english_home and 'href="/en/unit-converter.html"' in english_home, "English homepage unit converter card is missing")
require('tool_units:' in app and 'desc_units:' in app, "unit converter homepage localization is missing")
for page, locale, canonical in (
    (unit_ar, "ar", "https://pdf-globe.pages.dev/unit-converter.html"),
    (unit_en, "en", "https://pdf-globe.pages.dev/en/unit-converter.html"),
):
    require(f'<html lang="{locale}"' in page, f"{locale} unit-converter page has the wrong locale")
    require(f'rel="canonical" href="{canonical}"' in page, f"{locale} unit-converter canonical is incorrect")
    require('unit-converter.js?v=' in page and ' defer></script>' in page, f"{locale} unit-converter JavaScript is missing or not deferred")
    require('hreflang="ar"' in page and 'hreflang="en"' in page, f"{locale} unit-converter page is missing language alternates")
require("INGREDIENTS" in unit_js and "recipeUnitOptions" in unit_js, "ingredient-based cooking and recipe calculator are missing")
require(all(x in unit_js for x in ("temperature", "pressure", "energy", "data", "area", "speed")), "unit-converter categories are incomplete")
require("fetch(" not in unit_js and "XMLHttpRequest" not in unit_js, "unit converter should not transmit values to a server")
require("unit-converter.html" in sitemap and "unit-converter.html" in sitemap_all, "unit converter pages are missing from a sitemap")
require('.field[hidden]{display:none!important}' in unit_css, "non-cooking ingredient selector visibility rule is missing")

# Image compression/resizing is a separate browser-only tool.
image_ar = (STATIC / "image-compressor.html").read_text(encoding="utf-8")
image_en = (STATIC / "en" / "image-compressor.html").read_text(encoding="utf-8")
image_js = (STATIC / "image-compressor.js").read_text(encoding="utf-8")
image_css = (STATIC / "image-compressor.css").read_text(encoding="utf-8")
image_section_ar = re.search(r'<section class="directory-group" id="image-tools" data-tool-group>([\s\S]*?)</section>', home)
image_section_en = re.search(r'<section class="directory-group" id="image-tools" data-tool-group>([\s\S]*?)</section>', english_home)
require(image_section_ar is not None and image_section_ar.group(1).count('class="tool-card directory-tool-card"') == 4, "Arabic image tools section must contain four separate cards")
require(image_section_en is not None and image_section_en.group(1).count('class="tool-card directory-tool-card"') == 4, "English image tools section must contain four separate cards")
for mode in ("convert", "resize", "compress", "enhance"):
    require(f'href="/image-compressor.html?mode={mode}"' in image_section_ar.group(1), f"Arabic image mode card is missing: {mode}")
    require(f'href="/en/image-compressor.html?mode={mode}"' in image_section_en.group(1), f"English image mode card is missing: {mode}")
require('tool_imagecompress:' in app and 'desc_imagecompress:' in app, "image compressor homepage localization is missing")
for page, locale, canonical in (
    (image_ar, "ar", "https://pdf-globe.pages.dev/image-compressor.html"),
    (image_en, "en", "https://pdf-globe.pages.dev/en/image-compressor.html"),
):
    require(f'<html lang="{locale}"' in page, f"{locale} image compressor page has the wrong locale")
    require(f'rel="canonical" href="{canonical}"' in page, f"{locale} image compressor canonical is incorrect")
    require('image-compressor.js?v=' in page and ' defer></script>' in page, f"{locale} image compressor script is missing or not deferred")
    require('hreflang="ar"' in page and 'hreflang="en"' in page, f"{locale} image compressor page is missing language alternates")
require("/api/image/convert" in image_js, "image compressor does not call the image conversion API")
require("new FormData()" in image_js and "form.append(" in image_js, "image compressor does not submit image files to the server")
require("output_format" in image_js and "sharpen" in image_js and "brightness" in image_js, "image processing controls are not wired to the API")
require("مؤقت" in image_js or "Temporary" in image_js, "image converter upload behavior is not disclosed")
require("function invalidateResults()" in image_js, "image compressor must clear stale results when settings change")
require("image-compressor.html" in sitemap and "image-compressor.html" in sitemap_all, "image compressor pages are missing from a sitemap")
require("grid-template-columns:1fr" in image_css, "image compressor mobile layout is missing")

print(f"PASS: {len(cards)} homepage tools registered; {len(client_tools)} browser tools dispatched; {len(expected_server)} server tools mapped.")
print("PASS: API routes, public API configuration, Arabic/English homepages, hreflang, sitemap and deferred scripts.")


# PDF to Excel and PowerPoint are independent bilingual tools backed by real API routes.
requirements_text = (ROOT / "requirements.txt").read_text(encoding="utf-8")
require("openpyxl==" in requirements_text and "python-pptx==" in requirements_text, "Excel/PowerPoint conversion dependencies are missing")
require('@app.post("/api/pdf/to-excel")' in backend and "page.find_tables" in backend, "PDF to Excel table extraction route is missing")
require('@app.post("/api/pdf/to-powerpoint")' in backend and "Presentation()" in backend and "add_picture" in backend, "PDF to PowerPoint route is missing")
for locale, prefix, excel_url, ppt_url in (
    ("ar", "", "/pdf-to-excel.html", "/pdf-to-powerpoint.html"),
    ("en", "en/", "/en/pdf-to-excel.html", "/en/pdf-to-powerpoint.html"),
):
    home_page = (STATIC / (prefix + "index.html")).read_text(encoding="utf-8")
    grid_match = re.search(r'<div class="tool-grid" id="toolGrid">([\s\S]*?)</div>', home_page)
    require(grid_match is not None, f"{locale} homepage tool grid is missing")
    grid = grid_match.group(1)
    require(f'href="{excel_url}"' in grid and f'href="{ppt_url}"' in grid, f"{locale} homepage Excel/PowerPoint cards are missing from the tool grid")
    require('id="pdf-tools"' in home_page and 'id="image-tools"' in home_page, f"{locale} homepage directory sections are missing")
    require(f'href="/{prefix}image-compressor.html?mode=convert"' in home_page and f'href="/{prefix}unit-converter.html"' in home_page, f"{locale} image or unit utility link is missing")
    require('category-jump-grid' in home_page and 'directory-search' in home_page, f"{locale} directory navigation or global search is missing")
    for filename, url, kind in (
        ("pdf-to-excel.html", excel_url, "excel"),
        ("pdf-to-powerpoint.html", ppt_url, "powerpoint"),
    ):
        page = (STATIC / prefix / filename).read_text(encoding="utf-8")
        canonical = "https://pdf-globe.pages.dev" + url
        require(f'<html lang="{locale}"' in page, f"{locale} {kind} page has the wrong locale")
        require(f'rel="canonical" href="{canonical}"' in page, f"{locale} {kind} canonical is incorrect")
        require(f'data-converter="{kind}"' in page and "office-converter.js?v=" in page, f"{locale} {kind} converter wiring is missing")
        require('id="fileInput"' in page and 'id="convertButton"' in page, f"{locale} {kind} upload controls are missing")
        require('hreflang="ar"' in page and 'hreflang="en"' in page, f"{locale} {kind} language alternates are missing")
        require(canonical in sitemap and canonical in sitemap_all, f"{locale} {kind} page is missing from a sitemap")
office_js = (STATIC / "office-converter.js").read_text(encoding="utf-8")
office_css = (STATIC / "office-converter.css").read_text(encoding="utf-8")
require("/api/pdf/to-excel" in office_js and "/api/pdf/to-powerpoint" in office_js, "office converter frontend endpoints are missing")
require("FormData" in office_js and "application/pdf" in office_js, "office converter frontend does not upload PDF files")
require("office-drop" in office_css and "@media" in office_css, "office converter responsive styles are missing")
print("PASS: PDF to Excel and PDF to PowerPoint routes, bilingual pages, homepage cards and sitemap entries.")


# The homepage directory is organized into clear tool categories in both locales.
for locale, prefix in (("ar", ""), ("en", "en/")):
    page = (STATIC / prefix / "index.html").read_text(encoding="utf-8")
    for category_id in ("pdf-tools", "print-tools", "poster-tools", "measure-tools", "translation-tools", "image-tools"):
        require(f'id="{category_id}" data-tool-group' in page, f"{locale} homepage is missing directory group {category_id}")
    require('id="toolSearch"' in page and 'id="noResults"' in page, f"{locale} homepage global tool search is missing")
    require(page.count('class="category-jump-card"') == 7, f"{locale} homepage should expose seven category shortcuts")
    require(page.count('data-tool="') == 22, f"{locale} homepage tools are duplicated or missing")
    require('href="/saffha/"' in page and 'href="/poster-splitter.html"' in page, f"{locale} handout or poster tool link is missing")
require("directory-group" in (STATIC / "style.css").read_text(encoding="utf-8"), "Homepage directory styles are missing")
require("$('#categories').addEventListener" not in app, "Old category filter is still wired to the removed category strip")
require("data-tool-group" in app and "visibleCount" in app, "Global search does not show/hide directory groups")


# Homepage illustrated navigation: never ship blank category labels or icon-less cards.
icons_file = (STATIC / "tool-icons.svg").read_text(encoding="utf-8")
for icon_id in ("merge", "split", "compress", "pdf-word", "pdf-excel", "pdf-powerpoint",
                "saffha", "poster", "units", "ocr", "translate", "image-compress",
                "wm-pdf", "wm-print", "wm-poster", "wm-units", "wm-translate", "wm-image",
                "wm-special", "excel-pdf", "powerpoint-pdf", "dicom-pdf", "dwg-pdf"):
    require(f'<symbol id="{icon_id}"' in icons_file, f"homepage illustration {icon_id} is missing")
for locale, prefix in (("ar", ""), ("en", "en/")):
    page = (STATIC / prefix / "index.html").read_text(encoding="utf-8")
    require('app.js?v=20261123-api-wake-retry-1' in page, f"{locale} homepage JS cache version was not refreshed")
    require('style.css?v=20261123-mobile-layout-2' in page, f"{locale} homepage CSS cache version was not refreshed")
    for key in ("jump_pdf", "jump_print", "jump_poster", "jump_measure", "jump_translate", "jump_image"):
        require(re.search(rf'<b data-i18n="{key}">\s*[^<]+\s*</b>', page) is not None,
                f"{locale} homepage category label {key} has no HTML fallback text")
    require(page.count('<span class="tool-icon ') == 31, f"{locale} homepage does not contain 28 tool illustration slots")
    require(page.count('<use href="/tool-icons.svg#') >= 30, f"{locale} homepage category or tool illustrations are missing")
require("Illustrated tool directory" in (STATIC / "style.css").read_text(encoding="utf-8"),
        "Illustrated homepage tool directory styles are missing")


# The expanded image studio must expose real server-backed formats and controls.
image_page_ar = (STATIC / "image-compressor.html").read_text(encoding="utf-8")
image_page_en = (STATIC / "en" / "image-compressor.html").read_text(encoding="utf-8")
image_js = (STATIC / "image-compressor.js").read_text(encoding="utf-8")
image_backend = (ROOT / "image_conversion.py").read_text(encoding="utf-8")
for locale, page in (("ar", image_page_ar), ("en", image_page_en)):
    for control in ("outputFormat", "width", "height", "keepAspect", "quality", "sharpen", "contrast", "brightness", "background"):
        require(f'id="{control}"' in page, f"{locale} image converter control is missing: {control}")
    require('image-compressor.js?v=20261121-image-tools-4' in page, f"{locale} image converter JS cache tag is stale")
    require("api-config.js" in page, f"{locale} image converter API configuration is missing")
require("/api/image/convert" in image_js, "image studio does not call the image conversion API")
for fmt in ("webp", "jpeg", "png", "avif", "heic", "bmp", "gif", "tiff", "ico", "pdf"):
    require(f'"{fmt}"' in image_backend or f"'{fmt}'" in image_backend, f"image output format is missing: {fmt}")
requirements_text = (ROOT / "requirements.txt").read_text(encoding="utf-8")
for dependency in ("pydicom==", "pillow-heif==", "Pillow==13.0.0", "ezdxf=="):
    require(dependency in requirements_text, f"backend dependency is missing: {dependency}")
print("PASS: Excel/PowerPoint to PDF, DICOM/DWG routes, and extended image conversion controls.")

for page in (home, english_home):
    require("<strong>31</strong>" in page, "homepage tool count must reflect 31 available tools")


# NodeList iteration must use querySelectorAll ($$ helper), not querySelector ($).
for selector in ('.mobile-menu-panel a', '.tool-card', '.tool-subgroup', '[data-tool-group]'):
    escaped = re.escape(selector)
    pattern = rf"(?<!\\$)\\$\\(\\s*['\\\"]{escaped}['\\\"](?:\\s*,\\s*mobileMenu)?\\s*\\)\\.forEach"
    require(re.search(pattern, app) is None, f"single Element used with forEach for selector {selector}")
for selector in ("$$('.mobile-menu-panel a', mobileMenu).forEach", "$$('.tool-card').forEach", "$$('.tool-subgroup').forEach", "$$('[data-tool-group]').forEach"):
    require(selector in app, f"querySelectorAll iteration missing: {selector}")
require("$$('.tool-card[data-tool]').forEach" in app, "homepage tool card click handlers are not registered")


# The image section exposes four distinct, query-configured workflows.
for locale, prefix in (("ar", ""), ("en", "en/")):
    page = (STATIC / prefix / "index.html").read_text(encoding="utf-8")
    section = re.search(r'<section class="directory-group" id="image-tools" data-tool-group>([\s\S]*?)</section>', page)
    require(section is not None, f"{locale} image section is missing")
    image_section = section.group(1)
    for mode in ("convert", "resize", "compress", "enhance"):
        require(f"image-compressor.html?mode={mode}" in image_section, f"{locale} image task is missing: {mode}")
    require(image_section.count('class="tool-card directory-tool-card"') == 4, f"{locale} image section must show four independent cards")
for mode in ("convert", "resize", "compress", "enhance"):
    require(f"'{mode}'" in image_js, f"image task mode is not supported: {mode}")
require("function configureMode()" in image_js and "MODE_COPY[MODE]" in image_js, "image task settings or labels are not mode-specific")
require("image-compressor.js?v=20261121-image-tools-4" in image_ar and "image-compressor.js?v=20261121-image-tools-4" in image_en, "image tool script cache was not refreshed")
require("imageTools:'أدوات الصور'" in image_js and "imageTools:'Image tools'" in image_js, "image tools navigation labels are missing")
require("الذكاء الاصطناعي" in image_js and "super-resolution" in image_js, "image resize and enhancement limitations are not disclosed")
print("PASS: image conversion, resizing, compression and enhancement are separate task modes.")


# Check every executable inline script in the two standalone print tools.
for relative in ("static/saffha/index.html", "static/poster-splitter.html"):
    html = (ROOT / relative).read_text(encoding="utf-8")
    script_number = 0
    for match in re.finditer(r"<script\b([^>]*)>([\s\S]*?)</script\s*>", html, re.IGNORECASE):
        attributes, source = match.groups()
        if re.search(r"\bsrc\s*=", attributes, re.IGNORECASE):
            continue
        script_type = re.search(r"""\btype\s*=\s*["']([^"']+)["']""", attributes, re.IGNORECASE)
        if script_type and script_type.group(1).lower() not in ("text/javascript", "application/javascript", "module"):
            continue
        if not source.strip():
            continue
        script_number += 1
        with tempfile.NamedTemporaryFile("w", suffix=".js", encoding="utf-8", delete=False) as temp:
            temp.write(source)
            temp_path = Path(temp.name)
        try:
            checked = subprocess.run(["node", "--check", str(temp_path)], capture_output=True, text=True)
            require(checked.returncode == 0, f"{relative} inline script {script_number} has invalid JavaScript: {checked.stderr[-800:]}")
        finally:
            temp_path.unlink(missing_ok=True)
    require(script_number > 0, f"{relative} contains no executable inline JavaScript to check")
print("PASS: inline JavaScript syntax in Saffha and Poster Splitter.")
