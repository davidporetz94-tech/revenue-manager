import React, { useState } from 'react';
import { useAuth } from './AuthContext';

export default function LoginPage() {
  const { login } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e) {
    e.preventDefault();
    setLoading(true);
    setError('');
    const result = await login(email, password);
    if (!result.success) {
      setError(result.error);
    }
    setLoading(false);
  }

  return (
    <div className="min-h-screen flex bg-stone-50">
      {/* Left panel — branding */}
      <div className="hidden lg:flex lg:w-2/5 bg-stone-900 flex-col justify-between p-12 relative overflow-hidden">
        {/* Subtle grid texture */}
        <div className="absolute inset-0 opacity-[0.03]" style={{
          backgroundImage: 'linear-gradient(rgba(255,255,255,.1) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,.1) 1px, transparent 1px)',
          backgroundSize: '40px 40px',
        }} />

        <div className="relative z-10">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded bg-positive flex items-center justify-center">
              <span className="text-white font-mono font-bold text-sm">RM</span>
            </div>
            <span className="text-stone-400 text-sm font-medium tracking-wider uppercase">Revenue Management</span>
          </div>
        </div>

        <div className="relative z-10">
          <h1 className="font-display text-4xl text-white leading-tight mb-4">
            Pricing Health<br />Diagnostic Platform
          </h1>
          <p className="text-stone-400 text-sm leading-relaxed max-w-sm">
            AI-powered rent optimization for multifamily portfolios.
            Analyze pricing, identify revenue leaks, and generate
            actionable 30-day plans.
          </p>
        </div>

        <div className="relative z-10 flex gap-6 text-stone-500 text-xs">
          <span>Deterministic Metrics</span>
          <span className="text-stone-700">|</span>
          <span>AI Diagnosis</span>
          <span className="text-stone-700">|</span>
          <span>MAB Experiments</span>
        </div>
      </div>

      {/* Right panel — login form */}
      <div className="flex-1 flex items-center justify-center p-8">
        <div className="w-full max-w-sm">
          {/* Mobile brand mark */}
          <div className="lg:hidden flex items-center gap-3 mb-8">
            <div className="w-8 h-8 rounded bg-positive flex items-center justify-center">
              <span className="text-white font-mono font-bold text-sm">RM</span>
            </div>
            <span className="text-stone-500 text-sm font-medium tracking-wider uppercase">Revenue Management</span>
          </div>

          <h2 className="font-display text-2xl text-stone-900 mb-1">Sign in</h2>
          <p className="text-stone-400 text-sm mb-8">Enter your credentials to access the platform</p>

          <form onSubmit={handleSubmit} className="space-y-5">
            <div>
              <label htmlFor="email" className="block text-xs font-semibold text-stone-500 uppercase tracking-wider mb-2">
                Email
              </label>
              <input
                id="email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@company.com"
                className="w-full px-3 py-2.5 bg-white border border-stone-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-positive/40 focus:border-positive transition-colors"
                required
                autoComplete="email"
              />
            </div>
            <div>
              <label htmlFor="password" className="block text-xs font-semibold text-stone-500 uppercase tracking-wider mb-2">
                Password
              </label>
              <input
                id="password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Enter password"
                className="w-full px-3 py-2.5 bg-white border border-stone-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-positive/40 focus:border-positive transition-colors"
                required
                autoComplete="current-password"
              />
            </div>

            {error && (
              <div className="text-crisis text-sm bg-crisis/5 border border-crisis/20 p-3 rounded-lg animate-fade-in" role="alert">
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full py-2.5 bg-stone-900 text-white rounded-lg text-sm font-semibold hover:bg-stone-800 disabled:opacity-40 transition-all"
            >
              {loading ? (
                <span className="flex items-center justify-center gap-2">
                  <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  Signing in
                </span>
              ) : 'Sign In'}
            </button>
          </form>

          <p className="text-center text-xs text-stone-400 mt-8">
            Demo: demo@example.com / demo123
          </p>
        </div>
      </div>
    </div>
  );
}
