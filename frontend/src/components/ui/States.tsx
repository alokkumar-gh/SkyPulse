/**
 * Error / Empty State Components — Phase 7
 */
import React from 'react';
import { AlertCircle, Inbox, WifiOff, RefreshCw } from 'lucide-react';

interface ErrorStateProps {
  title?: string;
  message: string;
  onRetry?: () => void;
}

export function ErrorState({ title = 'Something went wrong', message, onRetry }: ErrorStateProps) {
  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        gap: '0.75rem',
        padding: '2rem',
        color: 'var(--text-secondary)',
        textAlign: 'center',
      }}
      role="alert"
    >
      <AlertCircle size={28} color="var(--sev-4)" strokeWidth={1.5} />
      <div>
        <div style={{ fontWeight: 700, color: 'var(--text-primary)', marginBottom: '0.25rem', fontFamily: 'var(--font-sans)', letterSpacing: '-0.01em' }}>
          {title}
        </div>
        <div style={{ fontSize: 'var(--text-xs)', fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>{message}</div>
      </div>
      {onRetry && (
        <button
          onClick={onRetry}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '0.4rem',
            padding: '0.4rem 1rem',
            borderRadius: 'var(--r-2)',
            border: '1px solid var(--border-subtle)',
            backgroundColor: 'var(--bg-elevated)',
            color: 'var(--teal)',
            fontSize: 'var(--text-sm)',
            cursor: 'pointer',
            fontFamily: 'var(--font-mono)',
            letterSpacing: '0.04em',
          }}
        >
          <RefreshCw size={13} />
          Retry
        </button>
      )}
    </div>
  );
}

interface LoadingStateProps {
  message?: string;
}

export function LoadingState({ message = 'Loading...' }: LoadingStateProps) {
  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        gap: '0.75rem',
        padding: '3rem 2rem',
        color: 'var(--text-secondary)',
        textAlign: 'center',
      }}
    >
      <span className="pulse-live" style={{ width: 8, height: 8 }} />
      <div style={{ fontSize: 'var(--text-xs)', fontFamily: 'var(--font-mono)', letterSpacing: '0.06em', color: 'var(--text-muted)', textTransform: 'uppercase' }}>{message}</div>
    </div>
  );
}

interface EmptyStateProps {
  icon?: React.ReactNode;
  title: string;
  description?: string;
  message?: string;
  action?: React.ReactNode;
}

export function EmptyState({ icon, title, description, message, action }: EmptyStateProps) {
  const desc = description ?? message;
  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        gap: '0.5rem',
        padding: '2.5rem',
        color: 'var(--text-secondary)',
        textAlign: 'center',
      }}
    >
      {icon ?? <Inbox size={32} color="var(--text-muted)" />}
      <div style={{ fontWeight: 600, color: 'var(--text-primary)', marginTop: '0.5rem' }}>{title}</div>
      {desc && <div style={{ fontSize: 'var(--text-sm)', maxWidth: 320 }}>{desc}</div>}
      {action && <div style={{ marginTop: '0.75rem' }}>{action}</div>}
    </div>
  );
}

export function OfflineBanner() {
  return (
    <div
      style={{
        position: 'fixed',
        top: 'var(--topbar-height)',
        left: 0,
        right: 0,
        zIndex: 1000,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        gap: '0.5rem',
        padding: '0.4rem 1rem',
        backgroundColor: 'var(--sev-4)',
        color: 'var(--white)',
        fontSize: 'var(--text-xs)',
        fontWeight: 700,
        fontFamily: 'var(--font-mono)',
        letterSpacing: '0.06em',
        textTransform: 'uppercase',
      }}
      role="status"
      aria-live="polite"
    >
      <WifiOff size={13} />
      LIVE CONNECTION LOST — Reconnecting…
    </div>
  );
}

export function TableSkeleton({ rows = 5 }: { rows?: number }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', padding: '1rem', backgroundColor: 'var(--bg-surface)', borderRadius: 'var(--radius-lg)', border: '1px solid var(--bg-border)' }}>
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} style={{ height: 28, backgroundColor: 'var(--bg-elevated)', borderRadius: 'var(--radius-sm)', animation: 'pulse 1.5s infinite' }} />
      ))}
    </div>
  );
}

export function DetailSkeleton() {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem', padding: '1.5rem', backgroundColor: 'var(--bg-surface)', borderRadius: 'var(--radius-lg)', border: '1px solid var(--bg-border)' }}>
      <div style={{ height: 32, width: '40%', backgroundColor: 'var(--bg-elevated)', borderRadius: 'var(--radius-sm)' }} />
      <div style={{ height: 18, width: '65%', backgroundColor: 'var(--bg-elevated)', borderRadius: 'var(--radius-sm)' }} />
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem', marginTop: '1rem' }}>
        <div style={{ height: 180, backgroundColor: 'var(--bg-elevated)', borderRadius: 'var(--radius-md)' }} />
        <div style={{ height: 180, backgroundColor: 'var(--bg-elevated)', borderRadius: 'var(--radius-md)' }} />
      </div>
    </div>
  );
}

