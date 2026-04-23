import React, { useState, useEffect, useCallback } from 'react';
import { formatDollar } from '../../utils/format';
import { previewRenewalPricing, saveRenewalRule } from '../../api/client';

const CALC_METHODS = [
  { value: 'DISCOUNT_FROM_NEW', label: 'Discount from New Lease' },
  { value: 'INCREASE_FROM_IN_PLACE', label: 'Increase from In-Place' },
];

function pctDisplay(val) {
  return (val * 100).toFixed(1) + '%';
}

export default function RenewalRuleCard({
  propertyId,
  unitTypeCode,
  targetMonth,
  floorplanData,
  existingRule,
  onRuleSaved,
}) {
  const { bed, bath, asking_rent, unit_count, units } = floorplanData;

  // Rule state — initialize from existing or defaults
  const [calcMethod, setCalcMethod] = useState(existingRule?.calc_method || 'INCREASE_FROM_IN_PLACE');
  const [calcValue, setCalcValue] = useState(existingRule?.calc_value ?? 0.03);
  const [minIncrease, setMinIncrease] = useState(existingRule?.min_increase_pct ?? 0.02);
  const [maxIncrease, setMaxIncrease] = useState(existingRule?.max_increase_pct ?? 0.08);

  const [preview, setPreview] = useState(existingRule?.outputs || null);
  const [previewSummary, setPreviewSummary] = useState(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(!!existingRule);
  const [expanded, setExpanded] = useState(!existingRule);
  const [dirty, setDirty] = useState(false);

  // Compute preview when rules change
  const computePreview = useCallback(async () => {
    if (!propertyId || !unitTypeCode || !targetMonth) return;
    setPreviewLoading(true);
    try {
      const result = await previewRenewalPricing({
        property_id: propertyId,
        unit_type_code: unitTypeCode,
        target_month: targetMonth,
        calc_method: calcMethod,
        calc_value: calcValue,
        min_increase_pct: minIncrease,
        max_increase_pct: maxIncrease,
      });
      setPreview(result.outputs);
      setPreviewSummary(result.summary);
    } catch {
      setPreview(null);
      setPreviewSummary(null);
    } finally {
      setPreviewLoading(false);
    }
  }, [propertyId, unitTypeCode, targetMonth, calcMethod, calcValue, minIncrease, maxIncrease]);

  // Auto-preview on mount and when rules change
  useEffect(() => {
    const timer = setTimeout(computePreview, 300);
    return () => clearTimeout(timer);
  }, [computePreview]);

  function handleParamChange(setter) {
    return (val) => {
      setter(val);
      setDirty(true);
      setSaved(false);
    };
  }

  async function handleSave() {
    setSaving(true);
    try {
      const result = await saveRenewalRule({
        property_id: propertyId,
        unit_type_code: unitTypeCode,
        target_month: targetMonth,
        calc_method: calcMethod,
        calc_value: calcValue,
        min_increase_pct: minIncrease,
        max_increase_pct: maxIncrease,
      });
      setSaved(true);
      setDirty(false);
      if (onRuleSaved) onRuleSaved(unitTypeCode, result);
    } catch (err) {
      // eslint-disable-next-line no-console
      console.error('Failed to save renewal rule:', err);
    } finally {
      setSaving(false);
    }
  }

  const avgInPlace = units.length > 0
    ? Math.round(units.reduce((s, u) => s + (u.current_rent || 0), 0) / units.length)
    : 0;

  const borderColor = saved ? '#059669' : dirty ? '#0D9488' : '#d6d3d1';

  return (
    <div
      className="bg-white rounded-xl border shadow-card transition-all"
      style={{ borderColor, borderLeftWidth: '4px', borderLeftColor: saved ? '#059669' : '#0D9488' }}
    >
      {/* Header — always visible */}
      <div
        className="px-5 py-4 flex items-center justify-between cursor-pointer hover:bg-stone-50/50 transition-colors"
        onClick={() => setExpanded(!expanded)}
      >
        <div className="flex items-center gap-4">
          <div>
            <span className="font-mono text-lg font-bold text-stone-800">{unitTypeCode}</span>
            <span className="text-xs text-stone-400 ml-2">{bed}bd/{bath}ba</span>
          </div>
          <div className="h-8 w-px bg-stone-200" />
          <div className="flex items-center gap-1.5">
            <span className="font-mono text-2xl font-bold" style={{ color: '#0D9488' }}>{unit_count}</span>
            <span className="text-xs text-stone-400">expiring</span>
          </div>
          <div className="h-8 w-px bg-stone-200" />
          <div>
            <span className="text-[10px] text-stone-400 uppercase tracking-wider">Avg In-Place</span>
            <span className="font-mono text-sm font-bold text-stone-700 block">{formatDollar(avgInPlace)}</span>
          </div>
          <div>
            <span className="text-[10px] text-stone-400 uppercase tracking-wider">New Lease</span>
            <span className="font-mono text-sm font-bold block" style={{ color: '#7C3AED' }}>{formatDollar(asking_rent)}</span>
          </div>
        </div>

        <div className="flex items-center gap-3">
          {saved && (
            <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded border bg-emerald-50 border-emerald-200">
              <svg className="w-3.5 h-3.5 text-emerald-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
              </svg>
              <span className="text-[10px] font-bold text-emerald-700">RULES SET</span>
            </span>
          )}
          {previewSummary && (
            <div className="text-right">
              <span className="text-[10px] text-stone-400 uppercase tracking-wider block">Monthly Impact</span>
              <span className="font-mono text-sm font-bold" style={{ color: (previewSummary.total_monthly_delta || 0) >= 0 ? '#059669' : '#DC2626' }}>
                {(previewSummary.total_monthly_delta || 0) >= 0 ? '+' : ''}{formatDollar(previewSummary.total_monthly_delta || 0)}
              </span>
            </div>
          )}
          <svg
            className={`w-5 h-5 text-stone-400 transition-transform ${expanded ? 'rotate-180' : ''}`}
            fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}
          >
            <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
          </svg>
        </div>
      </div>

      {/* Expanded content */}
      {expanded && (
        <div className="border-t border-stone-100">
          {/* Rule configuration */}
          <div className="px-5 py-4 bg-stone-50/50">
            <div className="flex items-center gap-2 mb-3">
              <div className="w-1.5 h-1.5 rounded-full bg-teal-500" />
              <span className="text-[10px] text-stone-500 uppercase tracking-wider font-semibold">Renewal Rules</span>
            </div>
            <div className="grid grid-cols-4 gap-4">
              {/* Calc method */}
              <div>
                <label className="text-[10px] text-stone-400 uppercase tracking-wider block mb-1">Method</label>
                <select
                  value={calcMethod}
                  onChange={(e) => handleParamChange(setCalcMethod)(e.target.value)}
                  className="w-full text-xs font-mono border border-stone-300 rounded-lg px-2.5 py-2 bg-white focus:outline-none focus:ring-2 focus:ring-teal-400/40 focus:border-teal-400 transition-colors"
                >
                  {CALC_METHODS.map(m => (
                    <option key={m.value} value={m.value}>{m.label}</option>
                  ))}
                </select>
              </div>
              {/* Calc value */}
              <div>
                <label className="text-[10px] text-stone-400 uppercase tracking-wider block mb-1">
                  {calcMethod === 'DISCOUNT_FROM_NEW' ? 'Discount %' : 'Increase %'}
                </label>
                <div className="relative">
                  <input
                    type="number"
                    step="0.5"
                    value={+(calcValue * 100).toFixed(1)}
                    onChange={(e) => handleParamChange(setCalcValue)(Number(e.target.value) / 100)}
                    className="w-full text-xs font-mono border border-stone-300 rounded-lg px-2.5 py-2 pr-6 bg-white focus:outline-none focus:ring-2 focus:ring-teal-400/40 focus:border-teal-400 transition-colors"
                  />
                  <span className="absolute right-2.5 top-1/2 -translate-y-1/2 text-xs text-stone-400">%</span>
                </div>
              </div>
              {/* Min increase */}
              <div>
                <label className="text-[10px] text-stone-400 uppercase tracking-wider block mb-1">Min Increase</label>
                <div className="relative">
                  <input
                    type="number"
                    step="0.5"
                    value={+(minIncrease * 100).toFixed(1)}
                    onChange={(e) => handleParamChange(setMinIncrease)(Number(e.target.value) / 100)}
                    className="w-full text-xs font-mono border border-stone-300 rounded-lg px-2.5 py-2 pr-6 bg-white focus:outline-none focus:ring-2 focus:ring-teal-400/40 focus:border-teal-400 transition-colors"
                  />
                  <span className="absolute right-2.5 top-1/2 -translate-y-1/2 text-xs text-stone-400">%</span>
                </div>
              </div>
              {/* Max increase */}
              <div>
                <label className="text-[10px] text-stone-400 uppercase tracking-wider block mb-1">Max Increase</label>
                <div className="relative">
                  <input
                    type="number"
                    step="0.5"
                    value={+(maxIncrease * 100).toFixed(1)}
                    onChange={(e) => handleParamChange(setMaxIncrease)(Number(e.target.value) / 100)}
                    className="w-full text-xs font-mono border border-stone-300 rounded-lg px-2.5 py-2 pr-6 bg-white focus:outline-none focus:ring-2 focus:ring-teal-400/40 focus:border-teal-400 transition-colors"
                  />
                  <span className="absolute right-2.5 top-1/2 -translate-y-1/2 text-xs text-stone-400">%</span>
                </div>
              </div>
            </div>
          </div>

          {/* Unit-level preview */}
          <div className="px-5 py-4">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <div className="w-1.5 h-1.5 rounded-full bg-violet-500" />
                <span className="text-[10px] text-stone-500 uppercase tracking-wider font-semibold">Unit Preview</span>
                {previewLoading && (
                  <div className="w-3 h-3 border border-stone-300 border-t-stone-600 rounded-full animate-spin ml-1" />
                )}
              </div>
              {previewSummary && (
                <div className="flex items-center gap-4 text-[10px]">
                  <span className="text-stone-400">
                    Avg increase: <span className="font-mono font-bold text-stone-600">{pctDisplay(previewSummary.avg_increase_pct || 0)}</span>
                  </span>
                  {previewSummary.clamped_count > 0 && (
                    <span className="text-amber-600 font-bold">
                      {previewSummary.clamped_count} clamped
                    </span>
                  )}
                  <span className="text-stone-400">
                    Annual: <span className="font-mono font-bold text-emerald-600">+{formatDollar(previewSummary.total_annual_delta || 0)}</span>
                  </span>
                </div>
              )}
            </div>

            {/* Unit table */}
            <div className="rounded-lg border border-stone-200 overflow-hidden">
              <div className="bg-stone-100 px-4 py-2 grid items-center text-[10px] text-stone-500 uppercase tracking-wider font-semibold"
                style={{ gridTemplateColumns: '60px 80px 1fr 80px 80px 60px 50px' }}>
                <span>Unit</span>
                <span>Lease End</span>
                <span>In-Place → Renewal</span>
                <span className="text-right">Increase</span>
                <span className="text-right">Delta</span>
                <span className="text-right">%</span>
                <span className="text-center">Flag</span>
              </div>
              {(preview || []).map((o, idx) => {
                const delta = (o.computed_renewal_rent || 0) - (o.in_place_rent || 0);
                const unitInfo = units.find(u => u.unit_number === o.unit_number);
                return (
                  <div
                    key={o.unit_number}
                    className={`px-4 py-2 grid items-center text-xs ${idx > 0 ? 'border-t border-stone-100' : ''} hover:bg-stone-50/50 transition-colors`}
                    style={{ gridTemplateColumns: '60px 80px 1fr 80px 80px 60px 50px' }}
                  >
                    <span className="font-mono font-bold text-stone-700">{o.unit_number}</span>
                    <span className="text-stone-400">{unitInfo?.lease_end ? new Date(unitInfo.lease_end + 'T00:00').toLocaleDateString('en-US', { month: 'short', day: 'numeric' }) : '—'}</span>
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-stone-600">{formatDollar(o.in_place_rent)}</span>
                      <span className="text-stone-300">&rarr;</span>
                      <span className="font-mono font-bold" style={{ color: '#0D9488' }}>{formatDollar(o.computed_renewal_rent)}</span>
                    </div>
                    <span className="font-mono text-right text-stone-600">{formatDollar(o.new_lease_rent)}</span>
                    <span className="font-mono text-right font-bold" style={{ color: delta >= 0 ? '#059669' : '#DC2626' }}>
                      {delta >= 0 ? '+' : ''}{formatDollar(delta)}
                    </span>
                    <span className="font-mono text-right text-stone-600">{pctDisplay(o.effective_increase_pct || 0)}</span>
                    <span className="text-center">
                      {o.was_clamped === 'MIN' && (
                        <span className="text-[9px] font-bold px-1 py-0.5 rounded bg-amber-50 text-amber-600 border border-amber-200">FLOOR</span>
                      )}
                      {o.was_clamped === 'MAX' && (
                        <span className="text-[9px] font-bold px-1 py-0.5 rounded bg-red-50 text-red-600 border border-red-200">CAP</span>
                      )}
                    </span>
                  </div>
                );
              })}
              {(!preview || preview.length === 0) && !previewLoading && (
                <div className="px-4 py-6 text-center text-xs text-stone-400">No expiring units for this floorplan</div>
              )}
            </div>
          </div>

          {/* Save bar */}
          <div className="px-5 py-3 border-t border-stone-100 flex items-center justify-between bg-stone-50/30">
            {existingRule && !dirty ? (
              <div className="flex items-center gap-2 text-xs text-stone-400">
                <svg className="w-3.5 h-3.5 text-emerald-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                </svg>
                <span>Set by {existingRule.created_by} · {new Date(existingRule.created_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}</span>
              </div>
            ) : (
              <span className="text-xs text-stone-400">
                {dirty ? 'Unsaved changes' : 'Configure rules above'}
              </span>
            )}
            <button
              onClick={handleSave}
              disabled={saving || (!dirty && saved)}
              className={`text-xs font-bold px-5 py-2 rounded-lg transition-all shadow-sm ${
                saving ? 'bg-stone-300 text-stone-500 cursor-wait' :
                !dirty && saved ? 'bg-stone-200 text-stone-400 cursor-default' :
                'bg-teal-600 text-white hover:bg-teal-700 hover:shadow-md'
              }`}
            >
              {saving ? (
                <span className="flex items-center gap-2">
                  <div className="w-3 h-3 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  Saving...
                </span>
              ) : saved && !dirty ? 'Saved' : 'Set Rules & Generate Pricing'}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
