# Spec 01: Data Model & Dummy Data Generation

## 1. Goal

Stand up the PostgreSQL database with all 14 tables, create SQLAlchemy ORM models, wire Alembic migrations, and seed two properties (A and B) with 156 units of dummy data that reconcile **exactly** to the EliseAI Pricing Export. Also seed 9 comp properties with 72 rent observations, 16 historical snapshots, a default client config, and a demo user. After seeding, a validation script must pass 56+ assertion checks confirming every aggregate matches the export.

**Measurable outcome:** `python -m pytest tests/test_reconciliation.py` passes with 0 failures.

## 2. Exemplar

**Primary:** `benavlabs/FastAPI-boilerplate` (https://github.com/benavlabs/FastAPI-boilerplate) — Gene-transfuse the project structure, SQLAlchemy 2.0 async patterns, Alembic setup, and env/config management. Adapt their `models/` and `schemas/` organization pattern.

**Secondary:** `tiangolo/full-stack-fastapi-template` (https://github.com/fastapi/full-stack-fastapi-template) — Reference for the User/auth model pattern and multi-tenancy approach.

**Do NOT clone these repos.** Study their structure and adapt patterns to our domain schema.

## 3. Constraints

- PostgreSQL 15+ required. All primary keys are UUIDs (`gen_random_uuid()`).
- SQLAlchemy 2.0 style (mapped_column, not legacy Column). Async optional for MVP — sync is acceptable.
- Alembic must be configured and first migration must create all 14 tables.
- Every seeded aggregate MUST match the export exactly. Use `round_half_up()` (not Python's `round()`) for all percentage calculations — the export uses round-half-up convention.
- Amenity premiums must sum to exact targets per unit type: A1=$4,272, A2=$2,988, B1=$3,000, B2=$5,664.
- In-place rent sums: A1=$58,374, A2=$40,424, B1=$29,868, B2=$67,536.
- Asking rent sums: A1=$4,095, A2=$8,466, B1=$9,150, B2=$9,924.
- Executed rent averages: A1=$1,324 (4 leases), A2=$1,392 (4 leases), B1=$1,655 (3 leases), B2=$1,659 (5 leases).
- DOM values: A1=[15,26,31], A2=[8,14,18,24,28,40], B1=[10,18,22,28,32,40], B2=[18,22,28,32,36,44].
- Days vacant: A1=[12,22], A2=[7,10,14,22,27], B1=[10,15,18,25,32], B2=[16,20,26,30,34,42].
- Status counts: A1(46/2/1), A2(31/5/1), B1(19/5/1), B2(42/6/0).
- B1 on-notice unit move-out date must be 31-60 days out (makes 30d exposure=0.21, 60d=0.25).
- All B2 occupied leases expire >90 days out (makes 30d/60d/90d exposure=0.10).
- Reference date for all calculations: March 15, 2026.
- Demo user: `demo@example.com` / `demo123`, role=admin, org="Demo Client".
- JSONB fields for client_config thresholds (not separate columns).
- audit_log table: append-only, no update/delete methods on the ORM model.

### Complete Database Schema (14 Tables)

**Domain 1: Auth (2 tables)**
- **organizations**: id(UUID PK), name, slug(UNIQUE), created_at
- **users**: id(UUID PK), email(UNIQUE), password_hash, full_name, role(admin|operator|viewer), organization_id(FK), created_at, last_login, is_active

**Domain 2: Properties & Units (3 tables)**
- **properties**: id(UUID PK), organization_id(FK), name, code, address, submarket, total_units, year_built, property_class, created_at. UNIQUE(organization_id, code).
- **unit_types**: id(UUID PK), property_id(FK), code, bed, bath, total_units, base_rent, sqft_min, sqft_max. UNIQUE(property_id, code).
- **units**: id(UUID PK), unit_type_id(FK), property_id(FK), unit_number, floor, sqft, premium_view(bool), high_floor(bool), corner_unit(bool), in_unit_wd(bool), renovated(bool), patio_balcony(bool), ev_charging(bool), garage_parking(bool), amenity_premium, predicted_rent, status(OCCUPIED|VACANT|ON_NOTICE), current_rent, lease_start, lease_end, tenant_id, asking_rent, days_on_market, days_vacant, move_out_date, last_executed_rent, last_executed_date, concession_active, concession_type, concession_value_monthly, created_at, updated_at. UNIQUE(property_id, unit_number).

**Domain 3: Comp Set (3 tables)**
- **comp_properties**: id(UUID PK), property_id(FK), name, address, submarket, total_units, year_built, property_class, distance_miles, data_source, notes, is_active, last_refreshed_at, created_at
- **comp_unit_types**: id(UUID PK), comp_property_id(FK), subject_unit_type_id(FK), bed, bath, sqft_range, relevance_score
- **comp_rents**: id(UUID PK), comp_unit_type_id(FK), observation_date, asking_rent, concession_advertised, net_effective_rent, units_advertised, source_url, data_source, created_at. INDEX(comp_unit_type_id, observation_date). ANTITRUST: public data only.

**Domain 4: Config (1 table)**
- **client_configs**: id(UUID PK), property_id(FK), version(INT), is_active(BOOL), investment_thesis, risk_profile, hold_period_years, business_plan_summary, occupancy_thresholds(JSONB), exposure_thresholds(JSONB), pricing_tolerance(JSONB), concession_policy(JSONB), renewal_policy(JSONB), lease_term_policy(JSONB), experiment_policy(JSONB), amenity_benchmarks(JSONB), created_at, created_by(FK users)

**Domain 5: Historical (1 table)**
- **historical_snapshots**: id(UUID PK), unit_type_id(FK), snapshot_date, total_units, occupied, vacant, on_notice, occupancy_rate, avg_in_place_rent, avg_asking_rent, avg_executed_rent, avg_days_on_market, exposure_pct, demand_score, comps_avg, created_at. UNIQUE(unit_type_id, snapshot_date).

**Domain 6: Diagnostics & Audit (2 tables)**
- **diagnostic_runs**: id(UUID PK), property_id(FK), config_id(FK), run_date, triggered_by(FK users), metrics_json(JSONB), flags_json(JSONB), diagnosis_json(JSONB), action_plan_json(JSONB), narrative_json(JSONB), slide_deck_json(JSONB), status(PENDING|RUNNING|COMPLETED|FAILED), error_message, metrics_compute_ms(INT), diagnosis_api_ms(INT), action_plan_api_ms(INT), narrative_api_ms(INT), total_ms(INT)
- **audit_log**: id(UUID PK), organization_id(FK), user_id(FK), action, entity_type, entity_id, details(JSONB), ip_address, created_at. APPEND-ONLY (no update/delete). INDEX(organization_id, created_at DESC).

**Domain 7: Experiments (2 tables)**
- **experiments**: id(UUID PK), diagnostic_run_id(FK), unit_type_id(FK), status(PROPOSED|APPROVED|ACTIVE|CONVERGED|CANCELLED|EXPIRED), experiment_design(JSONB), approved_by(FK), approved_at, started_at, ended_at, outcome, outcome_details(JSONB), created_at
- **experiment_assignments**: id(UUID PK), experiment_id(FK), unit_id(FK), arm_label, assigned_price, assigned_concession, leased(BOOL), lease_date, days_to_lease, application_received(BOOL), application_date, tours_count. UNIQUE(experiment_id, unit_id).

### Building Layouts

- Property A: 3-story garden-style, 28 units/floor (16 A1 + 12 A2 per floor = 84 total)
  - Floor 1: A-101 to A-116 (A1) + A-117 to A-128 (A2)
  - Floor 2: A-201 to A-216 (A1) + A-217 to A-228 (A2)
  - Floor 3: A-301 to A-316 (A1) + A-317 to A-328 (A2)
- Property B: 4-story mid-rise elevator, 18 units/floor (6 B1 + 12 B2 per floor = 72 total)
  - Each floor: B-X01 to B-X06 (B1) + B-X07 to B-X18 (B2)

### SqFt Ranges
A1: 600-650, A2: 850-920, B1: 680-730, B2: 980-1050

### Amenity Structure
Per-unit amenity flags: premium_view (+$20-25), high_floor (+$25-35), corner_unit (+$15), in_unit_wd (+$75-85), renovated (+$40-50), patio_balcony (+$30), ev_charging (+$20), garage_parking (+$15-20).
- Property A: ~42% have WD, ~25% renovated
- Property B: ~75% have WD (newer/premium), ~33% renovated, some EV/garage

### Amenity Assignment Rules
Deterministic from unit position (NOT random):
- high_floor: floor >= 3 (Property A) or floor >= 3 (Property B)
- patio_balcony: floor == 1
- corner_unit: unit_number endings (first and last on each floor)
- in_unit_wd: by percentage targets (42% for A, 75% for B)
- renovated: by percentage targets (25% for A, 33% for B)

### Executed Rent Values (Pre-computed, must average exactly)
- A1: 4 leases: $1,290, $1,310, $1,340, $1,356 → avg $1,324 ✓
- A2: 4 leases: $1,370, $1,385, $1,400, $1,413 → avg $1,392 ✓
- B1: 3 leases: $1,630, $1,660, $1,675 → avg $1,655 ✓
- B2: 5 leases: $1,640, $1,650, $1,660, $1,670, $1,675 → avg $1,659 ✓

### Comp Properties

**Property A — Submarket "Maplewood Gardens"** (4 comps):
- COMP-A-01: Riverside Terrace — 120 units, built 2008, Class B+, 0.8 mi
- COMP-A-02: Willow Creek — 96 units, built 2012, Class B+, 1.2 mi
- COMP-A-03: Oakmont Village — 144 units, built 2003, Class B, 0.5 mi
- COMP-A-04: Elm Street Residences — 72 units, built 2018, Class A-, 1.5 mi

**Property B — Submarket "Harbor Point"** (5 comps):
- COMP-B-01: The Meridian — 180 units, built 2019, Class A-, 0.6 mi
- COMP-B-02: Harbor View Lofts — 90 units, built 2015, Class B+, 0.9 mi
- COMP-B-03: Parkside Commons — 144 units, built 2010, Class B+, 1.1 mi
- COMP-B-04: Azure Tower — 200 units, built 2022, Class A, 1.4 mi
- COMP-B-05: Beacon Hill — 108 units, built 2013, Class B, 0.7 mi

### Comp Rent Time Series (all averages verified)

**A1 comps (simple average = Comps column):**
```
         Riverside  Willow  Oakmont  Elm St   Avg
Dec 2025   $1,320  $1,350  $1,275  $1,415  $1,340
Jan 2026   $1,330  $1,358  $1,282  $1,422  $1,348
Feb 2026   $1,335  $1,365  $1,290  $1,414  $1,351
Mar 2026   $1,340  $1,370  $1,295  $1,407  $1,353
```

**A2 comps:**
```
         Riverside  Willow  Oakmont  Elm St   Avg
Dec 2025   $1,325  $1,365  $1,395  $1,435  $1,380
Jan 2026   $1,335  $1,372  $1,400  $1,445  $1,388
Feb 2026   $1,340  $1,378  $1,405  $1,449  $1,393
Mar 2026   $1,345  $1,380  $1,410  $1,449  $1,396
```

**B1 comps (DECLINING market — $41 drop in 3 months):**
```
         Meridian  Harbor  Parkside  Azure  Beacon   Avg
Dec 2025  $1,510  $1,485   $1,420  $1,530  $1,430  $1,475
Jan 2026  $1,490  $1,465   $1,400  $1,520  $1,425  $1,460
Feb 2026  $1,475  $1,450   $1,390  $1,500  $1,410  $1,445
Mar 2026  $1,460  $1,435   $1,380  $1,485  $1,410  $1,434
```

**B2 comps (rising market — +$12 in 3 months):**
```
         Meridian  Harbor  Parkside  Azure  Beacon   Avg
Dec 2025  $1,675  $1,650   $1,580  $1,710  $1,635  $1,650
Jan 2026  $1,680  $1,660   $1,585  $1,715  $1,635  $1,655
Feb 2026  $1,688  $1,665   $1,590  $1,718  $1,639  $1,660
Mar 2026  $1,690  $1,665   $1,595  $1,720  $1,640  $1,662
```

### Historical Snapshots (4 months × 4 unit types = 16 rows)

**Property A trends:**
```
A1: Dec(occ=0.98, ask=$1,345, comp=$1,340) Jan(0.96, $1,355, $1,348) Feb(0.96, $1,360, $1,351) Mar(0.96, $1,365, $1,353)
A2: Dec(0.92, $1,385, $1,380) Jan(0.89, $1,395, $1,388) Feb(0.86, $1,405, $1,393) Mar(0.86, $1,411, $1,396)
```

**Property B trends:**
```
B1: Dec(0.88, $1,600, $1,475) Jan(0.83, $1,575, $1,460) Feb(0.79, $1,540, $1,445) Mar(0.79, $1,525, $1,434)
B2: Dec(0.90, $1,640, $1,650) Jan(0.90, $1,650, $1,655) Feb(0.88, $1,650, $1,660) Mar(0.88, $1,654, $1,662)
```

### Default Client Config ("Stabilized Balanced")

```json
{
  "business_context": {
    "investment_thesis": "STABILIZED",
    "risk_profile": "BALANCED",
    "hold_period_years": 5,
    "renovation_in_progress": false,
    "renovation_units_offline": 0,
    "market_type": "SUBURBAN",
    "seasonal_profile": "MODERATE",
    "cap_rate_sensitivity": "MEDIUM",
    "business_plan_summary": "Stabilized suburban portfolio, 5-year hold, balanced risk tolerance, targeting 94% occupancy."
  },
  "occupancy_thresholds": {
    "target_occupancy": 0.94,
    "push_pricing_above": 0.96,
    "concern_below": 0.92,
    "action_below": 0.88,
    "crisis_below": 0.82
  },
  "exposure_thresholds": {
    "green_below": 0.05,
    "caution_below": 0.10,
    "action_below": 0.15,
    "crisis_above": 0.20
  },
  "pricing_tolerance": {
    "max_premium_vs_comps_pct": 0.05,
    "max_discount_vs_comps_pct": 0.05,
    "max_asking_vs_predicted_pct": 0.04,
    "acceptable_days_on_market": 21
  },
  "concession_policy": {
    "concessions_allowed": true,
    "max_concession_weeks_free": 8,
    "prefer_concession_over_base_cut": true,
    "concession_triggers": {"min_exposure_pct": 0.12, "min_days_on_market": 21}
  },
  "renewal_policy": {
    "max_renewal_increase_pct": 0.08,
    "retention_priority": "BALANCED",
    "turnover_cost_estimate": 1500,
    "never_increase_above_occupancy_threshold": 0.88
  },
  "lease_term_policy": {
    "preferred_term_months": 14,
    "allow_month_to_month": true,
    "mtm_premium_pct": 0.30,
    "short_term_premium_pct": 0.10,
    "target_peak_expiration_pct": 0.60
  },
  "experiment_policy": {
    "experiments_enabled": true,
    "max_price_spread_pct": 0.06,
    "max_price_spread_dollars": 100,
    "min_vacant_for_experiment": 3,
    "observation_window_days": 14,
    "auto_converge_enabled": false,
    "min_occupancy_for_experiment": 0.75
  },
  "amenity_benchmarks": {
    "expected_amenity_pct_of_rent": 0.06,
    "amenity_audit_threshold_pct": 0.08
  }
}
```

### Seed Data Generation Algorithm

Use the "Balancing unit" approach:
1. Generate N-1 units with realistic values
2. Set the Nth unit's value to hit the exact aggregate target
3. For rent rolls: assign based on lease vintage (older leases = lower rent, discount from predicted)
4. B1 special case: most in-place rents ABOVE asking ($1,525) since in-place avg is $1,572 — this reflects negative loss-to-lease in a declining market

## 4. Anti-Patterns

- **Do NOT** use random seeding without a reconciliation pass. Generate units with target-aware logic, then adjust the last unit(s) in each group to hit exact aggregates ("balancing unit" approach).
- **Do NOT** use `round()` for percentage calculations. Use `math.floor(x * 10**d + 0.5) / 10**d`.
- **Do NOT** create a single monolithic seed script. Separate by domain: seed_properties → seed_units → seed_comps → seed_snapshots → seed_config. They must run in order.
- **Do NOT** hardcode UUIDs. Generate them at seed time and pass references between seed scripts.
- **Do NOT** put business logic in models. Models are pure data containers. Logic lives in services/.
- **Do NOT** skip indexes. The schema specifies which columns need indexes — include them all.
- **Do NOT** make audit_log updateable. No `__table_args__` that permit updates. No API route for PUT/DELETE on audit entries.

## 5. Scenarios (Inline Validation)

**During development, verify these continuously:**

1. After migration: all 14 tables exist with correct columns and constraints.
2. After seeding properties: 2 properties, 4 unit types, correct total_units per type.
3. After seeding units: 156 total rows. Status distribution matches exactly per unit type.
4. After seeding units: `SELECT AVG(current_rent) FROM units WHERE unit_type_id=X AND status='OCCUPIED'` matches export In-Place Rent for each type.
5. After seeding units: `SELECT AVG(asking_rent) FROM units WHERE unit_type_id=X AND status IN ('VACANT','ON_NOTICE')` matches export Asking Rent.
6. After seeding units: `SELECT AVG(amenity_premium) FROM units WHERE unit_type_id=X` matches export Amenity Price.
7. After seeding comps: 9 comp properties, 18 comp_unit_types, 72 comp_rents.
8. After seeding comps: comp rent averages for March 2026 match export Comps column exactly (A1=$1,353, A2=$1,396, B1=$1,434, B2=$1,662).
9. After seeding snapshots: 16 rows (4 unit types × 4 months). March values match current rent roll aggregates.
10. After seeding config: 1 active config per property with all JSONB threshold fields populated.

## 6. Convergence Criteria

The spec is DONE when:

- [ ] `alembic upgrade head` creates all 14 tables without error
- [ ] `python -m app.seed.seed_all` populates all tables
- [ ] `pytest tests/test_reconciliation.py` runs 56+ checks, all pass:
  - 4 unit types × 14 checks each = 56 minimum (status counts, rent averages, exposure %, DOM, DV, amenity avg, executed rent avg, base rent uniformity, predicted=base+amenity for all units)
- [ ] `pytest tests/test_reconciliation.py::test_comp_averages` — 4 checks pass (comp avg per unit type)
- [ ] `pytest tests/test_reconciliation.py::test_snapshot_march_matches_rent_roll` — confirms March snapshot matches live aggregation
- [ ] Alembic migration is reversible (`alembic downgrade -1` works)
- [ ] FastAPI app starts (`uvicorn app.main:app`) and serves `/docs` with auto-generated OpenAPI schema showing all models
