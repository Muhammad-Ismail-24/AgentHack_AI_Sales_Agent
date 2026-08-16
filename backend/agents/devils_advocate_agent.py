"""Devil's Advocate — two agents argue over a lead, a third resolves it.

A Prosecutor argues the company should be dropped, a Defender argues to
pursue, and a Judge weighs both. The judge's confidence IS the lead's
confidence score, and the full transcript is kept so the UI can show the
reasoning rather than assert it.

Not a node in the LangGraph pipeline — this runs on demand, one lead at a
time, from `POST /intelligence/leads/{id}/devils-advocate`. Keeping it out of
the graph means a normal run costs exactly what it did before.

Three LLM calls per debate, but prosecution and defence are independent, so
they go out together and only the judge waits. The RPM limiter in llm_utils
still serialises them against every other caller sharing the key.
"""

import asyncio
import json

from agents.llm_utils import call_llm_json
from config.prompts import (
    DEVILS_ADVOCATE_DEFENDER_PROMPT,
    DEVILS_ADVOCATE_JUDGE_PROMPT,
    DEVILS_ADVOCATE_PROSECUTOR_PROMPT,
)
from config.settings import settings
from utils.logger import get_logger

log = get_logger(__name__)

# The research fields a debate can actually argue from. How many are present
# decides the honest ceiling on evidence_strength — see _evidence_floor.
_RESEARCH_FIELDS = (
    "research_summary",
    "industry",
    "location",
    "employee_count",
    "recommended_service",
    "pitch_angle",
    "score_explanation",
)


def _research_payload(lead: dict) -> dict:
    """The subset of a lead document the debaters are allowed to see."""
    return {
        "company_name": lead.get("company_name"),
        "website": lead.get("website"),
        "industry": lead.get("industry"),
        "location": lead.get("location"),
        "employee_count": lead.get("employee_count"),
        "research_summary": lead.get("research_summary"),
        "apollo_data": lead.get("apollo_data"),
        "pipeline_stage": lead.get("pipeline_stage"),
        "lead_score": lead.get("lead_score"),
        "score_explanation": lead.get("score_explanation"),
        "recommended_service": lead.get("recommended_service"),
        "pitch_angle": lead.get("pitch_angle"),
        "contacts": [
            {"name": c.get("name"), "role": c.get("role")}
            for c in lead.get("contacts") or []
        ],
    }


def _evidence_floor(lead: dict) -> str:
    """The most the judge may honestly claim, given how much research exists.

    The model is asked to grade its own evidence and will happily say "high"
    off three empty fields. Capping it here is what stops a debate held over
    nothing from rendering as a confident verdict — rule 2 of the build spec:
    thin evidence must read as thin, not as certainty.
    """
    present = sum(1 for field in _RESEARCH_FIELDS if lead.get(field))
    if present >= 5:
        return "high"
    if present >= 3:
        return "medium"
    return "low"


def _company_knowledge(session_id: str) -> str:
    """What we sell, from the session's RAG collection.

    Imported lazily: the retriever pulls in the whole langchain/Qdrant stack,
    and a debate is still worth holding on ICP fit alone if the vector store
    is unreachable. The pipeline agents import it eagerly because they cannot
    run without it — this one can.
    """
    if not session_id:
        return ""
    try:
        from rag.retriever import query as rag_query
    except Exception as exc:  # noqa: BLE001
        log.warning("devils_advocate: RAG unavailable (%s) — debating without it", exc)
        return ""
    return rag_query(
        "what services and solutions does our company offer", f"company_{session_id}"
    )


def _cap_strength(claimed: object, floor: str) -> str:
    order = {"low": 0, "medium": 1, "high": 2}
    claimed_str = str(claimed or "").strip().lower()
    if claimed_str not in order:
        return floor
    return claimed_str if order[claimed_str] <= order[floor] else floor


def _arguments(result: object) -> list[dict]:
    """Normalise one side's arguments into [{claim, evidence}, ...]."""
    if not isinstance(result, dict):
        return []

    cleaned: list[dict] = []
    for entry in result.get("arguments") or []:
        if isinstance(entry, dict) and entry.get("claim"):
            cleaned.append(
                {
                    "claim": str(entry["claim"]),
                    "evidence": str(entry.get("evidence") or "no evidence available"),
                }
            )
        elif isinstance(entry, str) and entry.strip():
            # The model occasionally returns bare strings despite the schema.
            cleaned.append({"claim": entry, "evidence": "no evidence available"})
    return cleaned


def _closing(result: object) -> str:
    return str(result.get("closing") or "") if isinstance(result, dict) else ""


def _mock_debate(lead: dict, floor: str) -> dict:
    """Used when no Gemini key is configured, so the demo still renders.

    Deliberately labelled in the text — a judge watching the screen should
    never mistake a keyless fallback for a real debate.
    """
    name = lead.get("company_name") or "this company"
    score = lead.get("lead_score")
    return {
        "prosecution": [
            {
                "claim": f"(mock) The research on {name} is too thin to justify the time.",
                "evidence": lead.get("research_summary") or "no evidence available",
            }
        ],
        "defense": [
            {
                "claim": f"(mock) {name} matches the ICP on industry and location.",
                "evidence": f"{lead.get('industry') or 'unknown industry'}, "
                            f"{lead.get('location') or 'unknown location'}",
            }
        ],
        "prosecution_closing": "(mock) No configured LLM — prosecution not argued.",
        "defense_closing": "(mock) No configured LLM — defence not argued.",
        "winner": "defence" if (score or 0) >= settings.MIN_QUALIFICATION_SCORE else "prosecution",
        "confidence": score if score is not None else 50,
        "reasoning": "(mock) No Gemini API key configured, so this verdict "
                     "mirrors the qualification score rather than a real debate.",
        "decisive_argument": "(mock) none — no debate was held.",
        "evidence_strength": floor,
    }


async def run(lead: dict) -> dict:
    """Hold the debate over one lead document and return the resolved verdict.

    `lead` is a Firestore lead dict, optionally with a "contacts" list
    attached. Returns the dict shape `crud.create_verdict` expects. Never
    raises — a failed debate falls back to the mock so the caller always has
    something to persist and show.
    """
    floor = _evidence_floor(lead)
    company_name = lead.get("company_name") or "this company"

    if not settings.google_api_key:
        log.warning("devils_advocate: no Gemini key — returning the mock debate")
        return _mock_debate(lead, floor)

    try:
        research = json.dumps(_research_payload(lead))
        icp = json.dumps(
            {
                "industry": lead.get("industry"),
                "location": lead.get("location"),
                "employee_count": lead.get("employee_count"),
            }
        )
        # Per-session collection, written by rag_agent as company_{session_id}.
        company_knowledge = _company_knowledge(lead.get("session_id") or "") or (
            "(no company knowledge indexed for this session)"
        )

        prosecutor, defender = await asyncio.gather(
            call_llm_json(
                DEVILS_ADVOCATE_PROSECUTOR_PROMPT.format(
                    company_research=research,
                    icp=icp,
                    company_knowledge=company_knowledge,
                )
            ),
            call_llm_json(
                DEVILS_ADVOCATE_DEFENDER_PROMPT.format(
                    company_research=research,
                    icp=icp,
                    company_knowledge=company_knowledge,
                )
            ),
        )

        prosecution = _arguments(prosecutor)
        defense = _arguments(defender)

        if not prosecution and not defense:
            log.warning(
                "devils_advocate: neither side produced an argument for '%s' — "
                "falling back to the mock verdict",
                company_name,
            )
            return _mock_debate(lead, floor)

        judgement = await call_llm_json(
            DEVILS_ADVOCATE_JUDGE_PROMPT.format(
                company_name=company_name,
                prosecution=json.dumps(prosecution),
                prosecution_closing=_closing(prosecutor),
                defense=json.dumps(defense),
                defense_closing=_closing(defender),
            )
        )
        if not isinstance(judgement, dict):
            judgement = {}

        winner = str(judgement.get("winner") or "").strip().lower()
        if winner not in ("prosecution", "defence"):
            # "defense" is the spelling the model reaches for about half the
            # time; anything else means it ignored the schema.
            winner = "defence" if winner == "defense" else "prosecution"

        return {
            "prosecution": prosecution,
            "defense": defense,
            "prosecution_closing": _closing(prosecutor),
            "defense_closing": _closing(defender),
            "winner": winner,
            "confidence": judgement.get("confidence"),
            "reasoning": judgement.get("reasoning"),
            "decisive_argument": judgement.get("decisive_argument"),
            "evidence_strength": _cap_strength(
                judgement.get("evidence_strength"), floor
            ),
        }

    except Exception as exc:  # noqa: BLE001 — an on-demand extra must never 500
        log.error("devils_advocate failed for '%s': %s", company_name, exc)
        return _mock_debate(lead, floor)
