"""POST /pipeline/start and GET /pipeline/status/{session_id}.

The frontend polls the status endpoint every 3 seconds while a run is live.
"""

import asyncio

from fastapi import APIRouter, HTTPException

from api import orchestrator_bridge
from api.schemas import (
    PipelineStartRequest,
    PipelineStartResponse,
    PipelineStatusResponse,
)
from db import acrud
from db.models import ACTIVE_STAGES
from memory.long_term import long_term_memory
from memory.short_term import short_term_memory
from utils.logger import get_logger

log = get_logger(__name__)
router = APIRouter(prefix="/pipeline", tags=["pipeline"])

# Keeps a reference to each running task so it is not garbage collected
# mid-run, and so a duplicate /start is rejected instead of racing.
_running: dict[str, asyncio.Task] = {}


async def _run_and_persist(session_id: str, company: dict, icp: dict) -> None:
    """Background task: run the graph, then write the results to Firestore."""
    try:
        short_term_memory.set_pipeline_stage(session_id, "Discovering leads")
        state = await orchestrator_bridge.run_pipeline(
            session_id=session_id, company=company, icp=icp
        )

        if isinstance(state, dict):
            short_term_memory.set_pipeline_state(session_id, state)
            leads = state.get("outreach_queue") or state.get("qualified_leads") or []
            if leads:
                await long_term_memory.remember_leads(leads, session_id)

        short_term_memory.set_pipeline_stage(session_id, "complete")
        log.info("pipeline complete for session %s", session_id)

    except asyncio.CancelledError:
        short_term_memory.set_pipeline_stage(session_id, "idle")
        raise
    except Exception as exc:  # noqa: BLE001 - a failed run must not kill the app
        log.exception("pipeline failed for session %s", session_id)
        short_term_memory.set_pipeline_stage(session_id, "failed")
        short_term_memory.update_pipeline_state(session_id, error=str(exc))
    finally:
        _running.pop(session_id, None)


@router.post("/start", response_model=PipelineStartResponse)
async def start_pipeline(payload: PipelineStartRequest) -> PipelineStartResponse:
    """Kick off a full pipeline run in the background."""
    session_id = payload.session_id

    if session_id in _running and not _running[session_id].done():
        raise HTTPException(
            status_code=409, detail="A pipeline run is already in progress for this session."
        )

    company = short_term_memory.get_company(session_id)
    icp = short_term_memory.get_icp(session_id)
    if company is None:
        raise HTTPException(status_code=404, detail="No company info found for this session.")
    if icp is None:
        raise HTTPException(status_code=404, detail="No ICP defined for this session.")

    if not orchestrator_bridge.is_available():
        raise HTTPException(
            status_code=503,
            detail=(
                "The agent pipeline is not available in this build. "
                "Load the demo seed data to explore the dashboard."
            ),
        )

    short_term_memory.set_pipeline_stage(session_id, "starting")
    _running[session_id] = asyncio.create_task(
        _run_and_persist(session_id, company, icp)
    )

    log.info("pipeline started for session %s", session_id)
    return PipelineStartResponse(session_id=session_id, status="running")


@router.get("/status/{session_id}", response_model=PipelineStatusResponse)
async def get_pipeline_status(session_id: str) -> PipelineStatusResponse:
    """Current stage plus live lead counts. Safe to poll every few seconds."""
    stage = short_term_memory.get_pipeline_stage(session_id) or "idle"
    state = short_term_memory.get_pipeline_state(session_id) or {}

    task = _running.get(session_id)
    is_running = task is not None and not task.done()

    stage_counts = await acrud.count_leads_by_stage(session_id)

    return PipelineStatusResponse(
        session_id=session_id,
        stage=stage,
        is_running=is_running,
        raw_leads_count=len(state.get("raw_leads") or []),
        filtered_count=len(state.get("filtered_leads") or []),
        qualified_count=len(state.get("qualified_leads") or []),
        outreach_count=len(state.get("outreach_queue") or []),
        total_leads=sum(stage_counts.values()),
        stage_counts={s: stage_counts.get(s, 0) for s in ACTIVE_STAGES}
        | {k: v for k, v in stage_counts.items() if k not in ACTIVE_STAGES},
        error=state.get("error"),
    )


@router.post("/stop/{session_id}", response_model=PipelineStartResponse)
async def stop_pipeline(session_id: str) -> PipelineStartResponse:
    """Cancel a run in progress — handy if a demo goes sideways."""
    task = _running.get(session_id)
    if task is None or task.done():
        raise HTTPException(status_code=404, detail="No pipeline is running for this session.")
    task.cancel()
    short_term_memory.set_pipeline_stage(session_id, "idle")
    return PipelineStartResponse(session_id=session_id, status="stopped")
