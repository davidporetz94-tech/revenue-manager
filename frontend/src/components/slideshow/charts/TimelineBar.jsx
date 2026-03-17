import React from 'react';

export default function TimelineBar({ data }) {
  if (!data || !data.length) return null;

  return (
    <div className="flex gap-2 items-stretch">
      {data.map((phase) => (
        <div
          key={phase.phase}
          className="flex-1 rounded-lg p-4 text-white min-h-[100px]"
          style={{ backgroundColor: phase.color }}
        >
          <div className="text-xs font-medium opacity-80">Phase {phase.phase}</div>
          <div className="font-bold text-sm mt-1">{phase.title}</div>
          <div className="text-xs opacity-80 mt-1">Days {phase.days}</div>
          <div className="mt-2 flex gap-2">
            <span className="bg-white/20 rounded px-2 py-0.5 text-xs">
              {phase.actions_count} actions
            </span>
            {phase.experiments_count > 0 && (
              <span className="bg-white/20 rounded px-2 py-0.5 text-xs">
                {phase.experiments_count} experiments
              </span>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}
