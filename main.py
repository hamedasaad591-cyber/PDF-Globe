from __future__ import annotations

import os
import re
import html
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
    expose_headers=["X-PDF-Globe-Hybrid-Editable-Pages", "X-PDF-Globe-Hybrid-Image-Pages"],
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


@app.post("/api/pdf/to-word")
async def pdf_to_word(file: UploadFile = File(...), mode: str = Form("hybrid")):
    mode = (mode or "layout").strip().lower()
    if mode not in {"layout", "editable", "hybrid"}:
        raise HTTPException(status_code=400, detail="اختر طريقة التحويل: هجين، أو الحفاظ على شكل الصفحات، أو استخراج النص القابل للتحرير")
    with tempfile.TemporaryDirectory(prefix="pdfglobe-") as td:
        folder = Path(td)
        src = await store_upload(file, folder, {".pdf"})
        out = folder / f"{safe_name(file.filename)}.docx"

        if mode == "hybrid":
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
