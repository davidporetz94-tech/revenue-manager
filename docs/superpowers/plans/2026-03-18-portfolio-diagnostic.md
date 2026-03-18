# Portfolio-Wide Diagnostic Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a portfolio-level pricing diagnostic that aggregates all properties, runs Claude-powered analysis, and presents a superset slideshow.

**Architecture:** Extends the existing per-property diagnostic pattern. New `aggregate_cross_property()` pure function in the engine layer. New `portfolio_diagnostic_service.py` orchestrates multi-property metrics + Claude calls. New slide deck/viz/narrative services follow the same patterns as per-property. One Alembic migration adds `organization_id`, `scope`, and makes `property_id` nullable on `diagnostic_runs`.

**Tech Stack:** Python/FastAPI, SQLAlchemy 2.0, Alembic, React 18, Recharts, Claude API

**Spec:** `docs/superpowers/specs/2026-03-18-portfolio-diagnostic-design.md`

---

## File Map

### New Files
| File | Responsibility |
|------|---------------|
| `backend/alembic/versions/<hash>_add_portfolio_diagnostic_support.py` | Migration: org_id, scope, nullable property_id |
| `backend/app/services/portfolio_diagnostic_service.py` | Portfolio pipeline orchestrator (metrics → flags → Claude → store) |
| `backend/app/services/portfolio_viz_data_service.py` | Deterministic chart data generators for portfolio slides |
| `backend/app/services/portfolio_narrative_service.py` | Claude narrative generation for portfolio slides |
| `backend/app/services/portfolio_slide_deck_service.py` | Assembles portfolio slide deck from diagnosis + metrics |
| `backend/tests/test_portfolio_diagnostic.py` | Tests for aggregation, fallback, slides, endpoints |
| `frontend/src/components/slideshow/slides/PortfolioTitleSlide.jsx` | Portfolio title slide |
| `frontend/src/components/slideshow/slides/PropertyComparisonSlide.jsx` | Side-by-side property table |
| `frontend/src/components/slideshow/slides/PropertyRankingSlide.jsx` | Ranked property health cards |
| `frontend/src/components/slideshow/slides/PortfolioTrendSlide.jsx` | Blended trend lines |

### Modified Files
| File | Changes |
|------|---------|
| `backend/app/engine/aggregator.py` | Add `aggregate_cross_property()` |
| `backend/app/models/diagnostic.py` | Add `organization_id`, `scope` columns; make `property_id` nullable |
| `backend/app/schemas/diagnostic.py` | Make `property_id` optional in response schemas |
| `backend/app/api/diagnostic.py` | Add portfolio endpoints; update existing endpoints for scope-awareness |
| `backend/app/main.py` | No change needed (diagnostic router already registered) |
| `frontend/src/api/client.js` | Add `runPortfolioDiagnostic()`, `getPortfolioDiagnosticHistory()` |
| `frontend/src/components/slideshow/SlideshowViewer.jsx` | Add portfolio slide type mappings |
| `frontend/src/components/dashboard/PortfolioDashboard.jsx` | Add "Run Portfolio Diagnosis" button + state management |

---

## Task 1: Database Migration

**Files:**
- Create: `backend/alembic/versions/<auto>_add_portfolio_diagnostic_support.py`
- Modify: `backend/app/models/diagnostic.py`
- Modify: `backend/app/schemas/diagnostic.py`

- [ ] **Step 1: Update DiagnosticRun model**

In `backend/app/models/diagnostic.py`, add imports and columns:

```python
# Add to imports
from sqlalchemy import CheckConstraint

# Modify DiagnosticRun class:
# Change property_id to nullable:
property_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("properties.id"), nullable=True)

# Add after property_id:
organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False)
scope: Mapped[str] = mapped_column(String(20), nullable=False, server_default="property")

# Add table args after the last column (before any existing __table_args__ or at class level):
__table_args__ = (
    CheckConstraint("scope IN ('property', 'portfolio')", name="ck_diagnostic_runs_scope"),
)
```

- [ ] **Step 2: Update Pydantic schemas**

In `backend/app/schemas/diagnostic.py`, make `property_id` optional:

```python
class DiagnosticRunResponse(BaseModel):
    id: str
    property_id: str | None = None
    scope: str = "property"
    # ... rest unchanged
```

Add `scope` to `DiagnosticRunSummary` as well.

- [ ] **Step 3: Generate and edit Alembic migration**

Run: `cd backend && .venv/bin/alembic revision --autogenerate -m "add portfolio diagnostic support"`

Then edit the generated migration to add the backfill step:

```python
def upgrade():
    # Add organization_id as nullable first
    op.add_column('diagnostic_runs', sa.Column('organization_id', sa.UUID(), nullable=True))
    op.create_foreign_key('fk_diagnostic_runs_org', 'diagnostic_runs', 'organizations', ['organization_id'], ['id'])

    # Backfill organization_id from properties
    op.execute("""
        UPDATE diagnostic_runs dr
        SET organization_id = p.organization_id
        FROM properties p
        WHERE dr.property_id = p.id
    """)

    # Make organization_id NOT NULL
    op.alter_column('diagnostic_runs', 'organization_id', nullable=False)

    # Add scope column
    op.add_column('diagnostic_runs', sa.Column('scope', sa.String(20), nullable=False, server_default='property'))
    op.create_check_constraint('ck_diagnostic_runs_scope', 'diagnostic_runs', "scope IN ('property', 'portfolio')")

    # Make property_id nullable
    op.alter_column('diagnostic_runs', 'property_id', nullable=True)

    # Add index for portfolio history queries
    op.create_index('ix_diagnostic_runs_portfolio', 'diagnostic_runs', ['organization_id', 'scope', 'run_date'])


def downgrade():
    op.drop_index('ix_diagnostic_runs_portfolio')
    # Delete portfolio runs (have NULL property_id)
    op.execute("DELETE FROM diagnostic_runs WHERE scope = 'portfolio'")
    op.alter_column('diagnostic_runs', 'property_id', nullable=False)
    op.drop_constraint('ck_diagnostic_runs_scope', 'diagnostic_runs')
    op.drop_column('diagnostic_runs', 'scope')
    op.drop_constraint('fk_diagnostic_runs_org', 'diagnostic_runs', type_='foreignkey')
    op.drop_column('diagnostic_runs', 'organization_id')
```

- [ ] **Step 4: Apply migration**

Run: `cd backend && .venv/bin/alembic upgrade head`

- [ ] **Step 5: Run existing tests to verify no regressions**

Run: `cd backend && .venv/bin/python -m pytest tests/ -q`
Expected: 203 passed

- [ ] **Step 6: Commit**

```
feat: add portfolio diagnostic support to DiagnosticRun model

Add organization_id, scope columns. Make property_id nullable.
Backfill org_id from properties for existing runs.
```

---

## Task 2: Cross-Property Aggregation Engine Function

**Files:**
- Modify: `backend/app/engine/aggregator.py` (add `aggregate_cross_property()` after line 134)
- Create: `backend/tests/test_portfolio_diagnostic.py`

- [ ] **Step 1: Write failing tests for aggregation**

Create `backend/tests/test_portfolio_diagnostic.py`:

```python
"""Tests for portfolio-wide diagnostic pipeline."""
import pytest
from datetime import date

from app.database import SessionLocal
from app.models.property import Property
from app.models.config import ClientConfig
from app.services.metrics_engine import compute_property_metrics
from app.services.flag_generator import generate_flags
from app.engine.aggregator import aggregate_cross_property

REF_DATE = date(2026, 3, 1)


@pytest.fixture(scope="module")
def db():
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture(scope="module")
def all_property_metrics(db):
    """Compute metrics for all properties — reused across tests."""
    props = db.query(Property).all()
    results = []
    for p in props:
        config = db.query(ClientConfig).filter_by(property_id=p.id, is_active=True).first()
        if not config:
            continue
        config_dict = {
            k: getattr(config, k) or {}
            for k in [
                "occupancy_thresholds", "exposure_thresholds", "pricing_tolerance",
                "concession_policy", "renewal_policy", "lease_term_policy",
                "experiment_policy", "amenity_benchmarks",
            ]
        }
        metrics = compute_property_metrics(db, str(p.id), config_dict, REF_DATE)
        all_flags = {}
        for ut_code, ut_metrics in metrics["unit_type_metrics"].items():
            all_flags[ut_code] = generate_flags(ut_metrics, config_dict)
        results.append({"metrics": metrics, "flags": all_flags})
    return results


class TestCrossPropertyAggregation:
    def test_aggregate_returns_all_properties(self, all_property_metrics):
        agg = aggregate_cross_property(all_property_metrics)
        assert len(agg["properties"]) == 2

    def test_aggregate_total_units(self, all_property_metrics):
        agg = aggregate_cross_property(all_property_metrics)
        assert agg["aggregate"]["total_units"] == 156  # 84 + 72

    def test_aggregate_total_vacant(self, all_property_metrics):
        agg = aggregate_cross_property(all_property_metrics)
        assert agg["aggregate"]["total_vacant"] == 18  # 7 + 11

    def test_aggregate_blended_occupancy(self, all_property_metrics):
        agg = aggregate_cross_property(all_property_metrics)
        expected = (156 - 18) / 156  # ~0.8846
        assert abs(agg["aggregate"]["blended_occupancy"] - expected) < 0.01

    def test_aggregate_daily_burn(self, all_property_metrics):
        agg = aggregate_cross_property(all_property_metrics)
        assert agg["aggregate"]["total_daily_burn"] == 911  # 326 + 585

    def test_aggregate_has_all_flags(self, all_property_metrics):
        agg = aggregate_cross_property(all_property_metrics)
        total_ut = sum(len(flags) for flags in agg["all_flags"].values())
        assert total_ut == 4  # A1, A2, B1, B2

    def test_aggregate_worst_property(self, all_property_metrics):
        agg = aggregate_cross_property(all_property_metrics)
        assert "B" in agg["aggregate"]["worst_property"]  # Property B has higher burn
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && .venv/bin/python -m pytest tests/test_portfolio_diagnostic.py -v`
Expected: FAIL — `ImportError: cannot import name 'aggregate_cross_property'`

- [ ] **Step 3: Implement `aggregate_cross_property()`**

Add to `backend/app/engine/aggregator.py` after `compute_portfolio_metrics()`:

```python
def aggregate_cross_property(all_property_data: list[dict]) -> dict:
    """Aggregate metrics and flags across multiple properties.

    Args:
        all_property_data: list of dicts, each with 'metrics' and 'flags' keys.
            'metrics' is the output of compute_property_metrics().
            'flags' is a dict of unit_type_code -> flag list.

    Returns:
        Dict with 'properties', 'aggregate', and 'all_flags' sections.
    """
    properties = {}
    all_flags = {}
    total_units = 0
    total_vacant = 0
    total_occupied = 0
    total_daily_burn = 0.0
    total_monthly_cost = 0.0
    total_risk_30d = 0.0

    for entry in all_property_data:
        m = entry["metrics"]
        prop_name = m["property_name"]
        prop_code = m.get("property_id", prop_name)
        pm = m.get("portfolio_metrics", {})

        properties[prop_name] = {
            "name": prop_name,
            "property_id": m.get("property_id"),
            "unit_type_metrics": m["unit_type_metrics"],
            "portfolio_metrics": pm,
        }

        all_flags[prop_name] = entry["flags"]

        total_units += pm.get("total_units", 0)
        total_vacant += pm.get("total_vacant", 0)
        total_occupied += total_units - total_vacant

        for ut_m in m["unit_type_metrics"].values():
            total_daily_burn += ut_m["revenue_metrics"]["daily_vacancy_burn"]
            total_monthly_cost += ut_m["revenue_metrics"]["monthly_vacancy_cost"]
            total_risk_30d += ut_m["revenue_metrics"]["revenue_at_risk_30d"]

    blended_occ = total_occupied / total_units if total_units > 0 else 0.0

    # Find worst/best property by daily burn
    prop_burns = []
    for name, pdata in properties.items():
        burn = sum(
            ut["revenue_metrics"]["daily_vacancy_burn"]
            for ut in pdata["unit_type_metrics"].values()
        )
        prop_burns.append((name, burn))

    prop_burns.sort(key=lambda x: x[1], reverse=True)
    worst = prop_burns[0][0] if prop_burns else ""
    best = prop_burns[-1][0] if prop_burns else ""

    return {
        "properties": properties,
        "aggregate": {
            "total_units": total_units,
            "total_occupied": total_occupied,
            "total_vacant": total_vacant,
            "blended_occupancy": blended_occ,
            "total_daily_burn": total_daily_burn,
            "total_monthly_cost": total_monthly_cost,
            "total_revenue_at_risk_30d": total_risk_30d,
            "property_count": len(properties),
            "worst_property": worst,
            "best_property": best,
        },
        "all_flags": all_flags,
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && .venv/bin/python -m pytest tests/test_portfolio_diagnostic.py -v`
Expected: 7 passed

- [ ] **Step 5: Run full suite for regressions**

Run: `cd backend && .venv/bin/python -m pytest tests/ -q`
Expected: 210+ passed

- [ ] **Step 6: Commit**

```
feat: add aggregate_cross_property() engine function

Pure function that aggregates metrics and flags across multiple
properties for portfolio-level diagnostics.
```

---

## Task 3: Portfolio Diagnostic Service

**Files:**
- Create: `backend/app/services/portfolio_diagnostic_service.py`
- Modify: `backend/tests/test_portfolio_diagnostic.py` (add tests)

- [ ] **Step 1: Write failing test for portfolio diagnostic pipeline**

Add to `backend/tests/test_portfolio_diagnostic.py`:

```python
from unittest.mock import MagicMock
from app.services.portfolio_diagnostic_service import run_portfolio_diagnostic


class TestPortfolioDiagnosticPipeline:
    def test_run_completes(self, db):
        """Portfolio diagnostic completes with fallback (no Claude)."""
        mock_claude = MagicMock()
        mock_claude.call_json.side_effect = Exception("no API key")

        user = db.query(User).filter_by(email="demo@example.com").first()
        run = run_portfolio_diagnostic(
            db=db,
            organization_id=str(user.organization_id),
            user_id=str(user.id),
            claude_client=mock_claude,
            reference_date=REF_DATE,
        )
        assert run.status == "COMPLETED"
        assert run.scope == "portfolio"
        assert run.property_id is None
        assert run.organization_id == user.organization_id

    def test_metrics_include_all_properties(self, db):
        mock_claude = MagicMock()
        mock_claude.call_json.side_effect = Exception("no API key")

        user = db.query(User).filter_by(email="demo@example.com").first()
        run = run_portfolio_diagnostic(
            db=db,
            organization_id=str(user.organization_id),
            user_id=str(user.id),
            claude_client=mock_claude,
            reference_date=REF_DATE,
        )
        metrics = run.metrics_json
        assert "properties" in metrics
        assert len(metrics["properties"]) == 2
        assert "aggregate" in metrics

    def test_flags_include_all_unit_types(self, db):
        mock_claude = MagicMock()
        mock_claude.call_json.side_effect = Exception("no API key")

        user = db.query(User).filter_by(email="demo@example.com").first()
        run = run_portfolio_diagnostic(
            db=db,
            organization_id=str(user.organization_id),
            user_id=str(user.id),
            claude_client=mock_claude,
            reference_date=REF_DATE,
        )
        flags = run.flags_json
        total_ut = sum(len(v) for v in flags.values())
        assert total_ut == 4  # A1, A2, B1, B2

    def test_fallback_diagnosis_has_cross_property_assessment(self, db):
        mock_claude = MagicMock()
        mock_claude.call_json.side_effect = Exception("no API key")

        user = db.query(User).filter_by(email="demo@example.com").first()
        run = run_portfolio_diagnostic(
            db=db,
            organization_id=str(user.organization_id),
            user_id=str(user.id),
            claude_client=mock_claude,
            reference_date=REF_DATE,
        )
        diag = run.diagnosis_json
        assert "cross_property_assessment" in diag
        assert "property_assessments" in diag

    def test_audit_log_created(self, db):
        from app.models.diagnostic import AuditLog
        count_before = db.query(AuditLog).filter_by(action="RUN_PORTFOLIO_DIAGNOSTIC").count()

        mock_claude = MagicMock()
        mock_claude.call_json.side_effect = Exception("no API key")
        user = db.query(User).filter_by(email="demo@example.com").first()
        run_portfolio_diagnostic(
            db=db,
            organization_id=str(user.organization_id),
            user_id=str(user.id),
            claude_client=mock_claude,
            reference_date=REF_DATE,
        )
        count_after = db.query(AuditLog).filter_by(action="RUN_PORTFOLIO_DIAGNOSTIC").count()
        assert count_after > count_before
```

Add the User import at the top of the test file:
```python
from app.models.user import User
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/bin/python -m pytest tests/test_portfolio_diagnostic.py::TestPortfolioDiagnosticPipeline -v`
Expected: FAIL — `ImportError: cannot import name 'run_portfolio_diagnostic'`

- [ ] **Step 3: Implement `portfolio_diagnostic_service.py`**

Create `backend/app/services/portfolio_diagnostic_service.py`. Follow the same pattern as `diagnostic_service.py` but:
- Loop through all properties for the organization
- Skip properties without active config
- Call `aggregate_cross_property()` instead of single-property metrics
- Use portfolio-specific Claude prompts with `cross_property_assessment` output schema
- Fallback produces per-property assessments from flag counts + a cross_property_assessment
- Store with `property_id=None`, `scope="portfolio"`, `organization_id` set
- Audit log with `action="RUN_PORTFOLIO_DIAGNOSTIC"`

The service should be ~250 lines following the exact same structure as `diagnostic_service.py`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && .venv/bin/python -m pytest tests/test_portfolio_diagnostic.py -v`
Expected: All passed

- [ ] **Step 5: Commit**

```
feat: add portfolio diagnostic service

Orchestrates multi-property metrics, flags, Claude diagnosis,
and action plan for portfolio-level analysis.
```

---

## Task 4: Portfolio Viz Data, Narrative, and Slide Deck Services

**Files:**
- Create: `backend/app/services/portfolio_viz_data_service.py`
- Create: `backend/app/services/portfolio_narrative_service.py`
- Create: `backend/app/services/portfolio_slide_deck_service.py`
- Modify: `backend/tests/test_portfolio_diagnostic.py` (add slide tests)

- [ ] **Step 1: Write failing test for slide deck assembly**

Add to `backend/tests/test_portfolio_diagnostic.py`:

```python
from app.services.portfolio_slide_deck_service import assemble_portfolio_slide_deck


class TestPortfolioSlideDeck:
    def test_slide_count_two_properties(self, all_property_metrics):
        agg = aggregate_cross_property(all_property_metrics)
        # Minimal diagnosis/action plan for testing
        diagnosis = {
            "property_assessments": [],
            "cross_property_assessment": {"summary": "test", "portfolio_score": 50, "property_rankings": [], "top_3_priorities": []},
        }
        action_plan = {"phases": [
            {"phase_number": 1, "name": "Immediate", "days": "1-3", "actions": []},
            {"phase_number": 2, "name": "Calibrate", "days": "4-14", "actions": []},
            {"phase_number": 3, "name": "Decision", "days": "15-21", "actions": []},
            {"phase_number": 4, "name": "Optimize", "days": "22-30", "actions": []},
        ]}
        deck = assemble_portfolio_slide_deck(
            run_id="test-run",
            metrics=agg,
            diagnosis=diagnosis,
            action_plan=action_plan,
        )
        assert len(deck["slides"]) == 15  # 6 portfolio + 4 property (2x2) + 5 action/summary

    def test_slides_have_required_fields(self, all_property_metrics):
        agg = aggregate_cross_property(all_property_metrics)
        diagnosis = {
            "property_assessments": [],
            "cross_property_assessment": {"summary": "test", "portfolio_score": 50, "property_rankings": [], "top_3_priorities": []},
        }
        action_plan = {"phases": [
            {"phase_number": i, "name": f"Phase {i}", "days": "1-3", "actions": []}
            for i in range(1, 5)
        ]}
        deck = assemble_portfolio_slide_deck(
            run_id="test-run", metrics=agg, diagnosis=diagnosis, action_plan=action_plan,
        )
        for slide in deck["slides"]:
            assert "slide_number" in slide
            assert "slide_type" in slide
            assert "title" in slide
            assert "narrative" in slide

    def test_slide_types_sequential(self, all_property_metrics):
        agg = aggregate_cross_property(all_property_metrics)
        diagnosis = {
            "property_assessments": [],
            "cross_property_assessment": {"summary": "test", "portfolio_score": 50, "property_rankings": [], "top_3_priorities": []},
        }
        action_plan = {"phases": [
            {"phase_number": i, "name": f"Phase {i}", "days": "1-3", "actions": []}
            for i in range(1, 5)
        ]}
        deck = assemble_portfolio_slide_deck(
            run_id="test-run", metrics=agg, diagnosis=diagnosis, action_plan=action_plan,
        )
        numbers = [s["slide_number"] for s in deck["slides"]]
        assert numbers == list(range(1, len(numbers) + 1))
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && .venv/bin/python -m pytest tests/test_portfolio_diagnostic.py::TestPortfolioSlideDeck -v`
Expected: FAIL — ImportError

- [ ] **Step 3: Implement portfolio viz data service**

Create `backend/app/services/portfolio_viz_data_service.py` with these generators (all take the aggregate metrics dict, return Recharts-compatible dicts):

- `generate_portfolio_score_gauge(diagnosis)` — portfolio health score from `cross_property_assessment`
- `generate_portfolio_kpi_cards(aggregate)` — total units, blended occ, daily burn, monthly cost
- `generate_property_comparison_table(properties)` — rows per property with occ, vacant, burn, exposure
- `generate_property_ranking_cards(diagnosis)` — sorted by score from `property_assessments`
- `generate_portfolio_trend_lines(properties)` — blended occ trends from snapshot data
- `generate_portfolio_stacked_bar(properties)` — revenue at risk stacked by property

Follow the same return format as existing `viz_data_service.py`. All values from input dicts, no hardcoded data.

- [ ] **Step 4: Implement portfolio narrative service**

Create `backend/app/services/portfolio_narrative_service.py` following the same pattern as `narrative_service.py`:

- `generate_portfolio_narratives(diagnosis, action_plan, metrics, claude_client)` → `(dict, bool)`
- Two Claude calls: diagnostic narrative + action plan narrative
- Fallback with consulting tone, direct address, specific numbers
- Narrative keys: `slide_2_headline`, `slide_2_findings`, `slide_3_narrative`, `slide_4_narrative`, `slide_5_narrative`, `slide_6_narrative`, `slide_8_narrative`, `slide_9_narrative`, `slide_10_narrative`, `slide_11_narrative`, `slide_12_summary`

- [ ] **Step 5: Implement portfolio slide deck service**

Create `backend/app/services/portfolio_slide_deck_service.py` following `slide_deck_service.py` pattern:

`assemble_portfolio_slide_deck(run_id, metrics, diagnosis, action_plan, claude_client=None)` returns:
```python
{
    "slides": [...],
    "metadata": {
        "generated_at": str,
        "scope": "portfolio",
        "property_count": int,
        "run_id": str,
        "narrative_fallback": bool,
    }
}
```

15 slides for 2 properties (6 portfolio overview + 4 property deep dives + 5 action/summary).

Slide types to use:
- `PORTFOLIO_TITLE`, `PORTFOLIO_EXECUTIVE_SUMMARY`, `PORTFOLIO_SNAPSHOT`, `PROPERTY_RANKING`
- `PORTFOLIO_TRENDS`, `PORTFOLIO_REVENUE_AT_RISK`
- `PROPERTY_DEEP_DIVE` (reused, 2 per property)
- `PORTFOLIO_ACTION_PLAN`, `PORTFOLIO_PHASE_DETAIL`, `PORTFOLIO_DECISION_POINT`
- `PORTFOLIO_INVESTIGATION`, `PORTFOLIO_SUMMARY`

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd backend && .venv/bin/python -m pytest tests/test_portfolio_diagnostic.py -v`
Expected: All passed

- [ ] **Step 7: Commit**

```
feat: add portfolio viz, narrative, and slide deck services

Deterministic chart generators, Claude narrative layer, and
slide deck assembly for portfolio-wide diagnostics.
```

---

## Task 5: API Endpoints

**Files:**
- Modify: `backend/app/api/diagnostic.py`
- Modify: `backend/tests/test_portfolio_diagnostic.py` (add endpoint tests)

- [ ] **Step 1: Write failing test for portfolio endpoint**

Add to `backend/tests/test_portfolio_diagnostic.py`:

```python
from fastapi.testclient import TestClient
from app.main import app


class TestPortfolioEndpoints:
    def test_run_portfolio_diagnostic(self):
        client = TestClient(app)
        resp = client.post("/api/v1/diagnostic/portfolio/run")
        assert resp.status_code == 200
        data = resp.json()
        assert data["scope"] == "portfolio"
        assert data["property_id"] is None

    def test_portfolio_history(self):
        client = TestClient(app)
        # Run one first
        client.post("/api/v1/diagnostic/portfolio/run")
        resp = client.get("/api/v1/diagnostic/portfolio/history")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1
        assert data[0]["scope"] == "portfolio"

    def test_existing_property_diagnostic_still_works(self):
        client = TestClient(app)
        props = client.get("/api/v1/properties").json()
        pid = props[0]["id"]
        resp = client.post(f"/api/v1/properties/{pid}/diagnostic/run")
        assert resp.status_code == 200
        assert resp.json()["property_id"] == pid

    def test_portfolio_slides(self):
        client = TestClient(app)
        run = client.post("/api/v1/diagnostic/portfolio/run").json()
        resp = client.get(f"/api/v1/diagnostic/{run['id']}/slides")
        assert resp.status_code == 200
        slides = resp.json()["slides"]
        assert len(slides) >= 15
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && .venv/bin/python -m pytest tests/test_portfolio_diagnostic.py::TestPortfolioEndpoints -v`
Expected: FAIL — 404 (endpoint doesn't exist)

- [ ] **Step 3: Add portfolio endpoints to `diagnostic.py`**

Add to `backend/app/api/diagnostic.py`:

```python
@router.post("/diagnostic/portfolio/run")
def run_portfolio(db: Session = Depends(get_db)):
    """Run a portfolio-wide diagnostic for all properties."""
    user = _get_demo_user(db)
    from app.services.portfolio_diagnostic_service import run_portfolio_diagnostic
    run = run_portfolio_diagnostic(
        db=db,
        organization_id=str(user.organization_id),
        user_id=str(user.id),
    )
    return _run_to_response(run)


@router.get("/diagnostic/portfolio/history")
def portfolio_history(db: Session = Depends(get_db)):
    """Get portfolio diagnostic run history."""
    user = _get_demo_user(db)
    runs = (
        db.query(DiagnosticRun)
        .filter_by(organization_id=user.organization_id, scope="portfolio")
        .order_by(DiagnosticRun.run_date.desc())
        .limit(20)
        .all()
    )
    return [_run_to_summary(r) for r in runs]
```

Update the existing `get_diagnostic_run` endpoint to handle nullable property_id:
```python
# Change: property_id=str(run.property_id)
# To: property_id=str(run.property_id) if run.property_id else None
```

Update `get_diagnostic_slides` to detect portfolio scope and use portfolio slide deck service:
```python
if run.scope == "portfolio":
    from app.services.portfolio_slide_deck_service import assemble_portfolio_slide_deck
    deck = assemble_portfolio_slide_deck(
        run_id=str(run.id),
        metrics=run.metrics_json,
        diagnosis=run.diagnosis_json,
        action_plan=run.action_plan_json,
    )
else:
    # existing per-property logic
```

Extract helper functions `_run_to_response(run)` and `_run_to_summary(run)` to DRY up the response building.

- [ ] **Step 4: Add `scope` to response helpers**

Make sure the response dict includes `"scope": run.scope` in both response and summary helpers.

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && .venv/bin/python -m pytest tests/test_portfolio_diagnostic.py -v`
Expected: All passed

- [ ] **Step 6: Run full suite**

Run: `cd backend && .venv/bin/python -m pytest tests/ -q`
Expected: 215+ passed (203 existing + 12+ new)

- [ ] **Step 7: Commit**

```
feat: add portfolio diagnostic API endpoints

POST /diagnostic/portfolio/run, GET /diagnostic/portfolio/history.
Updated slides endpoint to handle portfolio scope.
```

---

## Task 6: Frontend — API Client and Slide Components

**Files:**
- Modify: `frontend/src/api/client.js`
- Create: `frontend/src/components/slideshow/slides/PortfolioTitleSlide.jsx`
- Create: `frontend/src/components/slideshow/slides/PropertyComparisonSlide.jsx`
- Create: `frontend/src/components/slideshow/slides/PropertyRankingSlide.jsx`
- Create: `frontend/src/components/slideshow/slides/PortfolioTrendSlide.jsx`
- Modify: `frontend/src/components/slideshow/SlideshowViewer.jsx`

- [ ] **Step 1: Add API client functions**

Add to `frontend/src/api/client.js` before `export default api`:

```javascript
export async function runPortfolioDiagnostic() {
  const res = await api.post('/diagnostic/portfolio/run');
  return res.data;
}

export async function getPortfolioDiagnosticHistory() {
  const res = await api.get('/diagnostic/portfolio/history');
  return res.data;
}
```

- [ ] **Step 2: Create portfolio slide components**

Create 4 new slide components in `frontend/src/components/slideshow/slides/`. Each receives `{ slide }` prop and renders from `slide.viz_data` and `slide.narrative`. Follow the same pattern as existing slides (Tailwind styling, Recharts for charts).

- `PortfolioTitleSlide.jsx` — "Portfolio Pricing Analysis" with date, property count
- `PropertyComparisonSlide.jsx` — table with property rows showing occ, burn, exposure, flags
- `PropertyRankingSlide.jsx` — cards sorted by health score with colored borders
- `PortfolioTrendSlide.jsx` — LineChart with all unit types' occupancy trends overlaid

- [ ] **Step 3: Add portfolio slide types to SlideshowViewer**

In `frontend/src/components/slideshow/SlideshowViewer.jsx`, add imports and mappings:

```javascript
import PortfolioTitleSlide from './slides/PortfolioTitleSlide';
import PropertyComparisonSlide from './slides/PropertyComparisonSlide';
import PropertyRankingSlide from './slides/PropertyRankingSlide';
import PortfolioTrendSlide from './slides/PortfolioTrendSlide';

// Add to SLIDE_COMPONENTS:
PORTFOLIO_TITLE: PortfolioTitleSlide,
PORTFOLIO_EXECUTIVE_SUMMARY: ExecutiveSummarySlide,  // reuse
PORTFOLIO_SNAPSHOT: PropertyComparisonSlide,
PROPERTY_RANKING: PropertyRankingSlide,
PORTFOLIO_TRENDS: PortfolioTrendSlide,
PORTFOLIO_REVENUE_AT_RISK: RevenueAtRiskSlide,  // reuse
PORTFOLIO_ACTION_PLAN: ActionPlanOverviewSlide,  // reuse
PORTFOLIO_PHASE_DETAIL: PhaseDetailSlide,  // reuse
PORTFOLIO_DECISION_POINT: DecisionTreeSlide,  // reuse
PORTFOLIO_INVESTIGATION: InvestigationSlide,  // reuse
PORTFOLIO_SUMMARY: SummarySlide,  // reuse
```

- [ ] **Step 4: Build frontend**

Run: `cd frontend && npx react-scripts build`
Expected: Compiled successfully

- [ ] **Step 5: Commit**

```
feat: add portfolio slide components and API client functions

4 new slide types for portfolio diagnostics. SlideshowViewer
updated with portfolio slide type mappings.
```

---

## Task 7: Frontend — Dashboard Integration

**Files:**
- Modify: `frontend/src/components/dashboard/PortfolioDashboard.jsx`
- Modify: `frontend/src/App.jsx`

- [ ] **Step 1: Add portfolio diagnostic state and button to PortfolioDashboard**

Add state variables:
```javascript
const [portfolioDiagLoading, setPortfolioDiagLoading] = useState(false);
const [portfolioDiagStatus, setPortfolioDiagStatus] = useState('');
const [portfolioError, setPortfolioError] = useState('');
```

Add imports:
```javascript
import { runPortfolioDiagnostic, getDiagnosticRun, getSlides, getPortfolioDiagnosticHistory } from '../../api/client';
```

Add the handler function (same polling pattern as per-property):
```javascript
async function handleRunPortfolioDiagnostic() {
  setPortfolioDiagLoading(true);
  setPortfolioDiagStatus('Computing metrics...');
  setPortfolioError('');
  try {
    const run = await runPortfolioDiagnostic();
    if (run.status === 'COMPLETED') {
      setPortfolioDiagStatus('Loading presentation...');
      const deck = await getSlides(run.id);
      setPortfolioDiagLoading(false);
      onShowPortfolioSlideshow(deck);
      return;
    }
    // ... polling logic same as per-property
  } catch (err) {
    setPortfolioDiagLoading(false);
    setPortfolioError(err.response?.data?.detail || 'Failed to start');
  }
}
```

Add the button to the hero KPI bar (next to the daily burn display):
```jsx
<button
  onClick={handleRunPortfolioDiagnostic}
  disabled={portfolioDiagLoading}
  className="px-5 py-2.5 bg-positive text-white rounded-lg hover:bg-positive/90 text-sm font-semibold transition-all flex items-center gap-2 disabled:opacity-30"
>
  {portfolioDiagLoading ? (
    <>
      <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
      {portfolioDiagStatus}
    </>
  ) : (
    <>Run Portfolio Diagnosis <span className="text-xs opacity-75">~20s</span></>
  )}
</button>
```

- [ ] **Step 2: Wire slideshow display through App.jsx**

Add `onShowPortfolioSlideshow` prop to PortfolioDashboard. In `App.jsx`, handle it the same way as the per-property slideshow — set `slideDeck` and `showSlideshow` state.

- [ ] **Step 3: Build and verify**

Run: `cd frontend && npx react-scripts build`
Expected: Compiled successfully

- [ ] **Step 4: Commit**

```
feat: add portfolio diagnosis button to dashboard

Run Portfolio Diagnosis button in hero KPI bar with loading
state and slideshow display on completion.
```

---

## Task 8: Full Verification

- [ ] **Step 1: Run full backend test suite**

Run: `cd backend && .venv/bin/python -m pytest tests/ -v`
Expected: 215+ passed (203 existing + 12+ new portfolio tests)

- [ ] **Step 2: Build frontend**

Run: `cd frontend && npx react-scripts build`
Expected: Compiled successfully

- [ ] **Step 3: Manual verification**

Start backend and frontend:
```bash
cd backend && .venv/bin/uvicorn app.main:app --reload &
cd frontend && npm start &
```

Verify:
1. Login with demo@example.com / demo123
2. Dashboard shows "Run Portfolio Diagnosis" button in hero bar
3. Click it → loading state with status messages
4. Slideshow opens with ~15 slides
5. First slides are portfolio-level (title, executive summary, comparison)
6. Middle slides are per-property deep dives
7. End slides are action plan and summary
8. Per-property diagnostic still works (click property → Get AI Review)
9. Keyboard navigation works in portfolio slideshow

- [ ] **Step 4: Update progress.md and decisions.md**

- [ ] **Step 5: Commit**

```
feat: portfolio-wide diagnostic complete

Full pipeline: metrics aggregation → Claude diagnosis → 15-slide
superset slideshow. All tests passing, frontend builds clean.
```
