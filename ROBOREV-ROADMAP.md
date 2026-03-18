# RoboRev — Product Roadmap & Next Steps

## Path to Best-in-Class Multifamily Revenue Management

Organized by priority tier — what moves the needle most for operator adoption and retention.

---

## Tier 1: Table Stakes (Must Have Before First Real Client)

### 1. Live Data Ingestion
Right now all data is seeded. A real tool needs:
- PMS integration layer (Yardi SOAP API, RealPage API, Entrata REST, AppFolio) to pull live rent rolls, lease data, unit status
- A normalized data model that maps each PMS's schema to RoboRev's internal model
- Nightly sync + on-demand refresh
- **This is the single biggest gap between "demo" and "product"**

### 2. Real Comp Data Pipeline
The simulated comp refresh is a placeholder. Real options:
- Apartments.com / Zillow / CoStar API partnerships (expensive, gated)
- Web scraper for public apartment listings (legal gray area — public asking rents only, which is the compliance-safe approach)
- Manual comp entry UI with bulk import (CSV)
- The comp data quality determines the quality of every pricing spread calculation

### 3. Multi-Property Scale
The engine runs in 9.7ms for 72 units. But real portfolios are 5,000-50,000 units across 20-200 properties. Need:
- Async diagnostic pipeline (Celery + Redis) — the sync architecture was an MVP decision (DEC-006), designed to be swappable
- Property-group and regional roll-ups
- Portfolio-level dashboards that aggregate across properties
- Batch diagnostic runs ("diagnose all 47 properties overnight")

### 4. User Roles & Permissions
Current: one admin user. Real operators have:
- **Site teams** — see their property only, can input data, can't change pricing
- **Regional managers** — see their region, can approve pricing changes
- **Asset managers** — see everything, set strategy/config, approve experiments
- **Executives** — portfolio-level dashboards only, no operational actions
- Role-based access control on every endpoint, not just org-level filtering

---

## Tier 2: Competitive Differentiators (Why Choose RoboRev Over RealPage/Yardi)

### 5. Outcome Tracking & Learning Loop
This is the biggest missed opportunity in the industry. Current tools recommend prices but never close the loop. RoboRev should:
- Track what happened after every recommendation (did the unit lease? how fast? at what price?)
- Build a property-specific model: "At this property, a $50 cut historically accelerates leasing by 8 days"
- Show operators their recommendation acceptance rate and the ROI of following vs. ignoring AI advice
- **This creates a flywheel:** better data → better recommendations → more trust → more adoption → more data

### 6. Renewal Pricing Engine
Renewals are 50%+ of the rent roll but our current engine barely touches them. A real renewal engine needs:
- Tenant retention probability model (based on tenure, rent increase history, market alternatives)
- Turnover cost calculator (vacancy loss + make-ready + leasing cost = typically $3,000-$5,000)
- Optimal renewal offer calculator: "This tenant has a 40% chance of leaving at a 5% increase but only 15% at 3% — the expected value of 3% is higher"
- Renewal vs. new-lease arbitrage: sometimes it's better to let a below-market tenant leave

### 7. Concession Intelligence
Concessions are a critical lever but poorly understood. The tool should:
- Model concession impact on net effective rent vs. headline rent (important for property valuations/cap rates)
- Track concession effectiveness: "1 month free converts 3x better than $50/mo off at this property"
- Auto-suggest concession types based on market and unit characteristics
- Flag when concessions are cannibalizing non-concession demand

### 8. Lease Term Optimization
The current engine has basic lease term metrics. Best-in-class would:
- Build an expiration heatmap showing month-by-month exposure risk
- Recommend specific lease terms per unit to concentrate expirations in peak season (May-Sep)
- Price short-term and month-to-month premiums dynamically based on seasonal position
- Model the revenue impact of a 12-month vs. 14-month vs. 16-month lease signed today

---

## Tier 3: UX & Workflow Integration (What Makes Operators *Love* Using It)

### 9. Daily Pricing Worksheet
Operators don't want to "run a diagnostic" — they want a daily workflow:
- Morning view: "Here are today's pricing actions" — units that need attention, sorted by urgency
- Each action is a card: unit number, current price, recommended price, reasoning, approve/reject buttons
- Batch approve with one click ("approve all 7 recommendations")
- **This replaces the Excel pricing sheet most operators use today**

### 10. AI Chat Interface
Instead of just running diagnostics, let operators ask questions:
- "Why is B1 not leasing?"
- "What would happen if I cut B2 by $50?"
- "Show me properties in my portfolio with similar occupancy patterns"
- "What's my exposure risk if 3 more leases expire next month?"
- The data is already in the system — a conversational interface over the metrics engine would be transformative

### 11. Alerts & Notifications
Proactive, not reactive:
- "B1 occupancy dropped below 80% — 3rd consecutive week of decline"
- "A2 has 4 units that have been on market for 30+ days"
- "Comp rents in Harbor Point dropped 2.5% this month"
- "Experiment B2-001 has enough data to evaluate — review results"
- Email digest, Slack integration, in-app notification center

### 12. Mobile Experience
Site teams live on their phones. They need:
- Mobile-optimized pricing approval workflow
- Quick glance dashboard (occupancy, vacant count, top actions)
- Push notifications for urgent pricing alerts
- Photo upload for unit condition documentation (ties into non-price factor investigation)

---

## Tier 4: Data & Intelligence Moat (Long-Term Defensibility)

### 13. Market Intelligence Layer
Move beyond property-level to market-level insights:
- Submarket supply/demand tracking (new construction pipeline, absorption rates)
- Seasonal pattern modeling by MSA (not just generic "peak is May-Sep")
- Economic indicator integration (employment, migration, housing starts)
- This data compounds over time and becomes a moat competitors can't easily replicate

### 14. Portfolio Optimization
Cross-property intelligence that no single-property tool can provide:
- "Property A and Property C are cannibalizing each other's demand — they're 0.5 miles apart with identical unit mix"
- Capital allocation recommendations: "Renovating 12 units at Property B would generate $18,000/year more than renovating at Property D"
- Portfolio-level pricing coordination (price one property slightly below market to fill, another slightly above to maximize)

### 15. Predictive Occupancy Model
Move from reactive ("you're at 79%") to predictive ("you'll be at 75% in 45 days"):
- Lease expiration + historical turn rate + seasonal demand = forecasted occupancy
- Leading indicators: tour-to-application conversion dropping, DOM increasing, etc.
- "If you don't act on B1 this week, you'll hit 75% occupancy by April 15 and lose experiment eligibility"

### 16. Anonymized Benchmarking
The compliance-safe version of cross-customer data:
- "Your B1 asking rent is in the 85th percentile for 1BR/1BA in this submarket"
- "Properties with similar age/class in this MSA average 92% occupancy — you're at 79%"
- Aggregate stats at submarket/MSA level (never property-level from other customers)
- This is the data network effect that makes the platform more valuable with each customer

---

## Tier 5: Business Model & Go-to-Market

### 17. Pricing Model
- Per-unit/month SaaS ($2-5/unit/month = $3,000-$7,500/month for a 1,500-unit portfolio)
- Value-based tier: basic (metrics + flags) vs. pro (AI diagnosis + experiments) vs. enterprise (portfolio optimization + benchmarking)
- Free tier for <100 units to drive adoption at smaller operators

### 18. Integration Ecosystem
- Yardi, RealPage, Entrata connectors (PMS data in)
- ILS posting integration (push recommended prices to Apartments.com, Zillow)
- Accounting system sync (rent changes flow to GL)
- Maintenance system integration (correlate unit condition with leasing velocity)

### 19. Compliance Certification
- Get an independent third-party audit of the algorithm (for antitrust defense)
- Publish methodology documentation (what data goes in, what doesn't)
- Build an "algorithm impact assessment" report that clients can show regulators
- **This becomes a selling point:** "We're the only RM tool with a published, audited methodology"

---

## Recommended Priority Order

If building toward first paying client, the 5 highest-leverage items:

| Priority | Item | Why |
|----------|------|-----|
| **1** | PMS integration (#1) | Without live data, nothing else matters |
| **2** | Daily pricing worksheet (#9) | The daily touchpoint that drives adoption — replaces Excel |
| **3** | Outcome tracking (#5) | Closes the loop, builds trust, creates a data moat |
| **4** | Renewal engine (#6) | 50%+ of revenue comes from renewals, current coverage is minimal |
| **5** | AI chat (#10) | The data is already there — conversational layer is the killer feature |

These five would take RoboRev from "impressive demo" to "tool operators can't live without."

---

## Competitive Landscape Context

| Competitor | Strength | RoboRev's Edge |
|-----------|----------|----------------|
| RealPage (YieldStar/AIRM) | Market share (4M+ units), data scale | DOJ settlement constrains data advantage; opaque algorithms; RoboRev is white-box and compliant by architecture |
| Yardi (Revenue IQ) | Deep PMS integration (8M+ Voyager users), clean antitrust record | Tightly coupled to Voyager ecosystem; RoboRev is PMS-agnostic with configurable thresholds |
| REBA Rent | Transparency-first, designed post-antitrust | No AI diagnosis, no experiments, deterministic rules only |
| Rentana | Fast setup, ML-based, proven pilot results | No MAB experiments, no action plans, no configurable client strategy |
| Manual (Excel) | Familiar, trusted, no vendor risk | Slow, error-prone, no comp integration, no experiments |

**RoboRev's unique position:** The only tool that combines deterministic auditability (Layer 1) with configurable client strategy (Layer 1.5) with intelligent AI judgment (Layer 3) — AND offers MAB price experimentation AND publishes its methodology for regulatory compliance.
