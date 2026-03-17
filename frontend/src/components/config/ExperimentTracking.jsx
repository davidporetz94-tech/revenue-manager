import React, { useState, useEffect } from 'react';
import { getExperiments, approveExperiment, cancelExperiment } from '../../api/client';
import { formatDollar } from '../../utils/format';

const STATUS_COLORS = {
  PROPOSED: { bg: 'bg-experiment/10', text: 'text-experiment', border: 'border-experiment/20' },
  APPROVED: { bg: 'bg-positive/10', text: 'text-positive', border: 'border-positive/20' },
  ACTIVE: { bg: 'bg-healthy/10', text: 'text-healthy', border: 'border-healthy/20' },
  CONVERGED: { bg: 'bg-stone-100', text: 'text-stone-600', border: 'border-stone-200' },
  CANCELLED: { bg: 'bg-stone-100', text: 'text-stone-400', border: 'border-stone-200' },
};

export default function ExperimentTracking({ propertyId }) {
  const [experiments, setExperiments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [message, setMessage] = useState('');

  useEffect(() => {
    loadExperiments();
  }, [propertyId]);

  async function loadExperiments() {
    try {
      const data = await getExperiments(propertyId);
      setExperiments(data);
    } catch {
      setMessage('Failed to load experiments');
    }
    setLoading(false);
  }

  async function handleApprove(id) {
    try {
      await approveExperiment(id);
      setMessage('Experiment approved');
      await loadExperiments();
      setTimeout(() => setMessage(''), 3000);
    } catch (err) {
      setMessage(err.response?.data?.detail || 'Approval failed');
    }
  }

  async function handleCancel(id) {
    if (!window.confirm('Cancel this experiment?')) return;
    try {
      await cancelExperiment(id);
      setMessage('Experiment cancelled');
      await loadExperiments();
      setTimeout(() => setMessage(''), 3000);
    } catch (err) {
      setMessage(err.response?.data?.detail || 'Cancellation failed');
    }
  }

  if (loading) return <div className="text-stone-400 text-sm py-8 text-center">Loading experiments...</div>;

  return (
    <div>
      <div className="mb-6">
        <h2 className="font-display text-xl text-stone-900">Experiments</h2>
        <p className="text-xs text-stone-400 mt-1">
          {experiments.length} experiment{experiments.length !== 1 ? 's' : ''} tracked
        </p>
      </div>

      {message && (
        <div className="bg-positive/5 border border-positive/20 text-positive p-3 rounded-lg mb-4 text-sm animate-fade-in">
          {message}
        </div>
      )}

      {experiments.length === 0 ? (
        <div className="bg-white rounded-xl border border-stone-200 p-12 text-center shadow-card">
          <p className="text-stone-400 text-sm">No experiments yet. Run a diagnostic to generate experiment proposals.</p>
        </div>
      ) : (
        <div className="space-y-4">
          {experiments.map((exp) => {
            const design = exp.experiment_design || {};
            const arms = design.arms || [];
            const colors = STATUS_COLORS[exp.status] || STATUS_COLORS.PROPOSED;

            return (
              <div key={exp.id} className="bg-white rounded-xl border border-stone-200 p-5 shadow-card">
                <div className="flex items-center justify-between mb-4">
                  <div className="flex items-center gap-3">
                    <span className={`text-[10px] font-bold uppercase tracking-wider px-2.5 py-1 rounded-full border ${colors.bg} ${colors.text} ${colors.border}`}>
                      {exp.status}
                    </span>
                    <span className="text-xs text-stone-400 font-mono">
                      {exp.created_at ? new Date(exp.created_at).toLocaleDateString() : ''}
                    </span>
                  </div>
                  <div className="flex gap-2">
                    {exp.status === 'PROPOSED' && (
                      <>
                        <button
                          onClick={() => handleApprove(exp.id)}
                          className="px-3 py-1.5 bg-positive text-white rounded-lg text-xs font-semibold hover:bg-positive/90 transition-colors"
                        >
                          Approve
                        </button>
                        <button
                          onClick={() => handleCancel(exp.id)}
                          className="px-3 py-1.5 border border-stone-300 text-stone-500 rounded-lg text-xs font-medium hover:bg-stone-50 transition-colors"
                        >
                          Cancel
                        </button>
                      </>
                    )}
                    {exp.status === 'APPROVED' && (
                      <button
                        onClick={() => handleCancel(exp.id)}
                        className="px-3 py-1.5 border border-stone-300 text-stone-500 rounded-lg text-xs font-medium hover:bg-stone-50 transition-colors"
                      >
                        Cancel
                      </button>
                    )}
                  </div>
                </div>

                {/* Experiment arms */}
                {arms.length > 0 && (
                  <div className="flex gap-3">
                    {arms.map((arm, i) => (
                      <div key={i} className="flex-1 bg-stone-50 rounded-lg p-3 text-center border border-stone-100">
                        <span className="text-[10px] text-stone-400 uppercase tracking-wider font-medium">
                          {arm.label}
                        </span>
                        <span className="font-mono text-lg font-bold text-stone-800 block mt-1">
                          {formatDollar(arm.price)}
                        </span>
                        <span className="text-[10px] text-stone-400">
                          {arm.units_allocated} unit{arm.units_allocated !== 1 ? 's' : ''}
                        </span>
                      </div>
                    ))}
                  </div>
                )}

                {/* Assignments */}
                {exp.assignments && exp.assignments.length > 0 && (
                  <div className="mt-3 border-t border-stone-100 pt-3">
                    <span className="text-[10px] text-stone-400 uppercase tracking-wider font-medium">Unit Assignments</span>
                    <div className="mt-2 space-y-1">
                      {exp.assignments.map((a) => (
                        <div key={a.id} className="flex items-center justify-between text-xs">
                          <span className="font-mono text-stone-600">{a.arm_label}</span>
                          <span className="font-mono text-stone-500">{formatDollar(a.assigned_price)}</span>
                          <span className={a.leased ? 'text-healthy font-semibold' : 'text-stone-400'}>
                            {a.leased ? 'Leased' : 'Active'}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
