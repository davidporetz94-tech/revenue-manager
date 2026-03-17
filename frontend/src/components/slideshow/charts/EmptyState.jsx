import React from 'react';

export default function EmptyState({ message = 'No data available' }) {
  return (
    <div className="flex items-center justify-center h-32 bg-stone-50 rounded-lg border border-dashed border-stone-200">
      <p className="text-xs text-stone-400 font-medium">{message}</p>
    </div>
  );
}
