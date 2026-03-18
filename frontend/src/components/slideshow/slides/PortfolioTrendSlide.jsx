import React from 'react';
import { LineChart, Line, ResponsiveContainer } from 'recharts';
import { formatPercent } from '../../../utils/format';

const COLORS = ['#7C3AED', '#2563EB', '#DC2626', '#059669', '#D97706', '#F59E0B'];

export default function PortfolioTrendSlide({ slide }) {
  const viz = slide.viz_data || {};
  const narrative = slide.narrative || {};
  const unitTrends = viz.unit_type_trends || {};

  return (
    <div className="h-full flex flex-col gap-4 p-4">
      <h2 className="font-display text-xl text-stone-900">{slide.title}</h2>

      <div className="grid grid-cols-2 gap-4 flex-1">
        {Object.entries(unitTrends).map(([code, trend], i) => (
          <div key={code} className="bg-stone-50 rounded-lg p-3">
            <div className="flex items-center justify-between mb-2">
              <span className="font-mono text-xs font-bold text-stone-700">{code}</span>
              {trend.length > 0 && (
                <span className="font-mono text-xs" style={{ color: COLORS[i % COLORS.length] }}>
                  {formatPercent(trend[trend.length - 1])}
                </span>
              )}
            </div>
            <ResponsiveContainer width="100%" height={80}>
              <LineChart data={trend.map((v, j) => ({ i: j, occ: v }))}>
                <Line type="monotone" dataKey="occ" stroke={COLORS[i % COLORS.length]} strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        ))}
      </div>

      {narrative.text && (
        <p className="text-sm text-stone-600 mt-2">{narrative.text}</p>
      )}
    </div>
  );
}
