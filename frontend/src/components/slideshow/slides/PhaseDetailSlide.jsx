import React from 'react';
import ExperimentDiagram from '../charts/ExperimentDiagram';
import { formatDollar } from '../../../utils/format';

export default function PhaseDetailSlide({ slide }) {
  const viz = slide.viz_data || {};
  const narrative = slide.narrative || {};
  const cards = viz.action_cards || [];

  const urgencyColors = {
    CRITICAL: 'border-red-500 bg-red-50',
    HIGH: 'border-amber-500 bg-amber-50',
  };

  return (
    <div className="h-full flex flex-col gap-4 p-2">
      {/* Action Cards 2x2 grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
        {cards.map((card, i) => (
          <div
            key={i}
            className={`rounded-lg p-4 border-l-4 shadow-sm ${urgencyColors[card.urgency] || 'border-gray-300 bg-white'}`}
            style={{ borderLeftColor: card.border_color }}
          >
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-bold text-gray-500">{card.unit_type}</span>
              <span className="text-xs px-2 py-0.5 rounded bg-gray-200 text-gray-600">
                {card.action_type.replace(/_/g, ' ')}
              </span>
            </div>
            <p className="text-sm font-medium text-gray-800">{card.title}</p>
            {card.target !== 'N/A' && (
              <p className="text-xs text-gray-500 mt-1">Target: {card.target}</p>
            )}
          </div>
        ))}
      </div>

      {/* Experiment Diagrams */}
      {viz.experiment_diagrams && viz.experiment_diagrams.length > 0 && (
        <ExperimentDiagram data={viz.experiment_diagrams} />
      )}

      {narrative.detail && (
        <div className="bg-gray-50 rounded-lg p-4 text-sm text-gray-700 leading-relaxed mt-auto">
          {narrative.detail}
        </div>
      )}
    </div>
  );
}
