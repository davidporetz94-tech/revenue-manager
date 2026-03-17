import React from 'react';
import { formatDollar } from '../../../utils/format';

export default function ExperimentDiagram({ data }) {
  if (!data || !data.length) return null;

  return (
    <div className="space-y-4">
      {data.map((exp, i) => (
        <div key={i} className="bg-white rounded-lg shadow p-4 border border-purple-200">
          <h4 className="text-sm font-bold text-purple-700 mb-3">
            {exp.unit_type} Experiment ({exp.window_days}-day observation)
          </h4>
          <div className="flex gap-3 justify-center">
            {exp.arms.map((arm, j) => (
              <div
                key={j}
                className="flex-1 rounded-lg p-3 text-center border-2"
                style={{ borderColor: arm.color, backgroundColor: arm.color + '10' }}
              >
                <div className="text-xs font-medium text-gray-500 uppercase">{arm.label}</div>
                <div className="text-lg font-bold mt-1" style={{ color: arm.color }}>
                  {formatDollar(arm.price)}
                </div>
                <div className="text-xs text-gray-500 mt-1">
                  {arm.units} unit{arm.units !== 1 ? 's' : ''}
                </div>
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
