import React from 'react';
import DecisionFlowchart from '../charts/DecisionFlowchart';

export default function DecisionTreeSlide({ slide }) {
  const viz = slide.viz_data || {};
  const narrative = slide.narrative || {};

  return (
    <div className="h-full flex flex-col gap-4 p-2">
      <DecisionFlowchart data={viz.flowcharts} />
      {narrative.explanation && (
        <div className="bg-gray-50 rounded-lg p-4 text-sm text-gray-700 leading-relaxed mt-auto">
          {narrative.explanation}
        </div>
      )}
    </div>
  );
}
