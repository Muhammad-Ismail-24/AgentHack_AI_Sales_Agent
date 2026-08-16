"""Adapter between my routes and Ismail's agent pipeline.

`backend/agents/orchestrator.py` is built on a different branch. Rather than
having my routes import it directly — which would make the whole API fail to
start whenever that file is missing or mid-refactor — everything goes through
these two functions.

If the orchestrator is importable, it is used. If it is not, the routes still
work and return a clear "pipeline not available" state instead of a 500, so
the frontend and the seeded demo remain fully usable.

Delete nothing here when the agents branch merges — the import simply starts
succeeding.
"""

from typing import Any, Callable

from utils.logger import get_logger

log = get_logger(__name__)


def _load(name: str) -> Callable | None:
    """Import a callable from agents.orchestrator, or None if unavailable."""
    try:
        from agents import orchestrator  # noqa: PLC0415 - deliberately lazy
    except Exception as exc:  # noqa: BLE001 - missing module or broken import
        log.warning("agents.orchestrator unavailable (%s)", exc)
        return None

    fn = getattr(orchestrator, name, None)
    if fn is None:
        log.warning("agents.orchestrator has no %s()", name)
    return fn


def is_available() -> bool:
    return _load("run_pipeline") is not None


async def run_pipeline(*, session_id: str, raw_input: str, input_type: str, icp: dict) -> Any:
    """Run the full LangGraph pipeline. Raises if the orchestrator is missing."""
    fn = _load("run_pipeline")
    if fn is None:
        raise RuntimeError(
            "Agent pipeline is not available in this build "
            "(backend/agents/orchestrator.py not found)."
        )
    return await fn(
        session_id=session_id,
        raw_input=raw_input,
        input_type=input_type,
        icp_raw=icp,
    )


def _require(name: str) -> Callable:
    """Load an orchestrator function or raise something a route can turn into
    a 503. Used by the intelligence extras, which have no useful fallback —
    a fabricated debate or post-mortem would be worse than an honest error."""
    fn = _load(name)
    if fn is None:
        raise RuntimeError(
            f"The agent pipeline is not available in this build, so {name}() "
            "cannot run (backend/agents/orchestrator.py not found or broken)."
        )
    return fn


async def run_devils_advocate(*, lead: dict) -> dict[str, Any]:
    """Prosecutor/Defender/Judge debate over one lead."""
    return await _require("run_devils_advocate")(lead)


async def run_autopsy(
    *,
    lead: dict,
    contacts: list[dict],
    emails: list[dict],
    replies: list[dict],
    events: list[dict],
) -> dict[str, Any]:
    """Post-mortem for one dead lead."""
    return await _require("run_autopsy")(lead, contacts, emails, replies, events)


def summarise_autopsies(*, autopsies: list[dict]) -> dict[str, Any]:
    """Aggregate post-mortems into ICP adjustments. Pure, no LLM call."""
    return _require("summarise_autopsies")(autopsies)


async def build_meeting_whisper(*, meeting_id: str) -> dict[str, Any] | None:
    """The pre-call script for a meeting."""
    return await _require("build_meeting_whisper")(meeting_id)


async def deliver_whisper_audio(*, meeting_id: str) -> dict[str, Any]:
    """The whisper as a voice note, sent to the admin on WhatsApp."""
    return await _require("deliver_whisper_audio")(meeting_id)


async def build_icp(*, session_id: str, raw_icp: dict) -> dict[str, Any]:
    """Turn the ICP form into a structured profile via Ismail's ICP agent.

    Falls back to echoing the form fields, which is a perfectly usable ICP.
    """
    fn = _load("build_icp")
    if fn is None:
        return {
            **raw_icp,
            "structured": False,
            "summary": (
                f"{raw_icp.get('company_size', 'any size')} "
                f"{raw_icp.get('industry', 'companies')} in "
                f"{raw_icp.get('location', 'any location')}"
            ),
        }

    icp = await fn(session_id=session_id, raw_icp=raw_icp)
    return icp if isinstance(icp, dict) else {**raw_icp, "structured": False}
