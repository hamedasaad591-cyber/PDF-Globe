# PDF Globe — Global PDF Tools

A responsive, multilingual PDF workspace with browser-side processing and a small FastAPI backend for conversions and translation.

## Included tools

- Merge PDF files
- Extract/split selected pages
- Compress PDF (PyMuPDF rewrite/deflate)
- Rotate, delete, and reorder pages
- PDF to editable DOCX (pdf2docx)
- DOC/DOCX/ODT/RTF to PDF (LibreOffice)
- JPG/PNG/WEBP images to PDF
- PDF pages to JPG images in a ZIP
- Add a text watermark, page numbers, or a drawn signature
- Password-protect and unlock PDFs (qpdf)
- Attempt PDF repair by rewriting the document
- OCR for PDF scans and images (Tesseract.js in the browser)
- Translate selectable PDF text and export it as DOCX

Most PDF actions run locally in the visitor's browser. Server-side conversion tools temporarily receive an uploaded file to perform the requested task. Temporary directories are deleted after each request. Translation text is sent to the configured translation provider (LibreTranslate when configured; otherwise the MyMemory public API fallback). See `PRIVACY.md` before operating this service publicly.

## Run locally with Docker (recommended)

Requirements: Docker Desktop or Docker Engine.

```bash
docker build -t pdf-globe .
docker run --rm -p 8080:8080 -e MAX_UPLOAD_MB=50 pdf-globe
```

Open `http://localhost:8080`.

## Run locally without Docker

Python 3.12 is recommended. In addition to Python dependencies, install:

- LibreOffice Writer (`libreoffice`) for Word-to-PDF conversion
- qpdf for PDF password operations
- A modern browser with JavaScript enabled

```bash
python -m venv .venv
# Windows PowerShell: .venv\Scripts\Activate.ps1
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --host 127.0.0.1 --port 8080
```

Open `http://127.0.0.1:8080`.

## Deploy publicly

The repository contains a `Dockerfile` and `render.yaml` blueprint for a Docker-capable host. A typical deployment flow is:

1. Create a GitHub repository and upload this project folder.
2. In your hosting provider, create a new web service from that repository and select Docker/Blueprint deployment.
3. Set `MAX_UPLOAD_MB` to a limit appropriate for your service plan (default 50).
4. Deploy and test `/api/health`, PDF upload, conversion and download from a second device/network.
5. Connect a custom domain in the hosting provider's dashboard and configure its DNS as instructed by the provider.
6. Configure a reliable translation endpoint in `LIBRETRANSLATE_URL`; set `LIBRETRANSLATE_API_KEY` if that endpoint requires a key. The fallback MyMemory public API is rate-limited/availability-dependent and is not suitable as a guaranteed unlimited production service.

The free hosting tiers of third-party providers can sleep, impose CPU/storage/bandwidth limits, change their terms, or stop being available. This project does not promise unlimited free usage. A public service needs monitoring, abuse protection/rate limits, backups for configuration, and a clear support contact before promotion.

## Translation notes

- The translation action extracts selectable text and automatically OCRs pages that have no text layer, using the OCR language codes entered in the tool. For mixed pages with both image text and selectable text, a separate OCR pass may still be needed.
- The translated output is a DOCX text document. Complex original page layout, tables, columns, embedded charts and scanned signatures are not preserved as a faithful page-for-page translation.
- Automatic translation can make mistakes in names, numbers, legal, medical, financial and technical terminology. Human review is required before official use.
- Language availability depends on the configured translation provider and the source/target pair. Selecting a language in the interface does not guarantee that a provider supports that pair.

## Important limitations

- PDF-to-Word quality varies with fonts, tables, columns and source PDF complexity. Scanned PDFs need OCR first; OCR output is plain text, not a reconstructed Word layout.
- Browser-side tools require a modern browser and sufficient device memory. Very large PDFs may be slow on phones.
- Password recovery is not provided. Unlock only files for which the visitor knows the password and is authorized to process.
- The repair tool attempts to rewrite a readable PDF; it cannot recover every damaged file.
- This code is an initial deployable product, not a certification of legal compliance, accessibility, security, or 100% conversion accuracy. Review the privacy and terms pages with a qualified professional before operating commercially.

## Environment variables

| Variable | Purpose | Default |
|---|---|---|
| `PORT` | HTTP port assigned by host | `8080` |
| `MAX_UPLOAD_MB` | Maximum upload size for server-side operations | `50` |
| `LIBRETRANSLATE_URL` | Base URL of a LibreTranslate-compatible API, without `/translate` | empty |
| `LIBRETRANSLATE_API_KEY` | Optional API key for that translation service | empty |

## Project structure

```text
pdf-globe/
  main.py
  requirements.txt
  Dockerfile
  render.yaml
  static/
    index.html
    style.css
    app.js
  README.md
  PRIVACY.md
  TERMS.md
```
