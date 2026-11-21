import io
import tempfile
from pathlib import Path

import fitz
import numpy as np
import pydicom
from fastapi import File, Form, HTTPException, UploadFile
from PIL import Image


MAX_DICOM_FRAME_PIXELS = 12_000_000
MAX_DICOM_TOTAL_PIXELS = 30_000_000
MAX_DICOM_TOTAL_SAMPLE_VALUES = 40_000_000
MAX_DICOM_PAGES = 200


def _dicom_to_rgb(frame, dataset):
    from pydicom.pixels.processing import (
        apply_color_lut,
        apply_modality_lut,
        apply_voi_lut,
        convert_color_space,
    )

    photo = str(getattr(dataset, "PhotometricInterpretation", "MONOCHROME2")).upper()
    pixels = np.asarray(frame)

    if photo == "PALETTE COLOR":
        pixels = apply_color_lut(pixels, dataset)
        photo = "RGB"

    if pixels.ndim == 3 and pixels.shape[-1] in (3, 4):
        if pixels.shape[-1] == 4:
            pixels = pixels[..., :3]
        if photo.startswith("YBR"):
            try:
                source = "YBR_FULL" if photo == "YBR_FULL_422" else photo
                pixels = convert_color_space(pixels, source, "RGB")
            except Exception:
                pass
        if pixels.dtype != np.uint8:
            values = pixels.astype(np.float32)
            low, high = np.percentile(values, (0.5, 99.5))
            if high <= low:
                high = low + 1
            pixels = np.clip((values - low) * 255.0 / (high - low), 0, 255).astype(np.uint8)
        return Image.fromarray(pixels, mode="RGB")

    if pixels.ndim != 2:
        raise HTTPException(status_code=422, detail="نوع بيانات البكسل داخل DICOM غير مدعوم")

    try:
        pixels = apply_modality_lut(pixels, dataset)
    except Exception:
        pixels = pixels.astype(np.float32)

    if hasattr(dataset, "VOILUTSequence") or (
        hasattr(dataset, "WindowCenter") and hasattr(dataset, "WindowWidth")
    ):
        try:
            pixels = apply_voi_lut(pixels, dataset, index=0)
        except Exception:
            pass

    values = np.asarray(pixels, dtype=np.float32)
    finite = values[np.isfinite(values)]
    if finite.size == 0:
        raise HTTPException(status_code=422, detail="صورة DICOM لا تحتوي على قيم صالحة")
    low, high = np.percentile(finite, (0.5, 99.5))
    if high <= low:
        low, high = float(finite.min()), float(finite.max())
    if high <= low:
        high = low + 1.0
    values = np.nan_to_num(values, nan=low, posinf=high, neginf=low)
    values = np.clip((values - low) * 255.0 / (high - low), 0, 255).astype(np.uint8)
    if photo == "MONOCHROME1":
        values = 255 - values
    return Image.fromarray(values, mode="L").convert("RGB")


def register_dicom_routes(app, store_upload, download_response):
    @app.post("/api/dicom/to-pdf")
    async def dicom_to_pdf(
        files: list[UploadFile] = File(...),
        consent: bool = Form(False),
    ):
        if not consent:
            raise HTTPException(
                status_code=400,
                detail="يجب تأكيد موافقتك على معالجة ملفات DICOM التي قد تتضمن معلومات صحية حساسة",
            )
        if not 1 <= len(files) <= 60:
            raise HTTPException(status_code=400, detail="اختر من ملف DICOM واحد إلى 60 ملفاً")

        with tempfile.TemporaryDirectory(prefix="pdfglobe-dicom-") as td:
            root = Path(td)
            inputs = []
            total_bytes = 0
            estimated_pages = 0
            estimated_pixels = 0
            estimated_sample_values = 0

            for index, upload in enumerate(files):
                sub = root / f"source-{index:03d}"
                sub.mkdir()
                src = await store_upload(upload, sub, {".dcm", ".dicom", ".ima"})
                total_bytes += src.stat().st_size
                if total_bytes > 120 * 1024 * 1024:
                    raise HTTPException(status_code=413, detail="الحد الإجمالي لملفات DICOM هو 120 MB")
                try:
                    dataset = pydicom.dcmread(src, force=True, stop_before_pixels=True)
                    frame_count = int(getattr(dataset, "NumberOfFrames", 1) or 1)
                    if frame_count < 1 or frame_count > 150:
                        raise HTTPException(status_code=413, detail="الحد الأقصى 150 إطاراً لكل ملف DICOM")
                    rows = int(getattr(dataset, "Rows", 0) or 0)
                    cols = int(getattr(dataset, "Columns", 0) or 0)
                    samples = int(getattr(dataset, "SamplesPerPixel", 1) or 1)
                    if not 1 <= rows <= 8192 or not 1 <= cols <= 8192:
                        raise HTTPException(status_code=413, detail="أبعاد صورة DICOM يجب أن تكون بين 1 و8192 بكسل")
                    if samples not in {1, 3, 4}:
                        raise HTTPException(status_code=415, detail="عدد قنوات ألوان DICOM غير مدعوم")
                    frame_pixels = rows * cols
                    if frame_pixels > MAX_DICOM_FRAME_PIXELS:
                        raise HTTPException(status_code=413, detail="إطار DICOM الواحد يتجاوز حد 12 مليون بكسل")
                    estimated_pages += frame_count
                    estimated_pixels += frame_pixels * frame_count
                    estimated_sample_values += frame_pixels * frame_count * samples
                    if estimated_pages > MAX_DICOM_PAGES:
                        raise HTTPException(status_code=413, detail="الحد الأقصى 200 صفحة DICOM في الطلب الواحد")
                    if estimated_pixels > MAX_DICOM_TOTAL_PIXELS or estimated_sample_values > MAX_DICOM_TOTAL_SAMPLE_VALUES:
                        raise HTTPException(status_code=413, detail="تجاوزت سلسلة DICOM حد المعالجة الآمن البالغ 30 مليون بكسل أو 40 مليون قيمة لونية")
                    instance_number = int(getattr(dataset, "InstanceNumber", index + 1) or index + 1)
                    inputs.append((instance_number, index, src, frame_count, rows, cols, samples))
                except HTTPException:
                    raise
                except Exception as exc:
                    raise HTTPException(
                        status_code=422,
                        detail=f"تعذر قراءة ملف DICOM: {upload.filename or index + 1}",
                    ) from exc

            # Instance Number is only a fallback ordering key; it is not always an acquisition order.
            inputs.sort(key=lambda item: (item[0], item[1]))
            output_pdf = fitz.open()
            page_count = 0
            pixel_total = 0
            try:
                for _, _, src, expected_frames, expected_rows, expected_cols, expected_samples in inputs:
                    try:
                        dataset = pydicom.dcmread(src, force=True)
                        if not hasattr(dataset, "PixelData"):
                            raise HTTPException(status_code=415, detail="ملف DICOM لا يحتوي على Pixel Data")
                        rows = int(dataset.Rows)
                        cols = int(dataset.Columns)
                        samples = int(getattr(dataset, "SamplesPerPixel", 1) or 1)
                        if (rows, cols, samples) != (expected_rows, expected_cols, expected_samples):
                            raise HTTPException(status_code=422, detail="بيانات أبعاد DICOM تغيرت بين الفحص والمعالجة")
                        pixel_array = dataset.pixel_array

                        if pixel_array.ndim == 2:
                            frames = [pixel_array]
                        elif pixel_array.ndim == 3 and pixel_array.shape[-1] in (3, 4) and expected_frames == 1:
                            frames = [pixel_array]
                        elif pixel_array.ndim in (3, 4):
                            frames = [pixel_array[i] for i in range(pixel_array.shape[0])]
                        else:
                            raise HTTPException(status_code=422, detail="ترتيب Pixel Data في الملف غير مدعوم")
                        if len(frames) != expected_frames:
                            raise HTTPException(status_code=422, detail="عدد إطارات Pixel Data لا يطابق بيانات DICOM الوصفية")

                        for frame in frames:
                            page_count += 1
                            pixel_total += rows * cols
                            if page_count > MAX_DICOM_PAGES or pixel_total > MAX_DICOM_TOTAL_PIXELS:
                                raise HTTPException(status_code=413, detail="تجاوزت السلسلة حد 200 صفحة أو 30 مليون بكسل إجمالاً")
                            image = _dicom_to_rgb(frame, dataset)
                            image.thumbnail((2400, 2400), Image.Resampling.LANCZOS)
                            buffer = io.BytesIO()
                            image.save(buffer, format="JPEG", quality=93, optimize=True)
                            page_width = 595.0
                            page_height = page_width * image.height / max(image.width, 1)
                            if page_height > 842:
                                page_height = 842
                                page_width = page_height * image.width / max(image.height, 1)
                            page = output_pdf.new_page(width=page_width, height=page_height)
                            page.insert_image(page.rect, stream=buffer.getvalue())
                            buffer.close()
                            image.close()
                    except HTTPException:
                        raise
                    except Exception as exc:
                        syntax = str(getattr(getattr(dataset, "file_meta", None), "TransferSyntaxUID", "unknown"))
                        raise HTTPException(
                            status_code=422,
                            detail=f"تعذر فك بيانات الصورة المضغوطة داخل DICOM ({syntax}). جرّب ملفاً غير تالف وبضغط مدعوم.",
                        ) from exc

                if page_count == 0:
                    raise HTTPException(status_code=422, detail="لم يتم العثور على صور قابلة للتحويل")
                output_path = root / "dicom-images.pdf"
                output_pdf.set_metadata({
                    "title": "DICOM image export",
                    "author": "PDF Globe",
                    "subject": "Rendered pixel data only",
                })
                output_pdf.save(output_path, garbage=4, deflate=True)
            finally:
                output_pdf.close()

            return download_response(output_path, "dicom-images.pdf", "application/pdf")
