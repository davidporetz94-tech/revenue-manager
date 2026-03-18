import React from 'react';
import EmptyState from './EmptyState';

export default function DimensionBreakdownChart({ data }) {
  if (!data?.dimensions?.length) return <EmptyState message="No dimension data" />;

  const dimensions = data.dimensions;
  const totalWeighted = dimensions.reduce((sum, d) => sum + (d.score * d.weight), 0);

  return (
    <div className="space-y-3">
      {/* Stacked bar */}
      <div className="flex h-8 rounded-lg overflow-hidden shadow-sm">
        {dimensions.map((dim, i) => {
          const widthPct = dim.weight * 100;
          return (
            <div
              key={i}
              className="flex items-center justify-center transition-all duration-300"
              style={{
                width: `${widthPct}%`,
                backgroundColor: dim.color || '#6B7280',
                minWidth: '40px',
              }}
              title={`${dim.name}: ${dim.score} (${Math.round(dim.weight * 100)}%)`}
            >
              <span className="text-[10px] font-bold text-white truncate px-1">
                {dim.score}
              </span>
            </div>
          );
        })}
      </div>

      {/* Legend */}
      <div className="flex flex-wrap gap-x-4 gap-y-1">
        {dimensions.map((dim, i) => (
          <div key={i} className="flex items-center gap-1.5">
            <div
              className="w-2.5 h-2.5 rounded-sm"
              style={{ backgroundColor: dim.color || '#6B7280' }}
            />
            <span className="text-xs text-gray-600">
              {dim.name}
              <span className="text-gray-400 ml-1">
                {dim.score} ({Math.round(dim.weight * 100)}%)
              </span>
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
