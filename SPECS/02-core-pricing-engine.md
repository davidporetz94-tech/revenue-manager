# Spec 02: Core Pricing Engine

## 1. Goal

Build the three-layer pricing engine: Layer 1 (deterministic metrics computation), Layer 1.5 (flag generation against client-configured thresholds), and the Claude API client wrapper used by Layer 3. After this spec, calling `metrics_engine.compute(property_id)` returns a complete metrics JSON, and `flag_generator.generate(metrics, config)` returns structured flags — both matching the schemas defined in the planning phase. The Claude client wrapper handles API calls, retries, JSON parsing, and error handling.

**Measurable outcome:** `pytest tests/test_metrics_engine.py` and `pytest tests/test_flag_generator.py` pass. Metrics for all 4 unit types match hand-computed values. Flag counts match: A1=3 flags, A2=7, B1=12, B2=7.

## 2. Exemplar

**Metrics engine pattern:** No single exemplar — this is custom domain logic. Structure it as a collection of pure functions in `app/engine/` modules, each computing one methodology's metrics. The aggregator composes them.

**Claude API client:** Reference Anthropic's official Python SDK patterns (https://github.com/anthropics/anthropic-sdk-python). Use the SDK directly (`anthropic.Anthropic()`), not raw HTTP requests. Wrap in a service class that handles retries, JSON extraction, and schema validation.

**Flag generator pattern:** Inspired by rule engine patterns — iterate through a list of rule functions, each producing 0-1 flags. No complex rule engine library needed; simple Python functions with config thresholds as parameters.

## 3. Constraints

- Metrics engine modules are PURE FUNCTIONS. They take data in, return data out. No database access, no side effects. The service layer handles DB queries and passes data to the engine.
- Every metric in the Layer 1 schema must be computed: occupancy_metrics, exposure_metrics, velocity_metrics, pricing_spreads, revenue_metrics, demand_metrics, lease_term_metrics, trend_metrics, portfolio_metrics.
- Flag generator takes metrics JSON + client_config JSON, returns flags JSON. Each flag has: type, value, threshold, severity (CRITICAL/HIGH/MEDIUM/LOW/POSITIVE/INFO).
- Use `round_half_up()` utility for all percentage outputs.
- Exposure calculations: total_exposure = (vacant + on_notice) / total. Forward-looking (30/60/90d) requires checking lease end dates.
- Revenue at risk = (asking_rent / 30) × vacant_units × 30 (monthly).
- Daily vacancy burn = (asking_rent / 30) × vacant_units.
- Price reduction breakeven = (reduction × 12) / (asking_rent / 30) — days faster fill needed to justify.
- Demand-occupancy divergence = demand_score - occupancy (flags when > 0.05 and occupancy below concern threshold).
- Executed rent: average of `last_executed_rent` for units with `last_executed_date` within 90 days.
- Claude API client must:
  - Use `claude-sonnet-4-20250514` model
  - Set `max_tokens: 4000`
  - Parse response content blocks for text type
  - Strip markdown code fences before JSON parsing
  - Retry once on failure
  - Return parsed dict or raise a typed exception
  - Accept system prompt and user message separately

### Complete Metrics Schema

```
identity:
  property: str
  unit_type: str
  bed: int
  bath: int
  total_units: int

occupancy_metrics:
  occupied: int
  vacant: int
  on_notice: int
  available: int
  occupancy_rate: float
  vacancy_rate: float

exposure_metrics:
  total_exposure_pct: float
  vacant_exposure_pct: float
  exposure_30d_pct: float
  exposure_60d_pct: float
  exposure_90d_pct: float
  exposure_trend: str (IMPROVING|STABLE|DETERIORATING)

velocity_metrics:
  avg_days_on_market: float
  avg_days_vacant: float
  absorption_rate: float

pricing_spreads:
  asking_rent: float
  predicted_rent: float
  comps_rent: float
  in_place_rent: float
  executed_rent: float
  base_rent: float
  amenity_price: float
  asking_vs_predicted_dollars: float
  asking_vs_predicted_pct: float
  asking_vs_comps_dollars: float
  asking_vs_comps_pct: float
  executed_vs_asking_dollars: float
  executed_vs_asking_pct: float
  loss_to_lease_dollars: float
  loss_to_lease_pct: float
  amenity_pct_of_predicted: float

revenue_metrics:
  monthly_potential_revenue: float
  monthly_actual_revenue: float
  monthly_vacancy_cost: float
  accumulated_vacancy_cost: float
  daily_vacancy_burn: float
  revenue_at_risk_30d: float
  price_reduction_breakeven_days: float

demand_metrics:
  demand_score: float
  demand_vs_occupancy_divergence: float

lease_term_metrics:
  expiration_distribution: dict (month→count)
  peak_season_expiration_pct: float
  recommended_new_lease_term_months: int

trend_metrics:
  occupancy_3mo_trend: list[float]
  asking_rent_3mo_trend: list[float]
  comps_3mo_trend: list[float]

portfolio_metrics:
  total_units: int
  total_vacant: int
  blended_occupancy: float
  total_monthly_vacancy_cost: float
  total_revenue_at_risk_30d: float
  worst_performing_unit_type: str
  best_performing_unit_type: str
```

### Complete Flag Generation Rules

Each rule below checks a condition and produces a flag if true:

```
OCCUPANCY_PUSH_ELIGIBLE:
  condition: occ >= config.occupancy_thresholds.push_pricing_above
  severity: POSITIVE

OCCUPANCY_BELOW_CONCERN:
  condition: occ < config.occupancy_thresholds.concern_below AND occ >= config.occupancy_thresholds.action_below
  severity: MEDIUM

OCCUPANCY_BELOW_ACTION:
  condition: occ < config.occupancy_thresholds.action_below AND occ >= config.occupancy_thresholds.crisis_below
  severity: HIGH

OCCUPANCY_CRISIS:
  condition: occ < config.occupancy_thresholds.crisis_below
  severity: CRITICAL

EXPOSURE_CAUTION:
  condition: exp >= config.exposure_thresholds.caution_below AND exp < config.exposure_thresholds.action_below
  severity: MEDIUM

EXPOSURE_ACTION_NEEDED:
  condition: exp >= config.exposure_thresholds.action_below AND exp < config.exposure_thresholds.crisis_above
  severity: HIGH

EXPOSURE_CRISIS:
  condition: exp >= config.exposure_thresholds.crisis_above
  severity: CRITICAL

EXPOSURE_DETERIORATING:
  condition: exposure_90d_pct > exposure_30d_pct
  severity: HIGH

ABOVE_COMP_PREMIUM_THRESHOLD:
  condition: (asking - comps) / comps > config.pricing_tolerance.max_premium_vs_comps_pct
  severity: HIGH

ASKING_ABOVE_PREDICTED_THRESHOLD:
  condition: (asking - predicted) / predicted > config.pricing_tolerance.max_asking_vs_predicted_pct
  severity: MEDIUM

DOM_ABOVE_THRESHOLD:
  condition: dom > config.pricing_tolerance.acceptable_days_on_market
  severity: MEDIUM

CONCESSION_TRIGGER:
  condition: total_exposure >= config.concession_policy.concession_triggers.min_exposure_pct AND dom >= config.concession_policy.concession_triggers.min_days_on_market
  severity: HIGH

NEGATIVE_LTL:
  condition: (asking - in_place) / in_place < 0
  severity: HIGH

EXECUTED_SIGNIFICANTLY_ABOVE_ASKING:
  condition: executed - asking > 50
  severity: HIGH

EXECUTED_BELOW_ASKING:
  condition: executed - asking < -30
  severity: LOW

AMENITY_AUDIT_RECOMMENDED:
  condition: amenity / predicted > config.amenity_benchmarks.amenity_audit_threshold_pct
  severity: MEDIUM

DEMAND_OCCUPANCY_DIVERGENCE:
  condition: demand - occ > 0.05 AND occ < config.occupancy_thresholds.concern_below
  severity: HIGH

HIGH_REVENUE_AT_RISK:
  condition: daily_vacancy_burn * 30 > 5000
  severity: HIGH

RENEWAL_FREEZE_RECOMMENDED:
  condition: occ < config.renewal_policy.never_increase_above_occupancy_threshold
  severity: MEDIUM

MAB_ELIGIBLE:
  condition: vacant >= config.experiment_policy.min_vacant_for_experiment AND occ >= config.experiment_policy.min_occupancy_for_experiment
  severity: INFO
```

### Engine Module Structure

```
app/engine/
├── __init__.py
├── utils.py          # round_half_up, safe_avg, safe_divide
├── occupancy.py      # compute_occupancy_metrics(units_data) → occupancy_metrics dict
├── exposure.py       # compute_exposure_metrics(units_data, reference_date) → exposure_metrics dict
├── pricing_spread.py # compute_pricing_spreads(units_data, comps_data) → pricing_spreads dict
├── revenue.py        # compute_revenue_metrics(pricing_spreads, occupancy_metrics) → revenue_metrics dict
├── loss_to_lease.py  # compute_ltl(pricing_spreads) → ltl dict (part of pricing_spreads)
├── lease_term.py     # compute_lease_term_metrics(units_data, config) → lease_term_metrics dict
├── seasonal.py       # compute_seasonal_context(reference_date) → seasonal dict
└── aggregator.py     # aggregate_metrics(property_id, units_data, comps_data, snapshots, config) → full metrics JSON
```

## 4. Anti-Patterns

- **Do NOT** put database queries in engine modules. The metrics engine is a pure computation layer. Service methods query the DB, convert to dicts/dataclasses, pass to engine.
- **Do NOT** hardcode thresholds in the flag generator. ALL thresholds come from the client_config parameter.
- **Do NOT** generate scores or grades in the flag generator. Flags are facts ("occupancy is below action threshold"), not judgments ("occupancy is bad"). Judgment is Layer 3's job.
- **Do NOT** skip null handling. Vacant units have no current_rent. On-notice units may have no asking_rent yet. Handle gracefully.
- **Do NOT** use `statistics.mean()` on empty lists — guard against division by zero when all units are vacant.
- **Do NOT** log or print the Claude API key. Use environment variable only.
- **Do NOT** fire-and-forget Claude API calls. Always await/handle the response.

## 5. Scenarios

1. **Metrics for A1:** occupancy=0.96, total_exposure=0.06, asking_vs_predicted=+$36 (+2.7%), asking_vs_comps=+$12 (+0.9%), ltl=+$96 (+7.6%), daily_burn=$91, amenity_pct=6.7%.
2. **Metrics for B1:** occupancy=0.79, total_exposure=0.25, asking_vs_comps=+$91 (+6.3%), ltl=-$47 (-3.0%), executed_vs_asking=+$130, daily_burn=$254. Exposure trend=DETERIORATING (30d=0.21 < 60d=0.25).
3. **Flags for A1:** Exactly 3 flags — DOM_ABOVE_THRESHOLD, EXECUTED_BELOW_ASKING, OCCUPANCY_PUSH_ELIGIBLE.
4. **Flags for B1:** 12 flags including 2 CRITICAL (OCCUPANCY_CRISIS, EXPOSURE_CRISIS), plus EXPOSURE_DETERIORATING, ABOVE_COMP_PREMIUM_THRESHOLD, CONCESSION_TRIGGER, NEGATIVE_LTL, EXECUTED_SIGNIFICANTLY_ABOVE_ASKING, HIGH_REVENUE_AT_RISK, DOM_ABOVE_THRESHOLD, AMENITY_AUDIT_RECOMMENDED, RENEWAL_FREEZE_RECOMMENDED, MAB_ELIGIBLE.
5. **Flag generator with different config:** Same B1 metrics but with value-add config (crisis_below=0.72, exposure_crisis=0.25) should produce OCCUPANCY_BELOW_ACTION (not CRISIS) and EXPOSURE_CRISIS (at exactly the threshold).
6. **Claude client:** Given a valid system+user prompt, returns parsed JSON dict. Given invalid response, retries once. Given second failure, raises `ClaudeAPIError`.
7. **Portfolio metrics:** Total units=156, total vacant=18, blended occupancy=(46+31+19+42)/156=0.8846.

## 6. Convergence Criteria

- [ ] `pytest tests/test_metrics_engine.py` passes — covers all 4 unit types with exact value assertions for every metric field
- [ ] `pytest tests/test_flag_generator.py` passes — covers flag count and flag types for all 4 unit types with default config
- [ ] `pytest tests/test_flag_generator.py::test_config_sensitivity` — same metrics with different configs produce different flags
- [ ] `pytest tests/test_claude_client.py` passes — tests JSON parsing, retry logic, error handling (can mock the API)
- [ ] Metrics engine runs in <200ms on the full 156-unit dataset
- [ ] All engine modules are importable standalone with no database dependency
- [ ] Engine code has zero references to SQLAlchemy, database sessions, or ORM models
