import React from 'react';

export default function ScoreGauge({ data }) {
  if (!data) return null;
  const { score, max, zones } = data;
  const pct = Math.min(score / max, 1);
  const angle = -90 + pct * 180; // -90 to 90 degrees

  const r = 80;
  const cx = 100;
  const cy = 95;

  function arcPath(startPct, endPct) {
    const startAngle = -Math.PI + startPct * Math.PI;
    const endAngle = -Math.PI + endPct * Math.PI;
    const x1 = cx + r * Math.cos(startAngle);
    const y1 = cy + r * Math.sin(startAngle);
    const x2 = cx + r * Math.cos(endAngle);
    const y2 = cy + r * Math.sin(endAngle);
    const large = endPct - startPct > 0.5 ? 1 : 0;
    return `M ${x1} ${y1} A ${r} ${r} 0 ${large} 1 ${x2} ${y2}`;
  }

  const needleAngle = -180 + pct * 180;
  const needleLen = r - 15;
  const nx = cx + needleLen * Math.cos((needleAngle * Math.PI) / 180);
  const ny = cy + needleLen * Math.sin((needleAngle * Math.PI) / 180);

  const currentZone = zones.find(z => score >= z.min && score <= z.max);

  return (
    <div className="flex flex-col items-center">
      <svg viewBox="0 0 200 120" className="w-48 h-auto">
        {zones.map((zone, i) => (
          <path
            key={i}
            d={arcPath(zone.min / max, zone.max / max)}
            fill="none"
            stroke={zone.color}
            strokeWidth="12"
            strokeLinecap="round"
            opacity={0.3}
          />
        ))}
        {currentZone && (
          <path
            d={arcPath(currentZone.min / max, Math.min(score, currentZone.max) / max)}
            fill="none"
            stroke={currentZone.color}
            strokeWidth="12"
            strokeLinecap="round"
          />
        )}
        <line
          x1={cx} y1={cy}
          x2={nx} y2={ny}
          stroke="#111827"
          strokeWidth="2.5"
          strokeLinecap="round"
        />
        <circle cx={cx} cy={cy} r="4" fill="#111827" />
      </svg>
      <div className="text-center -mt-2">
        <span className="text-3xl font-bold" style={{ color: currentZone?.color || '#6B7280' }}>
          {score}
        </span>
        <span className="text-sm text-gray-500 ml-1">/ {max}</span>
      </div>
      {currentZone && (
        <span className="text-sm font-medium mt-1" style={{ color: currentZone.color }}>
          {currentZone.label}
        </span>
      )}
    </div>
  );
}
