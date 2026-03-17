import React from 'react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from 'recharts';
import { formatDollar } from '../../../utils/format';
import EmptyState from './EmptyState';

export default function VacancyCostBar({ data }) {
  if (!data || !data.length) return <EmptyState message="No vacancy cost data" />;

  return (
    <ResponsiveContainer width="100%" height={250}>
      <BarChart data={data} layout="vertical" margin={{ top: 5, right: 30, left: 60, bottom: 5 }}>
        <CartesianGrid strokeDasharray="3 3" horizontal={false} />
        <XAxis type="number" tickFormatter={formatDollar} tick={{ fontSize: 11 }} />
        <YAxis type="category" dataKey="unit_type" tick={{ fontSize: 12, fontWeight: 600 }} />
        <Tooltip formatter={(val) => formatDollar(val)} labelFormatter={(l) => `Unit Type: ${l}`} />
        <Bar dataKey="vacancy_cost" radius={[0, 4, 4, 0]} barSize={30}>
          {data.map((entry, i) => (
            <Cell key={i} fill={entry.color} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
