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


async def ingest_company(
    *, session_id: str, text: str | None = None, filepath: str | None = None
) -> dict[str, Any]:
    """Send company info into RAG. Returns {company_name, chars, ingested}.

    Falls back to a no-RAG result carrying the raw text so onboarding still
    completes and the ICP step can proceed.
    """
    fn = _load("ingest_company")
    if fn is None:
        chars = len(text or "")
        return {
            "company_name": "Your Company",
            "chars": chars,
            "ingested": False,
            "message": "RAG pipeline not available — company info stored locally.",
        }

    result = await fn(session_id=session_id, text=text, filepath=filepath)
    if not isinstance(result, dict):
        result = {"company_name": str(result)}
    result.setdefault("ingested", True)
    result.setdefault("company_name", "Your Company")
    return result


async def run_pipeline(*, session_id: str, company: dict, icp: dict) -> Any:
    """Run the full LangGraph pipeline. Raises if the orchestrator is missing."""
    fn = _load("run_pipeline")
    if fn is None:
        raise RuntimeError(
            "Agent pipeline is not available in this build "
            "(backend/agents/orchestrator.py not found)."
        )
    return await fn(session_id=session_id, company=company, icp=icp)


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
