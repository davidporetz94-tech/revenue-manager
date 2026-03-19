import React from 'react';

export default function InvestigationSlide({ slide }) {
  const viz = slide.viz_data || {};
  const narrative = slide.narrative || {};
  const items = viz.investigation_table || [];

  return (
    <div className="h-full flex flex-col gap-4 p-2">
      {(narrative.overview || narrative.text) && (
        <p className="text-sm text-gray-700">{narrative.overview || narrative.text}</p>
      )}
      {items.length > 0 ? (
        <div className="overflow-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-gray-100">
                <th className="px-4 py-2 text-left font-semibold text-gray-700">Area</th>
                <th className="px-4 py-2 text-left font-semibold text-gray-700">Key Questions</th>
                <th className="px-4 py-2 text-left font-semibold text-gray-700">Data Needed</th>
                <th className="px-4 py-2 text-left font-semibold text-gray-700">Deadline</th>
              </tr>
            </thead>
            <tbody>
              {items.map((item, i) => (
                <tr key={i} className="border-b border-gray-100">
                  <td className="px-4 py-3 font-medium text-gray-800">{item.area}</td>
                  <td className="px-4 py-3 text-gray-600">
                    {item.questions?.map((q, j) => <p key={j}>{q}</p>)}
                  </td>
                  <td className="px-4 py-3 text-gray-600">{item.data_needed}</td>
                  <td className="px-4 py-3 text-gray-500">{item.deadline}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="flex items-center justify-center h-32 bg-stone-50 rounded-lg border border-dashed border-stone-200">
          <p className="text-xs text-stone-400 font-medium">
            No investigation items generated — run with Claude API for detailed recommendations
          </p>
        </div>
      )}
    </div>
  );
}
