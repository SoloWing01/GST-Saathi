"""Extract raw text from uploaded notices.

Supported inputs:
- PDF (text-based): uses pdfplumber
- PDF (scanned/image): falls back to OCR via pytesseract
- Image (jpg/png/tiff): OCR via pytesseract
- Plain text: returned as-is

The caller passes raw bytes + a content type; this module returns the
extracted text (or raises ValueError on unsupported types).
"""

from __future__ import annotations

import io
import logging

from PIL import Image

log = logging.getLogger(__name__)

# Content types we handle
_TEXT_TYPES = {"text/plain"}
_PDF_TYPES = {"application/pdf"}
_IMAGE_TYPES = {
    "image/jpeg",
    "image/png",
    "image/tiff",
    "image/bmp",
    "image/webp",
}


def extract_text(data: bytes, content_type: str) -> str:
    """Extract raw text from file bytes.

    Args:
        data: Raw file contents.
        content_type: MIME type of the file.

    Returns:
        Extracted text string (may be empty if nothing could be extracted).

    Raises:
        ValueError: If the content type is not supported.
    """
    ct = content_type.lower().split(";")[0].strip()

    if ct in _TEXT_TYPES:
        return data.decode("utf-8", errors="replace")

    if ct in _PDF_TYPES:
        return _extract_from_pdf(data)

    if ct in _IMAGE_TYPES:
        return _extract_from_image(data)

    raise ValueError(f"Unsupported content type: {content_type}")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _extract_from_pdf(data: bytes) -> str:
    """Try pdfplumber first; fall back to OCR if no text found."""
    text = _pdfplumber_extract(data)
    if text.strip():
        log.info("PDF text extracted via pdfplumber (%d chars)", len(text))
        return text

    log.info("pdfplumber returned no text, falling back to OCR")
    return _ocr_pdf_pages(data)


def _pdfplumber_extract(data: bytes) -> str:
    """Extract text from a text-based PDF using pdfplumber."""
    import pdfplumber

    with pdfplumber.open(io.BytesIO(data)) as pdf:
        pages = [page.extract_text() or "" for page in pdf.pages]
    return "\n\n".join(pages)


def _ocr_pdf_pages(data: bytes) -> str:
    """Convert each PDF page to an image, then OCR it."""
    import pdfplumber

    with pdfplumber.open(io.BytesIO(data)) as pdf:
        texts = []
        for i, page in enumerate(pdf.pages):
            img = page.to_image(resolution=300)
            # pdfplumber Image object has a .original (PIL Image)
            pil_img = img.original
            page_text = _ocr_pil_image(pil_img)
            texts.append(page_text)
            log.info("OCR page %d: %d chars", i + 1, len(page_text))
    return "\n\n".join(texts)


def _extract_from_image(data: bytes) -> str:
    """OCR an image file."""
    img = Image.open(io.BytesIO(data))
    return _ocr_pil_image(img)


def _ocr_pil_image(img: Image.Image) -> str:
    """Run pytesseract on a PIL Image."""
    import pytesseract

    # Convert to RGB if needed (tesseract doesn't handle RGBA/P-mode well)
    if img.mode not in ("RGB", "L"):
        img = img.convert("RGB")

    text = pytesseract.image_to_string(img)
    return text.strip()
