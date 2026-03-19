import React from 'react';
import TimelineBar from '../charts/TimelineBar';

export default function ActionPlanOverviewSlide({ slide }) {
  const viz = slide.viz_data || {};
  const narrative = slide.narrative || {};
  const hasTimeline = viz.timeline && viz.timeline.length > 0;

  return (
    <div className="h-full flex flex-col gap-4 p-2">
      {hasTimeline ? (
        <TimelineBar data={viz.timeline} />
      ) : (
        <div className="flex items-center justify-center h-32 bg-stone-50 rounded-lg border border-dashed border-stone-200">
          <p className="text-xs text-stone-400 font-medium">
            No action plan phases generated — run with Claude API for detailed recommendations
          </p>
        </div>
      )}
      {(narrative.overview || narrative.text) && (
        <div className="bg-gray-50 rounded-lg p-4 text-sm text-gray-700 leading-relaxed">
          {narrative.overview || narrative.text}
        </div>
      )}
    </div>
  );
}
