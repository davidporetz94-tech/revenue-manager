# Holdout Scenarios — Spec 04: Narrative Layer

## Scenario 4.1: Narrative Coherence and Accuracy

**Setup:** Complete diagnostic run for Property B with results stored in diagnostic_runs. Narrative generation triggered.

**Trigger:** `GET /api/v1/diagnostic/{run_id}/slides`

**Expected flow:**
1. Slide deck JSON returns with 12 slides, each having narrative and viz_data
2. Narrative consistency check runs:
   - Extract all dollar amounts from narrative text across all slides
   - Every `$X,XXX` pattern traces back to a known metric value
   - No dollar amount appears that doesn't exist in the metrics
3. Specific content checks:
   - Slide 2 headline: contains a clear verdict statement, ≤20 words
   - Slide 5 B1 narrative: mentions "$91" (asking vs comps spread) or "$1,525" (asking) or "25%" (exposure)
   - Slide 5 B2 narrative: mentions the puzzle/anomaly of being priced at comps but not leasing
   - Slide 7 narrative: mentions total daily or monthly vacancy cost
   - Slide 9 narratives: explain WHY each Phase 1 action is recommended
   - Slide 10 narratives: use plain language ("If 2 of your 3 test units lease..."), NOT technical jargon ("convergence criterion met")
4. Viz data checks:
   - Slide 7 STACKED_BAR: B2 bar value = $9,924, B1 = $7,625, A2 = $7,055, A1 = $2,730
   - Slide 6 LINE_CHARTS: B1 occupancy series = [0.88, 0.83, 0.79, 0.79]
   - Slide 3 DATA_TABLE: contains all 4 rows with correct values matching export

**Satisfaction criteria:**
- Zero false positives in consistency check (no valid metrics flagged as errors)
- Zero true positives (no hallucinated numbers in narrative)
- Narrative addresses client directly ("Your B1 units..." not "The B1 units...")
- No markdown formatting in narrative text (no `**bold**`, no `## headers`)
- Viz data values match metrics engine output to the penny

**Edge cases:**
- If Claude generates a percentage like "79% occupancy" — this must match the 0.79 in metrics (not 0.7917). Verify the prompt instructs Claude to use the same rounding displayed in the export.
- If narrative mentions "comps at $1,434" for B1 — this is correct (from comp avg). Verify it traces to comp data, not to a hallucination.

---

## Scenario 4.2: Missing Data Graceful Handling

**Setup:** Modify the diagnostic run to simulate a partial failure: diagnosis_json exists but narrative_json is null (Claude narrative call failed).

**Trigger:** `GET /api/v1/diagnostic/{run_id}/slides`

**Expected flow:**
1. Slide deck still returns 200 with 12 slides
2. Slides with Claude-generated narrative fields contain FALLBACK text:
   - Template-based narrative using metrics values
   - e.g., "Property B unit type B1 has an occupancy of 79% with 5 vacant units and 25% total exposure."
3. Viz data is UNAFFECTED — all charts render with correct data
4. Metadata includes `"narrative_fallback": true` indicator
5. No error is surfaced to the user (graceful degradation)

**Satisfaction criteria:**
- 200 response, not 500
- All 12 slides present with non-null narrative and viz_data
- Fallback narrative contains accurate numbers from metrics (not placeholder text)
- Viz data identical to a successful run
- Frontend can render the deck without special-casing fallback vs normal

**Edge cases:**
- What if BOTH diagnosis and narrative fail? The slide deck should still include slides 1-3 (which only need raw metrics) with useful content. Slides 4-12 would have minimal fallback content.
- What if metrics computation itself fails? Diagnostic run should be marked FAILED with error_message. Slides endpoint should return 404 or 422.
