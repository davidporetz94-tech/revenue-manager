import React from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts';
import { formatDollar, formatPercent } from '../../../utils/format';
import EmptyState from './EmptyState';

export default function TrendLineChart({ data }) {
  if (!data || !data.length) return <EmptyState message="No trend data available" />;

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
      {data.map((ut) => (
        <div key={ut.unit_type} className="bg-white rounded-lg p-3 shadow-sm">
          <h4 className="text-sm font-medium text-gray-700 mb-2">{ut.unit_type}</h4>
          <ResponsiveContainer width="100%" height={180}>
            <LineChart data={ut.series} margin={{ top: 5, right: 5, left: 5, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="month" tick={{ fontSize: 10 }} />
              <YAxis
                yAxisId="left"
                domain={[0.7, 1.0]}
                tickFormatter={(v) => (v * 100).toFixed(0) + '%'}
                tick={{ fontSize: 10 }}
              />
              <YAxis
                yAxisId="right"
                orientation="right"
                tickFormatter={formatDollar}
                tick={{ fontSize: 10 }}
              />
              <Tooltip
                formatter={(value, name) => {
                  if (name === 'occupancy') return formatPercent(value);
                  return formatDollar(value);
                }}
              />
              <Legend wrapperStyle={{ fontSize: 10 }} />
              <Line yAxisId="left" type="monotone" dataKey="occupancy" stroke="#059669" strokeWidth={2} dot={{ r: 3 }} />
              <Line yAxisId="right" type="monotone" dataKey="asking" stroke="#7C3AED" strokeWidth={2} dot={{ r: 3 }} />
              <Line yAxisId="right" type="monotone" dataKey="comps" stroke="#2563EB" strokeWidth={2} dot={{ r: 3 }} strokeDasharray="5 5" />
              {ut.series?.some(s => s.optimal != null) && (
                <Line yAxisId="right" type="monotone" dataKey="optimal" stroke="#059669" strokeWidth={2} dot={{ r: 2 }} strokeDasharray="3 3" name="optimal" />
              )}
            </LineChart>
          </ResponsiveContainer>
        </div>
      ))}
    </div>
  );
}
