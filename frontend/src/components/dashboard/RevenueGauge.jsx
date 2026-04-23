import React from 'react';
import { gradeColor, gradeLabel } from '../../utils/format';

const ZONES = [
  { max: 35, grade: 'CRISIS' },
  { max: 50, grade: 'DISTRESSED' },
  { max: 65, grade: 'IMBALANCED' },
  { max: 80, grade: 'OPPORTUNITY' },
  { max: 100, grade: 'OPTIMIZED' },
];

function scoreToGrade(score) {
  for (const z of ZONES) {
    if (score < z.max) return z.grade;
  }
  return 'OPTIMIZED';
}

export default function RevenueGauge({ score, grade, size = 200 }) {
  const displayGrade = grade || scoreToGrade(score || 0);
  const displayScore = score ?? 0;
  const color = gradeColor(displayGrade);
  const label = gradeLabel(displayGrade);

  // Circle-based semicircle gauge using stroke-dasharray
  const r = 80;
  const cx = 100;
  const cy = 90;
  const strokeW = 14;
  const circumference = 2 * Math.PI * r;
  const halfCirc = Math.PI * r;

  const clampedScore = Math.max(0, Math.min(100, displayScore));
  const fillLength = (clampedScore / 100) * halfCirc;

  // Zone background segments
  const zoneSegments = ZONES.map((zone, i) => {
    const prevMax = i === 0 ? 0 : ZONES[i - 1].max;
    const segStart = (prevMax / 100) * halfCirc;
    const segLength = ((zone.max - prevMax) / 100) * halfCirc;
    return (
      <circle
        key={zone.grade}
        cx={cx}
        cy={cy}
        r={r}
        fill="none"
        stroke={gradeColor(zone.grade)}
        strokeWidth={strokeW}
        strokeDasharray={`${segLength} ${circumference}`}
        strokeDashoffset={-segStart}
        opacity={0.15}
        transform={`rotate(180 ${cx} ${cy})`}
      />
    );
  });

  // Tick marks at zone boundaries
  const ticks = ZONES.slice(0, -1).map((zone) => {
    const angle = Math.PI - (zone.max / 100) * Math.PI;
    const innerR = r - strokeW / 2 - 2;
    const outerR = r + strokeW / 2 + 2;
    return (
      <line
        key={zone.grade + '-tick'}
        x1={cx + innerR * Math.cos(angle)}
        y1={cy - innerR * Math.sin(angle)}
        x2={cx + outerR * Math.cos(angle)}
        y2={cy - outerR * Math.sin(angle)}
        stroke="#d6d3d1"
        strokeWidth={1.5}
      />
    );
  });

  // Needle dot at score position
  const needleAngle = Math.PI - (clampedScore / 100) * Math.PI;
  const needleX = cx + r * Math.cos(needleAngle);
  const needleY = cy - r * Math.sin(needleAngle);

  // Scale to fit the requested size
  const viewW = 200;
  const viewH = 110;
  const scale = size / viewW;

  return (
    <div className="flex flex-col items-center">
      <svg
        width={size}
        height={viewH * scale}
        viewBox={`0 0 ${viewW} ${viewH}`}
      >
        {/* Zone background segments */}
        {zoneSegments}

        {/* Zone boundary ticks */}
        {ticks}

        {/* Active fill arc */}
        <circle
          cx={cx}
          cy={cy}
          r={r}
          fill="none"
          stroke={color}
          strokeWidth={strokeW}
          strokeDasharray={`${fillLength} ${circumference}`}
          strokeLinecap="round"
          transform={`rotate(180 ${cx} ${cy})`}
          style={{ transition: 'stroke-dasharray 0.6s ease' }}
        />

        {/* Needle dot */}
        <circle
          cx={needleX}
          cy={needleY}
          r={4}
          fill="white"
          stroke={color}
          strokeWidth={2.5}
        />

        {/* End caps — small dots at 0 and 100 positions */}
        <circle cx={cx - r} cy={cy} r={2} fill="#d6d3d1" />
        <circle cx={cx + r} cy={cy} r={2} fill="#d6d3d1" />
      </svg>
      <div className="flex flex-col items-center -mt-1">
        <span className="font-mono text-4xl font-bold" style={{ color }}>{displayScore}</span>
        <span
          className="text-[10px] font-bold uppercase tracking-wider mt-1 px-3 py-0.5 rounded"
          style={{ backgroundColor: color + '15', color }}
        >
          {label}
        </span>
      </div>
    </div>
  );
}
