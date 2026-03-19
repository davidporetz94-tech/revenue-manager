"""Portfolio viz data service — deterministic chart data for portfolio slides.

All generators take portfolio aggregate metrics and return Recharts-compatible JSON.
Never Claude-generated. Never hardcoded.
"""


def generate_portfolio_score_gauge(diagnosis: dict, aggregate: dict | None = None) -> dict:
    """Portfolio-level health score gauge.

    Args:
        diagnosis: portfolio diagnosis JSON.
        aggregate: optional aggregate metrics from cross-property aggregation.

    Returns:
        Recharts-compatible gauge data dict.
    """
    score = 50
    # Prefer aggregate revenue efficiency if available
    if aggregate and aggregate.get("portfolio_revenue_efficiency"):
        score = aggregate["portfolio_revenue_efficiency"]
    elif diagnosis and "cross_property_assessment" in diagnosis:
        score = diagnosis["cross_property_assessment"].get("portfolio_score", 50)
    return {
        "score": score,
        "max": 100,
        "zones": [
            {"min": 0, "max": 39, "color": "#DC2626", "label": "NEEDS ATTENTION"},
            {"min": 40, "max": 54, "color": "#D97706", "label": "UNDERPERFORMING"},
            {"min": 55, "max": 69, "color": "#F59E0B", "label": "ADJUSTING"},
            {"min": 70, "max": 84, "color": "#3B82F6", "label": "OPPORTUNITY"},
            {"min": 85, "max": 100, "color": "#059669", "label": "OPTIMIZED"},
        ],
    }


def generate_portfolio_kpi_cards(aggregate: dict) -> list[dict]:
    """Portfolio-level KPI cards."""
    monthly_vac = aggregate.get("total_monthly_vacancy_cost", 0)
    return [
        {"label": "Total Units", "value": aggregate.get("total_units", 0), "format": "number"},
        {"label": "Blended Occupancy", "value": aggregate.get("blended_occupancy", 0), "format": "percent"},
        {"label": "Total Vacant", "value": aggregate.get("total_vacant", 0), "format": "number"},
        {"label": "Revenue Gap", "value": aggregate.get("total_revenue_gap", 0), "format": "dollar", "suffix": "/mo"},
        {"label": "Vacancy Cost", "value": monthly_vac, "format": "dollar", "suffix": "/mo"},
        {"label": "Revenue Efficiency", "value": aggregate.get("portfolio_revenue_efficiency", 0), "format": "number", "suffix": "%"},
    ]


def generate_property_comparison_table(properties: dict) -> dict:
    """Side-by-side property comparison table with revenue metrics."""
    rows = []
    for name, pdata in properties.items():
        pm = pdata.get("portfolio_metrics", {})
        ut_metrics = pdata.get("unit_type_metrics", {})
        daily_burn = sum(
            ut.get("revenue_metrics", {}).get("daily_vacancy_burn", 0)
            for ut in ut_metrics.values()
        )
        rows.append({
            "property": name,
            "total_units": pm.get("total_units", 0),
            "occupancy": pm.get("blended_occupancy", 0),
            "vacant": pm.get("total_vacant", 0),
            "daily_burn": daily_burn,
            "monthly_cost": daily_burn * 30,
            "unit_types": len(ut_metrics),
            "revenue_gap": pdata.get("revenue_gap", 0),
            "revenue_efficiency": pdata.get("revenue_efficiency", 0),
        })
    rows.sort(key=lambda r: r["daily_burn"], reverse=True)
    return {
        "columns": [
            "property", "total_units", "occupancy",
            "vacant", "daily_burn", "monthly_cost",
            "revenue_gap", "revenue_efficiency",
        ],
        "rows": rows,
    }


def generate_property_ranking_cards(diagnosis: dict, property_ranking: list[dict] | None = None) -> list[dict]:
    """Property ranking cards sorted by score/efficiency.

    Args:
        diagnosis: portfolio diagnosis JSON with cross_property_assessment.
        property_ranking: optional aggregator property_ranking list with revenue data.

    Returns:
        List of ranking card dicts sorted worst-first.
    """
    # Prefer aggregator property_ranking if available (has revenue data)
    if property_ranking:
        cards = []
        for r in property_ranking:
            cards.append({
                "property_name": r.get("property_name", r.get("property_key", "")),
                "score": r.get("revenue_efficiency", 0),
                "total_units": r.get("total_units", 0),
                "total_vacant": r.get("total_vacant", 0),
                "revenue_gap": r.get("revenue_gap", 0),
                "revenue_efficiency": r.get("revenue_efficiency", 0),
                "vacancy_cost": r.get("vacancy_cost", 0),
            })
        return sorted(cards, key=lambda c: c.get("score", 0))

    # Fall back to diagnosis rankings
    if not diagnosis or "cross_property_assessment" not in diagnosis:
        return []
    rankings = diagnosis["cross_property_assessment"].get("property_rankings", [])
    return sorted(rankings, key=lambda r: r.get("score", 0))


def generate_portfolio_trend_lines(properties: dict) -> dict:
    """Blended occupancy trends across all unit types."""
    all_trends: dict[str, list] = {}
    for _name, pdata in properties.items():
        for code, ut_m in pdata["unit_type_metrics"].items():
            trend = ut_m.get("trend_metrics", {}).get("occupancy_trend", [])
            if trend:
                all_trends[code] = trend
    return {"unit_type_trends": all_trends}


def generate_portfolio_stacked_bar(properties: dict) -> list[dict]:
    """Revenue at risk stacked by property, including revenue gap."""
    bars = []
    for name, pdata in properties.items():
        ut_metrics = pdata.get("unit_type_metrics", {})
        daily_burn = sum(
            ut.get("revenue_metrics", {}).get("daily_vacancy_burn", 0)
            for ut in ut_metrics.values()
        )
        monthly = sum(
            ut.get("revenue_metrics", {}).get("monthly_vacancy_cost", 0)
            for ut in ut_metrics.values()
        )
        revenue_gap = pdata.get("revenue_gap", 0)
        color = "#DC2626" if daily_burn > 400 else "#D97706" if daily_burn > 200 else "#F59E0B"
        bars.append({
            "property": name,
            "daily_burn": daily_burn,
            "monthly_cost": monthly,
            "revenue_gap": revenue_gap,
            "color": color,
        })
    bars.sort(key=lambda b: b["daily_burn"], reverse=True)
    return bars


def generate_property_rent_waterfall(
    code: str,
    base_rent: float,
    amenity_price: float,
    predicted_rent: float,
    asking_rent: float,
    comps_rent: float,
) -> list[dict]:
    """Rent waterfall for a unit type using dynamic data (not EXPORT_DATA).

    Mirrors the structure of viz_data_service.generate_rent_waterfall
    but accepts values as args instead of looking them up in EXPORT_DATA.
    """
    return [
        {"label": "Base Rent", "value": base_rent, "type": "base", "color": "#6B7280"},
        {"label": f"+ Amenity (${amenity_price:.0f})", "value": amenity_price, "type": "addition", "color": "#0D9488"},
        {"label": "= Predicted", "value": predicted_rent, "type": "subtotal", "color": "#1F2937"},
        {"label": "Asking", "value": asking_rent, "type": "comparison", "color": "#7C3AED"},
        {"label": "Comps", "value": comps_rent, "type": "comparison", "color": "#2563EB"},
    ]


def generate_property_line_charts(ut_metrics: dict) -> list[dict]:
    """Trend line charts for unit types using dynamic data (not SNAPSHOT_TRENDS).

    Mirrors the structure of viz_data_service.generate_line_charts
    but builds from the trend_metrics in the provided ut_metrics dict.
    """
    charts = []
    for code, m in ut_metrics.items():
        trend = m.get("trend_metrics", {}).get("occupancy_trend", [])
        if trend:
            charts.append({"unit_type": code, "series": trend})
    return charts
