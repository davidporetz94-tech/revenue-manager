import React from 'react';
import { formatDollar } from '../../../utils/format';
import EmptyState from './EmptyState';

const TYPE_COLORS = {
  base: '#6B7280',
  addition: '#059669',
  subtraction: '#DC2626',
  total: '#7C3AED',
};

export default function RevenueGapWaterfall({ data }) {
  if (!data?.segments?.length) return <EmptyState message="No revenue gap data" />;

  const segments = data.segments;
  const maxVal = Math.max(...segments.map((s) => Math.abs(s.value)));

  return (
    <div className="space-y-2">
      {segments.map((seg, i) => {
        const pct = maxVal > 0 ? (Math.abs(seg.value) / maxVal) * 100 : 0;
        const color = seg.color || TYPE_COLORS[seg.type] || '#6B7280';
        const isTotal = seg.type === 'total';

        return (
          <div key={i} className="flex items-center gap-3">
            <div className="w-28 text-right">
              <span
                className={`text-xs font-medium ${isTotal ? 'font-bold text-gray-800' : 'text-gray-600'}`}
              >
                {seg.label}
              </span>
            </div>
            <div className="flex-1 h-7 bg-gray-50 rounded overflow-hidden relative">
              <div
                className="h-full rounded transition-all duration-500"
                style={{
                  width: `${Math.max(pct, 4)}%`,
                  backgroundColor: color,
                  opacity: isTotal ? 1 : 0.85,
                }}
              />
            </div>
            <div className="w-24 text-right">
              <span
                className="text-xs font-mono font-semibold"
                style={{ color }}
              >
                {seg.type === 'subtraction' ? '-' : seg.type === 'addition' ? '+' : ''}
                {formatDollar(Math.abs(seg.value))}
              </span>
            </div>
          </div>
        );
      })}
    </div>
  );
}
