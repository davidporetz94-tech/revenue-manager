# RoboRev — Multi-Agent Codebase Audit

**Date:** 2026-03-20
**Methodology:** 7 specialized agents audited the codebase simultaneously, each adopting a persona from `agents.md`. Findings are compiled and ranked by severity.

---

## Findings by Severity

### TIER 1: CRITICAL (Fix Before Any Real Customer Data)

| # | Agent | Finding | Impact |
|---|-------|---------|--------|
| C1 | Compliance | **Cross-org data leakage in diagnostic endpoints** — `GET /diagnostic/{run_id}` and `GET /diagnostic/{run_id}/slides` return data without organization_id filtering. Any authenticated user can read another org's diagnostics by UUID. | DOJ settlement violation. Competitor harvests pricing intelligence. |
| C2 | API Architect | **Property endpoints missing org_id filter** — `GET /properties/{id}`, `GET /properties/{id}/summary`, `GET /properties/{id}/snapshots` query by ID only, no org check. Some have no auth at all. | Cross-org property metadata, metrics, and historical trends exposed. |
| C3 | Compliance | **Comp refresh crosses all organizations** — `POST /comps/refresh` iterates ALL active comp properties globally. One org's refresh pollutes another's comp data. | Data corruption across tenants. Audit trail shows wrong org. |
| C4 | API Architect | **Config endpoints missing ownership validation** — `GET/POST /properties/{id}/config` don't verify the property belongs to the user's org. An attacker can read/overwrite another org's business strategy. | Config poisoning. Business plan exfiltration. |
| C5 | API Architect | **Experiment assignment update has no auth** — `PUT /experiments/{id}/assignments/{aid}` has no user dependency. Anyone can falsify experiment outcomes. | Operators can't trust experiment data. |
| C6 | Test Engineer | **No tests for async diagnostic flow** — Background thread completion, failure handling, and DB cleanup are completely untested. | Silent production failures. No CI safety net. |
| C7 | Test Engineer | **Chat endpoint has zero test coverage** — 192 lines including Claude API calls, metrics computation, and audit logging — all untested. | Chat feature is a black box. |

**Common root cause (C1–C5):** The codebase uses `_get_demo_user()` instead of proper `get_current_user` dependency injection on many endpoints, and most `{property_id}` routes don't validate the property belongs to the requesting user's organization.

**Remediation:** ~2 hours. Add org_id filter to all property/config/snapshot/diagnostic/comp queries. Replace `_get_demo_user()` with `get_current_user`.

---

### TIER 2: HIGH (Fix Before Production Use)

| # | Agent | Finding | Impact |
|---|-------|---------|--------|
| H1 | RM Analyst | **Exposure trend not treated as urgent signal** — EXPOSURE_DETERIORATING is HIGH severity, not CRITICAL. By the time exposure crosses 20% (crisis), 2-3 weeks of leasing time are lost. | Late action on early warnings. |
| H2 | RM Analyst | **Occupancy crisis threshold (82%) too lenient** — Industry standard for stabilized assets is 85%. A unit type declining 88% → 85% → 82% won't get flagged until 82%. | 4-6 weeks of missed pricing optionality. |
| H3 | RM Analyst | **MAB eligibility contradicts diagnosis grade** — B1 at 79% is MAB-eligible (>75%) but diagnosed CRISIS ("direct action, not experiments"). Conflicting recommendations. | Operator confusion. Either experiments or cuts, not both. |
| H4 | Prompt Engineer | **Action plan prompt missing pre-computed dollar impacts** — Prompt says "all amounts are pre-computed" but user message doesn't include per-action expected impacts. Claude must hallucinate them. | Fabricated dollar amounts in action plans. |
| H5 | Prompt Engineer | **Portfolio action plan same issue** — Missing `revenue_facts_by_property` in portfolio action plan user message. | Hallucinated portfolio-level impacts. |
| H6 | Data Engineer | **Float columns store monetary values** — 14+ monetary fields use `Float` instead of `Numeric(10,2)`. IEEE 754 precision loss compounds in aggregates. | Penny-level drift at scale. $0.01 errors across 1000s of units. |
| H7 | API Architect | **Demo user fallback in auth dependency** — `get_current_user` silently returns demo user if no JWT provided. Unsafe in production. | Unauthenticated access masquerading as demo user. |
| H8 | API Architect | **Chat endpoint synchronous Claude call** — 25s timeout ties up a FastAPI worker thread. Multiple slow requests exhaust workers. | Service becomes unresponsive under load. |
| H9 | Frontend | **Memory leaks from uncleaned polling intervals** — `PortfolioDashboard.jsx` uses `setInterval` without cleanup on unmount. Multiple diagnostic runs stack intervals. | Browser memory grows, API quota wasted. |
| H10 | Test Engineer | **No tests for revenue gap exact values** — Gap decomposition uses generous tolerance. 5-10% drift won't be caught. | Operators get plausible but incorrect revenue estimates. |
| H11 | Test Engineer | **Missing fallback diagnosis edge case tests** — Empty revenue_efficiency, missing revenue_gap, zero unit types — none tested. | Malformed fallback output in degraded scenarios. |

---

### TIER 3: MEDIUM (Fix in Next Sprint)

| # | Agent | Finding | Impact |
|---|-------|---------|--------|
| M1 | RM Analyst | **Vacancy cost penalty too aggressive** — 50% penalty in crisis zone uses fixed percentage, not actual turnover cost model. Rejects price cuts that would improve economics. | Optimizer recommends HOLD when CUT is clearly better. |
| M2 | RM Analyst | **Renewal freeze ignores concession drag** — Freezes at occ < 82% but ignores units propped up by concessions. 88% occ with $2K/mo concession drag is worse than 82% without. | Renewal increases on artificially inflated occupancy. |
| M3 | RM Analyst | **Elasticity confidence ignores seasonality** — 3-month off-peak sample (Dec-Feb) gets MEDIUM confidence, but misses seasonal dynamics. Price tests launched in peak succeed for wrong reasons. | False confidence in price elasticity estimates. |
| M4 | RM Analyst | **Revenue efficiency grade boundaries misaligned** — Score 60 = "OPPORTUNITY" implies optional improvement, but a 60-score unit type is leaving $2K+/month on the table. | Grade language understates urgency. |
| M5 | RM Analyst | **Concession removal thresholds too strict** — Requires occ ≥ 93% AND exp < 10%. Almost never met simultaneously. Operators rarely see the flag. | Concession drag persists longer than necessary. |
| M6 | Data Engineer | **round() used instead of round_half_up() in 3 seed locations** — seed_units.py:300, seed_units.py:332, seed_snapshots.py:140. Currently correct by luck, fragile under different data. | Future seed data changes may silently break reconciliation. |
| M7 | Prompt Engineer | **No Pydantic validation on Claude diagnosis responses** — Raw dict returned from `call_json()` without schema validation. Partial/malformed Claude output passes silently. | Incomplete diagnosis data shown to operators. |
| M8 | Prompt Engineer | **No explicit markdown ban in narrative prompts** — Fallback generates plain text, but Claude prompt doesn't enforce it. Claude may return markdown. | Inconsistent formatting between Claude and fallback narratives. |
| M9 | Frontend | **Missing error boundaries around slide components** — If a slide component throws, entire slideshow crashes. FallbackSlide exists but no React ErrorBoundary wraps the dynamic component. | One broken slide kills the entire presentation. |
| M10 | Frontend | **Incomplete loading state coverage** — Chat message send, renewal rule save, experiment approval — all lack disable-on-click or loading indicators. | Double-submissions on slow connections. |
| M11 | Frontend | **Silent .catch() blocks** — PortfolioDashboard:66, PricingReview:47 swallow errors. User sees empty state, not error message. | "Loading forever" UX on failed API calls. |
| M12 | Frontend | **Missing ARIA labels** — 12+ slider inputs, chat input, tab navigation, and several buttons lack accessible labels. | Screen reader users cannot operate config editor or understand slide position. |
| M13 | Compliance | **Seed script deletes audit log** — `seed_all.py` runs `db.query(AuditLog).delete()`. If accidentally run in production, erases audit trail. | Audit trail integrity violation. |
| M14 | Test Engineer | **No portfolio diagnostic tests** — Portfolio diagnostic service and endpoint have zero test coverage. | Portfolio feature is untested in CI. |
| M15 | Test Engineer | **Claude mock is fragile** — `side_effect=[MOCK_A, MOCK_B]` hardcodes exactly 2 calls. If flow changes to 3 calls, tests crash with StopIteration. | Brittle tests that break on refactor. |
| M16 | RM Analyst | **Demand-occupancy divergence flag gated on occ < 92%** — 95% occ with softening demand (0.75 score) won't be flagged, even though divergence signals market shift. | Missed early warning at high occupancy. |
| M17 | Data Engineer | **Missing FK indexes** — `diagnostic_runs.property_id`, `diagnostic_runs.config_id`, `experiment_assignments.unit_id` lack indexes. | Sequential scans at scale (100K+ units). |

---

### TIER 4: LOW (Nice-to-Have / Polish)

| # | Agent | Finding | Impact |
|---|-------|---------|--------|
| L1 | RM Analyst | **LTL doesn't distinguish actionable vs potential** — HIGH_LTL_CAPTURE requires occ ≥ 88%. 10% LTL at 85% occ isn't flagged even though the potential exists. | Missed LTL capture communication. |
| L2 | RM Analyst | **Revenue gap double-counts renewal LTL** — `in_place_underpricing` (all occupied × LTL) + `renewal_opportunity` (renewals × LTL) overlap. Gap appears larger than actionable. | Inflated gap estimates. |
| L3 | RM Analyst | **Seasonal adjustment applied in crisis zone** — B1 at 79% gets +1% seasonal bump approaching peak. Should be $0 — fill first, price later. | Mixed signals on crisis pricing posture. |
| L4 | RM Analyst | **Pricing tolerance hardcodes** — `exec_diff > 50`, `monthly_burn > 5000` are inline constants, not config-driven. | No operator customization for these flags. |
| L5 | RM Analyst | **Renewal increase decision table hardcoded** — 5%/3.5%/2.5% schedule not in config. | Operators can't customize renewal aggressiveness. |
| L6 | RM Analyst | **Portfolio efficiency blend (60/40) is arbitrary** — No documentation explaining why 60% composite + 40% capture. | Opaque methodology. |
| L7 | Data Engineer | **Duplicated round_half_up in optimizer modules** — revenue_optimizer.py and renewal_optimizer.py have local copies instead of importing from utils.py. | Code duplication; updates won't propagate. |
| L8 | Data Engineer | **Seed data hardcodes REF_DATE = March 15, 2026** — If app runs in July 2026, lease dates will be in the past. | Stale seed data breaks seasonal logic. |
| L9 | Prompt Engineer | **Chat fallback message is generic** — "Unable to analyze right now" gives no context. | Poor UX on Claude failure. |
| L10 | Prompt Engineer | **Grade mapping not included in portfolio narrative prompt** — Claude may misinterpret grade thresholds. | Inconsistent narrative grading language. |
| L11 | Frontend | **Console.error without eslint-disable** — 6 locations. | ESLint warnings in strict CI. |
| L12 | Frontend | **Config slider inputs not debounced** — Preview invalidates on every pixel drag. | Minor UX friction. |
| L13 | Frontend | **No TypeScript** — All props untyped. | Runtime-only prop error detection. |
| L14 | Compliance | **net_effective_rent column exists but unused** — Stored as metadata on CompRent. Currently compliant, but could be misused. | Low risk if documented. |
| L15 | Test Engineer | **No 100% occupancy edge case tests** — Seed data never reaches 1.0 occ. | Unknown behavior at full occupancy. |
| L16 | Test Engineer | **B2 rounding trap not explicitly documented in tests** — Test passes but doesn't explain why 0.13 not 0.12. | Future maintainers may unknowingly break rounding. |

---

## Cross-Agent Consensus

Issues independently flagged by multiple agents carry higher confidence:

| Issue | Flagged By | Consensus |
|-------|-----------|-----------|
| **Multi-tenancy / org_id filtering** | API Architect, Compliance, RM Analyst | 3/7 agents — highest priority |
| **Demo user fallback** | API Architect, Compliance | 2/7 agents — production blocker |
| **Claude timeout / async handling** | API Architect, Prompt Engineer | 2/7 agents — UX/reliability |
| **Missing tests for new features** | Test Engineer, Frontend | 2/7 agents — CI safety |
| **Rounding inconsistency (round vs round_half_up)** | Data Engineer, RM Analyst | 2/7 agents — data integrity |
| **MAB eligibility vs diagnosis contradiction** | RM Analyst, Prompt Engineer | 2/7 agents — operator confusion |

---

## Remediation Effort Estimates

| Tier | Issues | Estimated Effort | Timeline |
|------|--------|-----------------|----------|
| CRITICAL | C1–C7 | 4-5 hours | Before any customer data |
| HIGH | H1–H11 | 8-12 hours | Before production launch |
| MEDIUM | M1–M17 | 15-20 hours | Next 2-week sprint |
| LOW | L1–L16 | 10-15 hours | Backlog / as-needed |

---

## Agent Summaries

### Revenue Management Analyst
*"The engine is methodologically sound with strong RM fundamentals. An operator would trust 80% of these recommendations. But the thresholds need tightening to prevent late action on early warnings, and the MAB/diagnosis contradiction will confuse operators."*

### Data Engineer
*"Data layer is production-ready with caveats. The balancing-unit seed approach is elegant and reconciliation is comprehensive. But Float columns should be Numeric, and 3 locations use Python's round() where round_half_up() is required."*

### API Architect
*"Strong foundational architecture with well-separated concerns. But 6 critical multi-tenancy gaps could expose customer data across organizations. The demo user fallback is a production time bomb."*

### Frontend Engineer
*"Charts are accurate, keyboard navigation works, no hardcoded data. But polling intervals leak memory, slide components lack error boundaries, and accessibility (ARIA labels) needs work."*

### Claude Prompt Engineer
*"Strong prompt engineering discipline — revenue math is correctly separated from Claude. But two prompts claim amounts are pre-computed without actually providing them, forcing Claude to hallucinate dollar impacts."*

### Compliance Officer
*"Strong regulatory foundations (append-only audit, public comps only, white-box reasoning) but the platform does NOT currently meet DOJ settlement compliance due to multi-tenancy isolation failures. ~1.5 hours of fixes would achieve compliance."*

### Test Engineer
*"Good coverage on core engine (203 tests). Critical gaps: async diagnostic flow untested, chat endpoint untested, export untested, portfolio diagnostics untested. Existing tests are solid but missing edge cases and exact-value assertions on revenue gaps."*
