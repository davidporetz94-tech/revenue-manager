import React from 'react';

const SLIDE_LABELS = [
  'Title', 'Summary', 'Snapshot', 'Prop A', 'Prop B',
  'Trends', 'Revenue', 'Plan', 'Phase 1', 'Day 15',
  'Investigate', 'Next Steps',
];

export default function SlideNavigation({ currentSlide, totalSlides, onNavigate }) {
  return (
    <div className="no-print bg-stone-950 border-t border-stone-800 px-6 py-2.5 flex items-center gap-4">
      <button
        onClick={() => onNavigate(currentSlide - 1)}
        disabled={currentSlide <= 1}
        className="w-8 h-8 rounded-lg bg-stone-800 hover:bg-stone-700 disabled:opacity-20 text-stone-300 text-sm flex items-center justify-center transition-colors"
        aria-label="Previous slide"
      >
        &#8592;
      </button>

      <span className="font-mono text-xs text-stone-500 min-w-[64px] text-center tabular-nums">
        {currentSlide} of {totalSlides}
      </span>

      <button
        onClick={() => onNavigate(currentSlide + 1)}
        disabled={currentSlide >= totalSlides}
        className="w-8 h-8 rounded-lg bg-stone-800 hover:bg-stone-700 disabled:opacity-20 text-stone-300 text-sm flex items-center justify-center transition-colors"
        aria-label="Next slide"
      >
        &#8594;
      </button>

      <div className="flex-1" />

      {/* Thumbnail strip */}
      <div className="hidden lg:flex gap-0.5">
        {SLIDE_LABELS.slice(0, totalSlides).map((label, i) => (
          <button
            key={i}
            onClick={() => onNavigate(i + 1)}
            className={`px-2 py-1 text-[10px] rounded transition-all font-mono ${
              currentSlide === i + 1
                ? 'bg-positive text-white'
                : 'text-stone-600 hover:text-stone-400 hover:bg-stone-800'
            }`}
            title={label}
          >
            {i + 1}
          </button>
        ))}
      </div>
    </div>
  );
}
