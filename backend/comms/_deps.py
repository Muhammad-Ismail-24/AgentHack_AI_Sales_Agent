"""Single import point for everything the comms package shares.

Every module in comms/ imports settings, get_logger, and crud from here
rather than reaching into config/utils/db directly. That indirection is what
let this package be built before the rest of the backend existed.

The real backend now exists, so tier 1 below is the live path: `db.crud`
talks to Firestore. The in-memory shim is kept only as a fallback for running
the comms tests with no credentials configured.
"""

try:
    from config.settings import settings  # type: ignore
    from db import crud  # type: ignore
    from utils.logger import get_logger  # type: ignore

    USING_REAL_BACKEND = True
    USING_FIRESTORE = True  # db.crud is Firestore-backed

except ImportError:  # pragma: no cover - only when run outside the backend
    from comms._shim import crud as _shim_crud
    from comms._shim import get_logger, settings

    USING_REAL_BACKEND = False
    USING_FIRESTORE = False
    crud = _shim_crud

    get_logger("comms.deps").warning(
        "real backend not importable — comms is running on the in-memory shim"
    )

__all__ = ["settings", "get_logger", "crud", "USING_REAL_BACKEND", "USING_FIRESTORE"]
