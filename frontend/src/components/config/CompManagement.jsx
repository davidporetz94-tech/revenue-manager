import React, { useState, useEffect } from 'react';
import { getComps, refreshComps } from '../../api/client';
import { formatDollar } from '../../utils/format';

export default function CompManagement({ propertyId }) {
  const [comps, setComps] = useState([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [message, setMessage] = useState('');

  useEffect(() => {
    loadComps();
  }, [propertyId]);

  async function loadComps() {
    try {
      const data = await getComps(propertyId);
      setComps(data);
    } catch {
      setMessage('Failed to load comps');
    }
    setLoading(false);
  }

  async function handleRefresh() {
    setRefreshing(true);
    try {
      const result = await refreshComps();
      setMessage(result.message);
      await loadComps();
      setTimeout(() => setMessage(''), 3000);
    } catch {
      setMessage('Refresh failed');
    }
    setRefreshing(false);
  }

  if (loading) return <div className="text-stone-400 text-sm py-8 text-center">Loading comps...</div>;

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="font-display text-xl text-stone-900">Comp Set</h2>
          <p className="text-xs text-stone-400 mt-1">{comps.length} competitive properties tracked</p>
        </div>
        <button
          onClick={handleRefresh}
          disabled={refreshing}
          className="px-4 py-2 border border-stone-300 text-stone-700 rounded-lg text-sm font-medium hover:bg-stone-50 disabled:opacity-40 transition-colors"
        >
          {refreshing ? 'Refreshing...' : 'Refresh Rents'}
        </button>
      </div>

      {message && (
        <div className="bg-positive/5 border border-positive/20 text-positive p-3 rounded-lg mb-4 text-sm animate-fade-in">
          {message}
        </div>
      )}

      <div className="space-y-3">
        {comps.map((comp) => (
          <div key={comp.id} className="bg-white rounded-xl border border-stone-200 p-5 shadow-card">
            <div className="flex items-start justify-between">
              <div>
                <h3 className="font-semibold text-stone-800">{comp.name}</h3>
                <div className="flex items-center gap-3 mt-1 text-xs text-stone-400">
                  <span>{comp.total_units} units</span>
                  <span className="text-stone-300">|</span>
                  <span>Built {comp.year_built}</span>
                  <span className="text-stone-300">|</span>
                  <span>Class {comp.property_class}</span>
                  <span className="text-stone-300">|</span>
                  <span>{comp.distance_miles} mi</span>
                </div>
              </div>
              {comp.last_refreshed_at && (
                <span className="text-[10px] text-stone-400 font-mono">
                  Updated {new Date(comp.last_refreshed_at).toLocaleDateString()}
                </span>
              )}
            </div>

            {comp.unit_types && comp.unit_types.length > 0 && (
              <div className="mt-3 flex gap-4">
                {comp.unit_types.map((ut) => (
                  <div key={ut.id} className="bg-stone-50 rounded-lg px-3 py-2">
                    <span className="text-[10px] text-stone-400 uppercase tracking-wider">
                      {ut.bed}BR/{ut.bath}BA
                    </span>
                    <span className="font-mono text-sm font-bold text-stone-800 block">
                      {ut.latest_rent ? formatDollar(ut.latest_rent) : '—'}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
