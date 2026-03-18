"""Config API endpoints — view, save, generate, preview, history."""
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.config import ClientConfig
from app.models.property import Property
from app.models.user import User
from app.models.diagnostic import AuditLog
from app.auth.dependencies import get_current_user
from app.services.metrics_engine import compute_property_metrics
from app.services.flag_generator import generate_flags

router = APIRouter(prefix="/api/v1", tags=["config"])


class ConfigSaveRequest(BaseModel):
    occupancy_thresholds: dict | None = None
    exposure_thresholds: dict | None = None
    pricing_tolerance: dict | None = None
    concession_policy: dict | None = None
    renewal_policy: dict | None = None
    lease_term_policy: dict | None = None
    experiment_policy: dict | None = None
    amenity_benchmarks: dict | None = None
    investment_thesis: str | None = None
    risk_profile: str | None = None
    hold_period_years: int | None = None
    business_plan_summary: str | None = None


class TemplateApplyRequest(BaseModel):
    template_id: str


@router.get("/properties/{property_id}/config")
def get_config(property_id: str, db: Session = Depends(get_db)):
    """Get the active config for a property."""
    config = db.query(ClientConfig).filter_by(
        property_id=property_id, is_active=True
    ).first()
    if not config:
        raise HTTPException(status_code=404, detail="No active config")
    return _config_response(config)


@router.post("/properties/{property_id}/config")
def save_config(
    property_id: str,
    req: ConfigSaveRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Save a new config version, deactivating the previous."""
    # Deactivate current
    current = db.query(ClientConfig).filter_by(
        property_id=property_id, is_active=True
    ).first()

    new_version = 1
    if current:
        current.is_active = False
        new_version = current.version + 1

    config = ClientConfig(
        id=uuid.uuid4(),
        property_id=property_id,
        version=new_version,
        is_active=True,
        investment_thesis=req.investment_thesis,
        risk_profile=req.risk_profile,
        hold_period_years=req.hold_period_years,
        business_plan_summary=req.business_plan_summary,
        occupancy_thresholds=req.occupancy_thresholds,
        exposure_thresholds=req.exposure_thresholds,
        pricing_tolerance=req.pricing_tolerance,
        concession_policy=req.concession_policy,
        renewal_policy=req.renewal_policy,
        lease_term_policy=req.lease_term_policy,
        experiment_policy=req.experiment_policy,
        amenity_benchmarks=req.amenity_benchmarks,
        created_by=user.id,
    )
    db.add(config)

    # Audit log
    audit = AuditLog(
        id=uuid.uuid4(),
        organization_id=user.organization_id,
        user_id=user.id,
        action="CONFIG_SAVED",
        entity_type="client_config",
        entity_id=str(config.id),
        details={"property_id": property_id, "version": new_version},
    )
    db.add(audit)
    db.commit()

    return _config_response(config)


@router.get("/properties/{property_id}/config/history")
def config_history(property_id: str, db: Session = Depends(get_db)):
    """List config versions for a property."""
    configs = (
        db.query(ClientConfig)
        .filter_by(property_id=property_id)
        .order_by(ClientConfig.version.desc())
        .limit(10)
        .all()
    )
    return [
        {"id": str(c.id), "version": c.version, "is_active": c.is_active,
         "created_at": c.created_at.isoformat() if c.created_at else None}
        for c in configs
    ]


@router.post("/properties/{property_id}/config/preview")
def preview_diagnosis(
    property_id: str,
    req: ConfigSaveRequest,
    db: Session = Depends(get_db),
):
    """Preview flag counts with a draft config (without saving)."""
    from datetime import date
    config_dict = {
        "occupancy_thresholds": req.occupancy_thresholds or {},
        "exposure_thresholds": req.exposure_thresholds or {},
        "pricing_tolerance": req.pricing_tolerance or {},
        "concession_policy": req.concession_policy or {},
        "renewal_policy": req.renewal_policy or {},
        "lease_term_policy": req.lease_term_policy or {},
        "experiment_policy": req.experiment_policy or {},
        "amenity_benchmarks": req.amenity_benchmarks or {},
    }

    metrics = compute_property_metrics(db, property_id, config_dict, date(2026, 3, 15))
    result = {}
    for code, m in metrics["unit_type_metrics"].items():
        flags = generate_flags(m, config_dict)
        result[code] = {
            "flag_count": len(flags),
            "flags": [{"type": f["type"], "severity": f["severity"]} for f in flags],
        }
    return result


@router.get("/config/templates")
def list_templates():
    """List available config templates."""
    from app.services.config_templates import get_templates
    return get_templates()


@router.post("/properties/{property_id}/config/from-template")
def apply_template(
    property_id: str,
    request: TemplateApplyRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Apply a config template to a property."""
    from app.services.config_templates import get_template_config

    template_config = get_template_config(request.template_id)
    if not template_config:
        raise HTTPException(status_code=404, detail="Template not found")

    prop = db.query(Property).filter_by(id=property_id).first()
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")

    # Deactivate current config
    db.query(ClientConfig).filter_by(
        property_id=property_id, is_active=True
    ).update({"is_active": False})

    # Create new config from template
    new_config = ClientConfig(
        id=uuid.uuid4(),
        property_id=property_id,
        version=(db.query(func.max(ClientConfig.version)).filter_by(property_id=property_id).scalar() or 0) + 1,
        is_active=True,
        investment_thesis=f"Applied from template: {request.template_id}",
        risk_profile="balanced",
        hold_period_years=5,
        business_plan_summary=f"Configuration based on {request.template_id} template",
        created_by=str(user.id),
        **template_config,
    )
    db.add(new_config)

    # Audit log
    audit = AuditLog(
        id=uuid.uuid4(),
        organization_id=user.organization_id,
        user_id=str(user.id),
        action="APPLY_TEMPLATE",
        entity_type="client_config",
        entity_id=str(new_config.id),
        details={"template_id": request.template_id, "property_id": property_id},
    )
    db.add(audit)
    db.flush()

    return {"status": "ok", "config_id": str(new_config.id), "version": new_config.version}


def _config_response(config: ClientConfig) -> dict:
    return {
        "id": str(config.id),
        "property_id": str(config.property_id),
        "version": config.version,
        "is_active": config.is_active,
        "investment_thesis": config.investment_thesis,
        "risk_profile": config.risk_profile,
        "hold_period_years": config.hold_period_years,
        "business_plan_summary": config.business_plan_summary,
        "occupancy_thresholds": config.occupancy_thresholds,
        "exposure_thresholds": config.exposure_thresholds,
        "pricing_tolerance": config.pricing_tolerance,
        "concession_policy": config.concession_policy,
        "renewal_policy": config.renewal_policy,
        "lease_term_policy": config.lease_term_policy,
        "experiment_policy": config.experiment_policy,
        "amenity_benchmarks": config.amenity_benchmarks,
    }
