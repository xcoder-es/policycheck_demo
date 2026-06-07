"""PDF text extraction helpers."""

import io

MAX_PDF_PAGES = 40
MAX_EXTRACTED_CHARS = 120_000


def extract_text_from_pdf_bytes(content: bytes) -> str:
    """Extract text from a text-based PDF using pypdf, without OCR."""
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise RuntimeError("PDF support is not installed. Please install pypdf.") from exc

    reader = PdfReader(io.BytesIO(content))
    extracted_pages = []

    for page in reader.pages[:MAX_PDF_PAGES]:
        page_text = page.extract_text() or ""
        if page_text.strip():
            extracted_pages.append(page_text)
        if sum(len(part) for part in extracted_pages) >= MAX_EXTRACTED_CHARS:
            break

    return "\n\n".join(extracted_pages)[:MAX_EXTRACTED_CHARS]
