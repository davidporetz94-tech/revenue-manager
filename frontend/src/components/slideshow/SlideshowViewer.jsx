import React, { useState, useEffect, useCallback, Component } from 'react';
import SlideNavigation from './SlideNavigation';
import TitleSlide from './slides/TitleSlide';
import ExecutiveSummarySlide from './slides/ExecutiveSummarySlide';
import PortfolioSnapshotSlide from './slides/PortfolioSnapshotSlide';
import PropertyDeepDiveSlide from './slides/PropertyDeepDiveSlide';
import TrendAnalysisSlide from './slides/TrendAnalysisSlide';
import RevenueAtRiskSlide from './slides/RevenueAtRiskSlide';
import ActionPlanOverviewSlide from './slides/ActionPlanOverviewSlide';
import PhaseDetailSlide from './slides/PhaseDetailSlide';
import DecisionTreeSlide from './slides/DecisionTreeSlide';
import InvestigationSlide from './slides/InvestigationSlide';
import SummarySlide from './slides/SummarySlide';
import PortfolioTitleSlide from './slides/PortfolioTitleSlide';
import PropertyComparisonSlide from './slides/PropertyComparisonSlide';
import PropertyRankingSlide from './slides/PropertyRankingSlide';
import PortfolioTrendSlide from './slides/PortfolioTrendSlide';

const SLIDE_COMPONENTS = {
  TITLE: TitleSlide,
  EXECUTIVE_SUMMARY: ExecutiveSummarySlide,
  DATA_TABLE: PortfolioSnapshotSlide,
  PROPERTY_DEEP_DIVE: PropertyDeepDiveSlide,
  TREND_ANALYSIS: TrendAnalysisSlide,
  REVENUE_AT_RISK: RevenueAtRiskSlide,
  ACTION_PLAN_OVERVIEW: ActionPlanOverviewSlide,
  PHASE_DETAIL: PhaseDetailSlide,
  DECISION_TREE: DecisionTreeSlide,
  INVESTIGATION: InvestigationSlide,
  SUMMARY: SummarySlide,
  PORTFOLIO_TITLE: PortfolioTitleSlide,
  PORTFOLIO_EXECUTIVE_SUMMARY: ExecutiveSummarySlide,
  PORTFOLIO_SNAPSHOT: PropertyComparisonSlide,
  PROPERTY_RANKING: PropertyRankingSlide,
  PORTFOLIO_TRENDS: PortfolioTrendSlide,
  PORTFOLIO_REVENUE_AT_RISK: RevenueAtRiskSlide,
  PORTFOLIO_ACTION_PLAN: ActionPlanOverviewSlide,
  PORTFOLIO_PHASE_DETAIL: PhaseDetailSlide,
  PORTFOLIO_DECISION_POINT: DecisionTreeSlide,
  PORTFOLIO_INVESTIGATION: InvestigationSlide,
  PORTFOLIO_SUMMARY: SummarySlide,
};

export default function SlideshowViewer({ slideDeck, propertyName, onExit }) {
  const [currentSlide, setCurrentSlide] = useState(1);
  const [transitioning, setTransitioning] = useState(false);
  const slides = slideDeck?.slides || [];
  const totalSlides = slides.length;

  const navigate = useCallback((n) => {
    if (n >= 1 && n <= totalSlides && n !== currentSlide) {
      setTransitioning(true);
      setTimeout(() => {
        setCurrentSlide(n);
        setTransitioning(false);
      }, 150);
    }
  }, [totalSlides, currentSlide]);

  useEffect(() => {
    function handleKeyDown(e) {
      if (e.key === 'ArrowRight' || e.key === 'ArrowDown') {
        e.preventDefault();
        navigate(currentSlide + 1);
      } else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') {
        e.preventDefault();
        navigate(currentSlide - 1);
      } else if (e.key === 'Escape') {
        onExit?.();
      }
    }
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [currentSlide, navigate, onExit]);

  if (!slides.length) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-stone-900">
        <p className="text-stone-500">No slides available</p>
      </div>
    );
  }

  const slide = slides[currentSlide - 1];
  const SlideComponent = SLIDE_COMPONENTS[slide?.slide_type] || FallbackSlide;

  return (
    <div className="min-h-screen bg-stone-900 flex flex-col">
      {/* Header */}
      <div className="no-print bg-stone-950 border-b border-stone-800 px-6 py-2.5 flex items-center justify-between">
        <div className="flex items-center gap-4">
          <button
            onClick={onExit}
            className="text-stone-500 hover:text-stone-300 text-xs font-medium tracking-wide transition-colors flex items-center gap-1.5"
            aria-label="Exit slideshow"
          >
            <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" />
            </svg>
            EXIT
          </button>
          <div className="w-px h-4 bg-stone-800" />
          <span className="font-display text-sm text-stone-300">{propertyName}</span>
          {slideDeck?.metadata?.narrative_fallback && (
            <span className="text-[10px] bg-caution/20 text-caution px-2 py-0.5 rounded font-mono">
              FALLBACK
            </span>
          )}
        </div>
        <div className="font-mono text-xs text-stone-500">
          {currentSlide} / {totalSlides}
        </div>
      </div>

      {/* Slide canvas */}
      <div className="flex-1 flex items-center justify-center p-4 lg:p-8">
        <div
          className={`slide-container bg-white rounded-xl shadow-slide w-full max-w-5xl overflow-hidden transition-all duration-150 ${
            transitioning ? 'opacity-0 scale-[0.99]' : 'opacity-100 scale-100'
          }`}
          style={{ minHeight: '540px' }}
        >
          {slide.slide_type !== 'TITLE' && slide.slide_type !== 'PORTFOLIO_TITLE' && (
            <div className="border-b border-stone-100 px-8 py-4 flex items-center justify-between">
              <h3 className="font-display text-lg text-stone-900">{slide.title}</h3>
              <span className="font-mono text-[10px] text-stone-300 uppercase tracking-widest">
                Slide {currentSlide}
              </span>
            </div>
          )}

          <div className="p-8" style={{ minHeight: (slide.slide_type === 'TITLE' || slide.slide_type === 'PORTFOLIO_TITLE') ? '540px' : '460px' }}>
            <SlideErrorBoundary slideType={slide.slide_type}>
              <SlideComponent slide={slide} />
            </SlideErrorBoundary>
          </div>
        </div>
      </div>

      {/* Navigation */}
      <SlideNavigation
        currentSlide={currentSlide}
        totalSlides={totalSlides}
        onNavigate={navigate}
      />
    </div>
  );
}

class SlideErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError() {
    return { hasError: true };
  }

  componentDidCatch(error, errorInfo) {
    console.error(`Slide render error (${this.props.slideType}):`, error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="flex items-center justify-center h-full text-center">
          <div>
            <p className="text-stone-400 text-sm mb-2">Slide failed to render</p>
            <p className="text-stone-500 text-xs">{this.props.slideType}</p>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}

function FallbackSlide({ slide }) {
  return (
    <div className="flex items-center justify-center h-full text-center">
      <div>
        <p className="text-stone-400 text-sm mb-4">Slide type: {slide.slide_type}</p>
        {slide.narrative && typeof slide.narrative === 'object' && (
          <div className="text-sm text-stone-600 text-left max-w-lg mx-auto space-y-2">
            {Object.entries(slide.narrative).map(([key, val]) => (
              <p key={key}>{typeof val === 'string' ? val : ''}</p>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
