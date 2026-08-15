"""Centralised logging. Import this instead of using print().

    from utils.logger import get_logger
    log = get_logger(__name__)
    log.info("discovered %s leads", len(leads))
"""

import logging
import sys

from config.settings import settings

_CONFIGURED = False

_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)-28s | %(message)s"
_DATEFMT = "%H:%M:%S"


def _configure_root() -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(_FORMAT, datefmt=_DATEFMT))

    root = logging.getLogger("agenthack")
    root.setLevel(settings.LOG_LEVEL.upper())
    root.addHandler(handler)
    root.propagate = False

    # Third-party noise we never want in the demo output.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("apscheduler").setLevel(logging.WARNING)

    _CONFIGURED = True


def get_logger(name: str = "agenthack") -> logging.Logger:
    """Return a namespaced logger under the shared 'agenthack' root."""
    _configure_root()
    if name == "agenthack" or name.startswith("agenthack."):
        return logging.getLogger(name)
    return logging.getLogger(f"agenthack.{name}")


# Convenience module-level logger for quick imports.
logger = get_logger()
