import React from 'react';
import TimelineBar from '../charts/TimelineBar';

export default function ActionPlanOverviewSlide({ slide }) {
  const viz = slide.viz_data || {};
  const narrative = slide.narrative || {};

  return (
    <div className="h-full flex flex-col gap-4 p-2">
      <TimelineBar data={viz.timeline} />
      {narrative.overview && (
        <div className="bg-gray-50 rounded-lg p-4 text-sm text-gray-700 leading-relaxed">
          {narrative.overview}
        </div>
      )}
    </div>
  );
}
