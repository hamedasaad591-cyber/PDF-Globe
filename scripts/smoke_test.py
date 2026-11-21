"""End-to-end API smoke tests: verify that conversion routes return readable files."""
from __future__ import annotations

import io
import os
import shutil
import stat
import sys
import tempfile
import zipfile
from pathlib import Path
from unittest.mock import patch

import fitz
import numpy as np
import pydicom
from docx import Document
from fastapi.testclient import TestClient
from openpyxl import Workbook, load_workbook
from PIL import Image
from pptx import Presentation
from pydicom.dataset import FileDataset, FileMetaDataset
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pydicom.uid import (
    ExplicitVRLittleEndian,
    SecondaryCaptureImageStorage,
    generate_uid,
)

import main


client = TestClient(main.app)


def check(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def pdf_fixture() -> bytes:
    doc = fitz.open()
    page = doc.new_page(width=360, height=260)
    page.insert_text((35, 45), "PDF Globe smoke test", fontsize=18)
    page.insert_text((35, 90), "Name       Quantity       Price", fontsize=12)
    page.insert_text((35, 115), "Paper      12              4.50", fontsize=12)
    page.insert_text((35, 140), "Pens       5               2.00", fontsize=12)
    data = doc.tobytes(garbage=4, deflate=True)
    doc.close()
    return data


def assert_pdf(data: bytes, label: str) -> None:
    with fitz.open(stream=data, filetype="pdf") as doc:
        check(doc.page_count > 0, f"{label}: PDF has no pages")


def image_fixture() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (32, 24), (220, 40, 80)).save(buffer, format="PNG")
    return buffer.getvalue()


def dicom_fixture() -> bytes:
    with tempfile.TemporaryDirectory(prefix="pdfglobe-dicom-test-") as td:
        path = Path(td) / "smoke.dcm"
        meta = FileMetaDataset()
        meta.MediaStorageSOPClassUID = SecondaryCaptureImageStorage
        meta.MediaStorageSOPInstanceUID = generate_uid()
        meta.TransferSyntaxUID = ExplicitVRLittleEndian
        meta.ImplementationClassUID = generate_uid()
        dataset = FileDataset(str(path), {}, file_meta=meta, preamble=b"\0" * 128)
        dataset.SOPClassUID = meta.MediaStorageSOPClassUID
        dataset.SOPInstanceUID = meta.MediaStorageSOPInstanceUID
        dataset.StudyInstanceUID = generate_uid()
        dataset.SeriesInstanceUID = generate_uid()
        dataset.Modality = "OT"
        dataset.Rows = 2
        dataset.Columns = 2
        dataset.SamplesPerPixel = 1
        dataset.PhotometricInterpretation = "MONOCHROME2"
        dataset.BitsAllocated = 8
        dataset.BitsStored = 8
        dataset.HighBit = 7
        dataset.PixelRepresentation = 0
        dataset.InstanceNumber = 1
        dataset.PixelData = np.array([[0, 64], [180, 255]], dtype=np.uint8).tobytes()
        dataset.save_as(path, enforce_file_format=True)
        return path.read_bytes()


def test_health() -> None:
    response = client.get("/api/health")
    check(response.status_code == 200, "health endpoint did not return 200")
    data = response.json()
    check(data.get("ok") is True, "health endpoint did not report ok=true")
    for capability in (
        "compress_pdf", "pdf_to_word", "pdf_to_excel", "pdf_to_powerpoint",
        "image_conversion", "dicom_to_pdf", "excel_to_pdf", "powerpoint_to_pdf",
    ):
        check(capability in data.get("capabilities", {}), f"health response missing capability: {capability}")
    print("PASS API health and capability manifest")


def test_pdf_outputs(source_pdf: bytes) -> None:
    payload = {"file": ("smoke.pdf", source_pdf, "application/pdf")}

    response = client.post("/api/pdf/compress", files=payload)
    check(response.status_code == 200, f"PDF compression failed: {response.status_code} {response.text[:300]}")
    assert_pdf(response.content, "compressed PDF")

    response = client.post("/api/pdf/repair", files=payload)
    check(response.status_code == 200, f"PDF repair failed: {response.status_code} {response.text[:300]}")
    assert_pdf(response.content, "repaired PDF")

    response = client.post("/api/pdf/to-word", files=payload, data={"mode": "hybrid"})
    check(response.status_code == 200, f"PDF to Word failed: {response.status_code} {response.text[:300]}")
    document = Document(io.BytesIO(response.content))
    check(len(document.paragraphs) > 0 or len(document.inline_shapes) > 0, "PDF to Word returned an empty DOCX")

    response = client.post("/api/pdf/to-excel", files=payload)
    check(response.status_code == 200, f"PDF to Excel failed: {response.status_code} {response.text[:300]}")
    workbook = load_workbook(io.BytesIO(response.content), read_only=True)
    check("Read me" in workbook.sheetnames, "PDF to Excel workbook is missing the Read me sheet")
    check(len(workbook.sheetnames) >= 2, "PDF to Excel workbook is missing extracted page content")
    workbook.close()

    response = client.post("/api/pdf/to-powerpoint", files=payload)
    check(response.status_code == 200, f"PDF to PowerPoint failed: {response.status_code} {response.text[:300]}")
    presentation = Presentation(io.BytesIO(response.content))
    check(len(presentation.slides) == 1, "PDF to PowerPoint did not create one slide for the test page")
    check(len(presentation.slides[0].shapes) > 0, "PDF to PowerPoint slide contains no page image")

    print("PASS PDF compression, repair, PDF-to-Word, PDF-to-Excel and PDF-to-PowerPoint outputs")


def test_image_outputs() -> None:
    source = image_fixture()

    # Exercise every advertised output format, not only the common WebP/PDF paths.
    output_formats = {
        "jpg": "JPEG", "jpeg": "JPEG", "png": "PNG", "webp": "WEBP",
        "avif": "AVIF", "heic": "HEIF", "bmp": "BMP", "gif": "GIF",
        "tiff": "TIFF", "ico": "ICO",
    }
    for output_format, expected_format in output_formats.items():
        response = client.post(
            "/api/image/convert",
            data={"output_format": output_format, "quality": "86"},
            files=[("files", ("smoke.png", source, "image/png"))],
        )
        check(response.status_code == 200, f"PNG to {output_format.upper()} failed: {response.status_code} {response.text[:300]}")
        with Image.open(io.BytesIO(response.content)) as result:
            check(result.format == expected_format, f"PNG to {output_format.upper()} returned {result.format}, expected {expected_format}")
            check(result.width > 0 and result.height > 0, f"PNG to {output_format.upper()} returned empty image dimensions")

    # Animated GIF and multi-page TIFF exports must retain all source frames.
    animated_frames = [
        Image.new("RGB", (64, 48), (220, 30, 30)),
        Image.new("RGB", (64, 48), (30, 80, 220)),
    ]
    gif_source = io.BytesIO()
    animated_frames[0].save(gif_source, format="GIF", save_all=True, append_images=animated_frames[1:], duration=[80, 120], loop=0)
    response = client.post(
        "/api/image/convert",
        data={"output_format": "gif"},
        files=[("files", ("animated.gif", gif_source.getvalue(), "image/gif"))],
    )
    check(response.status_code == 200, f"Animated GIF conversion failed: {response.status_code} {response.text[:300]}")
    with Image.open(io.BytesIO(response.content)) as result:
        check(result.format == "GIF" and result.n_frames == 2, "Animated GIF conversion did not preserve both frames")

    tiff_source = io.BytesIO()
    animated_frames[0].save(tiff_source, format="TIFF", save_all=True, append_images=animated_frames[1:])
    response = client.post(
        "/api/image/convert",
        data={"output_format": "tiff"},
        files=[("files", ("animated.tiff", tiff_source.getvalue(), "image/tiff"))],
    )
    check(response.status_code == 200, f"Multi-page TIFF conversion failed: {response.status_code} {response.text[:300]}")
    with Image.open(io.BytesIO(response.content)) as result:
        check(result.format == "TIFF" and result.n_frames == 2, "TIFF conversion did not preserve both pages")
    for frame in animated_frames:
        frame.close()

    # Exercise every accepted input extension via a common PNG output.
    source_inputs = [
        (".jpg", "JPEG", "RGB"), (".jpeg", "JPEG", "RGB"), (".jfif", "JPEG", "RGB"),
        (".png", "PNG", "RGB"), (".webp", "WEBP", "RGB"), (".avif", "AVIF", "RGB"),
        (".heic", "HEIF", "RGB"), (".heif", "HEIF", "RGB"), (".bmp", "BMP", "RGB"),
        (".gif", "GIF", "RGB"), (".tif", "TIFF", "RGB"), (".tiff", "TIFF", "RGB"),
        (".ico", "ICO", "RGBA"), (".tga", "TGA", "RGB"), (".ppm", "PPM", "RGB"),
        (".pgm", "PPM", "L"), (".pbm", "PPM", "1"), (".pcx", "PCX", "RGB"),
    ]
    for extension, source_format, mode in source_inputs:
        color = 1 if mode == "1" else (120 if mode == "L" else (210, 55, 95, 255) if mode == "RGBA" else (210, 55, 95))
        generated = io.BytesIO()
        Image.new(mode, (64, 48), color).save(generated, format=source_format)
        response = client.post(
            "/api/image/convert",
            data={"output_format": "png"},
            files=[("files", (f"smoke{extension}", generated.getvalue(), "application/octet-stream"))],
        )
        check(response.status_code == 200, f"Input {extension} to PNG failed: {response.status_code} {response.text[:300]}")
        with Image.open(io.BytesIO(response.content)) as result:
            check(result.format == "PNG" and result.width > 0 and result.height > 0, f"Input {extension} did not produce a valid PNG")
            if extension != ".ico":
                check(result.size == (64, 48), f"Input {extension} changed its pixel dimensions unexpectedly: {result.size}")

    response = client.post(
        "/api/image/convert",
        data={"output_format": "pdf"},
        files=[("files", ("smoke.png", source, "image/png"))],
    )
    check(response.status_code == 200, f"Image to PDF failed: {response.status_code} {response.text[:300]}")
    assert_pdf(response.content, "image to PDF")

    response = client.post(
        "/api/image/convert",
        data={"output_format": "png"},
        files=[
            ("files", ("first.png", source, "image/png")),
            ("files", ("second.png", source, "image/png")),
        ],
    )
    check(response.status_code == 200, f"Batch image conversion failed: {response.status_code} {response.text[:300]}")
    check(zipfile.is_zipfile(io.BytesIO(response.content)), "Batch image conversion did not return a ZIP archive")
    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        check(len(archive.namelist()) == 2, "Batch image ZIP does not contain both converted images")

    print("PASS all 18 input image extensions and all 10 image output formats, image-to-PDF, and batch ZIP downloads")

def test_dicom_output() -> None:
    data = dicom_fixture()
    denied = client.post(
        "/api/dicom/to-pdf",
        files=[("files", ("smoke.dcm", data, "application/dicom"))],
    )
    check(denied.status_code == 400, "DICOM route did not enforce explicit consent")

    response = client.post(
        "/api/dicom/to-pdf",
        data={"consent": "true"},
        files=[("files", ("smoke.dcm", data, "application/dicom"))],
    )
    check(response.status_code == 200, f"DICOM to PDF failed: {response.status_code} {response.text[:300]}")
    assert_pdf(response.content, "DICOM to PDF")
    print("PASS DICOM consent gate and DICOM-to-PDF output")


def test_office_outputs() -> None:
    office = shutil.which("libreoffice")
    check(office is not None, "LibreOffice is required in the CI smoke-test environment")

    with tempfile.TemporaryDirectory(prefix="pdfglobe-office-test-") as td:
        folder = Path(td)

        workbook = Workbook()
        sheet = workbook.active
        sheet["A1"] = "Item"
        sheet["B1"] = "Quantity"
        sheet["A2"] = "Paper"
        sheet["B2"] = 12
        xlsx_path = folder / "smoke.xlsx"
        workbook.save(xlsx_path)

        response = client.post(
            "/api/office/excel-to-pdf",
            files={"file": ("smoke.xlsx", xlsx_path.read_bytes(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        )
        check(response.status_code == 200, f"Excel to PDF failed: {response.status_code} {response.text[:300]}")
        assert_pdf(response.content, "Excel to PDF")

        presentation = Presentation()
        slide = presentation.slides.add_slide(presentation.slide_layouts[6])
        slide.shapes.add_textbox(50_000, 50_000, 300_000, 80_000).text = "PDF Globe"
        pptx_path = folder / "smoke.pptx"
        presentation.save(pptx_path)

        response = client.post(
            "/api/office/powerpoint-to-pdf",
            files={"file": ("smoke.pptx", pptx_path.read_bytes(), "application/vnd.openxmlformats-officedocument.presentationml.presentation")},
        )
        check(response.status_code == 200, f"PowerPoint to PDF failed: {response.status_code} {response.text[:300]}")
        assert_pdf(response.content, "PowerPoint to PDF")

        doc = Document()
        doc.add_paragraph("PDF Globe Word-to-PDF smoke test")
        docx_path = folder / "smoke.docx"
        doc.save(docx_path)
        response = client.post(
            "/api/word/to-pdf",
            files={"file": ("smoke.docx", docx_path.read_bytes(), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
        )
        check(response.status_code == 200, f"Word to PDF failed: {response.status_code} {response.text[:300]}")
        assert_pdf(response.content, "Word to PDF")

    print("PASS Excel-to-PDF, PowerPoint-to-PDF, and Word-to-PDF file outputs")


def test_password_outputs(source_pdf: bytes) -> None:
    qpdf = shutil.which("qpdf")
    check(qpdf is not None, "qpdf is required in the CI smoke-test environment")

    response = client.post(
        "/api/pdf/protect",
        data={"password": "globe123"},
        files={"file": ("smoke.pdf", source_pdf, "application/pdf")},
    )
    check(response.status_code == 200, f"PDF protection failed: {response.status_code} {response.text[:300]}")
    with fitz.open(stream=response.content, filetype="pdf") as encrypted:
        check(encrypted.is_encrypted, "Protected PDF is not encrypted")

    response = client.post(
        "/api/pdf/unlock",
        data={"password": "globe123"},
        files={"file": ("protected.pdf", response.content, "application/pdf")},
    )
    check(response.status_code == 200, f"PDF unlocking failed: {response.status_code} {response.text[:300]}")
    assert_pdf(response.content, "unlocked PDF")
    print("PASS PDF protect/unlock outputs")


def test_translation_outputs() -> None:
    async def fake_translate(text: str, source: str, target: str) -> str:
        return f"[{source}->{target}] {text}"

    with patch.object(main, "translate_long_text", fake_translate):
        response = client.post(
            "/api/translate",
            json={"text": "PDF Globe test", "source": "en", "target": "ar"},
        )
    check(response.status_code == 200, f"Translation API test failed: {response.status_code} {response.text[:300]}")
    translated = response.json().get("translated_text", "")
    check(translated.startswith("[en->ar]"), "Translation API returned an unexpected result")

    response = client.post(
        "/api/translate/docx",
        json={"translated_text": translated, "target": "ar"},
    )
    check(response.status_code == 200, f"Translated DOCX export failed: {response.status_code} {response.text[:300]}")
    document = Document(io.BytesIO(response.content))
    check(any("[en->ar]" in paragraph.text for paragraph in document.paragraphs), "Translated DOCX does not contain translated text")

    languages = client.get("/api/languages")
    check(languages.status_code == 200 and len(languages.json().get("languages", [])) >= 10, "Languages endpoint did not return a language list")
    print("PASS translation response, Word export and language list (translation provider mocked, no external charge)")


def test_dwg_pipeline_with_converter_stub() -> None:
    with tempfile.TemporaryDirectory(prefix="pdfglobe-dwg-stub-") as td:
        directory = Path(td)
        executable = directory / "dwg2dxf"
        executable.write_text(
            "#!/usr/bin/env python3\n"
            "import sys, ezdxf\n"
            "out = sys.argv[sys.argv.index('-o') + 1]\n"
            "doc = ezdxf.new('R2010')\n"
            "doc.modelspace().add_line((0, 0), (100, 100))\n"
            "doc.saveas(out)\n",
            encoding="utf-8",
        )
        executable.chmod(executable.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        old_path = os.environ.get("PATH", "")
        os.environ["PATH"] = str(directory) + os.pathsep + old_path
        try:
            response = client.post(
                "/api/cad/dwg-to-pdf",
                files={"file": ("smoke.dwg", b"test dwg container", "application/octet-stream")},
            )
        finally:
            os.environ["PATH"] = old_path
    check(response.status_code == 200, f"DWG-to-PDF rendering stage failed: {response.status_code} {response.text[:300]}")
    assert_pdf(response.content, "DWG-to-PDF with synthetic DXF converter")
    print("PASS DWG-to-PDF rendering pipeline using a synthetic converter stub (not a real DWG parse)")


def main_test() -> None:
    source_pdf = pdf_fixture()
    test_health()
    test_pdf_outputs(source_pdf)
    test_image_outputs()
    test_dicom_output()
    test_office_outputs()
    test_password_outputs(source_pdf)
    test_translation_outputs()
    test_dwg_pipeline_with_converter_stub()
    print("PASS ALL BACKEND SMOKE TESTS: outputs opened and validated")


if __name__ == "__main__":
    main_test()
