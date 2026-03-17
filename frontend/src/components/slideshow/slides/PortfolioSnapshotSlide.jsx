import React from 'react';
import { formatDollar, formatPercent } from '../../../utils/format';

export default function PortfolioSnapshotSlide({ slide }) {
  const table = slide.viz_data?.data_table;
  if (!table) return <div className="p-8 text-gray-500">No data available</div>;

  const { columns, rows, highlights } = table;

  function getHighlight(rowIdx, colKey) {
    return highlights?.find(h => h.row === rowIdx && h.col === colKey);
  }

  function formatCell(value, format) {
    if (value == null) return '-';
    if (format === 'currency') return formatDollar(value);
    if (format === 'percent') return formatPercent(value);
    return String(value);
  }

  return (
    <div className="h-full overflow-auto p-2">
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-gray-100">
              {columns.map((col) => (
                <th key={col.key} className="px-3 py-2 text-left font-semibold text-gray-700 whitespace-nowrap">
                  {col.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, rowIdx) => (
              <tr key={rowIdx} className="border-b border-gray-100 hover:bg-gray-50">
                {columns.map((col) => {
                  const hl = getHighlight(rowIdx, col.key);
                  return (
                    <td
                      key={col.key}
                      className="px-3 py-2 whitespace-nowrap"
                      style={hl ? { color: hl.color, fontWeight: 700 } : {}}
                    >
                      {formatCell(row[col.key], col.format)}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
