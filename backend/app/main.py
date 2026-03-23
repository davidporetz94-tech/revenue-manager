import logging
import subprocess
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.api.auth import router as auth_router
from app.api.properties import router as properties_router
from app.api.diagnostic import router as diagnostic_router
from app.api.config import router as config_router
from app.api.comps import router as comps_router
from app.api.experiments import router as experiments_router
from app.api.snapshots import router as snapshots_router
from app.api.audit import router as audit_router
from app.api.chat import router as chat_router
from app.api.decisions import router as decisions_router
from app.api.renewals import router as renewals_router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Run Alembic migrations (non-fatal — allows local dev without alembic)
    try:
        logger.info("Running Alembic migrations...")
        result = subprocess.run(
            ["alembic", "upgrade", "head"],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            logger.info("Migrations complete.")
        else:
            logger.warning("Migration failed (non-fatal): %s", result.stderr)
    except FileNotFoundError:
        logger.warning("Alembic not found — skipping migrations.")

    # Seed demo data if not present (non-fatal — tables may not exist in local dev)
    try:
        from app.database import SessionLocal
        from app.models.user import User

        db = SessionLocal()
        try:
            demo_user = db.query(User).filter_by(email="demo@example.com").first()
            if demo_user is None:
                logger.info("No demo user found — seeding database...")
                from app.seed.seed_all import run_all_seeds
                run_all_seeds()
                logger.info("Seed complete.")
            else:
                logger.info("Demo user exists — skipping seed.")
        finally:
            db.close()
    except Exception as e:
        logger.warning("Seed check failed (non-fatal): %s", e)

    yield


app = FastAPI(
    title="Multifamily Revenue Management Platform",
    description="AI-powered pricing diagnostics and action plans for multifamily properties",
    version="0.1.0",
    lifespan=lifespan,
)

origins = [o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(properties_router)
app.include_router(diagnostic_router)
app.include_router(config_router)
app.include_router(comps_router)
app.include_router(experiments_router)
app.include_router(snapshots_router)
app.include_router(audit_router)
app.include_router(chat_router)
app.include_router(decisions_router)
app.include_router(renewals_router)


@app.get("/health")
def health_check():
    return {"status": "ok"}
