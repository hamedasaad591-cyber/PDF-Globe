import subprocess
import tempfile
from pathlib import Path

import fitz
from fastapi import File, HTTPException, UploadFile


def register_dwg_routes(app, store_upload, download_response, require_binary, safe_name):
    @app.post("/api/cad/dwg-to-pdf")
    async def dwg_to_pdf(file: UploadFile = File(...)):
        dwg2dxf = require_binary("dwg2dxf", "محرك قراءة DWG غير جاهز على الخادم")
        with tempfile.TemporaryDirectory(prefix="pdfglobe-dwg-") as td:
            root = Path(td)
            src = await store_upload(file, root, {".dwg"})
            if src.stat().st_size > 25 * 1024 * 1024:
                raise HTTPException(status_code=413, detail="حد ملف DWG هو 25 MB")
            dxf_path = root / (src.stem + ".dxf")
            try:
                result = subprocess.run(
                    [dwg2dxf, "-y", "-o", str(dxf_path), str(src)],
                    cwd=str(root), capture_output=True, text=True, timeout=120,
                )
            except subprocess.TimeoutExpired as exc:
                raise HTTPException(status_code=504, detail="انتهت مهلة قراءة DWG. جرّب رسماً أصغر") from exc
            if result.returncode or not dxf_path.exists() or dxf_path.stat().st_size == 0:
                reason = (result.stderr or result.stdout or "لم ينتج محول DWG ملف DXF")[-500:]
                raise HTTPException(status_code=422, detail="تعذر قراءة ملف DWG: " + reason)

            try:
                import ezdxf
                from ezdxf import recover
                from ezdxf.addons.drawing import Frontend, RenderContext, config as drawing_config
                from ezdxf.addons.drawing import layout as drawing_layout
                from ezdxf.addons.drawing import pymupdf as drawing_pdf

                try:
                    doc, auditor = recover.readfile(dxf_path)
                    if auditor.has_errors:
                        auditor.audit()
                except Exception:
                    doc = ezdxf.readfile(dxf_path)

                paper_names = [name for name in doc.layout_names() if str(name).casefold() != "model"]
                # Ignore empty paper layouts and viewport-only layouts: ezdxf's
                # drawing backend cannot derive a content bounding box from them.
                targets = []
                for name in paper_names:
                    layout_object = doc.layout(name)
                    has_drawable_entities = any(
                        entity.dxftype() != "VIEWPORT" for entity in layout_object
                    )
                    if has_drawable_entities:
                        targets.append((name, layout_object))
                    if len(targets) >= 12:
                        break
                if not targets:
                    targets = [("Model", doc.modelspace())]

                combined = fitz.open()
                try:
                    for name, layout_object in targets:
                        backend = drawing_pdf.PyMuPdfBackend()
                        Frontend(RenderContext(doc), backend, config=drawing_config.Configuration(background_policy=drawing_config.BackgroundPolicy.WHITE)).draw_layout(layout_object)
                        if str(name).casefold() == "model":
                            page_definition = drawing_layout.Page(0, 0)
                        else:
                            page_definition = drawing_layout.Page.from_dxf_layout(layout_object)
                        payload = backend.get_pdf_bytes(page_definition)
                        with fitz.open(stream=payload, filetype="pdf") as fragment:
                            if fragment.page_count:
                                combined.insert_pdf(fragment)
                    if combined.page_count == 0:
                        raise HTTPException(status_code=422, detail="لم ينتج الرسم صفحات قابلة للطباعة")
                    if combined.page_count > 12:
                        raise HTTPException(status_code=413, detail="تم تجاوز حد 12 صفحة تخطيط في ملف DWG")
                    combined.set_metadata({
                        "title": "DWG drawing export",
                        "author": "PDF Globe",
                        "subject": "2D CAD rendering",
                    })
                    output = root / (safe_name(file.filename or "drawing") + "_converted.pdf")
                    combined.save(output, garbage=4, deflate=True)
                finally:
                    combined.close()
            except HTTPException:
                raise
            except Exception as exc:
                raise HTTPException(
                    status_code=422,
                    detail="تعذر رسم محتوى DWG إلى PDF. قد يحتوي الملف على عناصر غير مدعومة. التفاصيل: " + str(exc)[:320],
                ) from exc

            return download_response(output, output.name, "application/pdf")
