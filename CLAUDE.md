# CLAUDE.md — Multifamily Revenue Management Platform

## Project Overview

A full-stack multifamily revenue management (RM) platform that ingests rent roll data, runs a pricing health diagnostic, and outputs an AI-generated 30-day action plan as an in-browser interactive slideshow.

**Dual purpose:**
1. Portfolio piece / case study submission for EliseAI's Revenue Manager Practical — answers "Are we priced correctly for new leases?" and "What should we do in the next 30 days?"
2. Production-deployable SaaS product — architected for real clients, real regulatory compliance, post-DOJ-settlement era

**Core philosophy:** The revenue management engine is the center of gravity. Features (auth, slideshow, etc.) sit on top of the RM methodology, not the other way around.

---

## Mandatory Living Documents (MUST UPDATE — NO EXCEPTIONS)

Three files MUST be kept current throughout all work. Failing to update these is a build violation.

| File | Update When | What to Write |
|------|------------|---------------|
| **`progress.md`** | After EVERY action — every file created, every test run, every bug fix, every convergence loop iteration | Timestamped entry with: what was done, files changed, test results, blockers, next step |
| **`decisions.md`** | Before implementing ANY decision — any choice between options, any deviation from spec, any ambiguous interpretation, any tradeoff | Numbered entry (DEC-NNN) with: context, options considered, decision, rationale, impact, reversibility |
| **`agents.md`** | Reference before starting any task — adopt the most relevant agent persona | No updates needed (read-only reference), but you may add new agents if a gap is discovered |

### Update Protocol

```
BEFORE starting any task:
  1. Read agents.md → adopt the right persona
  2. If the task requires a decision → log it in decisions.md FIRST

AFTER completing any task:
  3. Update progress.md with what you did
  4. If you made decisions during the task → verify they're all in decisions.md
```

**Why this matters:** These files create an audit trail that allows anyone (including a future Claude Code session) to understand what was done, why, and what the current state is. Without them, context is lost between sessions and mistakes get repeated.

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React 18+ with Tailwind CSS |
| Backend | Python / FastAPI |
| Database | PostgreSQL 15+ with SQLAlchemy 2.0 ORM (mapped_column style) |
| AI Engine | Hybrid — deterministic rules-based engine + Claude API (claude-sonnet-4-20250514) |
| Migrations | Alembic (reversible) |
| Charts | Recharts |
| Auth | JWT (bcrypt + PyJWT, 24h expiry) |
| Validation | Pydantic v2 |

---

## Key Commands

```bash
# Database
alembic upgrade head                          # Apply all migrations
alembic downgrade -1                          # Rollback last migration
python -m app.seed.seed_all                   # Seed all dummy data

# Backend
cd backend && uvicorn app.main:app --reload   # Start FastAPI dev server
cd backend && pytest                          # Run all backend tests
cd backend && pytest tests/test_reconciliation.py  # Verify data reconciliation (56+ checks)

# Frontend
cd frontend && npm install                    # Install dependencies
cd frontend && npm start                      # Start React dev server

# Docker
docker-compose up --build                     # Full stack

# Specific test suites
pytest tests/test_reconciliation.py           # Data integrity (Spec 01)
pytest tests/test_metrics_engine.py           # Pricing engine (Spec 02)
pytest tests/test_flag_generator.py           # Flag generation (Spec 02)
pytest tests/test_diagnostic_service.py       # Diagnostic pipeline (Spec 03)
pytest tests/test_narrative_service.py        # Narrative layer (Spec 04)
pytest tests/test_viz_data_service.py         # Visualization data (Spec 04)
```

---

## Architecture Summary

### Three-Layer Engine

```
Layer 1: Deterministic Metrics Engine (Python — pure computation, no judgment)
    │  Computes ~30 metrics per unit type from rent roll + export data
    │  Outputs structured JSON. No thresholds, no scores — just facts.
    ▼
Layer 1.5: Flag Generator (Python — compares metrics against client-configured thresholds)
    │  Takes metrics JSON + client_config JSON → structured flags list
    │  Each flag: {type, value, threshold, severity}
    ▼
Layer 3: Intelligent Diagnosis (Claude API)
    │  Receives metrics + flags + config + context
    │  Produces scored diagnoses, root causes, experiments, action recommendations
    ▼
Narrative Layer (Claude API)
    │  2 Claude calls: diagnostic narrative + action plan narrative
    │  Viz data generated DETERMINISTICALLY from metrics (never by Claude)
    ▼
Slideshow UI (React + Recharts)
    12-slide interactive presentation
```

### Engine Isolation Rule
Engine modules (`app/engine/`) are **PURE FUNCTIONS** — no database access, no side effects. Services query the DB, pass data to the engine. This is a hard architectural boundary.

### Data Flow
```
Database → Service Layer → Engine (pure computation) → Flag Generator → Claude API → Narrative → Slide Deck JSON → React Frontend
```

---

## Project Structure

```
multifamily-rm/
├── CLAUDE.md                          # This file
├── progress.md                        # Running work log (MUST UPDATE after every action)
├── decisions.md                       # Decision log (MUST UPDATE before every decision)
├── agents.md                          # Agent personas (read before every task)
├── SPECS/                             # 6 spec files (execution blueprints)
├── holdout-scenarios/                 # 6 scenario files (validation tests)
├── EXEMPLARS/                         # Gene-transfusion references
├── WORKLOG.md                         # Progress tracking
├── backend/
│   ├── alembic/                       # Database migrations
│   ├── app/
│   │   ├── main.py                    # FastAPI app entry point
│   │   ├── config.py                  # Environment config
│   │   ├── database.py                # SQLAlchemy engine + session
│   │   ├── models/                    # ORM models (pure data containers)
│   │   │   ├── user.py                # organizations, users
│   │   │   ├── property.py            # properties, unit_types, units
│   │   │   ├── comp.py                # comp_properties, comp_unit_types, comp_rents
│   │   │   ├── config.py              # client_configs
│   │   │   ├── snapshot.py            # historical_snapshots
│   │   │   ├── diagnostic.py          # diagnostic_runs, audit_log
│   │   │   └── experiment.py          # experiments, experiment_assignments
│   │   ├── schemas/                   # Pydantic request/response models
│   │   ├── api/                       # Route handlers (28 endpoints)
│   │   │   ├── auth.py                # POST /auth/login, /register, GET /me
│   │   │   ├── properties.py          # GET /properties, /{id}, /{id}/units, /{id}/export
│   │   │   ├── config.py              # GET/POST config, /generate, /history
│   │   │   ├── diagnostic.py          # POST /run, GET /{run_id}, /slides, /history
│   │   │   ├── comps.py               # GET comps, trends, POST suggest, refresh
│   │   │   ├── experiments.py         # GET, POST approve/cancel, PUT assignments, evaluate
│   │   │   ├── snapshots.py           # GET snapshots
│   │   │   └── audit.py               # GET audit log
│   │   ├── services/                  # Business logic orchestration
│   │   │   ├── metrics_engine.py      # Orchestrates Layer 1 computation
│   │   │   ├── flag_generator.py      # Layer 1.5 flag generation
│   │   │   ├── diagnostic_service.py  # Full pipeline orchestration
│   │   │   ├── action_plan_service.py # 30-day action plan generation
│   │   │   ├── narrative_service.py   # Claude narrative generation
│   │   │   ├── viz_data_service.py    # Deterministic chart data generation
│   │   │   ├── claude_client.py       # Claude API wrapper
│   │   │   ├── config_generator.py    # Business plan → config via Claude
│   │   │   └── experiment_service.py  # MAB experiment lifecycle
│   │   ├── engine/                    # PURE FUNCTIONS — no DB access
│   │   │   ├── occupancy.py
│   │   │   ├── exposure.py
│   │   │   ├── pricing_spread.py
│   │   │   ├── revenue.py
│   │   │   ├── loss_to_lease.py
│   │   │   ├── lease_term.py
│   │   │   ├── seasonal.py
│   │   │   └── aggregator.py
│   │   ├── auth/                      # JWT utilities
│   │   │   ├── jwt.py
│   │   │   ├── dependencies.py
│   │   │   └── password.py
│   │   └── seed/                      # Dummy data generation
│   │       ├── seed_all.py
│   │       ├── seed_properties.py
│   │       ├── seed_units.py
│   │       ├── seed_comps.py
│   │       ├── seed_snapshots.py
│   │       └── seed_config.py
│   ├── tests/
│   └── requirements.txt
├── frontend/
│   └── src/
│       ├── api/                       # API client functions
│       ├── auth/                      # Auth context + hooks
│       ├── utils/
│       └── components/
│           ├── layout/                # Sidebar, Header, Shell
│           ├── dashboard/             # Property list, KPI cards
│           ├── config/                # Config editor, sliders, preview
│           └── slideshow/             # THE primary deliverable
│               ├── SlideshowViewer.jsx
│               ├── slides/            # 11 slide components (Title thru Summary)
│               └── charts/            # 8 chart components (ScoreGauge thru BeforeAfter)
└── docker-compose.yml
```

---

## The EliseAI Pricing Export (Ground Truth)

Every number in the system must trace back to these exact values:

| Property | Unit Type | Bed | Bath | Total | Occupied | On Notice | Available | Vacant | Occ | DOM | DV | Demand | Tot Exp% | Vac Exp% | 30d% | 60d% | 90d% | Base | Amenity | In-Place | Executed | Asking | Predicted | Comps |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| A | A1 | 1 | 1 | 48 | 46 | 1 | 3 | 2 | 0.96 | 24 | 17 | 0.63 | 0.06 | 0.04 | 0.06 | 0.06 | 0.06 | 1240 | 89 | 1269 | 1324 | 1365 | 1329 | 1353 |
| A | A2 | 2 | 1 | 36 | 31 | 1 | 6 | 5 | 0.86 | 22 | 16 | 0.63 | 0.17 | 0.14 | 0.17 | 0.17 | 0.17 | 1275 | 83 | 1304 | 1392 | 1411 | 1358 | 1396 |
| B | B1 | 1 | 1 | 24 | 19 | 1 | 6 | 5 | 0.79 | 25 | 20 | 0.75 | 0.25 | 0.21 | 0.21 | 0.25 | 0.25 | 1405 | 125 | 1572 | 1655 | 1525 | 1530 | 1434 |
| B | B2 | 2 | 2 | 48 | 42 | 0 | 6 | 6 | 0.88 | 30 | 28 | 0.75 | 0.13 | 0.13 | 0.10 | 0.10 | 0.10 | 1465 | 118 | 1608 | 1659 | 1654 | 1583 | 1662 |

**Key relationship:** Predicted Rent = Base Rent + Amenity Price (exact for all 4 rows)

---

## Rounding Convention: round_half_up (CRITICAL)

The export uses round-half-up convention, NOT Python's banker's rounding. Use this utility everywhere:

```python
import math

def round_half_up(x, decimals=0):
    multiplier = 10 ** decimals
    return math.floor(x * multiplier + 0.5) / multiplier
```

**Example:** B2 Vacant Exposure = 6/48 = 0.125. Python `round(0.125, 2)` → 0.12 (banker's). Export shows 0.13. You MUST use `round_half_up(0.125, 2)` → 0.13.

---

## Revenue Management Domain Rules

### 10 Methodologies at Launch
1. **Supply/Demand Dynamic Pricing** — adjust based on real-time supply (vacant, on-notice, expiring) and demand signals
2. **Competitor Analysis** — PUBLIC asking rents only, never nonpublic data
3. **Amenity-Adjusted Pricing** — hedonic decomposition: predicted = base + amenity
4. **Lease-Term Optimization** — concentrate expirations in peak season (May-Sep), 14-month preferred terms
5. **Exposure Management** — total exposure is the key operational metric; 30d exposure below 5% = green light to push pricing
6. **Concession Management** — preserve headline rent, lower effective cost; valuations based on contractual rent
7. **Renewal Pricing (basic)** — 50%+ of rent roll; balance retention vs revenue
8. **Revenue Optimization** — maximize total revenue, not rent per unit; vacancy costs $1,800/mo at $1,800 asking
9. **Loss-to-Lease Analysis** — gap between market and in-place rent; addressed only as leases expire
10. **Seasonal Dynamics** — March 2026 approaching spring peak (May-Sep); 1.6-7.1% seasonal variation

### Multi-Armed Bandit (MAB) Price Experimentation
- Key differentiator: no other multifamily RM platform does this
- Bayesian approach (updating beliefs), not frequentist (p-values)
- Practical significance (5+ day velocity difference) over statistical significance
- Never experiment below 0.75 occupancy — just cut price
- Minimum 3 vacant units per experiment (configurable)
- Max price spread: 6% or $100, whichever tighter (configurable)
- Observation window: 14 days (configurable)
- Early termination: accept any application on any unit

### The Four Unit Type Archetypes

| Unit Type | Archetype | Key Signal | Expected Grade |
|-----------|-----------|------------|---------------|
| A1 | HEALTHY | 96% occ, aligned with comps, 7.6% LTL upside | 80-90, HEALTHY |
| A2 | OVERPRICING | 86% occ declining, $53 above predicted, 3-month occ erosion | 50-65, ACTION_NEEDED |
| B1 | CRISIS | 79% occ free-falling, $91 above ALL comps, negative LTL | 20-35, CRITICAL |
| B2 | PUZZLE | 88% occ, priced at comps, but 6 units × 28 days vacant | 55-65, ACTION_NEEDED |

### Expected Flag Counts (Default Config)
- A1: 3 flags (DOM_ABOVE_THRESHOLD, EXECUTED_BELOW_ASKING, OCCUPANCY_PUSH_ELIGIBLE)
- A2: 7 flags (OCCUPANCY_BELOW_ACTION, EXPOSURE_ACTION_NEEDED, CONCESSION_TRIGGER, HIGH_REVENUE_AT_RISK, DOM_ABOVE_THRESHOLD, RENEWAL_FREEZE_RECOMMENDED, MAB_ELIGIBLE)
- B1: 12 flags (OCCUPANCY_CRISIS, EXPOSURE_CRISIS, EXPOSURE_DETERIORATING, ABOVE_COMP_PREMIUM_THRESHOLD, CONCESSION_TRIGGER, NEGATIVE_LTL, EXECUTED_SIGNIFICANTLY_ABOVE_ASKING, HIGH_REVENUE_AT_RISK, DOM_ABOVE_THRESHOLD, AMENITY_AUDIT_RECOMMENDED, RENEWAL_FREEZE_RECOMMENDED, MAB_ELIGIBLE)
- B2: 7 flags (CONCESSION_TRIGGER, HIGH_REVENUE_AT_RISK, OCCUPANCY_BELOW_CONCERN, EXPOSURE_CAUTION, ASKING_ABOVE_PREDICTED_THRESHOLD, DOM_ABOVE_THRESHOLD, MAB_ELIGIBLE)

---

## Regulatory Compliance (NON-NEGOTIABLE)

These rules are embedded in the architecture and must be enforced in every piece of code:

1. **NEVER** use competitors' nonpublic data (effective rents, concessions, occupancy) in runtime pricing
2. **ONLY** public asking rents for competitive context — stored in `comp_rents` table
3. Each customer's data walled off at infrastructure level (`organization_id` filter on EVERY query)
4. No cross-customer data reporting more granular than state level
5. **Auto-accept NEVER the default** — operators must actively confirm pricing changes
6. Complete audit logs of every recommendation, operator action, and override (`audit_log` is **append-only** — no UPDATE, no DELETE)
7. Published methodology documentation (what data is used, what is excluded)
8. White-box transparency: every recommendation shows ranked factors and weights
9. Compliant with: DOJ settlement (Nov 2025), NY algorithmic pricing ban (Dec 2025), CA AB 325 (Jan 2026)

---

## Anti-Patterns (Global)

- **Do NOT** do any work without updating `progress.md` afterward. Every action gets logged.
- **Do NOT** implement a decision without logging it in `decisions.md` first. Decide, log, then build.
- **Do NOT** start a task without checking `agents.md` for the right persona to adopt.
- **Do NOT** put database queries in `engine/` modules. Engine is pure computation.
- **Do NOT** use `round()` for percentage calculations. Use `round_half_up()`.
- **Do NOT** hardcode thresholds. ALL thresholds come from `client_configs`.
- **Do NOT** let Claude compute dollar amounts. All revenue math is deterministic Python.
- **Do NOT** let Claude generate chart data. Viz data is deterministic from metrics.
- **Do NOT** use `statistics.mean()` on empty lists. Guard against division by zero.
- **Do NOT** make `audit_log` updateable. No update/delete methods on the ORM model.
- **Do NOT** store raw Claude API responses. Parse, validate, store clean structured JSON.
- **Do NOT** use random seeding without reconciliation. "Balancing unit" approach only.
- **Do NOT** skip loading states in the frontend. Every async operation shows feedback.

---

## Verification Steps

After each spec, run the corresponding holdout scenarios AND verify living documents:

| Check | Command/Action |
|-------|---------------|
| progress.md current | Verify the last entry matches the work just completed |
| decisions.md current | Verify any decisions made during the spec are logged |

| Spec | Test Command | Key Checks |
|------|-------------|------------|
| 01 | `pytest tests/test_reconciliation.py` | 56+ assertions, all rent/exposure/DOM averages match export |
| 02 | `pytest tests/test_metrics_engine.py tests/test_flag_generator.py` | Metrics values, flag counts (3/7/12/7) |
| 03 | `pytest tests/test_diagnostic_service.py tests/test_action_plan.py` | Pipeline completes, grades correct, experiments valid |
| 04 | `pytest tests/test_narrative_service.py tests/test_viz_data_service.py` | 12 slides, consistency check, fallback works |
| 05 | Manual: login → run diagnostic → navigate 12 slides | Charts render, data accurate, no console errors |
| 06 | Manual: register → login → config → comps → experiments | Full platform flow, audit logged |

---

## Reference Documents

| Document | Location | Purpose |
|----------|----------|---------|
| EliseAI_Pricing_Export.xlsx | Project root | Ground truth data — every number must tie |
| EliseAI_Revenue_Manager_Practical.pdf | Project root | Case study assignment defining requirements |
| Multifamily_Revenue_Management_Landscape.md | Project root | RM domain knowledge, competitive landscape, regulatory framework |
| layer3-decisions-log.md | Project root | Meta-planning decisions |
| layer2-decisions-log.md | Project root | Design & architecture decisions |
| **progress.md** | **Project root** | **Running work log — MUST update after every action** |
| **decisions.md** | **Project root** | **Decision log — MUST update before implementing any decision** |
| **agents.md** | **Project root** | **Agent personas — read before starting any task** |

---

## Demo Credentials

- Email: `demo@example.com`
- Password: `demo123`
- Role: admin
- Organization: "Demo Client"

---

## Database (14 Tables)

### Domain 1: Auth
- `organizations` (id, name, slug, created_at)
- `users` (id, email, password_hash, full_name, role, organization_id, created_at, last_login, is_active)

### Domain 2: Properties & Units
- `properties` (id, organization_id, name, code, address, submarket, total_units, year_built, property_class, created_at)
- `unit_types` (id, property_id, code, bed, bath, total_units, base_rent, sqft_min, sqft_max)
- `units` (id, unit_type_id, property_id, unit_number, floor, sqft, 8 amenity booleans, amenity_premium, predicted_rent, status, current_rent, lease_start, lease_end, tenant_id, asking_rent, days_on_market, days_vacant, move_out_date, last_executed_rent, last_executed_date, concession fields, created_at, updated_at)

### Domain 3: Comp Set
- `comp_properties` (id, property_id, name, address, submarket, total_units, year_built, property_class, distance_miles, data_source, notes, is_active, last_refreshed_at, created_at)
- `comp_unit_types` (id, comp_property_id, subject_unit_type_id, bed, bath, sqft_range, relevance_score)
- `comp_rents` (id, comp_unit_type_id, observation_date, asking_rent, concession_advertised, net_effective_rent, units_advertised, source_url, data_source, created_at) — **PUBLIC DATA ONLY**

### Domain 4: Config
- `client_configs` (id, property_id, version, is_active, investment_thesis, risk_profile, hold_period_years, business_plan_summary, 8 JSONB threshold fields, created_at, created_by)

### Domain 5: Historical
- `historical_snapshots` (id, unit_type_id, snapshot_date, occupancy/rent/exposure fields, created_at)

### Domain 6: Diagnostics & Audit
- `diagnostic_runs` (id, property_id, config_id, run_date, triggered_by, 6 JSONB result fields, status, error_message, timing fields, total_ms)
- `audit_log` (id, organization_id, user_id, action, entity_type, entity_id, details JSONB, ip_address, created_at) — **APPEND-ONLY**

### Domain 7: Experiments
- `experiments` (id, diagnostic_run_id, unit_type_id, status lifecycle, experiment_design JSONB, approved_by, outcome, outcome_details JSONB)
- `experiment_assignments` (id, experiment_id, unit_id, arm_label, assigned_price, concession, leased, days_to_lease, tours_count)

---

## API Endpoints (28 total)

All endpoints except `/auth/*` require JWT Bearer token. All queries filter by `organization_id` from token.

**Auth (3):** POST /auth/login, POST /auth/register, GET /auth/me
**Properties (4):** GET /properties, GET /properties/{id}, GET /properties/{id}/units, GET /properties/{id}/export
**Config (4):** GET /properties/{id}/config, POST /properties/{id}/config, POST /properties/{id}/config/generate, GET /properties/{id}/config/history
**Diagnostic (4):** POST /properties/{id}/diagnostic/run, GET /diagnostic/{run_id}, GET /diagnostic/{run_id}/slides, GET /properties/{id}/diagnostic/history
**Comps (4):** GET /properties/{id}/comps, GET /properties/{id}/comps/trends, POST /properties/{id}/comps/suggest, POST /comps/refresh
**Experiments (5):** GET /properties/{id}/experiments, POST /experiments/{id}/approve, POST /experiments/{id}/cancel, PUT /experiments/{id}/assignments/{aid}, POST /experiments/{id}/evaluate
**Snapshots (1):** GET /properties/{id}/snapshots
**Audit (1):** GET /audit

---

## Current Status

| Spec | Status | Tests Passing | Notes |
|------|--------|---------------|-------|
| 01 | COMPLETE | 71/71 | All reconciliation checks pass |
| 02 | COMPLETE | 56/56 | All metrics exact, flag counts 3/7/12/7, engine pure, <10ms |
| 03 | COMPLETE | 35/35 | Pipeline works, grades correct, experiments valid, audit logged |
| 04 | COMPLETE | 26/26 | 12 slides, viz exact, consistency check, fallback works |
| 05 | COMPLETE | Build OK | 8 charts, 11 slides, keyboard nav, property switching |
| 06 | COMPLETE | 15/15 | Auth, 22 endpoints, config preview, comp refresh, audit |

---

## Quick Reference — Reconciliation Targets

### Rent Pool Totals
| Unit Type | Amenity Total | In-Place Total | Asking Total |
|-----------|--------------|----------------|--------------|
| A1 | 48 x $89 = $4,272 | 46 x $1,269 = $58,374 | 3 x $1,365 = $4,095 |
| A2 | 36 x $83 = $2,988 | 31 x $1,304 = $40,424 | 6 x $1,411 = $8,466 |
| B1 | 24 x $125 = $3,000 | 19 x $1,572 = $29,868 | 6 x $1,525 = $9,150 |
| B2 | 48 x $118 = $5,664 | 42 x $1,608 = $67,536 | 6 x $1,654 = $9,924 |

### Pre-Computed Unit-Level Values
| Metric | A1 | A2 | B1 | B2 |
|--------|----|----|----|----|
| Executed | [1290,1310,1340,1356] | [1370,1385,1400,1413] | [1630,1660,1675] | [1640,1650,1660,1670,1675] |
| DOM | [15,26,31] | [8,14,18,24,28,40] | [10,18,22,28,32,40] | [18,22,28,32,36,44] |
| DV | [12,22] | [7,10,14,22,27] | [10,15,18,25,32] | [16,20,26,30,34,42] |

### Key Data Relationship
Export "Occupied" count INCLUDES on-notice units. In DB: pure_occupied = occupied - on_notice.
ON_NOTICE units have both current_rent (in-place) and asking_rent (re-lease listing).
