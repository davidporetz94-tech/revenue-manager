# EXEMPLARS — Gene-Transfusion References

## Philosophy

**Gene-transfusion, not cloning.** Study each exemplar for its structural patterns and conventions. Adapt what fits our domain. Never copy wholesale — these are inspirations, not templates.

---

## Spec 01: Data Model & Dummy Data

### Primary: benavlabs/FastAPI-boilerplate
- **URL:** https://github.com/benavlabs/FastAPI-boilerplate
- **Transfuse:** Project structure, SQLAlchemy 2.0 `mapped_column` patterns, Alembic config setup, `models/` and `schemas/` organization, env/config management with Pydantic Settings
- **Adapt:** Their generic CRUD patterns → our domain-specific models (properties, units, comps, configs). Their auth model → our JWT + organization multi-tenancy pattern
- **Ignore:** Their async setup (sync is fine for MVP), their Redis/caching layer, their Docker complexity

### Secondary: tiangolo/full-stack-fastapi-template
- **URL:** https://github.com/fastapi/full-stack-fastapi-template
- **Transfuse:** User/auth model pattern, multi-tenancy filtering approach, Alembic migration conventions
- **Adapt:** Their `owner_id` pattern → our `organization_id` pattern on every table
- **Ignore:** Their frontend (we use React + Tailwind, not their stack), their email/celery setup

### Gene-Transfusion Instructions for Spec 01
1. Study the boilerplate's `models/` directory — note how they use `mapped_column` with type annotations
2. Study their `alembic/env.py` — note how they configure the target metadata and database URL
3. Study their `config.py` — note how they use `pydantic_settings.BaseSettings` for environment variables
4. Apply these patterns to our 14-table schema. Every table uses UUID PKs, every query filters by `organization_id`
5. Do NOT use their CRUD generic classes — our domain logic is too specific

---

## Spec 02: Core Pricing Engine

### Primary: Anthropic Python SDK
- **URL:** https://github.com/anthropics/anthropic-sdk-python
- **Transfuse:** Client initialization pattern, message creation, content block parsing, error handling types
- **Adapt:** Wrap in a `ClaudeClient` service class with retry logic, JSON extraction, and Pydantic validation
- **Ignore:** Streaming (not needed for structured JSON output), tool use (not needed at this stage)

### Gene-Transfusion Instructions for Spec 02
1. Study the SDK's `client.messages.create()` call pattern
2. Note how response content is a list of content blocks — filter for `type == "text"`
3. Build a wrapper that: accepts system + user prompts, calls the API, extracts text, strips markdown fences, parses JSON, validates against Pydantic schema, retries once on failure
4. The engine modules themselves have no exemplar — they are pure domain logic. Structure as `app/engine/` with one module per methodology, each exporting pure functions that take dicts in and return dicts out

---

## Spec 03: Diagnostic & Action Plan

### Primary: Anthropic Structured Output Documentation
- **URL:** https://docs.anthropic.com/en/docs/build-with-claude/structured-output
- **Transfuse:** JSON schema enforcement patterns, system prompt structure for reliable JSON output, handling of partial/malformed responses
- **Adapt:** Build two separate Claude calls (diagnosis + action plan) that each produce validated JSON matching our schemas
- **Ignore:** Tool use patterns (we use direct JSON output, not tool-call-based structured output)

### Gene-Transfusion Instructions for Spec 03
1. Study the structured output docs — note the pattern of defining the exact JSON schema in the system prompt and requesting "Output valid JSON matching this schema"
2. Build the diagnostic service as an orchestrator: it calls metrics_engine, then flag_generator, then Claude (diagnosis), then Claude (action plan), saving intermediate results to diagnostic_runs at each step
3. Revenue math (vacancy costs, breakeven calculations) must be computed in Python BEFORE the Claude calls and passed as facts
4. No exemplar exists for the MAB experiment design logic — this is custom domain IP

---

## Spec 04: AI Narrative Layer

### Primary: Anthropic Structured Output Documentation (same as Spec 03)
- **Transfuse:** Same JSON output patterns, applied to per-slide narrative text generation
- **Adapt:** Two sub-calls — diagnostic narrative (slides 2-7, 11-12) and action plan narrative (slides 8-10)

### Gene-Transfusion Instructions for Spec 04
1. The narrative service is a thin layer on top of the Claude client — it constructs prompts from diagnosis/action plan data and parses the response into per-slide text
2. The viz_data_service is pure Python data reshaping — no exemplar needed. For each of the 14 visualization types, write a function that takes metrics and returns a Recharts-compatible data structure
3. Fallback narratives are template strings filled with metrics values — simple string formatting

---

## Spec 05: Interactive Slideshow UI

### Primary (Inspiration): bvaughn/react-presents
- **URL:** https://github.com/bvaughn/react-presents
- **Transfuse:** The concept of a `Presentation` → `Slide` component hierarchy. Keyboard navigation pattern (arrow keys). URL-based slide routing concept
- **Adapt:** Strip to bare minimum — we need: a container that holds N slides, arrow key navigation, a slide counter, and slide transitions. No presenter mode, no code highlighting, no complex routing
- **Ignore:** Their entire styling system, their code slide components, their overview mode

### Secondary (Charts): luck18210/react-tailwind-dashboard
- **URL:** https://github.com/luck18210/react-tailwind-dashboard
- **Transfuse:** Recharts + Tailwind layout patterns. How they wrap charts in `ResponsiveContainer`. Card layout patterns
- **Adapt:** Their dashboard card → our slide content containers. Their chart components → our custom chart components (ScoreGauge, RentWaterfall, etc.)
- **Ignore:** Their sidebar/navigation (we build our own for the platform shell)

### Tertiary: Recharts Official Docs
- **URL:** https://recharts.org/
- **Transfuse:** `BarChart`, `LineChart`, `ResponsiveContainer` usage. Dual y-axis pattern for `TrendLineChart`
- **Key patterns:**
  - Always wrap in `<ResponsiveContainer width="100%" height={300}>`
  - Use `<CartesianGrid strokeDasharray="3 3" />` for backgrounds
  - For dual axes: `<YAxis yAxisId="left" />` and `<YAxis yAxisId="right" orientation="right" />`
  - For tooltips: `<Tooltip formatter={(value) => formatDollar(value)} />`

### Gene-Transfusion Instructions for Spec 05
1. Build `SlideshowViewer` first — the container that manages slide state and keyboard events
2. Build chart components second — each one is standalone, receives data props, returns JSX
3. Build slide components third — each one composes charts + narrative text
4. The slideshow is the PRIMARY deliverable. Get it working before building dashboard chrome
5. Use CSS transitions for slide changes — no animation libraries

---

## Spec 06: Auth, Historical Tracking & Platform Shell

### Primary: tecelit/fast-api-boilerplate
- **URL:** https://github.com/tecelit/fast-api-boilerplate
- **Transfuse:** JWT auth flow (bcrypt hashing, token creation, FastAPI dependency injection). `get_current_user` dependency pattern. Role-based access control
- **Adapt:** Their user model → our users + organizations model. Their simple auth → our multi-tenant auth where every query filters by `organization_id` from the JWT payload
- **Ignore:** Their database setup (we already have ours from Spec 01), their non-auth routes

### Secondary: luck18210/react-tailwind-dashboard (same as Spec 05)
- **Transfuse:** Sidebar + main content layout. Navigation pattern. Card-based dashboard layout
- **Adapt:** Their sidebar → our Properties → Property Detail → Sub-tabs navigation hierarchy

### Gene-Transfusion Instructions for Spec 06
1. Build backend auth first (register, login, get_current_user dependency)
2. Build frontend auth second (login page, auth context, protected routes)
3. Build platform shell third (sidebar, header, navigation)
4. Build config editor fourth (forms with sliders, preview functionality)
5. Build comp management and experiment tracking last
6. The config "Preview Diagnosis" feature is a key differentiator — it calls the flag generator with a draft config and shows how many flags would fire. Don't skip this.

---

## General Gene-Transfusion Rules

1. **Read the exemplar's README first** — understand their architecture decisions
2. **Study their directory structure** — adapt the organizational pattern to our domain
3. **Look at their imports** — note which libraries they use and how
4. **Study one complete flow** — e.g., in the auth boilerplate, trace from route → service → model → response
5. **Never copy-paste code** — understand the pattern, then write fresh code that fits our specific schema and domain
6. **Our domain is unusual** — multifamily revenue management with regulatory compliance requirements. No exemplar will have this. The exemplars provide structural patterns only; the domain logic is ours.
