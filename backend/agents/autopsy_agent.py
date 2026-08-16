"""Deal Autopsy — every dead lead gets a cause of death.

Reads the whole communication history of a lost lead and returns a three-part
post-mortem: what killed it, what we got wrong, and what changes next time.
The `misfire_tag` is machine-read: `/intelligence/autopsies/insights` counts
tags across every autopsy and turns them into concrete ICP and scoring
adjustments, which is what closes the learning loop.

The engagement statistics are computed here in Python, not asked of the model.
Response latency and thread length are facts the records already hold, and a
measured "71h average reply latency against their 4h" is the kind of finding
the model would otherwise invent.

Runs on demand from `POST /intelligence/leads/{id}/autopsy`, never inside the
pipeline.
"""

import json
from datetime import datetime, timezone

from agents.llm_utils import call_llm_json
from config.prompts import DEAL_AUTOPSY_PROMPT
from config.settings import settings
from db.models import MISFIRE_TAGS
from utils.logger import get_logger

log = get_logger(__name__)


def _as_dt(value: object) -> datetime | None:
    """Same tolerance as crud._as_dt — seed data carries ISO strings."""
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    return None


def _hours_between(earlier: object, later: object) -> float | None:
    start, end = _as_dt(earlier), _as_dt(later)
    if start is None or end is None or end < start:
        return None
    return round((end - start).total_seconds() / 3600, 1)


def engagement_stats(
    emails: list[dict], replies: list[dict], events: list[dict]
) -> dict:
    """Measured facts about how the conversation actually went.

    `our_avg_response_hours` is how long we took to answer them;
    `their_avg_response_hours` is how long they took to answer us. The gap
    between the two is usually the most damning number in the whole autopsy.
    """
    sent = [e for e in emails if e.get("status") in ("sent", "replied")]
    by_id = {e["id"]: e for e in emails if e.get("id")}

    their_latencies: list[float] = []
    our_latencies: list[float] = []

    ordered_replies = sorted(
        replies, key=lambda r: _as_dt(r.get("received_at")) or datetime.min.replace(tzinfo=timezone.utc)
    )

    for reply in ordered_replies:
        parent = by_id.get(reply.get("email_id"))
        if parent is None:
            continue

        # Them answering us.
        gap = _hours_between(parent.get("sent_at"), reply.get("received_at"))
        if gap is not None:
            their_latencies.append(gap)

        # Us answering them: the next email we sent after this reply landed.
        received = _as_dt(reply.get("received_at"))
        if received is None:
            continue
        later_sends = [
            dt
            for dt in (_as_dt(e.get("sent_at")) for e in sent)
            if dt is not None and dt > received
        ]
        if later_sends:
            our_latencies.append(
                round((min(later_sends) - received).total_seconds() / 3600, 1)
            )

    def _mean(values: list[float]) -> float | None:
        return round(sum(values) / len(values), 1) if values else None

    last_touch = max(
        [dt for dt in (_as_dt(e.get("sent_at")) for e in sent) if dt is not None]
        + [dt for dt in (_as_dt(r.get("received_at")) for r in replies) if dt is not None],
        default=None,
    )

    return {
        "emails_sent": len(sent),
        "replies_received": len(replies),
        "their_avg_response_hours": _mean(their_latencies),
        "our_avg_response_hours": _mean(our_latencies),
        "stage_changes": len(events),
        "days_since_last_touch": (
            round((datetime.now(timezone.utc) - last_touch).total_seconds() / 86400, 1)
            if last_touch
            else None
        ),
        "died_at_stage": events[-1].get("to_stage") if events else None,
    }


def _format_emails(emails: list[dict]) -> str:
    if not emails:
        return "(we never sent anything)"
    return "\n".join(
        f"- [{e.get('status')}] {e.get('subject') or '(no subject)'}: "
        f"{(e.get('body') or '')[:300]}"
        for e in emails
    )


def _format_replies(replies: list[dict]) -> str:
    if not replies:
        return "(they never replied)"
    return "\n".join(
        f"- [{r.get('classification') or 'unclassified'}] "
        f"{r.get('summary') or (r.get('raw_body') or '')[:300]}"
        for r in replies
    )


def _format_events(events: list[dict]) -> str:
    if not events:
        return "(no stage changes recorded)"
    return "\n".join(
        f"- {e.get('from_stage') or 'start'} -> {e.get('to_stage')}: "
        f"{e.get('reason') or 'no reason recorded'}"
        for e in events
    )


def _mock_autopsy(lead: dict, stats: dict) -> dict:
    """Keyless fallback. Reads off the measured statistics only — it makes no
    claim the records do not already support, and says it is a mock."""
    if stats["replies_received"] == 0 and stats["emails_sent"] > 0:
        cause = "Died at Contacted — no reply was ever received."
        tag = "no_engagement"
    elif stats["emails_sent"] == 0:
        cause = "Died before outreach — no email was ever sent."
        tag = "no_engagement"
    else:
        cause = f"Died at {stats['died_at_stage'] or lead.get('pipeline_stage')} after the conversation stalled."
        tag = "wrong_timing"

    return {
        "cause_of_death": f"(mock) {cause}",
        "cause_evidence": (
            f"{stats['emails_sent']} email(s) sent, "
            f"{stats['replies_received']} repl(y/ies) received"
        ),
        "misfire": "(mock) No Gemini API key configured, so no diagnosis was made.",
        "misfire_tag": tag,
        "correction": "(mock) Set GEMINI_API_KEY to get a real post-mortem.",
        "icp_adjustment": "(mock) none",
        "confidence": 0,
    }


async def run(
    lead: dict,
    contacts: list[dict],
    emails: list[dict],
    replies: list[dict],
    events: list[dict],
) -> dict:
    """Produce the post-mortem for one dead lead.

    Takes the history the caller already assembled (long_term_memory's
    recall_lead_history returns exactly these five pieces). Returns the dict
    shape `crud.create_autopsy` expects, and never raises.
    """
    stats = engagement_stats(emails, replies, events)
    company_name = lead.get("company_name") or "this company"
    primary = next(
        (c for c in contacts if c.get("is_primary")), contacts[0] if contacts else {}
    )

    if not settings.google_api_key:
        log.warning("autopsy: no Gemini key — returning the mock post-mortem")
        findings = _mock_autopsy(lead, stats)
    else:
        try:
            result = await call_llm_json(
                DEAL_AUTOPSY_PROMPT.format(
                    company_name=company_name,
                    industry=lead.get("industry") or "unknown",
                    pipeline_stage=lead.get("pipeline_stage") or "unknown",
                    lead_score=lead.get("lead_score"),
                    score_explanation=lead.get("score_explanation") or "none recorded",
                    recommended_service=lead.get("recommended_service") or "none",
                    pitch_angle=lead.get("pitch_angle") or "none",
                    contact_name=primary.get("name") or "nobody",
                    contact_role=primary.get("role") or "unknown role",
                    research_summary=lead.get("research_summary") or "none on file",
                    email_history=_format_emails(emails),
                    reply_history=_format_replies(replies),
                    event_history=_format_events(events),
                    engagement_stats=json.dumps(stats),
                )
            )
            if not isinstance(result, dict) or not result.get("cause_of_death"):
                log.warning(
                    "autopsy: unusable LLM response for '%s' — falling back to the mock",
                    company_name,
                )
                findings = _mock_autopsy(lead, stats)
            else:
                findings = result
        except Exception as exc:  # noqa: BLE001 — an on-demand extra must never 500
            log.error("autopsy failed for '%s': %s", company_name, exc)
            findings = _mock_autopsy(lead, stats)

    tag = str(findings.get("misfire_tag") or "").strip().lower().replace(" ", "_")
    if tag not in MISFIRE_TAGS:
        if tag:
            log.warning(
                "autopsy: model returned unrecognised misfire_tag %r — recording "
                "as 'no_engagement' so the insights rollup stays countable",
                findings.get("misfire_tag"),
            )
        tag = "no_engagement"

    return {
        **findings,
        "misfire_tag": tag,
        "engagement_stats": stats,
        "final_stage": lead.get("pipeline_stage"),
    }


# ── Insights rollup ──────────────────────────────────────────────────
# The closed loop: what every autopsy so far, taken together, says the ICP
# and the scoring weights should change to.

_TAG_LESSONS = {
    "wrong_service": (
        "Service matching is the leading cause of death — raise the weight on "
        "RAG service-fit evidence and reject leads whose pain point is inferred "
        "rather than stated."
    ),
    "wrong_persona": (
        "We keep reaching the wrong person — prefer contacts whose title owns "
        "the problem the service solves over whoever ranks highest."
    ),
    "wrong_timing": (
        "Timing is killing deals — weight recent buying signals (funding, "
        "hiring, tooling changes) far more heavily during qualification."
    ),
    "slow_response": (
        "We are answering too slowly — shorten the follow-up window; the "
        "measured latency gap is costing live conversations."
    ),
    "weak_personalisation": (
        "Outreach is reading as generic — require at least one quoted, "
        "company-specific fact in every email before it can be sent."
    ),
    "no_engagement": (
        "Leads are never engaging at all — tighten the discovery filter and "
        "raise MIN_QUALIFICATION_SCORE; volume is being spent on non-prospects."
    ),
    "price": (
        "Price is the recurring blocker — qualify on budget signals earlier, "
        "and lead with the lower-commitment service."
    ),
}


def summarise(autopsies: list[dict]) -> dict:
    """Aggregate every post-mortem into ranked causes and concrete lessons.

    Pure function over documents already in Firestore — no LLM call, so the
    insights panel costs nothing to refresh.
    """
    counts: dict[str, int] = {}
    for autopsy in autopsies:
        tag = autopsy.get("misfire_tag")
        if tag:
            counts[tag] = counts.get(tag, 0) + 1

    ranked = sorted(counts.items(), key=lambda pair: pair[1], reverse=True)
    total = len(autopsies)

    return {
        "total_autopsies": total,
        "misfire_counts": dict(ranked),
        "top_misfire": ranked[0][0] if ranked else None,
        "lessons": [
            {
                "misfire_tag": tag,
                "count": count,
                "share": round(count / total * 100) if total else 0,
                "adjustment": _TAG_LESSONS.get(
                    tag, "No standing adjustment mapped to this misfire yet."
                ),
            }
            for tag, count in ranked
        ],
    }
