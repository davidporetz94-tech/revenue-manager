# Bootstrap Instructions — Layer 0 (Claude Code Execution)

## Persistent Context Block

```
┌─────────────────────────────────────────────────────────────────────┐
│ PERSISTENT CONTEXT — DO NOT MODIFY, DO NOT IGNORE                  │
│                                                                     │
│ YOUR LAYER: Layer 0 (Execution)                                     │
│ YOUR JOB: Bootstrap the project infrastructure, then execute specs  │
│   using convergence loops                                           │
│ YOUR DELIVERABLE: Working product, validated against holdout        │
│   scenarios                                                         │
│ NEXT LAYER: None — you are the final executor                      │
│                                                                     │
│ CRITICAL RULES:                                                     │
│ • You ARE the executor. Build the product.                         │
│ • Follow the CLAUDE.md for project context and rules.              │
│ • Execute specs from SPECS/ in the order given in execution-plan.  │
│ • Validate against holdout-scenarios/ after each spec.             │
│ • Use EXEMPLARS/ for gene-transfusion of proven patterns.          │
│ • Run convergence loops until satisfaction criteria are met.        │
│ • Read agents.md and adopt the right persona before each task.     │
│ • Update progress.md after EVERY action. No exceptions.            │
│ • Update decisions.md BEFORE implementing any decision.            │
│                                                                     │
│ EXECUTION SEQUENCE:                                                 │
│ 1. Run /user:bootstrap-playbook to initialize infrastructure       │
│ 2. Enhance CLAUDE.md with the additions in this file               │
│ 3. Copy specs into SPECS/, scenarios into holdout-scenarios/       │
│ 4. Read agents.md — adopt the right persona for each task          │
│ 5. Execute specs in order per execution-plan.md                    │
│ 6. For each spec: /user:converge <spec-name>                      │
│ 7. After each action: update progress.md                           │
│ 8. Before each decision: update decisions.md                       │
│ 9. After each phase: update CLAUDE.md, refresh pyramid summaries   │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Step 0: Prerequisites

Before starting, ensure the following are available in the project root:

| File | Purpose |
|------|---------|
| `CLAUDE.md` | Project context (from this artifact set) |
| `SPECS/01-data-model-and-dummy-data.md` | Spec 01 |
| `SPECS/02-core-pricing-engine.md` | Spec 02 |
| `SPECS/03-diagnostic-and-action-plan.md` | Spec 03 |
| `SPECS/04-ai-narrative-layer.md` | Spec 04 |
| `SPECS/05-interactive-slideshow-ui.md` | Spec 05 |
| `SPECS/06-auth-historical-platform-shell.md` | Spec 06 |
| `holdout-scenarios/01-data-scenarios.md` | Holdout scenarios for Spec 01 |
| `holdout-scenarios/02-pricing-engine-scenarios.md` | Holdout scenarios for Spec 02 |
| `holdout-scenarios/03-diagnostic-scenarios.md` | Holdout scenarios for Spec 03 |
| `holdout-scenarios/04-narrative-scenarios.md` | Holdout scenarios for Spec 04 |
| `holdout-scenarios/05-slideshow-scenarios.md` | Holdout scenarios for Spec 05 |
| `holdout-scenarios/06-platform-scenarios.md` | Holdout scenarios for Spec 06 |
| `EXEMPLARS/README.md` | Gene-transfusion references |
| `execution-plan.md` | Phased execution plan |
| `progress.md` | Running work log — MUST update after every action |
| `decisions.md` | Decision log — MUST update before every decision |
| `agents.md` | Agent personas — read before every task |
| `EliseAI_Pricing_Export.xlsx` | Ground truth data |
| `EliseAI_Revenue_Manager_Practical.pdf` | Case study assignment |
| `Multifamily_Revenue_Management__The_Complete_Landscape_in_2026.md` | Domain knowledge |

---

## Step 1: Bootstrap Playbook

Run these commands to initialize the project infrastructure:

```bash
# 1. Create project root
mkdir -p multifamily-rm
cd multifamily-rm

# 2. Create directory structure
mkdir -p backend/app/{models,schemas,api,services,engine,auth,seed}
mkdir -p backend/alembic/versions
mkdir -p backend/tests
mkdir -p frontend/src/{api,auth,utils}
mkdir -p frontend/src/components/{layout,dashboard,config,slideshow/{slides,charts}}
mkdir -p frontend/public
mkdir -p SPECS holdout-scenarios EXEMPLARS

# 3. Initialize WORKLOG.md
cat > WORKLOG.md << 'EOF'
# WORKLOG — Multifamily Revenue Management Platform

## Status: BOOTSTRAPPING

### Phase 1: Foundation (Spec 01)
- [ ] Database schema (14 tables)
- [ ] Alembic migrations
- [ ] Seed scripts
- [ ] Reconciliation tests (56+ assertions)

### Phase 2A: Pricing Engine (Spec 02)
- [ ] Engine modules (8 pure function modules)
- [ ] Flag generator (20+ rules)
- [ ] Claude API client wrapper
- [ ] Metrics + flag tests

### Phase 2B: Auth & Platform Shell (Spec 06)
- [ ] JWT auth backend
- [ ] Frontend auth + shell
- [ ] Config editor
- [ ] Comp management
- [ ] Experiment tracking

### Phase 3: Diagnostic Pipeline (Spec 03)
- [ ] Diagnostic service orchestration
- [ ] Action plan service
- [ ] MAB experiment design
- [ ] API endpoints

### Phase 4: Narrative Layer (Spec 04)
- [ ] Narrative service (2 Claude calls)
- [ ] Viz data service (14 generators)
- [ ] Slide deck assembly
- [ ] Consistency check + fallback

### Phase 5: Interactive Slideshow (Spec 05)
- [ ] SlideshowViewer
- [ ] 8 chart components
- [ ] 11 slide components
- [ ] Navigation + property switching

### Phase 6: Integration & Polish
- [ ] End-to-end walkthrough
- [ ] Docker compose
- [ ] Final validation
EOF

# 4. Initialize backend
cat > backend/requirements.txt << 'EOF'
fastapi==0.115.0
uvicorn[standard]==0.30.0
sqlalchemy==2.0.35
alembic==1.13.2
psycopg2-binary==2.9.9
pydantic==2.9.0
pydantic-settings==2.5.0
python-jose[cryptography]==3.3.0
passlib[bcrypt]==1.7.4
bcrypt==4.2.0
PyJWT==2.9.0
anthropic==0.34.0
python-multipart==0.0.9
httpx==0.27.0
pytest==8.3.0
pytest-asyncio==0.24.0
EOF

# 5. Initialize frontend
cat > frontend/package.json << 'PKGJSON'
{
  "name": "multifamily-rm-frontend",
  "version": "0.1.0",
  "private": true,
  "dependencies": {
    "react": "^18.3.0",
    "react-dom": "^18.3.0",
    "react-router-dom": "^6.26.0",
    "recharts": "^2.12.0",
    "axios": "^1.7.0",
    "react-scripts": "5.0.1",
    "tailwindcss": "^3.4.0",
    "autoprefixer": "^10.4.0",
    "postcss": "^8.4.0"
  },
  "scripts": {
    "start": "react-scripts start",
    "build": "react-scripts build",
    "test": "react-scripts test"
  },
  "browserslist": {
    "production": [">0.2%", "not dead", "not op_mini all"],
    "development": ["last 1 chrome version", "last 1 firefox version", "last 1 safari version"]
  }
}
PKGJSON

# 6. Create Tailwind config
cat > frontend/tailwind.config.js << 'TWCFG'
/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./src/**/*.{js,jsx,ts,tsx}"],
  theme: {
    extend: {
      colors: {
        crisis: '#DC2626',
        warning: '#D97706',
        caution: '#F59E0B',
        healthy: '#059669',
        positive: '#0D9488',
        experiment: '#7C3AED',
      }
    },
  },
  plugins: [],
}
TWCFG

# 7. Create PostCSS config
cat > frontend/postcss.config.js << 'PCSS'
module.exports = {
  plugins: {
    tailwindcss: {},
    autoprefixer: {},
  },
}
PCSS

# 8. Create .env template
cat > backend/.env.example << 'ENV'
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/multifamily_rm
ANTHROPIC_API_KEY=your-api-key-here
SECRET_KEY=your-jwt-secret-key-change-in-production
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440
ENV

# 9. Create docker-compose.yml
cat > docker-compose.yml << 'DOCKER'
version: '3.8'

services:
  db:
    image: postgres:15
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
      POSTGRES_DB: multifamily_rm
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data

  backend:
    build: ./backend
    ports:
      - "8000:8000"
    environment:
      DATABASE_URL: postgresql://postgres:postgres@db:5432/multifamily_rm
      ANTHROPIC_API_KEY: ${ANTHROPIC_API_KEY}
      SECRET_KEY: ${SECRET_KEY:-change-me-in-production}
    depends_on:
      - db
    volumes:
      - ./backend:/app

  frontend:
    build: ./frontend
    ports:
      - "3000:3000"
    environment:
      REACT_APP_API_URL: http://localhost:8000/api/v1
    depends_on:
      - backend

volumes:
  pgdata:
DOCKER

# 10. Create backend Dockerfile
cat > backend/Dockerfile << 'BDOCK'
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
BDOCK

# 11. Create frontend Dockerfile
cat > frontend/Dockerfile << 'FDOCK'
FROM node:18-slim
WORKDIR /app
COPY package.json .
RUN npm install
COPY . .
CMD ["npm", "start"]
FDOCK

# 12. Create .gitignore
cat > .gitignore << 'GIT'
__pycache__/
*.pyc
.env
node_modules/
build/
.pytest_cache/
*.egg-info/
dist/
venv/
.venv/
GIT

echo "Bootstrap complete. Project structure initialized."
```

---

## Step 2: CLAUDE.md Enhancements

After bootstrapping, add the following sections to the end of CLAUDE.md:

### Addition 1: Quick Reference — Reconciliation Targets

```markdown
## Quick Reference — Reconciliation Targets (copy into CLAUDE.md)

### Rent Pool Totals (sum of individual values must equal these)
| Unit Type | Amenity Total | In-Place Total | Asking Total |
|-----------|--------------|----------------|--------------|
| A1 | 48 × $89 = $4,272 | 46 × $1,269 = $58,374 | 3 × $1,365 = $4,095 |
| A2 | 36 × $83 = $2,988 | 31 × $1,304 = $40,424 | 6 × $1,411 = $8,466 |
| B1 | 24 × $125 = $3,000 | 19 × $1,572 = $29,868 | 6 × $1,525 = $9,150 |
| B2 | 48 × $118 = $5,664 | 42 × $1,608 = $67,536 | 6 × $1,654 = $9,924 |

### Pre-Computed Unit-Level Values
| Metric | A1 | A2 | B1 | B2 |
|--------|----|----|----|----|
| Executed | [1290,1310,1340,1356] | [1370,1385,1400,1413] | [1630,1660,1675] | [1640,1650,1660,1670,1675] |
| DOM | [15,26,31] | [8,14,18,24,28,40] | [10,18,22,28,32,40] | [18,22,28,32,36,44] |
| DV | [12,22] | [7,10,14,22,27] | [10,15,18,25,32] | [16,20,26,30,34,42] |
```

### Addition 2: Current Spec Status Tracker

```markdown
## Current Status (update after each spec)

| Spec | Status | Tests Passing | Notes |
|------|--------|---------------|-------|
| 01 | NOT STARTED | — | — |
| 02 | NOT STARTED | — | — |
| 03 | NOT STARTED | — | — |
| 04 | NOT STARTED | — | — |
| 05 | NOT STARTED | — | — |
| 06 | NOT STARTED | — | — |
```

---

## Step 3: Convergence Loop Protocol

For each spec, follow this exact sequence:

### 3.1: Pre-Read Phase
```
1. Read CLAUDE.md (project context)
2. Read agents.md → adopt the right persona for this spec
3. Read the spec file (SPECS/0X-*.md) — read COMPLETELY, don't skim
4. Read the holdout scenario file (holdout-scenarios/0X-*.md)
5. Read the EXEMPLARS/README.md section for this spec
6. Identify the convergence criteria (checkboxes at end of spec)
```

### 3.2: Implementation Phase
```
1. If any decisions are needed → log in decisions.md BEFORE implementing
2. Create all files specified in the spec
3. Implement functionality
4. Write tests that match the convergence criteria
5. Run tests
6. Update progress.md with what was done
```

### 3.3: Convergence Phase
```
LOOP:
  Run ALL convergence criteria checks
  IF all pass:
    Mark spec as COMPLETE in progress.md
    Update CLAUDE.md status tracker
    BREAK
  ELSE:
    Identify failing check
    Diagnose root cause
    If fix requires a decision → log in decisions.md FIRST
    Fix
    Re-run ALL checks (not just the failing one)
    Update progress.md with the iteration
    CONTINUE LOOP
```

### 3.4: Holdout Validation Phase
```
Run each holdout scenario for this spec
Verify satisfaction criteria
Document any edge cases encountered
Update progress.md with final results
Verify decisions.md is current (any decisions made during convergence?)
```

---

## Step 4: Spec Execution Order

Follow this exact order (matches execution-plan.md):

```
Phase 1:  Spec 01 (Data Model & Dummy Data)          — BLOCKS everything
Phase 2A: Spec 02 (Core Pricing Engine)               — After Spec 01; parallel with 2B
Phase 2B: Spec 06 (Auth, Historical & Platform Shell)  — After Spec 01; parallel with 2A
Phase 3:  Spec 03 (Diagnostic & Action Plan)           — After Specs 01, 02
Phase 4:  Spec 04 (AI Narrative Layer)                 — After Spec 03
Phase 5:  Spec 05 (Interactive Slideshow UI)           — After Spec 04
Phase 6:  Integration & Polish                         — After all specs
```

---

## Step 5: Critical Reminders for Layer 0

### Living Documents
- `progress.md` gets an entry after EVERY action. No "I'll update it later." Update it NOW.
- `decisions.md` gets an entry BEFORE implementing any decision. Decide → log → build.
- `agents.md` gets read BEFORE starting any task. Adopt the right persona.
- If you realize you forgot to update progress.md or decisions.md, stop and backfill immediately.

### Data Integrity
- The EliseAI Pricing Export is the ground truth. Every number must tie.
- Use `round_half_up()` everywhere. Python's `round()` will produce wrong results for 0.125 → 0.12 instead of 0.13.
- The "balancing unit" approach: generate N-1 units realistically, set Nth to hit exact aggregate.

### Engine Purity
- `app/engine/` modules must have ZERO imports from SQLAlchemy, database, or ORM.
- Services query the DB, convert to plain dicts/dataclasses, pass to engine.
- Engine returns dicts. Services store results.

### Claude API
- Model: `claude-sonnet-4-20250514` for all calls
- All revenue math is computed in Python BEFORE Claude calls
- Claude generates TEXT and STRUCTURED JSON only — never chart data, never dollar calculations
- Validate every Claude response against Pydantic schema before storing

### Regulatory Compliance
- comp_rents table stores ONLY public asking rents. Never executed rents, occupancy, or concessions from competitors.
- audit_log is APPEND-ONLY. No update, no delete. Ever.
- Every diagnostic run, config change, experiment approval, and comp refresh is logged.
- organization_id filter on EVERY database query.

### Frontend Priority
- The slideshow is THE primary deliverable. Build it before dashboard chrome.
- Charts use Recharts with ResponsiveContainer on every chart.
- No state management library — React Context is sufficient.
- All data comes from the API. Zero hardcoded data in the frontend.

---

## Step 6: Post-Completion Checklist

After all specs pass convergence, run this final validation:

```
[ ] docker-compose up --build starts the full stack
[ ] Navigate to http://localhost:3000 — login screen appears
[ ] Login with demo@example.com / demo123
[ ] Property list shows Property A and Property B
[ ] Navigate to Property B dashboard — KPI cards show correct values
[ ] Click "Run Diagnostic" — loading state appears
[ ] Slideshow renders within 20 seconds with 12 slides
[ ] Navigate through all slides with arrow keys
[ ] Slide 2: Score gauge + KPI cards display correct values
[ ] Slide 3: Data table matches EliseAI Pricing Export exactly
[ ] Slide 5: B1 shows CRITICAL (red), waterfall shows $91 gap
[ ] Slide 7: Vacancy cost bar shows $27,334/mo total
[ ] Slide 9: Action cards + experiment diagram render
[ ] Slide 10: Decision trees show branching paths
[ ] Switch to Property A — data updates correctly
[ ] Navigate to Config tab — editor shows sliders for all sections
[ ] Click "Preview Diagnosis" — flag counts display (A1=3, A2=7, B1=12, B2=7)
[ ] Navigate to Comps tab — comp properties listed with rents
[ ] Navigate to Experiments tab — proposed experiments visible
[ ] All pytest suites pass
[ ] No console errors in browser at any point
[ ] progress.md has entries for every phase of work
[ ] decisions.md has entries for every decision made during execution
[ ] WORKLOG.md shows all specs COMPLETE
```

---

## Troubleshooting Common Issues

### Database connection fails
```bash
# Ensure PostgreSQL is running
docker-compose up db -d
# Wait 5 seconds for it to initialize
sleep 5
# Then run migrations
cd backend && alembic upgrade head
```

### Reconciliation test fails on B2 exposure
```
Expected: 0.13
Got: 0.12
Fix: You're using Python's round() instead of round_half_up(). 
6/48 = 0.125. round(0.125, 2) = 0.12 (banker's rounding).
round_half_up(0.125, 2) = 0.13 (correct).
```

### Claude API returns non-JSON
```
Fix: Strip markdown code fences before parsing.
response_text = response_text.strip()
if response_text.startswith("```json"):
    response_text = response_text[7:]
if response_text.startswith("```"):
    response_text = response_text[3:]
if response_text.endswith("```"):
    response_text = response_text[:-3]
```

### Frontend charts don't resize
```
Fix: Wrap EVERY Recharts chart in <ResponsiveContainer width="100%" height={N}>.
Without this wrapper, charts render at 0 width.
```

### Amenity premiums don't sum correctly
```
Fix: Use the balancing unit approach. Generate 47 A1 units with realistic amenity premiums,
then set the 48th unit's premium so the total equals exactly $4,272.
```
