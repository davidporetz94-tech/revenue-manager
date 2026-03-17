import React, { useState } from 'react';
import { AuthProvider, useAuth } from './auth/AuthContext';
import ErrorBoundary from './components/ErrorBoundary';
import LoginPage from './auth/LoginPage';
import PropertyList from './components/dashboard/PropertyList';
import PropertyDetail from './components/dashboard/PropertyDetail';
import SlideshowViewer from './components/slideshow/SlideshowViewer';

function AppContent() {
  const { user, loading } = useAuth();
  const [selectedProperty, setSelectedProperty] = useState(null);
  const [slideDeck, setSlideDeck] = useState(null);
  const [showSlideshow, setShowSlideshow] = useState(false);

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
        propertyName={selectedProperty?.name || 'Property'}
        onExit={() => { setShowSlideshow(false); setSlideDeck(null); }}
      />
    );
  }

  if (selectedProperty) {
    return (
      <PropertyDetail
        property={selectedProperty}
        onBack={() => setSelectedProperty(null)}
        onDiagnosticComplete={(deck) => {
          setSlideDeck(deck);
          setShowSlideshow(true);
        }}
      />
    );
  }

  return (
    <PropertyList
      onSelectProperty={setSelectedProperty}
      onDiagnosticComplete={(deck) => {
        setSlideDeck(deck);
        setShowSlideshow(true);
      }}
      selectedProperty={selectedProperty}
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
