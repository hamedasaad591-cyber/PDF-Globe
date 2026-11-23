"""Smoke-test the deployed Render API using synthetic, non-sensitive files."""
from __future__ import annotations

import io
import os
import sys
import time
import unicodedata
import zipfile
from pathlib import Path

import fitz
import httpx
import numpy as np
import pydicom
from docx import Document
from docx.shared import Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from openpyxl import Workbook, load_workbook
from PIL import Image
from pptx import Presentation
from pydicom.dataset import FileDataset, FileMetaDataset
from pydicom.uid import ExplicitVRLittleEndian, SecondaryCaptureImageStorage, generate_uid


BASE_URL = os.getenv("PDF_GLOBE_API_URL", "https://pdf-globe.onrender.com").rstrip("/")
DWG_PATH = Path(os.getenv("PDF_GLOBE_DWG_FIXTURE", "/tmp/pdf-globe-line.dwg"))


def check(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def make_pdf() -> bytes:
    doc = fitz.open()
    page = doc.new_page(width=360, height=260)
    page.insert_text((35, 45), "PDF Globe LIVE deployment test", fontsize=18)
    page.insert_text((35, 90), "Item       Quantity       Price", fontsize=12)
    page.insert_text((35, 115), "Paper      12              4.50", fontsize=12)
    page.insert_text((35, 140), "Pens       5               2.00", fontsize=12)
    data = doc.tobytes(garbage=4, deflate=True)
    doc.close()
    return data



def _set_rtl_paragraph(paragraph) -> None:
    paragraph.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    ppr = paragraph._p.get_or_add_pPr()
    bidi = OxmlElement("w:bidi")
    bidi.set(qn("w:val"), "1")
    ppr.append(bidi)
    for run in paragraph.runs:
        run.font.name = "DejaVu Sans"
        rpr = run._element.get_or_add_rPr()
        rfonts = rpr.rFonts
        if rfonts is None:
            rfonts = OxmlElement("w:rFonts")
            rpr.insert(0, rfonts)
        for key in ("ascii", "hAnsi", "cs", "eastAsia"):
            rfonts.set(qn(f"w:{key}"), "DejaVu Sans")


def make_arabic_quality_docx() -> bytes:
    """Create a non-sensitive, two-page Arabic document with a real bordered table."""
    document = Document()
    section = document.sections[0]
    section.top_margin = Inches(0.55)
    section.bottom_margin = Inches(0.55)
    section.left_margin = Inches(0.6)
    section.right_margin = Inches(0.6)

    heading = document.add_heading("اختبار جودة اللغة العربية - PDF Globe", level=1)
    _set_rtl_paragraph(heading)
    intro = document.add_paragraph("هذا مستند تجريبي للتحقق من اتجاه الكتابة العربية واستخراج الجداول والأرقام.")
    _set_rtl_paragraph(intro)

    table = document.add_table(rows=1, cols=3)
    table.style = "Table Grid"
    try:
        table_pr = table._tbl.tblPr
        bidi_visual = OxmlElement("w:bidiVisual")
        bidi_visual.set(qn("w:val"), "1")
        table_pr.append(bidi_visual)
    except Exception:
        pass

    rows = [
        ("الصنف", "الكمية", "السعر"),
        ("ورق A4", "12", "15.50"),
        ("حبر أسود", "3", "48.00"),
        ("أقلام زرقاء", "25", "2.75"),
    ]
    for row_index, values in enumerate(rows):
        cells = table.rows[0].cells if row_index == 0 else table.add_row().cells
        for cell, value in zip(cells, values):
            cell.text = value
            for paragraph in cell.paragraphs:
                _set_rtl_paragraph(paragraph)
                for run in paragraph.runs:
                    if row_index == 0:
                        run.bold = True

    document.add_page_break()
    second = document.add_heading("الصفحة الثانية - نتائج الاختبار", level=2)
    _set_rtl_paragraph(second)
    paragraph = document.add_paragraph(
        "يجب أن تبقى الكلمات العربية واضحة، وأن تحتفظ الأرقام بقيمها، "
        "وأن يكون اتجاه الفقرات من اليمين إلى اليسار."
    )
    _set_rtl_paragraph(paragraph)
    paragraph = document.add_paragraph("مرجع الاختبار: AR-PDFG-2026-11-22")
    _set_rtl_paragraph(paragraph)

    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def _arabic_char_count(value: str) -> int:
    return sum(1 for character in value if "\u0600" <= character <= "\u06ff")


def _normal_text(value: str) -> str:
    return unicodedata.normalize("NFKC", value or "")


def test_arabic_conversion_quality(client: httpx.Client) -> None:
    """Exercise RTL text, bordered tables, editable Word and scanned-page fallbacks on live Render."""
    source_docx = make_arabic_quality_docx()
    response = post_with_retry(
        client,
        f"{BASE_URL}/api/word/to-pdf",
        files={"file": ("arabic-quality-test.docx", source_docx,
                        "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
    )
    expect_pdf(response, "Arabic Word-to-PDF")

    with fitz.open(stream=response.content, filetype="pdf") as source_pdf:
        check(source_pdf.page_count >= 2, "Arabic Word-to-PDF lost the second page")
        source_text = _normal_text("\n".join(page.get_text("text", sort=True) for page in source_pdf))
        check(_arabic_char_count(source_text) >= 30, "Arabic Word-to-PDF output lost most Arabic text")
        check("15.50" in source_text and "48.00" in source_text and "AR-PDFG-2026-11-22" in source_text,
              "Arabic Word-to-PDF lost table values or the page-two reference")
        tables = []
        for page in source_pdf:
            try:
                tables.extend(list(page.find_tables().tables))
            except Exception:
                pass
        check(any(getattr(table, "row_count", 0) >= 3 and getattr(table, "col_count", 0) >= 3
                  for table in tables),
              "Arabic Word-to-PDF did not preserve a detectable 3-column table")
    arabic_pdf = response.content
    print("PASS Arabic Word-to-PDF: RTL text, 2 pages, table geometry and numeric values")

    response = post_with_retry(
        client,
        f"{BASE_URL}/api/pdf/to-excel",
        files={"file": ("arabic-quality-test.pdf", arabic_pdf, "application/pdf")},
    )
    check(response.status_code == 200, f"Arabic PDF-to-Excel failed: {response.status_code}: {response.text[:300]}")
    workbook = load_workbook(io.BytesIO(response.content), read_only=False, data_only=False)
    table_sheets = [sheet for sheet in workbook.worksheets if sheet.title.startswith("Page ") and " Table " in sheet.title]
    check(bool(table_sheets), "Arabic PDF-to-Excel did not create a dedicated extracted-table worksheet")
    sheet_values = [
        _normal_text(str(cell.value or ""))
        for sheet in table_sheets
        for row in sheet.iter_rows()
        for cell in row
    ]
    joined_values = " ".join(sheet_values)
    check(_arabic_char_count(joined_values) >= 10, "Arabic PDF-to-Excel lost Arabic table labels or item names")
    check(all(value in joined_values for value in ("12", "15.50", "48.00", "2.75")),
          "Arabic PDF-to-Excel lost one or more table quantities/prices")
    workbook.close()
    print("PASS Arabic PDF-to-Excel: table worksheet, Arabic cells and all four numeric values")

    response = post_with_retry(
        client,
        f"{BASE_URL}/api/pdf/to-word",
        files={"file": ("arabic-quality-test.pdf", arabic_pdf, "application/pdf")},
        data={"mode": "structured"},
    )
    check(response.status_code == 200, f"Arabic structured PDF-to-Word failed: {response.status_code}: {response.text[:300]}")
    check(int(response.headers.get("X-PDF-Globe-Structured-Table-Pages", "0")) >= 1,
          "Structured PDF-to-Word did not report an editable table page")
    structured_doc = Document(io.BytesIO(response.content))
    structured_values = " ".join(
        _normal_text(cell.text)
        for table in structured_doc.tables
        for row in table.rows
        for cell in row.cells
    )
    check(len(structured_doc.tables) >= 1, "Structured PDF-to-Word did not create a native Word table")
    check(_arabic_char_count(structured_values) >= 10, "Structured PDF-to-Word lost Arabic table content")
    check(all(value in structured_values for value in ("12", "15.50", "48.00")),
          "Structured PDF-to-Word lost quantities or prices in its editable table")
    print("PASS Arabic structured PDF-to-Word: editable Word table, RTL text and numeric values")

    response = post_with_retry(
        client,
        f"{BASE_URL}/api/pdf/to-word",
        files={"file": ("arabic-quality-test.pdf", arabic_pdf, "application/pdf")},
        data={"mode": "hybrid"},
    )
    check(response.status_code == 200, f"Arabic hybrid PDF-to-Word failed: {response.status_code}: {response.text[:300]}")
    check(int(response.headers.get("X-PDF-Globe-Hybrid-Image-Pages", "0")) >= 1,
          "Hybrid PDF-to-Word did not preserve the complex table page as an image")
    hybrid_doc = Document(io.BytesIO(response.content))
    check(len(hybrid_doc.inline_shapes) >= 1, "Hybrid PDF-to-Word did not embed the original table page")
    check(int(response.headers.get("X-PDF-Globe-Hybrid-Editable-Pages", "0")) >= 1,
          "Hybrid PDF-to-Word did not retain simple text pages as editable content")
    print("PASS Arabic hybrid PDF-to-Word: complex page preserved visually and simple page editable")

    response = post_with_retry(
        client,
        f"{BASE_URL}/api/pdf/to-powerpoint",
        files={"file": ("arabic-quality-test.pdf", arabic_pdf, "application/pdf")},
    )
    check(response.status_code == 200, f"Arabic PDF-to-PowerPoint failed: {response.status_code}: {response.text[:300]}")
    presentation = Presentation(io.BytesIO(response.content))
    check(len(presentation.slides) == 2, "Arabic PDF-to-PowerPoint did not create one slide per source page")
    check(all(any(shape.shape_type == 13 for shape in slide.shapes) for slide in presentation.slides),
          "Arabic PDF-to-PowerPoint slide is missing its rendered page image")
    print("PASS Arabic PDF-to-PowerPoint: two slides with page images")

    # A scanned image-only page must not be presented as editable text without OCR.
    scan_buffer = io.BytesIO()
    scan = Image.new("RGB", (900, 1200), "white")
    from PIL import ImageDraw
    draw = ImageDraw.Draw(scan)
    draw.text((60, 70), "SCANNED PDF GLOBE TEST 2026", fill="black")
    scan.save(scan_buffer, format="PNG")
    scan.close()
    scanned_pdf_doc = fitz.open()
    scan_page = scanned_pdf_doc.new_page(width=595, height=842)
    scan_page.insert_image(scan_page.rect, stream=scan_buffer.getvalue())
    scanned_bytes = scanned_pdf_doc.tobytes(garbage=4, deflate=True)
    scanned_pdf_doc.close()

    response = post_with_retry(
        client,
        f"{BASE_URL}/api/pdf/to-word",
        files={"file": ("scanned-quality-test.pdf", scanned_bytes, "application/pdf")},
        data={"mode": "structured"},
    )
    check(response.status_code == 200, f"Scanned PDF-to-Word failed: {response.status_code}: {response.text[:300]}")
    check(int(response.headers.get("X-PDF-Globe-Structured-Image-Pages", "0")) == 1,
          "Scanned PDF-to-Word did not identify the image-only page fallback")
    scanned_doc = Document(io.BytesIO(response.content))
    check(len(scanned_doc.inline_shapes) >= 1, "Scanned PDF-to-Word did not preserve the scanned page image")
    print("PASS scanned PDF-to-Word: image-only page preserved and correctly not claimed as editable text")

    response = post_with_retry(
        client,
        f"{BASE_URL}/api/pdf/to-excel",
        files={"file": ("scanned-quality-test.pdf", scanned_bytes, "application/pdf")},
    )
    check(response.status_code == 200, f"Scanned PDF-to-Excel failed: {response.status_code}: {response.text[:300]}")
    scanned_workbook = load_workbook(io.BytesIO(response.content), read_only=True)
    guide = scanned_workbook["Read me"]
    guide_text = " ".join(str(cell.value or "") for row in guide.iter_rows() for cell in row)
    check("No selectable text or tables" in guide_text,
          "Scanned PDF-to-Excel did not explain that OCR is required")
    scanned_workbook.close()
    print("PASS scanned PDF-to-Excel: clearly reports that OCR is required")

def make_png() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (64, 48), (210, 55, 95)).save(buffer, format="PNG")
    return buffer.getvalue()


def make_dicom() -> bytes:
    meta = FileMetaDataset()
    meta.MediaStorageSOPClassUID = SecondaryCaptureImageStorage
    meta.MediaStorageSOPInstanceUID = generate_uid()
    meta.TransferSyntaxUID = ExplicitVRLittleEndian
    meta.ImplementationClassUID = generate_uid()
    ds = FileDataset(None, {}, file_meta=meta, preamble=b"\0" * 128)
    ds.SOPClassUID = meta.MediaStorageSOPClassUID
    ds.SOPInstanceUID = meta.MediaStorageSOPInstanceUID
    ds.StudyInstanceUID = generate_uid()
    ds.SeriesInstanceUID = generate_uid()
    ds.Modality = "OT"
    ds.Rows = 2
    ds.Columns = 2
    ds.SamplesPerPixel = 1
    ds.PhotometricInterpretation = "MONOCHROME2"
    ds.BitsAllocated = 8
    ds.BitsStored = 8
    ds.HighBit = 7
    ds.PixelRepresentation = 0
    ds.InstanceNumber = 1
    ds.PixelData = np.array([[0, 80], [160, 255]], dtype=np.uint8).tobytes()
    buffer = io.BytesIO()
    ds.save_as(buffer, enforce_file_format=True)
    return buffer.getvalue()


def make_office_files() -> tuple[bytes, bytes, bytes]:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Items"
    sheet.append(["Item", "Quantity"])
    sheet.append(["Paper", 12])
    xlsx = io.BytesIO()
    workbook.save(xlsx)

    presentation = Presentation()
    slide = presentation.slides.add_slide(presentation.slide_layouts[6])
    slide.shapes.add_textbox(50000, 50000, 300000, 80000).text = "PDF Globe live PowerPoint test"
    pptx = io.BytesIO()
    presentation.save(pptx)

    word = Document()
    word.add_paragraph("PDF Globe live Word-to-PDF test")
    docx = io.BytesIO()
    word.save(docx)
    return xlsx.getvalue(), pptx.getvalue(), docx.getvalue()


def post_with_retry(client: httpx.Client, url: str, **kwargs) -> httpx.Response:
    """Retry only transient transport/gateway failures during Render deploy swaps."""
    last_response = None
    for attempt in range(5):
        try:
            response = client.post(url, **kwargs)
            last_response = response
            if response.status_code not in {502, 503, 504}:
                return response
            message = f"HTTP {response.status_code}"
        except httpx.TransportError as exc:
            message = str(exc)[:200]
            if attempt == 4:
                raise
        if attempt == 4:
            break
        delay = min(3 * (attempt + 1), 10)
        print(f"WARNING transient Render response ({message}); retrying in {delay}s ({attempt + 1}/4)")
        time.sleep(delay)
    return last_response


def expect_pdf(response: httpx.Response, label: str) -> None:
    check(response.status_code == 200, f"{label}: HTTP {response.status_code}: {response.text[:400]}")
    check(response.content.startswith(b"%PDF-"), f"{label}: response is not a PDF")
    with fitz.open(stream=response.content, filetype="pdf") as pdf:
        check(pdf.page_count > 0, f"{label}: PDF contains no pages")


def wait_for_ready(client: httpx.Client) -> dict:
    deadline = time.monotonic() + 240
    last_error = "health endpoint has not responded"
    while time.monotonic() < deadline:
        try:
            response = client.get(f"{BASE_URL}/api/health")
            if response.status_code == 200:
                data = response.json()
                caps = data.get("capabilities", {})
                required = (
                    "compress_pdf", "pdf_to_word", "pdf_to_excel", "pdf_to_powerpoint",
                    "word_to_pdf", "excel_to_pdf", "powerpoint_to_pdf", "dicom_to_pdf",
                    "image_conversion", "dwg_to_pdf", "protect_pdf", "unlock_pdf",
                )
                missing = [name for name in required if not caps.get(name)]
                if data.get("ok") is True and not missing:
                    return data
                last_error = "API is alive but capabilities are not ready yet: " + ", ".join(missing)
            else:
                last_error = f"HTTP {response.status_code}: {response.text[:200]}"
        except Exception as exc:
            last_error = str(exc)
        time.sleep(5)
    raise RuntimeError(f"Render API did not become ready within 240 seconds: {last_error}")


def main() -> None:
    check(DWG_PATH.is_file() and DWG_PATH.stat().st_size > 1000, f"Real DWG fixture is missing or too small: {DWG_PATH}")
    pdf = make_pdf()
    png = make_png()
    dicom = make_dicom()
    xlsx, pptx, docx = make_office_files()

    with httpx.Client(timeout=httpx.Timeout(120, connect=20), follow_redirects=True) as client:
        health = wait_for_ready(client)
        print("PASS deployed API health and capabilities:", ", ".join(sorted(k for k, v in health["capabilities"].items() if v)))
        print("INFO deployed translation provider:", health.get("translation_provider"))

        cors = client.options(
            f"{BASE_URL}/api/office/excel-to-pdf",
            headers={
                "Origin": "https://pdf-globe.pages.dev",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type",
            },
        )
        check(cors.status_code in (200, 204), f"CORS preflight failed: HTTP {cors.status_code}")
        check(cors.headers.get("access-control-allow-origin") == "https://pdf-globe.pages.dev", "CORS does not allow the production Pages origin")
        print("PASS deployed CORS preflight for Cloudflare Pages origin")

        one_file = {"file": ("live-test.pdf", pdf, "application/pdf")}
        response = post_with_retry(client, f"{BASE_URL}/api/pdf/compress", files=one_file)
        expect_pdf(response, "live PDF compression")
        compression_result = response.headers.get("X-PDF-Globe-Compression-Result")
        original_size = int(response.headers.get("X-PDF-Globe-Original-Bytes", "0"))
        output_size = int(response.headers.get("X-PDF-Globe-Output-Bytes", "0"))
        check(compression_result in {"compressed", "unchanged"}, "live PDF compression metadata is missing or invalid")
        check(original_size == len(pdf), "live PDF compression reported an incorrect original size")
        check(output_size == len(response.content), "live PDF compression reported an incorrect output size")
        if compression_result == "compressed":
            check(output_size < original_size, "live compression claimed a size reduction but returned a larger/equal PDF")
        else:
            check(response.content == pdf, "live compression should preserve the original when there is no size reduction")
        response = post_with_retry(client, f"{BASE_URL}/api/pdf/repair", files=one_file)
        expect_pdf(response, "live PDF repair")

        response = post_with_retry(client, 
            f"{BASE_URL}/api/pdf/to-word",
            files=one_file,
            data={"mode": "hybrid"},
        )
        check(response.status_code == 200, f"live PDF-to-Word failed: {response.status_code} {response.text[:300]}")
        word_result = Document(io.BytesIO(response.content))
        check(len(word_result.paragraphs) > 0 or len(word_result.inline_shapes) > 0, "live PDF-to-Word returned an empty DOCX")

        response = post_with_retry(client, f"{BASE_URL}/api/pdf/to-excel", files=one_file)
        check(response.status_code == 200, f"live PDF-to-Excel failed: {response.status_code} {response.text[:300]}")
        wb = load_workbook(io.BytesIO(response.content), read_only=True)
        check("Read me" in wb.sheetnames, "live PDF-to-Excel workbook is missing its guide")
        wb.close()

        response = post_with_retry(client, f"{BASE_URL}/api/pdf/to-powerpoint", files=one_file)
        check(response.status_code == 200, f"live PDF-to-PowerPoint failed: {response.status_code} {response.text[:300]}")
        pres = Presentation(io.BytesIO(response.content))
        check(len(pres.slides) == 1 and len(pres.slides[0].shapes) > 0, "live PDF-to-PowerPoint output is empty")
        print("PASS deployed PDF compression, repair, Word, Excel and PowerPoint outputs")

        response = post_with_retry(client, 
            f"{BASE_URL}/api/pdf/protect",
            files=one_file,
            data={"password": "GlobeTest2026"},
        )
        check(response.status_code == 200, f"live PDF protection failed: {response.status_code} {response.text[:300]}")
        protected = response.content
        with fitz.open(stream=protected, filetype="pdf") as secured:
            check(secured.is_encrypted, "live protected PDF is not encrypted")
        response = post_with_retry(client, 
            f"{BASE_URL}/api/pdf/unlock",
            files={"file": ("protected.pdf", protected, "application/pdf")},
            data={"password": "GlobeTest2026"},
        )
        expect_pdf(response, "live PDF unlock")
        print("PASS deployed PDF protection and unlocking")

        image = {"files": ("live-test.png", png, "image/png")}
        response = post_with_retry(client, f"{BASE_URL}/api/image/convert", files=image, data={"output_format": "webp", "quality": "86"})
        check(response.status_code == 200, f"live PNG-to-WebP failed: {response.status_code} {response.text[:300]}")
        with Image.open(io.BytesIO(response.content)) as img:
            check(img.format == "WEBP" and img.size == (64, 48), "live PNG-to-WebP output is invalid")

        cmyk_buffer = io.BytesIO()
        Image.new("CMYK", (64, 48), (0, 100, 100, 0)).save(cmyk_buffer, format="JPEG")
        response = post_with_retry(
            client,
            f"{BASE_URL}/api/image/convert",
            files={"files": ("live-cmyk.jpg", cmyk_buffer.getvalue(), "image/jpeg")},
            data={"output_format": "png"},
        )
        check(response.status_code == 200, f"live CMYK JPEG-to-PNG failed: {response.status_code} {response.text[:300]}")
        with Image.open(io.BytesIO(response.content)) as img:
            check(img.format == "PNG" and img.mode in {"RGB", "RGBA"} and img.size == (64, 48),
                  "live CMYK JPEG-to-PNG output is invalid")

        response = post_with_retry(client, f"{BASE_URL}/api/image/convert", files=image, data={"output_format": "pdf"})
        expect_pdf(response, "live image-to-PDF")
        print("PASS deployed image conversion, resizing pipeline and image-to-PDF response")

        # Exercise every image-studio operation on the deployed API using synthetic files.
        resize_response = post_with_retry(
            client,
            f"{BASE_URL}/api/image/convert",
            files={"files": ("studio-resize.png", png, "image/png")},
            data={"output_format": "png", "width": "32", "height": "24",
                  "keep_aspect": "true", "quality": "88"},
        )
        check(resize_response.status_code == 200,
              f"live image resize failed: {resize_response.status_code} {resize_response.text[:250]}")
        with Image.open(io.BytesIO(resize_response.content)) as resized:
            check(resized.format == "PNG" and resized.size == (32, 24),
                  f"live image resize returned unexpected output: {resized.format} {resized.size}")
        print("PASS deployed image resize: exact pixel dimensions and PNG output")

        noise = np.random.default_rng(20261123).integers(0, 256, (256, 256, 3), dtype=np.uint8)
        noise_buffer = io.BytesIO()
        Image.fromarray(noise, mode="RGB").save(noise_buffer, format="PNG", optimize=False)
        noise_png = noise_buffer.getvalue()
        compressed_outputs = {}
        for quality_value in (25, 92):
            compressed = post_with_retry(
                client,
                f"{BASE_URL}/api/image/convert",
                files={"files": (f"studio-quality-{quality_value}.png", noise_png, "image/png")},
                data={"output_format": "webp", "quality": str(quality_value)},
            )
            check(compressed.status_code == 200,
                  f"live image compression quality {quality_value} failed: {compressed.status_code} {compressed.text[:250]}")
            with Image.open(io.BytesIO(compressed.content)) as converted:
                check(converted.format == "WEBP" and converted.size == (256, 256),
                      f"live image compression returned invalid WebP at quality {quality_value}")
                compressed_outputs[quality_value] = (len(compressed.content), np.asarray(converted.convert("RGB")).copy())
        check(compressed_outputs[25][0] < compressed_outputs[92][0],
              "live image compression quality did not reduce WebP size at lower quality")
        check(not np.array_equal(compressed_outputs[25][1], compressed_outputs[92][1]),
              "live image compression quality setting did not affect rendered pixels")
        print("PASS deployed image compression: low/high quality produce valid WebP with expected size and quality differences")

        yy, xx = np.mgrid[0:64, 0:96]
        gradient = np.stack((40 + xx, 55 + yy, 75 + (xx + yy) // 2), axis=2).clip(0, 255).astype(np.uint8)
        enhance_buffer = io.BytesIO()
        Image.fromarray(gradient, mode="RGB").save(enhance_buffer, format="PNG")
        enhance_png = enhance_buffer.getvalue()
        enhanced = post_with_retry(
            client,
            f"{BASE_URL}/api/image/convert",
            files={"files": ("studio-enhance.png", enhance_png, "image/png")},
            data={"output_format": "png", "sharpen": "80", "contrast": "35", "brightness": "20"},
        )
        check(enhanced.status_code == 200,
              f"live image enhancement failed: {enhanced.status_code} {enhanced.text[:250]}")
        with Image.open(io.BytesIO(enhanced.content)) as enhanced_image:
            enhanced_pixels = np.asarray(enhanced_image.convert("RGB")).copy()
            check(enhanced_image.format == "PNG" and enhanced_image.size == (96, 64),
                  f"live image enhancement returned invalid PNG: {enhanced_image.format} {enhanced_image.size}")
        check(float(enhanced_pixels.mean()) > float(gradient.mean()),
              "live image brightness/contrast enhancement did not change image pixel values as requested")
        print("PASS deployed image enhancement: sharpen, contrast and brightness affect valid output")

        batch_response = post_with_retry(
            client,
            f"{BASE_URL}/api/image/convert",
            files=[
                ("files", ("studio-batch-one.png", png, "image/png")),
                ("files", ("studio-batch-two.png", png, "image/png")),
            ],
            data={"output_format": "webp", "quality": "85"},
        )
        check(batch_response.status_code == 200,
              f"live image batch conversion failed: {batch_response.status_code} {batch_response.text[:250]}")
        with zipfile.ZipFile(io.BytesIO(batch_response.content)) as archive:
            image_names = [name for name in archive.namelist() if name.lower().endswith(".webp")]
            check(len(image_names) == 2, f"live image batch should return two WebP files; found {image_names}")
            for image_name in image_names:
                with Image.open(io.BytesIO(archive.read(image_name))) as batch_image:
                    check(batch_image.format == "WEBP" and batch_image.size == (64, 48),
                          f"live image batch produced an invalid file: {image_name}")
        print("PASS deployed image batch: two valid WebP files returned in ZIP")

        print("PASS ALL DEPLOYED IMAGE STUDIO MODES: convert, resize, compress, enhance and batch")

        response = post_with_retry(client, 
            f"{BASE_URL}/api/dicom/to-pdf",
            files={"files": ("live-test.dcm", dicom, "application/dicom")},
        )
        check(response.status_code == 400, "live DICOM endpoint did not require explicit consent")
        response = post_with_retry(client, 
            f"{BASE_URL}/api/dicom/to-pdf",
            files={"files": ("live-test.dcm", dicom, "application/dicom")},
            data={"consent": "true"},
        )
        expect_pdf(response, "live DICOM-to-PDF")
        print("PASS deployed DICOM consent and DICOM-to-PDF output")

        response = post_with_retry(client, 
            f"{BASE_URL}/api/office/excel-to-pdf",
            files={"file": ("live-test.xlsx", xlsx, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        )
        expect_pdf(response, "live Excel-to-PDF")
        response = post_with_retry(client, 
            f"{BASE_URL}/api/office/powerpoint-to-pdf",
            files={"file": ("live-test.pptx", pptx, "application/vnd.openxmlformats-officedocument.presentationml.presentation")},
        )
        expect_pdf(response, "live PowerPoint-to-PDF")
        response = post_with_retry(client, 
            f"{BASE_URL}/api/word/to-pdf",
            files={"file": ("live-test.docx", docx, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
        )
        expect_pdf(response, "live Word-to-PDF")
        print("PASS deployed Excel-to-PDF, PowerPoint-to-PDF and Word-to-PDF outputs")

        dwg_bytes = DWG_PATH.read_bytes()
        response = post_with_retry(client, 
            f"{BASE_URL}/api/cad/dwg-to-pdf",
            files={"file": ("libredwg-line-test.dwg", dwg_bytes, "application/octet-stream")},
        )
        expect_pdf(response, "live real DWG-to-PDF")
        print("PASS deployed real DWG parsing and PDF rendering")

        try:
            translated = post_with_retry(client, 
                f"{BASE_URL}/api/translate",
                json={"text": "Hello, world.", "source": "en", "target": "ar"},
            )
            if translated.status_code == 200 and translated.json().get("translated_text"):
                print("PASS live translation provider returned text")
                export = post_with_retry(client, 
                    f"{BASE_URL}/api/translate/docx",
                    json={"translated_text": translated.json()["translated_text"], "target": "ar"},
                )
                check(export.status_code == 200, f"live translated Word export failed: {export.status_code} {export.text[:200]}")
                Document(io.BytesIO(export.content))
                print("PASS live translation Word export")
            else:
                print("WARNING live translation provider did not return a result:", translated.status_code, translated.text[:250])
        except Exception as exc:
            print("WARNING live translation provider could not be verified:", str(exc)[:250])

        test_arabic_conversion_quality(client)

        print("PASS ALL DEPLOYED API SMOKE TESTS (excluding any translation-provider warning above)")


if __name__ == "__main__":
    main()
