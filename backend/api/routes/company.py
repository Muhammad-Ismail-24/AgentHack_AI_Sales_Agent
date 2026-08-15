"""POST /company/upload and POST /company/text — step 1 of onboarding."""

import uuid
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile

from api import orchestrator_bridge
from api.schemas import CompanyTextRequest, CompanyUploadResponse
from config.settings import settings
from memory.short_term import short_term_memory
from utils.logger import get_logger
from utils.pdf_parser import extract_text
from utils.validators import sanitise_text

log = get_logger(__name__)
router = APIRouter(prefix="/company", tags=["company"])

ALLOWED_SUFFIXES = {".pdf", ".txt", ".md"}
MAX_UPLOAD_BYTES = 20 * 1024 * 1024  # 20 MB


@router.post("/upload", response_model=CompanyUploadResponse)
async def upload_company_file(file: UploadFile = File(...)) -> CompanyUploadResponse:
    """Accept a company PDF, store it, and hand it to the RAG pipeline."""
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{suffix or 'unknown'}'. Upload a PDF or .txt file.",
        )

    contents = await file.read()
    if not contents:
        raise HTTPException(status_code=400, detail="The uploaded file is empty.")
    if len(contents) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File is larger than 20 MB.")

    session_id = str(uuid.uuid4())
    upload_dir = Path(settings.UPLOAD_DIR)
    upload_dir.mkdir(parents=True, exist_ok=True)
    dest = upload_dir / f"{session_id}{suffix}"
    dest.write_bytes(contents)

    try:
        text = extract_text(dest)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    result = await orchestrator_bridge.ingest_company(
        session_id=session_id, text=text, filepath=str(dest)
    )

    short_term_memory.set_company(
        session_id,
        {
            "company_name": result.get("company_name"),
            "text": text,
            "source": file.filename,
            "ingested": result.get("ingested", False),
        },
    )

    log.info("ingested %s for session %s", file.filename, session_id)
    return CompanyUploadResponse(
        session_id=session_id,
        company_name=result.get("company_name", "Your Company"),
        status="ingested",
        chars_ingested=len(text),
        message=result.get("message"),
    )


@router.post("/text", response_model=CompanyUploadResponse)
async def submit_company_text(payload: CompanyTextRequest) -> CompanyUploadResponse:
    """Accept a pasted company description instead of a file."""
    text = sanitise_text(payload.text)
    if len(text) < 20:
        raise HTTPException(
            status_code=400,
            detail="Please paste a longer description — at least a couple of sentences.",
        )

    session_id = str(uuid.uuid4())
    result = await orchestrator_bridge.ingest_company(session_id=session_id, text=text)

    company_name = payload.company_name or result.get("company_name", "Your Company")
    short_term_memory.set_company(
        session_id,
        {
            "company_name": company_name,
            "text": text,
            "source": "pasted text",
            "ingested": result.get("ingested", False),
        },
    )

    log.info("ingested pasted text (%s chars) for session %s", len(text), session_id)
    return CompanyUploadResponse(
        session_id=session_id,
        company_name=company_name,
        status="ingested",
        chars_ingested=len(text),
        message=result.get("message"),
    )
