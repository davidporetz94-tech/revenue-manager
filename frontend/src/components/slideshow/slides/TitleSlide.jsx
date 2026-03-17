import React from 'react';

export default function TitleSlide({ slide }) {
  return (
    <div className="flex flex-col items-center justify-center h-full bg-stone-900 text-white rounded-lg p-12 relative overflow-hidden">
      {/* Subtle grid background */}
      <div className="absolute inset-0 opacity-[0.04]" style={{
        backgroundImage: 'linear-gradient(rgba(255,255,255,.3) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,.3) 1px, transparent 1px)',
        backgroundSize: '60px 60px',
      }} />

      <div className="relative z-10 text-center">
        <div className="text-xs font-mono text-stone-500 tracking-[0.3em] uppercase mb-8">
          Pricing Health Diagnostic
        </div>
        <h1 className="font-display text-3xl lg:text-5xl text-white leading-tight mb-6">
          {slide.title}
        </h1>
        <div className="w-16 h-px bg-positive mx-auto mb-6" />
        <div className="text-stone-400 font-mono text-sm">
          {slide.narrative?.subtitle}
        </div>
      </div>
    </div>
  );
}
