"""
TEMPORARY — delete this file once Wajeeh's real backend/config/settings.py,
backend/utils/logger.py, and backend/db/crud.py land on main.

Single swap point for every comms/*.py module. Every module in this
package imports its shared dependencies from here, never directly from
config/utils/db — that way, when the real backend modules exist, they are
picked up automatically and nothing in comms/ needs to change.

See conflicts.md at the repo root for the merge checklist.
"""

try:
    from config.settings import settings  # type: ignore
    from utils.logger import get_logger  # type: ignore
    from db import crud  # type: ignore

    USING_REAL_BACKEND = True
except ImportError:
    from comms._shim import settings, get_logger, crud

    USING_REAL_BACKEND = False

__all__ = ["settings", "get_logger", "crud", "USING_REAL_BACKEND"]
