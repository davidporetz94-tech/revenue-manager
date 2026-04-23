"""Pricing and renewal decision API endpoints."""
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.decision import PricingDecision
from app.models.diagnostic import AuditLog
from app.models.property import Property
from app.models.user import User
from app.auth.dependencies import get_current_user
from app.schemas.decision import (
    PricingDecisionCreate,
    PricingDecisionBatchCreate,
    PricingDecisionResponse,
    PricingDecisionLatest,
)

router = APIRouter(prefix="/api/v1", tags=["decisions"])


def _decision_to_response(d: PricingDecision, user_name: str | None = None) -> dict:
    """Convert a PricingDecision ORM object to a response dict."""
    return {
        "id": str(d.id),
        "organization_id": str(d.organization_id),
        "property_id": str(d.property_id),
        "unit_type_code": d.unit_type_code,
        "decision_type": d.decision_type,
        "decision": d.decision,
        "recommended_value": d.recommended_value,
        "approved_value": d.approved_value,
        "reason": d.reason,
        "decided_by": str(d.decided_by),
        "decided_by_name": user_name,
        "decided_at": d.decided_at.isoformat() if d.decided_at else None,
        "context_snapshot": d.context_snapshot,
    }


def _create_decision(
    db: Session, user: User, req: PricingDecisionCreate
) -> PricingDecision:
    """Create a single pricing decision with audit logging."""
    prop_id = uuid.UUID(req.property_id) if isinstance(req.property_id, str) else req.property_id
    prop = db.query(Property).filter_by(
        id=prop_id, organization_id=user.organization_id
    ).first()
    if not prop:
        raise HTTPException(
            status_code=404,
            detail=f"Property {req.property_id} not found in your organization",
        )

    decision = PricingDecision(
        id=uuid.uuid4(),
        organization_id=user.organization_id,
        property_id=uuid.UUID(req.property_id),
        unit_type_code=req.unit_type_code,
        decision_type=req.decision_type,
        decision=req.decision,
        recommended_value=req.recommended_value,
        approved_value=req.approved_value,
        reason=req.reason,
        decided_by=user.id,
        decided_at=datetime.utcnow(),
        context_snapshot=req.context_snapshot,
    )
    db.add(decision)

    audit = AuditLog(
        id=uuid.uuid4(),
        organization_id=user.organization_id,
        user_id=user.id,
        action=f"{req.decision_type}_DECISION_{req.decision}",
        entity_type="pricing_decision",
        entity_id=str(decision.id),
        details={
            "property_id": req.property_id,
            "unit_type_code": req.unit_type_code,
            "decision": req.decision,
            "recommended_value": req.recommended_value,
            "approved_value": req.approved_value,
        },
    )
    db.add(audit)

    return decision


@router.post("/pricing-decisions", response_model=PricingDecisionResponse)
def create_pricing_decision(
    req: PricingDecisionCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    """Create a single pricing or renewal decision."""
    try:
        decision = _create_decision(db, user, req)
        db.commit()
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to create decision: {e}")

    return _decision_to_response(decision, user.full_name)


@router.post("/pricing-decisions/batch")
def create_batch_decisions(
    req: PricingDecisionBatchCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    """Create up to 20 decisions in a single request (for 'Approve All')."""
    try:
        decisions = []
        for item in req.decisions:
            d = _create_decision(db, user, item)
            decisions.append(d)
        db.commit()
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500, detail=f"Failed to create batch decisions: {e}"
        )

    return {
        "created": len(decisions),
        "decisions": [_decision_to_response(d, user.full_name) for d in decisions],
    }


@router.get("/pricing-decisions")
def list_pricing_decisions(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    decision_type: str | None = Query(None, description="PRICING or RENEWAL"),
    property_id: str | None = Query(None),
    since: str | None = Query(None, description="ISO datetime filter"),
    limit: int = Query(100, le=500),
) -> list[dict]:
    """List decisions for the current organization with optional filters."""
    query = (
        db.query(PricingDecision)
        .filter_by(organization_id=user.organization_id)
    )

    if decision_type:
        query = query.filter(PricingDecision.decision_type == decision_type)
    if property_id:
        pid = uuid.UUID(property_id) if isinstance(property_id, str) else property_id
        query = query.filter(PricingDecision.property_id == pid)
    if since:
        try:
            since_dt = datetime.fromisoformat(since)
            query = query.filter(PricingDecision.decided_at >= since_dt)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid 'since' datetime")

    decisions = query.order_by(desc(PricingDecision.decided_at)).limit(limit).all()

    # Batch-load user names
    user_ids = {d.decided_by for d in decisions}
    users = {
        u.id: u.full_name
        for u in db.query(User).filter(User.id.in_(user_ids)).all()
    } if user_ids else {}

    return [
        _decision_to_response(d, users.get(d.decided_by))
        for d in decisions
    ]


@router.get("/pricing-decisions/latest")
def get_latest_decisions(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    property_id: str = Query(..., description="Property ID"),
    decision_type: str = Query("PRICING", description="PRICING or RENEWAL"),
) -> list[dict]:
    """Get the latest decision per unit type for a property.

    Uses a subquery to find the max decided_at per unit_type_code,
    then fetches the full row for each.
    """
    from sqlalchemy import func

    pid = uuid.UUID(property_id) if isinstance(property_id, str) else property_id

    # Subquery: max decided_at per unit_type_code
    subq = (
        db.query(
            PricingDecision.unit_type_code,
            func.max(PricingDecision.decided_at).label("max_decided_at"),
        )
        .filter_by(
            organization_id=user.organization_id,
            property_id=pid,
            decision_type=decision_type,
        )
        .group_by(PricingDecision.unit_type_code)
        .subquery()
    )

    decisions = (
        db.query(PricingDecision)
        .join(
            subq,
            (PricingDecision.unit_type_code == subq.c.unit_type_code)
            & (PricingDecision.decided_at == subq.c.max_decided_at),
        )
        .filter(
            PricingDecision.organization_id == user.organization_id,
            PricingDecision.property_id == pid,
            PricingDecision.decision_type == decision_type,
        )
        .all()
    )

    # Load user names
    user_ids = {d.decided_by for d in decisions}
    users = {
        u.id: u.full_name
        for u in db.query(User).filter(User.id.in_(user_ids)).all()
    } if user_ids else {}

    return [
        {
            "unit_type_code": d.unit_type_code,
            "decision": d.decision,
            "decided_at": d.decided_at.isoformat() if d.decided_at else None,
            "approved_value": d.approved_value,
            "decided_by_name": users.get(d.decided_by),
        }
        for d in decisions
    ]
