"""Maintenance endpoints.

POST /admin/cleanup-orphans — delete child documents whose parent no longer
exists: emails/meetings/followups/pipeline_events pointing at a missing
lead, and replies pointing at a missing email. Safe by construction: it can
only remove dangling references, never a document whose parent is alive,
and repeat calls are no-ops.

POST /admin/wipe — wipe every collection. **Destructive**, and the only way
to clear the database when the Firebase key lives on a host with no shell.
Nothing is reloaded afterwards: this project has no seed/demo dataset, so
every lead in the database got there by a real pipeline run.
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


class WipeResponse(BaseModel):
    wiped: bool = True
    remaining: dict[str, int]


@router.post("/wipe", response_model=WipeResponse)
async def wipe() -> WipeResponse:
    """Wipe every collection. Nothing is reloaded afterward.

    Destructive: removes the output of every past pipeline run. There is no
    seed dataset to restore afterwards — repopulate by running the pipeline.
    """
    await asyncio.to_thread(crud.clear_all)
    client = fs.get_client()
    remaining = {
        collection: sum(1 for _ in client.collection(collection).stream())
        for collection in fs.ALL_COLLECTIONS
    }
    log.warning("wiped all collections, nothing reloaded")
    return WipeResponse(remaining=remaining)
