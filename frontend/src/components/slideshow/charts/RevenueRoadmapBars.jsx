import React from 'react';
import { formatDollar } from '../../../utils/format';
import EmptyState from './EmptyState';

export default function RevenueRoadmapBars({ data }) {
  if (!data) return <EmptyState message="No roadmap data" />;

  const { current_monthly, projected_monthly, levers } = data;
  if (current_monthly == null || projected_monthly == null) {
    return <EmptyState message="No roadmap data" />;
  }

  const maxVal = Math.max(current_monthly, projected_monthly);
  const currentPct = maxVal > 0 ? (current_monthly / maxVal) * 100 : 0;
  const projectedPct = maxVal > 0 ? (projected_monthly / maxVal) * 100 : 0;
  const delta = projected_monthly - current_monthly;

  return (
    <div className="space-y-4">
      {/* Before/After bars */}
      <div className="space-y-3">
        <div>
          <div className="flex items-center justify-between mb-1">
            <span className="text-xs font-medium text-gray-500">Current Monthly</span>
            <span className="text-sm font-mono font-bold text-gray-700">
              {formatDollar(current_monthly)}
            </span>
          </div>
          <div className="h-6 bg-gray-100 rounded overflow-hidden">
            <div
              className="h-full bg-gray-400 rounded transition-all duration-500"
              style={{ width: `${Math.max(currentPct, 4)}%` }}
            />
          </div>
        </div>

        <div>
          <div className="flex items-center justify-between mb-1">
            <span className="text-xs font-medium text-gray-500">Projected Monthly</span>
            <span className="text-sm font-mono font-bold text-teal-700">
              {formatDollar(projected_monthly)}
            </span>
          </div>
          <div className="h-6 bg-gray-100 rounded overflow-hidden">
            <div
              className="h-full bg-teal-500 rounded transition-all duration-500"
              style={{ width: `${Math.max(projectedPct, 4)}%` }}
            />
          </div>
        </div>

        {delta !== 0 && (
          <div className="text-center">
            <span className={`text-sm font-mono font-bold ${delta > 0 ? 'text-teal-600' : 'text-red-600'}`}>
              {delta > 0 ? '+' : ''}{formatDollar(delta)}/mo
            </span>
            <span className="text-xs text-gray-400 ml-2">
              ({delta > 0 ? '+' : ''}{maxVal > 0 ? ((delta / current_monthly) * 100).toFixed(1) : '0.0'}%)
            </span>
          </div>
        )}
      </div>

      {/* Lever breakdown */}
      {levers?.length > 0 && (
        <div className="border-t border-gray-100 pt-3">
          <h5 className="text-[11px] font-medium text-gray-400 uppercase tracking-wider mb-2">
            Revenue Levers
          </h5>
          <div className="space-y-1.5">
            {levers.map((lever, i) => (
              <div key={i} className="flex items-center justify-between">
                <span className="text-xs text-gray-600">{lever.label}</span>
                <span
                  className={`text-xs font-mono font-semibold ${
                    lever.amount >= 0 ? 'text-teal-600' : 'text-red-600'
                  }`}
                >
                  {lever.amount >= 0 ? '+' : ''}{formatDollar(lever.amount)}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
