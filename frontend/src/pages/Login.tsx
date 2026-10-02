/**
 * Login Page — Phase 7
 * Handles user authentication with JWT token storage.
 * Includes quick demo login shortcuts for:
 * - Analyst Role
 * - Admin Role
 * - Citizen Role
 */
import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, Button, Input } from '../components/ui/Primitives';
import { useAuthStore } from '../store/authStore';
import { Radio, ShieldAlert, User, ShieldCheck } from 'lucide-react';

export const Login: React.FC = () => {
  const navigate = useNavigate();
  const { login, loginAsDemo, error, clearError, loading } = useAuthStore();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    clearError();
    const success = await login(email, password);
    if (success) {
      navigate('/dashboard');
    }
  };

  const handleDemoLogin = (role: 'CITIZEN' | 'ANALYST' | 'ADMIN') => {
    loginAsDemo(role);
    navigate('/dashboard');
  };

  return (
    <div
      style={{
        minHeight: 'calc(100vh - var(--topbar-height, 56px))',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '1.5rem',
      }}
    >
      <div style={{ width: '100%', maxWidth: '420px', display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
        {/* Brand header */}
        <div style={{ textAlign: 'center' }}>
          <div
            style={{
              width: 48,
              height: 48,
              borderRadius: 'var(--radius-lg)',
              backgroundColor: 'var(--brand-blue)',
              display: 'inline-flex',
              alignItems: 'center',
              justifyContent: 'center',
              marginBottom: '1rem',
              boxShadow: '0 0 16px var(--brand-blue-glow)',
            }}
          >
            <Radio size={28} color="#fff" />
          </div>
          <h2 style={{ margin: 0, fontSize: 'var(--text-xl)', fontWeight: 700, color: 'var(--text-primary)' }}>
            Sign in to SkyPulse
          </h2>
          <p style={{ margin: '0.25rem 0 0 0', fontSize: 'var(--text-sm)', color: 'var(--text-secondary)' }}>
            National Weather Intelligence Platform
          </p>
        </div>

        {error && (
          <div
            style={{
              padding: '0.75rem',
              borderRadius: 'var(--radius-md)',
              backgroundColor: 'rgba(239, 68, 68, 0.15)',
              border: '1px solid rgba(239, 68, 68, 0.3)',
              color: 'var(--severity-4)',
              fontSize: 'var(--text-xs)',
              textAlign: 'center',
            }}
          >
            {error}
          </div>
        )}

        <Card>
          <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
            <Input
              label="Email Address"
              type="email"
              placeholder="analyst@skypulse.gov.in"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />

            <Input
              label="Password"
              type="password"
              placeholder="••••••••"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />

            <Button type="submit" variant="primary" loading={loading} style={{ width: '100%', marginTop: '0.5rem' }}>
              Sign In
            </Button>
          </form>

          {/* Quick Demo Access Buttons */}
          <div style={{ marginTop: '1.5rem', borderTop: '1px solid var(--bg-border)', paddingTop: '1.25rem' }}>
            <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-muted)', textAlign: 'center', marginBottom: '0.75rem' }}>
              FAST EVALUATION: QUICK LOGIN AS
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '0.5rem' }}>
              <button
                type="button"
                onClick={() => handleDemoLogin('ANALYST')}
                style={{
                  padding: '0.5rem',
                  borderRadius: 'var(--radius-md)',
                  backgroundColor: 'rgba(59, 130, 246, 0.12)',
                  border: '1px solid rgba(59, 130, 246, 0.3)',
                  color: 'var(--brand-blue)',
                  fontSize: 'var(--text-xs)',
                  fontWeight: 600,
                  cursor: 'pointer',
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  gap: '0.25rem',
                }}
              >
                <ShieldAlert size={16} />
                Analyst
              </button>

              <button
                type="button"
                onClick={() => handleDemoLogin('ADMIN')}
                style={{
                  padding: '0.5rem',
                  borderRadius: 'var(--radius-md)',
                  backgroundColor: 'rgba(124, 58, 237, 0.12)',
                  border: '1px solid rgba(124, 58, 237, 0.3)',
                  color: 'var(--demo-badge)',
                  fontSize: 'var(--text-xs)',
                  fontWeight: 600,
                  cursor: 'pointer',
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  gap: '0.25rem',
                }}
              >
                <ShieldCheck size={16} />
                Admin
              </button>

              <button
                type="button"
                onClick={() => handleDemoLogin('CITIZEN')}
                style={{
                  padding: '0.5rem',
                  borderRadius: 'var(--radius-md)',
                  backgroundColor: 'rgba(34, 197, 94, 0.12)',
                  border: '1px solid rgba(34, 197, 94, 0.3)',
                  color: 'var(--severity-1)',
                  fontSize: 'var(--text-xs)',
                  fontWeight: 600,
                  cursor: 'pointer',
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  gap: '0.25rem',
                }}
              >
                <User size={16} />
                Citizen
              </button>
            </div>
          </div>
        </Card>
      </div>
    </div>
  );
};
