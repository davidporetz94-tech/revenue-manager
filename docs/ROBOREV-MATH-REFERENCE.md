# RoboRev — Mathematical Reference

All formulas, algorithms, and statistical methods used in the revenue management engine. Every number in the system traces to one of these computations.

---

## Foundational Utilities

### Round-Half-Up (Critical)

Python's `round()` uses banker's rounding. The EliseAI export uses round-half-up. This one function cascades through every percentage in the system.

```
round_half_up(x, d) = floor(x × 10^d + 0.5) / 10^d
```

Example: B2 exposure = 6/48 = 0.125. `round(0.125, 2)` = 0.12 (wrong). `round_half_up(0.125, 2)` = 0.13 (correct).

**File:** `engine/utils.py`

### Safe Division & Safe Average

```
safe_divide(a, b) = a / b  if b ≠ 0, else 0.0
safe_avg(values)  = sum(values) / len(values)  if len > 0, else 0.0
```

Guards against division by zero and empty-list aggregation throughout the engine.

---

## Layer 1: Deterministic Metrics Engine

Pure functions. No thresholds, no judgment — just facts computed from rent roll data.

### Occupancy Metrics

| Metric | Formula | Notes |
|--------|---------|-------|
| Occupancy Rate | `occupied / total_units` | "Occupied" includes ON_NOTICE units |
| Vacancy Rate | `vacant / total_units` | VACANT status only |
| Available Units | `vacant + on_notice` | Forward-looking availability |

All rates: `round_half_up(ratio, 2)`

**File:** `engine/occupancy.py`

### Exposure Metrics

| Metric | Formula |
|--------|---------|
| Total Exposure | `(vacant + on_notice) / total_units` |
| Vacant Exposure | `vacant / total_units` |
| 30d/60d/90d Exposure | `(vacant + on_notice_within_window + leases_expiring_within_window) / total_units` |

Forward-looking windows count units that will become available within D days:
```
count_D = vacant
        + |{u : status=ON_NOTICE, move_out_date ≤ ref_date + D}|
        + |{u : status=OCCUPIED, lease_end ≤ ref_date + D}|
exposure_D = count_D / total_units
```

**Exposure Trend:**
- `90d > 30d` → DETERIORATING
- `90d < 30d` → IMPROVING
- Equal → STABLE

**File:** `engine/exposure.py`

### Pricing Spreads

14 spread metrics comparing rent values across different contexts:

| Metric | Formula | Population |
|--------|---------|-----------|
| Asking Rent | `avg(asking_rent)` | VACANT + ON_NOTICE units |
| In-Place Rent | `avg(current_rent)` | OCCUPIED + ON_NOTICE units |
| Executed Rent | `avg(last_executed_rent)` | Units executed within 90 days |
| Predicted Rent | `avg(predicted_rent)` | All units |
| Amenity Price | `avg(amenity_premium)` | All units with amenity data |
| Base Rent | From unit type definition | Per unit type |
| Comps Rent | From comp_rents table | External public data |

**Key relationship:** `Predicted = Base + Amenity` (exact for all 4 unit types)

**Spread calculations:**
```
asking_vs_comps_$ = asking - comps
asking_vs_comps_% = round_half_up((asking - comps) / comps × 100, 1)
asking_vs_predicted_% = round_half_up((asking - predicted) / predicted × 100, 1)
executed_vs_asking_% = round_half_up((executed - asking) / asking × 100, 1)
```

**Loss-to-Lease:**
```
LTL_$ = asking - in_place
LTL_% = round_half_up((asking - in_place) / in_place × 100, 1)
```
- Positive LTL = market upside (tenants pay below market)
- Negative LTL = overpriced in-place rents (B1: tenants pay MORE than asking)

**File:** `engine/pricing_spread.py`

### Revenue Metrics

| Metric | Formula | Interpretation |
|--------|---------|---------------|
| Daily Vacancy Burn | `(asking / 30) × vacant` | Cash lost per day |
| Revenue at Risk (30d) | `daily_burn × 30` | Monthly exposure |
| Monthly Potential | `asking × total_units` | If all units leased at asking |
| Monthly Actual | `in_place × occupied` | Current revenue |
| Monthly Vacancy Cost | `asking × vacant` | Revenue forgone |

**Breakeven Days (Price Reduction Justification):**
```
breakeven = (reduction_per_month × 12) / (asking / 30)
```
A $50/month rent cut breaks even if the unit fills X days sooner.

**File:** `engine/revenue.py`

### Velocity Metrics

```
avg_DOM = round(avg(days_on_market for VACANT + ON_NOTICE units))
avg_DV  = round(avg(days_vacant for VACANT units))
```

**File:** `engine/aggregator.py`

### Seasonal Context

Monthly pricing multipliers based on multifamily leasing seasonality:

| Month | Factor | Season |
|-------|--------|--------|
| Jan | 0.93 | OFF_PEAK |
| Feb | 0.95 | OFF_PEAK |
| Mar | 0.98 | SPRING_RAMP |
| Apr | 1.02 | SPRING_RAMP |
| May | 1.05 | PEAK |
| Jun | 1.07 | PEAK |
| Jul | 1.06 | PEAK |
| Aug | 1.04 | PEAK |
| Sep | 1.01 | PEAK |
| Oct | 0.97 | FALL_DECEL |
| Nov | 0.94 | FALL_DECEL |
| Dec | 0.92 | OFF_PEAK |

Seasonal variation range: 1.6–7.1% from baseline.

**Months to Peak:** `max(0, 5 - month)` if month ≤ 5, else `max(0, 17 - month)`

**File:** `engine/seasonal.py`

### Lease Term Metrics

```
peak_expiration_pct = |{u : lease_end.month ∈ {5,6,7,8,9}}| / |{u : has lease}|
```

Target: 60% of expirations in peak season (May–Sep). Preferred lease term: 14 months.

**File:** `engine/lease_term.py`

---

## Layer 1.5: Configurable Flag Generator

Compares Layer 1 metrics against client-configured thresholds. 20 rules, zero hardcoded values.

### Occupancy Bands (Mutually Exclusive)

| Flag | Condition | Default Threshold |
|------|-----------|------------------|
| OCCUPANCY_CRISIS | `occ < crisis_below` | 0.82 |
| OCCUPANCY_BELOW_ACTION | `occ < action_below` | 0.88 |
| OCCUPANCY_BELOW_CONCERN | `occ < concern_below` | 0.92 |
| OCCUPANCY_PUSH_ELIGIBLE | `occ ≥ push_pricing_above` | 0.96 |

### Exposure Bands (Mutually Exclusive)

| Flag | Condition | Default Threshold |
|------|-----------|------------------|
| EXPOSURE_CRISIS | `exp ≥ crisis_above` | 0.20 |
| EXPOSURE_ACTION_NEEDED | `exp ≥ action_below` | 0.15 |
| EXPOSURE_CAUTION | `exp ≥ caution_below` | 0.10 |
| EXPOSURE_DETERIORATING | `exp_90d > exp_30d` | — |

### Pricing Flags

| Flag | Condition | Default |
|------|-----------|---------|
| ABOVE_COMP_PREMIUM | `(asking - comps) / comps > max_premium_pct` | 5% |
| ASKING_ABOVE_PREDICTED | `(asking - predicted) / predicted > max_asking_vs_predicted_pct` | 4% |
| EXECUTED_BELOW_ASKING | `executed < asking` (executed exists) | — |
| EXECUTED_SIGNIFICANTLY_ABOVE_ASKING | `(executed - asking) / asking > 5%` | — |

### Concession Trigger (Compound Condition)

```
TRIGGER if: exposure ≥ min_exposure_pct AND DOM ≥ min_DOM
SUPPRESS if: occupancy ≥ removal_occupancy_threshold
```
Defaults: min_exposure=12%, min_DOM=21 days, removal_occ=93%

### Revenue & Optimization Flags

| Flag | Condition |
|------|-----------|
| HIGH_REVENUE_AT_RISK | `daily_burn × 30 > $5,000` |
| NEGATIVE_LTL | `LTL_$ < 0` |
| DOM_ABOVE_THRESHOLD | `avg_DOM > acceptable_DOM` (default 21) |
| AMENITY_AUDIT_RECOMMENDED | `amenity_% > audit_threshold` (default 8%) |
| RENEWAL_FREEZE_RECOMMENDED | `occ < freeze_below_occ` (default 0.82) |
| MAB_ELIGIBLE | `vacant ≥ min_vacant AND occ ≥ min_occ` (defaults: 3, 0.75) |

### Expected Flag Counts (Default Config)

| Unit Type | Count | Severity Profile |
|-----------|-------|-----------------|
| A1 | 3 | 0 CRITICAL, 0 HIGH |
| A2 | 7 | 0 CRITICAL, 3 HIGH |
| B1 | 12 | 2 CRITICAL, 5 HIGH |
| B2 | 7 | 0 CRITICAL, 2 HIGH |

**File:** `services/flag_generator.py`

---

## Layer 2: Revenue Optimization Engine

Advanced algorithms for elasticity estimation, optimal pricing, revenue gap decomposition, and efficiency scoring.

### Elasticity Estimation

Estimates price sensitivity from historical snapshot data.

**Month-over-month changes:**
```
rent_pct_change = (curr_rent - prev_rent) / prev_rent × 100
occ_change = curr_occ - prev_occ
```

**Elasticity coefficient:**
```
ε = -(occ_change / rent_pct_change) × 100
```
Interpretation: occupancy change (percentage points) per 1% rent change. Positive ε = classic demand elasticity (higher rent → lower occupancy).

**Confidence levels:**
- HIGH: ≥4 data points, consistent direction, avg rent change ≥0.5%
- MEDIUM: ≥3 data points, avg rent change ≥0.3%
- LOW: insufficient data

**Comp corroboration:** If comp rent trends move in the same direction as subject rents, confidence bumps one level (LOW→MEDIUM, MEDIUM→HIGH).

**File:** `engine/revenue_optimizer.py:57-242`

### Optimal Price Computation

Grid search over 41 price points (-10% to +10% in 0.5% steps).

```
For each candidate_price:
    pct_change = (candidate - current) / current × 100
    occ_delta = -ε × pct_change / 100
    estimated_occ = clamp(current_occ + occ_delta, 0, 1)
    estimated_units = round(estimated_occ × total_units)
    estimated_revenue = candidate × estimated_units
    vacancy_penalty = compute_penalty(estimated_occ, candidate, vacant)
    score = estimated_revenue - vacancy_penalty

optimal = argmax(score)
```

**Vacancy cost penalty (asymmetric):**
```
if occ ≥ stressed_threshold: penalty = 0
elif occ < crisis_threshold: penalty = vacant × price × 0.50
else: penalty = vacant × price × 0.25
```

**Comp constraint:** Clamp optimal to `[comps × 0.85, comps × 1.15]`

**Seasonal adjustment:** +1% if ≤3 months to peak, -1% if ≥9 months from peak

**Conservative recommendation:** `recommended = (current + optimal) / 2` (halfway)

**Price direction:**
- `> +2%` → INCREASE
- `< -2%` → DECREASE
- Within ±2% → HOLD

**File:** `engine/revenue_optimizer.py:249-408`

### Revenue Gap Decomposition

Breaks total revenue gap into 5 actionable levers:

```
total_gap = optimal_revenue - current_revenue

Components:
1. FILL:    vacancy_cost = vacant × asking_rent
2. REPRICE: new_lease_gap = max(0, optimal - asking) × vacant
3. RENEW:   in_place_gap = max(0, LTL_$) × occupied
4. RENEW:   renewal_opportunity (from renewal optimizer)
5. DE_CONCESSION: concession_drag = Σ(concession_monthly per unit)

dominant_lever = argmax(components)
```

**File:** `engine/revenue_optimizer.py:518-619`

### Revenue Efficiency Score (0–100)

Four-dimensional scoring with dynamic occupancy-zone weighting.

**Dimension 1: Occupancy Health**
```
target = market_occupancy × seasonal_factor
score = max(0, min(100, 100 - (target - actual_occ) × 500))
```
1% gap from target = 5 points lost.

**Dimension 2: Pricing Alignment**
```
gap_pct = |current_asking - optimal_asking| / optimal_asking
score = max(0, min(100, 100 - gap_pct × 1000))
```
1% price gap = 10 points lost.

**Dimension 3: Rent Roll Momentum**
```
baseline = 50
occ_bonus = (last_occ - first_occ) × 2000   [1% improvement = +20 pts]
rent_bonus = rent_pct_change × 500           [1% increase = +5 pts]
             (sign-flipped if overpriced)
score = clamp(baseline + occ_bonus + rent_bonus, 0, 100)
```

**Dimension 4: Revenue Capture**
```
gap_ratio = gap_monthly / optimal_revenue
score = 100 - gap_ratio × 300
```
0% gap → 100, 10% gap → 70, 33% gap → 0.

**Dynamic weights by occupancy zone:**

| Zone | Occ Range | Occ Wt | Pricing Wt | Momentum Wt | Capture Wt |
|------|-----------|--------|-----------|-------------|-----------|
| CRISIS | <82% | 0.50 | 0.10 | 0.20 | 0.20 |
| STRESSED | 82–89% | 0.35 | 0.25 | 0.20 | 0.20 |
| BALANCED | 89–94% | 0.25 | 0.30 | 0.25 | 0.20 |
| STRONG | 94–97% | 0.10 | 0.35 | 0.30 | 0.25 |
| FULL | ≥97% | 0.05 | 0.35 | 0.30 | 0.30 |

**Seasonal weight shift:** Spring (≤3 months to peak): +5% pricing, -5% occupancy. Off-peak (≥9 months): reverse.

**Composite:** `score = Σ(dimension_score × dimension_weight)`, clamped to [0, 100]

**Grade mapping:**

| Score | Grade |
|-------|-------|
| ≥85 | OPTIMIZED |
| ≥70 | OPPORTUNITY |
| ≥55 | IMBALANCED |
| ≥40 | DISTRESSED |
| <40 | CRISIS |

**File:** `engine/revenue_optimizer.py:626-751`

### Portfolio Revenue Efficiency (60/40 Blend)

Used for portfolio-level gauge display:

```
composite_score = Σ(unit_type_efficiency_score × unit_count) / total_units
revenue_capture_pct = (total_current_revenue / total_optimal_revenue) × 100
portfolio_efficiency = composite_score × 0.6 + revenue_capture_pct × 0.4
```

60% multi-dimensional quality + 40% actual dollar performance.

**File:** `engine/aggregator.py:211-237`, `api/properties.py:211-240`

---

## Layer 3: Renewal Optimization

### Renewal Increase Decision Table

Lookup by `(occupancy_zone, LTL > 5%, months_to_peak ≤ 3)`:

| Zone | LTL High | Peak Season | Recommended Increase |
|------|----------|-------------|---------------------|
| CRISIS / STRESSED | any | any | 0% (freeze) |
| BALANCED | any | off-peak | 2.0% |
| BALANCED | >5% | peak | 3.5% |
| BALANCED | ≤5% | any | 2.0% |
| STRONG / FULL | >5% | peak | 5.0% |
| STRONG / FULL | >5% | off-peak | 3.5% |
| STRONG / FULL | ≤5% | any | 2.5% |

### Turnover Probability Model

```
P(turnover) = min(max_cap, base_rate × (1 + increase_pct × sensitivity / 100))
```
Defaults: base_rate=10%, sensitivity=5.0, max_cap=60%

### Net Renewal Capture

```
turnover_cost_per_unit = avg_DOM × (asking / 30) + make_ready_cost
gross_annual = increase_$ × renewals × 12
net_annual = gross_annual - P(turnover) × turnover_cost × renewals
```

**File:** `engine/renewal_optimizer.py`

---

## Layer 3.5: MAB Experiment Design

### Unit Allocation

**Two-arm (standard):**

| Vacant | Control | Test |
|--------|---------|------|
| 2 | 1 | 1 |
| 3 | 1 | 2 |
| 4 | 2 | 2 |
| 5 | 2 | 3 |
| 6+ | n/2 | n - n/2 |

**Three-arm (when ≥6 vacant AND concession trigger):**
```
per_arm = vacant ÷ 3
control = per_arm, test = per_arm, concession = per_arm + remainder
```

### Experiment Direction

```
if occ < 0.82: CRISIS_DIRECT_ACTION (skip experiment)
if |asking - optimal| ≤ 3%: NOT_ELIGIBLE (already optimal)
if asking > optimal: DOWN (test lower price)
if asking < optimal AND occ ≥ 0.92: UP (test higher price)
else: DOWN (default)
```

### Downward Test Price

```
test = predicted_rent
if (asking - comps) / comps > 3%: test = comps
enforce: |control - test| ≤ min(max_spread_pct × control, max_spread_$)
minimum: |control - test| ≥ $20 (else: test = control - $50)
```
Defaults: max_spread=6% or $100

### Upward Test Price

```
test = (asking + optimal) / 2   [conservative halfway]
enforce: spread ≤ min(5% × control, $75)
minimum: spread ≥ $20 (else: test = control + $50)
```

### Convergence

```
RPD = monthly_rent / (vacancy_days + 1)    [revenue per unit per day]
practical_significance = 15% RPD difference
observation_window = 14 days
early_termination = any application on any unit
```

**File:** `services/action_plan_service.py`

---

## Diagnostic Scoring (Fallback)

When Claude is unavailable, deterministic scoring from flag severity:

| Condition | Score | Grade |
|-----------|-------|-------|
| ≥2 CRITICAL flags | 25 | CRISIS |
| 1 CRITICAL or ≥3 HIGH | 50 | DISTRESSED |
| ≥1 HIGH | 65 | IMBALANCED |
| No HIGH or CRITICAL | 85 | OPTIMIZED |

Claude's diagnosis uses the same rubric as guidance but can adjust ±5 points based on contextual judgment.

**File:** `services/diagnostic_service.py`

---

## Summary

| Category | Formulas | Key Insight |
|----------|----------|-------------|
| Occupancy | 3 | "Occupied" includes on-notice — this catches everyone |
| Exposure | 5 | Forward-looking (30/60/90d windows), not just current vacancy |
| Pricing Spreads | 14 | Every comparison is directional — who's above/below whom matters |
| Revenue | 6 | Daily burn is the hero metric ($911/day portfolio) |
| Seasonality | 3 | 7.1% peak-to-trough variation drives timing decisions |
| Flags | 20 rules | All threshold-driven from client config — zero hardcoded |
| Elasticity | 5 | Historical estimation with comp corroboration |
| Optimal Pricing | 8 | 41-point grid search with asymmetric vacancy penalty |
| Revenue Gap | 9 | 5-lever decomposition identifies dominant action |
| Efficiency Score | 8 | 4-dimensional, zone-weighted, seasonally adjusted |
| Renewals | 7 | Turnover probability model balances capture vs retention |
| Experiments | 7 | Bayesian MAB with practical significance, not p-values |
| **Total** | **~95** | |
