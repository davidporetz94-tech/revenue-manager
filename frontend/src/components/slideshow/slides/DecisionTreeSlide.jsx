import React from 'react';
import DecisionFlowchart from '../charts/DecisionFlowchart';

export default function DecisionTreeSlide({ slide }) {
  const viz = slide.viz_data || {};
  const narrative = slide.narrative || {};
  const hasFlowcharts = viz.flowcharts && viz.flowcharts.length > 0;

  return (
    <div className="h-full flex flex-col gap-4 p-2">
      {hasFlowcharts ? (
        <DecisionFlowchart data={viz.flowcharts} />
      ) : (
        <div className="flex items-center justify-center h-32 bg-stone-50 rounded-lg border border-dashed border-stone-200">
          <p className="text-xs text-stone-400 font-medium">
            No decision points generated — run with Claude API for detailed recommendations
          </p>
        </div>
      )}
      {(narrative.explanation || narrative.text) && (
        <div className="bg-gray-50 rounded-lg p-4 text-sm text-gray-700 leading-relaxed mt-auto">
          {narrative.explanation || narrative.text}
        </div>
      )}
    </div>
  );
}
