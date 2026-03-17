import React from 'react';
import TrendLineChart from '../charts/TrendLineChart';

export default function TrendAnalysisSlide({ slide }) {
  const viz = slide.viz_data || {};
  const narrative = slide.narrative || {};

  return (
    <div className="h-full flex flex-col gap-4 p-2">
      <TrendLineChart data={viz.line_charts} />
      {narrative.analysis && (
        <div className="bg-gray-50 rounded-lg p-4 text-sm text-gray-700 leading-relaxed">
          {narrative.analysis}
        </div>
      )}
    </div>
  );
}
