"""Single import point for everything the comms package shares.

Every module in comms/ imports settings, get_logger, and crud from here
rather than reaching into config/utils/db directly. That indirection is what
let this package be built before the rest of the backend existed.

It now resolves straight to the real backend: `db.crud` is Firestore-backed
and implements the exact signatures comms was written against, so no module
in this package needed changing when the backend landed. The two temporary
stand-ins that used to sit behind this file (`_shim.py`, `_firestore_crud.py`)
have been deleted.
"""

from config.settings import settings
from db import crud
from utils.logger import get_logger

# Kept because comms modules and test_comms.py read them for their banners.
USING_REAL_BACKEND = True
USING_FIRESTORE = True

__all__ = ["settings", "get_logger", "crud", "USING_REAL_BACKEND", "USING_FIRESTORE"]
