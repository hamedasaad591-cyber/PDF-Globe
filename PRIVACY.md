# Privacy notice — PDF Globe

**Draft notice.** Replace the operator contact details and have this notice reviewed for the jurisdictions in which the service will operate before public launch.

## What this service processes

PDF Globe lets visitors select files and run document operations. Many operations (merge, page extraction, rotation, watermarking, page numbering, signing, image conversion, PDF rendering and browser OCR) run in the visitor's browser. Server-side features (compression, PDF/Word conversion, password operations, repair and translation output generation) send the selected file or extracted text to the PDF Globe server for the requested operation.

## Temporary processing

The application writes server-side uploads and generated outputs into a temporary directory for the duration of a request. The directory is removed when the request completes. The application does not implement a permanent file library or user account system. Hosting infrastructure may still retain operational logs, security logs, backups, crash data or network metadata according to the hosting provider's policies.

## Third-party services

- The website loads JavaScript libraries and web fonts from third-party CDNs. Those providers may receive ordinary connection metadata such as IP address and browser headers.
- OCR language data may be downloaded by Tesseract.js from its configured language-data host.
- Translation sends extracted document text to the configured translation provider. If `LIBRETRANSLATE_URL` is configured, that service receives the text. Otherwise the current fallback sends text to the MyMemory public translation API. These providers operate under their own privacy terms and may process or retain requests independently of PDF Globe.
- The site operator should list the exact providers and links to their current privacy terms here before public launch.

## Sensitive information

Do not upload information that you are not authorized to process. Avoid uploading identity documents, medical records, financial records, confidential business materials or legal documents unless you have reviewed the data-processing arrangements and are comfortable with them. The visitor must obtain any required consent from other people whose information appears in a document.

## Cookies and tracking

This starter project does not include advertising pixels, analytics scripts, or account cookies. The interface uses browser memory only for its current operation. Hosting providers, CDNs or future added services may use their own technical mechanisms; update this notice if such services are added.

## Security and contact

The operator should use HTTPS, keep dependencies and the hosting environment updated, restrict upload sizes, configure abuse controls/rate limits, monitor errors, and publish a monitored privacy contact before launch.

**Operator contact:** add a real contact email and legal operator name before public launch.
