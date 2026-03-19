import React, { useState, useRef, useEffect } from 'react';
import { useAuth } from '../../auth/AuthContext';
import { runDiagnostic, getDiagnosticRun, getSlides, getConfig, previewDiagnosis, getPropertySummary } from '../../api/client';
import { formatDollar, formatPercent, gradeColor, gradeLabel } from '../../utils/format';
import { LineChart, Line, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from 'recharts';
import ConfigEditor from '../config/ConfigEditor';
import CompManagement from '../config/CompManagement';
import ExperimentTracking from '../config/ExperimentTracking';
import ChatPanel from '../chat/ChatPanel';

const TABS = [
  { key: 'overview', label: 'Overview' },
  { key: 'review', label: 'AI Review' },
  { key: 'config', label: 'Config' },
  { key: 'comps', label: 'Comps' },
  { key: 'experiments', label: 'Experiments' },
];

export default function PricingReview({ property, onBack, onShowSlideshow }) {
  const { user, logout } = useAuth();
  const [activeTab, setActiveTab] = useState('overview');
  const [diagLoading, setDiagLoading] = useState(false);
  const [diagStatus, setDiagStatus] = useState('');
  const [diagResult, setDiagResult] = useState(null);
  const [slideDeck, setSlideDeck] = useState(null);
  const [flagPreview, setFlagPreview] = useState(null);
  const [summaryData, setSummaryData] = useState(null);
  const [summaryLoading, setSummaryLoading] = useState(true);
  const [error, setError] = useState('');
  const [chatOpen, setChatOpen] = useState(false);
  const pollRef = useRef(null);

  useEffect(() => {
    loadFlagPreview();
    loadSummary();
    return () => { if (pollRef.current) clearInterval(pollRef.current); };
  }, [property.id]);

  async function loadFlagPreview() {
    try {
      const config = await getConfig(property.id);
      const preview = await previewDiagnosis(property.id, config);
      setFlagPreview(preview);
    } catch { /* silent — flags are supplementary */ }
  }

  async function loadSummary() {
    setSummaryLoading(true);
    try {
      const data = await getPropertySummary(property.id);
      setSummaryData(data);
    } catch { /* silent — will show loading state */ }
    setSummaryLoading(false);
  }

  async function handleRunDiagnostic() {
    setDiagLoading(true);
    setDiagStatus('Computing metrics...');
    setError('');
    try {
      const run = await runDiagnostic(property.id);
      if (run.status === 'COMPLETED') {
        setDiagResult(run);
        setDiagStatus('Loading presentation...');
        const deck = await getSlides(run.id);
        setSlideDeck(deck);
        setDiagLoading(false);
        return;
      }
      setDiagStatus('Running AI diagnosis...');
      let attempts = 0;
      pollRef.current = setInterval(async () => {
        attempts++;
        try {
          const status = await getDiagnosticRun(run.id);
          if (status.status === 'COMPLETED') {
            clearInterval(pollRef.current);
            pollRef.current = null;
            setDiagResult(status);
            const deck = await getSlides(status.id);
            setSlideDeck(deck);
            setDiagLoading(false);
          } else if (status.status === 'FAILED' || attempts >= 30) {
            clearInterval(pollRef.current);
            pollRef.current = null;
            setDiagLoading(false);
            setError(status.error_message || 'Timed out');
          }
        } catch {
          clearInterval(pollRef.current);
          pollRef.current = null;
          setDiagLoading(false);
          setError('Connection lost');
        }
      }, 2000);
    } catch (err) {
      setDiagLoading(false);
      setError(err.response?.data?.detail || 'Failed to start');
    }
  }

  return (
    <div className="min-h-screen bg-stone-50">
      <header className="bg-white border-b border-stone-200">
        <div className="max-w-7xl mx-auto px-6 py-3 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <button onClick={onBack} className="text-stone-400 hover:text-stone-600 text-sm transition-colors">
              ← Portfolio
            </button>
            <div className="w-px h-5 bg-stone-200" />
            <div className="flex items-center gap-3">
              <div className="w-7 h-7 rounded bg-positive flex items-center justify-center">
                <span className="text-white font-mono font-bold text-xs">RR</span>
              </div>
              <span className="font-display text-base text-stone-900">{property.name}</span>
              <span className="font-mono text-xs text-stone-400">{property.total_units} units</span>
            </div>
          </div>
          <div className="flex items-center gap-5">
            <button
              onClick={() => setChatOpen(!chatOpen)}
              className={`px-5 py-2.5 text-sm font-semibold rounded-lg transition-all flex items-center gap-2 shadow-sm ${
                chatOpen ? 'bg-stone-800 text-white shadow-lg' : 'bg-blue-600 text-white hover:bg-blue-700 shadow-blue-200'
              }`}
            >
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
              </svg>
              Ask AI
            </button>
            <span className="text-xs text-stone-400">{user?.email}</span>
            <button onClick={logout} className="text-xs text-stone-400 hover:text-stone-600 transition-colors">Sign out</button>
          </div>
        </div>
        <div className="max-w-7xl mx-auto px-6">
          <div className="flex gap-0">
            {TABS.map((tab) => (
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
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-6 py-6">
        {activeTab === 'overview' && (
          <OverviewTab
            property={property}
            flagPreview={flagPreview}
            summaryData={summaryData}
            summaryLoading={summaryLoading}
            diagLoading={diagLoading}
            diagResult={diagResult}
            onRunDiagnostic={() => { setActiveTab('review'); handleRunDiagnostic(); }}
          />
        )}
        {activeTab === 'review' && (
          <ReviewTab
            property={property}
            flagPreview={flagPreview}
            summaryData={summaryData}
            diagLoading={diagLoading}
            diagStatus={diagStatus}
            diagResult={diagResult}
            slideDeck={slideDeck}
            error={error}
            onRunDiagnostic={handleRunDiagnostic}
            onShowSlideshow={() => slideDeck && onShowSlideshow(slideDeck)}
            onClearError={() => setError('')}
          />
        )}
        {activeTab === 'config' && <ConfigEditor propertyId={property.id} />}
        {activeTab === 'comps' && <CompManagement propertyId={property.id} />}
        {activeTab === 'experiments' && <ExperimentTracking propertyId={property.id} />}
      </main>

      <ChatPanel
        propertyId={property.id}
        propertyName={property.name}
        latestRunId={diagResult?.id}
        summaryData={summaryData}
        isOpen={chatOpen}
        onToggle={() => setChatOpen(!chatOpen)}
      />
    </div>
  );
}

function ReviewTab({ property, flagPreview, summaryData, diagLoading, diagStatus, diagResult, slideDeck, error, onRunDiagnostic, onShowSlideshow, onClearError }) {
  const diagnosis = diagResult?.diagnosis_json;
  const actionPlan = diagResult?.action_plan_json;
  const flags = diagResult?.flags_json;
  const hasRunDiag = !!diagnosis;

  return (
    <div>
      {/* Top bar: Run Diagnostic + Present as Slideshow */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="font-display text-2xl text-stone-900">Pricing Review</h2>
          <p className="text-sm text-stone-400">Analyze rent positioning and get AI recommendations</p>
        </div>
        <div className="flex gap-3">
          {slideDeck && (
            <button
              onClick={onShowSlideshow}
              className="px-4 py-2 border border-stone-300 text-stone-700 rounded-lg text-sm font-medium hover:bg-stone-50 transition-colors flex items-center gap-2"
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M7 4v16M17 4v16M3 8h4m10 0h4M3 12h18M3 16h4m10 0h4M4 20h16a1 1 0 001-1V5a1 1 0 00-1-1H4a1 1 0 00-1 1v14a1 1 0 001 1z" />
              </svg>
              Present as Slideshow
            </button>
          )}
          <button
            onClick={onRunDiagnostic}
            disabled={diagLoading}
            className={`px-5 py-2.5 rounded-lg text-sm font-semibold transition-all flex items-center gap-2 ${
              !hasRunDiag && !diagLoading
                ? 'bg-positive text-white hover:bg-positive/90 ring-2 ring-positive/30 ring-offset-2'
                : 'bg-stone-900 text-white hover:bg-stone-800 disabled:opacity-30'
            }`}
          >
            {diagLoading ? (
              <>
                <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                {diagStatus}
              </>
            ) : (
              <>
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                </svg>
                Get AI Review
                {!hasRunDiag && <span className="text-xs opacity-75 ml-1">~10 seconds</span>}
              </>
            )}
          </button>
        </div>
      </div>

      {error && (
        <div className="bg-crisis/5 border border-crisis/20 text-crisis p-3 rounded-lg mb-4 text-sm animate-fade-in flex justify-between" role="alert">
          <span>
            {error === 'Timed out' || error === 'Connection lost'
              ? 'AI analysis is taking longer than expected. Showing automated metrics and flags below.'
              : error}
          </span>
          <button onClick={onClearError} className="text-crisis/60 hover:text-crisis">&times;</button>
        </div>
      )}

      {/* Progressive Phase 1: Metrics (shown immediately from summary) */}
      {diagLoading && summaryData && !diagnosis && (
        <div className="bg-white rounded-xl border border-stone-200 p-5 shadow-card mb-4 animate-fade-in">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-xs font-semibold text-stone-500 uppercase tracking-wider">Property Metrics</h3>
            <div className="flex items-center gap-2 text-xs text-stone-400">
              <span className="w-2 h-2 rounded-full bg-positive" /> Metrics computed
              <span className="w-2 h-2 rounded-full bg-positive ml-2" /> Flags generated
              <span className="w-2 h-2 rounded-full bg-stone-300 animate-pulse ml-2" /> AI analyzing...
            </div>
          </div>
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
            {Object.entries(summaryData.unit_types).map(([code, d]) => (
              <div key={code} className="bg-stone-50 rounded-lg p-3">
                <span className="font-mono text-xs font-bold text-stone-700">{code}</span>
                <div className="grid grid-cols-2 gap-1 mt-2 text-xs">
                  <span className="text-stone-400">Occ</span>
                  <span className="font-mono font-semibold" style={{ color: occColor(d.occ) }}>{formatPercent(d.occ)}</span>
                  <span className="text-stone-400">Asking</span>
                  <span className="font-mono font-semibold text-stone-700">{formatDollar(d.asking)}</span>
                  <span className="text-stone-400">vs Comps</span>
                  <span className="font-mono font-semibold" style={{ color: d.asking > d.comps ? '#D97706' : '#059669' }}>
                    {d.asking >= d.comps ? '+' : ''}{formatDollar(d.asking - d.comps)}
                  </span>
                  <span className="text-stone-400">Cost</span>
                  <span className="font-mono font-semibold text-crisis">{formatDollar(d.dailyBurn)}/d</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Progressive Phase 2: Flags (always visible if loaded) */}
      {flagPreview && !diagnosis && (
        <div className="bg-white rounded-xl border border-stone-200 p-5 shadow-card mb-6">
          <h3 className="text-xs font-semibold text-stone-500 uppercase tracking-wider mb-4">
            Current Pricing Flags (automated analysis)
          </h3>
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
            {Object.entries(flagPreview).map(([code, data]) => (
              <FlagCard key={code} code={code} data={data} />
            ))}
          </div>
          {!diagLoading && (
            <p className="text-xs text-stone-400 mt-4">
              These flags are computed automatically from your rent roll data. Click "Get AI Review" for diagnosis and recommendations.
            </p>
          )}
        </div>
      )}

      {/* Progressive Phase 3: AI Diagnosis (shown after diagnostic completes) */}
      {diagnosis && (
        <div className="space-y-4 mb-6 animate-fade-in">
          <div className="bg-white rounded-xl border border-stone-200 p-5 shadow-card">
            <h3 className="text-xs font-semibold text-stone-500 uppercase tracking-wider mb-4">
              AI Diagnosis
            </h3>

            {/* Unit type assessments */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-4">
              {(diagnosis.unit_type_assessments || []).map((a) => (
                <div key={a.unit_type} className="border border-stone-100 rounded-lg p-4" style={{ borderLeftWidth: '4px', borderLeftColor: gradeColor(a.grade) }}>
                  <div className="flex items-center justify-between mb-2">
                    <span className="font-mono text-sm font-bold text-stone-800">{a.unit_type}</span>
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-lg font-bold" style={{ color: gradeColor(a.grade) }}>{a.health_score}</span>
                      <span className="text-[10px] font-bold uppercase px-2 py-0.5 rounded" style={{
                        backgroundColor: gradeColor(a.grade) + '15',
                        color: gradeColor(a.grade),
                      }}>
                        {gradeLabel(a.grade)}
                      </span>
                    </div>
                  </div>
                  {a.root_cause && (
                    <p className="text-sm text-stone-600 mb-2">{a.root_cause}</p>
                  )}
                  {a.recommended_actions && a.recommended_actions.length > 0 && (
                    <div className="mt-3 pt-3 border-t border-stone-100">
                      <span className="text-[10px] text-stone-400 uppercase tracking-wider font-semibold">Recommended Actions</span>
                      <div className="mt-2 space-y-1.5">
                        {a.recommended_actions.slice(0, 3).map((act, i) => (
                          <div key={i} className="flex items-start gap-2 text-sm">
                            <span className="text-[10px] font-mono font-bold text-stone-400 mt-0.5">P{act.priority}</span>
                            <div>
                              <span className="text-stone-700">{act.description}</span>
                              <span className="text-[10px] ml-2 px-1.5 py-0.5 rounded" style={{
                                backgroundColor: act.confidence === 'HIGH' ? '#05966915' : act.confidence === 'MEDIUM' ? '#7C3AED15' : '#6B728015',
                                color: act.confidence === 'HIGH' ? '#059669' : act.confidence === 'MEDIUM' ? '#7C3AED' : '#6B7280',
                              }}>
                                {act.confidence}
                              </span>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              ))}
            </div>

            {/* Portfolio summary */}
            {diagnosis.portfolio_assessment && (
              <div className="bg-stone-50 rounded-lg p-4 text-sm text-stone-600">
                {diagnosis.portfolio_assessment.summary}
              </div>
            )}
          </div>

          {/* Step 3: Action Plan (shown after diagnostic) */}
          {actionPlan && actionPlan.phases && (
            <div className="bg-white rounded-xl border border-stone-200 p-5 shadow-card">
              <h3 className="text-xs font-semibold text-stone-500 uppercase tracking-wider mb-4">
                30-Day Action Plan
              </h3>
              <div className="space-y-3">
                {actionPlan.phases.map((phase) => (
                  <div key={phase.phase_number} className="border border-stone-100 rounded-lg p-4">
                    <div className="flex items-center gap-3 mb-2">
                      <span className="w-6 h-6 rounded-full bg-stone-800 text-white text-xs font-bold flex items-center justify-center">
                        {phase.phase_number}
                      </span>
                      <span className="font-semibold text-sm text-stone-800">{phase.name}</span>
                      <span className="text-xs text-stone-400">Days {phase.days}</span>
                    </div>
                    {phase.actions && phase.actions.length > 0 && (
                      <div className="ml-9 space-y-1.5">
                        {phase.actions.map((a, i) => (
                          <div key={i} className="flex items-center gap-2 text-sm">
                            <span className="font-mono text-[10px] text-stone-400">{a.id}</span>
                            <span className="font-mono text-[10px] text-stone-500">{a.unit_type}</span>
                            <span className="text-stone-600">{a.description}</span>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Flags detail (from diagnostic) */}
          {flags && (
            <div className="bg-white rounded-xl border border-stone-200 p-5 shadow-card">
              <h3 className="text-xs font-semibold text-stone-500 uppercase tracking-wider mb-4">
                Pricing Flags Detail
              </h3>
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                {Object.entries(flags).map(([code, flagList]) => (
                  <div key={code}>
                    <span className="font-mono text-xs font-bold text-stone-700">{code} — {flagList.length} flags</span>
                    <div className="mt-2 space-y-1">
                      {flagList.map((f, i) => (
                        <div key={i} className="flex items-center gap-2">
                          <SeverityDot severity={f.severity} />
                          <span className="text-xs text-stone-600">{f.type.replace(/_/g, ' ')}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Empty state when no diagnostic has been run */}
      {!diagnosis && !diagLoading && !flagPreview && (
        <div className="bg-white rounded-xl border border-stone-200 p-12 text-center shadow-card">
          <p className="text-stone-400 text-sm">Click "Get AI Review" to analyze pricing for {property.name}</p>
        </div>
      )}
    </div>
  );
}

function FlagCard({ code, data }) {
  const count = data.flag_count;
  const criticals = data.flags.filter(f => f.severity === 'CRITICAL').length;
  const highs = data.flags.filter(f => f.severity === 'HIGH').length;

  let badge;
  if (criticals > 0) badge = { label: 'CRITICAL', color: '#DC2626' };
  else if (count >= 5 || highs > 0) badge = { label: 'ACTION NEEDED', color: '#D97706' };
  else if (count >= 4) badge = { label: 'WATCH', color: '#F59E0B' };
  else badge = { label: 'HEALTHY', color: '#059669' };

  return (
    <div className="bg-stone-50 rounded-lg p-3" style={{ borderLeftWidth: '3px', borderLeftColor: badge.color }}>
      <div className="flex items-center justify-between mb-1">
        <span className="font-mono text-xs font-bold text-stone-700">{code}</span>
        <span className="text-[9px] font-bold px-1.5 py-0.5 rounded" style={{
          backgroundColor: badge.color + '15',
          color: badge.color,
        }}>
          {badge.label}
        </span>
      </div>
      <span className="font-mono text-2xl font-bold" style={{ color: badge.color }}>{count}</span>
      <span className="text-[10px] text-stone-400 ml-1">flags</span>
      {criticals > 0 && (
        <span className="text-[9px] font-bold text-crisis ml-2">{criticals} CRITICAL</span>
      )}
    </div>
  );
}

function SeverityDot({ severity }) {
  const colors = {
    CRITICAL: '#DC2626', HIGH: '#D97706', MEDIUM: '#F59E0B',
    LOW: '#6B7280', POSITIVE: '#0D9488', INFO: '#7C3AED',
  };
  return <div className="severity-dot" style={{ backgroundColor: colors[severity] || '#6B7280' }} />;
}

// ============================================================
// Overview Tab — property-level data from API
// ============================================================

function occColor(occ) {
  if (occ >= 0.96) return '#059669';
  if (occ >= 0.92) return '#0D9488';
  if (occ >= 0.88) return '#F59E0B';
  if (occ >= 0.82) return '#D97706';
  return '#DC2626';
}

function OverviewTab({ property, flagPreview, summaryData, summaryLoading, diagLoading, diagResult, onRunDiagnostic }) {
  if (summaryLoading || !summaryData) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="flex flex-col items-center gap-3">
          <div className="w-8 h-8 border-2 border-stone-300 border-t-stone-700 rounded-full animate-spin" />
          <span className="text-sm text-stone-400">Loading property data</span>
        </div>
      </div>
    );
  }

  const propCode = property.name === 'Property A' ? 'A' : 'B';
  const unitTypes = Object.entries(summaryData.unit_types).filter(([code]) => code.startsWith(propCode));
  const propVacant = unitTypes.reduce((s, [, d]) => s + d.vacant, 0);
  const propOccupied = unitTypes.reduce((s, [, d]) => s + d.occupied, 0);
  const propTotal = unitTypes.reduce((s, [, d]) => s + d.total, 0);
  const propOcc = propTotal > 0 ? propOccupied / propTotal : 0;
  const propBurn = unitTypes.reduce((s, [, d]) => s + d.dailyBurn, 0);
  const propMonthlyCost = unitTypes.reduce((s, [, d]) => s + d.monthlyCost, 0);
  const trends = summaryData.trends || {};

  return (
    <div>
      {/* Property KPIs */}
      <div className="flex items-center justify-between mb-6">
        <h2 className="font-display text-2xl text-stone-900">{property.name} Overview</h2>
        <button
          onClick={onRunDiagnostic}
          disabled={diagLoading}
          className={`px-5 py-2.5 rounded-lg text-sm font-semibold transition-all flex items-center gap-2 ${
            diagResult
              ? 'bg-stone-900 text-white hover:bg-stone-800'
              : 'bg-positive text-white hover:bg-positive/90 ring-2 ring-positive/30 ring-offset-2'
          } disabled:opacity-30`}
        >
          {diagLoading ? (
            <>
              <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
              Running...
            </>
          ) : diagResult ? (
            <>
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
              </svg>
              View AI Review
            </>
          ) : (
            <>
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
              </svg>
              Get AI Review
              <span className="text-xs opacity-75">~10s</span>
            </>
          )}
        </button>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-6">
        <div className="bg-white rounded-xl border border-stone-200 p-4 shadow-card">
          <p className="text-[10px] text-stone-400 font-semibold uppercase tracking-wider">Occupancy</p>
          <span className="font-mono text-xl font-bold" style={{ color: occColor(propOcc) }}>{(propOcc * 100).toFixed(1)}%</span>
        </div>
        <div className="bg-white rounded-xl border border-stone-200 p-4 shadow-card">
          <p className="text-[10px] text-stone-400 font-semibold uppercase tracking-wider">Vacant / Total</p>
          <span className="font-mono text-xl font-bold text-stone-800">{propVacant} <span className="text-stone-400 text-sm">/ {propTotal}</span></span>
        </div>
        <div className="bg-white rounded-xl border border-stone-200 p-4 shadow-card">
          <p className="text-[10px] text-stone-400 font-semibold uppercase tracking-wider">Daily Vacancy Cost</p>
          <span className="font-mono text-xl font-bold text-crisis">{formatDollar(propBurn)}<span className="text-[10px] text-stone-400 ml-1">/day</span></span>
        </div>
        <div className="bg-white rounded-xl border border-stone-200 p-4 shadow-card">
          <p className="text-[10px] text-stone-400 font-semibold uppercase tracking-wider">Monthly Vacancy Cost</p>
          <span className="font-mono text-xl font-bold text-crisis">{formatDollar(propMonthlyCost)}</span>
        </div>
      </div>

      {/* Flag summary if available */}
      {flagPreview && (
        <div className="bg-white rounded-xl border border-stone-200 p-5 shadow-card mb-6">
          <h3 className="text-xs font-semibold text-stone-500 uppercase tracking-wider mb-3">Automated Pricing Flags</h3>
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
            {Object.entries(flagPreview).filter(([code]) => code.startsWith(propCode)).map(([code, data]) => (
              <FlagCard key={code} code={code} data={data} />
            ))}
          </div>
        </div>
      )}

      {/* Deep unit type cards */}
      <h3 className="text-xs font-semibold text-stone-500 uppercase tracking-wider mb-3">Unit Type Analysis</h3>
      <div className="space-y-4 mb-6">
        {unitTypes.map(([code, d]) => {
          const spread = d.asking - d.comps;
          const spreadPct = d.comps > 0 ? ((spread / d.comps) * 100).toFixed(1) : '0.0';
          const ltl = d.asking - d.inPlace;
          const ltlPct = d.inPlace > 0 ? ((ltl / d.inPlace) * 100).toFixed(1) : '0.0';

          // Health badge from flag preview
          const fpData = flagPreview?.[code];
          const criticals = fpData ? fpData.flags.filter(f => f.severity === 'CRITICAL').length : 0;
          const highs = fpData ? fpData.flags.filter(f => f.severity === 'HIGH').length : 0;
          const flagCount = fpData ? fpData.flag_count : 0;
          let badge;
          if (criticals > 0) badge = { label: 'CRITICAL', color: '#DC2626' };
          else if (flagCount >= 5 || highs > 0) badge = { label: 'ACTION NEEDED', color: '#D97706' };
          else if (flagCount >= 4) badge = { label: 'WATCH', color: '#F59E0B' };
          else badge = { label: 'HEALTHY', color: '#059669' };

          return (
            <div key={code} className="bg-white rounded-xl border border-stone-200 p-6 shadow-card" style={{ borderLeftWidth: '4px', borderLeftColor: badge.color }}>
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-3">
                  <span className="font-mono text-lg font-bold text-stone-800">{code}</span>
                  <span className="text-xs text-stone-400">{d.total} units ({d.occupied} occ / {d.vacant} vac / {d.onNotice} notice)</span>
                  <span className="text-[9px] font-bold px-2 py-0.5 rounded" style={{
                    backgroundColor: badge.color + '15',
                    color: badge.color,
                  }}>
                    {badge.label}
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  <div className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: occColor(d.occ) }} />
                  <span className="font-mono text-sm font-bold" style={{ color: occColor(d.occ) }}>{(d.occ * 100).toFixed(0)}%</span>
                </div>
              </div>

              {/* Rent stack */}
              <div className="grid grid-cols-3 lg:grid-cols-7 gap-3 mb-4">
                <RentMetric label="Base" value={d.base} />
                <RentMetric label="Amenity" value={d.amenity} prefix="+" />
                <RentMetric label="Predicted" value={d.predicted} bold />
                <RentMetric label="Asking" value={d.asking} bold color="#7C3AED" />
                <RentMetric label="Comps" value={d.comps} color="#2563EB" />
                <RentMetric label="In-Place" value={d.inPlace} color="#059669" />
                <RentMetric label="Executed" value={d.executed} color="#78716c" />
              </div>

              {/* Spread analysis + velocity */}
              <div className="grid grid-cols-2 lg:grid-cols-6 gap-3 pt-3 border-t border-stone-100">
                <div>
                  <span className="text-[10px] text-stone-400 uppercase tracking-wider">vs Comps</span>
                  <span className="font-mono text-sm font-bold block" style={{ color: spread > 0 ? (Math.abs(spread/d.comps) > 0.05 ? '#DC2626' : '#D97706') : '#059669' }}>
                    {spread >= 0 ? '+' : ''}{formatDollar(spread)} ({spreadPct}%)
                  </span>
                </div>
                <div>
                  <span className="text-[10px] text-stone-400 uppercase tracking-wider">Loss-to-Lease</span>
                  <span className="font-mono text-sm font-bold block" style={{ color: ltl < 0 ? '#DC2626' : '#059669' }}>
                    {ltl >= 0 ? '+' : ''}{formatDollar(ltl)} ({ltlPct}%)
                  </span>
                </div>
                <div>
                  <span className="text-[10px] text-stone-400 uppercase tracking-wider">Exposure</span>
                  <span className="font-mono text-sm font-bold block" style={{ color: d.exposure >= 0.20 ? '#DC2626' : d.exposure >= 0.10 ? '#D97706' : '#6B7280' }}>
                    {(d.exposure * 100).toFixed(0)}%
                  </span>
                </div>
                <div>
                  <span className="text-[10px] text-stone-400 uppercase tracking-wider">DOM / DV</span>
                  <span className="font-mono text-sm font-bold text-stone-700 block">{d.dom}d / {d.dv}d</span>
                </div>
                <div>
                  <span className="text-[10px] text-stone-400 uppercase tracking-wider">Demand</span>
                  <span className="font-mono text-sm font-bold text-stone-700 block">{(d.demand * 100).toFixed(0)}%</span>
                </div>
                <div>
                  <span className="text-[10px] text-stone-400 uppercase tracking-wider">Daily Cost</span>
                  <span className="font-mono text-sm font-bold text-crisis block">{formatDollar(d.dailyBurn)}/day</span>
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {/* Trend charts — asking vs comps over time */}
      <h3 className="text-xs font-semibold text-stone-500 uppercase tracking-wider mb-3">Asking vs Comps Trend</h3>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-6">
        {unitTypes.map(([code, d]) => (
          <div key={code} className="bg-white rounded-xl border border-stone-200 p-5 shadow-card">
            <div className="flex items-center justify-between mb-3">
              <span className="font-mono text-sm font-bold text-stone-700">{code}</span>
              <div className="flex items-center gap-3 text-[10px] text-stone-400">
                <span className="flex items-center gap-1"><span className="w-3 h-0.5 bg-[#7C3AED] inline-block" /> Asking</span>
                <span className="flex items-center gap-1"><span className="w-3 h-0.5 bg-[#2563EB] inline-block border-dashed" /> Comps</span>
              </div>
            </div>
            {trends[code] ? (
              <ResponsiveContainer width="100%" height={160}>
                <LineChart data={trends[code]} margin={{ top: 5, right: 5, left: 5, bottom: 5 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e7e5e4" />
                  <XAxis dataKey="m" tick={{ fontSize: 10, fill: '#78716c' }} />
                  <YAxis tickFormatter={formatDollar} tick={{ fontSize: 10, fill: '#78716c' }} domain={['dataMin - 30', 'dataMax + 30']} />
                  <Tooltip formatter={(v) => formatDollar(v)} />
                  <Line type="monotone" dataKey="asking" stroke="#7C3AED" strokeWidth={2} dot={{ r: 3 }} />
                  <Line type="monotone" dataKey="comps" stroke="#2563EB" strokeWidth={2} dot={{ r: 3 }} strokeDasharray="5 5" />
                </LineChart>
              </ResponsiveContainer>
            ) : (
              <div className="h-[160px] flex items-center justify-center text-xs text-stone-400">No trend data</div>
            )}
          </div>
        ))}
      </div>

      {/* Property info */}
      <div className="bg-stone-100 rounded-xl p-4 text-xs text-stone-500">
        <span className="font-semibold text-stone-600">{property.name}</span> — {property.address} | {property.submarket} | Built {property.year_built} | Class {property.property_class}
      </div>
    </div>
  );
}

function RentMetric({ label, value, bold, color, prefix }) {
  return (
    <div>
      <span className="text-[10px] text-stone-400 uppercase tracking-wider">{label}</span>
      <span className={`font-mono text-sm block ${bold ? 'font-bold' : 'font-medium'}`} style={{ color: color || '#1c1917' }}>
        {prefix}{formatDollar(value)}
      </span>
    </div>
  );
}
