# RoboRev — Build Context & Presentation Reference

## What Is RoboRev?

RoboRev is a full-stack AI-powered revenue management platform for multifamily real estate. It ingests rent roll data, runs a deterministic pricing engine, generates AI-powered diagnoses via Claude, and outputs actionable 30-day plans — all presented through an interactive data-rich UI.

**Built in a single session** — from zero to 203 passing tests, 131 files, 13,400+ lines of code.

---

## The Problem It Solves

Multifamily operators manage thousands of units across dozens of properties. The core question is deceptively simple: **"Are we priced correctly for new leases?"**

Getting it wrong is expensive:
- Price too high → units sit vacant at $1,525/month asking rent → that's **$50.83/day** per unit burning cash
- Price too low → you lease fast but leave money on the table for years
- One-size-fits-all thresholds don't work → 80% occupancy is a crisis for a stabilized REIT but on-track for a lease-up

The industry's existing tools (Yardi Revenue IQ, RealPage YieldStar/AIRM) are under DOJ antitrust scrutiny for opaque, potentially collusive pricing algorithms. RoboRev takes a different approach: **white-box transparency** where every recommendation is auditable.

---

## Architecture: The Three-Layer Engine

This is the core IP. Most tools are either pure rules engines (rigid) or pure AI (hallucinate numbers). RoboRev is neither.

```
Layer 1: Deterministic Metrics Engine (Python)
  │  Pure functions. No judgment. Just facts.
  │  Computes ~30 metrics per unit type from rent roll data.
  │  Runs in 9.7ms on 156 units.
  │
Layer 1.5: Configurable Flag Generator (Python)
  │  Compares metrics against CLIENT-configured thresholds.
  │  Same data, different client strategy → different flags.
  │  20 rules. Zero hardcoded thresholds.
  │
Layer 3: AI Diagnosis (Claude API)
  │  Receives pre-computed metrics + flags + business context.
  │  Generates scored diagnosis, root causes, action plan.
  │  NEVER computes dollar amounts — only narrates and sequences.
  │
  → 12-slide presentation + inline review UI
```

**Why three layers?**
- Layer 1 is auditable. Every number traces to a computation.
- Layer 1.5 is configurable. The client's strategy shapes what "good" means.
- Layer 3 is intelligent. Claude provides judgment, not just rules.
- Separation means you can validate each layer independently.

---

## The Math That Matters

### Ground Truth: EliseAI Pricing Export

Every number in the system traces back to this export — the single source of truth.

| Unit Type | Total | Occ | Vacant | Occ% | Asking | Comps | In-Place | Exposure |
|-----------|-------|-----|--------|------|--------|-------|----------|----------|
| A1 | 48 | 46 | 2 | 96% | $1,365 | $1,353 | $1,269 | 6% |
| A2 | 36 | 31 | 5 | 86% | $1,411 | $1,396 | $1,304 | 17% |
| B1 | 24 | 19 | 5 | 79% | $1,525 | $1,434 | $1,572 | 25% |
| B2 | 48 | 42 | 6 | 88% | $1,654 | $1,662 | $1,608 | 13% |

### Key Relationship
**Predicted Rent = Base Rent + Amenity Premium** (exact for all 4 rows)

Example: B1 = $1,405 (base) + $125 (amenity) = $1,530 (predicted)

### The Rounding Trap
B2 exposure = 6/48 = 0.125. Python's `round(0.125, 2)` returns **0.12** (banker's rounding). The export shows **0.13**. We use `round_half_up()` everywhere — `math.floor(x * 10^d + 0.5) / 10^d`. This single decision cascades through every percentage in the system.

### Revenue At Risk
| Unit Type | Daily Burn | Monthly Cost |
|-----------|-----------|-------------|
| A1 | $91/day | $2,730/mo |
| A2 | $235/day | $7,055/mo |
| B1 | $254/day | $7,625/mo |
| B2 | $331/day | $9,924/mo |
| **Portfolio** | **$911/day** | **$27,334/mo** |

Formula: `daily_burn = (asking_rent / 30) × vacant_units`

---

## The Four Unit Type Archetypes

Each unit type tells a different pricing story:

### A1: The Healthy One
- 96% occupancy, $12 above comps (0.9%) — perfectly positioned
- 3 flags (all low severity). Push renewals, hold asking.
- **Lesson:** High occupancy + aligned comps = green light to push pricing.

### A2: The Overpricing Signal
- 86% occupancy, declining from 92% over 3 months
- $53 above predicted rent, 17% exposure
- 7 flags including OCCUPANCY_BELOW_ACTION and CONCESSION_TRIGGER
- **Lesson:** Occupancy erosion is the leading indicator. Price cut or experiment needed.

### B1: The Crisis
- 79% occupancy in freefall (was 88% three months ago)
- **$91 above EVERY comp** in a market where comps dropped $41 in 3 months
- 12 flags, 2 CRITICAL. Negative loss-to-lease (in-place tenants pay MORE than asking)
- Burning $254/day. Direct action, not experiment.
- **Lesson:** When you have HIGH confidence the problem is price AND the unit has CRITICAL flags, cut first, experiment later.

### B2: The Puzzle
- 88% occupancy, priced competitively ($8 BELOW comps)
- But 6 units vacant averaging 28 days — why aren't they leasing?
- 7 flags, zero CRITICAL. The problem likely isn't price.
- **Lesson:** When price is right but units aren't moving, investigate non-price factors (unit condition, listing quality, tour conversion).

---

## Key Architectural Decisions

### DEC-001: Three-Layer Over Two-Layer
**Why:** Same metrics mean different things to different clients. 80% occupancy = crisis for stabilized, on-track for lease-up. Thresholds must be configurable between the computation and the judgment.

### DEC-002: Python for Math, Claude for Judgment
**Why:** Claude hallucinating a vacancy cost of "$15,000" when the real number is "$7,625" would destroy trust. Every dollar amount is computed deterministically in Python. Claude receives pre-computed facts and generates narrative and diagnosis only. A regulatory audit can trace every number to a computation, not to an LLM.

### DEC-004: Direct Action for B1, Not Experiment
**Why:** B1 has 5 vacant units (eligible for MAB experiment) BUT 2 CRITICAL flags with HIGH confidence root cause ($91 above every comp). Experimenting while hemorrhaging $254/day is irresponsible. Cut first ($1,525 → $1,475). If it doesn't work by Day 15, THEN experiment at comps ($1,434).

### DEC-005: Bayesian Over Frequentist for MAB
**Why:** With 2-3 units per arm, p-values will never reach 0.05. Practical significance (did units in one arm lease 5+ days faster?) is more actionable than statistical significance that's unachievable at N=3.

---

## Flag Generation Logic (20 Rules)

Flags are facts, not judgments. Each rule compares a metric against a config threshold.

**Expected flag counts with default config:**
- A1: **3 flags** (DOM_ABOVE_THRESHOLD, EXECUTED_BELOW_ASKING, OCCUPANCY_PUSH_ELIGIBLE)
- A2: **7 flags** (OCCUPANCY_BELOW_ACTION, EXPOSURE_ACTION_NEEDED, CONCESSION_TRIGGER, HIGH_REVENUE_AT_RISK, DOM_ABOVE_THRESHOLD, RENEWAL_FREEZE_RECOMMENDED, MAB_ELIGIBLE)
- B1: **12 flags** (2 CRITICAL: OCCUPANCY_CRISIS + EXPOSURE_CRISIS, plus 10 more)
- B2: **7 flags** (zero CRITICAL — it's a puzzle, not a crisis)

**Config sensitivity:** Same B1 data with a value-add config (crisis_below=0.72 instead of 0.82) changes OCCUPANCY_CRISIS → OCCUPANCY_BELOW_ACTION. The flag generator doesn't know what's "bad" — the client's strategy defines it.

---

## MAB Experiment Framework

**Multi-Armed Bandit pricing experiments** — a key differentiator. No other multifamily RM platform does this.

### Unit Allocation Rules
| Vacant Units | Allocation |
|-------------|-----------|
| 2 | 1 control / 1 test |
| 3 | 1 control / 2 test |
| 4 | 2 control / 2 test |
| 5 | 2 control / 3 test |
| 6+ | Even split or 3-arm (control / price test / concession test) |

### B2 Example (Three-Arm)
- Control: $1,654 (2 units)
- Price test: $1,600 (2 units)
- Concession test: $1,654 + 2 weeks free (2 units)
- 14-day observation window
- Convergence: price arm leases 2x faster → winner

### Guard Rails
- Never experiment below 75% occupancy — just cut price
- Max price spread: 6% or $100, whichever tighter
- Operator must approve (auto-accept NEVER the default)
- Either arm can be pulled early on application

---

## 30-Day Action Plan Structure

**Phase 1 (Days 1-3):** Immediate stabilization
- B1: Cut asking $1,525→$1,475 + 4 weeks free on stalest 2 units
- B1: Freeze renewal increases (negative LTL — tenants already pay above market)
- A2: Launch price experiment ($1,411 control vs $1,358 test)
- B2: Launch three-arm experiment

**Phase 2 (Days 4-14):** Calibrate
- A1: Hold asking, push renewals to ~$1,332 (+5%)
- B1: Amenity audit ($125 premium at 8.2% — above threshold)
- B2: Non-price investigation (tour conversion, unit condition)

**Phase 3 (Days 15-21):** Decision point
- B1: ≥2 leased → hold $1,475. Zero leased → reduce to $1,434 (comps)
- A2/B2: Evaluate experiment results, converge or escalate

**Phase 4 (Days 22-30):** Lock strategies based on Phase 3 data

---

## Regulatory Compliance (Non-Negotiable)

Built for the post-DOJ-settlement era:
1. **ONLY public asking rents** from competitors — never effective rents, occupancy, or concessions
2. **Organization-level data isolation** — `organization_id` filter on every query
3. **Append-only audit log** — every recommendation, action, and override recorded
4. **Auto-accept NEVER the default** — operators maintain independent decision authority
5. **White-box transparency** — every recommendation shows ranked factors and weights
6. Compliant with DOJ settlement (Nov 2025), NY algorithmic pricing ban (Dec 2025), CA AB 325 (Jan 2026)

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React 18, Tailwind CSS, Recharts |
| Backend | Python 3.12, FastAPI, SQLAlchemy 2.0 |
| Database | PostgreSQL 15 (Railway managed, 14 tables, JSONB configs) |
| AI | Claude claude-sonnet-4-20250514 via Anthropic SDK |
| Auth | JWT (bcrypt + PyJWT, 24h expiry) |
| Migrations | Alembic (reversible, auto-run on startup) |
| Hosting | Railway Pro (3-service architecture) |

---

## Live Deployment (Railway)

| Service | URL |
|---------|-----|
| Frontend | https://frontend-production-341a.up.railway.app |
| Backend | https://backend-production-1827.up.railway.app |
| Database | PostgreSQL (internal: postgres.railway.internal:5432) |

**Login:** demo@example.com / demo123

### Deployment Architecture
- **PostgreSQL** — Railway managed plugin, DATABASE_URL auto-injected
- **Backend** — Python 3.12-slim Docker image, uvicorn, PORT from env var. Lifespan handler auto-runs Alembic migrations and seeds demo data on first boot.
- **Frontend** — Multi-stage Docker build (Node 20 → nginx:alpine). CRA build with `REACT_APP_API_URL` injected at build time. nginx serves static files with SPA fallback routing. PORT dynamically configured via sed at container start.

### Deployment Workflow
Code changes deploy via `railway up` from the respective service directory:
```bash
cd backend && railway up . --service backend --path-as-root
cd frontend && railway up . --service frontend --path-as-root
```

Environment variables are managed via Railway CLI:
```bash
railway variable set --service backend KEY=value
railway variable set --service frontend KEY=value
```

### Environment Variables (Railway)
| Service | Variable | Source |
|---------|----------|--------|
| Backend | DATABASE_URL | Railway Postgres plugin |
| Backend | ANTHROPIC_API_KEY | Manual (secret) |
| Backend | SECRET_KEY | Auto-generated (openssl rand -hex 32) |
| Backend | PORT | 8000 |
| Backend | CORS_ORIGINS | Frontend domain + localhost |
| Frontend | REACT_APP_API_URL | Backend public URL + /api/v1 |
| Frontend | PORT | 80 |

---

## Build Stats

| Metric | Value |
|--------|-------|
| Total files | 131+ |
| Lines of code | 13,454+ |
| Backend tests | 203 passing |
| Test suites | 7 (reconciliation, metrics, flags, claude client, diagnostic, action plan, narrative, viz data, auth) |
| API endpoints | 28+ |
| Database tables | 14 |
| Seed data | 156 units, 9 comp properties, 72 rent observations, 16 snapshots |
| Engine performance | 9.7ms for full property metrics |
| Frontend components | 30+ (8 chart components, 11 slide components, dashboard, config editor, comp management, experiment tracking) |

---

## The Workflow

```
Login
  → Portfolio Dashboard (KPIs, charts, trends, filterable by property/unit type)
    → Click Property
      → Property Overview (rent stack, spreads, LTL, exposure, demand, trend charts)
        → AI Review tab
          → "Get AI Review" button
            → Flags + Diagnosis + Action Plan shown inline
              → "Present as Slideshow" (optional — 12-slide consulting deck)
        → Config tab (sliders, preview diagnosis, save & activate)
        → Comps tab (comp list, refresh, trends)
        → Experiments tab (approve, cancel, track outcomes)
```

The slideshow is a **presentation export**, not the primary interface. The primary interface is a consultant-style review: see your data first, then ask the AI for its opinion.

---

## What Makes This Different

1. **Three-layer architecture** — deterministic math + configurable thresholds + intelligent judgment, each independently testable
2. **MAB price experimentation** — no other multifamily RM tool does this
3. **White-box transparency** — every recommendation shows its reasoning, every number traces to a computation
4. **Regulatory-first design** — built for the post-DOJ world, not retrofitted
5. **Claude for judgment, Python for math** — LLMs generate narrative and diagnosis, never dollar amounts
6. **Client-configurable everything** — same engine, different thresholds = different diagnosis. Your strategy, not ours.
