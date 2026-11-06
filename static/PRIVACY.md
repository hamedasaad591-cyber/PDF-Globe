# PDF Globe Privacy Policy

**Last updated: 6 November 2026**  
**Contact:** hamedasaad591@gmail.com  
**Website:** https://pdf-globe.pages.dev/

This notice describes the current PDF Globe website and application implementation. It is general information, not legal advice.

## 1. How file processing works

### Browser-based tools

Merge, split/extract pages, rotate, delete/reorder pages, watermarks, page numbers, signatures, images-to-PDF, PDF-to-images, and OCR are designed to process content in the visitor's browser. These browser-based operations do not intentionally upload the selected file to the PDF Globe API. The browser may download software libraries, fonts, or OCR language data from third-party content delivery networks; OCR recognition itself runs in the browser.

### Server-based tools

PDF compression, PDF-to-Word conversion, Word-to-PDF conversion, PDF repair, and PDF password protection/unlocking currently use the PDF Globe API hosted by Render. When one of these tools is selected, the file is transmitted over HTTPS to the API for processing.

### Translation

Text is extracted or recognised in the browser and sent to the PDF Globe API. The API forwards the text to the configured translation provider. The current primary configuration is Cloudflare Workers AI. Depending on configuration or availability, LibreTranslate or the MyMemory public translation API may be used instead. The translation workflow intentionally sends extracted text, not the original PDF, to the translation provider. The translated text is then sent to the PDF Globe API to generate a DOCX output.

## 2. Temporary files and retention

For server-based operations, the application uses request-scoped temporary working folders and is designed to remove uploaded working files and generated outputs when the request finishes. PDF Globe does not provide a permanent document library or user file account. Application-level cleanup does not control hosting infrastructure logs, security records, backups, crash diagnostics, or records retained by providers under their own policies. Unexpected process interruption may affect normal cleanup.

If a visitor emails the operator, the email address and message content are received and retained as reasonably needed to respond, keep a record of the communication, and meet applicable obligations.

## 3. Service providers and external resources

- **Cloudflare Pages:** serves the static website and may process ordinary connection/security metadata.
- **Render:** hosts the API and may process request, network, operational, and security metadata. Files used by server-based tools pass through this API.
- **Cloudflare Workers AI:** receives extracted text when configured as the translation provider.
- **LibreTranslate or MyMemory:** may receive translation text if configured or used as a fallback.
- **External assets:** the website loads some libraries, fonts, and OCR language resources from Google Fonts, unpkg, cdnjs, and jsDelivr. These providers receive ordinary requests from the browser when assets are retrieved.

Provider notices: [Cloudflare](https://www.cloudflare.com/privacypolicy/), [Render](https://render.com/privacy), [Google](https://policies.google.com/privacy). Each provider operates under its own terms and policies.

## 4. Technical information, cookies, and analytics

Hosting and security providers may receive IP address, browser/device information, request time, requested URL, referring page, and error/security events to deliver, secure, and troubleshoot the service.

The current application does not require registration and its application code does not intentionally set first-party login or advertising cookies or store user profiles in browser storage. The current site code does not intentionally include third-party advertising pixels or an advertising network. Hosting/security providers may use their own technical mechanisms under their policies. This notice will be updated if analytics, advertising, or other tracking technologies are added.

## 5. Visitor choices and responsibilities

- Use browser-based processing when preferred and supported.
- Submit only files the visitor has the right to use and process.
- Avoid submitting highly sensitive identity, medical, financial, legal, or confidential business documents unless the provider arrangements have been reviewed and accepted.
- Keep original files and personal backups; PDF Globe is not a permanent storage or backup service.

## 6. Security and international processing

The public website and API use HTTPS. No internet transmission or storage method can be guaranteed completely secure. Hosting and translation providers may process information in countries other than the visitor's country under their own arrangements and applicable laws.

## 7. Privacy requests

Depending on applicable law, visitors may have rights to request access to, correction of, or deletion of personal information. Contact: **hamedasaad591@gmail.com**. Do not email passwords, API keys, or confidential document contents. The operator may request sufficient information to understand and verify a request.

## 8. Changes

This notice may change when the website, its providers, or applicable requirements change. The “Last updated” date identifies the current version.
