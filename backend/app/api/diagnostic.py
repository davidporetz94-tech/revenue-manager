"""Diagnostic API endpoints.

POST /properties/{id}/diagnostic/run — trigger a property diagnostic run
POST /diagnostic/portfolio/run — trigger a portfolio-wide diagnostic run
GET /diagnostic/{run_id} — get diagnostic run status/results
GET /diagnostic/{run_id}/slides — get slide deck for a completed run
GET /properties/{id}/diagnostic/history — list past property runs
GET /diagnostic/portfolio/history — list past portfolio runs
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.diagnostic import DiagnosticRun
from app.models.property import Property
from app.models.user import User
from app.schemas.diagnostic import DiagnosticRunResponse, DiagnosticRunSummary
from app.services.diagnostic_service import run_diagnostic
from app.services.slide_deck_service import assemble_slide_deck
from app.auth.dependencies import get_current_user, verify_property_access

router = APIRouter(prefix="/api/v1", tags=["diagnostic"])


def _run_to_response(run: DiagnosticRun) -> DiagnosticRunResponse:
    """Convert a DiagnosticRun to a response dict."""
    return DiagnosticRunResponse(
        id=str(run.id),
        property_id=str(run.property_id) if run.property_id else None,
        scope=run.scope,
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


def _run_to_summary(run: DiagnosticRun) -> DiagnosticRunSummary:
    """Convert a DiagnosticRun to a summary dict."""
    return DiagnosticRunSummary(
        id=str(run.id),
        property_id=str(run.property_id) if run.property_id else None,
        scope=run.scope,
        status=run.status,
        run_date=run.run_date,
        total_ms=run.total_ms,
    )


@router.post(
    "/properties/{property_id}/diagnostic/run",
    response_model=DiagnosticRunResponse,
)
def create_diagnostic_run(
    property_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Trigger a full diagnostic run for a property."""
    verify_property_access(db, property_id, user)

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

    return _run_to_response(result)


@router.post("/diagnostic/portfolio/run", response_model=DiagnosticRunResponse)
def create_portfolio_diagnostic(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Trigger a portfolio-wide diagnostic for all properties."""
    from app.services.portfolio_diagnostic_service import run_portfolio_diagnostic

    try:
        result = run_portfolio_diagnostic(
            db=db,
            organization_id=str(user.organization_id),
            user_id=str(user.id),
        )
        db.commit()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Portfolio diagnostic failed: {e}")

    return _run_to_response(result)


@router.get("/diagnostic/{run_id}", response_model=DiagnosticRunResponse)
def get_diagnostic_run(
    run_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get a diagnostic run by ID."""
    run = db.query(DiagnosticRun).filter_by(
        id=run_id, organization_id=user.organization_id
    ).first()
    if not run:
        raise HTTPException(status_code=404, detail="Diagnostic run not found")

    return _run_to_response(run)


@router.get("/diagnostic/{run_id}/slides")
def get_diagnostic_slides(
    run_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get the slide deck for a completed diagnostic run."""
    run = db.query(DiagnosticRun).filter_by(
        id=run_id, organization_id=user.organization_id
    ).first()
    if not run:
        raise HTTPException(status_code=404, detail="Diagnostic run not found")
    if run.status != "COMPLETED":
        raise HTTPException(status_code=422, detail=f"Run status is {run.status}, not COMPLETED")

    # Check cache
    if run.slide_deck_json:
        return run.slide_deck_json

    # Generate slide deck based on scope
    if run.scope == "portfolio":
        from app.services.portfolio_slide_deck_service import assemble_portfolio_slide_deck

        deck = assemble_portfolio_slide_deck(
            run_id=str(run.id),
            metrics=run.metrics_json or {},
            diagnosis=run.diagnosis_json or {},
            action_plan=run.action_plan_json or {},
        )
    else:
        prop = db.query(Property).filter_by(id=run.property_id).first()
        deck = assemble_slide_deck(
            run_id=str(run.id),
            property_name=prop.name if prop else "Unknown",
            metrics=run.metrics_json or {},
            diagnosis=run.diagnosis_json or {},
            action_plan=run.action_plan_json or {},
            config_id=str(run.config_id) if run.config_id else None,
        )

    # Cache
    run.slide_deck_json = deck
    db.commit()

    return deck


@router.get(
    "/properties/{property_id}/diagnostic/history",
    response_model=list[DiagnosticRunSummary],
)
def get_diagnostic_history(
    property_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """List past diagnostic runs for a property."""
    verify_property_access(db, property_id, user)
    runs = (
        db.query(DiagnosticRun)
        .filter_by(property_id=property_id, scope="property")
        .order_by(DiagnosticRun.run_date.desc())
        .limit(20)
        .all()
    )
    return [_run_to_summary(r) for r in runs]


@router.get(
    "/diagnostic/portfolio/history",
    response_model=list[DiagnosticRunSummary],
)
def get_portfolio_history(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """List past portfolio diagnostic runs."""
    runs = (
        db.query(DiagnosticRun)
        .filter_by(organization_id=user.organization_id, scope="portfolio")
        .order_by(DiagnosticRun.run_date.desc())
        .limit(20)
        .all()
    )
    return [_run_to_summary(r) for r in runs]
