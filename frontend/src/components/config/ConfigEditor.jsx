import React, { useState, useEffect } from 'react';
import { getConfig, saveConfig, previewDiagnosis } from '../../api/client';
import TemplatePicker from './TemplatePicker';

const SECTIONS = [
  { key: 'occupancy_thresholds', label: 'Occupancy Thresholds', fields: [
    { key: 'target_occupancy', label: 'Target Occupancy', min: 0.85, max: 0.98, step: 0.01, format: 'pct' },
    { key: 'push_pricing_above', label: 'Push Pricing Above', min: 0.90, max: 0.99, step: 0.01, format: 'pct' },
    { key: 'concern_below', label: 'Concern Below', min: 0.85, max: 0.95, step: 0.01, format: 'pct' },
    { key: 'action_below', label: 'Action Below', min: 0.80, max: 0.92, step: 0.01, format: 'pct' },
    { key: 'crisis_below', label: 'Crisis Below', min: 0.70, max: 0.85, step: 0.01, format: 'pct' },
  ]},
  { key: 'exposure_thresholds', label: 'Exposure Thresholds', fields: [
    { key: 'green_below', label: 'Green Below', min: 0.02, max: 0.10, step: 0.01, format: 'pct' },
    { key: 'caution_below', label: 'Caution Below', min: 0.05, max: 0.15, step: 0.01, format: 'pct' },
    { key: 'action_below', label: 'Action Below', min: 0.10, max: 0.25, step: 0.01, format: 'pct' },
    { key: 'crisis_above', label: 'Crisis Above', min: 0.15, max: 0.35, step: 0.01, format: 'pct' },
  ]},
  { key: 'pricing_tolerance', label: 'Pricing Tolerance', fields: [
    { key: 'max_premium_vs_comps_pct', label: 'Max Premium vs Comps', min: 0.02, max: 0.15, step: 0.01, format: 'pct' },
    { key: 'max_asking_vs_predicted_pct', label: 'Max Asking vs Predicted', min: 0.02, max: 0.10, step: 0.01, format: 'pct' },
    { key: 'acceptable_days_on_market', label: 'Acceptable DOM', min: 14, max: 45, step: 1, format: 'days' },
  ]},
  { key: 'experiment_policy', label: 'Experiment Policy', fields: [
    { key: 'min_vacant_for_experiment', label: 'Min Vacant Units', min: 2, max: 6, step: 1, format: 'num' },
    { key: 'min_occupancy_for_experiment', label: 'Min Occupancy', min: 0.70, max: 0.85, step: 0.01, format: 'pct' },
    { key: 'max_price_spread_pct', label: 'Max Price Spread', min: 0.03, max: 0.10, step: 0.01, format: 'pct' },
    { key: 'observation_window_days', label: 'Observation Window', min: 7, max: 30, step: 1, format: 'days' },
  ]},
];

export default function ConfigEditor({ propertyId }) {
  const [config, setConfig] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [preview, setPreview] = useState(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [message, setMessage] = useState('');

  useEffect(() => {
    loadConfig();
  }, [propertyId]);

  async function loadConfig() {
    try {
      const data = await getConfig(propertyId);
      setConfig(data);
    } catch {
      setMessage('Failed to load config');
    }
    setLoading(false);
  }

  function updateField(section, field, value) {
    setConfig(prev => ({
      ...prev,
      [section]: { ...prev[section], [field]: Number(value) },
    }));
    setPreview(null);
  }

  async function handlePreview() {
    setPreviewLoading(true);
    try {
      const result = await previewDiagnosis(propertyId, config);
      setPreview(result);
    } catch {
      setMessage('Preview failed');
    }
    setPreviewLoading(false);
  }

  async function handleSave() {
    setSaving(true);
    try {
      await saveConfig(propertyId, config);
      setMessage('Config saved successfully');
      setTimeout(() => setMessage(''), 3000);
    } catch {
      setMessage('Save failed');
    }
    setSaving(false);
  }

  if (loading) return <div className="text-stone-400 text-sm py-8 text-center">Loading config...</div>;
  if (!config) return <div className="text-stone-400 text-sm py-8 text-center">No config found</div>;

  return (
    <div>
      <TemplatePicker propertyId={propertyId} onTemplateApplied={loadConfig} />
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="font-display text-xl text-stone-900">Configuration</h2>
          <p className="text-xs text-stone-400 mt-1">Version {config.version} — {config.investment_thesis} / {config.risk_profile}</p>
        </div>
        <div className="flex gap-3">
          <button
            onClick={handlePreview}
            disabled={previewLoading}
            className="px-4 py-2 border border-stone-300 text-stone-700 rounded-lg text-sm font-medium hover:bg-stone-50 disabled:opacity-40 transition-colors"
          >
            {previewLoading ? 'Computing...' : 'Preview Diagnosis'}
          </button>
          <button
            onClick={handleSave}
            disabled={saving}
            className="px-4 py-2 bg-stone-900 text-white rounded-lg text-sm font-semibold hover:bg-stone-800 disabled:opacity-40 transition-colors"
          >
            {saving ? 'Saving...' : 'Save & Activate'}
          </button>
        </div>
      </div>

      {message && (
        <div className="bg-positive/5 border border-positive/20 text-positive p-3 rounded-lg mb-4 text-sm animate-fade-in">
          {message}
        </div>
      )}

      {/* Preview results */}
      {preview && (
        <div className="bg-white rounded-xl border border-experiment/20 p-4 mb-6 shadow-card animate-fade-in">
          <h3 className="text-sm font-semibold text-experiment mb-3">Flag Preview</h3>
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
            {Object.entries(preview).map(([code, data]) => (
              <div key={code} className="bg-stone-50 rounded-lg p-3">
                <span className="font-mono text-sm font-bold text-stone-800">{code}</span>
                <span className="font-mono text-2xl font-bold block mt-1" style={{
                  color: data.flag_count >= 10 ? '#DC2626' : data.flag_count >= 5 ? '#D97706' : '#059669'
                }}>
                  {data.flag_count}
                </span>
                <span className="text-[10px] text-stone-400">flags</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Config sections */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {SECTIONS.map((section) => (
          <div key={section.key} className="bg-white rounded-xl border border-stone-200 p-5 shadow-card">
            <h3 className="text-sm font-semibold text-stone-700 mb-4">{section.label}</h3>
            <div className="space-y-4">
              {section.fields.map((field) => {
                const value = config[section.key]?.[field.key] ?? field.min;
                return (
                  <div key={field.key}>
                    <div className="flex items-center justify-between mb-1">
                      <label htmlFor={`${section.key}-${field.key}`} className="text-xs text-stone-500">
                        {field.label}
                      </label>
                      <span className="font-mono text-xs font-semibold text-stone-700">
                        {field.format === 'pct' ? `${(value * 100).toFixed(0)}%` :
                         field.format === 'days' ? `${value} days` : value}
                      </span>
                    </div>
                    <input
                      id={`${section.key}-${field.key}`}
                      type="range"
                      min={field.min}
                      max={field.max}
                      step={field.step}
                      value={value}
                      onChange={(e) => updateField(section.key, field.key, e.target.value)}
                      className="w-full h-1.5 bg-stone-200 rounded-lg appearance-none cursor-pointer accent-positive"
                    />
                  </div>
                );
              })}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
