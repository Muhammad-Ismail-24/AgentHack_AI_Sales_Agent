"""Firestore client. The single place the app connects to the database.

Credentials are resolved in this order:

1. `FIRESTORE_EMULATOR_HOST` — talk to a local emulator, no credentials.
2. `FIREBASE_SERVICE_ACCOUNT_PATH` — a service-account JSON on disk.
3. Application Default Credentials — `gcloud auth application-default login`,
   or the service account attached to a Cloud Run / GCE instance.

`get_client()` raises a clear, actionable error when none of those work,
rather than a stack trace out of the SDK. Call `is_available()` first if you
want to degrade instead of fail.
"""

from typing import Any

from config.settings import settings
from utils.logger import get_logger

log = get_logger(__name__)

# Collection names — the only place these strings are written.
LEADS = "leads"
CONTACTS = "contacts"
EMAILS = "emails"
REPLIES = "replies"
MEETINGS = "meetings"
FOLLOWUPS = "followups"
PIPELINE_EVENTS = "pipeline_events"

ALL_COLLECTIONS = [
    LEADS,
    CONTACTS,
    EMAILS,
    REPLIES,
    MEETINGS,
    FOLLOWUPS,
    PIPELINE_EVENTS,
]

_client: Any = None
_init_error: str | None = None


class FirestoreUnavailable(RuntimeError):
    """Raised when Firestore cannot be reached or credentialed."""


def set_client(client: Any) -> None:
    """Inject a client. Used by the test suite to run against a fake.

    Passing None clears the cached client so the next get_client() rebuilds.
    """
    global _client, _init_error
    _client = client
    _init_error = None


def is_available() -> bool:
    try:
        get_client()
        return True
    except Exception:  # noqa: BLE001
        return False


def get_client() -> Any:
    """Return a Firestore client, initialising it on first use."""
    global _client, _init_error

    if _client is not None:
        return _client
    if _init_error is not None:
        raise FirestoreUnavailable(_init_error)

    try:
        import firebase_admin
        from firebase_admin import credentials, firestore
    except ImportError as exc:  # pragma: no cover
        _init_error = (
            "firebase-admin is not installed — run "
            "pip install -r backend/requirements.txt"
        )
        raise FirestoreUnavailable(_init_error) from exc

    try:
        if not firebase_admin._apps:  # noqa: SLF001 - documented way to check
            options = {}
            if settings.FIREBASE_PROJECT_ID:
                options["projectId"] = settings.FIREBASE_PROJECT_ID

            if settings.FIRESTORE_EMULATOR_HOST:
                # The SDK reads FIRESTORE_EMULATOR_HOST from the process env.
                import os

                os.environ["FIRESTORE_EMULATOR_HOST"] = settings.FIRESTORE_EMULATOR_HOST
                options.setdefault("projectId", "demo-agenthack")
                firebase_admin.initialize_app(options=options)
                log.info(
                    "firestore: using emulator at %s",
                    settings.FIRESTORE_EMULATOR_HOST,
                )

            elif settings.FIREBASE_SERVICE_ACCOUNT_PATH:
                cred = credentials.Certificate(settings.FIREBASE_SERVICE_ACCOUNT_PATH)
                firebase_admin.initialize_app(cred, options or None)
                log.info(
                    "firestore: using service account %s",
                    settings.FIREBASE_SERVICE_ACCOUNT_PATH,
                )

            else:
                # Application Default Credentials.
                firebase_admin.initialize_app(options=options or None)
                log.info("firestore: using application default credentials")

        _client = firestore.client()
        return _client

    except Exception as exc:  # noqa: BLE001
        _init_error = (
            f"Could not connect to Firestore ({type(exc).__name__}: {exc}). "
            "Set FIREBASE_SERVICE_ACCOUNT_PATH in your .env to the path of a "
            "Firebase service-account JSON, or set FIRESTORE_EMULATOR_HOST to "
            "run against a local emulator."
        )
        log.error(_init_error)
        raise FirestoreUnavailable(_init_error) from exc


def collection(name: str) -> Any:
    return get_client().collection(name)


def health() -> str:
    """One cheap read, so /health can report the database honestly."""
    try:
        next(iter(get_client().collection(LEADS).limit(1).stream()), None)
        return "ok"
    except FirestoreUnavailable as exc:
        return f"unavailable: {exc}".split("(")[0].strip()
    except Exception as exc:  # noqa: BLE001
        return f"unreachable: {type(exc).__name__}"
