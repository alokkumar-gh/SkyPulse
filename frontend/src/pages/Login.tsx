/**
 * SkyPulse Login — Redesign
 * "National Weather Intelligence Access Gate"
 *
 * Design:
 * - Full-viewport editorial layout
 * - Left: brand identity with atmospheric grid texture
 * - Right: minimal authentication form
 * - No marketing gloss — operational, authoritative
 * - DM Serif Display for hero text
 * - Monospace for system stats
 */
import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuthStore } from '../store/authStore';
import { ShieldAlert, User, ShieldCheck, Eye, EyeOff } from 'lucide-react';

// Atmospheric grid background — SkyPulse visual signature
function AtmosphericGrid() {
  return (
    <svg
      style={{
        position: 'absolute',
        inset: 0,
        width: '100%',
        height: '100%',
        opacity: 0.07,
        pointerEvents: 'none',
      }}
      aria-hidden="true"
    >
      <defs>
        <pattern id="grid" width="40" height="40" patternUnits="userSpaceOnUse">
          <path d="M 40 0 L 0 0 0 40" fill="none" stroke="var(--teal)" strokeWidth="0.5" />
        </pattern>
        {/* Concentric circles — radar motif */}
        <radialGradient id="radarGrad" cx="50%" cy="40%" r="50%">
          <stop offset="0%" stopColor="var(--teal)" stopOpacity="0.3" />
          <stop offset="100%" stopColor="var(--teal)" stopOpacity="0" />
        </radialGradient>
      </defs>
      <rect width="100%" height="100%" fill="url(#grid)" />
      {/* Radar circles */}
      <circle cx="50%" cy="40%" r="80" fill="none" stroke="var(--teal)" strokeWidth="0.5" opacity="0.5" />
      <circle cx="50%" cy="40%" r="140" fill="none" stroke="var(--teal)" strokeWidth="0.5" opacity="0.3" />
      <circle cx="50%" cy="40%" r="200" fill="none" stroke="var(--teal)" strokeWidth="0.5" opacity="0.15" />
      {/* Crosshair */}
      <line x1="50%" y1="20%" x2="50%" y2="60%" stroke="var(--teal)" strokeWidth="0.5" opacity="0.4" strokeDasharray="4 4" />
      <line x1="30%" y1="40%" x2="70%" y2="40%" stroke="var(--teal)" strokeWidth="0.5" opacity="0.4" strokeDasharray="4 4" />
    </svg>
  );
}

export const Login: React.FC = () => {
  const navigate = useNavigate();
  const { login, loginAsDemo, error, clearError, loading } = useAuthStore();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPw, setShowPw] = useState(false);
  const [focused, setFocused] = useState<'email' | 'password' | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    clearError();
    const success = await login(email, password);
    if (success) navigate('/');
  };

  const handleDemo = (role: 'CITIZEN' | 'ANALYST' | 'ADMIN') => {
    loginAsDemo(role);
    navigate('/');
  };

  const DEMO_ROLES = [
    {
      role: 'ANALYST' as const,
      icon: <ShieldAlert size={14} />,
      label: 'Analyst',
      color: 'var(--teal)',
      bg: 'var(--teal-100)',
      border: 'var(--border-teal)',
    },
    {
      role: 'ADMIN' as const,
      icon: <ShieldCheck size={14} />,
      label: 'Admin',
      color: 'var(--sev-4)',
      bg: 'var(--sev-4-dim)',
      border: 'rgba(239,68,68,0.2)',
    },
    {
      role: 'CITIZEN' as const,
      icon: <User size={14} />,
      label: 'Citizen',
      color: 'var(--sev-1)',
      bg: 'var(--sev-1-dim)',
      border: 'rgba(34,197,94,0.2)',
    },
  ] as const;

  return (
    <div style={{
      minHeight: '100vh',
      display: 'flex',
      background: 'var(--bg-void)',
    }}>
      {/* ── Left: Brand identity column ──────────────────────────── */}
      <div style={{
        flex: '0 0 460px',
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'space-between',
        padding: '3.5rem 3rem',
        background: 'var(--bg-base)',
        borderRight: '1px solid var(--border-hairline)',
        position: 'relative',
        overflow: 'hidden',
      }}>
        <AtmosphericGrid />

        {/* Top: Brand mark */}
        <div style={{ position: 'relative', zIndex: 1 }}>
          <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: '0.625rem',
            marginBottom: '3.5rem',
          }}>
            {/* Radar icon */}
            <svg width="28" height="28" viewBox="0 0 28 28" fill="none" aria-hidden="true">
              <path d="M14 4 A10 10 0 0 1 24 14" stroke="var(--teal)" strokeWidth="1.5" strokeLinecap="round" opacity="0.4" />
              <path d="M14 7 A7 7 0 0 1 21 14"   stroke="var(--teal)" strokeWidth="1.5" strokeLinecap="round" opacity="0.65" />
              <circle cx="14" cy="14" r="2.5" fill="var(--teal)" />
            </svg>
            <div>
              <div style={{ fontFamily: 'var(--font-sans)', fontWeight: 800, fontSize: '1rem', letterSpacing: '-0.02em', color: 'var(--text-primary)' }}>
                SkyPulse
              </div>
              <div style={{ fontFamily: 'var(--font-mono)', fontSize: 'var(--text-2xs)', color: 'var(--text-muted)', letterSpacing: '0.12em', textTransform: 'uppercase' }}>
                NWI · India
              </div>
            </div>
          </div>

          {/* Editorial headline */}
          <h1 style={{
            fontFamily: 'var(--font-display)',
            fontSize: 'clamp(2rem, 3.5vw, 2.75rem)',
            fontWeight: 400,
            color: 'var(--text-primary)',
            lineHeight: 1.15,
            marginBottom: '1.25rem',
            letterSpacing: '-0.01em',
          }}>
            National<br />
            Weather<br />
            Intelligence
          </h1>

          {/* Teal signal line — brand motif */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '1.25rem' }}>
            <div style={{ width: 40, height: 1, background: 'var(--teal)', opacity: 0.6 }} />
            <span style={{
              fontFamily: 'var(--font-mono)',
              fontSize: 'var(--text-2xs)',
              color: 'var(--teal)',
              letterSpacing: '0.12em',
              textTransform: 'uppercase',
            }}>
              India · Real Time
            </span>
          </div>

          <p style={{
            fontFamily: 'var(--font-sans)',
            fontSize: 'var(--text-sm)',
            color: 'var(--text-secondary)',
            lineHeight: 1.75,
            maxWidth: 300,
          }}>
            Real-time multi-source ingestion, AI-assisted verification,
            and geospatial intelligence across all Indian states.
          </p>
        </div>

        {/* Bottom: System stats */}
        <div style={{ position: 'relative', zIndex: 1 }}>
          {/* Telemetry line */}
          <div style={{ height: 1, background: 'linear-gradient(90deg, var(--teal), transparent)', opacity: 0.2, marginBottom: '1rem' }} />

          {[
            { label: 'Ingestion Sources', value: '36' },
            { label: 'Active Connectors', value: '28' },
            { label: 'AI Verification', value: 'qwen3.8-27b' },
          ].map(({ label, value }) => (
            <div key={label} style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              padding: '0.5rem 0',
              borderBottom: '1px solid var(--border-hairline)',
            }}>
              <span style={{
                fontFamily: 'var(--font-mono)',
                fontSize: 'var(--text-2xs)',
                color: 'var(--text-muted)',
                letterSpacing: '0.06em',
                textTransform: 'uppercase',
              }}>
                {label}
              </span>
              <span style={{
                fontFamily: 'var(--font-mono)',
                fontSize: 'var(--text-xs)',
                fontWeight: 500,
                color: 'var(--text-secondary)',
              }}>
                {value}
              </span>
            </div>
          ))}

          <div style={{ marginTop: '1rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <span className="pulse-live" style={{ width: 6, height: 6 }} />
            <span style={{
              fontFamily: 'var(--font-mono)',
              fontSize: 'var(--text-2xs)',
              color: 'var(--teal)',
              letterSpacing: '0.1em',
              fontWeight: 600,
              textTransform: 'uppercase',
            }}>
              System Operational
            </span>
          </div>
        </div>
      </div>

      {/* ── Right: Authentication form ────────────────────────────── */}
      <div style={{
        flex: 1,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '2rem',
        background: 'var(--bg-base)',
      }}>
        <div style={{ width: '100%', maxWidth: 360, display: 'flex', flexDirection: 'column', gap: '1.75rem' }}>

          {/* Auth header */}
          <div>
            <div style={{
              fontFamily: 'var(--font-mono)',
              fontSize: 'var(--text-2xs)',
              color: 'var(--text-muted)',
              letterSpacing: '0.14em',
              textTransform: 'uppercase',
              marginBottom: '0.5rem',
            }}>
              Access Portal
            </div>
            <h2 style={{
              fontFamily: 'var(--font-sans)',
              fontSize: 'var(--text-2xl)',
              fontWeight: 700,
              color: 'var(--text-primary)',
              letterSpacing: '-0.025em',
            }}>
              Sign in
            </h2>
          </div>

          {/* Error */}
          {error && (
            <div style={{
              padding: '0.625rem 0.875rem',
              borderRadius: 'var(--r-2)',
              background: 'var(--sev-4-dim)',
              border: '1px solid rgba(239,68,68,0.25)',
              color: 'var(--sev-4)',
              fontFamily: 'var(--font-mono)',
              fontSize: 'var(--text-xs)',
              letterSpacing: '0.02em',
            }}>
              {error}
            </div>
          )}

          {/* Form */}
          <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
            {/* Email */}
            <div>
              <label htmlFor="login-email" style={{
                display: 'block',
                marginBottom: '0.4rem',
                fontFamily: 'var(--font-mono)',
                fontSize: 'var(--text-2xs)',
                fontWeight: 500,
                color: 'var(--text-muted)',
                letterSpacing: '0.1em',
                textTransform: 'uppercase',
              }}>
                Email
              </label>
              <input
                id="login-email"
                type="email"
                placeholder="analyst@skypulse.gov.in"
                value={email}
                onChange={(e) => { clearError(); setEmail(e.target.value); }}
                onFocus={() => setFocused('email')}
                onBlur={() => setFocused(null)}
                required
                autoComplete="email"
                style={{
                  width: '100%',
                  background: 'var(--bg-panel)',
                  border: `1px solid ${focused === 'email' ? 'var(--teal)' : 'var(--border-subtle)'}`,
                  borderRadius: 'var(--r-2)',
                  color: 'var(--text-primary)',
                  padding: '0.625rem 0.875rem',
                  fontSize: 'var(--text-sm)',
                  fontFamily: 'var(--font-sans)',
                  outline: 'none',
                  transition: 'border-color var(--t-fast)',
                }}
              />
            </div>

            {/* Password */}
            <div>
              <label htmlFor="login-password" style={{
                display: 'block',
                marginBottom: '0.4rem',
                fontFamily: 'var(--font-mono)',
                fontSize: 'var(--text-2xs)',
                fontWeight: 500,
                color: 'var(--text-muted)',
                letterSpacing: '0.1em',
                textTransform: 'uppercase',
              }}>
                Password
              </label>
              <div style={{ position: 'relative' }}>
                <input
                  id="login-password"
                  type={showPw ? 'text' : 'password'}
                  placeholder="••••••••"
                  value={password}
                  onChange={(e) => { clearError(); setPassword(e.target.value); }}
                  onFocus={() => setFocused('password')}
                  onBlur={() => setFocused(null)}
                  required
                  autoComplete="current-password"
                  style={{
                    width: '100%',
                    background: 'var(--bg-panel)',
                    border: `1px solid ${focused === 'password' ? 'var(--teal)' : 'var(--border-subtle)'}`,
                    borderRadius: 'var(--r-2)',
                    color: 'var(--text-primary)',
                    padding: '0.625rem 2.5rem 0.625rem 0.875rem',
                    fontSize: 'var(--text-sm)',
                    fontFamily: 'var(--font-sans)',
                    outline: 'none',
                    transition: 'border-color var(--t-fast)',
                  }}
                />
                <button
                  type="button"
                  onClick={() => setShowPw((v) => !v)}
                  style={{
                    position: 'absolute',
                    right: '0.75rem',
                    top: '50%',
                    transform: 'translateY(-50%)',
                    color: 'var(--text-muted)',
                    cursor: 'pointer',
                    padding: '0.1rem',
                  }}
                  aria-label={showPw ? 'Hide password' : 'Show password'}
                >
                  {showPw ? <EyeOff size={14} /> : <Eye size={14} />}
                </button>
              </div>
            </div>

            {/* Submit */}
            <button
              id="login-submit"
              type="submit"
              disabled={loading}
              style={{
                width: '100%',
                padding: '0.7rem',
                borderRadius: 'var(--r-2)',
                background: loading ? 'var(--bg-elevated)' : 'var(--teal)',
                border: 'none',
                color: loading ? 'var(--text-muted)' : 'var(--ink)',
                fontFamily: 'var(--font-sans)',
                fontSize: 'var(--text-sm)',
                fontWeight: 700,
                letterSpacing: '-0.01em',
                cursor: loading ? 'not-allowed' : 'pointer',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: '0.4rem',
                marginTop: '0.25rem',
                transition: 'all var(--t-fast)',
                opacity: loading ? 0.7 : 1,
              }}
              onMouseEnter={(e) => {
                if (!loading) (e.currentTarget as HTMLButtonElement).style.background = 'var(--teal-soft)';
              }}
              onMouseLeave={(e) => {
                if (!loading) (e.currentTarget as HTMLButtonElement).style.background = 'var(--teal)';
              }}
            >
              {loading ? (
                <>
                  <span style={{
                    width: 13,
                    height: 13,
                    border: '2px solid rgba(0,0,0,0.2)',
                    borderTopColor: 'var(--ink)',
                    borderRadius: '50%',
                    animation: 'spin 0.7s linear infinite',
                    display: 'inline-block',
                  }} />
                  Authenticating…
                </>
              ) : 'Sign In'}
            </button>
          </form>

          {/* Demo access */}
          <div>
            <div style={{
              display: 'flex',
              alignItems: 'center',
              gap: '0.75rem',
              marginBottom: '0.875rem',
            }}>
              <div style={{ flex: 1, height: 1, background: 'var(--border-hairline)' }} />
              <span style={{
                fontFamily: 'var(--font-mono)',
                fontSize: 'var(--text-2xs)',
                color: 'var(--text-ghost)',
                letterSpacing: '0.1em',
                textTransform: 'uppercase',
              }}>
                Evaluation Access
              </span>
              <div style={{ flex: 1, height: 1, background: 'var(--border-hairline)' }} />
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '0.5rem' }}>
              {DEMO_ROLES.map(({ role, icon, label, color, bg, border }) => (
                <button
                  key={role}
                  id={`demo-login-${role.toLowerCase()}`}
                  type="button"
                  onClick={() => handleDemo(role)}
                  style={{
                    padding: '0.6rem 0.5rem',
                    borderRadius: 'var(--r-2)',
                    background: bg,
                    border: `1px solid ${border}`,
                    color,
                    fontFamily: 'var(--font-mono)',
                    fontSize: 'var(--text-xs)',
                    fontWeight: 600,
                    cursor: 'pointer',
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: 'center',
                    gap: '0.35rem',
                    transition: 'all var(--t-fast)',
                    letterSpacing: '0.04em',
                  }}
                  onMouseEnter={(e) => { (e.currentTarget as HTMLButtonElement).style.opacity = '0.85'; }}
                  onMouseLeave={(e) => { (e.currentTarget as HTMLButtonElement).style.opacity = '1'; }}
                >
                  {icon}
                  {label}
                </button>
              ))}
            </div>

            <p style={{
              textAlign: 'center',
              marginTop: '0.75rem',
              fontFamily: 'var(--font-mono)',
              fontSize: 'var(--text-2xs)',
              color: 'var(--text-ghost)',
              letterSpacing: '0.04em',
              lineHeight: 1.6,
            }}>
              Demo sessions are read-only · No data is modified
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};
