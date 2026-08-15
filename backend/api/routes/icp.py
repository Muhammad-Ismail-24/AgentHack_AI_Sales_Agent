"""POST /icp/define — step 2 of onboarding, right before the pipeline runs."""

from fastapi import APIRouter, HTTPException

from api import orchestrator_bridge
from api.schemas import ICPRequest, ICPResponse
from memory.short_term import short_term_memory
from utils.logger import get_logger

log = get_logger(__name__)
router = APIRouter(prefix="/icp", tags=["icp"])


@router.post("/define", response_model=ICPResponse)
async def define_icp(payload: ICPRequest) -> ICPResponse:
    """Turn the ICP form into a structured profile and stash it on the session."""
    if short_term_memory.get_company(payload.session_id) is None:
        raise HTTPException(
            status_code=404,
            detail=(
                "No company info found for this session. "
                "Upload your company PDF or paste a description first."
            ),
        )

    raw_icp = {
        "location": payload.location,
        "industry": payload.industry,
        "company_size": payload.company_size,
        "special_focus": payload.special_focus or "",
    }

    icp = await orchestrator_bridge.build_icp(
        session_id=payload.session_id, raw_icp=raw_icp
    )

    short_term_memory.set_icp(payload.session_id, icp)
    short_term_memory.set_pipeline_stage(payload.session_id, "ICP defined")

    log.info("ICP set for session %s: %s", payload.session_id, raw_icp)
    return ICPResponse(session_id=payload.session_id, icp=icp)


@router.get("/{session_id}", response_model=ICPResponse)
async def get_icp(session_id: str) -> ICPResponse:
    """Read back the ICP for a session — used when reloading the dashboard."""
    icp = short_term_memory.get_icp(session_id)
    if icp is None:
        raise HTTPException(status_code=404, detail="No ICP defined for this session.")
    return ICPResponse(session_id=session_id, icp=icp)
