import React, { useState } from 'react';
import { useAuth } from '../../auth/AuthContext';
import ConfigEditor from '../config/ConfigEditor';
import CompManagement from '../config/CompManagement';
import ExperimentTracking from '../config/ExperimentTracking';
import { runDiagnostic, getDiagnosticRun, getSlides } from '../../api/client';

const TABS = [
  { key: 'dashboard', label: 'Dashboard' },
  { key: 'config', label: 'Config' },
  { key: 'comps', label: 'Comps' },
  { key: 'experiments', label: 'Experiments' },
];

export default function PropertyDetail({ property, onBack, onDiagnosticComplete }) {
  const { user, logout } = useAuth();
  const [activeTab, setActiveTab] = useState('dashboard');
  const [diagLoading, setDiagLoading] = useState(false);
  const [diagStatus, setDiagStatus] = useState('');
  const [error, setError] = useState('');

  async function handleRunDiagnostic() {
    setDiagLoading(true);
    setDiagStatus('Starting diagnostic...');
    setError('');
    try {
      const run = await runDiagnostic(property.id);
      if (run.status === 'COMPLETED') {
        const deck = await getSlides(run.id);
        setDiagLoading(false);
        onDiagnosticComplete(deck);
        return;
      }
      setDiagStatus('Running pipeline...');
      let attempts = 0;
      const poll = setInterval(async () => {
        attempts++;
        try {
          const status = await getDiagnosticRun(run.id);
          if (status.status === 'COMPLETED') {
            clearInterval(poll);
            const deck = await getSlides(run.id);
            setDiagLoading(false);
            onDiagnosticComplete(deck);
          } else if (status.status === 'FAILED' || attempts >= 30) {
            clearInterval(poll);
            setDiagLoading(false);
            setError(status.error_message || 'Diagnostic timed out');
          }
        } catch {
          clearInterval(poll);
          setDiagLoading(false);
          setError('Connection lost');
        }
      }, 2000);
    } catch (err) {
      setDiagLoading(false);
      setError(err.response?.data?.detail || 'Failed');
    }
  }

  return (
    <div className="min-h-screen bg-stone-50">
      <header className="bg-white border-b border-stone-200">
        <div className="max-w-6xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <button onClick={onBack} className="text-stone-400 hover:text-stone-600 text-sm transition-colors">
              ← Properties
            </button>
            <div className="w-px h-5 bg-stone-200" />
            <h1 className="font-display text-lg text-stone-900">{property.name}</h1>
            <span className="font-mono text-xs text-stone-400">{property.total_units} units</span>
          </div>
          <div className="flex items-center gap-4">
            <span className="text-xs text-stone-400">{user?.email}</span>
            <button onClick={logout} className="text-xs text-stone-400 hover:text-stone-600 transition-colors">Sign out</button>
          </div>
        </div>
        {/* Tab bar */}
        <div className="max-w-6xl mx-auto px-6">
          <div className="flex gap-0 border-b-0">
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

      <main className="max-w-6xl mx-auto px-6 py-6">
        {error && (
          <div className="bg-crisis/5 border border-crisis/20 text-crisis p-3 rounded-lg mb-4 text-sm" role="alert">
            {error}
          </div>
        )}

        {activeTab === 'dashboard' && (
          <div>
            <div className="flex items-center justify-between mb-6">
              <h2 className="font-display text-xl text-stone-900">Property Dashboard</h2>
              <button
                onClick={handleRunDiagnostic}
                disabled={diagLoading}
                className="px-5 py-2.5 bg-stone-900 text-white rounded-lg hover:bg-stone-800 disabled:opacity-30 text-sm font-semibold transition-all"
              >
                {diagLoading ? diagStatus : 'Run Diagnostic'}
              </button>
            </div>
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
              <InfoCard label="Total Units" value={property.total_units} />
              <InfoCard label="Submarket" value={property.submarket} />
              <InfoCard label="Year Built" value={property.year_built} />
              <InfoCard label="Class" value={property.property_class} />
            </div>
          </div>
        )}

        {activeTab === 'config' && <ConfigEditor propertyId={property.id} />}
        {activeTab === 'comps' && <CompManagement propertyId={property.id} />}
        {activeTab === 'experiments' && <ExperimentTracking propertyId={property.id} />}
      </main>
    </div>
  );
}

function InfoCard({ label, value }) {
  return (
    <div className="bg-white rounded-xl border border-stone-200 p-4 shadow-card">
      <p className="text-[11px] text-stone-400 font-medium uppercase tracking-wider">{label}</p>
      <p className="font-mono text-lg font-bold text-stone-800 mt-1">{value || '—'}</p>
    </div>
  );
}
