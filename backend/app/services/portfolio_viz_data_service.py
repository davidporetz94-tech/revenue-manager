"""Portfolio viz data service — deterministic chart data for portfolio slides.

All generators take portfolio aggregate metrics and return Recharts-compatible JSON.
Never Claude-generated. Never hardcoded.
"""


def generate_portfolio_score_gauge(diagnosis: dict) -> dict:
    """Portfolio-level health score gauge."""
    score = 50
    if diagnosis and "cross_property_assessment" in diagnosis:
        score = diagnosis["cross_property_assessment"].get("portfolio_score", 50)
    return {
        "score": score,
        "max": 100,
        "zones": [
            {"min": 0, "max": 39, "color": "#DC2626", "label": "CRITICAL"},
            {"min": 40, "max": 64, "color": "#D97706", "label": "ACTION NEEDED"},
            {"min": 65, "max": 79, "color": "#F59E0B", "label": "WATCH"},
            {"min": 80, "max": 100, "color": "#059669", "label": "HEALTHY"},
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
    """Side-by-side property comparison table."""
    rows = []
    for name, pdata in properties.items():
        pm = pdata["portfolio_metrics"]
        ut_metrics = pdata["unit_type_metrics"]
        daily_burn = sum(
            ut["revenue_metrics"]["daily_vacancy_burn"]
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
        })
    rows.sort(key=lambda r: r["daily_burn"], reverse=True)
    return {
        "columns": [
            "property", "total_units", "occupancy",
            "vacant", "daily_burn", "monthly_cost",
        ],
        "rows": rows,
    }


def generate_property_ranking_cards(diagnosis: dict) -> list[dict]:
    """Property ranking cards sorted by health score."""
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
    """Revenue at risk stacked by property."""
    bars = []
    for name, pdata in properties.items():
        ut_metrics = pdata["unit_type_metrics"]
        daily_burn = sum(
            ut["revenue_metrics"]["daily_vacancy_burn"]
            for ut in ut_metrics.values()
        )
        monthly = sum(
            ut["revenue_metrics"]["monthly_vacancy_cost"]
            for ut in ut_metrics.values()
        )
        color = "#DC2626" if daily_burn > 400 else "#D97706" if daily_burn > 200 else "#F59E0B"
        bars.append({
            "property": name,
            "daily_burn": daily_burn,
            "monthly_cost": monthly,
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
