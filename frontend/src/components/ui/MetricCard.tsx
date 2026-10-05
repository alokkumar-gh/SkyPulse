/**
 * SkyPulse Design System — Editorial Metric Component
 * Implements Section 7: "The metric should feel like a piece of intelligence."
 *
 * Structure:
 * CATEGORY / LABEL (Monospace, uppercase, tracked, muted)
 * 84 mm (Large typography: DM Serif Display or IBM Plex Mono)
 * +12% vs seasonal average (Contextual comparison)
 * IMD · 14:32 IST (Data source + Freshness)
 */

import React from 'react';
import { ArrowUpRight, ArrowDownRight, Minus, AlertCircle } from 'lucide-react';

export interface EditorialMetricProps {
  label: string;
  value: string | number;
  unit?: string;
  comparison?: {
    value: string | number;
    text: string;
    trend?: 'up' | 'down' | 'neutral';
    sentiment?: 'positive' | 'negative' | 'neutral' | 'warning';
  };
  source?: string;
  timestamp?: string;
  freshness?: string;
  signal?: 'teal' | 'sev-1' | 'sev-2' | 'sev-3' | 'sev-4';
  isAnomaly?: boolean;
  onClick?: () => void;
  className?: string;
  style?: React.CSSProperties;
}

export const MetricCard: React.FC<EditorialMetricProps> = ({
  label,
  value,
  unit,
  comparison,
  source,
  timestamp,
  freshness,
  signal,
  isAnomaly = false,
  onClick,
  className = '',
  style,
}) => {
  const getTrendIcon = () => {
    if (!comparison?.trend) return null;
    if (comparison.trend === 'up') return <ArrowUpRight size={13} />;
    if (comparison.trend === 'down') return <ArrowDownRight size={13} />;
    return <Minus size={13} />;
  };

  const getSentimentColor = () => {
    if (!comparison?.sentiment) return 'var(--text-muted)';
    switch (comparison.sentiment) {
      case 'negative':
        return 'var(--sev-4)';
      case 'warning':
        return 'var(--sev-3)';
      case 'positive':
        return 'var(--sev-1)';
      case 'neutral':
      default:
        return 'var(--teal)';
    }
  };

  const getSignalBorder = () => {
    if (signal === 'teal') return 'var(--teal)';
    if (signal === 'sev-1') return 'var(--sev-1)';
    if (signal === 'sev-2') return 'var(--sev-2)';
    if (signal === 'sev-3') return 'var(--sev-3)';
    if (signal === 'sev-4') return 'var(--sev-4)';
    return 'transparent';
  };

  return (
    <div
      onClick={onClick}
      style={{
        backgroundColor: 'var(--bg-surface)',
        border: '1px solid var(--border-hairline)',
        borderLeft: signal ? `3px solid ${getSignalBorder()}` : '1px solid var(--border-hairline)',
        borderRadius: 'var(--r-2)',
        padding: '1rem 1.15rem',
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'space-between',
        cursor: onClick ? 'pointer' : 'default',
        position: 'relative',
        transition: 'transform 0.18s ease, border-color 0.18s ease, background-color 0.18s ease',
        ...style,
      }}
      className={`sp-editorial-metric ${onClick ? 'sp-metric-clickable' : ''} ${className}`}
    >
      {/* Top row: Label & Anomaly Indicator */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '0.5rem', marginBottom: '0.4rem' }}>
        <span
          style={{
            fontFamily: 'var(--font-mono)',
            fontSize: 'var(--text-2xs)',
            fontWeight: 600,
            letterSpacing: '0.12em',
            textTransform: 'uppercase',
            color: 'var(--text-secondary)',
          }}
        >
          {label}
        </span>
        {isAnomaly && (
          <span
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '0.25rem',
              fontSize: 'var(--text-2xs)',
              fontFamily: 'var(--font-mono)',
              color: 'var(--sev-3)',
              backgroundColor: 'var(--sev-3-dim)',
              padding: '0.1rem 0.4rem',
              borderRadius: 'var(--r-1)',
              letterSpacing: '0.04em',
            }}
          >
            <AlertCircle size={10} />
            ANOMALY
          </span>
        )}
      </div>

      {/* Primary Value */}
      <div style={{ display: 'flex', alignItems: 'baseline', gap: '0.35rem', margin: '0.2rem 0' }}>
        <span
          style={{
            fontFamily: 'var(--font-mono)',
            fontSize: 'var(--text-3xl)',
            fontWeight: 700,
            color: isAnomaly ? 'var(--text-primary)' : 'var(--text-primary)',
            letterSpacing: '-0.03em',
            lineHeight: 1,
          }}
        >
          {value}
        </span>
        {unit && (
          <span
            style={{
              fontFamily: 'var(--font-mono)',
              fontSize: 'var(--text-xs)',
              color: 'var(--text-muted)',
              fontWeight: 500,
            }}
          >
            {unit}
          </span>
        )}
      </div>

      {/* Comparison Context */}
      {comparison && (
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '0.25rem',
            fontSize: 'var(--text-xs)',
            color: getSentimentColor(),
            fontFamily: 'var(--font-mono)',
            marginTop: '0.35rem',
            lineHeight: 1.2,
          }}
        >
          {getTrendIcon()}
          <span>{comparison.value}</span>
          <span style={{ color: 'var(--text-muted)' }}>{comparison.text}</span>
        </div>
      )}

      {/* Source & Freshness Metadata */}
      {(source || timestamp || freshness) && (
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '0.4rem',
            fontSize: 'var(--text-2xs)',
            color: 'var(--text-muted)',
            fontFamily: 'var(--font-mono)',
            marginTop: '0.75rem',
            paddingTop: '0.5rem',
            borderTop: '1px solid var(--border-hairline)',
            letterSpacing: '0.02em',
          }}
        >
          {source && <span style={{ fontWeight: 600, color: 'var(--text-secondary)' }}>{source}</span>}
          {source && (timestamp || freshness) && <span>·</span>}
          {timestamp && <span>{timestamp}</span>}
          {freshness && <span style={{ color: 'var(--teal-soft)' }}>{freshness}</span>}
        </div>
      )}
    </div>
  );
};
