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


def aggregate_cross_property(
    property_metrics: dict[str, dict],
) -> dict:
    """Aggregate metrics across multiple properties for portfolio-level reporting.

    Args:
        property_metrics: dict mapping property name/code to its
            compute_property_metrics() output.

    Returns:
        Dict with 'properties' detail, 'aggregate' totals, and 'property_ranking'.
    """
    properties = {}
    total_revenue_gap = 0.0
    total_optimal_revenue = 0.0
    total_current_revenue = 0.0
    total_renewal_opportunity = 0.0
    total_units = 0
    total_vacant = 0
    total_vacancy_cost = 0.0

    for prop_key, prop_data in property_metrics.items():
        ut_metrics = prop_data.get("unit_type_metrics", {})
        pm = prop_data.get("portfolio_metrics", {})

        prop_units = pm.get("total_units", 0)
        prop_vacant = pm.get("total_vacant", 0)
        prop_vacancy_cost = pm.get("total_monthly_vacancy_cost", 0)

        total_units += prop_units
        total_vacant += prop_vacant
        total_vacancy_cost += prop_vacancy_cost

        # Aggregate revenue fields from each unit type
        prop_gap = 0.0
        prop_optimal = 0.0
        prop_current = 0.0
        prop_renewal = 0.0

        for _code, m in ut_metrics.items():
            gap = m.get("revenue_gap", {})
            prop_gap += gap.get("total_gap_monthly", 0)

            opt = m.get("optimal_pricing", {})
            prop_optimal += opt.get("optimal_revenue_monthly", 0)
            prop_current += opt.get("current_revenue_monthly", 0)

            renewal = m.get("renewal_opportunity", {})
            prop_renewal += renewal.get("net_annual_capture", 0)

        # Per-property revenue efficiency
        prop_rev_efficiency = (
            round_half_up(safe_divide(prop_current, prop_optimal) * 100, 1)
            if prop_optimal > 0 else 0.0
        )

        total_revenue_gap += prop_gap
        total_optimal_revenue += prop_optimal
        total_current_revenue += prop_current
        total_renewal_opportunity += prop_renewal

        properties[prop_key] = {
            "property_name": prop_data.get("property_name", prop_key),
            "property_id": prop_data.get("property_id", ""),
            "total_units": prop_units,
            "total_vacant": prop_vacant,
            "total_monthly_vacancy_cost": prop_vacancy_cost,
            "revenue_gap": prop_gap,
            "revenue_efficiency": prop_rev_efficiency,
            "renewal_opportunity": prop_renewal,
            "unit_type_metrics": ut_metrics,
            "portfolio_metrics": pm,
        }

    # Portfolio-level aggregate
    portfolio_rev_efficiency = (
        round_half_up(safe_divide(total_current_revenue, total_optimal_revenue) * 100, 1)
        if total_optimal_revenue > 0 else 0.0
    )

    blended_occ = round_half_up(
        safe_divide(total_units - total_vacant, total_units), 4,
    )

    aggregate = {
        "total_units": total_units,
        "total_vacant": total_vacant,
        "blended_occupancy": blended_occ,
        "total_monthly_vacancy_cost": total_vacancy_cost,
        "total_revenue_gap": total_revenue_gap,
        "total_optimal_revenue": total_optimal_revenue,
        "total_current_revenue": total_current_revenue,
        "portfolio_revenue_efficiency": portfolio_rev_efficiency,
        "total_renewal_opportunity": total_renewal_opportunity,
    }

    # Property ranking: by revenue efficiency ascending (worst first)
    property_ranking = sorted(
        [
            {
                "property_key": pk,
                "property_name": pv["property_name"],
                "revenue_efficiency": pv["revenue_efficiency"],
                "revenue_gap": pv["revenue_gap"],
                "total_vacant": pv["total_vacant"],
                "total_units": pv["total_units"],
                "vacancy_cost": pv["total_monthly_vacancy_cost"],
            }
            for pk, pv in properties.items()
        ],
        key=lambda x: x["revenue_efficiency"],
    )

    return {
        "properties": properties,
        "aggregate": aggregate,
        "property_ranking": property_ranking,
    }
