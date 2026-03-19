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


def _format_kpi_value(value: float | int, fmt: str, suffix: str = "") -> str:
    """Format a KPI value for direct display in the frontend."""
    if fmt == "percent":
        if value <= 1:
            return f"{round(value * 100)}%{suffix}"
        return f"{round(value)}%{suffix}"
    if fmt == "dollar":
        return f"${round(value):,}{suffix}"
    return f"{round(value):,}{suffix}"


def _kpi_color(label: str, value: float | int) -> str:
    """Assign a color to a KPI card based on its label and value."""
    if label == "Total Units":
        return "#3B82F6"
    if label == "Blended Occupancy":
        if value >= 0.92:
            return "#059669"
        if value >= 0.85:
            return "#D97706"
        return "#DC2626"
    if label == "Total Vacant":
        if value <= 5:
            return "#059669"
        if value <= 10:
            return "#D97706"
        return "#DC2626"
    if label in ("Revenue Gap", "Vacancy Cost"):
        return "#DC2626"
    if label == "Revenue Efficiency":
        if value >= 70:
            return "#059669"
        if value >= 55:
            return "#D97706"
        return "#DC2626"
    return "#6B7280"


def generate_portfolio_kpi_cards(aggregate: dict) -> list[dict]:
    """Portfolio-level KPI cards with pre-formatted values and colors."""
    monthly_vac = aggregate.get("total_monthly_vacancy_cost", 0)
    rev_eff = aggregate.get("portfolio_revenue_efficiency", 0)
    blended_occ = aggregate.get("blended_occupancy", 0)
    total_vacant = aggregate.get("total_vacant", 0)
    total_rev_gap = aggregate.get("total_revenue_gap", 0)
    total_units = aggregate.get("total_units", 0)

    raw = [
        {"label": "Total Units", "raw": total_units, "format": "number", "suffix": ""},
        {"label": "Blended Occupancy", "raw": blended_occ, "format": "percent", "suffix": ""},
        {"label": "Total Vacant", "raw": total_vacant, "format": "number", "suffix": ""},
        {"label": "Revenue Gap", "raw": total_rev_gap, "format": "dollar", "suffix": "/mo"},
        {"label": "Vacancy Cost", "raw": monthly_vac, "format": "dollar", "suffix": "/mo"},
        {"label": "Revenue Efficiency", "raw": rev_eff, "format": "number", "suffix": "%"},
    ]
    cards = []
    for item in raw:
        cards.append({
            "label": item["label"],
            "value": _format_kpi_value(item["raw"], item["format"], item["suffix"]),
            "color": _kpi_color(item["label"], item["raw"]),
        })
    return cards


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
            tm = ut_m.get("trend_metrics", {})
            trend = tm.get("occupancy_trend", tm.get("occupancy_3mo_trend", []))
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
    """Trend line charts for unit types using dynamic data.

    Builds structured series objects from the trend_metrics dict,
    matching the shape expected by the TrendLineChart frontend component:
    [{unit_type, series: [{month, occupancy, asking, comps}, ...]}]
    """
    month_labels = ["Month 1", "Month 2", "Month 3", "Month 4"]
    charts = []
    for code, m in ut_metrics.items():
        tm = m.get("trend_metrics", {})
        occ_trend = tm.get("occupancy_trend", tm.get("occupancy_3mo_trend", []))
        asking_trend = tm.get("asking_rent_trend", tm.get("asking_rent_3mo_trend", []))
        comps_trend = tm.get("comps_rent_trend", tm.get("comps_3mo_trend", []))
        if not occ_trend:
            continue
        series = []
        for i in range(len(occ_trend)):
            point: dict = {
                "month": month_labels[i] if i < len(month_labels) else f"Month {i + 1}",
                "occupancy": occ_trend[i],
            }
            if i < len(asking_trend):
                point["asking"] = asking_trend[i]
            if i < len(comps_trend):
                point["comps"] = comps_trend[i]
            series.append(point)
        charts.append({"unit_type": code, "series": series})
    return charts


def generate_portfolio_revenue_gap_waterfall(
    stacked_bar: list[dict], aggregate: dict
) -> dict:
    """Revenue gap waterfall for the RevenueGapWaterfall chart component.

    Args:
        stacked_bar: per-property bar data from generate_portfolio_stacked_bar.
        aggregate: portfolio aggregate metrics.

    Returns:
        Dict with 'segments' list for the waterfall chart.
    """
    segments = []
    for bar in stacked_bar:
        segments.append({
            "label": bar["property"],
            "value": bar["revenue_gap"],
            "type": "addition",
            "color": bar["color"],
        })
    total_gap = aggregate.get("total_revenue_gap", 0)
    segments.append({
        "label": "Total Gap",
        "value": total_gap,
        "type": "total",
        "color": "#7C3AED",
    })
    return {"segments": segments}


_PHASE_COLORS = ["#DC2626", "#D97706", "#3B82F6", "#059669"]


def generate_portfolio_timeline(phases: list[dict]) -> list[dict]:
    """Transform action plan phases into TimelineBar format.

    Args:
        phases: list of phase dicts from the action plan.

    Returns:
        List of timeline entries for the TimelineBar component.
    """
    timeline = []
    for i, phase in enumerate(phases):
        actions = phase.get("actions", [])
        experiment_count = sum(
            1
            for a in actions
            if "experiment" in a.get("action_type", "").lower()
            or "mab" in a.get("action_type", "").lower()
        )
        timeline.append({
            "phase": phase.get("phase_number", i + 1),
            "title": phase.get("name", f"Phase {i + 1}"),
            "days": phase.get("days", ""),
            "color": _PHASE_COLORS[i % len(_PHASE_COLORS)],
            "actions_count": len(actions),
            "experiments_count": experiment_count,
        })
    return timeline


_URGENCY_MAP = {
    "EMERGENCY_PRICING": "CRITICAL",
    "CONCESSION_PACKAGE": "HIGH",
    "PRICING_ADJUSTMENT": "HIGH",
    "CONCESSION_STRATEGY": "HIGH",
    "CONDITIONAL_STRATEGY": "HIGH",
}

_BORDER_COLOR_MAP = {
    "CRITICAL": "#DC2626",
    "HIGH": "#D97706",
}


def generate_portfolio_action_cards(actions: list[dict]) -> list[dict]:
    """Transform phase actions into PhaseDetailSlide action_cards format.

    Args:
        actions: list of action dicts from a single phase.

    Returns:
        List of action card dicts for the PhaseDetailSlide component.
    """
    cards = []
    for action in actions:
        action_type = action.get("action_type", "")
        urgency = _URGENCY_MAP.get(action_type, "HIGH")
        cards.append({
            "unit_type": action.get("unit_type", ""),
            "action_type": action_type,
            "title": action.get("description", ""),
            "target": action.get("property", "N/A"),
            "urgency": urgency,
            "border_color": _BORDER_COLOR_MAP.get(urgency, "#6B7280"),
        })
    return cards


def generate_portfolio_flowcharts(phases: list[dict]) -> list[dict]:
    """Generate decision flowcharts from conditional strategy actions.

    Args:
        phases: list of phase dicts from the action plan.

    Returns:
        List of flowchart dicts for the DecisionFlowchart component.
    """
    flowcharts = []
    # Look for CONDITIONAL_STRATEGY actions in phase 3+
    for phase in phases:
        for action in phase.get("actions", []):
            action_type = action.get("action_type", "")
            desc = action.get("description", "")
            if action_type == "CONDITIONAL_STRATEGY" and "IF" in desc:
                unit_type = action.get("unit_type", "")
                prop = action.get("property", "")
                condition = f"{prop} {unit_type}: Day 15 Evaluation"
                outcomes = []
                # Parse IF/ELSE from description
                parts = desc.split("IF ")
                for part in parts[1:]:
                    if ":" in part:
                        cond_text, action_text = part.split(":", 1)
                        action_text = action_text.strip()
                        # Remove trailing IF clause
                        if ". IF " in action_text:
                            action_text = action_text.split(". IF ")[0]
                        is_positive = any(
                            w in cond_text.lower()
                            for w in [">", "above", "over"]
                        )
                        outcomes.append({
                            "label": f"IF {cond_text.strip()}",
                            "action": action_text.strip(),
                            "color": "#059669" if is_positive else "#D97706",
                        })
                if outcomes:
                    flowcharts.append({
                        "condition": condition,
                        "outcomes": outcomes,
                    })

    # If no conditional strategies found, generate a default
    if not flowcharts:
        flowcharts.append({
            "condition": "Day 15: Portfolio Performance Check",
            "outcomes": [
                {
                    "label": "IF occupancy improving across properties",
                    "action": "Maintain current strategy and begin concession wind-down",
                    "color": "#059669",
                },
                {
                    "label": "IF occupancy stagnant or declining",
                    "action": "Escalate pricing reductions and expand concession programs",
                    "color": "#D97706",
                },
            ],
        })

    return flowcharts


def generate_portfolio_investigation_table(
    properties: dict, diagnosis: dict
) -> list[dict]:
    """Generate investigation items from portfolio diagnosis.

    Args:
        properties: per-property metrics.
        diagnosis: portfolio diagnosis JSON.

    Returns:
        List of investigation item dicts for the InvestigationSlide component.
    """
    items = []
    # Standard investigation areas for portfolio diagnostics
    items.append({
        "area": "Pricing Alignment",
        "questions": [
            "Are asking rents aligned with comp market rents?",
            "Which unit types have the largest gap between asking and predicted?",
        ],
        "data_needed": "Comp rent refresh, pricing spread analysis",
        "deadline": "Day 7",
    })
    items.append({
        "area": "Lease Velocity",
        "questions": [
            "What is the average days-on-market by property?",
            "Are concessions accelerating lease-up?",
        ],
        "data_needed": "DOM trends, concession effectiveness data",
        "deadline": "Day 14",
    })
    items.append({
        "area": "Renewal Conversion",
        "questions": [
            "What percentage of expiring leases are renewing?",
            "Is loss-to-lease being captured at renewal?",
        ],
        "data_needed": "Renewal rate tracking, in-place vs market rent gap",
        "deadline": "Day 21",
    })

    # Add property-specific investigation items for underperformers
    for name, pdata in properties.items():
        occ = pdata.get("portfolio_metrics", {}).get("blended_occupancy", 1.0)
        if occ < 0.90:
            items.append({
                "area": f"{name} Occupancy",
                "questions": [
                    f"Why is {name} at {round(occ * 100)}% occupancy?",
                    "Are there local market factors affecting demand?",
                ],
                "data_needed": "Local market survey, traffic/tour data",
                "deadline": "Day 10",
            })

    return items


def generate_portfolio_before_after(aggregate: dict) -> list[dict]:
    """Generate before/after comparison table for summary slide.

    Args:
        aggregate: portfolio aggregate metrics.

    Returns:
        List of before/after row dicts for the SummarySlide component.
    """
    total_vacant = aggregate.get("total_vacant", 0)
    blended_occ = aggregate.get("blended_occupancy", 0)
    monthly_vac = aggregate.get("total_monthly_vacancy_cost", 0)
    rev_gap = aggregate.get("total_revenue_gap", 0)
    rev_eff = aggregate.get("portfolio_revenue_efficiency", 0)

    # Project 30-day improvements (conservative estimates)
    projected_occ = min(blended_occ + 0.03, 0.98)
    projected_vacant = max(total_vacant - 4, 0)
    projected_monthly = monthly_vac * 0.70
    projected_gap = rev_gap * 0.75
    projected_eff = min(rev_eff + 5, 100)

    return [
        {
            "metric": "Blended Occupancy",
            "current": f"{round(blended_occ * 100)}%",
            "projected": f"{round(projected_occ * 100)}%",
            "improvement": f"+{round((projected_occ - blended_occ) * 100)}pp",
            "color": "#059669",
        },
        {
            "metric": "Total Vacant Units",
            "current": str(total_vacant),
            "projected": str(projected_vacant),
            "improvement": f"-{total_vacant - projected_vacant}",
            "color": "#059669",
        },
        {
            "metric": "Monthly Vacancy Cost",
            "current": f"${round(monthly_vac):,}",
            "projected": f"${round(projected_monthly):,}",
            "improvement": f"-${round(monthly_vac - projected_monthly):,}",
            "color": "#059669",
        },
        {
            "metric": "Revenue Gap",
            "current": f"${round(rev_gap):,}/mo",
            "projected": f"${round(projected_gap):,}/mo",
            "improvement": f"-${round(rev_gap - projected_gap):,}",
            "color": "#059669",
        },
        {
            "metric": "Revenue Efficiency",
            "current": f"{round(rev_eff)}%",
            "projected": f"{round(projected_eff)}%",
            "improvement": f"+{round(projected_eff - rev_eff)}pp",
            "color": "#059669",
        },
    ]
