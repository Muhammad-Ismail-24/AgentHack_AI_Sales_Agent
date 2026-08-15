"""
TEMPORARY — delete this file once Wajeeh's real backend/config/settings.py,
backend/utils/logger.py, and backend/db/crud.py land on main.

Single swap point for every comms/*.py module. Every module in this
package imports its shared dependencies from here, never directly from
config/utils/db — that way, when the real backend modules exist, they are
picked up automatically and nothing in comms/ needs to change.

Three tiers, tried in order:
  1. Real backend (Wajeeh's config/settings.py + utils/logger.py +
     db/crud.py) — once these exist, everything below is dead code.
  2. Comms-local Firestore adapter (comms/_firestore_crud.py) — only
     tried when FIREBASE_SERVICE_ACCOUNT_PATH is set. This is NOT the
     team's database (CLAUDE.md/FOLDER_STRUCTURE.md say Postgres via
     Supabase) — see conflicts.md for the full scope note.
  3. In-memory shim (comms/_shim.py) — the original fallback, used when
     neither of the above is available (e.g. no Firebase credentials
     configured, or firebase-admin isn't installed). This is what
     teammates without a Firebase key get, so tests keep working for
     everyone regardless of local setup.

See conflicts.md at the repo root for the merge checklist.
"""

try:
    from config.settings import settings  # type: ignore
    from utils.logger import get_logger  # type: ignore
    from db import crud  # type: ignore

    USING_REAL_BACKEND = True
    USING_FIRESTORE = False
except ImportError:
    from comms._shim import crud as _shim_crud
    from comms._shim import get_logger, settings

    USING_REAL_BACKEND = False
    USING_FIRESTORE = False
    crud = _shim_crud

    if settings.FIREBASE_SERVICE_ACCOUNT_PATH:
        try:
            from comms._firestore_crud import crud as _firestore_crud

            crud = _firestore_crud
            USING_FIRESTORE = True
        except Exception as _exc:  # noqa: BLE001 — a bad Firestore config must never break the comms layer
            get_logger("comms.deps").warning(
                "FIREBASE_SERVICE_ACCOUNT_PATH is set but Firestore init failed (%s) - "
                "falling back to the in-memory shim",
                _exc,
            )

__all__ = ["settings", "get_logger", "crud", "USING_REAL_BACKEND", "USING_FIRESTORE"]
