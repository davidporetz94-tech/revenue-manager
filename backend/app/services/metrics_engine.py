"""Metrics engine service — orchestrates DB queries and passes data to engine modules.

This is the ONLY place where DB access happens for metrics computation.
Engine modules receive plain dicts, never ORM objects.
"""
from datetime import date

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.property import Unit, UnitType, Property
from app.models.comp import CompRent, CompUnitType
from app.models.snapshot import HistoricalSnapshot
from app.engine.aggregator import compute_unit_type_metrics, compute_portfolio_metrics
from app.engine.revenue_optimizer import (
    compute_implied_elasticity,
    compute_optimal_price,
    decompose_revenue_gap,
    compute_revenue_efficiency,
)
from app.engine.renewal_optimizer import compute_renewal_opportunity


def _units_to_dicts(units: list[Unit]) -> list[dict]:
    """Convert ORM Unit objects to plain dicts for engine consumption."""
    return [
        {
            "id": str(u.id),
            "unit_number": u.unit_number,
            "status": u.status,
            "current_rent": u.current_rent,
            "asking_rent": u.asking_rent,
            "predicted_rent": u.predicted_rent,
            "amenity_premium": u.amenity_premium,
            "days_on_market": u.days_on_market,
            "days_vacant": u.days_vacant,
            "lease_start": u.lease_start,
            "lease_end": u.lease_end,
            "move_out_date": u.move_out_date,
            "last_executed_rent": u.last_executed_rent,
            "last_executed_date": u.last_executed_date,
            "concession_active": u.concession_active,
            "concession_type": u.concession_type,
            "concession_value_monthly": u.concession_value_monthly,
        }
        for u in units
    ]


def _snapshots_to_dicts(snapshots: list[HistoricalSnapshot]) -> list[dict]:
    """Convert ORM HistoricalSnapshot objects to plain dicts."""
    return [
        {
            "snapshot_date": s.snapshot_date,
            "occupancy_rate": s.occupancy_rate,
            "avg_asking_rent": s.avg_asking_rent,
            "avg_executed_rent": s.avg_executed_rent,
            "comps_avg": s.comps_avg,
            "demand_score": s.demand_score,
        }
        for s in snapshots
    ]


def _fetch_comp_trends(
    db: Session,
    unit_type_id: str,
) -> list[dict]:
    """Fetch monthly average comp rents for a unit type, ordered by date.

    Args:
        db: database session.
        unit_type_id: UUID of the subject unit type.

    Returns:
        List of dicts with observation_date and avg_asking_rent.
    """
    rows = (
        db.query(
            CompRent.observation_date,
            func.avg(CompRent.asking_rent).label("avg_asking_rent"),
        )
        .join(CompUnitType)
        .filter(CompUnitType.subject_unit_type_id == unit_type_id)
        .group_by(CompRent.observation_date)
        .order_by(CompRent.observation_date)
        .all()
    )
    return [
        {"observation_date": r.observation_date, "avg_asking_rent": float(r.avg_asking_rent)}
        for r in rows
    ]


def _compute_concession_data(units_data: list[dict]) -> dict:
    """Compute concession drag from units with active concessions.

    Args:
        units_data: List of unit dicts with concession fields.

    Returns:
        Dict with total_concession_drag_monthly and active_concession_count.
    """
    total_drag = 0.0
    active_count = 0
    for u in units_data:
        if u.get("concession_active"):
            active_count += 1
            monthly_value = u.get("concession_value_monthly") or 0.0
            total_drag += monthly_value
    return {
        "total_concession_drag_monthly": total_drag,
        "active_concession_count": active_count,
    }


def compute_property_metrics(
    db: Session,
    property_id: str,
    config: dict,
    reference_date: date | None = None,
) -> dict:
    """Compute metrics for all unit types in a property.

    Args:
        db: database session.
        property_id: UUID of the property.
        config: client config dict with all threshold sections.
        reference_date: date for calculations (defaults to today).

    Returns:
        Dict with unit_type_metrics list and portfolio_metrics.
    """
    if reference_date is None:
        reference_date = date.today()

    prop = db.query(Property).filter_by(id=property_id).first()
    if not prop:
        raise ValueError(f"Property {property_id} not found")

    unit_types = db.query(UnitType).filter_by(property_id=property_id).all()

    zone_config = config.get("revenue_efficiency_zones", {})
    renewal_config = config.get("renewal_policy", {})

    all_metrics = []
    for ut in unit_types:
        # Fetch units
        units = db.query(Unit).filter_by(unit_type_id=ut.id).all()
        units_data = _units_to_dicts(units)

        # Fetch comp avg for March 2026 (latest)
        comps_avg_result = db.query(func.avg(CompRent.asking_rent)).join(CompUnitType).filter(
            CompUnitType.subject_unit_type_id == ut.id,
            CompRent.observation_date == date(2026, 3, 1),
        ).scalar()
        comps_avg = round(comps_avg_result) if comps_avg_result else 0.0

        # Fetch snapshots
        snapshots = db.query(HistoricalSnapshot).filter_by(
            unit_type_id=ut.id
        ).order_by(HistoricalSnapshot.snapshot_date).all()
        snapshots_data = _snapshots_to_dicts(snapshots)

        # Fetch comp trends for elasticity computation
        comp_trends = _fetch_comp_trends(db, ut.id)

        # Get demand score from latest snapshot
        demand_score = 0.0
        if snapshots_data:
            demand_score = snapshots_data[-1].get("demand_score", 0.0) or 0.0

        identity = {
            "property": prop.name,
            "unit_type": ut.code,
            "bed": ut.bed,
            "bath": ut.bath,
            "total_units": ut.total_units,
        }

        metrics = compute_unit_type_metrics(
            identity=identity,
            units_data=units_data,
            comps_avg=comps_avg,
            base_rent=ut.base_rent,
            snapshots=snapshots_data,
            config=config,
            reference_date=reference_date,
            demand_score=demand_score,
        )

        # --- Revenue optimization engine integration ---
        seasonal_context = metrics.get("seasonal_context", {})

        # 1. Elasticity
        elasticity = compute_implied_elasticity(snapshots_data, comp_trends)

        # 2. Optimal price
        optimal = compute_optimal_price(
            metrics, elasticity, seasonal_context, zone_config,
        )

        # 3. Renewal opportunity
        renewal = compute_renewal_opportunity(
            metrics, elasticity, seasonal_context,
            units_data, reference_date, renewal_config,
        )

        # 4. Concession data
        concession_data = _compute_concession_data(units_data)

        # 5. Revenue gap decomposition
        revenue_gap = decompose_revenue_gap(
            metrics, optimal, renewal, concession_data,
        )

        # 6. Revenue efficiency score
        efficiency = compute_revenue_efficiency(
            metrics, optimal, snapshots_data, seasonal_context, zone_config,
        )

        # Add new sections to the metrics dict
        metrics["elasticity"] = elasticity
        metrics["optimal_pricing"] = optimal
        metrics["renewal_opportunity"] = renewal
        metrics["revenue_gap"] = revenue_gap
        metrics["revenue_efficiency"] = efficiency

        all_metrics.append(metrics)

    portfolio = compute_portfolio_metrics(all_metrics)

    return {
        "property_id": str(property_id),
        "property_name": prop.name,
        "reference_date": reference_date.isoformat(),
        "unit_type_metrics": {m["identity"]["unit_type"]: m for m in all_metrics},
        "portfolio_metrics": portfolio,
    }
