# Spec 06: Auth, Historical Tracking & Platform Shell

## 1. Goal

Build the authentication system (JWT login/register), the platform shell (layout, navigation, property list dashboard), the config editor UI with business plan onboarding flow, the historical trend display, the comp set management UI, the experiment tracking UI, and the simulated comp refresh job. This is the "everything else" that makes the app feel like a complete platform rather than a one-off diagnostic tool.

**Measurable outcome:** A user can register, login, view a property dashboard with KPIs, configure thresholds via the config editor, view historical trends, manage comp sets, run diagnostics, and see experiment status — all within a cohesive platform UI.

## 2. Exemplar

**Auth pattern:** `tecelit/fast-api-boilerplate` (https://github.com/tecelit/fast-api-boilerplate) — Gene-transfuse the JWT auth implementation: bcrypt hashing, PyJWT token creation, FastAPI dependency injection for `get_current_user`. Adapt their role-based access pattern.

**Dashboard layout:** `luck18210/react-tailwind-dashboard` — Reference for sidebar + main content layout with Tailwind. Adapt for our navigation structure (Properties → Property Detail → Diagnostic/Config/Comps/Experiments).

**Config editor:** No direct exemplar. Build a form with sections matching the config schema. Each section (occupancy thresholds, exposure thresholds, etc.) renders as a card with labeled sliders and number inputs. Include Claude-generated reasoning tooltips.

## 3. Constraints

### Backend — Auth

- JWT tokens with 24-hour expiry. Payload: `{user_id, organization_id, role, exp}`.
- `POST /auth/register` creates user + organization. First user is admin.
- `POST /auth/login` returns `{access_token, token_type: "bearer", user: {...}}`.
- `GET /auth/me` returns current user with organization.
- All non-auth routes require valid JWT in `Authorization: Bearer <token>` header.
- FastAPI dependency `get_current_user` extracts user from token, verifies expiry.
- All database queries filter by `organization_id` from the token (multi-tenancy).
- Password hashing with bcrypt. Minimum 8 characters.

### Backend — Config

- `POST /properties/{id}/config/generate` sends business plan text to Claude, returns recommended config with reasoning per section.
- `POST /properties/{id}/config` saves config (deactivates previous, creates new version).
- Config versioning: `version` auto-increments. Only `is_active=True` config used by engine.
- Config generation Claude prompt: Claude ingests business plan text → recommends threshold config with reasoning per section → returns full config JSON matching the client_configs schema.

### Backend — Comp Management

- `POST /properties/{id}/comps/suggest` calls Claude with property attributes, returns suggested comp properties.
- `POST /comps/refresh` triggers simulated refresh: for each comp, generate new rent observation with ±1-2% noise from latest value, insert into comp_rents, update `last_refreshed_at`.
- Refresh creates an audit_log entry.

### Backend — Experiments

- `POST /experiments/{id}/approve` sets status=APPROVED, logs in audit.
- `POST /experiments/{id}/cancel` sets status=CANCELLED with reason.
- `PUT /experiments/{id}/assignments/{aid}` updates outcome data (leased, lease_date, tours_count).
- `POST /experiments/{id}/evaluate` calls Claude to assess results and recommend convergence/extension.

### Frontend — Platform Shell

- Sidebar navigation: Properties (list), selected Property → sub-nav (Dashboard, Config, Comps, Diagnostics, Experiments).
- Property Dashboard: cards showing each unit type with occupancy, exposure, asking rent, days on market. Color-coded by health (from latest diagnostic if available, or raw metrics).
- Header: user name, organization name, logout button, property switcher dropdown.

### Frontend — Config Editor

- Business plan upload (text area or file upload) → "Generate Config" button → loading → Claude returns recommended config → config displayed in editor with Claude's reasoning shown as info tooltips.
- Editor organized by section (matching config schema): Occupancy, Exposure, Pricing Tolerance, Concessions, Renewals, Lease Terms, Experiments, Amenities.
- Each numeric threshold has a slider + number input. Sliders have min/max based on reasonable ranges.
- "Preview Diagnosis" button: shows how the current portfolio would be flagged with these thresholds (calls flag_generator with draft config, displays flag count per unit type).
- "Save & Activate" button: saves config, deactivates previous version.

### Frontend — Historical Trends

- Displayed on property dashboard (sparkline charts per unit type).
- Also available as a dedicated view: 4 line charts (one per unit type) showing occupancy + asking + comps over available snapshot months.
- Data from `GET /properties/{id}/snapshots`.

### Frontend — Comp Management

- List of comp properties with current asking rents.
- "Suggest Comps" button: calls Claude API, shows suggestions with checkboxes.
- "Refresh Rents" button: triggers simulated refresh, shows updated values.
- Comp rent time series displayed as small line charts per comp.

### Frontend — Experiment Tracking

- List of experiments with status badges (Proposed/Approved/Active/Converged/Cancelled).
- Experiment detail view: arm diagram, unit assignments, outcome data entry fields.
- "Approve" and "Cancel" buttons with confirmation modals.
- "Evaluate Results" button: calls Claude to assess and shows recommendation.

## 4. Anti-Patterns

- **Do NOT** build a full user management system. One user per organization for MVP. No password reset, no email verification, no user invitations. Just register + login.
- **Do NOT** build the config editor before the auth system. Auth gates everything.
- **Do NOT** skip the config preview. The "Preview Diagnosis" feature is a key differentiator — operators can see the impact of threshold changes BEFORE activating.
- **Do NOT** make the comp refresh produce wildly different values. ±1-2% noise from the latest observation. The trend should be recognizable as a continuation, not a random walk.
- **Do NOT** build complex experiment evaluation logic in the frontend. The frontend sends "evaluate" to the backend, which calls Claude, and returns the recommendation. Frontend just displays it.
- **Do NOT** use localStorage for auth tokens. Use httpOnly cookies or in-memory storage (React context). For MVP, React context with sessionStorage fallback is acceptable.

## 5. Scenarios

1. **Registration flow:** New user navigates to `/register`, enters email/password/name/org name. Submits → account created → redirected to login. Login → redirected to property list (which shows the 2 seeded properties).

2. **Config onboarding:** User navigates to Property B → Config tab. Sees default config. Pastes a business plan excerpt: "Stabilized suburban portfolio, 5-year hold, medium risk tolerance, targeting 94% occupancy." Clicks "Generate Config". After ~4 seconds, config editor populates with Claude-recommended thresholds. Each section shows reasoning tooltip ("We recommend a target occupancy of 94% based on your stated goal..."). User adjusts exposure crisis threshold from 0.20 to 0.18 using slider. Clicks "Preview Diagnosis" — sees B1 flag count go from 12 to 12 (no change at this threshold). Clicks "Save & Activate".

3. **Comp suggestion flow:** User navigates to Property A → Comps tab. Clicks "Suggest Comps". Claude returns 5 suggestions. User deselects 1, adds a manual comp. Saves. Comp list shows 5 properties with latest rents.

4. **Comp refresh:** User clicks "Refresh Rents". After ~2 seconds, comp rents update with slightly different values. "Last refreshed" timestamp updates. Audit log shows the refresh event.

5. **Experiment tracking:** After running a diagnostic, user navigates to Experiments tab. Sees "B2 Price Experiment — Proposed" with 3 arms. Clicks into it, sees unit assignments. Clicks "Approve". Status changes to "Approved". User manually enters that unit B-210 (Test arm) received an application after 8 days. Clicks "Evaluate Results" — Claude recommends "Insufficient data, extend window by 7 days."

6. **Historical trends:** Property dashboard shows sparkline for each unit type. B1 sparkline shows declining occupancy (red trend). A1 shows stable (green). Clicking into the full trend view shows the 4-month line charts with dual axes.

## 6. Convergence Criteria

- [ ] `POST /auth/register` creates user + org; `POST /auth/login` returns valid JWT
- [ ] Protected endpoints return 401 without token, 200 with valid token
- [ ] `/auth/me` returns correct user with organization
- [ ] Config generation endpoint returns valid config JSON from Claude
- [ ] Config save creates new version, deactivates old
- [ ] Comp suggest endpoint returns comp suggestions from Claude
- [ ] Comp refresh creates new comp_rent entries with realistic noise
- [ ] Experiment approve/cancel/evaluate endpoints work correctly
- [ ] Frontend: login → property list → property dashboard → config editor → diagnostic → slideshow — full flow works end-to-end
- [ ] Config editor shows sliders for all threshold sections with "Preview Diagnosis" working
- [ ] Comp management UI displays comps with refresh capability
- [ ] Experiment tracking UI shows experiment status and allows outcome data entry
- [ ] Historical trend sparklines appear on property dashboard
- [ ] Audit log records all config changes, diagnostic runs, experiment approvals, and comp refreshes
- [ ] All API endpoints filter by organization_id from JWT (multi-tenancy verified)
