"""Test diagnostic service — full pipeline with mocked Claude responses.

Tests the deterministic parts (metrics, flags, revenue math, experiment design)
and validates that the pipeline stores results correctly.
"""
import json
from datetime import date
from unittest.mock import MagicMock

import pytest

from app.database import SessionLocal
from app.models.property import Property, UnitType
from app.models.config import ClientConfig
from app.models.diagnostic import DiagnosticRun, AuditLog
from app.services.diagnostic_service import run_diagnostic
from app.services.claude_client import ClaudeClient

REF_DATE = date(2026, 3, 15)


# Realistic mock Claude responses — updated for revenue optimization
MOCK_DIAGNOSIS_B = {
    "unit_type_assessments": [
        {
            "unit_type": "B1",
            "health_score": 25,
            "grade": "CRISIS",
            "score_reasoning": "Revenue efficiency score 25. Dominant vacancy at 79% occupancy, asking $91 above comps in a declining market.",
            "dominant_lever": "FILL",
            "revenue_gap_monthly": 12500,
            "root_cause": "Asking rent $1,525 is $91 above comp average of $1,434 in a declining market. FILL lever dominates: $7,625/mo vacancy cost.",
            "key_findings": ["Revenue gap: $12,500/mo", "Dominant lever: FILL", "$91 above comps", "Negative LTL"],
            "anomalies": ["Executed rent $1,655 far above asking — legacy leases from stronger market"],
            "recommended_actions": [
                {"action_type": "REDUCE_ASKING_RENT", "lever": "REPRICE", "priority": 1, "description": "Cut asking from $1,525 to $1,475", "target_value": 1475, "expected_impact_monthly": 2540, "confidence": "HIGH", "downside_risk": "May lower renewal benchmarks", "reasoning": "CRISIS grade with FILL dominant lever — reduce price to accelerate fill"},
                {"action_type": "OFFER_MOVE_IN_CONCESSION", "lever": "FILL", "priority": 2, "description": "4 weeks free on 2 stalest units", "target_value": None, "expected_impact_monthly": 3050, "confidence": "HIGH", "downside_risk": "Concession drag if market recovers", "reasoning": "Accelerate fill on longest-vacant units"},
                {"action_type": "FREEZE_RENEWAL_INCREASES", "lever": "RENEW", "priority": 3, "description": "Freeze all B1 renewal increases", "target_value": None, "expected_impact_monthly": 0, "confidence": "HIGH", "downside_risk": "Miss renewal revenue capture", "reasoning": "Negative LTL — in-place tenants already pay above market"},
                {"action_type": "AUDIT_AMENITY_PRICING", "lever": "REPRICE", "priority": 4, "description": "Audit $125 amenity premium (8.2% of predicted)", "target_value": None, "expected_impact_monthly": 0, "confidence": "MEDIUM", "downside_risk": "None significant", "reasoning": "Above 8% audit threshold"},
            ],
            "experiment_design": {"recommended": False, "arms": [], "observation_window_days": 14, "convergence_rule": "", "rationale": "Direct action preferred — CRISIS grade, no time for experiments"},
        },
        {
            "unit_type": "B2",
            "health_score": 58,
            "grade": "IMBALANCED",
            "score_reasoning": "Revenue efficiency score 58. Priced at comps but 6 units vacant averaging 28 days — one dimension dragging.",
            "dominant_lever": "FILL",
            "revenue_gap_monthly": 9924,
            "root_cause": "Priced at comps ($1,654 vs $1,662 avg) but not leasing. FILL lever dominates. Non-price factors likely.",
            "key_findings": ["Revenue gap: $9,924/mo", "Dominant lever: FILL", "6 vacant at 28 avg days", "Priced at comps"],
            "anomalies": ["High DOM despite competitive pricing suggests non-price friction"],
            "recommended_actions": [
                {"action_type": "LAUNCH_PRICE_EXPERIMENT", "lever": "REPRICE", "priority": 1, "description": "Three-arm experiment: control $1,654, price test $1,600, concession test $1,654 + 2wk free", "target_value": 1600, "expected_impact_monthly": 3000, "confidence": "MEDIUM", "downside_risk": "Experiment delays lease-up by 14 days", "reasoning": "IMBALANCED grade with medium confidence — experimentation needed"},
                {"action_type": "INVESTIGATE_NON_PRICE_FACTORS", "lever": "FILL", "priority": 2, "description": "Audit tour conversion, unit condition, listing photos", "target_value": None, "expected_impact_monthly": 0, "confidence": "MEDIUM", "downside_risk": "None", "reasoning": "Competitive pricing but high vacancy suggests non-price issues"},
            ],
            "experiment_design": {
                "recommended": True,
                "arms": [
                    {"label": "control", "price": 1654, "units_allocated": 2},
                    {"label": "price_test", "price": 1600, "units_allocated": 2},
                    {"label": "concession_test", "price": 1654, "units_allocated": 2},
                ],
                "observation_window_days": 14,
                "convergence_rule": "Price wins → converge $1,600. Concession wins → extend. No winner → non-price investigation.",
                "rationale": "6 vacant units allow three-arm test. Medium confidence warrants experimentation.",
            },
        },
    ],
    "portfolio_assessment": {
        "summary": "Property B requires immediate attention. B1 is in CRISIS from overpricing. B2 is IMBALANCED — a diagnostic puzzle.",
        "cross_unit_type_risks": ["Both unit types have elevated DOM", "Vacancy concentrated in larger units"],
        "overall_portfolio_score": 42,
        "top_3_priorities": ["B1 price reduction (FILL lever)", "B2 experiment launch (REPRICE lever)", "B1 amenity audit"],
    },
    "further_investigation": [
        {"area": "B2 tour conversion", "reason": "Competitive pricing but high vacancy", "data_needed": "Tour-to-application ratio"},
    ],
}

MOCK_ACTION_PLAN_B = {
    "phases": [
        {
            "phase_number": 1, "name": "Immediate Stabilization", "days": "1-3",
            "actions": [
                {"id": "P1-1", "unit_type": "B1", "action_type": "REDUCE_ASKING_RENT", "description": "Reduce B1 asking from $1,525 to $1,475", "target_value": 1475, "rationale": "CRITICAL flags, $91 above comps", "success_criteria": "At least 1 tour within 72 hours", "contingency": None},
                {"id": "P1-2", "unit_type": "B1", "action_type": "FREEZE_RENEWAL_INCREASES", "description": "Freeze all B1 renewals", "target_value": None, "rationale": "Negative LTL", "success_criteria": "No renewals lost", "contingency": None},
                {"id": "P1-3", "unit_type": "B2", "action_type": "LAUNCH_PRICE_EXPERIMENT", "description": "Three-arm: $1,654 control (2) vs $1,600 test (2) vs $1,654+2wk free (2)", "target_value": 1600, "rationale": "Medium confidence, need data", "success_criteria": "At least 1 application per arm", "contingency": "If no applications in 7 days, add concession to price test arm"},
            ],
        },
        {
            "phase_number": 2, "name": "Calibrate & Optimize", "days": "4-14",
            "actions": [
                {"id": "P2-1", "unit_type": "B1", "action_type": "AUDIT_AMENITY_PRICING", "description": "Review $125 amenity premium", "target_value": None, "rationale": "8.2% above 8% threshold", "success_criteria": "Amenity breakdown documented", "contingency": None},
                {"id": "P2-2", "unit_type": "B2", "action_type": "INVESTIGATE_NON_PRICE_FACTORS", "description": "Audit tour conversion and listing quality", "target_value": None, "rationale": "Priced at comps but not leasing", "success_criteria": "Root cause identified", "contingency": None},
            ],
        },
        {
            "phase_number": 3, "name": "Decision Point", "days": "15-21",
            "actions": [
                {"id": "P3-1", "unit_type": "B1", "action_type": "HOLD_ASKING_RENT", "description": "Evaluate B1 at $1,475", "target_value": 1475, "rationale": "Assess Phase 1 impact", "success_criteria": "2+ units leased", "contingency": "If 0 leased, reduce to $1,434 (comps)"},
                {"id": "P3-2", "unit_type": "B2", "action_type": "CONVERGE_EXPERIMENT", "description": "Evaluate B2 experiment results", "target_value": None, "rationale": "14-day observation complete", "success_criteria": "Clear winner across arms", "contingency": "If no winner, redirect to non-price findings"},
            ],
        },
        {
            "phase_number": 4, "name": "Optimization", "days": "22-30",
            "actions": [
                {"id": "P4-1", "unit_type": "B1", "action_type": "HOLD_ASKING_RENT", "description": "Lock B1 strategy based on Phase 3", "target_value": None, "rationale": "Data-driven decision", "success_criteria": "Occupancy trending up", "contingency": None},
                {"id": "P4-2", "unit_type": "B2", "action_type": "HOLD_ASKING_RENT", "description": "Lock B2 strategy based on experiment", "target_value": None, "rationale": "Experiment converged", "success_criteria": "Vacancy cost declining", "contingency": None},
            ],
        },
    ],
    "decision_points": [
        {
            "day": 15,
            "description": "Mid-month evaluation of B1 price cut and B2 experiment",
            "conditions": [
                {"if_condition": "B1 >= 2 units leased", "then_action": "Hold $1,475"},
                {"if_condition": "B1 0 units leased", "then_action": "Reduce to $1,434 (comps)"},
                {"if_condition": "B2 price arm wins", "then_action": "Converge to $1,600"},
                {"if_condition": "B2 concession arm wins", "then_action": "Extend concession offer"},
                {"if_condition": "B2 no winner", "then_action": "Redirect to non-price investigation"},
            ],
        },
    ],
    "revenue_impact_summary": {
        "current_monthly_vacancy_cost": 17549,
        "projected_monthly_savings": 5000,
        "daily_burn_rate": 585,
        "break_even_timeline_days": 14,
    },
    "experiment_summary": [
        {
            "unit_type": "B2",
            "experiment_type": "three_arm",
            "arms": [
                {"label": "control", "price": 1654, "units": 2},
                {"label": "price_test", "price": 1600, "units": 2},
                {"label": "concession_test", "price": 1654, "units": 2},
            ],
            "observation_days": 14,
            "convergence_rule": "Price wins → converge. Concession wins → extend. No winner → non-price.",
        },
    ],
}


@pytest.fixture(scope="module")
def db():
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture(scope="module")
def mock_claude():
    """Create a mock Claude client that returns realistic responses."""
    client = MagicMock(spec=ClaudeClient)
    client.call_json = MagicMock(side_effect=[
        MOCK_DIAGNOSIS_B,
        MOCK_ACTION_PLAN_B,
    ])
    return client


@pytest.fixture(scope="module")
def diagnostic_run_b(db, mock_claude):
    """Run diagnostic for Property B with mocked Claude."""
    prop = db.query(Property).filter_by(code="PROP-B").first()
    user_id = db.query(Property).filter_by(code="PROP-B").first()
    from app.models.user import User
    user = db.query(User).filter_by(email="demo@example.com").first()

    result = run_diagnostic(
        db=db,
        property_id=str(prop.id),
        user_id=str(user.id),
        organization_id=str(user.organization_id),
        claude_client=mock_claude,
        reference_date=REF_DATE,
    )
    db.commit()
    return result


class TestDiagnosticPipeline:
    def test_run_completes(self, diagnostic_run_b):
        assert diagnostic_run_b.status == "COMPLETED"

    def test_metrics_populated(self, diagnostic_run_b):
        assert diagnostic_run_b.metrics_json is not None
        assert "unit_type_metrics" in diagnostic_run_b.metrics_json
        assert "B1" in diagnostic_run_b.metrics_json["unit_type_metrics"]
        assert "B2" in diagnostic_run_b.metrics_json["unit_type_metrics"]

    def test_flags_populated(self, diagnostic_run_b):
        assert diagnostic_run_b.flags_json is not None
        assert "B1" in diagnostic_run_b.flags_json
        assert "B2" in diagnostic_run_b.flags_json

    def test_b1_flag_count(self, diagnostic_run_b):
        assert len(diagnostic_run_b.flags_json["B1"]) == 12

    def test_b2_flag_count(self, diagnostic_run_b):
        assert len(diagnostic_run_b.flags_json["B2"]) == 7

    def test_diagnosis_populated(self, diagnostic_run_b):
        diag = diagnostic_run_b.diagnosis_json
        assert diag is not None
        assert "unit_type_assessments" in diag
        assert len(diag["unit_type_assessments"]) == 2

    def test_b1_grade_crisis(self, diagnostic_run_b):
        diag = diagnostic_run_b.diagnosis_json
        b1 = [a for a in diag["unit_type_assessments"] if a["unit_type"] == "B1"][0]
        assert b1["grade"] == "CRISIS"
        assert b1["health_score"] < 40

    def test_b2_grade_imbalanced(self, diagnostic_run_b):
        diag = diagnostic_run_b.diagnosis_json
        b2 = [a for a in diag["unit_type_assessments"] if a["unit_type"] == "B2"][0]
        assert b2["grade"] == "IMBALANCED"
        assert 50 <= b2["health_score"] <= 69

    def test_b1_has_dominant_lever(self, diagnostic_run_b):
        diag = diagnostic_run_b.diagnosis_json
        b1 = [a for a in diag["unit_type_assessments"] if a["unit_type"] == "B1"][0]
        assert "dominant_lever" in b1
        assert b1["dominant_lever"] in ("FILL", "REPRICE", "RENEW", "DE_CONCESSION")

    def test_b1_has_revenue_gap(self, diagnostic_run_b):
        diag = diagnostic_run_b.diagnosis_json
        b1 = [a for a in diag["unit_type_assessments"] if a["unit_type"] == "B1"][0]
        assert "revenue_gap_monthly" in b1
        assert b1["revenue_gap_monthly"] > 0

    def test_action_plan_populated(self, diagnostic_run_b):
        plan = diagnostic_run_b.action_plan_json
        assert plan is not None
        assert "phases" in plan

    def test_four_phases(self, diagnostic_run_b):
        plan = diagnostic_run_b.action_plan_json
        assert len(plan["phases"]) == 4

    def test_phase1_has_b1_price_cut(self, diagnostic_run_b):
        plan = diagnostic_run_b.action_plan_json
        phase1 = plan["phases"][0]
        b1_actions = [a for a in phase1["actions"] if a["unit_type"] == "B1"]
        action_types = {a["action_type"] for a in b1_actions}
        assert "REDUCE_ASKING_RENT" in action_types or "OFFER_MOVE_IN_CONCESSION" in action_types

    def test_phase1_has_b2_experiment(self, diagnostic_run_b):
        plan = diagnostic_run_b.action_plan_json
        phase1 = plan["phases"][0]
        b2_actions = [a for a in phase1["actions"] if a["unit_type"] == "B2"]
        action_types = {a["action_type"] for a in b2_actions}
        assert "LAUNCH_PRICE_EXPERIMENT" in action_types

    def test_decision_point_exists(self, diagnostic_run_b):
        plan = diagnostic_run_b.action_plan_json
        assert len(plan["decision_points"]) >= 1
        dp = plan["decision_points"][0]
        assert dp["day"] == 15

    def test_timing_recorded(self, diagnostic_run_b):
        assert diagnostic_run_b.metrics_compute_ms is not None
        assert diagnostic_run_b.total_ms is not None

    def test_audit_log_entry(self, db, diagnostic_run_b):
        audit = db.query(AuditLog).filter_by(
            entity_type="diagnostic_run",
            entity_id=str(diagnostic_run_b.id),
        ).first()
        assert audit is not None
        assert audit.action == "RUN_DIAGNOSTIC"


class TestExperimentDesign:
    """Test the deterministic experiment design logic."""

    def test_b2_experiment_eligibility(self, diagnostic_run_b):
        """B2 has 6 vacant >= 3 min, 0.88 occ >= 0.75 → eligible."""
        metrics = diagnostic_run_b.metrics_json
        b2 = metrics["unit_type_metrics"]["B2"]
        assert b2["occupancy_metrics"]["vacant"] == 6
        assert b2["occupancy_metrics"]["occupancy_rate"] == 0.88

    def test_b1_direct_action_preferred(self, diagnostic_run_b):
        """B1 has CRITICAL flags → direct action preferred over experiment."""
        diag = diagnostic_run_b.diagnosis_json
        b1 = [a for a in diag["unit_type_assessments"] if a["unit_type"] == "B1"][0]
        assert b1["experiment_design"]["recommended"] is False

    def test_b2_three_arm(self, diagnostic_run_b):
        """B2 with 6 vacant + CONCESSION_TRIGGER → three-arm experiment."""
        diag = diagnostic_run_b.diagnosis_json
        b2 = [a for a in diag["unit_type_assessments"] if a["unit_type"] == "B2"][0]
        assert b2["experiment_design"]["recommended"] is True
        assert len(b2["experiment_design"]["arms"]) >= 2


class TestFallbackDiagnosis:
    def test_fallback_on_claude_failure(self, db):
        """When Claude fails, fallback produces structured diagnosis with revenue efficiency data."""
        from app.services.diagnostic_service import _fallback_diagnosis
        from app.services.metrics_engine import compute_property_metrics
        from app.services.flag_generator import generate_flags

        prop = db.query(Property).filter_by(code="PROP-B").first()
        config = db.query(ClientConfig).filter_by(property_id=prop.id, is_active=True).first()
        config_dict = {k: getattr(config, k) or {} for k in [
            "occupancy_thresholds", "exposure_thresholds", "pricing_tolerance",
            "concession_policy", "renewal_policy", "lease_term_policy",
            "experiment_policy", "amenity_benchmarks", "revenue_efficiency_zones",
        ]}
        metrics = compute_property_metrics(db, str(prop.id), config_dict, REF_DATE)
        all_flags = {code: generate_flags(m, config_dict) for code, m in metrics["unit_type_metrics"].items()}

        fallback = _fallback_diagnosis(metrics, all_flags)
        assert "unit_type_assessments" in fallback
        assert len(fallback["unit_type_assessments"]) == 2

        b1 = [a for a in fallback["unit_type_assessments"] if a["unit_type"] == "B1"][0]
        # B1 should be CRISIS or DISTRESSED based on revenue efficiency
        assert b1["grade"] in ("CRISIS", "DISTRESSED")
        assert b1["health_score"] < 55

    def test_fallback_has_revenue_efficiency_grades(self, db):
        """Fallback uses pre-computed revenue efficiency grades, not flag counts."""
        from app.services.diagnostic_service import _fallback_diagnosis
        from app.services.metrics_engine import compute_property_metrics
        from app.services.flag_generator import generate_flags

        prop = db.query(Property).filter_by(code="PROP-B").first()
        config = db.query(ClientConfig).filter_by(property_id=prop.id, is_active=True).first()
        config_dict = {k: getattr(config, k) or {} for k in [
            "occupancy_thresholds", "exposure_thresholds", "pricing_tolerance",
            "concession_policy", "renewal_policy", "lease_term_policy",
            "experiment_policy", "amenity_benchmarks", "revenue_efficiency_zones",
        ]}
        metrics = compute_property_metrics(db, str(prop.id), config_dict, REF_DATE)
        all_flags = {code: generate_flags(m, config_dict) for code, m in metrics["unit_type_metrics"].items()}

        fallback = _fallback_diagnosis(metrics, all_flags)

        for a in fallback["unit_type_assessments"]:
            assert a["grade"] in ("CRISIS", "DISTRESSED", "IMBALANCED", "OPPORTUNITY", "OPTIMIZED")
            assert "dominant_lever" in a
            assert a["dominant_lever"] in ("FILL", "REPRICE", "RENEW", "DE_CONCESSION")
            assert "revenue_gap_monthly" in a
            assert isinstance(a["revenue_gap_monthly"], (int, float))

    def test_fallback_has_recommended_actions(self, db):
        """Fallback builds recommended actions from gap components."""
        from app.services.diagnostic_service import _fallback_diagnosis
        from app.services.metrics_engine import compute_property_metrics
        from app.services.flag_generator import generate_flags

        prop = db.query(Property).filter_by(code="PROP-B").first()
        config = db.query(ClientConfig).filter_by(property_id=prop.id, is_active=True).first()
        config_dict = {k: getattr(config, k) or {} for k in [
            "occupancy_thresholds", "exposure_thresholds", "pricing_tolerance",
            "concession_policy", "renewal_policy", "lease_term_policy",
            "experiment_policy", "amenity_benchmarks", "revenue_efficiency_zones",
        ]}
        metrics = compute_property_metrics(db, str(prop.id), config_dict, REF_DATE)
        all_flags = {code: generate_flags(m, config_dict) for code, m in metrics["unit_type_metrics"].items()}

        fallback = _fallback_diagnosis(metrics, all_flags)

        # At least one unit type should have recommended actions
        all_actions = [a for assess in fallback["unit_type_assessments"] for a in assess["recommended_actions"]]
        assert len(all_actions) > 0

        # Every action should have the new fields
        for action in all_actions:
            assert "lever" in action
            assert action["lever"] in ("FILL", "REPRICE", "RENEW", "DE_CONCESSION")
            assert "expected_impact_monthly" in action
            assert "confidence" in action
            assert "downside_risk" in action

    def test_fallback_sorted_by_gap(self, db):
        """Fallback sorts unit types by revenue gap descending."""
        from app.services.diagnostic_service import _fallback_diagnosis
        from app.services.metrics_engine import compute_property_metrics
        from app.services.flag_generator import generate_flags

        prop = db.query(Property).filter_by(code="PROP-B").first()
        config = db.query(ClientConfig).filter_by(property_id=prop.id, is_active=True).first()
        config_dict = {k: getattr(config, k) or {} for k in [
            "occupancy_thresholds", "exposure_thresholds", "pricing_tolerance",
            "concession_policy", "renewal_policy", "lease_term_policy",
            "experiment_policy", "amenity_benchmarks", "revenue_efficiency_zones",
        ]}
        metrics = compute_property_metrics(db, str(prop.id), config_dict, REF_DATE)
        all_flags = {code: generate_flags(m, config_dict) for code, m in metrics["unit_type_metrics"].items()}

        fallback = _fallback_diagnosis(metrics, all_flags)
        gaps = [a["revenue_gap_monthly"] for a in fallback["unit_type_assessments"]]
        assert gaps == sorted(gaps, reverse=True)

    def test_fallback_portfolio_score(self, db):
        """Fallback computes weighted portfolio score from unit type scores."""
        from app.services.diagnostic_service import _fallback_diagnosis
        from app.services.metrics_engine import compute_property_metrics
        from app.services.flag_generator import generate_flags

        prop = db.query(Property).filter_by(code="PROP-B").first()
        config = db.query(ClientConfig).filter_by(property_id=prop.id, is_active=True).first()
        config_dict = {k: getattr(config, k) or {} for k in [
            "occupancy_thresholds", "exposure_thresholds", "pricing_tolerance",
            "concession_policy", "renewal_policy", "lease_term_policy",
            "experiment_policy", "amenity_benchmarks", "revenue_efficiency_zones",
        ]}
        metrics = compute_property_metrics(db, str(prop.id), config_dict, REF_DATE)
        all_flags = {code: generate_flags(m, config_dict) for code, m in metrics["unit_type_metrics"].items()}

        fallback = _fallback_diagnosis(metrics, all_flags)
        portfolio_score = fallback["portfolio_assessment"]["overall_portfolio_score"]
        assert 0 <= portfolio_score <= 100
        # Should have top priorities
        assert len(fallback["portfolio_assessment"]["top_3_priorities"]) > 0

    def test_fallback_new_action_types(self, db):
        """Fallback may include new action types from the expanded taxonomy."""
        from app.services.diagnostic_service import _fallback_diagnosis
        from app.services.metrics_engine import compute_property_metrics
        from app.services.flag_generator import generate_flags

        prop = db.query(Property).filter_by(code="PROP-A").first()
        config = db.query(ClientConfig).filter_by(property_id=prop.id, is_active=True).first()
        config_dict = {k: getattr(config, k) or {} for k in [
            "occupancy_thresholds", "exposure_thresholds", "pricing_tolerance",
            "concession_policy", "renewal_policy", "lease_term_policy",
            "experiment_policy", "amenity_benchmarks", "revenue_efficiency_zones",
        ]}
        metrics = compute_property_metrics(db, str(prop.id), config_dict, REF_DATE)
        all_flags = {code: generate_flags(m, config_dict) for code, m in metrics["unit_type_metrics"].items()}

        fallback = _fallback_diagnosis(metrics, all_flags)

        # All action types should be from the taxonomy
        valid_types = {
            "REDUCE_ASKING_RENT", "INCREASE_ASKING_RENT", "HOLD_ASKING_RENT",
            "TEST_HIGHER_ASKING", "TEST_TERM_PREMIUM",
            "OFFER_MOVE_IN_CONCESSION", "OFFER_LOOK_AND_LEASE", "REMOVE_CONCESSION",
            "LAUNCH_PRICE_EXPERIMENT", "LAUNCH_CONCESSION_EXPERIMENT", "CONVERGE_EXPERIMENT",
            "IMPLEMENT_RENEWAL_INCREASE", "SET_RENEWAL_INCREASE", "FREEZE_RENEWAL_INCREASES",
            "ADJUST_PREFERRED_LEASE_TERM", "OFFER_SHORT_TERM_PREMIUM",
            "AUDIT_AMENITY_PRICING", "INVESTIGATE_NON_PRICE_FACTORS",
        }
        for assess in fallback["unit_type_assessments"]:
            for action in assess["recommended_actions"]:
                assert action["action_type"] in valid_types, f"Unknown action type: {action['action_type']}"
