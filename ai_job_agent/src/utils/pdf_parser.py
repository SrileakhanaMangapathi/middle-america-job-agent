"""PDF text extraction utility using pdfplumber."""
from __future__ import annotations

import logging
from pathlib import Path

from ai_job_agent.src.utils.logger import setup_logger

_logger: logging.Logger = setup_logger("pdf_parser")


def extract_text_from_pdf(pdf_path: str | Path) -> str:
    """Extract all text from a PDF file using pdfplumber.

    Args:
        pdf_path: Path to the PDF file.

    Returns:
        Concatenated text from all pages, stripped of leading/trailing whitespace.

    Raises:
        FileNotFoundError: If the PDF does not exist.
        RuntimeError: If pdfplumber is not installed.
    """
    path = Path(pdf_path)
    if not path.exists():
        raise FileNotFoundError(f"PDF not found: {path}")

    try:
        import pdfplumber
    except ImportError as exc:
        raise RuntimeError(
            "pdfplumber is required for PDF parsing. "
            "Install it with: pip install pdfplumber"
        ) from exc

    _logger.info("Extracting text from PDF: %s", path)
    pages_text: list[str] = []

    with pdfplumber.open(path) as pdf:
        for i, page in enumerate(pdf.pages):
            text = page.extract_text() or ""
            pages_text.append(text)
            _logger.debug("Page %d: %d chars extracted", i + 1, len(text))

    full_text = "\n\n".join(pages_text).strip()
    _logger.info(
        "Extraction complete: %d chars across %d pages", len(full_text), len(pages_text)
    )
    return full_text
