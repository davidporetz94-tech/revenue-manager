"""Experiment tracking API endpoints."""
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.experiment import Experiment, ExperimentAssignment
from app.models.diagnostic import AuditLog
from app.models.user import User
from app.auth.dependencies import get_current_user

router = APIRouter(prefix="/api/v1", tags=["experiments"])


class AssignmentUpdate(BaseModel):
    leased: bool | None = None
    lease_date: str | None = None
    days_to_lease: int | None = None
    application_received: bool | None = None
    tours_count: int | None = None


@router.get("/properties/{property_id}/experiments")
def list_experiments(property_id: str, db: Session = Depends(get_db)):
    """List experiments for a property (via diagnostic runs)."""
    from app.models.diagnostic import DiagnosticRun
    run_ids = [
        str(r.id) for r in
        db.query(DiagnosticRun.id).filter_by(property_id=property_id).all()
    ]
    if not run_ids:
        return []

    experiments = db.query(Experiment).filter(
        Experiment.diagnostic_run_id.in_(run_ids)
    ).order_by(Experiment.created_at.desc()).all()

    result = []
    for exp in experiments:
        assignments = db.query(ExperimentAssignment).filter_by(experiment_id=exp.id).all()
        result.append({
            "id": str(exp.id),
            "unit_type_id": str(exp.unit_type_id),
            "status": exp.status,
            "experiment_design": exp.experiment_design,
            "outcome": exp.outcome,
            "created_at": exp.created_at.isoformat() if exp.created_at else None,
            "assignments": [
                {
                    "id": str(a.id),
                    "unit_id": str(a.unit_id),
                    "arm_label": a.arm_label,
                    "assigned_price": a.assigned_price,
                    "leased": a.leased,
                    "days_to_lease": a.days_to_lease,
                    "tours_count": a.tours_count,
                }
                for a in assignments
            ],
        })
    return result


@router.post("/experiments/{experiment_id}/approve")
def approve_experiment(
    experiment_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Approve a proposed experiment."""
    exp = db.query(Experiment).filter_by(id=experiment_id).first()
    if not exp:
        raise HTTPException(status_code=404, detail="Experiment not found")
    if exp.status != "PROPOSED":
        raise HTTPException(status_code=400, detail=f"Cannot approve experiment with status {exp.status}")

    exp.status = "APPROVED"
    exp.approved_by = user.id
    exp.approved_at = datetime.utcnow()

    audit = AuditLog(
        id=uuid.uuid4(),
        organization_id=user.organization_id,
        user_id=user.id,
        action="EXPERIMENT_APPROVED",
        entity_type="experiment",
        entity_id=str(exp.id),
    )
    db.add(audit)
    db.commit()

    return {"message": "Experiment approved", "status": exp.status}


@router.post("/experiments/{experiment_id}/cancel")
def cancel_experiment(
    experiment_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Cancel an experiment."""
    exp = db.query(Experiment).filter_by(id=experiment_id).first()
    if not exp:
        raise HTTPException(status_code=404, detail="Experiment not found")
    if exp.status in ("CONVERGED", "CANCELLED"):
        raise HTTPException(status_code=400, detail=f"Cannot cancel experiment with status {exp.status}")

    exp.status = "CANCELLED"
    exp.ended_at = datetime.utcnow()

    audit = AuditLog(
        id=uuid.uuid4(),
        organization_id=user.organization_id,
        user_id=user.id,
        action="EXPERIMENT_CANCELLED",
        entity_type="experiment",
        entity_id=str(exp.id),
    )
    db.add(audit)
    db.commit()

    return {"message": "Experiment cancelled", "status": exp.status}


@router.put("/experiments/{experiment_id}/assignments/{assignment_id}")
def update_assignment(
    experiment_id: str,
    assignment_id: str,
    req: AssignmentUpdate,
    db: Session = Depends(get_db),
):
    """Update outcome data for an experiment assignment."""
    assignment = db.query(ExperimentAssignment).filter_by(
        id=assignment_id, experiment_id=experiment_id
    ).first()
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")

    if req.leased is not None:
        assignment.leased = req.leased
    if req.days_to_lease is not None:
        assignment.days_to_lease = req.days_to_lease
    if req.application_received is not None:
        assignment.application_received = req.application_received
    if req.tours_count is not None:
        assignment.tours_count = req.tours_count

    db.commit()
    return {"message": "Assignment updated"}
