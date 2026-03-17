import React, { useState, useEffect, useRef } from 'react';
import { useAuth } from '../../auth/AuthContext';
import { getProperties, runDiagnostic, getDiagnosticRun, getSlides } from '../../api/client';

export default function PropertyList({ onSelectProperty, onDiagnosticComplete, selectedProperty }) {
  const { user, logout } = useAuth();
  const [properties, setProperties] = useState([]);
  const [loading, setLoading] = useState(true);
  const [diagLoading, setDiagLoading] = useState(false);
  const [diagStatus, setDiagStatus] = useState('');
  const [error, setError] = useState('');
  const pollRef = useRef(null);

  useEffect(() => {
    loadProperties();
    return () => { if (pollRef.current) clearInterval(pollRef.current); };
  }, []);

  async function loadProperties() {
    try {
      const data = await getProperties();
      setProperties(data);
    } catch {
      setError('Failed to load properties. Is the backend running?');
    }
    setLoading(false);
  }

  async function handleRunDiagnostic(property) {
    onSelectProperty(property);
    setDiagLoading(true);
    setDiagStatus('Initializing diagnostic pipeline...');
    setError('');

    try {
      const run = await runDiagnostic(property.id);
      const runId = run.id;

      if (run.status === 'COMPLETED') {
        setDiagStatus('Assembling slide deck...');
        const deck = await getSlides(runId);
        setDiagLoading(false);
        onDiagnosticComplete(deck);
        return;
      }

      setDiagStatus('Computing metrics and generating diagnosis...');
      let attempts = 0;

      pollRef.current = setInterval(async () => {
        attempts++;
        try {
          const status = await getDiagnosticRun(runId);
          if (status.status === 'COMPLETED') {
            clearInterval(pollRef.current);
            pollRef.current = null;
            setDiagStatus('Assembling slide deck...');
            const deck = await getSlides(runId);
            setDiagLoading(false);
            onDiagnosticComplete(deck);
          } else if (status.status === 'FAILED') {
            clearInterval(pollRef.current);
            pollRef.current = null;
            setDiagLoading(false);
            setError(status.error_message || 'Diagnostic failed');
          } else if (attempts >= 30) {
            clearInterval(pollRef.current);
            pollRef.current = null;
            setDiagLoading(false);
            setError('Diagnostic timed out');
          }
        } catch {
          clearInterval(pollRef.current);
          pollRef.current = null;
          setDiagLoading(false);
          setError('Lost connection during diagnostic');
        }
      }, 2000);
    } catch (err) {
      setDiagLoading(false);
      setError(err.response?.data?.detail || 'Failed to start diagnostic');
    }
  }

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-stone-50">
        <div className="flex flex-col items-center gap-3">
          <div className="w-8 h-8 border-2 border-stone-300 border-t-stone-700 rounded-full animate-spin" />
          <span className="text-sm text-stone-400">Loading properties</span>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-stone-50">
      <header className="bg-white border-b border-stone-200">
        <div className="max-w-6xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-7 h-7 rounded bg-positive flex items-center justify-center">
              <span className="text-white font-mono font-bold text-xs">RM</span>
            </div>
            <div>
              <h1 className="font-display text-lg text-stone-900 leading-tight">Revenue Management</h1>
              <p className="text-xs text-stone-400">Pricing Diagnostic Platform</p>
            </div>
          </div>
          <div className="flex items-center gap-5">
            <span className="text-xs text-stone-400">{user?.email}</span>
            <button onClick={logout} className="text-xs text-stone-400 hover:text-stone-600 transition-colors">
              Sign out
            </button>
          </div>
        </div>
      </header>

      <main className="max-w-6xl mx-auto px-6 py-8">
        <div className="mb-8">
          <h2 className="font-display text-2xl text-stone-900 mb-1">Properties</h2>
          <p className="text-sm text-stone-400">Select a property to run a pricing diagnostic</p>
        </div>

        {error && (
          <div className="bg-crisis/5 border border-crisis/20 text-crisis p-4 rounded-lg mb-6 text-sm animate-fade-in flex items-center justify-between" role="alert">
            <span>{error}</span>
            <button onClick={() => setError('')} className="text-crisis/60 hover:text-crisis ml-4">&times;</button>
          </div>
        )}

        {diagLoading && (
          <div className="bg-white border border-positive/20 rounded-xl p-8 mb-6 text-center shadow-card animate-fade-in" role="status" aria-live="polite">
            <div className="inline-block w-8 h-8 border-2 border-positive/30 border-t-positive rounded-full animate-spin mb-4" />
            <p className="text-stone-700 font-medium">{diagStatus}</p>
            <p className="text-xs text-stone-400 mt-2">This typically takes 10-20 seconds</p>
          </div>
        )}

        <div className="grid gap-4">
          {properties.map((prop) => (
            <div key={prop.id} className="bg-white rounded-xl border border-stone-200 p-6 shadow-card hover:shadow-card-hover transition-shadow">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="font-display text-xl text-stone-900">{prop.name}</h3>
                  <div className="flex items-center gap-4 mt-2 flex-wrap">
                    <span className="text-xs text-stone-400 font-medium">{prop.submarket}</span>
                    <span className="text-xs text-stone-300">|</span>
                    <span className="font-mono text-xs text-stone-500">{prop.total_units} units</span>
                    <span className="text-xs text-stone-300">|</span>
                    <span className="text-xs text-stone-400">Built {prop.year_built}</span>
                    <span className="text-xs text-stone-300">|</span>
                    <span className="text-xs text-stone-400">Class {prop.property_class}</span>
                  </div>
                </div>
                <div className="flex gap-2">
                  <button
                    onClick={() => onSelectProperty(prop)}
                    className="px-4 py-2 border border-stone-300 text-stone-700 rounded-lg hover:bg-stone-50 text-sm font-medium transition-colors"
                  >
                    View Details
                  </button>
                  <button
                    onClick={() => handleRunDiagnostic(prop)}
                    disabled={diagLoading}
                    className="px-5 py-2.5 bg-stone-900 text-white rounded-lg hover:bg-stone-800 disabled:opacity-30 text-sm font-semibold transition-all"
                  >
                    Run Diagnostic
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      </main>
    </div>
  );
}
