from __future__ import annotations

import os
import re
import html
from io import BytesIO
import shutil
import subprocess
import tempfile
import unicodedata
from pathlib import Path
from typing import Optional

import fitz  # PyMuPDF
import httpx
from docx import Document
from docx.shared import Pt, RGBColor
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT, WD_ROW_HEIGHT_RULE, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "50"))
MAX_UPLOAD_BYTES = MAX_UPLOAD_MB * 1024 * 1024
LIBRETRANSLATE_URL = os.getenv("LIBRETRANSLATE_URL", "").rstrip("/")
LIBRETRANSLATE_API_KEY = os.getenv("LIBRETRANSLATE_API_KEY", "")
CLOUDFLARE_ACCOUNT_ID = os.getenv("CLOUDFLARE_ACCOUNT_ID", "").strip()
CLOUDFLARE_API_TOKEN = os.getenv("CLOUDFLARE_API_TOKEN", "").strip()
CLOUDFLARE_TRANSLATION_MODEL = os.getenv("CLOUDFLARE_TRANSLATION_MODEL", "@cf/meta/m2m100-1.2b").strip()
MYMEMORY_CONTACT_EMAIL = os.getenv("MYMEMORY_CONTACT_EMAIL", "").strip()


def translation_provider_name() -> str:
    if CLOUDFLARE_ACCOUNT_ID or CLOUDFLARE_API_TOKEN:
        if CLOUDFLARE_ACCOUNT_ID and CLOUDFLARE_API_TOKEN:
            return "Cloudflare Workers AI (Meta M2M100 1.2B)"
        return "Cloudflare configuration incomplete"
    if LIBRETRANSLATE_URL:
        return "LibreTranslate"
    return "MyMemory fallback"

app = FastAPI(title="PDF Globe API", version="1.1.0")

# The static UI is hosted on Cloudflare Pages; PDF Globe's API remains on Render.
# Set FRONTEND_ORIGINS in Render if the Pages project name or custom domain changes.
FRONTEND_ORIGINS = [
    origin.strip().rstrip("/")
    for origin in os.getenv(
        "FRONTEND_ORIGINS",
        "https://pdf-globe.pages.dev,https://pdf-globe.onrender.com",
    ).split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=FRONTEND_ORIGINS,
    # Allows Cloudflare Pages branch/commit preview URLs for this project only.
    allow_origin_regex=r"^https://([a-z0-9-]+\.)*pdf-globe\.pages\.dev$",
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type"],
    expose_headers=[
        "X-PDF-Globe-Hybrid-Editable-Pages", "X-PDF-Globe-Hybrid-Image-Pages",
        "X-PDF-Globe-Structured-Editable-Pages", "X-PDF-Globe-Structured-Table-Pages",
        "X-PDF-Globe-Structured-Image-Pages",
    ],
    max_age=3600,
)


def safe_name(name: str, fallback: str = "document") -> str:
    raw = Path(name or fallback).stem
    clean = re.sub(r"[^A-Za-z0-9_.-]+", "_", raw).strip("._")
    return (clean or fallback)[:80]


async def store_upload(upload: UploadFile, folder: Path, allowed_suffixes: Optional[set[str]] = None) -> Path:
    suffix = Path(upload.filename or "file").suffix.lower()
    if allowed_suffixes is not None and suffix not in allowed_suffixes:
        raise HTTPException(status_code=415, detail=f"نوع الملف غير مدعوم: {suffix or 'بدون امتداد'}")
    path = folder / (safe_name(upload.filename or "file") + suffix)
    total = 0
    with path.open("wb") as out:
        while True:
            chunk = await upload.read(1024 * 1024)
            if not chunk:
                break
            total += len(chunk)
            if total > MAX_UPLOAD_BYTES:
                out.close()
                path.unlink(missing_ok=True)
                raise HTTPException(status_code=413, detail=f"حجم الملف يتجاوز الحد الحالي ({MAX_UPLOAD_MB} MB)")
            out.write(chunk)
    if total == 0:
        raise HTTPException(status_code=400, detail="الملف فارغ")
    return path



def download_response(path: Path, filename: str, media_type: str) -> Response:
    # Read into memory before TemporaryDirectory is cleaned up after the request.
    data = path.read_bytes()
    return Response(content=data, media_type=media_type, headers={"Content-Disposition": f'attachment; filename="{filename}"'})


def require_binary(name: str, install_hint: str) -> str:
    binary = shutil.which(name)
    if not binary:
        raise HTTPException(status_code=503, detail=f"الخدمة غير جاهزة على الخادم: {name}. {install_hint}")
    return binary


@app.get("/api/health")
async def health():
    return {
        "ok": True,
        "service": "PDF Globe",
        "max_upload_mb": MAX_UPLOAD_MB,
        "translation_provider": translation_provider_name(),
        "cloudflare_configured": bool(CLOUDFLARE_ACCOUNT_ID and CLOUDFLARE_API_TOKEN),
        "libreoffice": bool(shutil.which("libreoffice")),
        "qpdf": bool(shutil.which("qpdf")),
    }


@app.post("/api/pdf/compress")
async def compress_pdf(file: UploadFile = File(...)):
    with tempfile.TemporaryDirectory(prefix="pdfglobe-") as td:
        folder = Path(td)
        src = await store_upload(file, folder, {".pdf"})
        out = folder / f"{safe_name(file.filename)}_compressed.pdf"
        try:
            doc = fitz.open(src)
            if doc.is_encrypted:
                raise HTTPException(status_code=423, detail="الملف محمي بكلمة مرور. أزل الحماية أولاً")
            doc.save(out, garbage=4, deflate=True, deflate_images=True, deflate_fonts=True, clean=True)
            doc.close()
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(status_code=422, detail=f"تعذر ضغط الملف: {exc}")
        return download_response(out, out.name, "application/pdf")


def create_layout_preserving_docx(src: Path, out: Path, dpi: int = 180) -> None:
    """Create a DOCX with one full-page image per PDF page.

    This mode prioritizes visual fidelity for mixed RTL/LTR documents, labels,
    barcodes, tables, and scanned pages. The page content is not text-editable.
    """
    pdf = fitz.open(src)
    if pdf.is_encrypted:
        pdf.close()
        raise ValueError("الملف محمي بكلمة مرور. أزل الحماية أولاً")
    if pdf.page_count > 80:
        pdf.close()
        raise ValueError("وضع الحفاظ على التصميم يدعم حتى 80 صفحة في المرة الواحدة")

    doc = Document()
    doc.core_properties.title = "PDF Globe - Layout-preserved PDF conversion"
    max_page_pt = 22 * 72  # Word's practical maximum page dimension.
    epsilon_pt = 0.7      # Avoid a fractional-point overflow onto a blank page.

    try:
        for index, page in enumerate(pdf):
            section = doc.sections[0] if index == 0 else doc.add_section(WD_SECTION.NEW_PAGE)
            width_pt = float(page.rect.width)
            height_pt = float(page.rect.height)
            dimension_scale = min(1.0, max_page_pt / max(width_pt, height_pt))
            target_w = width_pt * dimension_scale
            target_h = height_pt * dimension_scale

            section.page_width = Pt(target_w)
            section.page_height = Pt(target_h)
            section.top_margin = Pt(0)
            section.bottom_margin = Pt(0)
            section.left_margin = Pt(0)
            section.right_margin = Pt(0)
            section.header_distance = Pt(0)
            section.footer_distance = Pt(0)

            render_scale = (dpi / 72.0) * dimension_scale
            pix = page.get_pixmap(
                matrix=fitz.Matrix(render_scale, render_scale),
                colorspace=fitz.csRGB,
                alpha=False,
                annots=True,
            )
            image_path = out.parent / f"pdfglobe-page-{index + 1}.png"
            pix.save(image_path)

            paragraph = doc.add_paragraph()
            paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
            fmt = paragraph.paragraph_format
            fmt.space_before = Pt(0)
            fmt.space_after = Pt(0)
            fmt.left_indent = Pt(0)
            fmt.right_indent = Pt(0)
            fmt.first_line_indent = Pt(0)
            fmt.line_spacing = Pt(max(1, target_h - epsilon_pt))
            run = paragraph.add_run()
            run.add_picture(
                str(image_path),
                width=Pt(max(1, target_w - epsilon_pt)),
                height=Pt(max(1, target_h - epsilon_pt)),
            )
            image_path.unlink(missing_ok=True)
    finally:
        pdf.close()

    doc.save(out)


_ARABIC_BIDI = {"R", "AL", "AN"}


def _is_rtl_text(value: str) -> bool:
    """Return True when Arabic/Hebrew directional characters dominate a block."""
    directional = [unicodedata.bidirectional(ch) for ch in value if ch.isalpha()]
    if not directional:
        return False
    rtl_count = sum(code in _ARABIC_BIDI for code in directional)
    return rtl_count >= max(1, int(len(directional) * 0.18))


def _block_plain_text(block: dict) -> str:
    lines = block.get("lines", [])
    return "\n".join(
        "".join(str(span.get("text", "")) for span in line.get("spans", []))
        for line in lines
    ).strip()


def _cluster_y_rows(blocks: list[dict], tolerance: float = 8.0) -> list[list[dict]]:
    rows: list[list[dict]] = []
    for block in sorted(blocks, key=lambda item: (item["bbox"][1], item["bbox"][0])):
        y = (float(block["bbox"][1]) + float(block["bbox"][3])) / 2
        match = None
        for row in rows:
            row_y = sum(item["center_y"] for item in row) / len(row)
            if abs(y - row_y) <= tolerance:
                match = row
                break
        if match is None:
            match = []
            rows.append(match)
        match.append({"block": block, "center_y": y})
    return [[entry["block"] for entry in row] for row in rows]


def detect_complex_page(page) -> tuple[bool, str]:
    """Conservatively detect pages whose spatial structure should remain an image.

    The detection is intentionally conservative: when a page looks like a table,
    bracket, form, diagram, or scan, the full page is embedded as an image in DOCX.
    Plain text pages remain editable. This avoids silently rearranging matches,
    names, times, and table cells into unrelated paragraphs.
    """
    page_rect = page.rect
    page_area = max(1.0, float(page_rect.width * page_rect.height))
    raw_blocks = page.get_text("dict").get("blocks", [])
    text_blocks = [
        block for block in raw_blocks
        if block.get("type") == 0 and _block_plain_text(block)
    ]
    text_chars = sum(len(_block_plain_text(block)) for block in text_blocks)

    # 1) Native table detection (PyMuPDF >= 1.23; requirements use 1.25.5).
    try:
        found = page.find_tables()
        for table in getattr(found, "tables", []) or []:
            row_count = int(getattr(table, "row_count", 0) or 0)
            col_count = int(getattr(table, "col_count", 0) or 0)
            if row_count >= 2 and col_count >= 2 and row_count * col_count >= 4:
                return True, f"table:{row_count}x{col_count}"
    except Exception:
        # Table detection can fail on malformed or unusual PDFs. Continue with heuristics.
        pass

    # 2) Large embedded images or image-only/scanned pages.
    try:
        image_infos = page.get_image_info()
    except Exception:
        image_infos = []
    for image in image_infos:
        bbox = image.get("bbox")
        if bbox and len(bbox) == 4:
            area = max(0.0, float(bbox[2] - bbox[0])) * max(0.0, float(bbox[3] - bbox[1]))
            if area / page_area >= 0.22:
                return True, "large-image-region"
    if text_chars < 25 and (image_infos or page.get_images(full=True)):
        return True, "scanned-or-image-page"

    # 3) Vector drawing density plus spatially distributed labels: common in
    # tournament brackets, flowcharts and forms. A normal Arabic page often has
    # many decorative rules but all text blocks share one right edge, so require
    # both left and right edges to form several distinct clusters.
    try:
        drawings = page.get_drawings()
        drawing_items = sum(len(drawing.get("items", [])) for drawing in drawings)
    except Exception:
        drawing_items = 0

    def _cluster_sizes(values: list[float], tolerance: float = 32.0) -> list[int]:
        clusters: list[list[float]] = []
        for value in sorted(values):
            if not clusters or abs(value - (sum(clusters[-1]) / len(clusters[-1]))) > tolerance:
                clusters.append([value])
            else:
                clusters[-1].append(value)
        return [len(cluster) for cluster in clusters]

    if drawing_items >= 14 and len(text_blocks) >= 6:
        left_edges = [float(block["bbox"][0]) for block in text_blocks]
        right_edges = [float(block["bbox"][2]) for block in text_blocks]
        left_clusters = _cluster_sizes(left_edges)
        right_clusters = _cluster_sizes(right_edges)
        left_dominance = max(left_clusters, default=0) / max(1, len(text_blocks))
        right_dominance = max(right_clusters, default=0) / max(1, len(text_blocks))
        bracket_like_alignment = (
            len(left_clusters) >= 3 and len(right_clusters) >= 3
            and left_dominance < 0.78 and right_dominance < 0.78
        )
        if bracket_like_alignment:
            return True, f"diagram:{drawing_items}-vector-items"

    # 4) Repeated rows with multiple separately positioned text blocks indicate tables.
    rows = _cluster_y_rows(text_blocks)
    multi_block_rows = [row for row in rows if len(row) >= 2]
    if len(text_blocks) >= 8 and len(multi_block_rows) >= 4:
        return True, f"aligned-table-rows:{len(multi_block_rows)}"

    # 5) Multiple stable text columns with repeated blocks can indicate a bracket/table.
    x_positions = sorted(float(block["bbox"][0]) for block in text_blocks)
    x_clusters: list[list[float]] = []
    for x in x_positions:
        if not x_clusters or abs(x - (sum(x_clusters[-1]) / len(x_clusters[-1]))) > 42:
            x_clusters.append([x])
        else:
            x_clusters[-1].append(x)
    substantial_columns = [cluster for cluster in x_clusters if len(cluster) >= 4]
    if len(text_blocks) >= 10 and len(substantial_columns) >= 2:
        return True, f"multi-column-layout:{len(substantial_columns)}"

    return False, "plain-text"


def _set_paragraph_bidi(paragraph, rtl: bool) -> None:
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    ppr = paragraph._p.get_or_add_pPr()
    existing = ppr.find(qn("w:bidi"))
    if existing is None and rtl:
        bidi = OxmlElement("w:bidi")
        bidi.set(qn("w:val"), "1")
        ppr.append(bidi)


def _set_run_direction(run, rtl: bool) -> None:
    if not rtl:
        return
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    rpr = run._r.get_or_add_rPr()
    rtl_node = rpr.find(qn("w:rtl"))
    if rtl_node is None:
        rtl_node = OxmlElement("w:rtl")
        rtl_node.set(qn("w:val"), "1")
        rpr.append(rtl_node)
    rfonts = rpr.rFonts
    if rfonts is not None:
        rfonts.set(qn("w:cs"), "Arial")
        rfonts.set(qn("w:eastAsia"), "Arial")


def _configure_docx_page(section, width_pt: float, height_pt: float, image_page: bool) -> float:
    max_page_pt = 22 * 72
    scale = min(1.0, max_page_pt / max(width_pt, height_pt, 1.0))
    section.page_width = Pt(max(36, width_pt * scale))
    section.page_height = Pt(max(36, height_pt * scale))
    margin = 0 if image_page else min(18.0, max(8.0, width_pt * scale * 0.025))
    section.top_margin = Pt(margin)
    section.bottom_margin = Pt(margin)
    section.left_margin = Pt(margin)
    section.right_margin = Pt(margin)
    section.header_distance = Pt(0)
    section.footer_distance = Pt(0)
    return scale


def _add_full_page_image(doc: Document, page, section, image_path: Path, dpi: int = 160) -> None:
    width_pt = float(page.rect.width)
    height_pt = float(page.rect.height)
    scale = _configure_docx_page(section, width_pt, height_pt, image_page=True)
    render_scale = (dpi / 72.0) * scale
    pix = page.get_pixmap(
        matrix=fitz.Matrix(render_scale, render_scale),
        colorspace=fitz.csRGB,
        alpha=False,
        annots=True,
    )
    pix.save(image_path)
    paragraph = doc.add_paragraph()
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    paragraph.paragraph_format.space_before = Pt(0)
    paragraph.paragraph_format.space_after = Pt(0)
    paragraph.paragraph_format.left_indent = Pt(0)
    paragraph.paragraph_format.right_indent = Pt(0)
    paragraph.paragraph_format.first_line_indent = Pt(0)
    target_w = max(1.0, width_pt * scale - 0.8)
    target_h = max(1.0, height_pt * scale - 0.8)
    paragraph.paragraph_format.line_spacing = Pt(max(1.0, target_h - 0.5))
    paragraph.add_run().add_picture(str(image_path), width=Pt(target_w), height=Pt(target_h))
    image_path.unlink(missing_ok=True)


def _add_editable_text_page(doc: Document, page, section) -> bool:
    """Write ordinary text blocks as editable paragraphs with approximate placement."""
    width_pt = float(page.rect.width)
    height_pt = float(page.rect.height)
    scale = _configure_docx_page(section, width_pt, height_pt, image_page=False)
    margin = float(section.left_margin.pt)
    blocks = [
        block for block in page.get_text("dict").get("blocks", [])
        if block.get("type") == 0 and _block_plain_text(block)
    ]
    blocks.sort(key=lambda block: (float(block["bbox"][1]), float(block["bbox"][0])))
    if not blocks:
        return False

    previous_bottom = margin / max(scale, 0.001)
    body_width = max(20.0, width_pt - (2 * margin / max(scale, 0.001)))
    for block in blocks:
        x0, y0, x1, y1 = [float(value) for value in block.get("bbox", (0, 0, width_pt, 12))]
        x0, y0, x1, y1 = [max(0.0, value) for value in (x0, y0, x1, y1)]
        block_text = _block_plain_text(block)
        rtl = _is_rtl_text(block_text)
        center_x = (x0 + x1) / 2
        centered = abs(center_x - width_pt / 2) <= width_pt * 0.07

        paragraph = doc.add_paragraph()
        paragraph.paragraph_format.space_before = Pt(max(0.0, (y0 - previous_bottom) * scale))
        paragraph.paragraph_format.space_after = Pt(0)
        paragraph.paragraph_format.keep_together = True
        paragraph.paragraph_format.widow_control = False
        paragraph.paragraph_format.line_spacing = 1.0
        if centered:
            paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
        elif rtl:
            paragraph.alignment = WD_ALIGN_PARAGRAPH.RIGHT
            right_indent = max(0.0, width_pt - x1 - margin)
            paragraph.paragraph_format.right_indent = Pt(right_indent * scale)
        else:
            paragraph.alignment = WD_ALIGN_PARAGRAPH.LEFT
            left_indent = max(0.0, x0 - margin)
            paragraph.paragraph_format.left_indent = Pt(left_indent * scale)
        _set_paragraph_bidi(paragraph, rtl)

        lines = block.get("lines", [])
        first_line = True
        for line in lines:
            spans = line.get("spans", [])
            if not first_line:
                paragraph.add_run().add_break()
            for span in spans:
                text = str(span.get("text", ""))
                if not text:
                    continue
                run = paragraph.add_run(text)
                run.font.name = "Arial"
                font_size = float(span.get("size", 10) or 10) * scale
                run.font.size = Pt(min(42, max(5, font_size)))
                font_name = str(span.get("font", "")).lower()
                flags = int(span.get("flags", 0) or 0)
                run.bold = ("bold" in font_name) or bool(flags & 16)
                run.italic = ("italic" in font_name) or bool(flags & 2)
                color = span.get("color")
                if isinstance(color, int) and color >= 0:
                    run.font.color.rgb = RGBColor((color >> 16) & 255, (color >> 8) & 255, color & 255)
                _set_run_direction(run, rtl)
            first_line = False
        previous_bottom = max(previous_bottom, y1)

    return True


def create_hybrid_docx(src: Path, out: Path, dpi: int = 160) -> dict:
    """Create a hybrid DOCX: ordinary text pages editable, complex pages as images.

    Table/bracket/diagram/scan detection is conservative and page-based. If a page
    contains a detected complex region, the whole page is embedded as an image to
    preserve the spatial relationships that editable extraction commonly destroys.
    """
    pdf = fitz.open(src)
    if pdf.is_encrypted:
        pdf.close()
        raise ValueError("الملف محمي بكلمة مرور. أزل الحماية أولاً")
    if pdf.page_count > 60:
        pdf.close()
        raise ValueError("التحويل الهجين يدعم حتى 60 صفحة في المرة الواحدة لتقليل استهلاك الذاكرة")

    doc = Document()
    doc.core_properties.title = "PDF Globe - Hybrid PDF to Word conversion"
    editable_pages = 0
    image_pages = 0
    reasons: list[str] = []
    try:
        for index, page in enumerate(pdf):
            if index > 0:
                section = doc.add_section(WD_SECTION.NEW_PAGE)
            else:
                section = doc.sections[0]
            complex_page, reason = detect_complex_page(page)
            if complex_page:
                image_pages += 1
                reasons.append(f"{index + 1}:{reason}")
                image_path = out.parent / f"pdfglobe-hybrid-page-{index + 1}.png"
                _add_full_page_image(doc, page, section, image_path, dpi=dpi)
            else:
                if _add_editable_text_page(doc, page, section):
                    editable_pages += 1
                else:
                    image_pages += 1
                    reasons.append(f"{index + 1}:no-extractable-text")
                    image_path = out.parent / f"pdfglobe-hybrid-page-{index + 1}.png"
                    _add_full_page_image(doc, page, section, image_path, dpi=dpi)
    finally:
        pdf.close()

    if editable_pages == 0 and image_pages == 0:
        raise ValueError("لم يتم العثور على صفحات قابلة للتحويل")
    doc.core_properties.subject = (
        f"Hybrid conversion: {editable_pages} editable text page(s); "
        f"{image_pages} page image(s) used for complex layouts."
    )
    doc.core_properties.comments = (
        "Complex pages such as tables, tournament brackets, forms, diagrams, or scans "
        "may be embedded as page images to preserve their appearance."
    )
    doc.save(out)
    return {"editable_pages": editable_pages, "image_pages": image_pages, "reasons": reasons}



# ---------------- Editable-layout DOCX conversion ----------------
# Unlike the legacy hybrid mode, this mode does NOT rasterize complex text pages.
# It maps spatially aligned PDF text lines into a native Word table grid so that
# names, times, labels and table cells remain editable. Horizontal/vertical PDF
# rules are approximated as Word cell borders. Exact fidelity is not guaranteed:
# PDF does not necessarily contain semantic table cells, and diagonal/vector art
# or unusual layouts may need manual touch-up.

def _normalise_pdf_text(value: str) -> str:
    # PDF fonts sometimes expose Arabic Presentation Forms; NFKC converts them
    # back to ordinary Unicode Arabic characters suitable for editing in Word.
    return unicodedata.normalize("NFKC", value or "")


def _extract_page_layout_items(page) -> list[dict]:
    data = page.get_text("dict", sort=False)
    items: list[dict] = []
    for block_index, block in enumerate(data.get("blocks", [])):
        if block.get("type") == 0:
            for line_index, line in enumerate(block.get("lines", [])):
                spans = [sp for sp in line.get("spans", []) if str(sp.get("text", ""))]
                text = _normalise_pdf_text("".join(str(sp.get("text", "")) for sp in spans)).strip()
                if not text:
                    continue
                bbox = line.get("bbox") or block.get("bbox")
                if not bbox or len(bbox) != 4:
                    continue
                x0, y0, x1, y1 = map(float, bbox)
                rtl = _is_rtl_text(text)
                # Right edge is the more stable anchor for right-aligned RTL
                # columns; left edge works better for LTR columns.
                anchor = x1 if rtl else x0
                items.append({
                    "kind": "text", "text": text, "spans": spans,
                    "bbox": (x0, y0, x1, y1), "center_y": (y0 + y1) / 2,
                    # Keep all three horizontal anchors. A PDF line's right edge
                    # is NOT a stable column anchor when centered Arabic labels
                    # have different text lengths. The page-level selector below
                    # chooses left, center, or right alignment from the evidence.
                    "anchor": (x0 + x1) / 2,
                    "anchor_left": x0,
                    "anchor_center": (x0 + x1) / 2,
                    "anchor_right": x1,
                    "rtl": rtl,
                    "font_size": max([float(sp.get("size", 10) or 10) for sp in spans] or [10]),
                    "order": (block_index, line_index),
                })
        elif block.get("type") == 1 and block.get("image"):
            bbox = block.get("bbox")
            if not bbox or len(bbox) != 4:
                continue
            x0, y0, x1, y1 = map(float, bbox)
            items.append({
                "kind": "image", "image": block["image"], "ext": block.get("ext", "png"),
                "bbox": (x0, y0, x1, y1), "center_y": (y0 + y1) / 2,
                "anchor": (x0 + x1) / 2, "rtl": False, "font_size": 10,
                "order": (block_index, 0),
            })
    return items


def _cluster_numeric(values: list[float], tolerance: float) -> list[list[float]]:
    clusters: list[list[float]] = []
    for value in sorted(values):
        if not clusters or abs(value - (sum(clusters[-1]) / len(clusters[-1]))) > tolerance:
            clusters.append([value])
        else:
            clusters[-1].append(value)
    return clusters


def _native_table_column_bounds(page) -> tuple[list[float] | None, int, int]:
    """Return trustworthy x boundaries from PyMuPDF's detected native tables.

    PyMuPDF Table.cells is column-major: cells for column 0 come first, then
    column 1, etc. We only use the geometry when it forms a complete rectangular
    grid with stable column edges. Otherwise the layout-anchor heuristic is used.
    """
    try:
        tables = list(getattr(page.find_tables(), "tables", []) or [])
    except Exception:
        return None, 0, 0
    candidates = []
    for table in tables:
        rows = int(getattr(table, "row_count", 0) or 0)
        cols = int(getattr(table, "col_count", 0) or 0)
        cells = list(getattr(table, "cells", []) or [])
        if rows < 2 or cols < 2 or len(cells) < rows * cols:
            continue
        column_ranges = []
        valid = True
        for col in range(cols):
            col_cells = [cells[col * rows + row] for row in range(rows)]
            col_cells = [cell for cell in col_cells if cell and len(cell) == 4]
            if len(col_cells) < max(2, rows // 2):
                valid = False
                break
            x0 = min(float(cell[0]) for cell in col_cells)
            x1 = max(float(cell[2]) for cell in col_cells)
            if x1 - x0 < 5:
                valid = False
                break
            column_ranges.append((x0, x1))
        if not valid:
            continue
        bounds = [column_ranges[0][0]]
        for left, right in column_ranges:
            if abs(left - bounds[-1]) > 4.0 and len(bounds) > 1:
                valid = False
                break
            if len(bounds) == 1:
                bounds[0] = left
            bounds.append(right)
        if not valid or len(bounds) != cols + 1:
            continue
        if any(bounds[i + 1] - bounds[i] < 4 for i in range(cols)):
            continue
        area = max(0.0, float(table.bbox[2] - table.bbox[0])) * max(0.0, float(table.bbox[3] - table.bbox[1]))
        candidates.append((area, bounds, rows, cols))
    if not candidates:
        return None, 0, 0
    _, bounds, rows, cols = max(candidates, key=lambda item: item[0])
    return bounds, rows, cols


def _select_column_anchor(items: list[dict], page_width: float) -> tuple[str, list[list[float]]]:
    """Choose the most stable horizontal anchor for a page's text columns.

    PDF text spans expose the visible glyph bounds, not their containing cell.
    Using the right edge for every RTL line fragments a centered Arabic column
    into many false columns whenever player/team names have different lengths.
    Compare left, center and right anchors and prefer the strategy that produces
    a compact set of repeatedly occupied columns with few singleton clusters.
    """
    tolerance = max(12.0, min(24.0, page_width * 0.035))
    strategies = ("left", "center", "right")
    scored: list[tuple[float, int, str, list[list[float]]]] = []
    for strategy in strategies:
        key = f"anchor_{strategy}"
        values = [float(item.get(key, item.get("anchor", 0.0))) for item in items]
        clusters = _cluster_numeric(values, tolerance)
        if not clusters:
            continue
        singletons = sum(1 for cluster in clusters if len(cluster) == 1)
        # Penalise fragmentation much more than a modestly larger legitimate
        # column count. Repeated alignments are strong evidence of real columns.
        singleton_ratio = singletons / len(clusters)
        too_many = max(0, len(clusters) - 12)
        dispersion = sum(
            sum(abs(value - (sum(cluster) / len(cluster))) for value in cluster) / max(1, len(cluster))
            for cluster in clusters
        ) / len(clusters)
        score = len(clusters) + 2.2 * singletons + 0.015 * dispersion + 2.5 * too_many
        scored.append((score, len(clusters), strategy, clusters))
    if not scored:
        return "center", []
    # Stable tie-break favors center alignment for diagrams/brackets, where
    # labels are commonly centered within their visual boxes.
    scored.sort(key=lambda row: (round(row[0], 4), row[1], 0 if row[2] == "center" else 1))
    _, _, selected, clusters = scored[0]
    for item in items:
        item["anchor"] = float(item.get(f"anchor_{selected}", item.get("anchor", 0.0)))
    return selected, clusters


def _set_cell_margins(cell, top=0, start=0, bottom=0, end=0) -> None:
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    tc = cell._tc
    tc_pr = tc.get_or_add_tcPr()
    tc_mar = tc_pr.first_child_found_in("w:tcMar")
    if tc_mar is None:
        tc_mar = OxmlElement("w:tcMar")
        tc_pr.append(tc_mar)
    for edge, value in (("top", top), ("start", start), ("bottom", bottom), ("end", end)):
        node = tc_mar.find(qn(f"w:{edge}"))
        if node is None:
            node = OxmlElement(f"w:{edge}")
            tc_mar.append(node)
        node.set(qn("w:w"), str(int(value)))
        node.set(qn("w:type"), "dxa")


def _set_cell_edge(cell, edge: str, color: str = "808080", size: int = 4, style: str = "single") -> None:
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    tc_pr = cell._tc.get_or_add_tcPr()
    borders = tc_pr.first_child_found_in("w:tcBorders")
    if borders is None:
        borders = OxmlElement("w:tcBorders")
        tc_pr.append(borders)
    tag = qn(f"w:{edge}")
    node = borders.find(tag)
    if node is None:
        node = OxmlElement(f"w:{edge}")
        borders.append(node)
    node.set(qn("w:val"), style)
    node.set(qn("w:sz"), str(max(2, min(16, int(size)))))
    node.set(qn("w:space"), "0")
    node.set(qn("w:color"), color if re.fullmatch(r"[0-9A-Fa-f]{6}", color or "") else "808080")


def _line_segments(page) -> list[dict]:
    segments: list[dict] = []
    try:
        drawings = page.get_drawings()
    except Exception:
        return segments
    for drawing in drawings:
        color_value = drawing.get("color") or drawing.get("fill") or (0.5, 0.5, 0.5)
        try:
            color = "".join(f"{round(max(0, min(1, float(c))) * 255):02X}" for c in color_value[:3])
        except Exception:
            color = "808080"
        width = float(drawing.get("width", 0.5) or 0.5)
        for item in drawing.get("items", []):
            kind = item[0]
            if kind == "l" and len(item) >= 3:
                p1, p2 = item[1], item[2]
                x1, y1, x2, y2 = float(p1.x), float(p1.y), float(p2.x), float(p2.y)
                if abs(y1 - y2) <= 1.5 and abs(x1 - x2) >= 5:
                    segments.append({"kind": "h", "pos": (y1 + y2) / 2, "a": min(x1, x2), "b": max(x1, x2), "color": color, "width": width})
                elif abs(x1 - x2) <= 1.5 and abs(y1 - y2) >= 5:
                    segments.append({"kind": "v", "pos": (x1 + x2) / 2, "a": min(y1, y2), "b": max(y1, y2), "color": color, "width": width})
            elif kind == "re" and len(item) >= 2:
                rect = item[1]
                x0, y0, x1, y1 = float(rect.x0), float(rect.y0), float(rect.x1), float(rect.y1)
                if x1 - x0 >= 5 and y1 - y0 >= 5:
                    segments.extend([
                        {"kind": "h", "pos": y0, "a": x0, "b": x1, "color": color, "width": width},
                        {"kind": "h", "pos": y1, "a": x0, "b": x1, "color": color, "width": width},
                        {"kind": "v", "pos": x0, "a": y0, "b": y1, "color": color, "width": width},
                        {"kind": "v", "pos": x1, "a": y0, "b": y1, "color": color, "width": width},
                    ])
    return segments


def _apply_pdf_rules_to_grid(table, row_bounds: list[float], col_bounds: list[float], segments: list[dict], scale: float) -> None:
    if not segments:
        return
    y_tol = 2.2
    x_tol = 2.2
    for r, row in enumerate(table.rows):
        y0, y1 = row_bounds[r], row_bounds[r + 1]
        for c, cell in enumerate(row.cells):
            x0, x1 = col_bounds[c], col_bounds[c + 1]
            for seg in segments:
                if seg["kind"] == "h":
                    overlaps = min(x1, seg["b"]) - max(x0, seg["a"])
                    if overlaps < max(7.0, (x1 - x0) * 0.18):
                        continue
                    if abs(seg["pos"] - y0) <= y_tol:
                        _set_cell_edge(cell, "top", seg["color"], round(seg["width"] * scale * 8))
                    if abs(seg["pos"] - y1) <= y_tol:
                        _set_cell_edge(cell, "bottom", seg["color"], round(seg["width"] * scale * 8))
                else:
                    overlaps = min(y1, seg["b"]) - max(y0, seg["a"])
                    if overlaps < max(7.0, (y1 - y0) * 0.18):
                        continue
                    if abs(seg["pos"] - x0) <= x_tol:
                        _set_cell_edge(cell, "left", seg["color"], round(seg["width"] * scale * 8))
                    if abs(seg["pos"] - x1) <= x_tol:
                        _set_cell_edge(cell, "right", seg["color"], round(seg["width"] * scale * 8))


def _add_editable_spans(paragraph, spans: list[dict], rtl: bool, scale: float, left_indent_pt: float = 0.0, right_indent_pt: float = 0.0) -> None:
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    paragraph.alignment = WD_ALIGN_PARAGRAPH.RIGHT if rtl else WD_ALIGN_PARAGRAPH.LEFT
    _set_paragraph_bidi(paragraph, rtl)
    pf = paragraph.paragraph_format
    pf.space_before = Pt(0)
    pf.space_after = Pt(0)
    pf.left_indent = Pt(max(0.0, left_indent_pt))
    pf.right_indent = Pt(max(0.0, right_indent_pt))
    pf.first_line_indent = Pt(0)
    pf.line_spacing = 1.0
    for span in spans:
        text = _normalise_pdf_text(str(span.get("text", "")))
        if not text:
            continue
        run = paragraph.add_run(text)
        run.font.name = "Arial"
        run._element.get_or_add_rPr().rFonts.set(qn("w:ascii"), "Arial")
        run._element.get_or_add_rPr().rFonts.set(qn("w:hAnsi"), "Arial")
        font_size = float(span.get("size", 10) or 10) * scale
        run.font.size = Pt(min(36, max(5, font_size)))
        font_name = str(span.get("font", "")).lower()
        flags = int(span.get("flags", 0) or 0)
        run.bold = ("bold" in font_name) or bool(flags & 16)
        run.italic = ("italic" in font_name) or bool(flags & 2)
        color = span.get("color")
        if isinstance(color, int) and color >= 0:
            run.font.color.rgb = RGBColor((color >> 16) & 255, (color >> 8) & 255, color & 255)
        _set_run_direction(run, rtl)



def _add_editable_layout_grid_page(doc: Document, page, section, dpi: int = 160) -> dict:
    """Rebuild a complex PDF page as a native editable Word table grid.

    Text is placed in actual Word table cells, not rasterized. The grid approximates
    the PDF's x/y geometry; detected horizontal and vertical rules become cell
    borders. This is intended for schedules, forms and table-like tournament pages.
    """
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    page_w = float(page.rect.width)
    page_h = float(page.rect.height)
    scale = _configure_docx_page(section, page_w, page_h, image_page=False)
    # Horizontal margins stay zero. Vertical margins are calculated from the first
    # and last content baselines so the Word table preserves top/bottom whitespace
    # without forcing an oversized blank final row onto an extra page.
    section.left_margin = Pt(0)
    section.right_margin = Pt(0)

    items = _extract_page_layout_items(page)
    text_items = [item for item in items if item["kind"] == "text"]
    if len(text_items) < 2:
        raise ValueError("لا توجد نصوص كافية لإعادة بناء جدول قابل للتحرير. قد يكون الملف صورة ممسوحة ضوئياً؛ استخدم OCR أولاً.")

    median_font = sorted(item["font_size"] for item in text_items)[len(text_items) // 2]
    # PDF lines that visually share a row can have slightly different text
    # baselines (especially when Arabic and Latin labels are mixed).
    y_tolerance = max(2.8, min(7.5, median_font * 0.62))
    row_groups: list[list[dict]] = []
    for item in sorted(items, key=lambda obj: (obj["center_y"], obj["bbox"][0])):
        if not row_groups:
            row_groups.append([item])
            continue
        row_center = sum(obj["center_y"] for obj in row_groups[-1]) / len(row_groups[-1])
        if abs(item["center_y"] - row_center) <= y_tolerance:
            row_groups[-1].append(item)
        else:
            row_groups.append([item])

    # Prefer actual rectangular table geometry when PyMuPDF can detect it.
    # This preserves original cell widths instead of guessing them from glyphs.
    native_col_bounds, native_rows, native_cols = _native_table_column_bounds(page)
    if native_col_bounds and 2 <= len(native_col_bounds) - 1 <= 14:
        anchor_strategy = "native-table-centers"
        col_bounds = native_col_bounds
        col_centers = [(col_bounds[i] + col_bounds[i + 1]) / 2 for i in range(len(col_bounds) - 1)]
        # Map text by visible center when real cell boundaries are available;
        # this avoids text-length-dependent edge anchors in mixed Arabic/LTR rows.
        for item in text_items:
            item["anchor"] = item["anchor_center"]
        for item in items:
            if item["kind"] == "image":
                item["anchor"] = (item["bbox"][0] + item["bbox"][2]) / 2
    else:
        # Infer the page's actual alignment strategy. For centered Arabic team
        # names, x1/right-edge clustering creates a separate column for each text
        # length; center anchors retain the shared visual column. Left/right
        # strategies remain available for ordinary aligned tabular documents.
        anchor_strategy, anchor_clusters = _select_column_anchor(text_items, page_w)
        while len(anchor_clusters) > 14:
            gaps = [
                (abs(sum(anchor_clusters[i + 1]) / len(anchor_clusters[i + 1]) - sum(anchor_clusters[i]) / len(anchor_clusters[i])), i)
                for i in range(len(anchor_clusters) - 1)
            ]
            _, idx = min(gaps)
            anchor_clusters[idx] = anchor_clusters[idx] + anchor_clusters[idx + 1]
            del anchor_clusters[idx + 1]
        if not anchor_clusters:
            raise ValueError("تعذر تحديد أعمدة الصفحة")
        col_centers = [sum(cluster) / len(cluster) for cluster in anchor_clusters]
        col_bounds = [0.0]
        for left, right in zip(col_centers, col_centers[1:]):
            col_bounds.append(max(col_bounds[-1] + 4.0, (left + right) / 2))
        col_bounds.append(page_w)
        # Keep all physical column widths positive and in order.
        for i in range(1, len(col_bounds)):
            col_bounds[i] = max(col_bounds[i], col_bounds[i - 1] + 2.0)
        col_bounds[-1] = page_w

    row_centers = [sum(item["center_y"] for item in group) / len(group) for group in row_groups]
    vertical_pad = max(8.0, min(18.0, median_font * 1.35))
    content_top = max(0.0, row_centers[0] - vertical_pad)
    content_bottom = min(page_h, row_centers[-1] + vertical_pad)
    row_bounds = [content_top]
    for top, bottom in zip(row_centers, row_centers[1:]):
        row_bounds.append((top + bottom) / 2)
    row_bounds.append(max(row_bounds[-1] + 6.0, content_bottom))
    section.top_margin = Pt(content_top * scale)
    section.bottom_margin = Pt(0)

    # Limit table size on the free Render instance; a page with unusually dense
    # text is still preserved, but the API returns a clear message instead.
    rows_count = len(row_groups)
    cols_count = len(col_centers)
    if rows_count > 180 or cols_count > 14 or rows_count * cols_count > 1800:
        raise ValueError("تخطيط الصفحة كثيف جداً لإعادة بناء جدول Word آمن. جرّب تقسيم الملف أو وضع استخراج النص.")

    table = doc.add_table(rows=rows_count, cols=cols_count)
    table.alignment = WD_TABLE_ALIGNMENT.LEFT
    table.autofit = False
    tbl_pr = table._tbl.tblPr
    layout = tbl_pr.find(qn("w:tblLayout"))
    if layout is None:
        layout = OxmlElement("w:tblLayout")
        tbl_pr.append(layout)
    layout.set(qn("w:type"), "fixed")
    tbl_w = tbl_pr.find(qn("w:tblW"))
    if tbl_w is None:
        tbl_w = OxmlElement("w:tblW")
        tbl_pr.append(tbl_w)
    tbl_w.set(qn("w:w"), str(int(page_w * scale * 20)))
    tbl_w.set(qn("w:type"), "dxa")
    tbl_ind = tbl_pr.find(qn("w:tblInd"))
    if tbl_ind is None:
        tbl_ind = OxmlElement("w:tblInd")
        tbl_pr.append(tbl_ind)
    tbl_ind.set(qn("w:w"), "0")
    tbl_ind.set(qn("w:type"), "dxa")

    for c, col in enumerate(table.columns):
        width = max(4.0, (col_bounds[c + 1] - col_bounds[c]) * scale)
        col.width = Pt(width)
        for cell in col.cells:
            cell.width = Pt(width)
            _set_cell_margins(cell, 0, 0, 0, 0)
            cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER

    for r, row in enumerate(table.rows):
        row_height = max(7.0, (row_bounds[r + 1] - row_bounds[r]) * scale)
        row.height = Pt(row_height)
        row.height_rule = WD_ROW_HEIGHT_RULE.AT_LEAST
        tr_pr = row._tr.get_or_add_trPr()
        cant_split = OxmlElement("w:cantSplit")
        tr_pr.append(cant_split)
        for cell in row.cells:
            cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
            _set_cell_margins(cell, 0, 0, 0, 0)

    # If a text line physically spans more than one inferred column (for example
    # a page title above a bracket), merge the corresponding Word cells. This
    # preserves its original line width and keeps the text editable.
    item_column: dict[int, int] = {}
    row_cell_maps: dict[int, dict[int, int]] = {}
    for r, group in enumerate(row_groups):
        mapped = {}
        for item in group:
            base_col = min(range(cols_count), key=lambda idx: abs(col_centers[idx] - item["anchor"]))
            mapped[id(item)] = base_col
        row_cell_maps[r] = {c: c for c in range(cols_count)}
        for item in [x for x in group if x["kind"] == "text"]:
            x0, _, x1, _ = item["bbox"]
            start_col = max(0, min(cols_count - 1, next((i for i in range(cols_count) if x0 < col_bounds[i + 1]), cols_count - 1)))
            end_col = max(start_col, min(cols_count - 1, next((i for i in range(cols_count) if x1 <= col_bounds[i + 1] + 1.0), cols_count - 1)))
            base_col = mapped[id(item)]
            # Merge only when the line crosses a column boundary and no other
            # item in this row is anchored in the intervening cells.
            occupied = {mapped[id(other)] for other in group if other is not item}
            if end_col > start_col and not any(c in occupied for c in range(start_col + 1, end_col + 1)):
                try:
                    table.cell(r, start_col).merge(table.cell(r, end_col))
                    for c in range(start_col, end_col + 1):
                        row_cell_maps[r][c] = start_col
                    item_column[id(item)] = start_col
                except Exception:
                    item_column[id(item)] = base_col
            else:
                item_column[id(item)] = base_col
        for item in group:
            if id(item) not in item_column:
                item_column[id(item)] = mapped[id(item)]

    # Place each text line or embedded image into its nearest (possibly merged) cell.
    for r, group in enumerate(row_groups):
        cell_items: dict[int, list[dict]] = {}
        for item in group:
            c = item_column[id(item)]
            cell_items.setdefault(c, []).append(item)
        for c, content_items in cell_items.items():
            cell = table.cell(r, c)
            # Word merges retain the original empty paragraphs from each source
            # cell. Remove those extra blanks or they inflate row heights and can
            # push the final rows onto an unintended second page.
            for extra_paragraph in list(cell.paragraphs[1:]):
                if not extra_paragraph.text.strip():
                    extra_paragraph._element.getparent().remove(extra_paragraph._element)
            paragraph = cell.paragraphs[0]
            for child in list(paragraph._p):
                if child.tag != qn("w:pPr"):
                    paragraph._p.remove(child)
            content_items.sort(key=lambda obj: (obj["bbox"][1], obj["bbox"][0]))
            first = True
            for item in content_items:
                if item["kind"] == "text":
                    p = paragraph if first else cell.add_paragraph()
                    if item["rtl"]:
                        left_indent = 0.0
                        right_indent = max(0.0, (col_bounds[c + 1] - item["bbox"][2]) * scale)
                    else:
                        left_indent = max(0.0, (item["bbox"][0] - col_bounds[c]) * scale)
                        right_indent = 0.0
                    _add_editable_spans(p, item["spans"], item["rtl"], scale, left_indent, right_indent)
                    first = False
                else:
                    p = paragraph if first else cell.add_paragraph()
                    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                    p.paragraph_format.space_before = Pt(0)
                    p.paragraph_format.space_after = Pt(0)
                    img = BytesIO(item["image"])
                    max_width = max(4.0, (col_bounds[c + 1] - col_bounds[c]) * scale)
                    max_height = max(4.0, (row_bounds[r + 1] - row_bounds[r]) * scale)
                    try:
                        p.add_run().add_picture(img, width=Pt(min(max_width, max(4.0, item["bbox"][2] - item["bbox"][0]) * scale)))
                    except Exception:
                        pass
                    first = False

    segments = _line_segments(page)
    _apply_pdf_rules_to_grid(table, row_bounds, col_bounds, segments, scale)
    if anchor_strategy == "native-table-centers":
        # Native table detection is reliable evidence that the source has cell
        # boundaries. Apply a restrained grid to all output cells; detected PDF
        # rules above can then override the default edge colors/weights.
        for row in table.rows:
            for cell in row.cells:
                for edge in ("top", "bottom", "left", "right"):
                    _set_cell_edge(cell, edge, "B8C2CC", 4)
    return {"rows": rows_count, "columns": cols_count, "text_lines": len(text_items), "anchor_strategy": anchor_strategy}


def create_structured_editable_docx(src: Path, out: Path) -> dict:
    """Convert text and table-like pages to an editable Word layout grid.

    Simple prose pages use editable paragraphs. Complex table/bracket pages use
    native Word table cells with editable text and approximated borders/geometry.
    Image-only/scanned pages fall back to a page image because they have no text
    layer to edit; an OCR pass is needed to make their contents editable.
    """
    pdf = fitz.open(src)
    if pdf.is_encrypted:
        pdf.close()
        raise ValueError("الملف محمي بكلمة مرور. أزل الحماية أولاً")
    if pdf.page_count > 50:
        pdf.close()
        raise ValueError("وضع الجداول القابلة للتحرير يدعم حتى 50 صفحة في المرة الواحدة")
    doc = Document()
    doc.core_properties.title = "PDF Globe - Editable Table Layout"
    editable_pages = 0
    table_pages = 0
    image_pages = 0
    page_summaries: list[dict] = []
    try:
        for index, page in enumerate(pdf):
            if index == 0:
                section = doc.sections[0]
                # Remove python-docx's initial empty paragraph so the first grid
                # starts at the top edge of the page.
                if doc.paragraphs:
                    p = doc.paragraphs[0]._element
                    p.getparent().remove(p)
            else:
                section = doc.add_section(WD_SECTION.NEW_PAGE)
            complex_page, reason = detect_complex_page(page)
            if not complex_page and page.get_images(full=True):
                complex_page, reason = True, "embedded-images"
            if complex_page:
                # Full-page image regions (scans, shipping labels, photo-heavy forms)
                # do not have enough native text geometry to reconstruct faithfully.
                # Preserve those pages visually; table/bracket pages with selectable
                # text and vector layout are rebuilt as editable Word table grids.
                if reason.startswith("large-image-region") or reason.startswith("scanned-or-image-page"):
                    image_path = out.parent / f"pdfglobe-structured-fallback-{index + 1}.png"
                    _add_full_page_image(doc, page, section, image_path, dpi=180)
                    image_pages += 1
                    page_summaries.append({"page": index + 1, "mode": "image-fallback", "reason": reason})
                    continue
                try:
                    info = _add_editable_layout_grid_page(doc, page, section)
                    table_pages += 1
                    editable_pages += 1
                    page_summaries.append({"page": index + 1, "mode": "editable-table", **info, "reason": reason})
                except ValueError as exc:
                    # If extraction is genuinely impossible (e.g. scan), preserve
                    # the visual page rather than silently produce empty Word.
                    image_path = out.parent / f"pdfglobe-structured-fallback-{index + 1}.png"
                    _add_full_page_image(doc, page, section, image_path, dpi=170)
                    image_pages += 1
                    page_summaries.append({"page": index + 1, "mode": "image-fallback", "reason": str(exc)[:150]})
            else:
                if _add_editable_text_page(doc, page, section):
                    editable_pages += 1
                    page_summaries.append({"page": index + 1, "mode": "editable-text"})
                else:
                    image_path = out.parent / f"pdfglobe-structured-fallback-{index + 1}.png"
                    _add_full_page_image(doc, page, section, image_path, dpi=170)
                    image_pages += 1
                    page_summaries.append({"page": index + 1, "mode": "image-fallback", "reason": "no-text-layer"})
    finally:
        pdf.close()
    doc.core_properties.subject = (
        f"Editable layout conversion: {editable_pages} editable page(s), "
        f"{table_pages} editable table-layout page(s), {image_pages} image fallback page(s)."
    )
    doc.core_properties.comments = (
        "Complex pages are reconstructed as native Word table grids with editable text; "
        "font, spacing and vector rules are best-effort and may require manual review. "
        "Scanned/image-only pages remain images unless OCR is performed first."
    )
    doc.save(out)
    return {"editable_pages": editable_pages, "table_pages": table_pages, "image_pages": image_pages, "pages": page_summaries}


@app.post("/api/pdf/to-word")
async def pdf_to_word(file: UploadFile = File(...), mode: str = Form("structured")):
    mode = (mode or "layout").strip().lower()
    if mode not in {"layout", "editable", "hybrid", "structured"}:
        raise HTTPException(status_code=400, detail="اختر طريقة التحويل: هجين، أو الحفاظ على شكل الصفحات، أو استخراج النص القابل للتحرير")
    with tempfile.TemporaryDirectory(prefix="pdfglobe-") as td:
        folder = Path(td)
        src = await store_upload(file, folder, {".pdf"})
        out = folder / f"{safe_name(file.filename)}.docx"

        if mode == "structured":
            try:
                summary = create_structured_editable_docx(src, out)
            except ValueError as exc:
                raise HTTPException(status_code=422, detail=str(exc))
            except Exception as exc:
                raise HTTPException(status_code=422, detail=f"تعذر إنشاء Word بجداول قابلة للتحرير: {str(exc)[:300]}")
        elif mode == "hybrid":
            try:
                summary = create_hybrid_docx(src, out, dpi=160)
            except ValueError as exc:
                raise HTTPException(status_code=422, detail=str(exc))
            except Exception as exc:
                raise HTTPException(status_code=422, detail=f"تعذر إنشاء Word بالتحويل الهجين: {str(exc)[:300]}")
        elif mode == "layout":
            try:
                create_layout_preserving_docx(src, out, dpi=200)
            except ValueError as exc:
                raise HTTPException(status_code=422, detail=str(exc))
            except Exception as exc:
                raise HTTPException(status_code=422, detail=f"تعذر إنشاء Word مع الحفاظ على شكل الصفحات: {str(exc)[:300]}")
        elif mode == "editable":
            # pdf2docx is best-effort for editable extraction. It does not reliably
            # preserve RTL/bidi order, complex Arabic shaping, labels or barcodes.
            # Do not silently return a text-only PyMuPDF fallback: that fallback
            # loses geometry and can scramble Arabic reading order while appearing
            # to have succeeded.
            converter = None
            try:
                from pdf2docx import Converter
                converter = Converter(str(src))
                converter.convert(str(out), start=0, end=None)
            except Exception as exc:
                out.unlink(missing_ok=True)
                raise HTTPException(
                    status_code=422,
                    detail=(
                        "تعذر استخراج نص قابل للتحرير من هذا الملف. قد يكون تخطيطه معقداً أو "
                        "يحتوي على نص عربي/مختلط الاتجاه. جرّب وضع الحفاظ على شكل الصفحات. "
                        f"التفاصيل: {str(exc)[:220]}"
                    ),
                )
            finally:
                if converter is not None:
                    try:
                        converter.close()
                    except Exception:
                        pass
            if not out.exists() or out.stat().st_size == 0:
                raise HTTPException(status_code=422, detail="لم ينتج محرك التحويل ملف Word صالحاً. جرّب وضع الحفاظ على شكل الصفحات.")
        else:
            raise HTTPException(status_code=400, detail="اختر وضع التحويل: layout أو editable")

        response = download_response(
            out,
            out.name,
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
        if mode == "structured":
            response.headers["X-PDF-Globe-Structured-Editable-Pages"] = str(summary["editable_pages"])
            response.headers["X-PDF-Globe-Structured-Table-Pages"] = str(summary["table_pages"])
            response.headers["X-PDF-Globe-Structured-Image-Pages"] = str(summary["image_pages"])
        if mode == "hybrid":
            response.headers["X-PDF-Globe-Hybrid-Editable-Pages"] = str(summary["editable_pages"])
            response.headers["X-PDF-Globe-Hybrid-Image-Pages"] = str(summary["image_pages"])
        return response

@app.post("/api/word/to-pdf")
async def word_to_pdf(file: UploadFile = File(...)):
    office = require_binary("libreoffice", "أضف LibreOffice إلى صورة Docker الخاصة بالموقع")
    with tempfile.TemporaryDirectory(prefix="pdfglobe-") as td:
        folder = Path(td)
        src = await store_upload(file, folder, {".docx", ".doc", ".odt", ".rtf"})
        try:
            result = subprocess.run(
                [office, "-env:UserInstallation=file://" + str(folder / "lo-profile"), "--headless", "--convert-to", "pdf", "--outdir", str(folder), str(src)],
                capture_output=True, text=True, timeout=90,
            )
        except subprocess.TimeoutExpired:
            raise HTTPException(status_code=504, detail="انتهت مهلة التحويل. جرّب ملفاً أصغر")
        out = folder / (src.stem + ".pdf")
        if result.returncode != 0 or not out.exists():
            raise HTTPException(status_code=422, detail="فشل تحويل Word إلى PDF: " + (result.stderr[-600:] or result.stdout[-600:]))
        return download_response(out, out.name, "application/pdf")


@app.post("/api/pdf/protect")
async def protect_pdf(file: UploadFile = File(...), password: str = Form(...)):
    qpdf = require_binary("qpdf", "أضف qpdf إلى صورة Docker الخاصة بالموقع")
    if len(password) < 4:
        raise HTTPException(status_code=400, detail="استخدم كلمة مرور من 4 أحرف على الأقل")
    with tempfile.TemporaryDirectory(prefix="pdfglobe-") as td:
        folder = Path(td)
        src = await store_upload(file, folder, {".pdf"})
        out = folder / f"{safe_name(file.filename)}_protected.pdf"
        proc = subprocess.run([qpdf, "--encrypt", password, password, "256", "--", str(src), str(out)], capture_output=True, text=True, timeout=60)
        if proc.returncode != 0 or not out.exists():
            raise HTTPException(status_code=422, detail="تعذر حماية الملف. قد يكون تالفاً أو محمياً مسبقاً")
        return download_response(out, out.name, "application/pdf")


@app.post("/api/pdf/unlock")
async def unlock_pdf(file: UploadFile = File(...), password: str = Form(...)):
    qpdf = require_binary("qpdf", "أضف qpdf إلى صورة Docker الخاصة بالموقع")
    with tempfile.TemporaryDirectory(prefix="pdfglobe-") as td:
        folder = Path(td)
        src = await store_upload(file, folder, {".pdf"})
        out = folder / f"{safe_name(file.filename)}_unlocked.pdf"
        proc = subprocess.run([qpdf, f"--password={password}", "--decrypt", str(src), str(out)], capture_output=True, text=True, timeout=60)
        if proc.returncode != 0 or not out.exists():
            raise HTTPException(status_code=422, detail="كلمة المرور غير صحيحة أو تعذر فتح الملف")
        return download_response(out, out.name, "application/pdf")


@app.post("/api/pdf/repair")
async def repair_pdf(file: UploadFile = File(...)):
    with tempfile.TemporaryDirectory(prefix="pdfglobe-") as td:
        folder = Path(td)
        src = await store_upload(file, folder, {".pdf"})
        out = folder / f"{safe_name(file.filename)}_repaired.pdf"
        try:
            doc = fitz.open(src)
            doc.save(out, garbage=4, deflate=True, clean=True)
            doc.close()
        except Exception as exc:
            raise HTTPException(status_code=422, detail=f"تعذر إصلاح الملف: {exc}")
        return download_response(out, out.name, "application/pdf")


def split_character_chunks(paragraph: str, max_chars: int) -> list[str]:
    """Split long text at word boundaries, with a hard character fallback."""
    text = paragraph.strip()
    if not text:
        return []
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + max_chars, len(text))
        if end < len(text):
            cut = text.rfind(" ", start, end)
            if cut > start:
                end = cut
        piece = text[start:end].strip()
        if piece:
            chunks.append(piece)
        start = end
        while start < len(text) and text[start].isspace():
            start += 1
    return chunks


def split_utf8_chunks(paragraph: str, max_bytes: int = 450) -> list[str]:
    """Split a paragraph into chunks that stay below MyMemory's 500-byte q limit.

    Count UTF-8 bytes rather than Python characters; Arabic and many other scripts
    use multiple bytes per character. Prefer word boundaries, but split a single
    oversized token safely at Unicode character boundaries when necessary.
    """
    text = paragraph.strip()
    if not text:
        return []
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = start
        used = 0
        last_space = -1
        while end < len(text):
            char_size = len(text[end].encode("utf-8"))
            if used + char_size > max_bytes:
                break
            used += char_size
            if text[end].isspace():
                last_space = end
            end += 1
        if end == len(text):
            piece = text[start:end].strip()
            if piece:
                chunks.append(piece)
            break
        if end == start:
            # Defensive guard: max_bytes is much larger than one UTF-8 code point.
            raise ValueError("تعذر تقسيم النص إلى أجزاء صالحة لمحرك الترجمة")
        if last_space >= start:
            cut = last_space
            piece = text[start:cut].strip()
            next_start = last_space + 1
        else:
            # A single word/token is larger than the provider limit.
            piece = text[start:end].strip()
            next_start = end
        if piece:
            chunks.append(piece)
        start = next_start
    return chunks


async def translate_chunk(text: str, source: str, target: str) -> str:
    # Primary option: Cloudflare-hosted Meta M2M100 translation model.
    # The model supports Arabic and many other languages; credentials stay on Render.
    if CLOUDFLARE_ACCOUNT_ID or CLOUDFLARE_API_TOKEN:
        if not (CLOUDFLARE_ACCOUNT_ID and CLOUDFLARE_API_TOKEN):
            raise HTTPException(
                status_code=503,
                detail="إعداد Cloudflare غير مكتمل. أضف CLOUDFLARE_ACCOUNT_ID وCLOUDFLARE_API_TOKEN معاً في Render.",
            )
        if source == "auto":
            raise HTTPException(
                status_code=400,
                detail="اختر لغة المصدر صراحةً عند استخدام محرك Cloudflare؛ وضع الكشف التلقائي غير مدعوم في هذا النموذج.",
            )
        url = (
            "https://api.cloudflare.com/client/v4/accounts/"
            f"{CLOUDFLARE_ACCOUNT_ID}/ai/run/{CLOUDFLARE_TRANSLATION_MODEL}"
        )
        payload = {"text": text, "source_lang": source, "target_lang": target}
        headers = {"Authorization": f"Bearer {CLOUDFLARE_API_TOKEN}", "Content-Type": "application/json"}
        try:
            async with httpx.AsyncClient(timeout=90, follow_redirects=True) as client:
                response = await client.post(url, json=payload, headers=headers)
        except httpx.TimeoutException as exc:
            raise HTTPException(status_code=504, detail="انتهت مهلة الاتصال بمحرك Cloudflare AI. حاول مجدداً بعد قليل") from exc
        except httpx.RequestError as exc:
            raise HTTPException(status_code=502, detail="تعذر الاتصال بمحرك Cloudflare AI من الخادم. تحقق من الاتصال وحاول لاحقاً") from exc

        try:
            data = response.json()
        except ValueError as exc:
            raise HTTPException(status_code=502, detail="أعاد Cloudflare استجابة غير مفهومة") from exc

        errors = data.get("errors") or []
        error_text = " ".join(str(item.get("message", item)) for item in errors) if isinstance(errors, list) else str(errors)
        lowered = error_text.lower()
        if response.status_code == 429 or "3036" in error_text or "daily free allocation" in lowered or "neurons" in lowered:
            raise HTTPException(
                status_code=503,
                detail="تم استهلاك الحصة المجانية اليومية لـ Cloudflare Workers AI (10,000 Neurons). تتجدد الحصة يومياً؛ حاول في اليوم التالي.",
            )
        if response.status_code >= 500:
            raise HTTPException(status_code=503, detail=f"محرك Cloudflare AI يواجه عطلاً مؤقتاً (HTTP {response.status_code}). حاول لاحقاً")
        if response.status_code >= 400 or data.get("success") is False or errors:
            detail = error_text[:240] or f"HTTP {response.status_code}"
            raise HTTPException(status_code=502, detail=f"رفض Cloudflare طلب الترجمة: {detail}")

        translated = (data.get("result") or {}).get("translated_text")
        if not translated:
            raise HTTPException(status_code=502, detail="لم يرجع نموذج Cloudflare M2M100 نصاً مترجماً")
        return str(translated)

    # Optional self-hosted LibreTranslate endpoint, if an operator configures one.
    if LIBRETRANSLATE_URL:
        payload = {"q": text, "source": source, "target": target, "format": "text"}
        if LIBRETRANSLATE_API_KEY:
            payload["api_key"] = LIBRETRANSLATE_API_KEY
        async with httpx.AsyncClient(timeout=60, follow_redirects=True) as client:
            try:
                response = await client.post(f"{LIBRETRANSLATE_URL}/translate", data=payload)
                response.raise_for_status()
                data = response.json()
            except httpx.TimeoutException as exc:
                raise HTTPException(status_code=504, detail="انتهت مهلة الاتصال بمحرك LibreTranslate. حاول مجدداً بعد قليل") from exc
            except httpx.RequestError as exc:
                raise HTTPException(status_code=502, detail="تعذر الوصول إلى خادم LibreTranslate. تحقق من عنوان الخدمة وإعداداتها في Render") from exc
            except ValueError as exc:
                raise HTTPException(status_code=502, detail="أعاد LibreTranslate استجابة غير مفهومة") from exc
        if not data.get("translatedText"):
            raise HTTPException(status_code=502, detail="استقبل الموقع رداً من LibreTranslate لكنه لا يحتوي على نص مترجم")
        return data["translatedText"]

    # Fallback option: MyMemory, subject to its independent daily usage limits.
    if len(text.encode("utf-8")) > 450:
        raise HTTPException(status_code=413, detail="جزء النص أكبر من الحد الآمن لمحرك MyMemory. أعد المحاولة بعد تحديث الموقع")
    if source == "auto":
        raise HTTPException(status_code=400, detail="اختر لغة المصدر بدلاً من (تلقائي) عند استخدام محرك MyMemory المجاني")

    params = {"q": text, "langpair": f"{source}|{target}"}
    if MYMEMORY_CONTACT_EMAIL:
        params["de"] = MYMEMORY_CONTACT_EMAIL
    try:
        async with httpx.AsyncClient(timeout=45, follow_redirects=True, headers={"User-Agent": "PDF-Globe/1.2"}) as client:
            response = await client.get("https://api.mymemory.translated.net/get", params=params)
    except httpx.TimeoutException as exc:
        raise HTTPException(status_code=504, detail="انتهت مهلة الاتصال بمحرك MyMemory. حاول مجدداً بعد قليل") from exc
    except httpx.RequestError as exc:
        raise HTTPException(status_code=502, detail="تعذر الوصول إلى خادم MyMemory من Render. قد تكون الخدمة الخارجية غير متاحة مؤقتاً") from exc

    if response.status_code == 429:
        raise HTTPException(status_code=503, detail="محرك MyMemory رفض الطلب بسبب حد الاستخدام أو كثرة الطلبات. انتظر ثم حاول لاحقاً")
    if response.status_code >= 500:
        raise HTTPException(status_code=503, detail=f"محرك MyMemory يواجه عطلاً مؤقتاً (HTTP {response.status_code}). حاول لاحقاً")
    if response.status_code >= 400:
        raise HTTPException(status_code=502, detail=f"محرك MyMemory رفض الطلب (HTTP {response.status_code}). تحقق من اللغات وحجم النص")

    try:
        data = response.json()
    except ValueError as exc:
        raise HTTPException(status_code=502, detail="أعاد محرك MyMemory استجابة غير مفهومة") from exc

    try:
        provider_status = int(data.get("responseStatus", 0))
    except (TypeError, ValueError):
        provider_status = 0
    if provider_status != 200:
        details = str(data.get("responseDetails") or "محرك الترجمة لم يقبل الطلب")
        low = details.lower()
        quota_terms = ("quota", "daily", "limit", "too many", "available free", "exceeded")
        if any(term in low for term in quota_terms):
            raise HTTPException(status_code=503, detail="تم تجاوز الحصة المجانية لمحرك MyMemory أو حد الطلبات. انتظر تجدد الحصة أو اضبط MYMEMORY_CONTACT_EMAIL في Render لرفع الحد اليومي المعلن من المزود")
        raise HTTPException(status_code=502, detail=f"محرك MyMemory رفض طلب الترجمة: {details[:220]}")

    translated = data.get("responseData", {}).get("translatedText")
    if not translated:
        raise HTTPException(status_code=502, detail="لم يرجع محرك MyMemory نصاً مترجماً")
    return html.unescape(translated)


async def translate_long_text(text: str, source: str, target: str) -> str:
    chunks: list[str] = []
    if CLOUDFLARE_ACCOUNT_ID and CLOUDFLARE_API_TOKEN:
        # M2M100 has a finite model context; keep pieces conservative, especially for Arabic.
        max_chars = 700
        for paragraph in text.splitlines():
            if not paragraph.strip():
                chunks.append("")
            else:
                chunks.extend(split_character_chunks(paragraph, max_chars=max_chars))
    elif LIBRETRANSLATE_URL:
        # LibreTranslate's accepted request size depends on the configured instance.
        max_chars = 4500
        for paragraph in text.splitlines():
            if not paragraph.strip():
                chunks.append("")
            else:
                chunks.extend(split_character_chunks(paragraph, max_chars=max_chars))
    else:
        # MyMemory documents a 500-byte maximum for q. Use 450 bytes for headroom.
        for paragraph in text.splitlines():
            if not paragraph.strip():
                chunks.append("")
            else:
                chunks.extend(split_utf8_chunks(paragraph, max_bytes=450))

    translated: list[str] = []
    for chunk in chunks:
        if not chunk:
            translated.append("")
        else:
            translated.append(await translate_chunk(chunk, source, target))
    return "\n".join(translated)


@app.post("/api/translate")
async def translate_api(payload: dict):
    text_value = str(payload.get("text", ""))
    source = str(payload.get("source", "auto")).lower()
    target = str(payload.get("target", "ar")).lower()
    if not text_value.strip():
        raise HTTPException(status_code=400, detail="لا يوجد نص لترجمته")
    if CLOUDFLARE_ACCOUNT_ID and CLOUDFLARE_API_TOKEN:
        limit = 100_000
        limit_label = "100 ألف حرف لكل طلب"
    elif LIBRETRANSLATE_URL:
        limit = 100_000
        limit_label = "100 ألف حرف"
    else:
        limit = 4_000
        limit_label = "4 آلاف حرف في وضع الترجمة المجانية الاحتياطي"
    if len(text_value) > limit:
        raise HTTPException(status_code=413, detail=f"النص يتجاوز الحد الحالي ({limit_label}). قسّم المستند إلى أجزاء أصغر")
    try:
        result = await translate_long_text(text_value, source, target)
        provider = translation_provider_name()
        notice = "راجع الأسماء والأرقام والمصطلحات قبل اعتماد الترجمة النهائية."
        if provider.startswith("Cloudflare"):
            notice += " الحصة المجانية لـ Cloudflare Workers AI محدودة يومياً وقد تتوقف الترجمة عند استنفادها."
        return {"translated_text": result, "provider": provider, "notice": notice}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"تعذر الاتصال بمحرك الترجمة: {str(exc)[:300]}")


@app.post("/api/translate/docx")
async def translated_docx(payload: dict):
    translated = str(payload.get("translated_text", ""))
    target = str(payload.get("target", "translated"))
    if not translated.strip():
        raise HTTPException(status_code=400, detail="النص المترجم فارغ")
    with tempfile.TemporaryDirectory(prefix="pdfglobe-") as td:
        out = Path(td) / "translated_document.docx"
        doc = Document()
        section = doc.sections[0]
        section.top_margin = section.bottom_margin = 720000  # 0.79in
        rtl_codes = {"ar", "ur", "fa", "he"}
        for line in translated.splitlines():
            paragraph = doc.add_paragraph(line)
            if target.lower() in rtl_codes:
                from docx.oxml import OxmlElement
                ppr = paragraph._p.get_or_add_pPr()
                bidi = OxmlElement("w:bidi")
                bidi.set("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}val", "1")
                ppr.append(bidi)
        doc.core_properties.title = "PDF Globe translated document"
        doc.save(out)
        return download_response(out, f"translated_{safe_name(target)}.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document")


@app.get("/api/languages")
async def languages():
    if LIBRETRANSLATE_URL:
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                response = await client.get(f"{LIBRETRANSLATE_URL}/languages")
                response.raise_for_status()
                data = response.json()
                return {"provider": "LibreTranslate", "languages": data}
        except Exception:
            pass
    return {"provider": translation_provider_name(), "languages": [
        {"code": "ar", "name": "Arabic"}, {"code": "en", "name": "English"}, {"code": "fr", "name": "French"},
        {"code": "es", "name": "Spanish"}, {"code": "de", "name": "German"}, {"code": "it", "name": "Italian"},
        {"code": "pt", "name": "Portuguese"}, {"code": "tr", "name": "Turkish"}, {"code": "ur", "name": "Urdu"},
        {"code": "hi", "name": "Hindi"}, {"code": "zh", "name": "Chinese"}, {"code": "ja", "name": "Japanese"},
        {"code": "ko", "name": "Korean"}, {"code": "ru", "name": "Russian"}, {"code": "nl", "name": "Dutch"},
        {"code": "pl", "name": "Polish"}, {"code": "sv", "name": "Swedish"}, {"code": "fa", "name": "Persian"},
        {"code": "id", "name": "Indonesian"}, {"code": "ms", "name": "Malay"}, {"code": "uk", "name": "Ukrainian"},
        {"code": "el", "name": "Greek"}, {"code": "he", "name": "Hebrew"}, {"code": "vi", "name": "Vietnamese"}
    ]}


app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
