from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.auth import router as auth_router
from app.api.properties import router as properties_router
from app.api.diagnostic import router as diagnostic_router
from app.api.config import router as config_router
from app.api.comps import router as comps_router
from app.api.experiments import router as experiments_router
from app.api.snapshots import router as snapshots_router
from app.api.audit import router as audit_router

app = FastAPI(
    title="Multifamily Revenue Management Platform",
    description="AI-powered pricing diagnostics and action plans for multifamily properties",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
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


@app.get("/health")
def health_check():
    return {"status": "ok"}
