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
    # Registered last: only fills gaps the routers above do not cover.
    ("api.routes.dashboard", "router", "dashboard", None),
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
    version="1.0.0",
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


@app.get("/health", response_model=HealthResponse, tags=["meta"])
async def health() -> HealthResponse:
    """Liveness check. Reports Firestore reachability without failing on it."""
    import asyncio

    db_status = await asyncio.to_thread(fs.health)
    return HealthResponse(status="ok", database=db_status, version=app.version)


@app.get("/", tags=["meta"])
async def root() -> dict[str, str]:
    return {
        "name": "AgentHack — Autonomous AI Sales Agent",
        "docs": "/docs",
        "health": "/health",
    }
