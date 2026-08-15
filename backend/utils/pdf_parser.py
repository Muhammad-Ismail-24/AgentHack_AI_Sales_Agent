"""Extract raw text from an uploaded company PDF, using PyMuPDF."""

from pathlib import Path

from utils.logger import get_logger
from utils.validators import sanitise_text

log = get_logger(__name__)


def extract_text_from_pdf(path: str | Path, max_chars: int = 200_000) -> str:
    """Return the full text of a PDF as a single string.

    Raises ValueError when the file is missing, is not a readable PDF, or
    contains no extractable text (a scanned-image PDF, typically).
    """
    path = Path(path)
    if not path.exists():
        raise ValueError(f"file not found: {path}")

    try:
        import fitz  # PyMuPDF
    except ImportError as exc:  # pragma: no cover
        raise ValueError(
            "PyMuPDF is not installed — run pip install -r requirements.txt"
        ) from exc

    try:
        with fitz.open(path) as doc:
            pages = [page.get_text() for page in doc]
    except Exception as exc:  # noqa: BLE001 - surface any parse failure as ValueError
        raise ValueError(f"could not read PDF {path.name}: {exc}") from exc

    text = sanitise_text("\n\n".join(pages), max_length=max_chars)
    if not text:
        raise ValueError(
            f"{path.name} has no extractable text — it may be a scanned image"
        )

    log.info("extracted %s chars from %s (%s pages)", len(text), path.name, len(pages))
    return text


def extract_text(path: str | Path) -> str:
    """Read a .pdf or a plain-text file and return its text either way."""
    path = Path(path)
    if path.suffix.lower() == ".pdf":
        return extract_text_from_pdf(path)
    if not path.exists():
        raise ValueError(f"file not found: {path}")
    return sanitise_text(path.read_text(encoding="utf-8", errors="replace"))
