"""Maintenance endpoints.

POST /admin/cleanup-orphans — delete child documents whose parent no longer
exists: emails/meetings/followups/pipeline_events pointing at a missing
lead, and replies pointing at a missing email. Safe by construction: it can
only remove dangling references, never a document whose parent is alive,
and repeat calls are no-ops.

POST /admin/reseed — wipe every collection and reload data/seeds/*.json.
**Destructive**, and the only way to reset the demo when the Firebase key
lives on a host with no shell. It reuses load_seeds.py rather than
reimplementing the loading rules, so there is one source of truth for what
the demo data is.

POST /admin/wipe — wipe every collection and reload nothing. **Destructive.**
For clearing seed/demo/test data out before a genuine pipeline run, when you
want an empty database rather than the reseeded demo state.
"""

import asyncio

from fastapi import APIRouter
from pydantic import BaseModel

from db import crud, firestore as fs
from utils.logger import get_logger

log = get_logger(__name__)
router = APIRouter(prefix="/admin", tags=["admin"])


class CleanupResponse(BaseModel):
    deleted: dict[str, int]
    remaining: dict[str, int]


def _cleanup_orphans() -> tuple[dict[str, int], dict[str, int]]:
    """Synchronous cleanup — runs in a worker thread."""
    client = fs.get_client()

    lead_ids = {snap.id for snap in client.collection(fs.LEADS).stream()}
    deleted = {c: 0 for c in (fs.EMAILS, fs.REPLIES, fs.MEETINGS, fs.FOLLOWUPS, fs.PIPELINE_EVENTS, fs.CONTACTS)}

    # Children keyed by lead_id.
    for collection in (fs.CONTACTS, fs.EMAILS, fs.MEETINGS, fs.FOLLOWUPS, fs.PIPELINE_EVENTS):
        for snap in client.collection(collection).stream():
            data = snap.to_dict() or {}
            if data.get("lead_id") not in lead_ids:
                snap.reference.delete()
                deleted[collection] += 1

    # Replies key off emails — resolve against what survived above.
    email_ids = {snap.id for snap in client.collection(fs.EMAILS).stream()}
    for snap in client.collection(fs.REPLIES).stream():
        data = snap.to_dict() or {}
        if data.get("email_id") not in email_ids:
            snap.reference.delete()
            deleted[fs.REPLIES] += 1

    remaining = {
        collection: sum(1 for _ in client.collection(collection).stream())
        for collection in fs.ALL_COLLECTIONS
    }
    return deleted, remaining


@router.post("/cleanup-orphans", response_model=CleanupResponse)
async def cleanup_orphans() -> CleanupResponse:
    """Remove dangling child documents. Safe to call any number of times."""
    deleted, remaining = await asyncio.to_thread(_cleanup_orphans)
    total = sum(deleted.values())
    log.warning("orphan cleanup removed %s documents: %s", total, deleted)
    return CleanupResponse(deleted=deleted, remaining=remaining)


class ReseedResponse(BaseModel):
    reseeded: bool = True
    loaded: dict[str, int]
    remaining: dict[str, int]
    session_id: str


def _reseed() -> tuple[dict[str, int], dict[str, int], str]:
    """Wipe and reload the demo seeds. Synchronous — runs in a thread."""
    import load_seeds

    leads = load_seeds._read("leads_seed.json")
    if not leads:
        raise FileNotFoundError("data/seeds/leads_seed.json is missing")

    crud.clear_all()

    lead_count, contact_count = load_seeds.load_leads(leads)
    emails = load_seeds._read("emails_seed.json")
    replies = load_seeds._read("replies_seed.json")
    meetings = load_seeds._read("meetings_seed.json")

    loaded = {
        "leads": lead_count,
        "contacts": contact_count,
        "emails": load_seeds.load_emails(emails) if emails else 0,
        "replies": load_seeds.load_replies(replies) if replies else 0,
        "meetings": load_seeds.load_meetings(meetings) if meetings else 0,
    }

    client = fs.get_client()
    remaining = {
        collection: sum(1 for _ in client.collection(collection).stream())
        for collection in fs.ALL_COLLECTIONS
    }
    return loaded, remaining, load_seeds.SESSION_ID


@router.post("/reseed", response_model=ReseedResponse)
async def reseed() -> ReseedResponse:
    """Wipe every collection and reload the demo seed data.

    Destructive: anything not in data/seeds/ is gone, including the output
    of real pipeline runs. That is the point — it restores a known-good
    demo state and clears whatever test runs left behind.
    """
    loaded, remaining, session_id = await asyncio.to_thread(_reseed)
    log.warning("reseeded demo data: %s", loaded)
    return ReseedResponse(loaded=loaded, remaining=remaining, session_id=session_id)


class WipeResponse(BaseModel):
    wiped: bool = True
    remaining: dict[str, int]


@router.post("/wipe", response_model=WipeResponse)
async def wipe() -> WipeResponse:
    """Wipe every collection. Nothing is reloaded afterward.

    Destructive: removes seed data, demo data, and the output of every past
    pipeline run alike. Use this instead of /reseed when you want a genuinely
    empty database for a real pipeline run, not the canned demo state.
    """
    await asyncio.to_thread(crud.clear_all)
    client = fs.get_client()
    remaining = {
        collection: sum(1 for _ in client.collection(collection).stream())
        for collection in fs.ALL_COLLECTIONS
    }
    log.warning("wiped all collections, nothing reloaded")
    return WipeResponse(remaining=remaining)
