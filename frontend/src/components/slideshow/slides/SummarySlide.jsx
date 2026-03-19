import React from 'react';
import RevenueRoadmapBars from '../charts/RevenueRoadmapBars';

export default function SummarySlide({ slide }) {
  const viz = slide.viz_data || {};
  const narrative = slide.narrative || {};
  const beforeAfter = viz.before_after || [];

  return (
    <div className="h-full flex flex-col gap-6 p-2">
      {(narrative.summary || narrative.text) && (
        <div className="bg-teal-50 rounded-lg p-4 border border-teal-200">
          <p className="text-sm text-teal-800 font-medium leading-relaxed">
            {narrative.summary || narrative.text}
          </p>
        </div>
      )}

      <div className="flex flex-col lg:flex-row gap-6">
        {/* Before/After table */}
        {beforeAfter.length > 0 && (
          <div className={`overflow-auto ${viz.revenue_roadmap ? 'lg:w-1/2' : 'w-full'}`}>
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-gray-100">
                  <th className="px-4 py-2 text-left font-semibold text-gray-700">Metric</th>
                  <th className="px-4 py-2 text-left font-semibold text-gray-700">Current</th>
                  <th className="px-4 py-2 text-left font-semibold text-gray-700">Projected (30d)</th>
                  <th className="px-4 py-2 text-left font-semibold text-gray-700">Improvement</th>
                </tr>
              </thead>
              <tbody>
                {beforeAfter.map((row, i) => (
                  <tr key={i} className="border-b border-gray-100">
                    <td className="px-4 py-3 font-medium text-gray-800">{row.metric}</td>
                    <td className="px-4 py-3 text-gray-600">{row.current}</td>
                    <td className="px-4 py-3 text-gray-600">{row.projected}</td>
                    <td className="px-4 py-3 font-bold" style={{ color: row.color }}>
                      {row.improvement}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Revenue Roadmap */}
        {viz.revenue_roadmap && (
          <div className={`${beforeAfter.length > 0 ? 'lg:w-1/2' : 'w-full'}`}>
            <div className="bg-white rounded-lg shadow-sm p-4">
              <h4 className="text-sm font-medium text-gray-500 mb-3">Revenue Roadmap</h4>
              <RevenueRoadmapBars data={viz.revenue_roadmap} />
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
