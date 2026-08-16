"""FastAPI entry point. Run with:

    cd backend && uvicorn main:app --reload --port 8000

All three teammates' routers are registered here. Registration is still
defensive — a router that fails to import logs a warning and the app starts
without it, so one broken module cannot take the whole demo down.
"""

from contextlib import asynccontextmanager
from importlib import import_module

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from api.schemas import HealthResponse
from config.settings import settings
from db import firestore as fs
from utils.logger import get_logger

log = get_logger("main")

ROUTERS = [
    # (module, attribute, label, prefix)
    ("api.routes.company", "router", "company", None),
    ("api.routes.icp", "router", "icp", None),
    ("api.routes.pipeline", "router", "pipeline", None),
    ("api.routes.leads", "router", "leads", None),
    # Sufiyan's routers define their paths without a prefix, so they are
    # mounted under one here.
    ("api.routes.emails", "router", "emails", "/emails"),
    ("api.routes.meetings", "router", "meetings", "/meetings"),
    ("api.routes.webhook", "router", "webhook", "/webhook"),
    ("api.routes.intelligence", "router", "intelligence", None),
    # Registered last: only fills gaps the routers above do not cover.
    ("api.routes.dashboard", "router", "dashboard", None),
    ("api.routes.admin", "router", "admin", None),
]


def _register(app: FastAPI, module_path: str, attr: str, label: str, prefix: str | None) -> None:
    try:
        module = import_module(module_path)
        router = getattr(module, attr)
        app.include_router(router, prefix=prefix) if prefix else app.include_router(router)
        log.info("registered router: %s", label)
    except Exception as exc:  # noqa: BLE001 - never let one router stop startup
        log.warning("skipping router %s (%s)", label, exc)


def _start_followup_scheduler() -> None:
    """Start Sufiyan's APScheduler jobs."""
    try:
        from comms.followup_scheduler import start_scheduler
    except Exception as exc:  # noqa: BLE001
        log.warning("follow-up scheduler not available (%s)", exc)
        return

    try:
        start_scheduler()
        log.info("follow-up scheduler started")
    except Exception:  # noqa: BLE001
        log.exception("follow-up scheduler failed to start")


def _stop_followup_scheduler() -> None:
    try:
        from comms.followup_scheduler import stop_scheduler
    except Exception:  # noqa: BLE001
        return
    try:
        stop_scheduler()
    except Exception:  # noqa: BLE001
        log.exception("follow-up scheduler failed to stop cleanly")


# What each capability needs, and what silently degrades without it.
#
# A capability is satisfied when any one GROUP is fully set — SMTP needs its
# three keys together, but Resend on its own is an equally valid sender.
CAPABILITIES = [
    (
        "lead discovery",
        (("SERPER_API_KEY",), ("TAVILY_API_KEY",)),
        "discovery finds nothing and every run completes with 0 leads",
    ),
    (
        "LLM (Gemini)",
        (("GEMINI_API_KEY",), ("GOOGLE_API_KEY",)),
        "the agents fall back to mock output",
    ),
    (
        "contact enrichment",
        (("APOLLO_API_KEY",), ("HUNTER_API_KEY",)),
        "qualified leads have no real address to send outreach to",
    ),
    (
        "outreach email",
        (("SMTP_HOST", "SMTP_USER", "SMTP_PASSWORD"), ("RESEND_API_KEY",)),
        "EmailSender runs in MOCK MODE and nothing is actually delivered",
    ),
]


def _describe(groups: tuple[tuple[str, ...], ...]) -> str:
    return " or ".join(" + ".join(group) for group in groups)


def _log_capability_warnings() -> None:
    """Name every capability whose keys are missing, once, at boot.

    Serper, Tavily, Apollo and Hunter each log a warning and return an empty
    result when their key is unset — none of them raise. A misconfigured
    deploy therefore looks exactly like a working one from the outside: the
    pipeline reports `complete` with `error: null` and simply has no leads in
    it. Checking here turns that into something you can read at startup
    instead of having to infer it from an empty dashboard.
    """
    degraded = 0

    for capability, groups, consequence in CAPABILITIES:
        satisfied = any(
            all(getattr(settings, key, "") for key in group) for group in groups
        )
        if not satisfied:
            degraded += 1
            log.warning(
                "%s is DISABLED — set %s, or %s",
                capability,
                _describe(groups),
                consequence,
            )

    if degraded:
        log.warning(
            "%d of %d capabilities degraded — the API will start, but the "
            "pipeline will not produce usable results until they are set",
            degraded,
            len(CAPABILITIES),
        )
    else:
        log.info("all %d capability key groups present", len(CAPABILITIES))


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown."""
    log.info("starting AgentHack backend")

    # Connect eagerly so a credentials problem shows up in the log at boot
    # rather than as a surprise on the first request.
    if fs.is_available():
        log.info("firestore connected")
    else:
        log.error(
            "firestore is NOT connected — set FIREBASE_SERVICE_ACCOUNT_PATH in "
            ".env. The API will start but every data route will return 503."
        )

    _log_capability_warnings()

    settings.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    _start_followup_scheduler()

    yield

    log.info("shutting down")
    _stop_followup_scheduler()


app = FastAPI(
    title="AgentHack — Autonomous AI Sales Agent",
    description=(
        "Ingests a company profile, finds and researches matching leads, scores "
        "them, writes and sends outreach, classifies replies, and books meetings."
    ),
    version="1.2.0",
    lifespan=lifespan,
)

# Wide open on purpose — hackathon build, frontend origin varies by machine.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

for module_path, attr, label, prefix in ROUTERS:
    _register(app, module_path, attr, label, prefix)

# Generated drive-time audio briefings, served read-only so the dashboard can
# play a clip straight from an <audio> tag. Created here rather than in
# lifespan because StaticFiles checks the directory exists at mount time,
# which is import time.
settings.AUDIO_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/audio", StaticFiles(directory=settings.AUDIO_DIR), name="audio")


@app.head("/health", tags=["meta"])
@app.get("/health", response_model=HealthResponse, tags=["meta"])
async def health() -> HealthResponse:
    """Liveness check. Reports Firestore reachability without failing on it."""
    import asyncio

    db_status = await asyncio.to_thread(fs.health)
    return HealthResponse(status="ok", database=db_status, version=app.version)


@app.head("/", tags=["meta"])
@app.get("/", tags=["meta"])
async def root() -> dict[str, str]:
    return {
        "name": "AgentHack — Autonomous AI Sales Agent",
        "docs": "/docs",
        "health": "/health",
    }
