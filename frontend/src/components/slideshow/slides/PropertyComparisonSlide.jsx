import React from 'react';
import { formatDollar, formatPercent } from '../../../utils/format';

export default function PropertyComparisonSlide({ slide }) {
  const viz = slide.viz_data || {};
  const narrative = slide.narrative || {};
  const table = viz.comparison_table || { rows: [] };

  return (
    <div className="h-full flex flex-col gap-4 p-4">
      <h2 className="font-display text-xl text-stone-900">{slide.title}</h2>

      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-stone-200">
              <th className="text-left py-2 px-3 text-xs font-semibold text-stone-500 uppercase">Property</th>
              <th className="text-right py-2 px-3 text-xs font-semibold text-stone-500 uppercase">Units</th>
              <th className="text-right py-2 px-3 text-xs font-semibold text-stone-500 uppercase">Occupancy</th>
              <th className="text-right py-2 px-3 text-xs font-semibold text-stone-500 uppercase">Vacant</th>
              <th className="text-right py-2 px-3 text-xs font-semibold text-stone-500 uppercase">Daily Cost</th>
              <th className="text-right py-2 px-3 text-xs font-semibold text-stone-500 uppercase">Monthly Cost</th>
              <th className="text-right py-2 px-3 text-xs font-semibold text-stone-500 uppercase">Rev Gap</th>
              <th className="text-right py-2 px-3 text-xs font-semibold text-stone-500 uppercase">Efficiency</th>
            </tr>
          </thead>
          <tbody>
            {table.rows.map((row, i) => (
              <tr key={i} className="border-b border-stone-100">
                <td className="py-3 px-3 font-semibold text-stone-800">{row.property}</td>
                <td className="py-3 px-3 text-right font-mono text-stone-600">{row.total_units}</td>
                <td className="py-3 px-3 text-right font-mono" style={{ color: row.occupancy >= 0.90 ? '#059669' : row.occupancy >= 0.85 ? '#D97706' : '#DC2626' }}>
                  {formatPercent(row.occupancy)}
                </td>
                <td className="py-3 px-3 text-right font-mono text-stone-600">{row.vacant}</td>
                <td className="py-3 px-3 text-right font-mono text-crisis">{formatDollar(row.daily_burn)}</td>
                <td className="py-3 px-3 text-right font-mono text-stone-600">{formatDollar(row.monthly_cost)}</td>
                <td className="py-3 px-3 text-right font-mono" style={{ color: row.revenue_gap > 5000 ? '#DC2626' : row.revenue_gap > 2000 ? '#D97706' : '#059669' }}>
                  {formatDollar(row.revenue_gap || 0)}/mo
                </td>
                <td className="py-3 px-3 text-right font-mono" style={{ color: row.revenue_efficiency >= 70 ? '#059669' : row.revenue_efficiency >= 55 ? '#D97706' : '#DC2626' }}>
                  {Math.round(row.revenue_efficiency || 0)}%
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {narrative.text && (
        <p className="text-sm text-stone-600 mt-2">{narrative.text}</p>
      )}
    </div>
  );
}
