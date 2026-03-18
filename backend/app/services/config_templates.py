"""Config templates — pre-built threshold configurations for common strategies."""

TEMPLATES = [
    {
        "id": "stabilized_balanced",
        "name": "Stabilized Balanced",
        "description": "Conservative strategy for stabilized assets targeting 93-95% occupancy with moderate pricing tolerance.",
        "key_values": {"crisis_below": 0.82, "action_below": 0.90, "max_price_spread": 0.06},
        "config": {
            "occupancy_thresholds": {
                "crisis_below": 0.82,
                "action_below": 0.90,
                "concern_below": 0.93,
                "push_above": 0.96,
                "trend_months": 3,
            },
            "exposure_thresholds": {
                "crisis_above": 0.20,
                "action_above": 0.15,
                "caution_above": 0.10,
                "deteriorating_threshold": 0.05,
            },
            "pricing_tolerance": {
                "above_comps_premium_threshold": 0.05,
                "asking_above_predicted_threshold": 0.03,
                "executed_vs_asking_deviation": 0.05,
            },
            "concession_policy": {
                "trigger_dom_days": 21,
                "max_concession_value_months": 1,
                "headline_preservation": True,
            },
            "renewal_policy": {
                "freeze_threshold_occupancy": 0.85,
                "max_increase_pct": 0.05,
                "preferred_increase_pct": 0.03,
            },
            "lease_term_policy": {
                "preferred_term_months": 14,
                "peak_months": [5, 6, 7, 8, 9],
                "short_term_premium_pct": 0.10,
            },
            "experiment_policy": {
                "min_vacant_for_experiment": 3,
                "max_price_spread_pct": 0.06,
                "max_price_spread_dollars": 100,
                "observation_window_days": 14,
                "min_occupancy_for_experiment": 0.75,
            },
            "amenity_benchmarks": {
                "audit_threshold_pct": 0.08,
                "high_amenity_floor": 100,
            },
        },
    },
    {
        "id": "value_add_aggressive",
        "name": "Value-Add Aggressive",
        "description": "Aggressive strategy for value-add repositioning. Wider pricing tolerance, lower crisis thresholds.",
        "key_values": {"crisis_below": 0.72, "action_below": 0.82, "max_price_spread": 0.08},
        "config": {
            "occupancy_thresholds": {
                "crisis_below": 0.72,
                "action_below": 0.82,
                "concern_below": 0.88,
                "push_above": 0.94,
                "trend_months": 3,
            },
            "exposure_thresholds": {
                "crisis_above": 0.30,
                "action_above": 0.22,
                "caution_above": 0.15,
                "deteriorating_threshold": 0.08,
            },
            "pricing_tolerance": {
                "above_comps_premium_threshold": 0.08,
                "asking_above_predicted_threshold": 0.05,
                "executed_vs_asking_deviation": 0.07,
            },
            "concession_policy": {
                "trigger_dom_days": 30,
                "max_concession_value_months": 2,
                "headline_preservation": True,
            },
            "renewal_policy": {
                "freeze_threshold_occupancy": 0.78,
                "max_increase_pct": 0.08,
                "preferred_increase_pct": 0.05,
            },
            "lease_term_policy": {
                "preferred_term_months": 12,
                "peak_months": [5, 6, 7, 8, 9],
                "short_term_premium_pct": 0.15,
            },
            "experiment_policy": {
                "min_vacant_for_experiment": 2,
                "max_price_spread_pct": 0.08,
                "max_price_spread_dollars": 150,
                "observation_window_days": 10,
                "min_occupancy_for_experiment": 0.70,
            },
            "amenity_benchmarks": {
                "audit_threshold_pct": 0.10,
                "high_amenity_floor": 125,
            },
        },
    },
    {
        "id": "lease_up",
        "name": "Lease-Up",
        "description": "Velocity-focused strategy for lease-up properties. Prioritize fill rate over per-unit revenue.",
        "key_values": {"crisis_below": 0.60, "action_below": 0.75, "max_price_spread": 0.10},
        "config": {
            "occupancy_thresholds": {
                "crisis_below": 0.60,
                "action_below": 0.75,
                "concern_below": 0.85,
                "push_above": 0.93,
                "trend_months": 2,
            },
            "exposure_thresholds": {
                "crisis_above": 0.40,
                "action_above": 0.30,
                "caution_above": 0.20,
                "deteriorating_threshold": 0.10,
            },
            "pricing_tolerance": {
                "above_comps_premium_threshold": 0.03,
                "asking_above_predicted_threshold": 0.02,
                "executed_vs_asking_deviation": 0.08,
            },
            "concession_policy": {
                "trigger_dom_days": 14,
                "max_concession_value_months": 2,
                "headline_preservation": False,
            },
            "renewal_policy": {
                "freeze_threshold_occupancy": 0.70,
                "max_increase_pct": 0.03,
                "preferred_increase_pct": 0.02,
            },
            "lease_term_policy": {
                "preferred_term_months": 12,
                "peak_months": [5, 6, 7, 8, 9],
                "short_term_premium_pct": 0.05,
            },
            "experiment_policy": {
                "min_vacant_for_experiment": 3,
                "max_price_spread_pct": 0.10,
                "max_price_spread_dollars": 200,
                "observation_window_days": 7,
                "min_occupancy_for_experiment": 0.60,
            },
            "amenity_benchmarks": {
                "audit_threshold_pct": 0.12,
                "high_amenity_floor": 100,
            },
        },
    },
    {
        "id": "affordable_controlled",
        "name": "Affordable / Rent-Controlled",
        "description": "Conservative strategy for rent-controlled or affordable housing. Minimize vacancy, no comp-based pricing.",
        "key_values": {"crisis_below": 0.97, "action_below": 0.98, "max_price_spread": 0.02},
        "config": {
            "occupancy_thresholds": {
                "crisis_below": 0.97,
                "action_below": 0.98,
                "concern_below": 0.99,
                "push_above": 1.0,
                "trend_months": 3,
            },
            "exposure_thresholds": {
                "crisis_above": 0.05,
                "action_above": 0.03,
                "caution_above": 0.02,
                "deteriorating_threshold": 0.01,
            },
            "pricing_tolerance": {
                "above_comps_premium_threshold": 0.15,
                "asking_above_predicted_threshold": 0.10,
                "executed_vs_asking_deviation": 0.10,
            },
            "concession_policy": {
                "trigger_dom_days": 7,
                "max_concession_value_months": 0.5,
                "headline_preservation": True,
            },
            "renewal_policy": {
                "freeze_threshold_occupancy": 0.95,
                "max_increase_pct": 0.03,
                "preferred_increase_pct": 0.02,
            },
            "lease_term_policy": {
                "preferred_term_months": 12,
                "peak_months": [5, 6, 7, 8, 9],
                "short_term_premium_pct": 0.05,
            },
            "experiment_policy": {
                "min_vacant_for_experiment": 5,
                "max_price_spread_pct": 0.02,
                "max_price_spread_dollars": 25,
                "observation_window_days": 21,
                "min_occupancy_for_experiment": 0.95,
            },
            "amenity_benchmarks": {
                "audit_threshold_pct": 0.05,
                "high_amenity_floor": 50,
            },
        },
    },
]


def get_templates() -> list[dict]:
    """Return all config templates with metadata."""
    return [
        {
            "id": t["id"],
            "name": t["name"],
            "description": t["description"],
            "key_values": t["key_values"],
        }
        for t in TEMPLATES
    ]


def get_template_config(template_id: str) -> dict | None:
    """Return the full config dict for a template."""
    for t in TEMPLATES:
        if t["id"] == template_id:
            return t["config"]
    return None
