# Execution Plan — Multifamily Revenue Management Platform

## Overview

6 specs executed in dependency order, with parallelization where possible. Each spec follows a convergence loop: implement → test against holdout scenarios → fix → re-test until all convergence criteria pass.

---

## Dependency Graph

```
Spec 01: Data Model & Dummy Data
    │
    ├──→ Spec 02: Core Pricing Engine (depends on Spec 01 for data)
    │         │
    │         └──→ Spec 03: Diagnostic & Action Plan (depends on Spec 02 for engine)
    │                   │
    │                   └──→ Spec 04: AI Narrative Layer (depends on Spec 03 for diagnosis)
    │                             │
    │                             └──→ Spec 05: Interactive Slideshow UI (depends on Spec 04 for slide data)
    │
    └──→ Spec 06: Auth, Historical & Platform Shell (depends on Spec 01 for schema)
              │
              └──→ Integrates with Specs 02-05 for full platform flow
```

**Parallelization opportunity:** After Spec 01 completes, Specs 02 and 06 can run simultaneously in separate Claude Code sessions.

---

## Phase 1: Foundation (Spec 01)

**Duration estimate:** 2-4 hours

### What gets built
- PostgreSQL database with all 14 tables
- SQLAlchemy 2.0 ORM models
- Alembic migrations (reversible)
- Seed scripts (5 scripts in order: properties → units → comps → snapshots → config)
- 156 units of reconciling dummy data
- 9 comp properties with 72 rent observations
- 16 historical snapshots
- Default client config
- Demo user (demo@example.com / demo123)
- Reconciliation test suite (56+ assertions)

### Validation
```bash
alembic upgrade head
python -m app.seed.seed_all
pytest tests/test_reconciliation.py -v
pytest tests/test_schema.py -v
```

### Success gate
ALL reconciliation tests pass. Every aggregate matches the EliseAI Pricing Export exactly. Migration round-trip works.

### Key risks
- Rounding: B2 exposure 0.125 must round to 0.13, not 0.12. Use `round_half_up()`.
- B1 in-place rent ($1,572 avg) must be ABOVE asking ($1,525). Requires careful seeding.
- Amenity premiums must sum exactly (A1=$4,272, A2=$2,988, B1=$3,000, B2=$5,664).

---

## Phase 2A: Pricing Engine (Spec 02) — can run parallel with 2B

**Duration estimate:** 3-5 hours

### What gets built
- Engine modules in `app/engine/` (8 modules, all pure functions)
- `round_half_up()` utility
- Metrics engine service (orchestrates engine modules)
- Flag generator (20+ flag rules, all parameterized by config)
- Claude API client wrapper (retry, JSON parsing, error handling)
- Test suites for metrics and flags

### Validation
```bash
pytest tests/test_metrics_engine.py -v
pytest tests/test_flag_generator.py -v
pytest tests/test_claude_client.py -v
```

### Success gate
Metrics for all 4 unit types match hand-computed values. Flag counts: A1=3, A2=7, B1=12, B2=7. Config sensitivity test passes (different config → different flags).

### Key risks
- Engine modules accidentally importing database code. Enforce: zero SQLAlchemy imports in `app/engine/`.
- Flag count off-by-one: carefully verify each flag rule's condition boundaries.
- Demand-occupancy divergence must NOT fire for B1 (demand 0.75 < occ 0.79).

---

## Phase 2B: Auth & Platform Shell (Spec 06) — can run parallel with 2A

**Duration estimate:** 3-5 hours

### What gets built
- JWT auth backend (register, login, get_current_user dependency)
- Multi-tenancy filtering (organization_id on every query)
- Frontend login/register pages
- Platform shell (sidebar, header, navigation)
- Property list dashboard with KPI cards
- Config editor with sliders and preview
- Historical trend sparklines
- Comp management UI
- Experiment tracking UI
- Simulated comp refresh

### Validation
```bash
pytest tests/test_auth.py -v
# Manual: login → property list → property dashboard → config editor
```

### Success gate
Full auth flow works. Demo user can log in and see properties. Config editor renders with all 8 sections. Preview Diagnosis shows flag counts.

---

## Phase 3: Diagnostic Pipeline (Spec 03)

**Duration estimate:** 3-5 hours
**Depends on:** Specs 01, 02

### What gets built
- Diagnostic service (full pipeline orchestration)
- Action plan service (30-day phased plan generation)
- MAB experiment design logic
- API endpoints (POST /diagnostic/run, GET /diagnostic/{id})
- Diagnostic run storage (all JSONB fields)
- Audit logging for diagnostic runs

### Validation
```bash
pytest tests/test_diagnostic_service.py -v
pytest tests/test_action_plan.py -v
# Manual: POST to diagnostic endpoint, verify response
```

### Success gate
Diagnostic run completes in <30s. B1 grades CRITICAL. B2 experiment has 3 arms. Action plan has 4 phases with Day 15 decision point. Revenue math correct.

### Key risks
- Claude response validation: if Claude returns malformed JSON, the pipeline must not crash.
- Revenue math must be computed in Python, not by Claude. Verify no dollar amounts originate from Claude's output.

---

## Phase 4: Narrative Layer (Spec 04)

**Duration estimate:** 2-4 hours
**Depends on:** Spec 03

### What gets built
- Narrative service (2 Claude calls for per-slide text)
- Visualization data service (14 viz type generators)
- Slide deck JSON assembly
- Narrative consistency check (dollar amount validation)
- Fallback narrative templates
- API endpoint (GET /diagnostic/{run_id}/slides)

### Validation
```bash
pytest tests/test_narrative_service.py -v
pytest tests/test_viz_data_service.py -v
# Manual: GET slides endpoint, verify all 12 slides have narrative + viz_data
```

### Success gate
12 slides returned. All viz_data numeric values match metrics engine. Narrative mentions key figures ($91 comp premium, $911/day burn). Fallback works when Claude is mocked to fail.

---

## Phase 5: Interactive Slideshow (Spec 05)

**Duration estimate:** 4-6 hours
**Depends on:** Spec 04

### What gets built
- SlideshowViewer component (navigation, keyboard, polling)
- 11 slide components
- 8 custom chart components (ScoreGauge, RentWaterfall, TrendLineChart, etc.)
- Slide navigation (arrows, counter, thumbnails)
- Property switching
- Progressive loading
- Print styles

### Validation
```bash
# Manual end-to-end:
# 1. Login with demo@example.com / demo123
# 2. Select Property B
# 3. Click "Run Diagnostic"
# 4. Navigate through all 12 slides
# 5. Verify charts show correct data
# 6. Switch to Property A
# 7. Verify data updates
```

### Success gate
12 slides render without console errors. Charts show correct values. Keyboard navigation works. Property switching works. No broken layouts at 1280px.

### Key risks
- Recharts ResponsiveContainer must wrap every chart or they won't resize.
- ScoreGauge is custom SVG — must be built from scratch.
- RentWaterfall needs floating bar segments — complex Recharts customization.

---

## Phase 6: Integration & Polish

**Duration estimate:** 2-3 hours
**Depends on:** All previous specs

### What gets done
- Full end-to-end walkthrough (register → login → configure → diagnose → slideshow)
- Fix any integration issues between specs
- Verify all holdout scenarios pass
- Add loading states, error handling, edge cases
- Docker compose setup (PostgreSQL + Backend + Frontend)
- README with setup instructions

### Final validation checklist
- [ ] `docker-compose up --build` starts the full stack
- [ ] Demo user can log in
- [ ] Both properties show on dashboard
- [ ] Diagnostic pipeline completes for both properties
- [ ] Slideshow renders all 12 slides with correct data
- [ ] Config editor with Preview Diagnosis works
- [ ] Comp management with refresh works
- [ ] Experiment tracking shows proposed experiments
- [ ] Audit log captures all actions
- [ ] No console errors in browser
- [ ] All pytest suites pass

---

## Timeline Summary

| Phase | Spec(s) | Estimated Hours | Parallel? |
|-------|---------|-----------------|-----------|
| 1 | Spec 01: Data Model | 2-4h | — |
| 2A | Spec 02: Pricing Engine | 3-5h | ✅ with 2B |
| 2B | Spec 06: Auth/Platform | 3-5h | ✅ with 2A |
| 3 | Spec 03: Diagnostic | 3-5h | — |
| 4 | Spec 04: Narrative | 2-4h | — |
| 5 | Spec 05: Slideshow | 4-6h | — |
| 6 | Integration & Polish | 2-3h | — |
| **Total** | | **19-32h** | |

With parallelization of Phase 2 and leveraging Claude Code's compression, target is 2-3 calendar days.

---

## Convergence Loop Per Spec

For each spec, follow this loop:

```
1. Read the spec file completely
2. Read the corresponding holdout scenario file
3. Read the EXEMPLARS/README.md section for this spec
4. Implement the spec
5. Run the convergence criteria checks
6. If any check fails:
   a. Identify root cause
   b. Fix
   c. Re-run ALL checks (not just the failing one)
   d. Repeat until all pass
7. Run the holdout scenario tests
8. Update WORKLOG.md with results
9. Proceed to next spec
```
