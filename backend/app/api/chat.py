"""Chat API — natural language Q&A over property metrics."""
import json
import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.property import Property
from app.models.config import ClientConfig
from app.models.diagnostic import DiagnosticRun, AuditLog
from app.models.user import User
from app.auth.dependencies import get_current_user, verify_property_access
from app.services.metrics_engine import compute_property_metrics
from app.services.flag_generator import generate_flags
from app.services.claude_client import ClaudeClient, ClaudeAPIError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["chat"])

CHAT_SYSTEM_PROMPT = """You are a senior revenue management analyst. You have access to comprehensive pricing metrics for a multifamily property.

DATA YOU HAVE ACCESS TO (per unit type):
- Occupancy, vacancy, exposure, DOM, days vacant
- Asking, comps, predicted, in-place, executed rents
- Optimal asking rent (revenue-maximizing price from the pricing engine)
- Recommended asking rent (conservative step toward optimal)
- Price direction (INCREASE/DECREASE/HOLD) and confidence level
- Elasticity coefficient and direction (ELASTIC/INELASTIC/UNIT_ELASTIC)
- Revenue gap: total monthly gap and breakdown by lever (vacancy_cost, new_lease_underpricing, renewal_opportunity, concession_drag)
- Revenue efficiency score (0-100) and grade (CRISIS/DISTRESSED/IMBALANCED/OPPORTUNITY/OPTIMIZED)
- Renewal opportunity: upcoming count, recommended increase %, monthly capture
- Daily vacancy burn and monthly vacancy cost
- Flags with severity levels

RULES:
- Answer with specific numbers from the metrics provided. Never invent numbers.
- Use the optimal_asking, elasticity, and gap_components data to answer "what if" pricing questions.
- For price change questions: reference the gap_components to quantify impact by lever.
- For simple questions: 1-3 sentences max.
- For complex questions: use a short lead-in sentence, then bullet points (use "•" not "-"). Never write a wall of text.
- Tone: senior consultant in a quick Slack exchange. Direct, specific, no fluff.
- NEVER compute dollar amounts yourself. Only reference amounts provided in the metrics.
- NEVER use hedging language ("It appears that...", "You may want to consider...").
- Address the operator directly: "Your B1 units..."
- Use active voice: "Cut asking rent" not "Prices should be adjusted"
"""


class ChatRequest(BaseModel):
    """Request body for chat endpoint."""

    message: str
    latest_run_id: str | None = None


class ChatResponse(BaseModel):
    """Response body for chat endpoint."""

    response: str
    sources: list[str]


@router.post("/properties/{property_id}/chat", response_model=ChatResponse)
def chat(
    property_id: str,
    request: ChatRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ChatResponse:
    """Chat with AI about property pricing metrics."""
    prop = verify_property_access(db, property_id, user)

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

    # Compute current metrics
    metrics = compute_property_metrics(db, property_id, config_dict)
    sources = ["metrics"]

    # Generate flags
    all_flags = {}
    for ut_code, ut_metrics in metrics["unit_type_metrics"].items():
        flags = generate_flags(ut_metrics, config_dict)
        all_flags[ut_code] = [
            {"type": f["type"], "severity": f["severity"]} for f in flags
        ]
    sources.append("flags")

    # Get diagnosis if available
    diagnosis_summary = None
    if request.latest_run_id:
        run = db.query(DiagnosticRun).filter_by(
            id=request.latest_run_id
        ).first()
        if run and run.diagnosis_json:
            diagnosis_summary = {
                a["unit_type"]: {
                    "grade": a.get("grade"),
                    "score": a.get("health_score"),
                    "root_cause": a.get("root_cause"),
                }
                for a in run.diagnosis_json.get("unit_type_assessments", [])
            }
            sources.append("diagnosis")

    # Build metrics summary for Claude
    metrics_summary = _build_metrics_summary(metrics)

    total_daily = sum(
        m["revenue_metrics"]["daily_vacancy_burn"]
        for m in metrics["unit_type_metrics"].values()
    )

    user_msg = json.dumps({
        "property_name": prop.name,
        "metrics_by_unit_type": metrics_summary,
        "flags_by_unit_type": all_flags,
        "portfolio_daily_burn": total_daily,
        "portfolio_monthly_cost": total_daily * 30,
        "diagnosis": diagnosis_summary,
        "operator_question": request.message,
    }, indent=2)

    try:
        client = ClaudeClient()
        response_text = client.call_text(
            CHAT_SYSTEM_PROMPT,
            user_msg,
            max_tokens=1000,
            timeout=25.0,
        )
    except ClaudeAPIError as e:
        logger.error("Chat Claude call failed: %s", e)
        response_text = (
            "I'm unable to analyze your data right now. "
            "Please try again in a moment."
        )

    # Audit log
    audit = AuditLog(
        id=uuid.uuid4(),
        organization_id=user.organization_id,
        user_id=user.id,
        action="CHAT_QUERY",
        entity_type="property",
        entity_id=str(property_id),
        details={"question": request.message[:200]},
    )
    db.add(audit)
    db.flush()

    return ChatResponse(response=response_text, sources=sources)


def _build_metrics_summary(metrics: dict) -> dict:
    """Extract a concise metrics summary for the Claude prompt.

    Args:
        metrics: full metrics dict from compute_property_metrics.

    Returns:
        Dict keyed by unit type code with key pricing/occupancy numbers.
    """
    summary = {}
    for code, m in metrics["unit_type_metrics"].items():
        ps = m["pricing_spreads"]
        rev = m["revenue_metrics"]
        occ = m["occupancy_metrics"]
        exp = m["exposure_metrics"]
        vel = m["velocity_metrics"]
        # Revenue optimization sections (all optional, backward-compatible)
        optimal = m.get("optimal_pricing", {})
        elasticity = m.get("elasticity", {})
        gap = m.get("revenue_gap", {})
        renewal = m.get("renewal_opportunity", {})
        efficiency = m.get("revenue_efficiency", {})

        summary[code] = {
            "occupancy": occ["occupancy_rate"],
            "vacant": occ["vacant"],
            "total": m["identity"]["total_units"],
            "exposure": exp["total_exposure_pct"],
            "asking": ps["asking_rent"],
            "comps": ps["comps_rent"],
            "predicted": ps["predicted_rent"],
            "in_place": ps["in_place_rent"],
            "asking_vs_comps": ps["asking_vs_comps_dollars"],
            "loss_to_lease": ps["loss_to_lease_dollars"],
            "daily_burn": rev["daily_vacancy_burn"],
            "monthly_cost": rev["monthly_vacancy_cost"],
            "dom": vel["avg_days_on_market"],
            "days_vacant": vel["avg_days_vacant"],
            # Revenue optimization data
            "optimal_asking": optimal.get("optimal_asking"),
            "recommended_asking": optimal.get("recommended_asking"),
            "price_direction": optimal.get("price_direction"),
            "pricing_confidence": optimal.get("confidence"),
            "elasticity_coefficient": elasticity.get("elasticity_coefficient"),
            "elasticity_direction": elasticity.get("direction"),
            "elasticity_confidence": elasticity.get("confidence"),
            "revenue_gap_monthly": gap.get("total_gap_monthly"),
            "dominant_lever": gap.get("dominant_lever"),
            "gap_components": gap.get("gap_components"),
            "revenue_efficiency_score": efficiency.get("revenue_efficiency_score"),
            "grade": efficiency.get("grade"),
            "upcoming_renewals_90d": renewal.get("upcoming_renewals_90d"),
            "renewal_increase_pct": renewal.get("recommended_increase_pct"),
            "renewal_capture_monthly": renewal.get("net_monthly_capture"),
        }
    return summary
