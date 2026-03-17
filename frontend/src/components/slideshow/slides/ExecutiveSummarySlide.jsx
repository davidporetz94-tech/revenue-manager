import React from 'react';
import ScoreGauge from '../charts/ScoreGauge';
import KPICards from '../charts/KPICards';

export default function ExecutiveSummarySlide({ slide }) {
  const viz = slide.viz_data || {};
  const narrative = slide.narrative || {};

  return (
    <div className="h-full flex flex-col gap-4 p-2">
      <div className="flex flex-col lg:flex-row gap-6 items-start">
        <div className="lg:w-1/3 flex justify-center">
          <ScoreGauge data={viz.score_gauge} />
        </div>
        <div className="lg:w-2/3">
          <p className="text-lg font-semibold text-gray-800 mb-3">
            {narrative.headline}
          </p>
          {narrative.key_findings && (
            <ul className="space-y-2">
              {narrative.key_findings.map((finding, i) => (
                <li key={i} className="flex items-start gap-2">
                  <span className="text-teal-600 font-bold mt-0.5">&#8226;</span>
                  <span className="text-sm text-gray-700">{finding}</span>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
      <div className="mt-auto">
        <KPICards data={viz.kpi_cards} />
      </div>
    </div>
  );
}
