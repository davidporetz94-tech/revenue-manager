import React, { useState, useMemo, useEffect } from 'react';
import { useAuth } from '../../auth/AuthContext';
import { formatDollar, formatPercent } from '../../utils/format';
import { getPropertySummary, runPortfolioDiagnostic, getDiagnosticRun, getSlides } from '../../api/client';
import { LineChart, Line, ResponsiveContainer, BarChart, Bar, Cell, XAxis, YAxis, Tooltip } from 'recharts';

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

function healthBadge(flagCount, hasCritical) {
  if (hasCritical) return { label: 'CRITICAL', color: '#DC2626' };
  if (flagCount >= 5) return { label: 'ACTION NEEDED', color: '#D97706' };
  if (flagCount >= 4) return { label: 'WATCH', color: '#F59E0B' };
  return { label: 'HEALTHY', color: '#059669' };
}

export default function PortfolioDashboard({ properties, onSelectProperty, onShowPortfolioSlideshow }) {
  const { user, logout } = useAuth();
  const [propertyFilter, setPropertyFilter] = useState('All Properties');
  const [unitTypeFilter, setUnitTypeFilter] = useState('All');
  const [summaryData, setSummaryData] = useState({}); // keyed by property id
  const [summaryLoading, setSummaryLoading] = useState(true);
  const [portfolioDiagLoading, setPortfolioDiagLoading] = useState(false);
  const [portfolioDiagStatus, setPortfolioDiagStatus] = useState('');
  const [portfolioError, setPortfolioError] = useState('');

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
    };
  }, [filtered]);

  const blendedOcc = kpis.totalUnits > 0 ? kpis.totalOccupied / kpis.totalUnits : 0;

  // Vacancy cost chart from filtered data
  const vacancyCostData = useMemo(() => {
    return filtered
      .map(([code, d]) => ({
        name: code,
        cost: d.monthlyCost,
        color: d.monthlyCost > 8000 ? '#DC2626' : d.monthlyCost > 5000 ? '#D97706' : d.monthlyCost > 2000 ? '#F59E0B' : '#6B7280',
      }))
      .sort((a, b) => b.cost - a.cost);
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
      </header>

      <main className="max-w-7xl mx-auto px-6 py-6">
        {/* Title + Filters */}
        <div className="flex items-start justify-between mb-6">
          <div>
            <h2 className="font-display text-2xl text-stone-900 mb-1">Portfolio Overview</h2>
            <p className="text-sm text-stone-400">March 2026</p>
          </div>
          <div className="flex gap-2">
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
        </div>

        {/* Hero KPI — Daily Burn prominent */}
        <div className="bg-white rounded-xl border border-stone-200 p-6 shadow-card mb-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs text-stone-400 font-semibold uppercase tracking-wider mb-1">Portfolio Daily Burn</p>
              <div className="flex items-baseline gap-2">
                <span className="font-mono text-4xl font-bold text-crisis">{formatDollar(kpis.dailyBurn)}</span>
                <span className="text-sm text-stone-400">/day</span>
                <span className="inline-flex items-center gap-1.5 ml-3">
                  <span className="w-2 h-2 rounded-full bg-crisis animate-pulse" />
                  <span className="text-sm text-stone-500">= {formatDollar(kpis.monthlyCost)}/mo</span>
                </span>
              </div>
            </div>
            <div className="flex gap-6 items-center">
              <button
                onClick={handleRunPortfolioDiagnostic}
                disabled={portfolioDiagLoading}
                className="px-4 py-2 bg-positive text-white rounded-lg hover:bg-positive/90 text-sm font-semibold transition-all flex items-center gap-2 disabled:opacity-30"
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
              <div className="text-right">
                <p className="text-[10px] text-stone-400 font-semibold uppercase tracking-wider">Blended Occ</p>
                <span className="font-mono text-2xl font-bold" style={{ color: occColor(blendedOcc) }}>{(blendedOcc * 100).toFixed(1)}%</span>
              </div>
              <div className="text-right">
                <p className="text-[10px] text-stone-400 font-semibold uppercase tracking-wider">Vacant</p>
                <span className="font-mono text-2xl font-bold text-stone-800">{kpis.totalVacant} <span className="text-sm text-stone-400 font-normal">/ {kpis.totalUnits}</span></span>
              </div>
            </div>
          </div>
        </div>

        {portfolioError && (
          <div className="bg-crisis/5 border border-crisis/20 text-crisis p-3 rounded-lg mb-4 text-sm flex justify-between">
            <span>{portfolioError}</span>
            <button onClick={() => setPortfolioError('')} className="text-crisis/60 hover:text-crisis">&times;</button>
          </div>
        )}

        {/* Charts row */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-6">
          <div className="bg-white rounded-xl border border-stone-200 p-5 shadow-card">
            <h3 className="text-xs font-semibold text-stone-500 uppercase tracking-wider mb-4">Vacancy Cost by Unit Type</h3>
            {vacancyCostData.length > 0 ? (
              <ResponsiveContainer width="100%" height={180}>
                <BarChart data={vacancyCostData} layout="vertical" margin={{ left: 5, right: 10 }}>
                  <XAxis type="number" tickFormatter={formatDollar} tick={{ fontSize: 10, fill: '#78716c' }} />
                  <YAxis type="category" dataKey="name" tick={{ fontSize: 11, fontWeight: 600, fill: '#57534e' }} width={30} />
                  <Tooltip formatter={(v) => formatDollar(v)} />
                  <Bar dataKey="cost" radius={[0, 4, 4, 0]} barSize={20}>
                    {vacancyCostData.map((d, i) => <Cell key={i} fill={d.color} />)}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <div className="h-[180px] flex items-center justify-center text-xs text-stone-400">No data for selection</div>
            )}
          </div>

          <div className="lg:col-span-2 bg-white rounded-xl border border-stone-200 p-5 shadow-card">
            <h3 className="text-xs font-semibold text-stone-500 uppercase tracking-wider mb-4">Occupancy Trends (4 months)</h3>
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
              {filtered.map(([code, d]) => (
                <div key={code}>
                  <div className="flex items-center justify-between mb-1">
                    <span className="font-mono text-xs font-bold text-stone-700">{code}</span>
                    <span className="font-mono text-xs font-semibold" style={{ color: occColor(d.occ) }}>
                      {(d.occ * 100).toFixed(0)}%
                    </span>
                  </div>
                  {trendData[code] ? (
                    <ResponsiveContainer width="100%" height={48}>
                      <LineChart data={trendData[code]}>
                        <Line type="monotone" dataKey="occ" stroke={occColor(d.occ)} strokeWidth={2} dot={false} />
                      </LineChart>
                    </ResponsiveContainer>
                  ) : (
                    <div className="h-[48px] flex items-center justify-center text-[10px] text-stone-300">No trend data</div>
                  )}
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Unit type detail cards — filtered */}
        <h3 className="text-xs font-semibold text-stone-500 uppercase tracking-wider mb-3">
          Unit Type Detail
          {filtered.length < Object.keys(unitTypeData).length && (
            <span className="ml-2 text-stone-400 normal-case font-normal">
              — showing {filtered.length} of {Object.keys(unitTypeData).length}
            </span>
          )}
        </h3>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-6">
          {filtered.map(([code, d]) => {
            const spread = d.asking - d.comps;
            const spreadPct = d.comps > 0 ? ((spread / d.comps) * 100).toFixed(1) : '0.0';
            return (
              <div key={code} className="bg-white rounded-xl border border-stone-200 p-5 shadow-card hover:shadow-card-hover transition-shadow">
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-3">
                    <span className="font-mono text-base font-bold text-stone-800">{code}</span>
                    <span className="text-xs text-stone-400">{d.property}</span>
                  </div>
                  <div className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: occColor(d.occ) }} title={`${(d.occ*100).toFixed(0)}% occupancy`} />
                </div>

                <div className="grid grid-cols-4 gap-3 mb-3">
                  <Metric label="Occupancy" value={formatPercent(d.occ)} color={occColor(d.occ)} />
                  <Metric label="Exposure" value={formatPercent(d.exposure)} color={d.exposure >= 0.20 ? '#DC2626' : d.exposure >= 0.10 ? '#D97706' : '#6B7280'} />
                  <Metric label="DOM" value={`${d.dom}d`} color={d.dom > 21 ? '#D97706' : '#6B7280'} />
                  <Metric label="Vacant" value={d.vacant} color={d.vacant >= 5 ? '#D97706' : '#6B7280'} />
                </div>

                <div className="grid grid-cols-3 gap-3 pt-3 border-t border-stone-100">
                  <div>
                    <span className="text-[10px] text-stone-400 uppercase tracking-wider">Asking</span>
                    <span className="font-mono text-sm font-bold text-stone-800 block">{formatDollar(d.asking)}</span>
                  </div>
                  <div>
                    <span className="text-[10px] text-stone-400 uppercase tracking-wider">Comps</span>
                    <span className="font-mono text-sm font-bold text-stone-600 block">{formatDollar(d.comps)}</span>
                  </div>
                  <div>
                    <span className="text-[10px] text-stone-400 uppercase tracking-wider">vs Comps</span>
                    <span className="font-mono text-sm font-bold block" style={{ color: spreadColor(d.asking, d.comps) }}>
                      {spread >= 0 ? '+' : ''}{formatDollar(spread)} ({spreadPct}%)
                    </span>
                  </div>
                </div>
              </div>
            );
          })}
        </div>

        {/* Property cards with health indicators */}
        <h3 className="text-xs font-semibold text-stone-500 uppercase tracking-wider mb-3">Properties</h3>
        <div className="grid gap-4">
          {properties
            .filter((prop) => propertyFilter === 'All Properties' || prop.name === propertyFilter)
            .map((prop) => {
              // Use direct KPIs from /properties response, fallback to computed from summaryData
              const propTypes = Object.entries(unitTypeData).filter(([, d]) => d.property === prop.name);
              const propVacant = prop.total_vacant ?? propTypes.reduce((s, [, d]) => s + d.vacant, 0);
              const propOcc = prop.blended_occ ?? (prop.total_units > 0 ? propTypes.reduce((s, [, d]) => s + d.occupied, 0) / prop.total_units : 0);
              const propBurn = prop.daily_burn ?? propTypes.reduce((s, [, d]) => s + d.dailyBurn, 0);
              const needsAttention = propOcc < 0.90 || propBurn > 400;
              const accentColor = needsAttention ? '#DC2626' : '#059669';
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
                        {needsAttention && (
                          <span className="text-[10px] font-bold bg-crisis/10 text-crisis px-2 py-0.5 rounded">
                            Needs attention
                          </span>
                        )}
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
                  <div className="grid grid-cols-4 gap-3 pt-3 border-t border-stone-100">
                    <Metric label="Occupancy" value={formatPercent(propOcc)} color={occColor(propOcc)} />
                    <Metric label="Vacant" value={propVacant} color={propVacant >= 8 ? '#D97706' : '#6B7280'} />
                    <Metric label="Daily Burn" value={formatDollar(propBurn)} color={needsAttention ? '#DC2626' : '#6B7280'} />
                    <Metric label="Unit Types" value={propTypes.length} color="#6B7280" />
                  </div>
                </div>
              );
            })}
        </div>

        {/* CTA guidance */}
        {properties.length > 0 && (
          <p className="text-center text-xs text-stone-400 mt-4">
            Click a property to see pricing details and run an AI diagnosis
          </p>
        )}
      </main>
    </div>
  );
}

function KPICard({ label, value, format, color, subtitle }) {
  let display;
  if (format === 'dollar') display = formatDollar(value);
  else if (format === 'pct') display = `${(value * 100).toFixed(1)}%`;
  else display = String(value);

  return (
    <div className="bg-white rounded-xl border border-stone-200 p-4 shadow-card">
      <p className="text-[10px] text-stone-400 font-semibold uppercase tracking-wider">{label}</p>
      <div className="flex items-baseline gap-1 mt-1">
        <span className="font-mono text-xl font-bold" style={{ color: color || '#1c1917' }}>{display}</span>
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
