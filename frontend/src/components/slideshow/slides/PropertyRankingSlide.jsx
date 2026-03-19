import React from 'react';
import { formatDollar, gradeColor, gradeLabel } from '../../../utils/format';

export default function PropertyRankingSlide({ slide }) {
  const viz = slide.viz_data || {};
  const narrative = slide.narrative || {};
  const rankings = viz.ranking_cards || [];

  return (
    <div className="h-full flex flex-col gap-4 p-4">
      <h2 className="font-display text-xl text-stone-900">{slide.title}</h2>

      <div className="grid gap-3">
        {rankings.map((r, i) => {
          const color = gradeColor(r.grade);
          return (
            <div key={i} className="bg-white rounded-lg border border-stone-200 p-4 flex items-center justify-between"
              style={{ borderLeftWidth: '4px', borderLeftColor: color }}>
              <div className="flex items-center gap-4">
                <span className="font-mono text-2xl font-bold w-8 text-center" style={{ color }}>{i + 1}</span>
                <div>
                  <span className="font-semibold text-stone-800">{r.property}</span>
                  <span className="text-xs ml-2 px-2 py-0.5 rounded" style={{ backgroundColor: color + '15', color }}>
                    {gradeLabel(r.grade)}
                  </span>
                </div>
              </div>
              <div className="flex items-center gap-6">
                <div className="text-right">
                  <span className="text-[10px] text-stone-400 uppercase block">Score</span>
                  <span className="font-mono text-lg font-bold" style={{ color }}>{r.score}</span>
                </div>
                <div className="text-right">
                  <span className="text-[10px] text-stone-400 uppercase block">Daily Cost</span>
                  <span className="font-mono text-sm font-bold text-crisis">{formatDollar(r.daily_burn)}</span>
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
