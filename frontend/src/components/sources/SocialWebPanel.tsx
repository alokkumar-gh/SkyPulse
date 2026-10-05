/**
 * SocialWebPanel — Phase 10
 * Wraps the existing social/web connector overview for the Sources page.
 * All data comes from real backend via socialWebAPI.
 */
import { useEffect, useState } from 'react';
import { socialWebAPI } from '../../utils/api';
import type { SocialWebConnectorOverview } from '../../types';
import { Globe, CheckCircle2, XCircle, RefreshCw, Radio } from 'lucide-react';

function StatusDot({ healthy }: { healthy: boolean }) {
  return (
    <span style={{
      width: 7, height: 7,
      borderRadius: '50%',
      background: healthy ? 'var(--sev-1)' : 'var(--sev-4)',
      display: 'inline-block',
      flexShrink: 0,
    }} />
  );
}

export function SocialWebPanel() {
  const [data, setData] = useState<SocialWebConnectorOverview | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await socialWebAPI.overview();
      setData(res);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load connector overview');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  if (loading) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '3rem', gap: '0.5rem', color: 'var(--text-muted)' }}>
        <RefreshCw size={16} style={{ animation: 'spin 0.8s linear infinite' }} />
        <span style={{ fontFamily: 'var(--font-mono)', fontSize: 'var(--text-sm)' }}>
          Loading social/web intelligence connector...
        </span>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-muted)' }}>
        <Globe size={32} style={{ marginBottom: '0.75rem', opacity: 0.4 }} />
        <div style={{ fontSize: 'var(--text-sm)', marginBottom: '0.5rem' }}>
          {error ?? 'Connector overview unavailable'}
        </div>
        <button
          onClick={load}
          style={{
            display: 'inline-flex', alignItems: 'center', gap: '0.35rem',
            padding: '0.35rem 0.85rem',
            borderRadius: 'var(--r-2)',
            border: '1px solid var(--border-default)',
            background: 'var(--bg-elevated)',
            color: 'var(--text-secondary)',
            fontSize: 'var(--text-xs)',
            cursor: 'pointer',
          }}
        >
          <RefreshCw size={12} /> Retry
        </button>
      </div>
    );
  }

  const sources = (data as any).sources ?? (data as any).source_configs ?? [];
  const healthySources = (data as any).healthy_sources ?? 0;
  const totalSources = (data as any).total_sources ?? sources.length;
  const connectorStatus = (data as any).connector_status ?? 'UNKNOWN';

  return (
    <div style={{ width: '100%' }}>
      {/* Status overview strip */}
      <div style={{
        display: 'flex',
        gap: '1px',
        background: 'var(--border-subtle)',
        borderRadius: 'var(--r-3)',
        overflow: 'hidden',
        marginBottom: '1.5rem',
        border: '1px solid var(--border-subtle)',
      }}>
        {[
          {
            label: 'CONNECTOR',
            value: connectorStatus,
            color: connectorStatus === 'OPERATIONAL' ? 'var(--sev-1)' : 'var(--sev-3)',
          },
          { label: 'SOURCES', value: `${healthySources}/${totalSources}`, color: 'var(--blue-400)' },
          { label: 'MODE', value: (data as any).discovery_mode ?? 'MULTI-SOURCE', color: 'var(--text-secondary)' },
        ].map(({ label, value, color }) => (
          <div key={label} style={{
            flex: 1, padding: '0.75rem 1rem',
            background: 'var(--bg-panel)',
          }}>
            <div style={{ fontFamily: 'var(--font-mono)', fontSize: 'var(--text-2xs)', color: 'var(--text-muted)', letterSpacing: '0.08em', textTransform: 'uppercase', marginBottom: '0.2rem' }}>
              {label}
            </div>
            <div style={{ fontFamily: 'var(--font-mono)', fontSize: 'var(--text-lg)', fontWeight: 700, color, letterSpacing: '-0.02em' }}>
              {value}
            </div>
          </div>
        ))}
      </div>

      {/* Source list */}
      {sources.length > 0 ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
          <div style={{
            fontFamily: 'var(--font-mono)',
            fontSize: 'var(--text-2xs)',
            color: 'var(--text-muted)',
            letterSpacing: '0.08em',
            textTransform: 'uppercase',
            marginBottom: '0.5rem',
          }}>
            Configured Sources — {sources.length}
          </div>
          {sources.map((src: any, i: number) => {
            const healthy = src.status === 'HEALTHY' || src.is_active !== false;
            return (
              <div key={src.name ?? src.url ?? i} style={{
                background: 'var(--bg-panel)',
                border: '1px solid var(--border-subtle)',
                borderLeft: `3px solid ${healthy ? 'var(--sev-1)' : 'var(--sev-4)'}`,
                borderRadius: 'var(--r-3)',
                padding: '0.625rem 0.875rem',
                display: 'flex',
                alignItems: 'center',
                gap: '0.75rem',
              }}>
                <StatusDot healthy={healthy} />
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 'var(--text-sm)', fontWeight: 500, color: 'var(--text-primary)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {src.name ?? src.source_name ?? 'Unnamed Source'}
                  </div>
                  {src.url && (
                    <div style={{ fontFamily: 'var(--font-mono)', fontSize: 'var(--text-2xs)', color: 'var(--text-muted)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', marginTop: '0.1rem' }}>
                      {src.url}
                    </div>
                  )}
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexShrink: 0 }}>
                  {src.type && (
                    <span style={{ fontFamily: 'var(--font-mono)', fontSize: 'var(--text-2xs)', color: 'var(--text-muted)', letterSpacing: '0.05em' }}>
                      {src.type}
                    </span>
                  )}
                  {healthy
                    ? <CheckCircle2 size={13} color="var(--sev-1)" />
                    : <XCircle size={13} color="var(--sev-4)" />
                  }
                </div>
              </div>
            );
          })}
        </div>
      ) : (
        <div style={{ textAlign: 'center', padding: '2rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', fontSize: 'var(--text-sm)' }}>
          <Radio size={24} style={{ marginBottom: '0.75rem', opacity: 0.3 }} />
          <div>No source details returned by connector overview API</div>
        </div>
      )}
    </div>
  );
}
