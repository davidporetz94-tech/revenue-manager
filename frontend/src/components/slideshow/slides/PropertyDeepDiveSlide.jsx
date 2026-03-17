import React from 'react';
import RentWaterfall from '../charts/RentWaterfall';
import { gradeColor } from '../../../utils/format';

export default function PropertyDeepDiveSlide({ slide }) {
  const viz = slide.viz_data || {};
  const narrative = slide.narrative || {};
  const scoreCards = viz.score_cards || [];

  // Get both waterfalls
  const waterfalls = Object.entries(viz)
    .filter(([key]) => key.startsWith('waterfall_'))
    .map(([key, data]) => ({ key, unitType: key.replace('waterfall_', '').toUpperCase(), data }));

  return (
    <div className="h-full flex flex-col gap-4 p-2">
      {/* Score cards */}
      <div className="flex gap-4">
        {scoreCards.map((card) => (
          <div
            key={card.unit_type}
            className="flex-1 rounded-lg p-4 border-l-4 bg-white shadow-sm"
            style={{ borderLeftColor: gradeColor(card.grade) }}
          >
            <div className="flex items-center justify-between">
              <span className="font-bold text-gray-800">{card.unit_type}</span>
              <span
                className="text-xs font-bold px-2 py-0.5 rounded"
                style={{ backgroundColor: gradeColor(card.grade) + '20', color: gradeColor(card.grade) }}
              >
                {card.grade}
              </span>
            </div>
            <div className="text-2xl font-bold mt-2" style={{ color: gradeColor(card.grade) }}>
              {card.score}
            </div>
            <p className="text-xs text-gray-500 mt-1 line-clamp-2">{card.key_metric}</p>
          </div>
        ))}
      </div>

      {/* Waterfalls */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 flex-1">
        {waterfalls.map(({ key, unitType, data }) => (
          <div key={key} className="bg-white rounded-lg shadow-sm p-3">
            <RentWaterfall data={data} unitType={unitType} />
          </div>
        ))}
      </div>

      {/* Narrative */}
      {narrative.analysis && (
        <div className="bg-gray-50 rounded-lg p-4 text-sm text-gray-700 leading-relaxed">
          {narrative.analysis}
        </div>
      )}
    </div>
  );
}
