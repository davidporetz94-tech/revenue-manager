"""Comp management API endpoints."""
import uuid
import random
from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.comp import CompProperty, CompUnitType, CompRent
from app.models.diagnostic import AuditLog
from app.models.user import User
from app.auth.dependencies import get_current_user

router = APIRouter(prefix="/api/v1", tags=["comps"])


@router.get("/properties/{property_id}/comps")
def get_comps(property_id: str, db: Session = Depends(get_db)):
    """Get comp properties and their latest rents."""
    comps = db.query(CompProperty).filter_by(property_id=property_id, is_active=True).all()
    result = []
    for cp in comps:
        unit_types = db.query(CompUnitType).filter_by(comp_property_id=cp.id).all()
        ut_data = []
        for cut in unit_types:
            latest_rent = (
                db.query(CompRent)
                .filter_by(comp_unit_type_id=cut.id)
                .order_by(CompRent.observation_date.desc())
                .first()
            )
            ut_data.append({
                "id": str(cut.id),
                "bed": cut.bed,
                "bath": cut.bath,
                "subject_unit_type_id": str(cut.subject_unit_type_id),
                "latest_rent": latest_rent.asking_rent if latest_rent else None,
                "latest_date": latest_rent.observation_date.isoformat() if latest_rent else None,
            })

        result.append({
            "id": str(cp.id),
            "name": cp.name,
            "address": cp.address,
            "total_units": cp.total_units,
            "year_built": cp.year_built,
            "property_class": cp.property_class,
            "distance_miles": cp.distance_miles,
            "last_refreshed_at": cp.last_refreshed_at.isoformat() if cp.last_refreshed_at else None,
            "unit_types": ut_data,
        })
    return result


@router.get("/properties/{property_id}/comps/trends")
def get_comp_trends(property_id: str, db: Session = Depends(get_db)):
    """Get comp rent time series for a property."""
    comps = db.query(CompProperty).filter_by(property_id=property_id, is_active=True).all()
    result = []
    for cp in comps:
        for cut in db.query(CompUnitType).filter_by(comp_property_id=cp.id).all():
            rents = (
                db.query(CompRent)
                .filter_by(comp_unit_type_id=cut.id)
                .order_by(CompRent.observation_date)
                .all()
            )
            result.append({
                "comp_name": cp.name,
                "bed": cut.bed,
                "bath": cut.bath,
                "series": [
                    {"date": r.observation_date.isoformat(), "rent": r.asking_rent}
                    for r in rents
                ],
            })
    return result


@router.post("/comps/refresh")
def refresh_comps(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Simulate comp rent refresh — add new observations with +/-1-2% noise."""
    today = date.today()
    refreshed = 0

    for cp in db.query(CompProperty).filter_by(is_active=True).all():
        for cut in db.query(CompUnitType).filter_by(comp_property_id=cp.id).all():
            latest = (
                db.query(CompRent)
                .filter_by(comp_unit_type_id=cut.id)
                .order_by(CompRent.observation_date.desc())
                .first()
            )
            if not latest:
                continue

            # +/-1-2% noise
            noise_pct = random.uniform(-0.02, 0.02)
            new_rent = round(latest.asking_rent * (1 + noise_pct))

            new_obs = CompRent(
                id=uuid.uuid4(),
                comp_unit_type_id=cut.id,
                observation_date=today,
                asking_rent=new_rent,
                data_source="simulated_refresh",
            )
            db.add(new_obs)
            refreshed += 1

        cp.last_refreshed_at = datetime.utcnow()

    # Audit log
    audit = AuditLog(
        id=uuid.uuid4(),
        organization_id=user.organization_id,
        user_id=user.id,
        action="COMP_REFRESH",
        entity_type="comp_rents",
        details={"observations_created": refreshed},
    )
    db.add(audit)
    db.commit()

    return {"message": f"Refreshed {refreshed} comp rent observations"}
