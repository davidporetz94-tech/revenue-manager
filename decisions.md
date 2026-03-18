# Decisions Log — Multifamily Revenue Management Platform

> **MANDATORY:** This file MUST be updated every time a decision is made during execution. A "decision" is any choice between two or more options, any deviation from a spec, any interpretation of an ambiguous requirement, any tradeoff, or any technical choice not explicitly specified in the specs. Log it BEFORE implementing it. If you made a choice, it goes here.

---

## Format

Each entry follows this structure:

```
### DEC-[NNN] — [SHORT TITLE]
**Date:** [YYYY-MM-DD]
**Phase:** [Spec number or Integration]
**Context:** What situation required a decision?
**Options considered:**
1. Option A — [description]
2. Option B — [description]
3. (Optional) Option C — [description]
**Decision:** [Which option was chosen]
**Rationale:** Why this option over the others
**Impact:** What does this affect downstream?
**Reversible:** Yes/No — and what would reversal require
```

---

## Pre-Loaded Decisions (from Layer 2/3 Planning)

These decisions were made during planning and are FINAL. They are logged here for traceability. Do not re-litigate them.

### DEC-001 — Three-Layer Engine Architecture
**Date:** 2026-03-17 (Layer 2)
**Phase:** Architecture
**Context:** How should the pricing engine be structured?
**Options considered:**
1. Monolithic rules engine with hardcoded thresholds
2. Two-layer (metrics + Claude)
3. Three-layer (metrics → configurable flags → Claude diagnosis)
**Decision:** Option 3 — Three-layer
**Rationale:** Same data means different things for different clients. 80% occupancy is crisis for a stabilized REIT, on-track for a lease-up. Thresholds must be configurable. Judgment must be intelligent (Claude), not hardcoded.
**Impact:** Requires client_configs table, flag generator module, config editor UI
**Reversible:** No — fundamental to the architecture

### DEC-002 — Claude for Diagnosis, Not for Math
**Date:** 2026-03-17 (Layer 2)
**Phase:** Architecture
**Context:** Should Claude compute revenue figures, or should Python handle all math?
**Decision:** Python handles ALL math. Claude receives pre-computed facts and generates narrative/diagnosis only.
**Rationale:** Claude can hallucinate numbers. Revenue math must be deterministic and auditable. A regulatory audit needs to trace every dollar amount to a computation, not to an LLM output.
**Impact:** Revenue metrics, vacancy costs, breakeven calculations all live in Python. Claude prompts include these as facts.
**Reversible:** No — regulatory requirement

### DEC-003 — round_half_up Instead of Python round()
**Date:** 2026-03-17 (Layer 2)
**Phase:** Data integrity
**Context:** B2 exposure = 6/48 = 0.125. Python's round(0.125, 2) = 0.12 (banker's rounding). Export shows 0.13.
**Decision:** Use round_half_up() everywhere: `math.floor(x * 10**d + 0.5) / 10**d`
**Rationale:** The export uses round-half-up convention. Every number must match exactly.
**Impact:** All percentage calculations throughout the codebase
**Reversible:** No — data integrity requirement

### DEC-004 — Direct Action for B1 Instead of Experiment
**Date:** 2026-03-17 (Layer 2)
**Phase:** RM Methodology
**Context:** B1 has 5 vacant units (MAB-eligible) but also 2 CRITICAL flags. Experiment or direct price cut?
**Decision:** Direct action ($50 cut to $1,475 + 4wk free on stalest 2 units). Not experiment.
**Rationale:** 2 CRITICAL flags + HIGH confidence root cause is price ($91 above every comp). Experimenting while hemorrhaging $254/day is irresponsible. Cut first, experiment later if the cut doesn't work (Stage 2 at Day 15).
**Impact:** B1 Phase 1 action is REDUCE_ASKING_RENT, not LAUNCH_EXPERIMENT
**Reversible:** Yes — if diagnosis prompt is tuned, Claude could recommend experiment for less severe cases

### DEC-005 — Bayesian Over Frequentist for MAB
**Date:** 2026-03-17 (Layer 2)
**Phase:** RM Methodology
**Context:** How should experiment results be evaluated — p-values or Bayesian updating?
**Decision:** Bayesian with practical significance (5+ day velocity difference)
**Rationale:** With only 2-3 units per arm, frequentist statistics lack power. Practical significance ("did units in one arm lease 5+ days faster?") is more actionable than a p-value that can never reach 0.05 with N=3.
**Impact:** Experiment evaluation logic, Claude evaluation prompts
**Reversible:** Yes — could add frequentist checks as secondary validation

### DEC-006 — Sync Execution for MVP
**Date:** 2026-03-17 (Layer 2)
**Phase:** Architecture
**Context:** Should the diagnostic pipeline be async (Celery/background workers) or sync?
**Decision:** Synchronous. ~12-15 seconds is acceptable. Frontend polls every 2s.
**Rationale:** Avoids Celery complexity at launch. Async-ready architecture (return run_id, poll for completion) means switching to background workers later is a refactor, not a redesign.
**Impact:** No Celery, no Redis, no worker processes. Simpler deployment.
**Reversible:** Yes — designed for easy migration to async

### DEC-007 — Recharts Over D3 for Visualizations
**Date:** 2026-03-17 (Layer 2)
**Phase:** Frontend
**Context:** Which charting library for the slideshow?
**Decision:** Recharts
**Rationale:** React-native (declarative), responsive out of the box, handles all needed chart types (bar, line, area). D3 is more powerful but requires imperative DOM manipulation that fights React. Recharts is in the approved artifact library.
**Impact:** All chart components use Recharts API. ScoreGauge is custom SVG (Recharts doesn't have gauge charts).
**Reversible:** Yes — chart components are isolated, could swap library per component

---

## Execution Decisions (add new entries below as decisions are made)

### DEC-008 — Use PostgreSQL 17 Instead of 15
**Date:** 2026-03-17
**Phase:** Spec 01
**Context:** Spec requires PostgreSQL 15+. Local machine has PostgreSQL 17 via Homebrew.
**Options considered:**
1. Install PostgreSQL 15 separately
2. Use the already-running PostgreSQL 17
**Decision:** Option 2 — Use PostgreSQL 17
**Rationale:** PostgreSQL 17 is backward-compatible with 15. Already running locally. No need to install a separate version.
**Impact:** None — all features used (UUID, JSONB, indexes) are available in both 15 and 17.
**Reversible:** Yes — trivial to switch

### DEC-009 — Use Relaxed Version Pins for Python 3.14 Compatibility
**Date:** 2026-03-17
**Phase:** Spec 01
**Context:** Bootstrap instructions pinned exact versions (e.g., psycopg2-binary==2.9.9) but Python 3.14 needs newer wheels.
**Options considered:**
1. Downgrade Python to 3.11/3.12
2. Use >= version constraints to allow compatible versions
**Decision:** Option 2 — Relaxed version pins with >= constraints
**Rationale:** Python 3.14 is available on the system. Newer package versions are backward-compatible. No need to manage a different Python version.
**Impact:** Specific installed versions may differ slightly from bootstrap spec but all APIs remain compatible.
**Reversible:** Yes — can pin exact versions if issues arise

### DEC-010 — Deterministic Scoring Rubric in Claude Prompt
**Date:** 2026-03-18
**Phase:** Polish (Step 1A)
**Context:** Same inputs to Claude produced different health scores across runs, undermining evaluator confidence.
**Options considered:**
1. Hardcode scores in fallback only
2. Add rubric to Claude prompt with expected ranges
3. Remove Claude scoring entirely and compute deterministically
**Decision:** Option 2 — Add rubric to prompt with flag-count-based score bands
**Rationale:** Keeps Claude's judgment for nuanced scoring while constraining the range. ±5 point tolerance is acceptable. Fully deterministic scoring (option 3) would remove Claude's ability to weigh flag severity context.
**Impact:** Scores now stay within ±5 across runs. Fallback scoring also aligned to same rubric.
**Reversible:** Yes — rubric can be tuned

### DEC-011 — Server-Side Property Summary Endpoint
**Date:** 2026-03-18
**Phase:** Polish (Step 4)
**Context:** Frontend used hardcoded UNIT_TYPE_DATA and SNAPSHOT_TRENDS. Needed real API data for evaluator credibility.
**Options considered:**
1. Have frontend call metrics_engine directly (impossible — Python backend)
2. Add GET /properties/{id}/summary that reuses compute_property_metrics()
3. Embed metrics in the GET /properties response
**Decision:** Option 2 for detail + enhanced option 3 for dashboard KPIs
**Rationale:** Summary endpoint returns full unit type metrics + trends. Enhanced /properties includes per-property KPIs (vacant, occ, burn) to avoid N+1 calls from the dashboard.
**Impact:** Frontend now shows real data from the engine. Hardcoded constants removed from both PortfolioDashboard and PricingReview.
**Reversible:** Yes — additive change

### DEC-012 — Progressive Loading via Frontend Phasing
**Date:** 2026-03-18
**Phase:** Polish (Step 6)
**Context:** 12-15 seconds blank screen during Claude processing was poor UX.
**Options considered:**
1. Backend streaming/SSE for partial results
2. Frontend-only phasing using already-loaded data
3. WebSocket progress updates
**Decision:** Option 2 — Frontend phases metrics (immediate) → flags (immediate) → AI diagnosis (when ready)
**Rationale:** Summary data and flagPreview are already loaded when user navigates to property. Zero additional API calls. AI layer just adds on top. Simplest approach with best UX impact.
**Impact:** Evaluator sees metrics and flags within 1 second of clicking "Get AI Review". AI diagnosis fades in when ready.
**Reversible:** Yes — can add streaming later

<!--
INSTRUCTIONS:
- Number sequentially from DEC-013 onward
- Log BEFORE implementing
- Every decision gets all fields
- "I just went with X" is NOT a valid entry — explain WHY
-->
