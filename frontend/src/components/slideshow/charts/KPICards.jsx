import React from 'react';
import EmptyState from './EmptyState';

export default function KPICards({ data }) {
  if (!data || !data.length) return <EmptyState message="No KPI data available" />;

  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
      {data.map((card, i) => (
        <div key={i} className="bg-stone-50 rounded-lg p-4 border-l-3" style={{ borderLeftColor: card.color, borderLeftWidth: '3px' }}>
          <p className="text-[11px] text-stone-400 font-medium uppercase tracking-wider">{card.label}</p>
          <p className="font-mono text-xl font-bold mt-1.5" style={{ color: card.color }}>
            {card.value}
          </p>
          {card.trend && card.trend !== 'neutral' && (
            <span className={`text-xs ${card.trend === 'up' ? 'text-crisis' : 'text-healthy'}`}>
              {card.trend === 'up' ? '▲' : '▼'}
            </span>
          )}
        </div>
      ))}
    </div>
  );
}
