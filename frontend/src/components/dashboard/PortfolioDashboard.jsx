import React, { useState, useMemo, useEffect } from 'react';
import { useAuth } from '../../auth/AuthContext';
import { formatDollar, formatPercent, gradeColor, gradeLabel } from '../../utils/format';
import { getPropertySummary, runPortfolioDiagnostic, getDiagnosticRun, getSlides, getLatestDecisions, createPricingDecision, createBatchDecisions, getExpiringLeases, getRenewalRules } from '../../api/client';
import { LineChart, Line, ResponsiveContainer, BarChart, Bar, Cell, XAxis, YAxis, Tooltip, CartesianGrid } from 'recharts';
import RevenueGauge from './RevenueGauge';
import PricingTrendChart from './PricingTrendChart';
import RevenueGapBars from './RevenueGapBars';
import DirectionBadge from './DirectionBadge';
import DecisionButtons from './DecisionButtons';
import DecisionBadge from './DecisionBadge';
import RenewalRuleCard from './RenewalRuleCard';

function occColor(occ) {
  if (occ >= 0.96) return '#059669';
  if (occ >= 0.92) return '#0D9488';
  if (occ >= 0.88) return '#F59E0B';
  if (occ >= 0.82) return '#D97706';
  return '#DC2626';
}

function spreadColor(asking, comps) {
  const pct = (asking - comps) / comps;
  if (pct > 0.05) return '#DC2626';
  if (pct > 0.02) return '#D97706';
  if (pct < -0.02) return '#059669';
  return '#6B7280';
}

function scoreToGrade(score) {
  if (score >= 75) return 'OPTIMIZED';
  if (score >= 60) return 'OPPORTUNITY';
  if (score >= 45) return 'IMBALANCED';
  if (score >= 30) return 'DISTRESSED';
  return 'CRISIS';
}

export default function PortfolioDashboard({ properties, onSelectProperty, onShowPortfolioSlideshow }) {
  const { user, logout } = useAuth();
  const [activeTab, setActiveTab] = useState('overview');
  const [propertyFilter, setPropertyFilter] = useState('All Properties');
  const [unitTypeFilter, setUnitTypeFilter] = useState('All');
  const [summaryData, setSummaryData] = useState({}); // keyed by property id
  const [summaryLoading, setSummaryLoading] = useState(true);
  const [portfolioDiagLoading, setPortfolioDiagLoading] = useState(false);
  const [portfolioDiagStatus, setPortfolioDiagStatus] = useState('');
  const [portfolioError, setPortfolioError] = useState('');
  const [pricingDecisions, setPricingDecisions] = useState({}); // keyed by unit_type_code
  const [renewalDecisions, setRenewalDecisions] = useState({});
  const [decisionLoading, setDecisionLoading] = useState({}); // keyed by `${type}-${code}`

  // Renewal rule workflow state
  const RENEWAL_LOOKAHEAD = 3; // months ahead (configurable)
  const [renewalMonth, setRenewalMonth] = useState(null); // selected target month
  const [renewalMonths, setRenewalMonths] = useState([]); // available months
  const [expiringData, setExpiringData] = useState({}); // keyed by property_id
  const [renewalRules, setRenewalRules] = useState({}); // keyed by unit_type_code
  const [expiringLoading, setExpiringLoading] = useState(false);

  // Load summaries for all properties
  useEffect(() => {
    if (properties.length === 0) return;
    setSummaryLoading(true);
    Promise.all(
      properties.map(p =>
        getPropertySummary(p.id).then(data => ({ id: p.id, data })).catch(() => null)
      )
    ).then(results => {
      const map = {};
      for (const r of results) {
        if (r) map[r.id] = r.data;
      }
      setSummaryData(map);
      setSummaryLoading(false);
    });
  }, [properties]);

  // Build unit type data from summaries
  const unitTypeData = useMemo(() => {
    const data = {};
    for (const prop of properties) {
      const summary = summaryData[prop.id];
      if (!summary) continue;
      for (const [code, ut] of Object.entries(summary.unit_types)) {
        data[code] = ut;
      }
    }
    return data;
  }, [properties, summaryData]);

  // Build trend data from summaries
  const trendData = useMemo(() => {
    const data = {};
    for (const prop of properties) {
      const summary = summaryData[prop.id];
      if (!summary) continue;
      for (const [code, trend] of Object.entries(summary.trends)) {
        data[code] = trend;
      }
    }
    return data;
  }, [properties, summaryData]);

  // Portfolio-level revenue intelligence
  const portfolioRevenue = useMemo(() => {
    let totalEfficiency = 0;
    let totalUnits = 0;
    let totalGap = 0;
    let totalRenewal = 0;
    for (const summary of Object.values(summaryData)) {
      if (summary.portfolio) {
        totalEfficiency += (summary.portfolio.portfolio_revenue_efficiency || 0) * (summary.portfolio.total_units || 0);
        totalUnits += summary.portfolio.total_units || 0;
        totalGap += summary.portfolio.total_revenue_gap || 0;
        totalRenewal += summary.portfolio.total_renewal_opportunity || 0;
      }
    }
    const score = totalUnits > 0 ? Math.round(totalEfficiency / totalUnits) : 0;
    return { score, grade: scoreToGrade(score), totalGap, totalRenewal };
  }, [summaryData]);

  const propertyNames = useMemo(() => {
    return ['All Properties', ...properties.map(p => p.name)];
  }, [properties]);

  // Filter unit types based on selections
  const filtered = useMemo(() => {
    return Object.entries(unitTypeData).filter(([code, d]) => {
      if (propertyFilter !== 'All Properties' && d.property !== propertyFilter) return false;
      if (unitTypeFilter !== 'All' && code !== unitTypeFilter) return false;
      return true;
    });
  }, [propertyFilter, unitTypeFilter, unitTypeData]);

  // Available unit type options based on property filter
  const availableUnitTypes = useMemo(() => {
    const codes = Object.entries(unitTypeData)
      .filter(([, d]) => propertyFilter === 'All Properties' || d.property === propertyFilter)
      .map(([code]) => code);
    return ['All', ...codes];
  }, [propertyFilter, unitTypeData]);

  // Recalculate KPIs from filtered data
  const kpis = useMemo(() => {
    const entries = filtered.map(([, d]) => d);
    return {
      totalUnits: entries.reduce((s, d) => s + d.total, 0),
      totalOccupied: entries.reduce((s, d) => s + d.occupied, 0),
      totalVacant: entries.reduce((s, d) => s + d.vacant, 0),
      dailyBurn: entries.reduce((s, d) => s + d.dailyBurn, 0),
      monthlyCost: entries.reduce((s, d) => s + d.monthlyCost, 0),
      revenueGap: entries.reduce((s, d) => s + (d.revenueGapMonthly || 0), 0),
      renewalOpportunity: entries.reduce((s, d) => s + (d.renewalCaptureAnnual || 0), 0),
    };
  }, [filtered]);

  const blendedOcc = kpis.totalUnits > 0 ? kpis.totalOccupied / kpis.totalUnits : 0;

  // Vacancy cost chart data (restored from original)
  const vacancyCostData = useMemo(() => {
    return filtered
      .map(([code, d]) => ({
        name: code,
        cost: d.monthlyCost,
        color: d.monthlyCost > 8000 ? '#DC2626' : d.monthlyCost > 5000 ? '#D97706' : d.monthlyCost > 2000 ? '#F59E0B' : '#6B7280',
      }))
      .sort((a, b) => b.cost - a.cost);
  }, [filtered]);

  // Filtered unit type data as object for RevenueGapBars
  const filteredUnitTypeData = useMemo(() => {
    return Object.fromEntries(filtered);
  }, [filtered]);

  // Weighted revenue efficiency for filtered view
  const filteredEfficiency = useMemo(() => {
    const entries = filtered.map(([, d]) => d);
    const totalU = entries.reduce((s, d) => s + d.total, 0);
    if (totalU === 0) return { score: 0, grade: 'CRISIS' };
    const weighted = entries.reduce((s, d) => s + (d.revenueEfficiency || 0) * d.total, 0);
    const score = Math.round(weighted / totalU);
    return { score, grade: scoreToGrade(score) };
  }, [filtered]);

  // Pricing tab: all unit types sorted by revenue gap (biggest opportunity first)
  const pricingSorted = useMemo(() => {
    return [...filtered].sort((a, b) => Math.abs(b[1].revenueGapMonthly || 0) - Math.abs(a[1].revenueGapMonthly || 0));
  }, [filtered]);

  // Renewals tab: unit types with upcoming renewals
  const renewalData = useMemo(() => {
    return filtered
      .filter(([, d]) => (d.renewalCount90d || 0) > 0)
      .sort((a, b) => (b[1].renewalCount90d || 0) - (a[1].renewalCount90d || 0));
  }, [filtered]);

  const totalRenewals = useMemo(() => {
    return filtered.reduce((s, [, d]) => s + (d.renewalCount90d || 0), 0);
  }, [filtered]);

  // Reset unit type filter when property changes
  function handlePropertyFilter(val) {
    setPropertyFilter(val);
    setUnitTypeFilter('All');
  }

  async function handleRunPortfolioDiagnostic() {
    setPortfolioDiagLoading(true);
    setPortfolioDiagStatus('Computing metrics...');
    setPortfolioError('');
    try {
      const run = await runPortfolioDiagnostic();
      if (run.status === 'COMPLETED') {
        setPortfolioDiagStatus('Loading presentation...');
        const deck = await getSlides(run.id);
        setPortfolioDiagLoading(false);
        if (onShowPortfolioSlideshow) onShowPortfolioSlideshow(deck);
        return;
      }
      setPortfolioDiagStatus('Running AI analysis...');
      let attempts = 0;
      const poll = setInterval(async () => {
        attempts++;
        try {
          const status = await getDiagnosticRun(run.id);
          if (status.status === 'COMPLETED') {
            clearInterval(poll);
            const deck = await getSlides(status.id);
            setPortfolioDiagLoading(false);
            if (onShowPortfolioSlideshow) onShowPortfolioSlideshow(deck);
          } else if (status.status === 'FAILED' || attempts >= 30) {
            clearInterval(poll);
            setPortfolioDiagLoading(false);
            setPortfolioError(status.error_message || 'Timed out');
          }
        } catch {
          clearInterval(poll);
          setPortfolioDiagLoading(false);
          setPortfolioError('Connection lost');
        }
      }, 2000);
    } catch (err) {
      setPortfolioDiagLoading(false);
      setPortfolioError(err.response?.data?.detail || 'Failed to start');
    }
  }

  // Load latest decisions for all properties
  useEffect(() => {
    if (properties.length === 0) return;
    Promise.all(
      properties.flatMap(p => [
        getLatestDecisions(p.id, 'PRICING').then(decs => ({ type: 'PRICING', decs })).catch(() => null),
        getLatestDecisions(p.id, 'RENEWAL').then(decs => ({ type: 'RENEWAL', decs })).catch(() => null),
      ])
    ).then(results => {
      const pricing = {};
      const renewal = {};
      for (const r of results) {
        if (!r) continue;
        for (const d of r.decs) {
          if (r.type === 'PRICING') pricing[d.unit_type_code] = d;
          else renewal[d.unit_type_code] = d;
        }
      }
      setPricingDecisions(pricing);
      setRenewalDecisions(renewal);
    });
  }, [properties]);

  // Initialize renewal months on mount
  useEffect(() => {
    const now = new Date();
    const months = [];
    for (let i = 1; i <= RENEWAL_LOOKAHEAD; i++) {
      const d = new Date(now.getFullYear(), now.getMonth() + i, 1);
      const key = d.toISOString().slice(0, 10);
      const label = d.toLocaleDateString('en-US', { month: 'long', year: 'numeric' });
      months.push({ key, label, month: d.getMonth() + 1, year: d.getFullYear() });
    }
    setRenewalMonths(months);
    if (months.length > 0 && !renewalMonth) setRenewalMonth(months[0].key);
  // eslint-disable-next-line
  }, []);

  // Load expiring leases and existing rules when month or properties change
  useEffect(() => {
    if (!renewalMonth || properties.length === 0) return;
    setExpiringLoading(true);
    Promise.all(
      properties.flatMap(p => [
        getExpiringLeases(p.id, renewalMonth)
          .then(data => ({ type: 'expiring', propertyId: p.id, data }))
          .catch(() => null),
        getRenewalRules(p.id, renewalMonth)
          .then(data => ({ type: 'rules', data }))
          .catch(() => null),
      ])
    ).then(results => {
      const expiring = {};
      const rules = {};
      for (const r of results) {
        if (!r) continue;
        if (r.type === 'expiring') {
          expiring[r.propertyId] = r.data;
        } else {
          for (const rule of r.data) {
            rules[rule.unit_type_code] = rule;
          }
        }
      }
      setExpiringData(expiring);
      setRenewalRules(rules);
      setExpiringLoading(false);
    });
  }, [renewalMonth, properties]);

  // Aggregate floorplans across properties for selected month
  const renewalFloorplans = useMemo(() => {
    const fps = {};
    for (const [propId, data] of Object.entries(expiringData)) {
      if (!data?.floorplans) continue;
      const prop = properties.find(p => p.id === propId);
      for (const [code, fp] of Object.entries(data.floorplans)) {
        if (propertyFilter !== 'All Properties' && prop?.name !== propertyFilter) continue;
        fps[code] = { ...fp, property: prop?.name, propertyId: propId };
      }
    }
    return fps;
  }, [expiringData, properties, propertyFilter]);

  const totalExpiringUnits = useMemo(() => {
    return Object.values(renewalFloorplans).reduce((s, fp) => s + fp.unit_count, 0);
  }, [renewalFloorplans]);

  const rulesSetCount = useMemo(() => {
    return Object.keys(renewalFloorplans).filter(code => renewalRules[code]).length;
  }, [renewalFloorplans, renewalRules]);

  function handleRenewalRuleSaved(code, result) {
    setRenewalRules(prev => ({ ...prev, [code]: result }));
  }

  async function handleDecision(code, decisionType, decision, recommendedValue, extra = {}) {
    const prop = properties.find(p => {
      const summary = summaryData[p.id];
      if (!summary) return false;
      return Object.keys(summary.unit_types).includes(code);
    });
    if (!prop) return;

    const loadKey = `${decisionType}-${code}`;
    setDecisionLoading(prev => ({ ...prev, [loadKey]: true }));
    try {
      await createPricingDecision({
        property_id: prop.id,
        unit_type_code: code,
        decision_type: decisionType,
        decision,
        recommended_value: recommendedValue,
        ...extra,
      });
      // Reload decisions for this property
      const decs = await getLatestDecisions(prop.id, decisionType);
      const setter = decisionType === 'PRICING' ? setPricingDecisions : setRenewalDecisions;
      setter(prev => {
        const next = { ...prev };
        for (const d of decs) next[d.unit_type_code] = d;
        return next;
      });
    } catch (err) {
      // eslint-disable-next-line no-console
      console.error('Decision failed:', err);
    } finally {
      setDecisionLoading(prev => ({ ...prev, [loadKey]: false }));
    }
  }

  async function handleApproveAllPricing() {
    const undecided = pricingSorted.filter(([code]) => !pricingDecisions[code]);
    if (undecided.length === 0) return;

    const prop = properties.find(p => {
      const summary = summaryData[p.id];
      return summary && Object.keys(summary.unit_types).some(c => undecided.some(([uc]) => uc === c));
    });
    if (!prop) return;

    // Group by property for batch calls
    const byProperty = {};
    for (const [code, d] of undecided) {
      const p = properties.find(pr => {
        const s = summaryData[pr.id];
        return s && Object.keys(s.unit_types).includes(code);
      });
      if (!p) continue;
      if (!byProperty[p.id]) byProperty[p.id] = [];
      byProperty[p.id].push({
        property_id: p.id,
        unit_type_code: code,
        decision_type: 'PRICING',
        decision: 'APPROVE',
        recommended_value: d.recommendedAsking || d.asking,
      });
    }

    for (const [code] of undecided) {
      setDecisionLoading(prev => ({ ...prev, [`PRICING-${code}`]: true }));
    }

    try {
      for (const [propertyId, decisions] of Object.entries(byProperty)) {
        await createBatchDecisions(decisions);
        const decs = await getLatestDecisions(propertyId, 'PRICING');
        setPricingDecisions(prev => {
          const next = { ...prev };
          for (const d of decs) next[d.unit_type_code] = d;
          return next;
        });
      }
    } catch (err) {
      // eslint-disable-next-line no-console
      console.error('Batch approve failed:', err);
    } finally {
      for (const [code] of undecided) {
        setDecisionLoading(prev => ({ ...prev, [`PRICING-${code}`]: false }));
      }
    }
  }

  async function handleApproveAllRenewals() {
    const undecided = renewalData.filter(([code]) => !renewalDecisions[code]);
    if (undecided.length === 0) return;

    const byProperty = {};
    for (const [code, d] of undecided) {
      const p = properties.find(pr => {
        const s = summaryData[pr.id];
        return s && Object.keys(s.unit_types).includes(code);
      });
      if (!p) continue;
      if (!byProperty[p.id]) byProperty[p.id] = [];
      byProperty[p.id].push({
        property_id: p.id,
        unit_type_code: code,
        decision_type: 'RENEWAL',
        decision: 'APPROVE',
        recommended_value: d.inPlace + (d.renewalIncreaseDollars || 0),
      });
    }

    for (const [code] of undecided) {
      setDecisionLoading(prev => ({ ...prev, [`RENEWAL-${code}`]: true }));
    }

    try {
      for (const [propertyId, decisions] of Object.entries(byProperty)) {
        await createBatchDecisions(decisions);
        const decs = await getLatestDecisions(propertyId, 'RENEWAL');
        setRenewalDecisions(prev => {
          const next = { ...prev };
          for (const d of decs) next[d.unit_type_code] = d;
          return next;
        });
      }
    } catch (err) {
      // eslint-disable-next-line no-console
      console.error('Batch approve renewals failed:', err);
    } finally {
      for (const [code] of undecided) {
        setDecisionLoading(prev => ({ ...prev, [`RENEWAL-${code}`]: false }));
      }
    }
  }

  // Compute review status for tabs
  const pricingReviewCount = pricingSorted.filter(([code]) => pricingDecisions[code]).length;
  const renewalReviewCount = renewalData.filter(([code]) => renewalDecisions[code]).length;

  const lastPricingReview = useMemo(() => {
    const dates = Object.values(pricingDecisions).map(d => d.decided_at).filter(Boolean);
    if (dates.length === 0) return null;
    return dates.sort().reverse()[0];
  }, [pricingDecisions]);

  const lastRenewalReview = useMemo(() => {
    const dates = Object.values(renewalDecisions).map(d => d.decided_at).filter(Boolean);
    if (dates.length === 0) return null;
    return dates.sort().reverse()[0];
  }, [renewalDecisions]);

  if (summaryLoading) {
    return (
      <div className="min-h-screen bg-stone-50 flex items-center justify-center">
        <div className="flex flex-col items-center gap-3">
          <div className="w-8 h-8 border-2 border-stone-300 border-t-stone-700 rounded-full animate-spin" />
          <span className="text-sm text-stone-400">Loading portfolio data</span>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-stone-50">
      <header className="bg-white border-b border-stone-200">
        <div className="max-w-7xl mx-auto px-6 py-3 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-7 h-7 rounded bg-positive flex items-center justify-center">
              <span className="text-white font-mono font-bold text-xs">RR</span>
            </div>
            <span className="font-display text-base text-stone-900">RoboRev</span>
          </div>
          <div className="flex items-center gap-5">
            <span className="text-xs text-stone-400">{user?.email}</span>
            <button onClick={logout} className="text-xs text-stone-400 hover:text-stone-600 transition-colors">Sign out</button>
          </div>
        </div>
        <div className="max-w-7xl mx-auto px-6 flex items-center justify-between">
          <div className="flex gap-0">
            {[
              { key: 'overview', label: 'Overview' },
              { key: 'properties', label: 'Properties' },
              { key: 'pricing', label: 'Pricing' },
              { key: 'renewals', label: 'Renewals' },
            ].map((tab) => (
              <button
                key={tab.key}
                onClick={() => setActiveTab(tab.key)}
                className={`px-4 py-2.5 text-sm font-medium border-b-2 transition-colors ${
                  activeTab === tab.key
                    ? 'border-positive text-stone-900'
                    : 'border-transparent text-stone-400 hover:text-stone-600'
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>
          <button
            onClick={handleRunPortfolioDiagnostic}
            disabled={portfolioDiagLoading}
            className="px-4 py-2 mb-1 bg-positive text-white rounded-lg hover:bg-positive/90 text-sm font-semibold transition-all flex items-center gap-2 disabled:opacity-30"
          >
            {portfolioDiagLoading ? (
              <>
                <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                {portfolioDiagStatus}
              </>
            ) : (
              <>
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M9 17V7m0 10a2 2 0 01-2 2H5a2 2 0 01-2-2V7a2 2 0 012-2h2a2 2 0 012 2m0 10a2 2 0 002 2h2a2 2 0 002-2M9 7a2 2 0 012-2h2a2 2 0 012 2m0 10V7" />
                </svg>
                Run Portfolio Diagnosis
                <span className="text-xs opacity-75">~20s</span>
              </>
            )}
          </button>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-6 py-6">
        {/* Filters — shared across all tabs */}
        <div className="flex items-center justify-end gap-2 mb-6">
          <select
            value={propertyFilter}
            onChange={(e) => handlePropertyFilter(e.target.value)}
            className="text-sm bg-white border border-stone-200 rounded-lg px-3 py-2 text-stone-700 focus:outline-none focus:ring-2 focus:ring-positive/40 font-medium"
            aria-label="Filter by property"
          >
            {propertyNames.map((name) => (
              <option key={name} value={name}>{name}</option>
            ))}
          </select>
          <select
            value={unitTypeFilter}
            onChange={(e) => setUnitTypeFilter(e.target.value)}
            className="text-sm bg-white border border-stone-200 rounded-lg px-3 py-2 text-stone-700 focus:outline-none focus:ring-2 focus:ring-positive/40 font-medium"
            aria-label="Filter by unit type"
          >
            {availableUnitTypes.map((code) => (
              <option key={code} value={code}>{code === 'All' ? 'All Unit Types' : code}</option>
            ))}
          </select>
        </div>

        {portfolioError && (
          <div className="bg-crisis/5 border border-crisis/20 text-crisis p-3 rounded-lg mb-4 text-sm flex justify-between">
            <span>{portfolioError}</span>
            <button onClick={() => setPortfolioError('')} className="text-crisis/60 hover:text-crisis">&times;</button>
          </div>
        )}

        {/* ========== OVERVIEW TAB ========== */}
        {activeTab === 'overview' && <>
          {/* Hero: Gauge + KPIs */}
          <div className="bg-white rounded-xl border border-stone-200 p-6 shadow-card mb-4">
            <div className="flex items-stretch gap-6">
              <div className="flex-shrink-0 flex flex-col items-center justify-center" style={{ width: '40%' }}>
                <p className="text-[10px] text-stone-400 font-semibold uppercase tracking-wider mb-2">Revenue Efficiency</p>
                <RevenueGauge score={filteredEfficiency.score} grade={filteredEfficiency.grade} size={200} />
              </div>
              <div className="flex-1">
                <div className="grid grid-cols-3 gap-3 h-full">
                  <KPICard label="Revenue Gap" value={formatDollar(Math.abs(kpis.revenueGap))} subtitle="/mo" color="#DC2626" />
                  <KPICard label="Blended Occupancy" value={`${(blendedOcc * 100).toFixed(1)}%`} color={occColor(blendedOcc)} />
                  <KPICard label="Renewals (90d)" value={`${totalRenewals}`} color={totalRenewals > 0 ? '#0D9488' : '#6B7280'} />
                  <KPICard label="Total Vacant" value={`${kpis.totalVacant}`} subtitle={`/ ${kpis.totalUnits}`} color={kpis.totalVacant >= 10 ? '#D97706' : '#6B7280'} />
                  <KPICard label="Vacancy Cost" value={formatDollar(kpis.monthlyCost)} subtitle="/mo" color="#D97706" />
                  <KPICard label="Renewal Opportunity" value={formatDollar(kpis.renewalOpportunity)} subtitle="/yr" color="#059669" />
                </div>
              </div>
            </div>
          </div>

          {/* Row 2: Asking Rent Trends + Vacancy Cost */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-4">
            <div className="bg-white rounded-xl border border-stone-200 p-5 shadow-card">
              <h3 className="text-xs font-semibold text-stone-500 uppercase tracking-wider mb-3">Asking Rent Trends</h3>
              {filtered.length > 0 ? (
                <ResponsiveContainer width="100%" height={180}>
                  <LineChart margin={{ top: 5, right: 10, left: 5, bottom: 5 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#e7e5e4" />
                    <XAxis dataKey="m" type="category" allowDuplicatedCategory={false} tick={{ fontSize: 10, fill: '#78716c' }} />
                    <YAxis tickFormatter={formatDollar} tick={{ fontSize: 10, fill: '#78716c' }} domain={['dataMin - 30', 'dataMax + 30']} />
                    <Tooltip formatter={(v) => formatDollar(v)} />
                    {filtered.map(([code], i) => {
                      const colors = ['#7C3AED', '#2563EB', '#059669', '#EA580C'];
                      return trendData[code] ? (
                        <Line key={code} data={trendData[code]} type="monotone" dataKey="asking" name={code}
                          stroke={colors[i % colors.length]} strokeWidth={2} dot={{ r: 3 }} />
                      ) : null;
                    })}
                  </LineChart>
                </ResponsiveContainer>
              ) : (
                <div className="h-[180px] flex items-center justify-center text-xs text-stone-400">No data</div>
              )}
              <div className="flex items-center justify-center gap-4 mt-1">
                {filtered.map(([code], i) => {
                  const colors = ['#7C3AED', '#2563EB', '#059669', '#EA580C'];
                  return (
                    <span key={code} className="flex items-center gap-1.5 text-[10px] text-stone-500">
                      <span className="w-3 h-0.5 inline-block rounded" style={{ backgroundColor: colors[i % colors.length] }} /> {code}
                    </span>
                  );
                })}
              </div>
            </div>

            <div className="bg-white rounded-xl border border-stone-200 p-5 shadow-card">
              <h3 className="text-xs font-semibold text-stone-500 uppercase tracking-wider mb-3">Vacancy Cost by Unit Type</h3>
              {vacancyCostData.length > 0 ? (
                <ResponsiveContainer width="100%" height={180}>
                  <BarChart data={vacancyCostData} layout="vertical" margin={{ left: 5, right: 10 }}>
                    <XAxis type="number" tickFormatter={formatDollar} tick={{ fontSize: 10, fill: '#78716c' }} />
                    <YAxis type="category" dataKey="name" tick={{ fontSize: 11, fontWeight: 600, fill: '#57534e' }} width={30} />
                    <Tooltip formatter={(v) => formatDollar(v)} />
                    <Bar dataKey="cost" radius={[0, 4, 4, 0]} barSize={22}>
                      {vacancyCostData.map((d, i) => <Cell key={i} fill={d.color} />)}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              ) : (
                <div className="h-[180px] flex items-center justify-center text-xs text-stone-400">No data</div>
              )}
            </div>
          </div>

          {/* Row 3: Revenue Gap + Occupancy Trends */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-4">
            <div className="bg-white rounded-xl border border-stone-200 p-5 shadow-card">
              <h3 className="text-xs font-semibold text-stone-500 uppercase tracking-wider mb-3">Revenue Gap by Unit Type</h3>
              <RevenueGapBars unitTypeData={filteredUnitTypeData} height={Math.max(140, filtered.length * 40)} />
            </div>

            <div className="bg-white rounded-xl border border-stone-200 p-5 shadow-card">
              <h3 className="text-xs font-semibold text-stone-500 uppercase tracking-wider mb-3">Occupancy Trends (4 months)</h3>
              <div className="grid grid-cols-2 gap-4">
                {filtered.map(([code, d]) => (
                  <div key={code}>
                    <div className="flex items-center justify-between mb-1">
                      <span className="font-mono text-xs font-bold text-stone-700">{code}</span>
                      <span className="font-mono text-xs font-semibold" style={{ color: occColor(d.occ) }}>{(d.occ * 100).toFixed(0)}%</span>
                    </div>
                    {trendData[code] ? (
                      <ResponsiveContainer width="100%" height={56}>
                        <LineChart data={trendData[code]}>
                          <Line type="monotone" dataKey="occ" stroke={occColor(d.occ)} strokeWidth={2.5} dot={{ r: 2.5, fill: occColor(d.occ) }} />
                          <XAxis dataKey="m" tick={{ fontSize: 8, fill: '#a8a29e' }} axisLine={false} tickLine={false} />
                        </LineChart>
                      </ResponsiveContainer>
                    ) : (
                      <div className="h-[56px] flex items-center justify-center text-[10px] text-stone-300">No data</div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Row 4: Action Items — unit types needing attention, sorted by urgency */}
          <div className="bg-white rounded-xl border border-stone-200 p-5 shadow-card mb-4">
            <h3 className="text-xs font-semibold text-stone-500 uppercase tracking-wider mb-3">Action Items</h3>
            <div className="space-y-2">
              {pricingSorted.map(([code, d]) => {
                const dirColor = d.priceDirection === 'DECREASE' ? '#DC2626' : d.priceDirection === 'INCREASE' ? '#059669' : '#a8a29e';
                return (
                  <div key={code} className="flex items-center gap-4 py-2.5 px-4 bg-stone-50 rounded-lg" style={{ borderLeftWidth: '3px', borderLeftColor: dirColor }}>
                    <span className="font-mono text-sm font-bold text-stone-800 w-8">{code}</span>
                    <span className="text-xs text-stone-400 w-20 truncate">{d.property}</span>
                    <DirectionBadge direction={d.priceDirection} />
                    <div className="flex items-center gap-1">
                      <span className="text-xs text-stone-500">Asking</span>
                      <span className="font-mono text-xs font-semibold text-stone-700">{formatDollar(d.asking)}</span>
                      <span className="text-stone-300 mx-1">&rarr;</span>
                      <span className="font-mono text-xs font-bold" style={{ color: dirColor }}>{formatDollar(d.recommendedAsking)}</span>
                    </div>
                    <div className="flex items-center gap-1 ml-auto">
                      <span className="text-xs text-stone-400">Gap</span>
                      <span className="font-mono text-xs font-bold text-crisis">{formatDollar(Math.abs(d.revenueGapMonthly || 0))}/mo</span>
                    </div>
                    <span className="text-[9px] font-bold px-1.5 py-0.5 rounded bg-stone-200 text-stone-600">{d.dominantLever || '—'}</span>
                    <span className="font-mono text-xs" style={{ color: occColor(d.occ) }}>{(d.occ * 100).toFixed(0)}%</span>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Row 5: Property Comparison */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {properties
              .filter((prop) => propertyFilter === 'All Properties' || prop.name === propertyFilter)
              .map((prop) => {
                const propTypes = Object.entries(unitTypeData).filter(([, d]) => d.property === prop.name);
                const propOcc = prop.total_units > 0 ? propTypes.reduce((s, [, d]) => s + d.occupied, 0) / prop.total_units : 0;
                const propGap = propTypes.reduce((s, [, d]) => s + (d.revenueGapMonthly || 0), 0);
                const propBurn = propTypes.reduce((s, [, d]) => s + d.dailyBurn, 0);
                const propTotalUnits = propTypes.reduce((s, [, d]) => s + d.total, 0);
                const propEffScore = propTotalUnits > 0
                  ? Math.round(propTypes.reduce((s, [, d]) => s + (d.revenueEfficiency || 0) * d.total, 0) / propTotalUnits) : 0;
                const propGrade = scoreToGrade(propEffScore);
                const accentColor = gradeColor(propGrade);
                return (
                  <div key={prop.id} onClick={() => onSelectProperty(prop)}
                    className="bg-white rounded-xl border border-stone-200 p-5 shadow-card hover:shadow-card-hover cursor-pointer transition-all"
                    style={{ borderLeftWidth: '4px', borderLeftColor: accentColor }}
                  >
                    <div className="flex items-center justify-between mb-3">
                      <div className="flex items-center gap-2">
                        <h3 className="font-display text-base text-stone-900">{prop.name}</h3>
                        <span className="font-mono text-sm font-bold" style={{ color: accentColor }}>{propEffScore}</span>
                        <span className="text-[9px] font-bold px-1.5 py-0.5 rounded" style={{ backgroundColor: accentColor + '15', color: accentColor }}>
                          {gradeLabel(propGrade)}
                        </span>
                      </div>
                      <svg className="w-4 h-4 text-stone-300" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
                      </svg>
                    </div>
                    <div className="grid grid-cols-4 gap-3 text-xs">
                      <Metric label="Occupancy" value={formatPercent(propOcc)} color={occColor(propOcc)} />
                      <Metric label="Rev Gap" value={`${formatDollar(Math.abs(propGap))}/mo`} color="#DC2626" />
                      <Metric label="Daily Burn" value={formatDollar(propBurn)} color={propBurn > 400 ? '#DC2626' : '#6B7280'} />
                      <Metric label="Unit Types" value={propTypes.length} color="#6B7280" />
                    </div>
                  </div>
                );
              })}
          </div>
        </>}

        {/* ========== PROPERTIES TAB ========== */}
        {activeTab === 'properties' && <>
          <div className="grid gap-4">
            {properties
              .filter((prop) => propertyFilter === 'All Properties' || prop.name === propertyFilter)
              .map((prop) => {
                const propTypes = Object.entries(unitTypeData).filter(([, d]) => d.property === prop.name);
                const propVacant = prop.total_vacant ?? propTypes.reduce((s, [, d]) => s + d.vacant, 0);
                const propOcc = prop.blended_occ ?? (prop.total_units > 0 ? propTypes.reduce((s, [, d]) => s + d.occupied, 0) / prop.total_units : 0);
                const propGap = propTypes.reduce((s, [, d]) => s + (d.revenueGapMonthly || 0), 0);
                const propRenewals = propTypes.reduce((s, [, d]) => s + (d.renewalCount90d || 0), 0);
                const directions = propTypes.map(([, d]) => d.priceDirection).filter(Boolean);
                const incCount = directions.filter(d => d === 'INCREASE').length;
                const decCount = directions.filter(d => d === 'DECREASE').length;
                const netDirection = incCount > decCount ? 'INCREASE' : decCount > incCount ? 'DECREASE' : 'HOLD';
                const propTotalUnits = propTypes.reduce((s, [, d]) => s + d.total, 0);
                const propEffScore = propTotalUnits > 0
                  ? Math.round(propTypes.reduce((s, [, d]) => s + (d.revenueEfficiency || 0) * d.total, 0) / propTotalUnits) : 0;
                const propGrade = scoreToGrade(propEffScore);
                const accentColor = gradeColor(propGrade);

                return (
                  <div
                    key={prop.id}
                    onClick={() => onSelectProperty(prop)}
                    className="bg-white rounded-xl border border-stone-200 p-5 shadow-card hover:shadow-card-hover hover:border-stone-300 transition-all cursor-pointer"
                    style={{ borderLeftWidth: '4px', borderLeftColor: accentColor }}
                  >
                    <div className="flex items-center justify-between mb-3">
                      <div>
                        <div className="flex items-center gap-3">
                          <h3 className="font-display text-lg text-stone-900">{prop.name}</h3>
                          <span className="font-mono text-sm font-bold" style={{ color: accentColor }}>{propEffScore}</span>
                          <span className="text-[10px] font-bold px-2 py-0.5 rounded" style={{ backgroundColor: accentColor + '15', color: accentColor }}>
                            {gradeLabel(propGrade)}
                          </span>
                        </div>
                        <div className="flex items-center gap-4 mt-1 text-xs text-stone-400">
                          <span>{prop.submarket}</span>
                          <span className="text-stone-300">|</span>
                          <span className="font-mono">{prop.total_units} units</span>
                          <span className="text-stone-300">|</span>
                          <span>Class {prop.property_class}</span>
                        </div>
                      </div>
                      <svg className="w-5 h-5 text-stone-300" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
                      </svg>
                    </div>
                    <div className="grid grid-cols-5 gap-3 pt-3 border-t border-stone-100">
                      <Metric label="Occupancy" value={formatPercent(propOcc)} color={occColor(propOcc)} />
                      <Metric label="Vacant" value={propVacant} color={propVacant >= 8 ? '#D97706' : '#6B7280'} />
                      <Metric label="Rev Gap" value={`${formatDollar(Math.abs(propGap))}/mo`} color="#DC2626" />
                      <div>
                        <span className="text-[10px] text-stone-400 uppercase tracking-wider">Renewals 90d</span>
                        <span className="font-mono text-sm font-bold block" style={{ color: propRenewals > 0 ? '#0D9488' : '#6B7280' }}>{propRenewals}</span>
                      </div>
                      <div>
                        <span className="text-[10px] text-stone-400 uppercase tracking-wider">Direction</span>
                        <DirectionBadge direction={netDirection} className="mt-0.5" />
                      </div>
                    </div>

                    {/* Inline unit type breakdown */}
                    <div className="mt-3 pt-3 border-t border-stone-100">
                      <div className="grid gap-2">
                        {propTypes.map(([utCode, ut]) => (
                          <div key={utCode} className="flex items-center gap-3 py-1.5 px-3 bg-stone-50 rounded-lg text-xs">
                            <span className="font-mono font-bold text-stone-700 w-8">{utCode}</span>
                            <span className="font-mono" style={{ color: occColor(ut.occ) }}>{(ut.occ * 100).toFixed(0)}%</span>
                            <span className="text-stone-400">{ut.vacant}v / {ut.total}</span>
                            <span className="font-mono text-stone-600">{formatDollar(ut.asking)}</span>
                            <DirectionBadge direction={ut.priceDirection} />
                            <span className="font-mono text-crisis ml-auto">{formatDollar(Math.abs(ut.revenueGapMonthly || 0))}/mo</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                );
              })}
          </div>
          <p className="text-center text-xs text-stone-400 mt-4">Click a property to see pricing details and run an AI diagnosis</p>
        </>}

        {/* ========== PRICING TAB ========== */}
        {activeTab === 'pricing' && <>
          {/* Summary bar */}
          <div className="bg-white rounded-xl border border-stone-200 p-4 shadow-card mb-4 flex items-center justify-between">
            <div>
              <h3 className="font-display text-lg text-stone-900">Pricing Recommendations</h3>
              <p className="text-xs text-stone-400 mt-0.5">{pricingSorted.length} unit types — sorted by revenue opportunity</p>
              {lastPricingReview && (
                <p className="text-xs mt-1" style={{ color: (Date.now() - new Date(lastPricingReview).getTime()) < 7 * 86400000 ? '#059669' : '#D97706' }}>
                  Last reviewed: {new Date(lastPricingReview).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
                  {' '}({Math.floor((Date.now() - new Date(lastPricingReview).getTime()) / 86400000)}d ago)
                </p>
              )}
            </div>
            <div className="flex items-center gap-6">
              <div className="text-right">
                <p className="text-[10px] text-stone-400 uppercase tracking-wider">Reviewed</p>
                <span className="font-mono text-lg font-bold" style={{ color: pricingReviewCount === pricingSorted.length && pricingSorted.length > 0 ? '#059669' : '#6B7280' }}>
                  {pricingReviewCount} <span className="text-xs text-stone-400 font-normal">of {pricingSorted.length}</span>
                </span>
              </div>
              <div className="text-right">
                <p className="text-[10px] text-stone-400 uppercase tracking-wider">Total Gap</p>
                <span className="font-mono text-lg font-bold text-crisis">{formatDollar(Math.abs(kpis.revenueGap))}<span className="text-xs text-stone-400 font-normal">/mo</span></span>
              </div>
              <div className="text-right">
                <p className="text-[10px] text-stone-400 uppercase tracking-wider">Avg Efficiency</p>
                <span className="font-mono text-lg font-bold" style={{ color: gradeColor(filteredEfficiency.grade) }}>{filteredEfficiency.score}</span>
              </div>
              {pricingReviewCount < pricingSorted.length && pricingSorted.length > 0 && (
                <button
                  onClick={handleApproveAllPricing}
                  className="text-xs font-bold px-4 py-2 rounded-lg bg-emerald-600 text-white hover:bg-emerald-700 transition-colors shadow-sm"
                >
                  Approve All Remaining
                </button>
              )}
            </div>
          </div>

          {/* Table header */}
          <div className="bg-stone-100 rounded-t-lg px-5 py-2.5 grid gap-3 items-center text-[10px] text-stone-500 uppercase tracking-wider font-semibold" style={{ gridTemplateColumns: '80px 90px 1fr 90px 90px 80px 90px 70px 160px' }}>
            <span>Type</span>
            <span>Property</span>
            <span>Asking vs Comps</span>
            <span>Current</span>
            <span>Recommended</span>
            <span>Direction</span>
            <span>Rev Gap</span>
            <span>Lever</span>
            <span>Action</span>
          </div>

          {/* Pricing rows — undecided first, decided last */}
          <div className="border border-stone-200 rounded-b-lg overflow-hidden mb-6">
            {[...pricingSorted]
              .sort((a, b) => {
                const aDecided = pricingDecisions[a[0]] ? 1 : 0;
                const bDecided = pricingDecisions[b[0]] ? 1 : 0;
                if (aDecided !== bDecided) return aDecided - bDecided;
                return Math.abs(b[1].revenueGapMonthly || 0) - Math.abs(a[1].revenueGapMonthly || 0);
              })
              .map(([code, d], idx) => {
              const dirColor = d.priceDirection === 'DECREASE' ? '#DC2626' : d.priceDirection === 'INCREASE' ? '#059669' : '#a8a29e';
              const spread = d.asking - d.comps;
              const existingDecision = pricingDecisions[code];
              const isDecided = !!existingDecision;
              return (
                <div
                  key={code}
                  className={`px-5 py-3 grid gap-3 items-center transition-colors hover:bg-stone-50 ${idx > 0 ? 'border-t border-stone-100' : ''}`}
                  style={{
                    gridTemplateColumns: '80px 90px 1fr 90px 90px 80px 90px 70px 160px',
                    borderLeftWidth: '3px',
                    borderLeftColor: dirColor,
                    opacity: isDecided ? 0.6 : 1,
                  }}
                >
                  <span className="font-mono text-sm font-bold text-stone-800">{code}</span>
                  <span className="text-xs text-stone-500 truncate">{d.property}</span>

                  {/* Inline sparkline */}
                  <div className="flex items-center gap-2">
                    {trendData[code] ? (
                      <ResponsiveContainer width="100%" height={32}>
                        <LineChart data={trendData[code]} margin={{ top: 2, right: 2, bottom: 2, left: 2 }}>
                          <Line type="monotone" dataKey="asking" stroke="#7C3AED" strokeWidth={1.5} dot={false} />
                          <Line type="monotone" dataKey="comps" stroke="#EA580C" strokeWidth={1.5} dot={false} strokeDasharray="4 3" />
                        </LineChart>
                      </ResponsiveContainer>
                    ) : <div className="h-[32px]" />}
                    <span className="font-mono text-[10px] font-semibold flex-shrink-0" style={{ color: spread > 0 ? '#D97706' : '#059669' }}>
                      {spread >= 0 ? '+' : ''}{formatDollar(spread)}
                    </span>
                  </div>

                  <span className="font-mono text-sm text-stone-700">{formatDollar(d.asking)}</span>
                  <span className="font-mono text-sm font-bold" style={{ color: dirColor }}>{formatDollar(d.recommendedAsking)}</span>
                  <DirectionBadge direction={d.priceDirection} />
                  <span className="font-mono text-sm font-bold text-crisis">{formatDollar(Math.abs(d.revenueGapMonthly || 0))}</span>
                  <span className="text-[9px] font-bold px-1.5 py-0.5 rounded bg-stone-100 text-stone-600 text-center">{d.dominantLever || '—'}</span>
                  <div>
                    {isDecided ? (
                      <DecisionBadge
                        decision={existingDecision.decision}
                        decidedAt={existingDecision.decided_at}
                        approvedValue={existingDecision.approved_value}
                        decidedByName={existingDecision.decided_by_name}
                      />
                    ) : (
                      <DecisionButtons
                        recommendedValue={d.recommendedAsking || d.asking}
                        loading={!!decisionLoading[`PRICING-${code}`]}
                        onApprove={() => handleDecision(code, 'PRICING', 'APPROVE', d.recommendedAsking || d.asking)}
                        onHold={(reason) => handleDecision(code, 'PRICING', 'HOLD', d.recommendedAsking || d.asking, { reason })}
                        onModify={(value) => handleDecision(code, 'PRICING', 'MODIFY', d.recommendedAsking || d.asking, { approved_value: value })}
                      />
                    )}
                  </div>
                </div>
              );
            })}
          </div>

          {/* Asking vs Comps trend charts */}
          <h3 className="text-xs font-semibold text-stone-500 uppercase tracking-wider mb-3">Asking vs Comps Trends</h3>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-6">
            {filtered.map(([code, d]) => {
              const spread = d.asking - d.comps;
              return (
                <div key={code} className="bg-white rounded-xl border border-stone-200 p-5 shadow-card">
                  <div className="flex items-center justify-between mb-3">
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-sm font-bold text-stone-700">{code}</span>
                      <span className="text-xs text-stone-400">{d.property}</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <DirectionBadge direction={d.priceDirection} />
                      <span className="font-mono text-[10px] font-semibold" style={{ color: spread > 0 ? '#D97706' : '#059669' }}>
                        {spread >= 0 ? '+' : ''}{formatDollar(spread)} vs comps
                      </span>
                    </div>
                  </div>
                  {trendData[code] ? (
                    <ResponsiveContainer width="100%" height={120}>
                      <LineChart data={trendData[code]} margin={{ top: 5, right: 5, left: 5, bottom: 5 }}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#e7e5e4" />
                        <XAxis dataKey="m" tick={{ fontSize: 10, fill: '#78716c' }} />
                        <YAxis tickFormatter={formatDollar} tick={{ fontSize: 10, fill: '#78716c' }} domain={['dataMin - 20', 'dataMax + 20']} />
                        <Tooltip formatter={(v) => formatDollar(v)} />
                        <Line type="monotone" dataKey="asking" stroke="#7C3AED" strokeWidth={2.5} dot={{ r: 3, fill: '#7C3AED' }} name="Asking" />
                        <Line type="monotone" dataKey="comps" stroke="#EA580C" strokeWidth={2} dot={{ r: 2.5, fill: '#EA580C' }} strokeDasharray="6 4" name="Comps" />
                      </LineChart>
                    </ResponsiveContainer>
                  ) : (
                    <div className="h-[120px] flex items-center justify-center text-xs text-stone-400">No trend data</div>
                  )}
                </div>
              );
            })}
          </div>

          {/* Revenue Gap Decomposition */}
          <div className="bg-white rounded-xl border border-stone-200 p-5 shadow-card">
            <h3 className="text-xs font-semibold text-stone-500 uppercase tracking-wider mb-4">Revenue Gap Decomposition</h3>
            <RevenueGapBars unitTypeData={filteredUnitTypeData} height={Math.max(120, filtered.length * 40)} />
          </div>
        </>}

        {/* ========== RENEWALS TAB ========== */}
        {activeTab === 'renewals' && <>
          {/* Header with month selector */}
          <div className="bg-white rounded-xl border border-stone-200 shadow-card mb-4 overflow-hidden">
            <div className="px-5 py-4 flex items-center justify-between">
              <div>
                <h3 className="font-display text-lg text-stone-900">Renewal Pricing Rules</h3>
                <p className="text-xs text-stone-400 mt-0.5">Set rules per floorplan — generates unit-level renewal pricing</p>
              </div>
              <div className="flex items-center gap-6">
                <div className="text-right">
                  <p className="text-[10px] text-stone-400 uppercase tracking-wider">Rules Set</p>
                  <span className="font-mono text-lg font-bold" style={{ color: rulesSetCount === Object.keys(renewalFloorplans).length && Object.keys(renewalFloorplans).length > 0 ? '#059669' : '#6B7280' }}>
                    {rulesSetCount} <span className="text-xs text-stone-400 font-normal">of {Object.keys(renewalFloorplans).length}</span>
                  </span>
                </div>
                <div className="text-right">
                  <p className="text-[10px] text-stone-400 uppercase tracking-wider">Expiring Units</p>
                  <span className="font-mono text-lg font-bold" style={{ color: '#0D9488' }}>{totalExpiringUnits}</span>
                </div>
              </div>
            </div>

            {/* Month tabs */}
            <div className="border-t border-stone-100 px-5 flex items-center gap-0">
              {renewalMonths.map(m => {
                const isActive = renewalMonth === m.key;
                const hasRules = Object.entries(expiringData).some(([pid, d]) =>
                  d?.floorplans && Object.keys(d.floorplans).length > 0
                );
                return (
                  <button
                    key={m.key}
                    onClick={() => setRenewalMonth(m.key)}
                    className={`relative px-5 py-3 text-xs font-semibold transition-colors ${
                      isActive
                        ? 'text-teal-700'
                        : 'text-stone-400 hover:text-stone-600'
                    }`}
                  >
                    {m.label}
                    {isActive && (
                      <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-teal-600 rounded-t" />
                    )}
                  </button>
                );
              })}
            </div>
          </div>

          {/* Loading state */}
          {expiringLoading && (
            <div className="flex items-center justify-center py-12">
              <div className="flex flex-col items-center gap-3">
                <div className="w-6 h-6 border-2 border-stone-300 border-t-teal-600 rounded-full animate-spin" />
                <span className="text-xs text-stone-400">Loading expiring leases...</span>
              </div>
            </div>
          )}

          {/* No expiring leases */}
          {!expiringLoading && Object.keys(renewalFloorplans).length === 0 && (
            <div className="bg-white rounded-xl border border-stone-200 p-12 text-center shadow-card">
              <div className="w-12 h-12 rounded-full bg-stone-100 flex items-center justify-center mx-auto mb-3">
                <svg className="w-6 h-6 text-stone-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
                </svg>
              </div>
              <p className="text-stone-500 text-sm font-medium">No leases expiring this month</p>
              <p className="text-stone-400 text-xs mt-1">Try selecting a different month above</p>
            </div>
          )}

          {/* Floorplan rule cards */}
          {!expiringLoading && Object.keys(renewalFloorplans).length > 0 && (
            <div className="space-y-4">
              {Object.entries(renewalFloorplans)
                .sort((a, b) => {
                  // Unconfigured first, then by unit count
                  const aSet = renewalRules[a[0]] ? 1 : 0;
                  const bSet = renewalRules[b[0]] ? 1 : 0;
                  if (aSet !== bSet) return aSet - bSet;
                  return b[1].unit_count - a[1].unit_count;
                })
                .map(([code, fp]) => (
                  <RenewalRuleCard
                    key={`${renewalMonth}-${code}`}
                    propertyId={fp.propertyId}
                    unitTypeCode={code}
                    targetMonth={renewalMonth}
                    floorplanData={fp}
                    existingRule={renewalRules[code] || null}
                    onRuleSaved={handleRenewalRuleSaved}
                  />
                ))
              }
            </div>
          )}

          {/* Loss-to-Lease context */}
          {!expiringLoading && filtered.length > 0 && (
            <div className="bg-white rounded-xl border border-stone-200 p-5 shadow-card mt-6">
              <h3 className="text-xs font-semibold text-stone-500 uppercase tracking-wider mb-3">Loss-to-Lease Context</h3>
              <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
                {filtered.map(([code, d]) => {
                  const ltlColor = d.ltlDollars > 0 ? '#059669' : d.ltlDollars < 0 ? '#DC2626' : '#6B7280';
                  return (
                    <div key={code} className="p-3 bg-stone-50 rounded-lg">
                      <div className="flex items-center justify-between mb-1">
                        <span className="font-mono text-xs font-bold text-stone-700">{code}</span>
                        <span className="font-mono text-xs font-bold" style={{ color: ltlColor }}>
                          {d.ltlDollars >= 0 ? '+' : ''}{formatDollar(d.ltlDollars)}
                        </span>
                      </div>
                      <div className="flex items-center justify-between text-[10px]">
                        <span className="text-stone-400">In-Place: {formatDollar(d.inPlace)}</span>
                        <span className="text-stone-400">Asking: {formatDollar(d.asking)}</span>
                      </div>
                      <div className="mt-1.5 h-1.5 bg-stone-200 rounded-full overflow-hidden">
                        <div
                          className="h-full rounded-full"
                          style={{
                            width: `${Math.min(100, Math.max(5, (d.inPlace / d.asking) * 100))}%`,
                            backgroundColor: ltlColor,
                          }}
                        />
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </>}
      </main>
    </div>
  );
}

function KPICard({ label, value, color, subtitle }) {
  return (
    <div className="bg-stone-50 rounded-lg p-3 flex flex-col justify-between">
      <p className="text-[10px] text-stone-400 font-semibold uppercase tracking-wider">{label}</p>
      <div className="flex items-baseline gap-1 mt-1">
        <span className="font-mono text-lg font-bold" style={{ color: color || '#1c1917' }}>{value}</span>
        {subtitle && <span className="text-[10px] text-stone-400">{subtitle}</span>}
      </div>
    </div>
  );
}

function Metric({ label, value, color }) {
  return (
    <div>
      <span className="text-[10px] text-stone-400 uppercase tracking-wider">{label}</span>
      <span className="font-mono text-sm font-bold block" style={{ color }}>{value}</span>
    </div>
  );
}
