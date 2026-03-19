import React, { useState } from 'react';
import { formatDollar } from '../../utils/format';

export default function DecisionButtons({ recommendedValue, onApprove, onHold, onModify, loading }) {
  const [mode, setMode] = useState(null); // null | 'hold' | 'modify'
  const [reason, setReason] = useState('');
  const [modifyValue, setModifyValue] = useState(recommendedValue || 0);

  if (loading) {
    return (
      <div className="flex items-center gap-2">
        <div className="w-4 h-4 border-2 border-stone-300 border-t-stone-600 rounded-full animate-spin" />
        <span className="text-xs text-stone-400">Saving...</span>
      </div>
    );
  }

  if (mode === 'hold') {
    return (
      <div className="flex items-center gap-2">
        <input
          type="text"
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          placeholder="Reason for hold..."
          className="text-xs border border-stone-300 rounded px-2 py-1 w-40 focus:outline-none focus:ring-1 focus:ring-amber-400"
          autoFocus
          onKeyDown={(e) => {
            if (e.key === 'Enter' && reason.trim()) onHold(reason.trim());
            if (e.key === 'Escape') setMode(null);
          }}
        />
        <button
          onClick={() => reason.trim() && onHold(reason.trim())}
          disabled={!reason.trim()}
          className="text-[10px] font-bold px-2 py-1 rounded bg-amber-500 text-white hover:bg-amber-600 disabled:opacity-40 transition-colors"
        >
          Confirm
        </button>
        <button
          onClick={() => { setMode(null); setReason(''); }}
          className="text-[10px] text-stone-400 hover:text-stone-600"
        >
          Cancel
        </button>
      </div>
    );
  }

  if (mode === 'modify') {
    return (
      <div className="flex items-center gap-2">
        <span className="text-[10px] text-stone-400">$</span>
        <input
          type="number"
          value={modifyValue}
          onChange={(e) => setModifyValue(Number(e.target.value))}
          className="text-xs font-mono border border-stone-300 rounded px-2 py-1 w-24 focus:outline-none focus:ring-1 focus:ring-blue-400"
          autoFocus
          onKeyDown={(e) => {
            if (e.key === 'Enter') onModify(modifyValue);
            if (e.key === 'Escape') setMode(null);
          }}
        />
        <button
          onClick={() => onModify(modifyValue)}
          className="text-[10px] font-bold px-2 py-1 rounded bg-blue-500 text-white hover:bg-blue-600 transition-colors"
        >
          Set
        </button>
        <button
          onClick={() => { setMode(null); setModifyValue(recommendedValue || 0); }}
          className="text-[10px] text-stone-400 hover:text-stone-600"
        >
          Cancel
        </button>
      </div>
    );
  }

  return (
    <div className="flex items-center gap-1.5">
      <button
        onClick={onApprove}
        className="text-[10px] font-bold px-2.5 py-1 rounded bg-emerald-50 text-emerald-700 hover:bg-emerald-100 border border-emerald-200 transition-colors"
        title="Approve recommendation"
      >
        Approve
      </button>
      <button
        onClick={() => setMode('hold')}
        className="text-[10px] font-bold px-2.5 py-1 rounded bg-amber-50 text-amber-700 hover:bg-amber-100 border border-amber-200 transition-colors"
        title="Put on hold with reason"
      >
        Hold
      </button>
      <button
        onClick={() => setMode('modify')}
        className="text-[10px] font-bold px-2.5 py-1 rounded bg-blue-50 text-blue-700 hover:bg-blue-100 border border-blue-200 transition-colors"
        title="Modify to custom amount"
      >
        Modify
      </button>
    </div>
  );
}
