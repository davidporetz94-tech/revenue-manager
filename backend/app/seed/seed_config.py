"""Seed default client config for both properties."""
import uuid
from datetime import datetime

from sqlalchemy.orm import Session

from app.models.config import ClientConfig

DEFAULT_CONFIG = {
    "occupancy_thresholds": {
        "target_occupancy": 0.94,
        "push_pricing_above": 0.96,
        "concern_below": 0.92,
        "action_below": 0.88,
        "crisis_below": 0.82,
    },
    "exposure_thresholds": {
        "green_below": 0.05,
        "caution_below": 0.10,
        "action_below": 0.15,
        "crisis_above": 0.20,
    },
    "pricing_tolerance": {
        "max_premium_vs_comps_pct": 0.05,
        "max_discount_vs_comps_pct": 0.05,
        "max_asking_vs_predicted_pct": 0.04,
        "acceptable_days_on_market": 21,
        "rent_push_gap_pct": 0.03,
        "underpriced_vs_comps_pct": 0.03,
        "max_upward_experiment_spread_pct": 0.05,
    },
    "concession_policy": {
        "concessions_allowed": True,
        "max_concession_weeks_free": 8,
        "prefer_concession_over_base_cut": True,
        "concession_triggers": {"min_exposure_pct": 0.12, "min_days_on_market": 21},
        "removal_occupancy_threshold": 0.93,
        "removal_exposure_threshold": 0.10,
    },
    "renewal_policy": {
        "max_renewal_increase_pct": 0.08,
        "retention_priority": "BALANCED",
        "turnover_cost_estimate": 1500,
        "never_increase_above_occupancy_threshold": 0.88,
        "freeze_below_occupancy": 0.82,
        "make_ready_cost_estimate": 2500,
        "base_non_renewal_rate": 0.10,
        "increase_sensitivity_factor": 5.0,
    },
    "lease_term_policy": {
        "preferred_term_months": 14,
        "allow_month_to_month": True,
        "mtm_premium_pct": 0.30,
        "short_term_premium_pct": 0.10,
        "target_peak_expiration_pct": 0.60,
    },
    "experiment_policy": {
        "experiments_enabled": True,
        "max_price_spread_pct": 0.06,
        "max_price_spread_dollars": 100,
        "min_vacant_for_experiment": 3,
        "observation_window_days": 14,
        "auto_converge_enabled": False,
        "min_occupancy_for_experiment": 0.75,
    },
    "amenity_benchmarks": {
        "expected_amenity_pct_of_rent": 0.06,
        "amenity_audit_threshold_pct": 0.08,
    },
    "revenue_efficiency_zones": {
        "crisis_below": 0.82,
        "stressed_below": 0.89,
        "balanced_below": 0.94,
        "strong_below": 0.97,
        "market_occupancy": 0.94,
        "crisis_weights": [0.50, 0.10, 0.20, 0.20],
        "stressed_weights": [0.35, 0.25, 0.20, 0.20],
        "balanced_weights": [0.25, 0.30, 0.25, 0.20],
        "strong_weights": [0.10, 0.35, 0.30, 0.25],
        "full_weights": [0.05, 0.35, 0.30, 0.30],
        "seasonal_weight_shift": 0.05,
        "max_turnover_probability": 0.60,
    },
}


def seed_config(db: Session, ids: dict) -> None:
    """Seed one active config per property with all threshold JSONB fields."""
    for prop_key in ("prop_a_id", "prop_b_id"):
        config = ClientConfig(
            id=uuid.uuid4(),
            property_id=ids[prop_key],
            version=1,
            is_active=True,
            investment_thesis="STABILIZED",
            risk_profile="BALANCED",
            hold_period_years=5,
            business_plan_summary=(
                "Stabilized suburban portfolio, 5-year hold, balanced risk tolerance, "
                "targeting 94% occupancy."
            ),
            occupancy_thresholds=DEFAULT_CONFIG["occupancy_thresholds"],
            exposure_thresholds=DEFAULT_CONFIG["exposure_thresholds"],
            pricing_tolerance=DEFAULT_CONFIG["pricing_tolerance"],
            concession_policy=DEFAULT_CONFIG["concession_policy"],
            renewal_policy=DEFAULT_CONFIG["renewal_policy"],
            lease_term_policy=DEFAULT_CONFIG["lease_term_policy"],
            experiment_policy=DEFAULT_CONFIG["experiment_policy"],
            amenity_benchmarks=DEFAULT_CONFIG["amenity_benchmarks"],
            revenue_efficiency_zones=DEFAULT_CONFIG["revenue_efficiency_zones"],
            created_at=datetime.utcnow(),
            created_by=ids["user_id"],
        )
        db.add(config)

    db.flush()
