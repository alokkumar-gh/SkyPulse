/**
 * SkyPulse Error Boundary — Phase 10 Production Stability
 * ========================================================
 * Catches rendering and lifecycle errors in React component subtrees.
 * Prevents application crashes / blank white screens and provides
 * a clean, operational fallback with component-level retry capability.
 * Handles ChunkLoadError for stale client bundles gracefully.
 */
import { Component, type ErrorInfo, type ReactNode } from 'react';
import { AlertTriangle, RefreshCw, Home } from 'lucide-react';

interface ErrorBoundaryProps {
  children: ReactNode;
  fallbackTitle?: string;
  fallbackMessage?: string;
  onReset?: () => void;
  isolate?: boolean; // If true, displays compact card instead of full page
}

interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
  errorId: string | null;
  timestamp: string | null;
}

export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = {
      hasError: false,
      error: null,
      errorId: null,
      timestamp: null,
    };
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    const errorId = `ERR-${Math.random().toString(36).substring(2, 9).toUpperCase()}`;
    const timestamp = new Date().toISOString();
    return {
      hasError: true,
      error,
      errorId,
      timestamp,
    };
  }

  override componentDidCatch(error: Error, errorInfo: ErrorInfo): void {
    // Check if error is ChunkLoadError (e.g. after a new deployment)
    const isChunkError =
      error.name === 'ChunkLoadError' ||
      error.message?.includes('Loading chunk') ||
      error.message?.includes('Failed to fetch dynamically imported module');

    if (isChunkError) {
      const hasReloaded = sessionStorage.getItem('skypulse_chunk_reload');
      if (!hasReloaded) {
        sessionStorage.setItem('skypulse_chunk_reload', 'true');
        window.location.reload();
        return;
      }
    }

    // Safe error reporting in console without exposing secrets
    console.error('[SkyPulse ErrorBoundary]', {
      name: error.name,
      message: error.message,
      componentStack: errorInfo.componentStack,
      timestamp: new Date().toISOString(),
    });
  }

  handleRetry = (): void => {
    sessionStorage.removeItem('skypulse_chunk_reload');
    this.props.onReset?.();
    this.setState({
      hasError: false,
      error: null,
      errorId: null,
      timestamp: null,
    });
  };

  handleReload = (): void => {
    sessionStorage.removeItem('skypulse_chunk_reload');
    window.location.reload();
  };

  handleGoHome = (): void => {
    window.location.href = '/';
  };

  override render(): ReactNode {
    if (this.state.hasError) {
      const { isolate = false, fallbackTitle, fallbackMessage } = this.props;
      const title = fallbackTitle || 'System Interface Error';
      const message =
        fallbackMessage ||
        'An unexpected interface error occurred while rendering this weather intelligence module.';

      if (isolate) {
        return (
          <div
            style={{
              padding: '1.25rem',
              backgroundColor: 'var(--bg-surface, #0d1020)',
              border: '1px solid rgba(239,68,68,0.3)',
              borderRadius: 'var(--r-3, 8px)',
              display: 'flex',
              flexDirection: 'column',
              gap: '0.75rem',
              color: 'var(--text-primary, #e2e8f2)',
              margin: '0.5rem 0',
            }}
            role="alert"
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: 'var(--sev-4, #ef4444)' }}>
              <AlertTriangle size={18} />
              <span style={{ fontWeight: 700, fontSize: 'var(--text-sm, 14px)' }}>{title}</span>
            </div>
            <p style={{ margin: 0, fontSize: 'var(--text-xs, 12px)', color: 'var(--text-secondary, #8b98ae)' }}>
              {message}
            </p>
            <div style={{ display: 'flex', gap: '0.5rem', marginTop: '0.25rem' }}>
              <button
                onClick={this.handleRetry}
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '0.35rem',
                  padding: '0.35rem 0.75rem',
                  backgroundColor: 'var(--blue-500, #3b82f6)',
                  color: '#fff',
                  border: 'none',
                  borderRadius: 'var(--r-2, 5px)',
                  fontSize: 'var(--text-xs, 12px)',
                  fontWeight: 600,
                  cursor: 'pointer',
                }}
              >
                <RefreshCw size={13} />
                Retry Module
              </button>
            </div>
          </div>
        );
      }

      return (
        <div
          style={{
            minHeight: '60vh',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: '2rem',
            backgroundColor: 'var(--bg-primary, #08091a)',
          }}
          role="alert"
        >
          <div
            style={{
              maxWidth: '520px',
              width: '100%',
              backgroundColor: 'var(--bg-surface, #0d1020)',
              border: '1px solid var(--border-strong, rgba(255,255,255,0.18))',
              borderRadius: 'var(--r-4, 12px)',
              padding: '2rem',
              display: 'flex',
              flexDirection: 'column',
              gap: '1.25rem',
              boxShadow: 'var(--shadow-xl, 0 16px 64px rgba(0,0,0,0.7))',
              position: 'relative',
              overflow: 'hidden',
            }}
          >
            {/* Header branding */}
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', borderBottom: '1px solid var(--border-subtle)', paddingBottom: '0.75rem' }}>
              <span
                style={{
                  fontFamily: 'var(--font-mono, monospace)',
                  fontSize: 'var(--text-2xs, 10px)',
                  fontWeight: 700,
                  letterSpacing: '0.1em',
                  color: 'var(--blue-400, #60a5fa)',
                  textTransform: 'uppercase',
                }}
              >
                SKYPULSE COMMAND CENTER
              </span>
              <span
                style={{
                  fontFamily: 'var(--font-mono, monospace)',
                  fontSize: 'var(--text-2xs, 10px)',
                  color: 'var(--text-muted, #566270)',
                }}
              >
                {this.state.errorId}
              </span>
            </div>

            {/* Error title */}
            <div style={{ display: 'flex', alignItems: 'flex-start', gap: '0.75rem' }}>
              <div
                style={{
                  padding: '0.5rem',
                  borderRadius: 'var(--r-3, 8px)',
                  backgroundColor: 'var(--sev-4-dim, rgba(239,68,68,0.12))',
                  color: 'var(--sev-4, #ef4444)',
                  display: 'flex',
                  flexShrink: 0,
                }}
              >
                <AlertTriangle size={24} />
              </div>
              <div>
                <h2
                  style={{
                    margin: 0,
                    fontSize: 'var(--text-lg, 18px)',
                    fontWeight: 700,
                    color: 'var(--text-primary, #e2e8f2)',
                    lineHeight: 1.3,
                  }}
                >
                  {title}
                </h2>
                <p
                  style={{
                    margin: '0.35rem 0 0 0',
                    fontSize: 'var(--text-sm, 14px)',
                    color: 'var(--text-secondary, #8b98ae)',
                    lineHeight: 1.5,
                  }}
                >
                  {message}
                </p>
              </div>
            </div>

            {/* Telemetry info */}
            <div
              style={{
                backgroundColor: 'var(--bg-void, #060810)',
                border: '1px solid var(--border-subtle, rgba(255,255,255,0.055))',
                borderRadius: 'var(--r-2, 5px)',
                padding: '0.65rem 0.85rem',
                fontSize: 'var(--text-2xs, 10px)',
                fontFamily: 'var(--font-mono, monospace)',
                color: 'var(--text-muted, #566270)',
                display: 'flex',
                flexDirection: 'column',
                gap: '0.25rem',
              }}
            >
              <div>INCIDENT ID: {this.state.errorId}</div>
              <div>TIMESTAMP: {this.state.timestamp}</div>
            </div>

            {/* Actions */}
            <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap', paddingTop: '0.25rem' }}>
              <button
                onClick={this.handleRetry}
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '0.4rem',
                  padding: '0.6rem 1.1rem',
                  backgroundColor: 'var(--blue-500, #3b82f6)',
                  color: '#fff',
                  border: 'none',
                  borderRadius: 'var(--r-2, 5px)',
                  fontSize: 'var(--text-sm, 14px)',
                  fontWeight: 600,
                  cursor: 'pointer',
                  transition: 'background 0.15s ease',
                }}
              >
                <RefreshCw size={15} />
                Retry Component
              </button>

              <button
                onClick={this.handleReload}
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '0.4rem',
                  padding: '0.6rem 1.1rem',
                  backgroundColor: 'var(--bg-elevated, #181c2e)',
                  color: 'var(--text-primary, #e2e8f2)',
                  border: '1px solid var(--border-default, rgba(255,255,255,0.10))',
                  borderRadius: 'var(--r-2, 5px)',
                  fontSize: 'var(--text-sm, 14px)',
                  fontWeight: 500,
                  cursor: 'pointer',
                }}
              >
                Reload Dashboard
              </button>

              <button
                onClick={this.handleGoHome}
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '0.4rem',
                  padding: '0.6rem 1rem',
                  backgroundColor: 'transparent',
                  color: 'var(--text-secondary, #8b98ae)',
                  border: 'none',
                  fontSize: 'var(--text-sm, 14px)',
                  cursor: 'pointer',
                  marginLeft: 'auto',
                }}
              >
                <Home size={15} />
                Overview
              </button>
            </div>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
