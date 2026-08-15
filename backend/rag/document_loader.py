"""Loads raw company knowledge from either a PDF file or plain text."""

from backend.utils.logger import logger
from backend.utils.pdf_parser import extract_text


def load_from_pdf(filepath: str) -> str:
    """Extract raw text from a company PDF using pdf_parser.py."""
    text = extract_text(filepath)
    if not text:
        logger.warning(f"No text extracted from PDF: {filepath}")
    return text.strip()


def load_from_text(text: str) -> str:
    """Basic clean-up pass over raw pasted company text."""
    if not text:
        return ""
    # Normalise line endings and collapse excessive blank lines.
    cleaned = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [line.strip() for line in cleaned.split("\n")]
    return "\n".join(lines).strip()
