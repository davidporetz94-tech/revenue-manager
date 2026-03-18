import React from 'react';
import RevenueGapWaterfall from '../charts/RevenueGapWaterfall';
import { formatDollar } from '../../../utils/format';

export default function RevenueAtRiskSlide({ slide }) {
  const viz = slide.viz_data || {};
  const narrative = slide.narrative || {};
  const burn = viz.daily_burn || {};

  return (
    <div className="h-full flex flex-col gap-4 p-2">
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="bg-red-50 rounded-lg p-4 text-center border border-red-200">
          <p className="text-sm text-red-600 font-medium">Daily Burn Rate</p>
          <p className="text-3xl font-bold text-red-700 mt-1">{formatDollar(burn.daily_amount)}</p>
          <p className="text-xs text-red-500 mt-1">per day</p>
        </div>
        <div className="bg-red-50 rounded-lg p-4 text-center border border-red-200">
          <p className="text-sm text-red-600 font-medium">Monthly Cost</p>
          <p className="text-3xl font-bold text-red-700 mt-1">{formatDollar(burn.monthly_amount)}</p>
          <p className="text-xs text-red-500 mt-1">per month</p>
        </div>
        <div className="bg-red-50 rounded-lg p-4 text-center border border-red-200">
          <p className="text-sm text-red-600 font-medium">Annual Impact</p>
          <p className="text-3xl font-bold text-red-700 mt-1">{formatDollar(burn.annual_amount)}</p>
          <p className="text-xs text-red-500 mt-1">projected annual</p>
        </div>
      </div>

      <div className="flex-1 bg-white rounded-lg shadow-sm p-4">
        <h4 className="text-sm font-medium text-gray-500 mb-2">Revenue Gap Decomposition</h4>
        <RevenueGapWaterfall data={viz.revenue_gap_waterfall} />
      </div>

      {narrative.analysis && (
        <div className="bg-gray-50 rounded-lg p-4 text-sm text-gray-700 leading-relaxed">
          {narrative.analysis}
        </div>
      )}
    </div>
  );
}
