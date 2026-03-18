"""Properties API endpoints."""
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.property import Property, UnitType, Unit
from app.models.config import ClientConfig
from app.models.snapshot import HistoricalSnapshot
from app.models.user import User
from app.auth.dependencies import get_current_user
from app.services.metrics_engine import compute_property_metrics

router = APIRouter(prefix="/api/v1", tags=["properties"])


def _get_demo_user(db: Session) -> User:
    user = db.query(User).filter_by(email="demo@example.com").first()
    if not user:
        raise HTTPException(status_code=500, detail="Demo user not found")
    return user


def _compute_property_summary(db: Session, prop: Property) -> dict:
    """Compute summary KPIs for a property using the metrics engine."""
    config = db.query(ClientConfig).filter_by(
        property_id=prop.id, is_active=True
    ).first()
    if not config:
        return {"total_vacant": 0, "blended_occ": 0, "daily_burn": 0, "monthly_cost": 0}

    config_dict = {
        k: getattr(config, k) or {}
        for k in [
            "occupancy_thresholds", "exposure_thresholds", "pricing_tolerance",
            "concession_policy", "renewal_policy", "lease_term_policy",
            "experiment_policy", "amenity_benchmarks",
        ]
    }
    metrics = compute_property_metrics(db, str(prop.id), config_dict)
    pm = metrics.get("portfolio_metrics", {})
    ut_metrics = metrics.get("unit_type_metrics", {})

    total_daily_burn = sum(
        m["revenue_metrics"]["daily_vacancy_burn"]
        for m in ut_metrics.values()
    )
    total_monthly = sum(
        m["revenue_metrics"]["monthly_vacancy_cost"]
        for m in ut_metrics.values()
    )

    return {
        "total_vacant": pm.get("total_vacant", 0),
        "blended_occ": pm.get("blended_occupancy", 0),
        "daily_burn": total_daily_burn,
        "monthly_cost": total_monthly,
    }


@router.get("/properties")
def list_properties(db: Session = Depends(get_db)):
    """List all properties with summary KPIs."""
    user = _get_demo_user(db)
    props = db.query(Property).filter_by(organization_id=user.organization_id).all()
    result = []
    for p in props:
        summary = _compute_property_summary(db, p)
        result.append({
            "id": str(p.id),
            "name": p.name,
            "code": p.code,
            "address": p.address,
            "submarket": p.submarket,
            "total_units": p.total_units,
            "year_built": p.year_built,
            "property_class": p.property_class,
            **summary,
        })
    return result


@router.get("/properties/{property_id}")
def get_property(property_id: str, db: Session = Depends(get_db)):
    """Get a single property by ID."""
    prop = db.query(Property).filter_by(id=property_id).first()
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")
    return {
        "id": str(prop.id),
        "name": prop.name,
        "code": prop.code,
        "address": prop.address,
        "submarket": prop.submarket,
        "total_units": prop.total_units,
        "year_built": prop.year_built,
        "property_class": prop.property_class,
    }


@router.get("/properties/{property_id}/summary")
def get_property_summary(property_id: str, db: Session = Depends(get_db)):
    """Get detailed unit type metrics and trends for a property.

    Returns data needed by the frontend dashboard and overview tabs.
    """
    prop = db.query(Property).filter_by(id=property_id).first()
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")

    config = db.query(ClientConfig).filter_by(
        property_id=property_id, is_active=True
    ).first()
    if not config:
        raise HTTPException(status_code=404, detail="No active config")

    config_dict = {
        k: getattr(config, k) or {}
        for k in [
            "occupancy_thresholds", "exposure_thresholds", "pricing_tolerance",
            "concession_policy", "renewal_policy", "lease_term_policy",
            "experiment_policy", "amenity_benchmarks",
        ]
    }
    metrics = compute_property_metrics(db, property_id, config_dict)

    # Build frontend-friendly unit type data
    unit_types = {}
    for code, m in metrics["unit_type_metrics"].items():
        occ = m["occupancy_metrics"]
        exp = m["exposure_metrics"]
        ps = m["pricing_spreads"]
        rev = m["revenue_metrics"]
        vel = m["velocity_metrics"]
        dem = m["demand_metrics"]

        unit_types[code] = {
            "total": m["identity"]["total_units"],
            "occupied": occ["occupied"],
            "vacant": occ["vacant"],
            "onNotice": occ["on_notice"],
            "occ": occ["occupancy_rate"],
            "asking": ps["asking_rent"],
            "comps": ps["comps_rent"],
            "inPlace": ps["in_place_rent"],
            "executed": ps["executed_rent"],
            "predicted": ps["predicted_rent"],
            "base": ps["base_rent"],
            "amenity": ps["amenity_price"],
            "dom": vel["avg_days_on_market"],
            "dv": vel["avg_days_vacant"],
            "exposure": exp["total_exposure_pct"],
            "demand": dem["demand_score"],
            "dailyBurn": rev["daily_vacancy_burn"],
            "monthlyCost": rev["monthly_vacancy_cost"],
            "property": prop.name,
        }

    # Build trend data from snapshots
    trends = {}
    ut_models = db.query(UnitType).filter_by(property_id=property_id).all()
    month_labels = ["Dec", "Jan", "Feb", "Mar"]
    for ut in ut_models:
        snapshots = (
            db.query(HistoricalSnapshot)
            .filter_by(unit_type_id=ut.id)
            .order_by(HistoricalSnapshot.snapshot_date)
            .all()
        )
        trend_points = []
        for i, s in enumerate(snapshots):
            label = month_labels[i] if i < len(month_labels) else s.snapshot_date.strftime("%b")
            trend_points.append({
                "m": label,
                "occ": s.occupancy_rate,
                "asking": s.avg_asking_rent,
                "comps": s.comps_avg,
            })
        trends[ut.code] = trend_points

    return {
        "unit_types": unit_types,
        "trends": trends,
        "portfolio": metrics.get("portfolio_metrics", {}),
    }
