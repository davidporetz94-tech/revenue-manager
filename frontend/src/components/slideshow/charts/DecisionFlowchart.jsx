import React from 'react';

export default function DecisionFlowchart({ data }) {
  if (!data || !data.length) return null;

  return (
    <div className="space-y-4">
      {data.map((tree, i) => (
        <div key={i} className="bg-white rounded-lg shadow p-4">
          <h4 className="text-sm font-bold text-gray-700 mb-3">{tree.condition}</h4>
          <div className="space-y-2">
            {tree.outcomes.map((outcome, j) => (
              <div key={j} className="flex items-start gap-3">
                <div
                  className="w-3 h-3 rounded-full mt-1 flex-shrink-0"
                  style={{ backgroundColor: outcome.color }}
                />
                <div className="flex-1">
                  <span className="text-sm font-medium text-gray-600">{outcome.label}</span>
                  <span className="text-sm text-gray-500 ml-2">{outcome.action}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
