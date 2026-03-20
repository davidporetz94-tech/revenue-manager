import React from 'react';

const DIRECTIONS = {
  INCREASE: { arrow: '\u2191', label: 'INCREASE', color: '#059669', bg: '#05966915' },
  DECREASE: { arrow: '\u2193', label: 'DECREASE', color: '#DC2626', bg: '#DC262615' },
  HOLD: { arrow: '\u2192', label: 'HOLD', color: '#6B7280', bg: '#6B728015' },
};

export default function DirectionBadge({ direction, showLabel = true, className = '' }) {
  const d = DIRECTIONS[direction] || DIRECTIONS.HOLD;
  return (
    <span
      className={`inline-flex items-center gap-1 text-[10px] font-bold px-2 py-0.5 rounded ${className}`}
      style={{ backgroundColor: d.bg, color: d.color }}
    >
      <span className="text-xs">{d.arrow}</span>
      {showLabel && d.label}
    </span>
  );
}
