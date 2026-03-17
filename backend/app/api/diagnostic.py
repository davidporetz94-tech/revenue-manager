"""Diagnostic API endpoints.

POST /properties/{id}/diagnostic/run — trigger a diagnostic run
GET /diagnostic/{run_id} — get diagnostic run status/results
GET /properties/{id}/diagnostic/history — list past runs
"""
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.diagnostic import DiagnosticRun
from app.models.property import Property
from app.models.user import User, Organization
from app.schemas.diagnostic import DiagnosticRunResponse, DiagnosticRunSummary
from app.services.diagnostic_service import run_diagnostic
from app.services.slide_deck_service import assemble_slide_deck

router = APIRouter(prefix="/api/v1", tags=["diagnostic"])


def _get_demo_user(db: Session) -> User:
    """Temporary: get demo user until auth is wired up in Spec 06."""
    user = db.query(User).filter_by(email="demo@example.com").first()
    if not user:
        raise HTTPException(status_code=500, detail="Demo user not found")
    return user


@router.post(
    "/properties/{property_id}/diagnostic/run",
    response_model=DiagnosticRunResponse,
)
def create_diagnostic_run(property_id: str, db: Session = Depends(get_db)):
    """Trigger a full diagnostic run for a property."""
    user = _get_demo_user(db)

    prop = db.query(Property).filter_by(id=property_id).first()
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")

    try:
        result = run_diagnostic(
            db=db,
            property_id=property_id,
            user_id=str(user.id),
            organization_id=str(user.organization_id),
        )
        db.commit()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Diagnostic failed: {e}")

    return DiagnosticRunResponse(
        id=str(result.id),
        property_id=str(result.property_id),
        status=result.status,
        run_date=result.run_date,
        metrics_json=result.metrics_json,
        flags_json=result.flags_json,
        diagnosis_json=result.diagnosis_json,
        action_plan_json=result.action_plan_json,
        error_message=result.error_message,
        metrics_compute_ms=result.metrics_compute_ms,
        diagnosis_api_ms=result.diagnosis_api_ms,
        action_plan_api_ms=result.action_plan_api_ms,
        total_ms=result.total_ms,
    )


@router.get("/diagnostic/{run_id}", response_model=DiagnosticRunResponse)
def get_diagnostic_run(run_id: str, db: Session = Depends(get_db)):
    """Get a diagnostic run by ID."""
    run = db.query(DiagnosticRun).filter_by(id=run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Diagnostic run not found")

    return DiagnosticRunResponse(
        id=str(run.id),
        property_id=str(run.property_id),
        status=run.status,
        run_date=run.run_date,
        metrics_json=run.metrics_json,
        flags_json=run.flags_json,
        diagnosis_json=run.diagnosis_json,
        action_plan_json=run.action_plan_json,
        error_message=run.error_message,
        metrics_compute_ms=run.metrics_compute_ms,
        diagnosis_api_ms=run.diagnosis_api_ms,
        action_plan_api_ms=run.action_plan_api_ms,
        total_ms=run.total_ms,
    )


@router.get("/diagnostic/{run_id}/slides")
def get_diagnostic_slides(run_id: str, db: Session = Depends(get_db)):
    """Get the slide deck for a completed diagnostic run."""
    run = db.query(DiagnosticRun).filter_by(id=run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Diagnostic run not found")
    if run.status != "COMPLETED":
        raise HTTPException(status_code=422, detail=f"Run status is {run.status}, not COMPLETED")

    prop = db.query(Property).filter_by(id=run.property_id).first()

    # Check if slide deck is cached
    if run.slide_deck_json:
        return run.slide_deck_json

    # Generate slide deck
    deck = assemble_slide_deck(
        run_id=str(run.id),
        property_name=prop.name if prop else "Unknown",
        metrics=run.metrics_json or {},
        diagnosis=run.diagnosis_json or {},
        action_plan=run.action_plan_json or {},
        config_id=str(run.config_id) if run.config_id else None,
    )

    # Cache for future requests
    run.slide_deck_json = deck
    db.commit()

    return deck


@router.get(
    "/properties/{property_id}/diagnostic/history",
    response_model=list[DiagnosticRunSummary],
)
def get_diagnostic_history(property_id: str, db: Session = Depends(get_db)):
    """List past diagnostic runs for a property."""
    runs = (
        db.query(DiagnosticRun)
        .filter_by(property_id=property_id)
        .order_by(DiagnosticRun.run_date.desc())
        .limit(20)
        .all()
    )
    return [
        DiagnosticRunSummary(
            id=str(r.id),
            status=r.status,
            run_date=r.run_date,
            total_ms=r.total_ms,
        )
        for r in runs
    ]
