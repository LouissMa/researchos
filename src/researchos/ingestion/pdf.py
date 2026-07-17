"""Optional PDF full-text extraction via PyMuPDF.

Kept optional (``researchos[pdf]``) so the default install stays light and offline. When
disabled, papers carry title + abstract only, which is enough for the foundation's
retrieval and landscape building.
"""

from __future__ import annotations

import httpx

from researchos.logging import get_logger

log = get_logger(__name__)


def pdf_available() -> bool:
    try:
        import fitz  # noqa: F401  (PyMuPDF)

        return True
    except Exception:
        return False


def fetch_pdf_text(pdf_url: str, timeout: float = 60.0, max_pages: int = 20) -> str | None:
    """Download a PDF and extract text. Returns None on any failure (best-effort)."""
    if not pdf_url or not pdf_available():
        return None
    try:
        import fitz

        resp = httpx.get(pdf_url, timeout=timeout, follow_redirects=True)
        resp.raise_for_status()
        doc = fitz.open(stream=resp.content, filetype="pdf")
        pages = [doc[i].get_text() for i in range(min(len(doc), max_pages))]
        doc.close()
        return "\n".join(pages).strip() or None
    except Exception as exc:  # never let PDF issues break a run
        log.warning("PDF extraction failed for %s: %s", pdf_url, exc)
        return None
