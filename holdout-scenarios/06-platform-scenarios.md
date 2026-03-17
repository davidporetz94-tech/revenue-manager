# Holdout Scenarios: Spec 06 — Auth, Historical Tracking & Platform Shell

## Scenario 6.1: Authentication Flow

### Setup
Clean database with seeded demo user (demo@example.com / demo123).

### Trigger
User navigates to app root URL.

### Satisfaction Criteria

**Login:** Valid credentials → JWT → property list. Invalid → error. No credential enumeration (same error for wrong email vs wrong password).

**Registration:** Valid submission → account created → redirect to login. Duplicate email → error. Short password → validation error.

**Protected routes:** No token → 401. Valid token → 200. Expired token → 401. Other org's property → 404 (not 403).

**Multi-tenancy:** Demo user sees only "Demo Client" properties. All DB queries filter by organization_id. URL manipulation cannot access other orgs' data.

**Session:** JWT in React context. Logout clears token. Page refresh maintains session. Concurrent tabs work (stateless JWT).

### Edge Cases
- Tampered JWT payload → 401
- Token with valid signature but non-existent user_id → 401
- `/auth/me` returns correct user + organization

---

## Scenario 6.2: Historical Trend Display & Config Editor

### Setup
User logged in. Property B selected. 4 months of snapshots seeded.

### Trigger
View dashboard trends → navigate to Config tab → modify and preview.

### Satisfaction Criteria

**Trends:** Sparklines on dashboard — B1 declining (red), B2 flat. Full trend view shows 4-point line charts with dual y-axis. Data matches snapshots: B1 Dec occ=0.88 → Mar occ=0.79; B1 asking $1,600 → $1,525; B1 comps $1,475 → $1,434.

**Config editor:** All 8 sections rendered with sliders/inputs. Values match seeded default. Slider↔input sync works. Sensible min/max ranges.

**Business plan onboarding:** Text area + "Generate Config" → Claude returns recommended thresholds with reasoning tooltips → user can adjust before saving.

**Config preview:** "Preview Diagnosis" shows flag counts per unit type. Changing a threshold updates the preview. Default: A1=3, A2=7, B1=12, B2=7.

**Config save:** Creates new version, deactivates old, increments version number, logs to audit_log.

**Comp management:** List shows comps with rents. "Refresh" creates new observations with ±1-2% noise. Timestamp updates. Audit logged.

**Experiment tracking:** Proposed experiments visible. Approve changes status. Unit assignments shown. Audit logged.

### Edge Cases
- Extreme config values (crisis_below=0.50) reduce B1 flags — preview reflects this
- Invalid config (target > push_above) shows validation error
- Comp refresh with no comps → graceful handling
- Only 1 month of snapshot data → single point, no line
- Approving an already-cancelled experiment → error
