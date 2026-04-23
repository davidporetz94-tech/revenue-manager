"""Renewal rule management API endpoints."""
import uuid
import math
from datetime import datetime, date

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, model_validator
from sqlalchemy import desc, extract
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.renewal import RenewalRule, RenewalOutput
from app.models.property import Property, Unit, UnitType
from app.models.diagnostic import AuditLog
from app.models.user import User
from app.auth.dependencies import get_current_user, verify_property_access

router = APIRouter(prefix="/api/v1", tags=["renewals"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class RenewalRuleCreate(BaseModel):
    """Request body for creating/updating a renewal rule."""

    property_id: str
    unit_type_code: str
    target_month: str  # "YYYY-MM-DD" (first of month)
    calc_method: str  # DISCOUNT_FROM_NEW or INCREASE_FROM_IN_PLACE
    calc_value: float  # percentage as decimal, e.g., 0.03 for 3%
    min_increase_pct: float
    max_increase_pct: float

    @model_validator(mode="after")
    def validate_fields(self) -> "RenewalRuleCreate":
        """Validate rule parameters."""
        if self.calc_method not in ("DISCOUNT_FROM_NEW", "INCREASE_FROM_IN_PLACE"):
            raise ValueError("calc_method must be DISCOUNT_FROM_NEW or INCREASE_FROM_IN_PLACE")
        if self.min_increase_pct > self.max_increase_pct:
            raise ValueError("min_increase_pct cannot exceed max_increase_pct")
        return self


class RenewalPreviewRequest(BaseModel):
    """Request body for previewing renewal outputs without saving."""

    property_id: str
    unit_type_code: str
    target_month: str
    calc_method: str
    calc_value: float
    min_increase_pct: float
    max_increase_pct: float


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _compute_renewal_price(
    in_place: float,
    new_lease: float,
    calc_method: str,
    calc_value: float,
    min_increase_pct: float,
    max_increase_pct: float,
) -> tuple[float, float, str | None]:
    """Compute renewal price from rule parameters.

    Returns (renewal_rent, effective_increase_pct, clamp_status).
    """
    if calc_method == "DISCOUNT_FROM_NEW":
        raw = new_lease * (1.0 - calc_value)
    else:  # INCREASE_FROM_IN_PLACE
        raw = in_place * (1.0 + calc_value)

    if in_place > 0:
        eff_pct = (raw - in_place) / in_place
    else:
        eff_pct = 0.0

    clamp = None
    if eff_pct < min_increase_pct:
        raw = in_place * (1.0 + min_increase_pct)
        eff_pct = min_increase_pct
        clamp = "MIN"
    elif eff_pct > max_increase_pct:
        raw = in_place * (1.0 + max_increase_pct)
        eff_pct = max_increase_pct
        clamp = "MAX"

    return round(raw), round(eff_pct, 4), clamp


def _get_expiring_units(
    db: Session,
    property_id: str,
    unit_type_code: str,
    target_month: date,
) -> list[Unit]:
    """Get units expiring in the given month for a floorplan."""
    pid = uuid.UUID(property_id) if isinstance(property_id, str) else property_id

    # Get unit type IDs for this code in this property
    ut_ids = [
        ut.id for ut in
        db.query(UnitType).filter_by(property_id=pid, code=unit_type_code).all()
    ]
    if not ut_ids:
        return []

    # Find occupied units with lease_end in target month
    year = target_month.year
    month = target_month.month

    units = (
        db.query(Unit)
        .filter(
            Unit.unit_type_id.in_(ut_ids),
            Unit.status.in_(["occupied", "OCCUPIED", "on_notice", "ON_NOTICE"]),
            Unit.lease_end.isnot(None),
            extract("year", Unit.lease_end) == year,
            extract("month", Unit.lease_end) == month,
        )
        .order_by(Unit.unit_number)
        .all()
    )
    return units


def _get_asking_rent_for_type(db: Session, property_id: str, unit_type_code: str) -> float:
    """Get the current asking rent for a unit type (new lease pricing)."""
    pid = uuid.UUID(property_id) if isinstance(property_id, str) else property_id
    ut = db.query(UnitType).filter_by(property_id=pid, code=unit_type_code).first()
    if not ut:
        return 0.0
    # Get average asking rent from available units, or fall back to base_rent
    available = (
        db.query(Unit)
        .filter(
            Unit.unit_type_id == ut.id,
            Unit.asking_rent.isnot(None),
            Unit.status.in_(["vacant", "VACANT", "on_notice", "ON_NOTICE"]),
        )
        .all()
    )
    if available:
        return round(sum(u.asking_rent for u in available) / len(available))
    return round(ut.base_rent)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/renewals/expiring")
def get_expiring_leases(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    property_id: str = Query(...),
    target_month: str = Query(..., description="YYYY-MM-DD first of month"),
) -> dict:
    """Get units with leases expiring in a target month, grouped by floorplan."""
    prop_id = uuid.UUID(property_id) if isinstance(property_id, str) else property_id
    prop = db.query(Property).filter_by(
        id=prop_id, organization_id=user.organization_id
    ).first()
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")

    month_date = date.fromisoformat(target_month)
    year, month = month_date.year, month_date.month

    # Get all unit types for this property
    unit_types = db.query(UnitType).filter_by(property_id=prop_id).all()

    result = {}
    for ut in unit_types:
        units = (
            db.query(Unit)
            .filter(
                Unit.unit_type_id == ut.id,
                Unit.status.in_(["occupied", "OCCUPIED", "on_notice", "ON_NOTICE"]),
                Unit.lease_end.isnot(None),
                extract("year", Unit.lease_end) == year,
                extract("month", Unit.lease_end) == month,
            )
            .order_by(Unit.unit_number)
            .all()
        )
        if not units:
            continue

        # Get asking rent for this type
        asking = _get_asking_rent_for_type(db, property_id, ut.code)

        result[ut.code] = {
            "unit_type_code": ut.code,
            "bed": ut.bed,
            "bath": ut.bath,
            "asking_rent": asking,
            "unit_count": len(units),
            "units": [
                {
                    "id": str(u.id),
                    "unit_number": u.unit_number,
                    "floor": u.floor,
                    "sqft": u.sqft,
                    "current_rent": u.current_rent,
                    "lease_end": u.lease_end.isoformat() if u.lease_end else None,
                    "amenity_premium": u.amenity_premium,
                }
                for u in units
            ],
        }

    return {
        "property_id": property_id,
        "target_month": target_month,
        "floorplans": result,
    }


@router.post("/renewals/preview")
def preview_renewal_pricing(
    req: RenewalPreviewRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    """Preview computed renewal prices without saving."""
    verify_property_access(db, req.property_id, user)
    month_date = date.fromisoformat(req.target_month)
    units = _get_expiring_units(db, req.property_id, req.unit_type_code, month_date)
    new_lease = _get_asking_rent_for_type(db, req.property_id, req.unit_type_code)

    outputs = []
    for u in units:
        in_place = u.current_rent or 0
        renewal, eff_pct, clamp = _compute_renewal_price(
            in_place, new_lease, req.calc_method, req.calc_value,
            req.min_increase_pct, req.max_increase_pct,
        )
        outputs.append({
            "unit_id": str(u.id),
            "unit_number": u.unit_number,
            "in_place_rent": in_place,
            "new_lease_rent": new_lease,
            "computed_renewal_rent": renewal,
            "effective_increase_pct": eff_pct,
            "was_clamped": clamp,
            "monthly_delta": renewal - in_place,
        })

    total_delta = sum(o["monthly_delta"] for o in outputs)
    avg_increase = (
        sum(o["effective_increase_pct"] for o in outputs) / len(outputs)
        if outputs else 0
    )

    return {
        "unit_type_code": req.unit_type_code,
        "unit_count": len(outputs),
        "outputs": outputs,
        "summary": {
            "total_monthly_delta": total_delta,
            "total_annual_delta": total_delta * 12,
            "avg_increase_pct": avg_increase,
            "clamped_count": sum(1 for o in outputs if o["was_clamped"]),
        },
    }


@router.post("/renewal-rules")
def save_renewal_rule(
    req: RenewalRuleCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    """Save a renewal rule and generate per-unit outputs."""
    prop_id = uuid.UUID(req.property_id) if isinstance(req.property_id, str) else req.property_id
    prop = db.query(Property).filter_by(
        id=prop_id, organization_id=user.organization_id
    ).first()
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")

    month_date = date.fromisoformat(req.target_month)

    # Delete existing rule + outputs for this floorplan/month (replace)
    existing = (
        db.query(RenewalRule)
        .filter_by(
            property_id=prop_id,
            unit_type_code=req.unit_type_code,
            target_month=month_date,
        )
        .first()
    )
    if existing:
        db.query(RenewalOutput).filter_by(rule_id=existing.id).delete()
        db.delete(existing)

    # Create rule
    rule = RenewalRule(
        id=uuid.uuid4(),
        organization_id=user.organization_id,
        property_id=prop_id,
        unit_type_code=req.unit_type_code,
        target_month=month_date,
        calc_method=req.calc_method,
        calc_value=req.calc_value,
        min_increase_pct=req.min_increase_pct,
        max_increase_pct=req.max_increase_pct,
        created_by=user.id,
    )
    db.add(rule)

    # Compute outputs
    units = _get_expiring_units(db, req.property_id, req.unit_type_code, month_date)
    new_lease = _get_asking_rent_for_type(db, req.property_id, req.unit_type_code)

    outputs = []
    for u in units:
        in_place = u.current_rent or 0
        renewal, eff_pct, clamp = _compute_renewal_price(
            in_place, new_lease, req.calc_method, req.calc_value,
            req.min_increase_pct, req.max_increase_pct,
        )
        out = RenewalOutput(
            id=uuid.uuid4(),
            rule_id=rule.id,
            unit_id=u.id,
            unit_number=u.unit_number,
            in_place_rent=in_place,
            new_lease_rent=new_lease,
            computed_renewal_rent=renewal,
            effective_increase_pct=eff_pct,
            was_clamped=clamp,
        )
        db.add(out)
        outputs.append(out)

    # Audit log
    audit = AuditLog(
        id=uuid.uuid4(),
        organization_id=user.organization_id,
        user_id=user.id,
        action="RENEWAL_RULE_SET",
        entity_type="renewal_rule",
        entity_id=str(rule.id),
        details={
            "property_id": req.property_id,
            "unit_type_code": req.unit_type_code,
            "target_month": req.target_month,
            "calc_method": req.calc_method,
            "calc_value": req.calc_value,
            "min_increase_pct": req.min_increase_pct,
            "max_increase_pct": req.max_increase_pct,
            "units_affected": len(outputs),
        },
    )
    db.add(audit)

    try:
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to save rule: {e}")

    total_delta = sum(o.computed_renewal_rent - o.in_place_rent for o in outputs)

    return {
        "id": str(rule.id),
        "unit_type_code": rule.unit_type_code,
        "target_month": rule.target_month.isoformat(),
        "calc_method": rule.calc_method,
        "calc_value": rule.calc_value,
        "min_increase_pct": rule.min_increase_pct,
        "max_increase_pct": rule.max_increase_pct,
        "created_by": user.full_name,
        "created_at": rule.created_at.isoformat() if rule.created_at else None,
        "units_affected": len(outputs),
        "total_monthly_delta": total_delta,
        "outputs": [
            {
                "unit_number": o.unit_number,
                "in_place_rent": o.in_place_rent,
                "new_lease_rent": o.new_lease_rent,
                "computed_renewal_rent": o.computed_renewal_rent,
                "effective_increase_pct": o.effective_increase_pct,
                "was_clamped": o.was_clamped,
            }
            for o in outputs
        ],
    }


@router.get("/renewal-rules")
def get_renewal_rules(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    property_id: str = Query(...),
    target_month: str | None = Query(None),
) -> list[dict]:
    """Get renewal rules for a property, optionally filtered by month."""
    pid = uuid.UUID(property_id) if isinstance(property_id, str) else property_id
    query = db.query(RenewalRule).filter_by(
        organization_id=user.organization_id,
        property_id=pid,
    )
    if target_month:
        query = query.filter(RenewalRule.target_month == date.fromisoformat(target_month))

    rules = query.order_by(RenewalRule.target_month, RenewalRule.unit_type_code).all()

    # Load outputs for each rule
    result = []
    for rule in rules:
        outputs = db.query(RenewalOutput).filter_by(rule_id=rule.id).all()
        total_delta = sum(o.computed_renewal_rent - o.in_place_rent for o in outputs)

        # Get creator name
        creator = db.query(User).filter_by(id=rule.created_by).first()

        result.append({
            "id": str(rule.id),
            "unit_type_code": rule.unit_type_code,
            "target_month": rule.target_month.isoformat(),
            "calc_method": rule.calc_method,
            "calc_value": rule.calc_value,
            "min_increase_pct": rule.min_increase_pct,
            "max_increase_pct": rule.max_increase_pct,
            "created_by": creator.full_name if creator else None,
            "created_at": rule.created_at.isoformat() if rule.created_at else None,
            "units_affected": len(outputs),
            "total_monthly_delta": total_delta,
            "outputs": [
                {
                    "unit_number": o.unit_number,
                    "in_place_rent": o.in_place_rent,
                    "new_lease_rent": o.new_lease_rent,
                    "computed_renewal_rent": o.computed_renewal_rent,
                    "effective_increase_pct": o.effective_increase_pct,
                    "was_clamped": o.was_clamped,
                }
                for o in outputs
            ],
        })

    return result
