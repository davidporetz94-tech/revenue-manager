import React, { useMemo } from 'react';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell, Legend } from 'recharts';
import { formatDollar } from '../../utils/format';

const LEVER_COLORS = {
  FILL: '#DC2626',
  REPRICE: '#D97706',
  RENEW: '#0D9488',
  DE_CONCESSION: '#7C3AED',
};

const LEVER_LABELS = {
  FILL: 'Fill Vacancy',
  REPRICE: 'Reprice',
  RENEW: 'Renewals',
  DE_CONCESSION: 'De-Concession',
};

export default function RevenueGapBars({ unitTypeData, height = 200 }) {
  const chartData = useMemo(() => {
    if (!unitTypeData) return [];
    return Object.entries(unitTypeData)
      .filter(([, d]) => d.revenueGapComponents)
      .map(([code, d]) => {
        const comps = d.revenueGapComponents;
        return {
          name: code,
          FILL: Math.abs(comps.vacancy_cost?.amount || 0),
          REPRICE: Math.abs(comps.new_lease_underpricing?.amount || 0),
          RENEW: Math.abs((comps.in_place_underpricing?.amount || 0) + (comps.renewal_opportunity?.amount || 0)),
          DE_CONCESSION: Math.abs(comps.concession_drag?.amount || 0),
          total: Math.abs(d.revenueGapMonthly || 0),
        };
      })
      .sort((a, b) => b.total - a.total);
  }, [unitTypeData]);

  if (chartData.length === 0) {
    return (
      <div className="flex items-center justify-center text-xs text-stone-400" style={{ height }}>
        No revenue gap data
      </div>
    );
  }

  const levers = ['FILL', 'REPRICE', 'RENEW', 'DE_CONCESSION'];

  return (
    <div>
      <ResponsiveContainer width="100%" height={height}>
        <BarChart data={chartData} layout="vertical" margin={{ left: 5, right: 30 }}>
          <XAxis type="number" tickFormatter={formatDollar} tick={{ fontSize: 10, fill: '#78716c' }} />
          <YAxis type="category" dataKey="name" tick={{ fontSize: 11, fontWeight: 600, fill: '#57534e' }} width={35} />
          <Tooltip
            formatter={(v, name) => [formatDollar(v), LEVER_LABELS[name] || name]}
            contentStyle={{ fontSize: 12, borderRadius: 8, border: '1px solid #e7e5e4' }}
          />
          {levers.map((lever) => (
            <Bar key={lever} dataKey={lever} stackId="gap" fill={LEVER_COLORS[lever]} radius={0} barSize={22} />
          ))}
        </BarChart>
      </ResponsiveContainer>
      <div className="flex items-center justify-center gap-4 mt-2">
        {levers.map((lever) => (
          <span key={lever} className="flex items-center gap-1.5 text-[10px] text-stone-500">
            <span className="w-2.5 h-2.5 rounded-sm inline-block" style={{ backgroundColor: LEVER_COLORS[lever] }} />
            {LEVER_LABELS[lever]}
          </span>
        ))}
      </div>
    </div>
  );
}
