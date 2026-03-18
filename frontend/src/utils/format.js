export function formatDollar(value) {
  if (value == null) return '$0';
  return '$' + Math.round(value).toLocaleString();
}

export function formatPercent(value) {
  if (value == null) return '0%';
  if (value <= 1) return (value * 100).toFixed(0) + '%';
  return value.toFixed(1) + '%';
}

export function gradeColor(grade) {
  const colors = {
    // Legacy 4-zone
    CRITICAL: '#DC2626',
    ACTION_NEEDED: '#D97706',
    WATCH: '#F59E0B',
    HEALTHY: '#059669',
    // New 5-zone
    CRISIS: '#DC2626',
    DISTRESSED: '#EA580C',
    IMBALANCED: '#D97706',
    OPPORTUNITY: '#0D9488',
    OPTIMIZED: '#059669',
  };
  return colors[grade] || '#6B7280';
}

export function severityColor(severity) {
  const colors = {
    CRITICAL: '#DC2626',
    HIGH: '#D97706',
    MEDIUM: '#F59E0B',
    LOW: '#6B7280',
    POSITIVE: '#0D9488',
    INFO: '#7C3AED',
  };
  return colors[severity] || '#6B7280';
}
