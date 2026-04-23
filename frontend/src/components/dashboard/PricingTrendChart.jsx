import React from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine } from 'recharts';
import { formatDollar } from '../../utils/format';

const SERIES_CONFIG = {
  asking: { stroke: '#7C3AED', strokeWidth: 2, dash: null, dot: true, label: 'Asking' },
  comps: { stroke: '#2563EB', strokeWidth: 2, dash: '5 5', dot: true, label: 'Comps' },
  predicted: { stroke: '#78716c', strokeWidth: 1.5, dash: '3 3', dot: false, label: 'Predicted' },
  optimal: { stroke: '#EA580C', strokeWidth: 1.5, dash: '6 3', dot: false, label: 'Optimal' },
  executed: { stroke: '#059669', strokeWidth: 2, dash: null, dot: true, label: 'Executed' },
  inPlace: { stroke: '#0D9488', strokeWidth: 1.5, dash: '2 2', dot: false, label: 'In-Place' },
};

export default function PricingTrendChart({
  data,
  series = ['asking', 'comps'],
  height = 180,
  referenceLines = [],
  xKey = 'm',
}) {
  if (!data || data.length === 0) {
    return (
      <div className={`flex items-center justify-center text-xs text-stone-400`} style={{ height }}>
        No trend data
      </div>
    );
  }

  return (
    <div>
      <ResponsiveContainer width="100%" height={height}>
        <LineChart data={data} margin={{ top: 5, right: 10, left: 5, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e7e5e4" />
          <XAxis dataKey={xKey} tick={{ fontSize: 10, fill: '#78716c' }} />
          <YAxis
            tickFormatter={formatDollar}
            tick={{ fontSize: 10, fill: '#78716c' }}
            domain={['dataMin - 30', 'dataMax + 30']}
          />
          <Tooltip
            formatter={(v, name) => [formatDollar(v), SERIES_CONFIG[name]?.label || name]}
            contentStyle={{ fontSize: 12, borderRadius: 8, border: '1px solid #e7e5e4' }}
          />
          {series.map((key) => {
            const cfg = SERIES_CONFIG[key];
            if (!cfg) return null;
            return (
              <Line
                key={key}
                type="monotone"
                dataKey={key}
                stroke={cfg.stroke}
                strokeWidth={cfg.strokeWidth}
                strokeDasharray={cfg.dash || undefined}
                dot={cfg.dot ? { r: 3 } : false}
                connectNulls
              />
            );
          })}
          {referenceLines.map((ref) => (
            <ReferenceLine
              key={ref.label}
              y={ref.value}
              stroke={ref.color || '#EA580C'}
              strokeDasharray="6 3"
              label={{ value: ref.label, fontSize: 9, fill: ref.color || '#EA580C', position: 'right' }}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
      <div className="flex items-center justify-center gap-4 mt-2">
        {series.map((key) => {
          const cfg = SERIES_CONFIG[key];
          if (!cfg) return null;
          return (
            <span key={key} className="flex items-center gap-1.5 text-[10px] text-stone-500">
              <span
                className="inline-block w-4 h-0.5"
                style={{
                  backgroundColor: cfg.stroke,
                  borderTop: cfg.dash ? `2px dashed ${cfg.stroke}` : undefined,
                  height: cfg.dash ? 0 : 2,
                }}
              />
              {cfg.label}
            </span>
          );
        })}
        {referenceLines.map((ref) => (
          <span key={ref.label} className="flex items-center gap-1.5 text-[10px] text-stone-500">
            <span className="inline-block w-4 h-0 border-t-2 border-dashed" style={{ borderColor: ref.color || '#EA580C' }} />
            {ref.label}
          </span>
        ))}
      </div>
    </div>
  );
}
