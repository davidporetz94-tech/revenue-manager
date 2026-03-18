import React, { useState, useEffect } from 'react';
import { AuthProvider, useAuth } from './auth/AuthContext';
import ErrorBoundary from './components/ErrorBoundary';
import LoginPage from './auth/LoginPage';
import PortfolioDashboard from './components/dashboard/PortfolioDashboard';
import PricingReview from './components/dashboard/PricingReview';
import SlideshowViewer from './components/slideshow/SlideshowViewer';
import { getProperties } from './api/client';

function AppContent() {
  const { user, loading } = useAuth();
  const [properties, setProperties] = useState([]);
  const [selectedProperty, setSelectedProperty] = useState(null);
  const [slideDeck, setSlideDeck] = useState(null);
  const [showSlideshow, setShowSlideshow] = useState(false);
  const [propsLoading, setPropsLoading] = useState(true);

  useEffect(() => {
    if (user) {
      getProperties()
        .then(setProperties)
        .catch(() => {})
        .finally(() => setPropsLoading(false));
    }
  }, [user]);

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-stone-50">
        <div className="flex flex-col items-center gap-3">
          <div className="w-8 h-8 border-2 border-stone-300 border-t-stone-700 rounded-full animate-spin" />
          <span className="text-sm text-stone-400 font-medium tracking-wide">Loading</span>
        </div>
      </div>
    );
  }

  if (!user) return <LoginPage />;

  if (showSlideshow && slideDeck) {
    return (
      <SlideshowViewer
        slideDeck={slideDeck}
        propertyName={selectedProperty?.name || 'Portfolio'}
        onExit={() => setShowSlideshow(false)}
      />
    );
  }

  if (selectedProperty) {
    return (
      <PricingReview
        property={selectedProperty}
        onBack={() => { setSelectedProperty(null); setSlideDeck(null); }}
        onShowSlideshow={(deck) => {
          setSlideDeck(deck);
          setShowSlideshow(true);
        }}
      />
    );
  }

  if (propsLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-stone-50">
        <div className="flex flex-col items-center gap-3">
          <div className="w-8 h-8 border-2 border-stone-300 border-t-stone-700 rounded-full animate-spin" />
          <span className="text-sm text-stone-400">Loading portfolio</span>
        </div>
      </div>
    );
  }

  return (
    <PortfolioDashboard
      properties={properties}
      onSelectProperty={setSelectedProperty}
      onShowPortfolioSlideshow={(deck) => {
        setSlideDeck(deck);
        setShowSlideshow(true);
      }}
    />
  );
}

export default function App() {
  return (
    <ErrorBoundary>
      <AuthProvider>
        <AppContent />
      </AuthProvider>
    </ErrorBoundary>
  );
}
