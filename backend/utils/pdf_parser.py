import fitz  # PyMuPDF

from backend.utils.logger import logger


def extract_text(filepath: str) -> str:
    text = ""
    try:
        with fitz.open(filepath) as doc:
            for page in doc:
                text += page.get_text()
    except Exception as e:
        logger.error(f"Error reading PDF {filepath}: {e}")
    return text
