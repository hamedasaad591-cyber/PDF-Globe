import io
import tempfile
import zipfile
from pathlib import Path

import fitz
from fastapi import File, Form, HTTPException, UploadFile
from PIL import Image, ImageEnhance, ImageOps, UnidentifiedImageError
from pillow_heif import register_heif_opener

register_heif_opener()

# Keep the combined decoded-image working set within the memory budget of the
# small Render instance. The per-frame check is performed before source.copy()
# so oversized images are rejected before their full pixel buffer is allocated.
MAX_IMAGE_PIXELS_PER_FRAME = 25_000_000
MAX_BATCH_INPUT_PIXELS = 35_000_000
MAX_BATCH_OUTPUT_PIXELS = 40_000_000
MAX_BATCH_FRAMES = 240
Image.MAX_IMAGE_PIXELS = MAX_IMAGE_PIXELS_PER_FRAME


def register_image_routes(app, store_upload, download_response):
    input_exts = {
        ".jpg", ".jpeg", ".jfif", ".png", ".webp", ".avif", ".heic", ".heif",
        ".bmp", ".gif", ".tif", ".tiff", ".ico", ".tga", ".ppm", ".pgm",
        ".pbm", ".pcx",
    }
    output_formats = {
        "jpg": ("JPEG", ".jpg", "image/jpeg"), "jpeg": ("JPEG", ".jpg", "image/jpeg"),
        "png": ("PNG", ".png", "image/png"), "webp": ("WEBP", ".webp", "image/webp"),
        "avif": ("AVIF", ".avif", "image/avif"), "heic": ("HEIF", ".heic", "image/heic"),
        "bmp": ("BMP", ".bmp", "image/bmp"), "gif": ("GIF", ".gif", "image/gif"),
        "tiff": ("TIFF", ".tiff", "image/tiff"), "ico": ("ICO", ".ico", "image/x-icon"),
        "pdf": ("PDF", ".pdf", "application/pdf"),
    }

    @app.post("/api/image/convert")
    async def convert_images(
        files: list[UploadFile] = File(...),
        output_format: str = Form("webp"),
        width: int = Form(0),
        height: int = Form(0),
        keep_aspect: bool = Form(True),
        quality: int = Form(88),
        sharpen: int = Form(0),
        contrast: int = Form(0),
        brightness: int = Form(0),
        background: str = Form("#ffffff"),
    ):
        if not 1 <= len(files) <= 20:
            raise HTTPException(status_code=400, detail="اختر من صورة واحدة إلى 20 صورة")
        fmt = output_format.strip().lower()
        if fmt not in output_formats:
            raise HTTPException(status_code=415, detail="صيغة الإخراج غير مدعومة")
        if not (0 <= width <= 10000 and 0 <= height <= 10000):
            raise HTTPException(status_code=400, detail="أبعاد الإخراج يجب أن تكون بين 1 و10000 بكسل")
        if not 1 <= quality <= 100 or not 0 <= sharpen <= 100 or not 0 <= contrast <= 100 or not -50 <= brightness <= 50:
            raise HTTPException(status_code=400, detail="إعدادات الجودة والتحسين غير صالحة")
        try:
            bg = background if len(background) == 7 and background.startswith("#") else "#ffffff"
            int(bg[1:], 16)
        except Exception as exc:
            raise HTTPException(status_code=400, detail="لون الخلفية غير صالح") from exc

        with tempfile.TemporaryDirectory(prefix="pdfglobe-images-") as td:
            root = Path(td)
            output_dir = root / "output"
            output_dir.mkdir()
            converted = []
            total_bytes = 0
            total_input_pixels = 0
            total_output_pixels = 0
            total_processed_frames = 0

            for index, upload in enumerate(files, start=1):
                ext = Path(upload.filename or "").suffix.lower()
                if ext not in input_exts:
                    raise HTTPException(status_code=415, detail=f"صيغة الصورة غير مدعومة: {ext or 'بدون امتداد'}")
                sub = root / f"input-{index:02d}"
                sub.mkdir()
                src = await store_upload(upload, sub, input_exts)
                total_bytes += src.stat().st_size
                if total_bytes > 120 * 1024 * 1024:
                    raise HTTPException(status_code=413, detail="الحد الإجمالي لصور الدفعة هو 120 MB")

                try:
                    with Image.open(src) as source:
                        frame_count = int(getattr(source, "n_frames", 1) or 1)
                        if frame_count > 120:
                            raise HTTPException(status_code=413, detail="الصورة المتحركة تتجاوز 120 إطاراً")
                        preserve_frames = fmt in {"gif", "tiff"} and frame_count > 1
                        frame_indexes = range(frame_count) if preserve_frames else range(1)
                        if total_processed_frames + len(frame_indexes) > MAX_BATCH_FRAMES:
                            raise HTTPException(status_code=413, detail=f"الحد الأقصى للدفعة هو {MAX_BATCH_FRAMES} إطاراً صورياً")
                        frames = []
                        durations = []

                        for frame_index in frame_indexes:
                            source.seek(frame_index)
                            source_width, source_height = source.size
                            original_pixels = int(source_width) * int(source_height)
                            total_input_pixels += original_pixels
                            total_processed_frames += 1
                            if original_pixels > MAX_IMAGE_PIXELS_PER_FRAME:
                                raise HTTPException(status_code=413, detail="الصورة الواحدة تتجاوز حد المعالجة الآمن البالغ 25 مليون بكسل")
                            if total_input_pixels > MAX_BATCH_INPUT_PIXELS:
                                raise HTTPException(status_code=413, detail="تجاوزت الدفعة حد المعالجة البالغ 35 مليون بكسل أصلي إجمالاً")
                            # Copy/decode only after the dimensions have passed the pixel budget.
                            frame = ImageOps.exif_transpose(source.copy())

                            if width or height:
                                sw = width / frame.width if width else float("inf")
                                sh = height / frame.height if height else float("inf")
                                if keep_aspect:
                                    scale = min(sw, sh)
                                    new_size = (max(1, round(frame.width * scale)), max(1, round(frame.height * scale)))
                                else:
                                    new_size = (width or frame.width, height or frame.height)
                                new_pixels = new_size[0] * new_size[1]
                                if new_pixels > MAX_IMAGE_PIXELS_PER_FRAME:
                                    raise HTTPException(status_code=413, detail="أبعاد الصورة الناتجة تتجاوز حد 25 مليون بكسل")
                                if new_size != frame.size:
                                    frame = frame.resize(new_size, Image.Resampling.LANCZOS)

                            output_pixels = frame.width * frame.height
                            total_output_pixels += output_pixels
                            if total_output_pixels > MAX_BATCH_OUTPUT_PIXELS:
                                raise HTTPException(status_code=413, detail="تجاوزت الصور الناتجة حد المعالجة البالغ 40 مليون بكسل إجمالاً")

                            if brightness:
                                frame = ImageEnhance.Brightness(frame).enhance(1 + brightness / 100.0)
                            if contrast:
                                frame = ImageEnhance.Contrast(frame).enhance(1 + contrast / 100.0)
                            if sharpen:
                                frame = ImageEnhance.Sharpness(frame).enhance(1 + sharpen / 50.0)
                            frames.append(frame)
                            durations.append(int(source.info.get("duration", 100) or 100))

                        safe_base = "".join(ch if ch.isalnum() or ch in "-_." else "_" for ch in Path(upload.filename or f"image-{index}").stem)[:70]
                        safe_base = safe_base or f"image-{index}"
                        out_path = output_dir / (f"{index:02d}_{safe_base}" + output_formats[fmt][1])

                        if fmt == "pdf":
                            part_pdf = fitz.open()
                            try:
                                for frame in frames:
                                    rgb = frame.convert("RGB")
                                    buffer = io.BytesIO()
                                    rgb.save(buffer, format="JPEG", quality=94, optimize=True)
                                    page_width = 595.0
                                    page_height = page_width * rgb.height / max(rgb.width, 1)
                                    if page_height > 842:
                                        page_height = 842
                                        page_width = page_height * rgb.width / max(rgb.height, 1)
                                    page = part_pdf.new_page(width=page_width, height=page_height)
                                    page.insert_image(page.rect, stream=buffer.getvalue())
                                    buffer.close()
                                    rgb.close()
                                part_pdf.save(out_path, garbage=4, deflate=True)
                            finally:
                                part_pdf.close()
                        else:
                            first = frames[0]
                            options = {}
                            pillow_format = output_formats[fmt][0]

                            if fmt in {"jpg", "jpeg"}:
                                rgba = first.convert("RGBA")
                                canvas = Image.new("RGBA", rgba.size, bg)
                                first = Image.alpha_composite(canvas, rgba).convert("RGB")
                                options.update(quality=quality, optimize=True, progressive=True)
                            elif fmt == "webp":
                                if first.mode not in {"RGB", "RGBA"}:
                                    first = first.convert("RGBA" if "transparency" in first.info else "RGB")
                                options.update(quality=quality, method=6)
                            elif fmt == "avif":
                                if first.mode not in {"RGB", "RGBA"}:
                                    first = first.convert("RGBA" if "transparency" in first.info else "RGB")
                                options.update(quality=quality, speed=6)
                            elif fmt == "heic":
                                first = first.convert("RGB")
                                options.update(quality=quality)
                            elif fmt == "png":
                                options.update(optimize=True, compress_level=6)
                            elif fmt == "tiff":
                                options.update(compression="tiff_lzw")
                                if len(frames) > 1:
                                    options.update(save_all=True, append_images=frames[1:])
                            elif fmt == "ico":
                                first = first.convert("RGBA")
                                options.update(sizes=[(16,16),(32,32),(48,48),(64,64),(128,128),(256,256)])
                            elif fmt == "gif":
                                frames = [f.convert("P", palette=Image.Palette.ADAPTIVE) for f in frames]
                                gif_duration = durations if len(frames) > 1 else (durations[0] if durations else 100)
                                options.update(save_all=len(frames) > 1, append_images=frames[1:], duration=gif_duration, loop=0, optimize=True, disposal=2)
                                first = frames[0]
                            elif fmt == "bmp":
                                first = first.convert("RGB")

                            first.save(out_path, format=pillow_format, **options)

                        for frame in frames:
                            try:
                                frame.close()
                            except Exception:
                                pass
                        converted.append(out_path)

                except HTTPException:
                    raise
                except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError) as exc:
                    raise HTTPException(status_code=415, detail=f"تعذر فتح أو تحويل {upload.filename or index}. تحقق من الصيغة وأن الملف غير تالف.") from exc
                except Exception as exc:
                    raise HTTPException(status_code=422, detail=f"فشل تحويل {upload.filename or index}: {str(exc)[:160]}") from exc

            if fmt == "pdf":
                if len(converted) == 1:
                    return download_response(converted[0], converted[0].name.split("_", 1)[-1], "application/pdf")
                merged = fitz.open()
                try:
                    for path in converted:
                        with fitz.open(path) as part:
                            merged.insert_pdf(part)
                    output = root / "converted-images.pdf"
                    merged.save(output, garbage=4, deflate=True)
                finally:
                    merged.close()
                return download_response(output, output.name, "application/pdf")

            if len(converted) == 1:
                path = converted[0]
                return download_response(path, path.name.split("_", 1)[-1], output_formats[fmt][2])

            archive = root / "converted-images.zip"
            with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
                for path in converted:
                    bundle.write(path, arcname=path.name)
            return download_response(archive, archive.name, "application/zip")
