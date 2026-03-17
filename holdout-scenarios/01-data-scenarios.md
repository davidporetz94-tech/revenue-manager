# Holdout Scenarios — Spec 01: Data Model & Dummy Data

## Scenario 1.1: Full Data Reconciliation

**Setup:** Database seeded via `seed_all.py`. All 14 tables populated.

**Trigger:** Run `pytest tests/test_reconciliation.py`

**Expected flow:**
1. Test connects to database, queries each unit type
2. For each of the 4 unit types (A1, A2, B1, B2), asserts:
   - `COUNT(*) WHERE status='OCCUPIED'` matches export Occupied column
   - `COUNT(*) WHERE status='VACANT'` matches export Vacant column
   - `COUNT(*) WHERE status='ON_NOTICE'` matches export On Notice column
   - `COUNT(*)` matches export Total Units column
   - `AVG(current_rent) WHERE status='OCCUPIED'` matches export In-Place Rent (integer)
   - `AVG(asking_rent) WHERE status IN ('VACANT','ON_NOTICE')` matches export Asking Rent
   - `AVG(amenity_premium)` matches export Amenity Price
   - All `base_rent` values equal export Base Rent (uniform within type)
   - `AVG(days_on_market) WHERE status IN ('VACANT','ON_NOTICE')` matches export Days on Market
   - `AVG(days_vacant) WHERE status='VACANT'` matches export Days Vacant
   - `round_half_up((vacant + on_notice) / total, 2)` matches export Total Exposure %
   - `round_half_up(vacant / total, 2)` matches export Vacant Exposure %
   - `predicted_rent == base_rent + amenity_premium` for EVERY unit (not just averages)
   - Demand Score stored in snapshot matches export
3. For executed rent: average of `last_executed_rent` where `last_executed_date >= today - 90 days` matches export Executed Rent per unit type
4. Comp averages: for each unit type, average of March comp_rents matches export Comps column

**Satisfaction criteria:**
- All 60+ assertions pass
- `round_half_up` used for all percentage comparisons
- Integer dollar comparison for rent fields

**Edge cases:**
- B2 Vacant Exposure: 6/48 = 0.125 → must round to 0.13 (round-half-up), not 0.12
- B1 on-notice unit: `move_out_date` must be 31-60 days out (makes 30d exp=0.21, 60d=0.25)
- B1 executed rent ($1,655) is HIGHER than asking ($1,525) — seed data must support this with older execution dates
- No unit should have `amenity_premium < 0` or `predicted_rent != base_rent + amenity_premium`

---

## Scenario 1.2: Schema Integrity & Relationships

**Setup:** Fresh database with `alembic upgrade head` applied.

**Trigger:** Run `pytest tests/test_schema.py`

**Expected flow:**
1. Verify all 14 tables exist
2. Test foreign key relationships by JOINing across all FK pairs
3. Verify CHECK constraints reject invalid values (e.g., `status='INVALID'` on units)
4. Verify UNIQUE constraints reject duplicates (e.g., duplicate unit_number per property)
5. Verify JSONB columns on client_configs accept and return valid JSON
6. Verify `alembic downgrade -1` reverses cleanly and `alembic upgrade head` re-applies

**Satisfaction criteria:**
- All FK JOINs return expected row counts
- Invalid insertions raise `IntegrityError`
- Migration round-trip (upgrade → downgrade → upgrade) succeeds
- UUIDs are generated for all PKs (no sequential integers)

**Edge cases:**
- audit_log ORM model must NOT have update/delete methods
- Inserting 0-length `password_hash` should fail (NOT NULL constraint)
- JSONB fields accept nested objects (config thresholds are nested)
