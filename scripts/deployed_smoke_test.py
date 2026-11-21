"""Smoke-test the deployed Render API using synthetic, non-sensitive files."""
from __future__ import annotations

import io
import os
import sys
import time
import zipfile
from pathlib import Path

import fitz
import httpx
import numpy as np
import pydicom
from docx import Document
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

        print("PASS ALL DEPLOYED API SMOKE TESTS (excluding any translation-provider warning above)")


if __name__ == "__main__":
    main()
