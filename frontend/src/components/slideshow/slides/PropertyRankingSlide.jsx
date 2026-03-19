import React from 'react';
import { formatDollar } from '../../../utils/format';

function efficiencyColor(score) {
  if (score >= 70) return '#059669';
  if (score >= 55) return '#D97706';
  return '#DC2626';
}

function efficiencyLabel(score) {
  if (score >= 85) return 'OPTIMIZED';
  if (score >= 70) return 'OPPORTUNITY';
  if (score >= 55) return 'ADJUSTING';
  if (score >= 40) return 'UNDERPERFORMING';
  return 'NEEDS ATTENTION';
}

export default function PropertyRankingSlide({ slide }) {
  const viz = slide.viz_data || {};
  const narrative = slide.narrative || {};
  const rankings = viz.ranking_cards || [];

  return (
    <div className="h-full flex flex-col gap-4 p-4">
      <h2 className="font-display text-xl text-stone-900">{slide.title}</h2>

      <div className="grid gap-3">
        {rankings.map((r, i) => {
          const name = r.property_name || r.property || `Property ${i + 1}`;
          const score = r.revenue_efficiency || r.score || 0;
          const color = efficiencyColor(score);
          const label = efficiencyLabel(score);
          const gap = r.revenue_gap || 0;
          const vacCost = r.vacancy_cost || r.daily_burn || 0;
          const vacant = r.total_vacant || 0;
          const units = r.total_units || 0;

          return (
            <div key={i} className="bg-white rounded-lg border border-stone-200 p-5 flex items-center justify-between"
              style={{ borderLeftWidth: '4px', borderLeftColor: color }}>
              <div className="flex items-center gap-4">
                <span className="font-mono text-2xl font-bold w-8 text-center" style={{ color }}>{i + 1}</span>
                <div>
                  <span className="font-semibold text-stone-800 text-lg">{name}</span>
                  <span className="text-xs ml-2 px-2 py-0.5 rounded" style={{ backgroundColor: color + '15', color }}>
                    {label}
                  </span>
                  <div className="text-xs text-stone-500 mt-1">{units} units &middot; {vacant} vacant</div>
                </div>
              </div>
              <div className="flex items-center gap-8">
                <div className="text-right">
                  <span className="text-[10px] text-stone-400 uppercase block">Efficiency</span>
                  <span className="font-mono text-lg font-bold" style={{ color }}>{Math.round(score)}</span>
                </div>
                <div className="text-right">
                  <span className="text-[10px] text-stone-400 uppercase block">Rev Gap</span>
                  <span className="font-mono text-sm font-bold text-amber-600">{formatDollar(gap)}/mo</span>
                </div>
                <div className="text-right">
                  <span className="text-[10px] text-stone-400 uppercase block">Vacancy Cost</span>
                  <span className="font-mono text-sm font-bold text-red-600">{formatDollar(vacCost)}/mo</span>
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {narrative.text && (
        <p className="text-sm text-stone-600 mt-2">{narrative.text}</p>
      )}
    </div>
  );
}
