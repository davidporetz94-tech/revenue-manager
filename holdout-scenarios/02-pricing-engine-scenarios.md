# Holdout Scenarios — Spec 02: Pricing Engine

## Scenario 2.1: Correctly Identifies Overpriced Unit (A2)

**Setup:** Metrics engine loaded with seeded A2 data. Default "Stabilized Balanced" config active.

**Trigger:** `metrics = metrics_engine.compute(property_a_id, [a2_unit_type_id])`; `flags = flag_generator.generate(metrics, config)`

**Expected flow:**
1. Metrics engine computes:
   - occupancy = 0.86 (31/36)
   - asking_vs_predicted = +$53 (+3.9%)
   - asking_vs_comps = +$15 (+1.1%)
   - total_exposure = 0.17
   - daily_vacancy_burn = $235
   - ltl = +$107 (+8.2%)
2. Flag generator produces exactly 7 flags:
   - OCCUPANCY_BELOW_ACTION (0.86 < 0.88 threshold)
   - EXPOSURE_ACTION_NEEDED (0.17 > 0.15 threshold)
   - CONCESSION_TRIGGER (exposure 0.17 > 0.12 AND dom 22 >= 21)
   - HIGH_REVENUE_AT_RISK ($7,055 > $5,000)
   - DOM_ABOVE_THRESHOLD (22 > 21)
   - RENEWAL_FREEZE_RECOMMENDED (0.86 < 0.88)
   - MAB_ELIGIBLE (5 vacant >= 3 min, 0.86 occ >= 0.75 floor)

**Satisfaction criteria:**
- All 7 metric values match within $1 for dollar amounts, 0.01 for percentages
- Exactly 7 flags generated (not 6, not 8)
- Flag types match exactly
- No CRITICAL severity flags (A2 is serious but not crisis)

**Edge cases:**
- If DOM were 20 instead of 22, CONCESSION_TRIGGER should NOT fire (dom < 21)
- If config.acceptable_days_on_market changed to 25, DOM_ABOVE_THRESHOLD should NOT fire

---

## Scenario 2.2: Correctly Identifies Underpriced/Healthy Unit (A1)

**Setup:** Metrics engine loaded with seeded A1 data. Default config.

**Trigger:** Same as above but for A1.

**Expected flow:**
1. Metrics: occupancy=0.96, asking_vs_predicted=+$36 (+2.7%), asking_vs_comps=+$12 (+0.9%), total_exposure=0.06, ltl=+$96 (+7.6%)
2. Only 3 flags:
   - OCCUPANCY_PUSH_ELIGIBLE (0.96 >= 0.96) — POSITIVE severity
   - DOM_ABOVE_THRESHOLD (24 > 21) — MEDIUM
   - EXECUTED_BELOW_ASKING (-$41) — LOW

**Satisfaction criteria:**
- Exactly 3 flags
- OCCUPANCY_PUSH_ELIGIBLE has severity POSITIVE (not a problem flag)
- No HIGH or CRITICAL flags

**Edge cases:**
- A1 has only 2 vacant units — MAB_ELIGIBLE should NOT fire (2 < 3 min)

---

## Scenario 2.3: Correctly Identifies Crisis Unit (B1)

**Setup:** Metrics engine with B1 data. Default config.

**Trigger:** Compute metrics and flags for B1.

**Expected flow:**
1. Metrics: occupancy=0.79, exposure=0.25, asking_vs_comps=+$91 (+6.3%), ltl=-$47 (-3.0%), executed_vs_asking=+$130, daily_burn=$254
2. Exposure trend: DETERIORATING (30d=0.21, 60d=0.25, 90d=0.25)
3. Exactly 12 flags including:
   - 2 CRITICAL: OCCUPANCY_CRISIS (0.79 < 0.82), EXPOSURE_CRISIS (0.25 > 0.20)
   - HIGH: EXPOSURE_DETERIORATING, ABOVE_COMP_PREMIUM_THRESHOLD, CONCESSION_TRIGGER, NEGATIVE_LTL, EXECUTED_SIGNIFICANTLY_ABOVE_ASKING, HIGH_REVENUE_AT_RISK
   - MEDIUM: DOM_ABOVE_THRESHOLD, AMENITY_AUDIT_RECOMMENDED (8.2% > 8%), RENEWAL_FREEZE_RECOMMENDED
   - INFO: MAB_ELIGIBLE (5 vacant >= 3, 0.79 occ >= 0.75)

**Satisfaction criteria:**
- 12 flags total
- Exactly 2 CRITICAL
- NEGATIVE_LTL flag present (only B1 has this)
- EXECUTED_SIGNIFICANTLY_ABOVE_ASKING flag present with spread=$130

**Edge cases:**
- Demand-occupancy divergence: B1 demand=0.75, occ=0.79 → gap = -0.04. Flag requires gap > 0.05 AND occ below concern. Since demand < occ here, this flag should NOT fire for B1. Verify this.
- B1 MAB_ELIGIBLE: 0.79 is barely above the 0.75 experiment floor. If one more unit goes vacant and occ drops to 0.75, experiment is still eligible. At 0.74, it's not.

---

## Scenario 2.4: High-Exposure Emergency (B2 with stale vacancy)

**Setup:** Metrics engine with B2 data. Default config.

**Trigger:** Compute metrics and flags for B2.

**Expected flow:**
1. Metrics: occupancy=0.88, exposure=0.13, asking_vs_comps=-$8 (-0.5%), asking_vs_predicted=+$71 (+4.5%), dom=30, days_vacant=28, daily_burn=$331
2. Exposure trend: STABLE/IMPROVING (total=0.13, 30d/60d/90d=0.10)
3. Exactly 7 flags:
   - HIGH: CONCESSION_TRIGGER, HIGH_REVENUE_AT_RISK ($9,924)
   - MEDIUM: OCCUPANCY_BELOW_CONCERN, EXPOSURE_CAUTION, ASKING_ABOVE_PREDICTED_THRESHOLD (4.5% > 4%), DOM_ABOVE_THRESHOLD (30 > 21)
   - INFO: MAB_ELIGIBLE (6 vacant >= 3, 0.88 occ >= 0.75)

**Satisfaction criteria:**
- 7 flags, zero CRITICAL (B2 is not a crisis — it's a puzzle)
- No ABOVE_COMP_PREMIUM_THRESHOLD flag (B2 is -0.5% vs comps, within tolerance)
- HIGH_REVENUE_AT_RISK flag present — B2 has the HIGHEST dollar amount at risk ($9,924/mo)
- Exposure trend is NOT deteriorating (30d < total exposure)

**Edge cases:**
- B2 has 0 on-notice units. Total exposure (0.13) differs from 30d exposure (0.10) because one vacant unit is expected to fill. Verify the engine handles the `available != vacant` case for B2.
- B2 daily burn ($331/day) is the highest of any unit type — verify this surfaces in portfolio_metrics.
