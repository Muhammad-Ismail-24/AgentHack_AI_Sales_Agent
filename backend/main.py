"""FastAPI entry point. Run with:

    cd backend && uvicorn main:app --reload --port 8000

Routers owned by Ismail (agents) and Sufiyan (comms) are registered
defensively: if their module is missing or mid-refactor on this branch, the
app logs it and starts anyway rather than refusing to boot. That way nobody's
branch can break everybody's demo.
"""

from contextlib import asynccontextmanager
from importlib import import_module

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from api.schemas import HealthResponse
from config.settings import settings
from db.database import SessionLocal, close_db, init_db
from utils.logger import get_logger

log = get_logger("main")

# Routers everyone relies on. (module path, attribute, description)
CORE_ROUTERS = [
    ("api.routes.company", "router", "company"),
    ("api.routes.icp", "router", "icp"),
    ("api.routes.pipeline", "router", "pipeline"),
    ("api.routes.leads", "router", "leads"),
]

# Teammates' routers — optional at import time.
OPTIONAL_ROUTERS = [
    ("api.routes.emails", "router", "emails (Sufiyan)"),
    ("api.routes.meetings", "router", "meetings (Sufiyan)"),
    ("api.routes.webhook", "router", "webhook (Sufiyan)"),
]

# Registered last so any real handler above wins the path match.
FALLBACK_ROUTERS = [
    ("api.routes.dashboard", "router", "dashboard fallbacks"),
]


def _register(app: FastAPI, module_path: str, attr: str, label: str, *, required: bool) -> bool:
    try:
        module = import_module(module_path)
        app.include_router(getattr(module, attr))
        log.info("registered router: %s", label)
        return True
    except Exception as exc:  # noqa: BLE001 - a missing teammate module is expected
        if required:
            log.error("could not register required router %s: %s", label, exc)
            raise
        log.warning("skipping router %s (%s)", label, exc)
        return False


def _start_followup_scheduler() -> None:
    """Start Sufiyan's APScheduler job, if that module has landed."""
    try:
        from comms.followup_scheduler import start_scheduler
    except Exception as exc:  # noqa: BLE001
        log.warning("follow-up scheduler not available (%s)", exc)
        return

    try:
        start_scheduler()
        log.info("follow-up scheduler started")
    except Exception:  # noqa: BLE001 - never let a scheduler fault block startup
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
    """Startup and shutdown. (on_event is deprecated — this replaces it.)"""
    log.info("starting AgentHack backend")
    try:
        await init_db()
    except Exception:  # noqa: BLE001 - surface the error but keep /health alive
        log.exception("database init failed — check DATABASE_URL")

    settings.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    _start_followup_scheduler()

    yield

    log.info("shutting down")
    _stop_followup_scheduler()
    await close_db()


app = FastAPI(
    title="AgentHack — Autonomous AI Sales Agent",
    description=(
        "Ingests a company profile, finds and researches matching leads, scores "
        "them, writes and sends outreach, classifies replies, and books meetings."
    ),
    version="0.1.0",
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

for module_path, attr, label in CORE_ROUTERS:
    _register(app, module_path, attr, label, required=True)

for module_path, attr, label in OPTIONAL_ROUTERS:
    _register(app, module_path, attr, label, required=False)

for module_path, attr, label in FALLBACK_ROUTERS:
    _register(app, module_path, attr, label, required=False)


@app.get("/health", response_model=HealthResponse, tags=["meta"])
async def health() -> HealthResponse:
    """Liveness check. Reports database reachability without failing on it."""
    db_status = "ok"
    try:
        async with SessionLocal() as session:
            await session.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001
        db_status = f"unreachable: {type(exc).__name__}"

    return HealthResponse(status="ok", database=db_status, version=app.version)


@app.get("/", tags=["meta"])
async def root() -> dict[str, str]:
    return {
        "name": "AgentHack — Autonomous AI Sales Agent",
        "docs": "/docs",
        "health": "/health",
    }
