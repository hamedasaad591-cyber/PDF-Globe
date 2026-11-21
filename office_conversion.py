import os
import subprocess
import tempfile
from pathlib import Path

import fitz
from fastapi import File, HTTPException, UploadFile


def register_office_routes(app, store_upload, download_response, require_binary):
    def office_to_pdf(src: Path, folder: Path, office: str, export_filter: str) -> Path:
        profile = folder / "lo-profile"
        home = folder / "lo-home"
        home.mkdir(exist_ok=True)
        env = os.environ.copy()
        env["HOME"] = str(home)
        env["SAL_USE_VCLPLUGIN"] = "svp"
        try:
            result = subprocess.run(
                [office, "-env:UserInstallation=" + profile.as_uri(), "--headless",
                 "--convert-to", "pdf:" + export_filter, "--outdir", str(folder), str(src)],
                capture_output=True, text=True, timeout=120, env=env,
            )
        except subprocess.TimeoutExpired as exc:
            raise HTTPException(status_code=504, detail="انتهت مهلة التحويل. قلّل حجم الملف أو عدد الصفحات") from exc
        output = folder / (src.stem + ".pdf")
        if result.returncode or not output.exists() or output.stat().st_size == 0:
            detail = (result.stderr or result.stdout or "لم ينتج LibreOffice ملف PDF")[-600:]
            raise HTTPException(status_code=422, detail="تعذر تحويل الملف إلى PDF: " + detail)
        try:
            with fitz.open(output) as check:
                if not 1 <= check.page_count <= 250:
                    raise HTTPException(status_code=413, detail="الملف الناتج يجب أن يكون بين صفحة واحدة و250 صفحة")
        except fitz.FileDataError as exc:
            raise HTTPException(status_code=422, detail="ملف PDF الناتج غير صالح") from exc
        return output

    @app.post("/api/office/excel-to-pdf")
    async def excel_to_pdf(file: UploadFile = File(...)):
        office = require_binary("libreoffice", "خدمة Office غير مثبتة على الخادم")
        with tempfile.TemporaryDirectory(prefix="pdfglobe-excel-") as td:
            folder = Path(td)
            src = await store_upload(file, folder, {".xlsx", ".xls", ".xlsm", ".ods", ".csv"})
            if src.stat().st_size > 25 * 1024 * 1024:
                raise HTTPException(status_code=413, detail="حد تحويل Excel هو 25 MB")
            output = office_to_pdf(src, folder, office, "calc_pdf_Export")
            return download_response(output, output.name, "application/pdf")

    @app.post("/api/office/powerpoint-to-pdf")
    async def powerpoint_to_pdf(file: UploadFile = File(...)):
        office = require_binary("libreoffice", "خدمة Office غير مثبتة على الخادم")
        with tempfile.TemporaryDirectory(prefix="pdfglobe-ppt-") as td:
            folder = Path(td)
            src = await store_upload(file, folder, {".pptx", ".ppt", ".ppsx", ".odp"})
            if src.stat().st_size > 25 * 1024 * 1024:
                raise HTTPException(status_code=413, detail="حد تحويل PowerPoint هو 25 MB")
            output = office_to_pdf(src, folder, office, "impress_pdf_Export")
            return download_response(output, output.name, "application/pdf")
