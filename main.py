from __future__ import annotations

import os
import re
import html
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

import fitz  # PyMuPDF
import httpx
from docx import Document
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "50"))
MAX_UPLOAD_BYTES = MAX_UPLOAD_MB * 1024 * 1024
LIBRETRANSLATE_URL = os.getenv("LIBRETRANSLATE_URL", "").rstrip("/")
LIBRETRANSLATE_API_KEY = os.getenv("LIBRETRANSLATE_API_KEY", "")

app = FastAPI(title="PDF Globe API", version="1.0.0")


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
        "translation_provider": "LibreTranslate" if LIBRETRANSLATE_URL else "MyMemory fallback",
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


@app.post("/api/pdf/to-word")
async def pdf_to_word(file: UploadFile = File(...)):
    with tempfile.TemporaryDirectory(prefix="pdfglobe-") as td:
        folder = Path(td)
        src = await store_upload(file, folder, {".pdf"})
        out = folder / f"{safe_name(file.filename)}.docx"
        conversion_error = None
        try:
            from pdf2docx import Converter
            converter = Converter(str(src))
            converter.convert(str(out), start=0, end=None)
            converter.close()
        except Exception as exc:
            conversion_error = exc
            # Text-only fallback keeps the action usable when pdf2docx cannot parse a PDF.
            try:
                fallback = Document()
                source_pdf = fitz.open(src)
                extracted_any = False
                for page_no, page in enumerate(source_pdf, start=1):
                    if page_no > 1:
                        fallback.add_page_break()
                    for block in page.get_text("blocks"):
                        block_text = str(block[4]).strip()
                        if block_text:
                            fallback.add_paragraph(block_text)
                            extracted_any = True
                source_pdf.close()
                if extracted_any:
                    fallback.save(out)
            except Exception:
                pass
        if not out.exists():
            detail = f"تعذر التحويل إلى Word. قد يكون الملف ممسوحاً ضوئياً أو معقد التخطيط: {conversion_error}"
            raise HTTPException(status_code=422, detail=detail)
        return download_response(out, out.name, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")


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


async def translate_chunk(text: str, source: str, target: str) -> str:
    if LIBRETRANSLATE_URL:
        payload = {"q": text, "source": source, "target": target, "format": "text"}
        if LIBRETRANSLATE_API_KEY:
            payload["api_key"] = LIBRETRANSLATE_API_KEY
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(f"{LIBRETRANSLATE_URL}/translate", data=payload)
            response.raise_for_status()
            data = response.json()
            if not data.get("translatedText"):
                raise ValueError("لم يرجع محرك الترجمة نصاً مترجماً")
            return data["translatedText"]
    # Free fallback for small jobs. MyMemory has provider-side quotas and language-pair limits.
    if source == "auto":
        raise HTTPException(status_code=400, detail="اختر لغة المصدر بدلاً من (تلقائي) عند استخدام الترجمة المجانية الاحتياطية")
    async with httpx.AsyncClient(timeout=45) as client:
        response = await client.get(
            "https://api.mymemory.translated.net/get",
            params={"q": text, "langpair": f"{source}|{target}"},
        )
        response.raise_for_status()
        data = response.json()
        if data.get("responseStatus") != 200:
            raise ValueError(data.get("responseDetails") or "محرك الترجمة لم يقبل الطلب")
        translated = data.get("responseData", {}).get("translatedText")
        if not translated:
            raise ValueError("لم ينتج محرك الترجمة نصاً")
        return html.unescape(translated)


async def translate_long_text(text: str, source: str, target: str) -> str:
    # Split on paragraphs and then into provider-safe chunks, retaining paragraph boundaries.
    chunks: list[str] = []
    max_chars = 450 if not LIBRETRANSLATE_URL else 4500
    for paragraph in text.splitlines():
        if not paragraph.strip():
            chunks.append("")
            continue
        current = ""
        for word in paragraph.split(" "):
            candidate = (current + " " + word).strip()
            if len(candidate) > max_chars and current:
                chunks.append(current)
                current = word
            else:
                current = candidate
        if current:
            chunks.append(current)
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
    limit = 100_000 if LIBRETRANSLATE_URL else 4_000
    if len(text_value) > limit:
        label = "100 ألف حرف" if LIBRETRANSLATE_URL else "4 آلاف حرف في وضع الترجمة المجانية الاحتياطي"
        raise HTTPException(status_code=413, detail=f"النص يتجاوز الحد الحالي ({label}). استخدم خدمة LibreTranslate مهيأة للملفات الطويلة أو قسّم المستند")
    try:
        result = await translate_long_text(text_value, source, target)
        return {"translated_text": result, "provider": "LibreTranslate" if LIBRETRANSLATE_URL else "MyMemory", "notice": "راجع الأسماء والأرقام والمصطلحات قبل اعتماد الترجمة النهائية."}
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
    return {"provider": "MyMemory", "languages": [
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
