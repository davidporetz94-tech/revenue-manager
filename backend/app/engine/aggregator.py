"""Aggregates all engine modules into a single metrics computation.
Pure function — no DB access. Takes pre-fetched data dicts.
"""
from datetime import date

from app.engine.occupancy import compute_occupancy_metrics
from app.engine.exposure import compute_exposure_metrics
from app.engine.pricing_spread import compute_pricing_spreads
from app.engine.revenue import compute_revenue_metrics
from app.engine.loss_to_lease import compute_ltl_analysis
from app.engine.lease_term import compute_lease_term_metrics
from app.engine.seasonal import compute_seasonal_context
from app.engine.utils import round_half_up, safe_avg, safe_divide


def compute_unit_type_metrics(
    identity: dict,
    units_data: list[dict],
    comps_avg: float,
    base_rent: float,
    snapshots: list[dict],
    config: dict,
    reference_date: date,
    demand_score: float = 0.0,
) -> dict:
    """Compute all metrics for a single unit type.

    Args:
        identity: dict with property, unit_type, bed, bath, total_units.
        units_data: list of unit dicts for this unit type.
        comps_avg: average comp asking rent.
        base_rent: base rent for this unit type.
        snapshots: historical snapshot dicts for trend computation.
        config: client config dict.
        reference_date: current date.
        demand_score: demand score from export/snapshot.

    Returns:
        Complete metrics dict matching the schema.
    """
    occupancy = compute_occupancy_metrics(units_data)
    exposure = compute_exposure_metrics(units_data, reference_date)
    pricing = compute_pricing_spreads(units_data, comps_avg, base_rent, reference_date)
    revenue = compute_revenue_metrics(pricing, occupancy)
    ltl = compute_ltl_analysis(pricing)
    lease_term = compute_lease_term_metrics(units_data, config, reference_date)
    seasonal = compute_seasonal_context(reference_date)

    # Velocity metrics
    dom_values = [u["days_on_market"] for u in units_data
                  if u["status"] in ("VACANT", "ON_NOTICE") and u.get("days_on_market") is not None]
    dv_values = [u["days_vacant"] for u in units_data
                 if u["status"] == "VACANT" and u.get("days_vacant") is not None]

    avg_dom = round(safe_avg(dom_values)) if dom_values else 0
    avg_dv = round(safe_avg(dv_values)) if dv_values else 0

    # Absorption rate: leased units / total available in recent period
    absorption_rate = round_half_up(demand_score, 2)

    velocity = {
        "avg_days_on_market": avg_dom,
        "avg_days_vacant": avg_dv,
        "absorption_rate": absorption_rate,
    }

    # Demand metrics
    demand_vs_occ = round_half_up(demand_score - occupancy["occupancy_rate"], 2)
    demand = {
        "demand_score": demand_score,
        "demand_vs_occupancy_divergence": demand_vs_occ,
    }

    # Trend metrics from snapshots (last 3 months)
    sorted_snaps = sorted(snapshots, key=lambda s: s["snapshot_date"])
    recent_snaps = sorted_snaps[-3:] if len(sorted_snaps) >= 3 else sorted_snaps

    occ_trend = [s["occupancy_rate"] for s in recent_snaps]
    ask_trend = [s.get("avg_asking_rent", 0) for s in recent_snaps]
    comps_trend = [s.get("comps_avg", 0) for s in recent_snaps]

    trend = {
        "occupancy_3mo_trend": occ_trend,
        "asking_rent_3mo_trend": ask_trend,
        "comps_3mo_trend": comps_trend,
    }

    return {
        "identity": identity,
        "occupancy_metrics": occupancy,
        "exposure_metrics": exposure,
        "velocity_metrics": velocity,
        "pricing_spreads": pricing,
        "revenue_metrics": revenue,
        "demand_metrics": demand,
        "lease_term_metrics": lease_term,
        "trend_metrics": trend,
        "seasonal_context": seasonal,
        "ltl_analysis": ltl,
    }


def compute_portfolio_metrics(unit_type_metrics: list[dict]) -> dict:
    """Compute portfolio-level aggregate metrics across all unit types.

    Args:
        unit_type_metrics: list of per-unit-type metrics dicts.

    Returns:
        Dict with portfolio_metrics fields.
    """
    total_units = sum(m["identity"]["total_units"] for m in unit_type_metrics)
    total_vacant = sum(m["occupancy_metrics"]["vacant"] for m in unit_type_metrics)
    total_occupied = sum(m["occupancy_metrics"]["occupied"] for m in unit_type_metrics)

    blended_occ = round_half_up(safe_divide(total_occupied, total_units), 4)

    total_vacancy_cost = sum(m["revenue_metrics"]["monthly_vacancy_cost"] for m in unit_type_metrics)
    total_risk_30d = sum(m["revenue_metrics"]["revenue_at_risk_30d"] for m in unit_type_metrics)

    # Best/worst by occupancy
    sorted_by_occ = sorted(unit_type_metrics, key=lambda m: m["occupancy_metrics"]["occupancy_rate"])
    worst = sorted_by_occ[0]["identity"]["unit_type"] if sorted_by_occ else ""
    best = sorted_by_occ[-1]["identity"]["unit_type"] if sorted_by_occ else ""

    return {
        "total_units": total_units,
        "total_vacant": total_vacant,
        "blended_occupancy": blended_occ,
        "total_monthly_vacancy_cost": total_vacancy_cost,
        "total_revenue_at_risk_30d": total_risk_30d,
        "worst_performing_unit_type": worst,
        "best_performing_unit_type": best,
    }
