import React from 'react';
import { formatDollar } from '../../utils/format';

function relativeTime(dateStr) {
  const now = new Date();
  const then = new Date(dateStr);
  const diffMs = now - then;
  const diffMin = Math.floor(diffMs / 60000);
  const diffHr = Math.floor(diffMs / 3600000);
  const diffDay = Math.floor(diffMs / 86400000);

  if (diffMin < 1) return 'just now';
  if (diffMin < 60) return `${diffMin}m ago`;
  if (diffHr < 24) return `${diffHr}h ago`;
  if (diffDay === 1) return 'yesterday';
  if (diffDay < 7) return `${diffDay}d ago`;
  return `${Math.floor(diffDay / 7)}w ago`;
}

const DECISION_STYLES = {
  APPROVE: {
    bg: 'bg-emerald-50',
    border: 'border-emerald-200',
    text: 'text-emerald-700',
    label: 'APPROVED',
  },
  HOLD: {
    bg: 'bg-amber-50',
    border: 'border-amber-200',
    text: 'text-amber-700',
    label: 'ON HOLD',
  },
  MODIFY: {
    bg: 'bg-blue-50',
    border: 'border-blue-200',
    text: 'text-blue-700',
    label: 'MODIFIED',
  },
};

export default function DecisionBadge({ decision, decidedAt, approvedValue, decidedByName }) {
  const style = DECISION_STYLES[decision] || DECISION_STYLES.APPROVE;

  return (
    <div className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded border ${style.bg} ${style.border}`}>
      <span className={`text-[10px] font-bold ${style.text}`}>
        {style.label}
        {decision === 'MODIFY' && approvedValue != null && (
          <span className="ml-1 font-mono">{formatDollar(approvedValue)}</span>
        )}
      </span>
      <span className="text-[9px] text-stone-400" title={decidedAt}>
        {relativeTime(decidedAt)}
      </span>
      {decidedByName && (
        <span className="text-[9px] text-stone-400">· {decidedByName}</span>
      )}
    </div>
  );
}
