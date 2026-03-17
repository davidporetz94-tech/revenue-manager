# Holdout Scenarios — Spec 03: Diagnostic & Action Plan

## Scenario 3.1: Correct Action Plan for Property B

**Setup:** Full diagnostic pipeline with default "Stabilized Balanced" config. Property B with B1 and B2 unit types.

**Trigger:** `POST /api/v1/properties/{property_b_id}/diagnostic/run`

**Expected flow:**
1. Metrics engine runs (~100ms) — produces metrics for B1 and B2
2. Flag generator runs (~10ms) — produces 12 flags for B1, 7 for B2
3. Claude diagnosis call (~4s) — returns:
   - B1: health_score < 35, grade=CRITICAL, root_cause mentions "$91 above comps" and "declining market"
   - B2: health_score 50-65, grade=ACTION_NEEDED, root_cause mentions "priced at comps but not leasing"
4. Action plan call (~4s) — returns 4-phase plan:
   - Phase 1 (Days 1-3): B1 price reduction (target ~$1,475) + B1 renewal freeze + B2 experiment launch
   - Phase 2 (Days 4-14): B1 amenity audit + B2 non-price investigation
   - Phase 3 (Days 15-21): Decision point with branching paths per B1/B2 outcomes
   - Phase 4 (Days 22-30): Optimization actions contingent on Phase 3 results
5. diagnostic_runs record saved with status=COMPLETED, all JSON fields populated

**Satisfaction criteria:**
- Run completes within 30 seconds
- B1 actions include at least one REDUCE_ASKING_RENT or OFFER_CONCESSION action
- B1 actions include FREEZE_RENEWAL_INCREASES
- B2 experiment has 2-3 arms (price test and/or concession test)
- B2 experiment allocates units respecting 6 vacant (2/2/2 or 3/3 split)
- Action plan has exactly 4 phases
- A Day 15 decision point exists with conditional branching
- Revenue at risk figures in action plan match metrics engine output
- audit_log contains RUN_DIAGNOSTIC entry

**Edge cases:**
- If Claude returns B1 experiment instead of direct action: validate that the engine's CRITICAL flags should have pushed toward direct action. The prompt instructs Claude to prefer direct action for CRITICAL+HIGH confidence situations — if it still recommends experiment, the prompt may need tuning.
- If Claude omits B1 renewal freeze: the NEGATIVE_LTL + RENEWAL_FREEZE_RECOMMENDED flags should have prompted this. Flag as a prompt quality issue.

---

## Scenario 3.2: Correct Action Plan for Property A

**Setup:** Same as 3.1 but for Property A.

**Trigger:** `POST /api/v1/properties/{property_a_id}/diagnostic/run`

**Expected flow:**
1. A1: health_score > 75, grade=HEALTHY. Action = HOLD + push renewals (+5%, target ~$1,332)
2. A2: health_score 50-65, grade=ACTION_NEEDED. Action = EXPERIMENT ($1,411 vs $1,358)
3. A2 experiment: 2 control units at $1,411, 3 test units at $1,358
4. Phase 1 includes A2 experiment launch. Phase 2 includes A1 renewal optimization.
5. No CRITICAL-severity actions (Property A has no crisis)

**Satisfaction criteria:**
- A1 gets HOLD_ASKING_RENT (not reduce, not experiment)
- A1 gets SET_RENEWAL_INCREASE with target between $1,320-$1,345
- A2 experiment spread: $1,411 - $1,358 = $53 (3.8%) — within 6% config max
- A2 experiment has 14-day observation window
- Total actions for Property A < total actions for Property B (A is healthier)

**Edge cases:**
- A1 has only 2 vacant units — too few for experiment (min_vacant=3). Verify no experiment recommended.
- A1 DOM=24 is above the 21-day threshold, but at 96% occupancy, DOM is not a concern. Claude should NOT recommend price reduction based on DOM alone when occupancy is excellent.

---

## Scenario 3.3: MAB Experiment Validity for Small Unit Counts

**Setup:** B1 has 5 vacant units. Experiment policy: min_vacant=3, min_occ=0.75, max_spread=6%.

**Trigger:** Diagnostic run produces an experiment design for B1 (if recommended) or validates why it wasn't.

**Expected flow:**
- B1 occupancy is 0.79 — above 0.75 floor: experiment IS eligible
- But B1 has 2 CRITICAL flags — engine should prefer direct action
- If experiment IS recommended despite crisis: verify unit allocation (2 control + 3 test or vice versa for 5 units)
- Price spread must be within 6% of control: e.g., $1,525 to $1,475 = $50 (3.3%) ✓
- Convergence rule must be specified and make sense for N=5

**Satisfaction criteria:**
- If experiment recommended: allocation sums to exactly 5 units across arms
- If experiment recommended: no arm has 0 units
- If experiment NOT recommended: reason documented (CRITICAL flags → direct action)
- Either way: the decision is justified in the action plan reasoning

**Edge cases:**
- What if B1 had only 2 vacant units? Engine should NOT recommend experiment (below min_vacant=3). Test this by temporarily modifying the data or config.
- What if occupancy dropped to 0.74? Below experiment floor (0.75). Engine should recommend direct price cut only.

---

## Scenario 3.4: 100% Occupancy Edge Case

**Setup:** Modify A1 to have 0 vacant, 0 on-notice (all 48 occupied). Recompute.

**Trigger:** Run diagnostic for this modified A1.

**Expected flow:**
1. Metrics: occupancy=1.00, exposure=0.00, vacant=0, daily_burn=$0
2. Flags: OCCUPANCY_PUSH_ELIGIBLE only (no DOM, no vacancy, no exposure flags)
3. Diagnosis: HEALTHY, score > 90
4. Actions: INCREASE_ASKING_RENT or HOLD depending on comp position. No experiment (nothing to experiment on). Push renewal increases aggressively.
5. No MAB_ELIGIBLE flag (0 vacant < 3 min)

**Satisfaction criteria:**
- No division by zero errors (avg days_on_market with 0 available units)
- No null pointer/key errors (no asking_rent to average)
- Revenue at risk = $0 for this unit type
- Action plan acknowledges 100% occupancy as an opportunity, not as "no action needed"

**Edge cases:**
- If all units also have lease_end > 6 months out, forward exposure = 0 across all horizons. This is the best possible state.
- Executed rent calculation: if no leases signed in last 90 days (fully occupied, no turnover), executed_rent should be null or based on older data. Verify no crash.
