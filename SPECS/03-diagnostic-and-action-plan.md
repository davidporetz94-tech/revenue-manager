# Spec 03: Diagnostic & Action Plan Logic

## 1. Goal

Build the diagnostic service (Layer 3) and action plan service that orchestrate the full pipeline: metrics → flags → Claude diagnosis → action plan → experiment designs. After this spec, calling `POST /properties/{id}/diagnostic/run` triggers the complete pipeline and stores results in `diagnostic_runs`. The diagnosis produces health scores, root causes, and recommendations for all unit types. The action plan produces a phased 30-day plan with MAB experiment designs. Both are stored as JSONB in the diagnostic_runs record.

**Measurable outcome:** A diagnostic run for Property A produces an action plan with experiments for A2. A diagnostic run for Property B produces crisis-level diagnosis for B1, a three-arm experiment for B2, and specific dollar-amount actions.

## 2. Exemplar

No direct exemplar for the diagnostic orchestration — this is the core IP. For the Claude prompt engineering pattern, reference Anthropic's structured output documentation (https://docs.anthropic.com/en/docs/build-with-claude/structured-output). Use the JSON mode patterns from the Claude API docs.

For the action plan data structure, reference the phased plan schema designed in Step 3 (action_plan_output_schema).

## 3. Constraints

- **Diagnostic service** orchestrates: metrics_engine → flag_generator → Claude API (diagnosis) → Claude API (action plan). Sequential execution, saving intermediate results to diagnostic_runs at each step.
- **Claude diagnosis prompt** must include: metrics JSON, flags JSON, client config, business plan summary, seasonal context (March 2026), historical trend data. System prompt enforces JSON output schema matching the diagnosis_json structure.
- **Claude action plan prompt** must include: diagnosis JSON, metrics JSON, client config, action taxonomy, MAB framework rules. System prompt enforces JSON output schema matching action_plan_json.
- **Revenue math is deterministic** — computed in Python, not by Claude. Vacancy costs, breakeven calculations, and net effective rent calculations are done before passing to Claude. Claude sequences and narrates but does not compute dollar amounts.
- **Experiment design rules** from MAB framework must be enforced:
  - Never experiment below min_occupancy_for_experiment (default 0.75)
  - Max price spread from config (default 6% or $100, whichever tighter)
  - Unit allocation rules: 2 vacant=1/1, 3=1/2, 4=2/2, 5=2/3, 6+=even or 3-way
  - Observation window from config (default 14 days)
- **Confidence → action mapping:** HIGH confidence = direct action, MEDIUM = experiment, LOW = investigate. This is guidance in the prompt, not hardcoded logic.
- All diagnostic_runs entries must have: metrics_json, flags_json, diagnosis_json, action_plan_json, status, timing fields.
- Every diagnostic run is logged in audit_log.
- API endpoint returns run_id immediately; frontend polls for completion.

### Claude Diagnosis Prompt (System)

```
You are a senior multifamily revenue management analyst. You receive structured metrics and flags from a pricing engine, along with the client's business plan context and threshold configuration. Produce:
1. Health score (0-100) per unit type WITH reasoning
2. Root cause analysis for underperforming unit types
3. Cross-portfolio pattern detection
4. Specific, actionable recommendations including experiment designs
5. Areas for further investigation

Score reflects alignment with CLIENT'S strategy, not abstract "health." Every recommendation must be auditable. When confidence is MEDIUM, prefer experiments over direct action. When LOW, prefer investigation.

Output valid JSON matching the diagnosis schema.
```

### Diagnosis Output Schema

```json
{
  "unit_type_assessments": [{
    "unit_type": "str",
    "health_score": "int 0-100",
    "score_reasoning": "str",
    "grade": "HEALTHY|WATCH|ACTION_NEEDED|CRITICAL",
    "root_cause": "str|null",
    "key_findings": ["str"],
    "anomalies": ["str"],
    "recommended_actions": [{
      "action_type": "str from taxonomy",
      "priority": "int",
      "description": "str",
      "target_value": "float|null",
      "expected_impact_monthly": "float|null",
      "confidence": "HIGH|MEDIUM|LOW",
      "reasoning": "str"
    }],
    "experiment_design": {
      "recommended": "bool",
      "arms": [{"label": "str", "price": "float", "units_allocated": "int"}],
      "observation_window_days": "int",
      "convergence_rule": "str",
      "rationale": "str"
    }
  }],
  "portfolio_assessment": {
    "property_a_summary": "str",
    "property_b_summary": "str",
    "cross_property_patterns": ["str"],
    "overall_portfolio_score": "int",
    "top_3_priorities": ["str"]
  },
  "further_investigation": [{
    "area": "str", "reason": "str", "data_needed": "str"
  }]
}
```

### Action Taxonomy (14 action types across 6 categories)

- **Pricing:** REDUCE_ASKING_RENT, INCREASE_ASKING_RENT, HOLD_ASKING_RENT
- **Concessions:** OFFER_MOVE_IN_CONCESSION, OFFER_LOOK_AND_LEASE, REMOVE_CONCESSION
- **Experiments:** LAUNCH_PRICE_EXPERIMENT, LAUNCH_CONCESSION_EXPERIMENT, CONVERGE_EXPERIMENT
- **Renewals:** SET_RENEWAL_INCREASE, FREEZE_RENEWAL_INCREASES
- **Lease terms:** ADJUST_PREFERRED_LEASE_TERM, OFFER_SHORT_TERM_PREMIUM
- **Audits:** AUDIT_AMENITY_PRICING, INVESTIGATE_NON_PRICE_FACTORS

### MAB Experiment Framework

- Two-arm default (control vs test), three-arm when 6+ vacant and two plausible price points
- Unit allocation: 2 vacant→1/1, 3→1/2, 4→2/2, 5→2/3, 6+→even or 3-way
- Price point selection: test between predicted and asking (or between comps and asking)
- Max spread from config (default 6% or $100, whichever tighter)
- Never test below predicted unless comp data strongly supports
- Observation window from config (default 14 days)
- Convergence: one arm leases ≥2x faster → winner. No difference → hold control. Neither leases → escalate to non-price investigation.
- Sequential experimentation for large gaps (B1's $91): test midpoint first, narrow by ~50% each stage
- Bayesian approach, not frequentist. Practical significance (5+ day velocity difference) over statistical significance.
- Guard rails: never experiment below min_occupancy (0.75), operator must approve, either arm can be pulled early if application received

### Mapped 30-Day Plan for the Case Study (4 Phases)

**Phase 1 (Days 1-3) — Immediate Stabilization:**
- P1-1: B1 reduce asking $1,525→$1,475 + 4 weeks free on 2 stalest units (net effective ~$1,377). Direct action, not experiment — CRITICAL flags + HIGH confidence.
- P1-2: B1 freeze renewal increases. Negative LTL means in-place tenants pay above market.
- P1-3: A2 price experiment: $1,411 control (2 units) vs $1,358 test (3 units). 14-day window.
- P1-4: B2 three-arm experiment: $1,654 control (2) vs $1,600 price test (2) vs $1,654+2wk free concession (2). 14-day window.

**Phase 2 (Days 4-14) — Calibrate & Optimize:**
- P2-1: A1 hold asking + push renewals to $1,332 (+5%). Offer 14-month lease terms.
- P2-2: B1 amenity audit ($125 premium at 8.2% — above 8% threshold).
- P2-3: B2 non-price investigation (tour conversion, unit condition, listing quality).
- P2-4: Portfolio-wide 14-month lease term preference (pushes March expirations to May peak).

**Phase 3 (Days 15-21) — Decision Point:**
- B1: ≥2 leased → hold $1,475. 0 leased → Stage 2 experiment at $1,434 (comps).
- A2: Test won → converge to $1,358. No diff → investigate non-price. Neither leased → deep concession test.
- B2: Price won → converge $1,600. Concession won → extend concession. No winner → redirect to non-price findings.

**Phase 4 (Days 22-30) — Optimize:**
- A1 spring push to $1,385-$1,395 if occupancy held
- A2/B1/B2 strategies locked based on Phase 3 outcomes
- Portfolio-wide renewal strategy update
- Config calibration from month's outcome data

### Revenue at Risk

- A1: $2,730/mo (2 vacant × $1,365)
- A2: $7,055/mo (5 × $1,411)
- B1: $7,625/mo (5 × $1,525)
- B2: $9,924/mo (6 × $1,654)
- Total: $27,334/mo = $328,008/year. Daily burn: $911/day.

## 4. Anti-Patterns

- **Do NOT** let Claude compute dollar amounts. All revenue math (vacancy cost, breakeven, net effective rent) must be pre-computed in Python and passed to Claude as facts.
- **Do NOT** hardcode the "right answers" for the four unit types. The engine must derive them from the data + config. If someone changes the config thresholds, the diagnosis should change accordingly.
- **Do NOT** skip Claude response validation. Parse the JSON, validate against the expected schema (Pydantic), and handle missing/extra fields gracefully.
- **Do NOT** store raw Claude API responses. Parse, validate, and store the clean structured JSON.
- **Do NOT** make the diagnostic endpoint blocking for >30 seconds. If Claude is slow, the endpoint should return the run_id and let the frontend poll. Set a reasonable timeout (30s per Claude call, 90s total).
- **Do NOT** create experiments for unit types with <3 vacant units (unless config overrides).

## 5. Scenarios

1. **Full diagnostic for Property B with default config:**
   - B1 gets grade CRITICAL, health score <30
   - B1 actions include REDUCE_ASKING_RENT ($1,475 target) and FREEZE_RENEWAL_INCREASES
   - B1 experiment is eligible (5 vacant, 0.79 occ > 0.75 floor) but direct action preferred due to CRITICAL flags
   - B2 gets grade ACTION_NEEDED, health score 55-65
   - B2 experiment recommended: three-arm (price test + concession test + control), 2 units each
   - Action plan has 4 phases with Day 15 decision point

2. **Full diagnostic for Property A with default config:**
   - A1 gets grade HEALTHY, health score >80
   - A1 actions: HOLD_ASKING_RENT + SET_RENEWAL_INCREASE (target ~$1,332)
   - A2 gets grade ACTION_NEEDED, health score 50-65
   - A2 experiment recommended: $1,411 (control, 2 units) vs $1,358 (test, 3 units)
   - Action plan phases sequence A2 experiment in Phase 1, A1 optimization in Phase 2

3. **Diagnostic with value-add config (looser thresholds):**
   - B1 at 79% occupancy reads as ACTION_REQUIRED (not CRISIS) since crisis_below=0.72
   - Experiment more likely to be recommended over direct price cut
   - Same metrics, different diagnosis

4. **Experiment design validation for B2:**
   - 6 vacant units → three-arm eligible
   - Price spread: $1,654 to $1,600 = $54 (3.3%) — within 6% config max
   - Concession arm: $1,654 with 2 weeks free → net effective ~$1,536
   - Observation window: 14 days
   - Each arm gets 2 units
   - Convergence rule specified for all three outcomes (price wins, concession wins, no winner)

5. **Edge case — 100% occupancy:** If a unit type has 0 vacant and 0 on-notice units, the engine should produce OCCUPANCY_PUSH_ELIGIBLE flag, no experiment (nothing to experiment on), and recommend pushing asking rent for the next vacancy.

6. **Claude API failure:** If Claude call fails after retry, diagnostic_runs.status='FAILED', error_message populated. Frontend shows error state.

## 6. Convergence Criteria

- [ ] `POST /api/v1/properties/{property_b_id}/diagnostic/run` completes within 30 seconds
- [ ] `GET /api/v1/diagnostic/{run_id}` returns status=COMPLETED with all JSON fields populated
- [ ] diagnosis_json contains unit_type_assessments for both B1 and B2 with health_score, grade, recommended_actions, and experiment_design fields
- [ ] action_plan_json contains 4 phases, with Phase 1 including the B1 price cut and B2 experiment
- [ ] B1 diagnosis flags CRITICAL severity; B2 does not
- [ ] Experiment designs respect config constraints (price spread, min vacant, observation window)
- [ ] `pytest tests/test_diagnostic_service.py` passes — can use mocked Claude responses to test the full pipeline deterministically
- [ ] `pytest tests/test_action_plan.py` passes — validates revenue math, experiment allocation, and phase sequencing
- [ ] audit_log contains entry for every diagnostic run
- [ ] Re-running diagnostic with different config produces different diagnosis (test with value-add config)
