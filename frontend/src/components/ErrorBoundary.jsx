import React from 'react';

export default class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="min-h-screen flex items-center justify-center bg-stone-50 p-8">
          <div className="max-w-md text-center">
            <div className="w-12 h-12 rounded-full bg-crisis/10 flex items-center justify-center mx-auto mb-4">
              <span className="text-crisis text-xl">!</span>
            </div>
            <h2 className="font-display text-xl text-stone-900 mb-2">Something went wrong</h2>
            <p className="text-sm text-stone-500 mb-6">
              {this.state.error?.message || 'An unexpected error occurred.'}
            </p>
            <button
              onClick={() => window.location.reload()}
              className="px-4 py-2 bg-stone-900 text-white rounded-lg text-sm font-medium hover:bg-stone-800 transition-colors"
            >
              Reload Application
            </button>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
