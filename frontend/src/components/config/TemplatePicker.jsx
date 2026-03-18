import React, { useState, useEffect } from 'react';
import { getConfigTemplates, applyTemplate, previewDiagnosis } from '../../api/client';

export default function TemplatePicker({ propertyId, onTemplateApplied }) {
  const [templates, setTemplates] = useState([]);
  const [loading, setLoading] = useState(true);
  const [previewing, setPreviewing] = useState(null);
  const [previewResults, setPreviewResults] = useState({});
  const [applying, setApplying] = useState(null);

  useEffect(() => {
    getConfigTemplates()
      .then(setTemplates)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  async function handlePreview(template) {
    setPreviewing(template.id);
    try {
      // Build a config object from template key_values for preview
      const res = await getConfigTemplates();
      const full = res.find(t => t.id === template.id);
      // Use the preview endpoint with template config
      const preview = await previewDiagnosis(propertyId, template.key_values);
      setPreviewResults(prev => ({ ...prev, [template.id]: preview }));
    } catch { /* silent */ }
    setPreviewing(null);
  }

  async function handleApply(templateId) {
    setApplying(templateId);
    try {
      await applyTemplate(propertyId, templateId);
      if (onTemplateApplied) onTemplateApplied();
    } catch { /* silent */ }
    setApplying(null);
  }

  if (loading) {
    return (
      <div className="flex items-center gap-2 py-4 text-sm text-stone-400">
        <div className="w-4 h-4 border-2 border-stone-300 border-t-stone-600 rounded-full animate-spin" />
        Loading templates...
      </div>
    );
  }

  if (templates.length === 0) return null;

  return (
    <div className="mb-6">
      <h3 className="text-xs font-semibold text-stone-500 uppercase tracking-wider mb-2">
        Start from a template, then customize
      </h3>
      <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-4 gap-3">
        {templates.map((t) => (
          <div key={t.id} className="bg-white border border-stone-200 rounded-xl p-4 shadow-card hover:shadow-card-hover transition-shadow">
            <h4 className="font-semibold text-sm text-stone-800 mb-1">{t.name}</h4>
            <p className="text-xs text-stone-500 mb-3 leading-relaxed">{t.description}</p>

            <div className="space-y-1 mb-3">
              {Object.entries(t.key_values).map(([k, v]) => (
                <div key={k} className="flex justify-between text-xs">
                  <span className="text-stone-400">{k.replace(/_/g, ' ')}</span>
                  <span className="font-mono font-semibold text-stone-700">
                    {typeof v === 'number' && v < 1 ? `${(v * 100).toFixed(0)}%` : v}
                  </span>
                </div>
              ))}
            </div>

            {previewResults[t.id] && (
              <div className="bg-stone-50 rounded-lg p-2 mb-3">
                <span className="text-[10px] text-stone-400 uppercase tracking-wider font-semibold">Flag Preview</span>
                <div className="flex gap-2 mt-1">
                  {Object.entries(previewResults[t.id]).map(([code, data]) => (
                    <div key={code} className="text-xs">
                      <span className="font-mono font-bold text-stone-600">{code}:</span>
                      <span className="ml-1 font-mono" style={{
                        color: data.flag_count >= 10 ? '#DC2626' : data.flag_count >= 5 ? '#D97706' : '#059669'
                      }}>{data.flag_count}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            <div className="flex gap-2">
              <button
                onClick={() => handlePreview(t)}
                disabled={previewing === t.id}
                className="flex-1 px-3 py-1.5 border border-stone-200 text-stone-600 rounded-lg text-xs font-medium hover:bg-stone-50 disabled:opacity-50 transition-colors"
              >
                {previewing === t.id ? 'Previewing...' : 'Preview'}
              </button>
              <button
                onClick={() => handleApply(t.id)}
                disabled={applying === t.id}
                className="flex-1 px-3 py-1.5 bg-stone-800 text-white rounded-lg text-xs font-medium hover:bg-stone-700 disabled:opacity-50 transition-colors"
              >
                {applying === t.id ? 'Applying...' : 'Apply'}
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
