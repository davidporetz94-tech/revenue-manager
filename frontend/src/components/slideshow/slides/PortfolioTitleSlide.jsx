import React from 'react';

export default function PortfolioTitleSlide({ slide }) {
  const narrative = slide.narrative || {};
  return (
    <div className="h-full flex flex-col items-center justify-center text-center gap-6 p-8">
      <div className="w-16 h-16 rounded-xl bg-positive flex items-center justify-center">
        <span className="text-white font-mono font-bold text-2xl">RR</span>
      </div>
      <h1 className="font-display text-4xl text-stone-900">{slide.title}</h1>
      <p className="text-lg text-stone-500 max-w-xl">{narrative.subtitle}</p>
    </div>
  );
}
