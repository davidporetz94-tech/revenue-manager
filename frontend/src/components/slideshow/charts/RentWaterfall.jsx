import React from 'react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from 'recharts';
import { formatDollar } from '../../../utils/format';
import EmptyState from './EmptyState';

export default function RentWaterfall({ data, unitType }) {
  if (!data || !data.length) return <EmptyState message="No rent data available" />;

  const askingItem = data.find(d => d.label === 'Asking');
  const compsItem = data.find(d => d.label === 'Comps');
  const spread = askingItem && compsItem ? askingItem.value - compsItem.value : 0;
  const spreadPct = compsItem?.value > 0 ? ((spread / compsItem.value) * 100).toFixed(1) : '0.0';

  const chartData = data.map(item => ({
    name: item.label.replace(/^\+ /, '').replace(/^= /, ''),
    value: item.value,
    fill: item.color,
  }));

  return (
    <div>
      {unitType && (
        <h4 className="text-xs font-mono text-stone-400 uppercase tracking-wider mb-2">{unitType}</h4>
      )}
      <ResponsiveContainer width="100%" height={200}>
        <BarChart data={chartData} margin={{ top: 10, right: 10, left: 10, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e7e5e4" />
          <XAxis dataKey="name" tick={{ fontSize: 10, fill: '#78716c' }} />
          <YAxis
            domain={['dataMin - 100', 'dataMax + 50']}
            tickFormatter={formatDollar}
            tick={{ fontSize: 10, fill: '#78716c' }}
          />
          <Tooltip
            formatter={(val) => [formatDollar(val), 'Rent']}
            contentStyle={{ fontSize: 12, borderRadius: 8, border: '1px solid #e7e5e4' }}
          />
          <Bar dataKey="value" radius={[3, 3, 0, 0]}>
            {chartData.map((entry, i) => (
              <Cell key={i} fill={entry.fill} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
      {spread !== 0 && (
        <div className="text-center mt-2">
          <span className={`font-mono text-xs font-semibold ${spread > 0 ? 'text-crisis' : 'text-healthy'}`}>
            {spread > 0 ? '+' : ''}{formatDollar(spread)} vs Comps ({spread > 0 ? '+' : ''}{spreadPct}%)
          </span>
        </div>
      )}
    </div>
  );
}
