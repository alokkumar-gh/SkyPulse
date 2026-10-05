/**
 * SkyPulse Alert Component
 * Implements Section 22:
 * "Alerts should be calm but unmistakable.
 *  Severity should be communicated through:
 *  Typography, Signal bar, Small semantic color — not giant red backgrounds."
 *
 * Structure:
 * SEVERE WEATHER | ODISHA
 * Cyclonic activity detected
 * Updated 14:32 IST · IMD Radar
 * [View event →]
 */

import { Clock, MapPin } from 'lucide-react';
import { Button } from './Primitives';

export interface AlertItemProps {
  id?: string;
  category: string;
  location: string;
  headline: string;
  summary?: string;
  severity: 1 | 2 | 3 | 4;
  timestamp: string;
  source?: string;
  onExplore?: () => void;
  style?: React.CSSProperties;
  className?: string;
}

export const AlertItem: React.FC<AlertItemProps> = ({
  category,
  location,
  headline,
  summary,
  severity,
  timestamp,
  source = 'IMD Civil Safety',
  onExplore,
  style,
  className = '',
}) => {
  const getSeverityMeta = () => {
    switch (severity) {
      case 4:
        return {
          color: 'var(--sev-4)',
          bg: 'var(--sev-4-dim)',
          label: 'CRITICAL / EXTREME',
          badgeColor: 'var(--sev-4)',
        };
      case 3:
        return {
          color: 'var(--sev-3)',
          bg: 'var(--sev-3-dim)',
          label: 'SEVERE / WARNING',
          badgeColor: 'var(--sev-3)',
        };
      case 2:
        return {
          color: 'var(--sev-2)',
          bg: 'var(--sev-2-dim)',
          label: 'MODERATE / ADVISORY',
          badgeColor: 'var(--sev-2)',
        };
      case 1:
      default:
        return {
          color: 'var(--sev-1)',
          bg: 'var(--sev-1-dim)',
          label: 'MINOR / WATCH',
          badgeColor: 'var(--sev-1)',
        };
    }
  };

  const meta = getSeverityMeta();

  return (
    <div
      style={{
        backgroundColor: 'var(--bg-surface)',
        border: '1px solid var(--border-hairline)',
        borderLeft: `3px solid ${meta.color}`,
        borderRadius: 'var(--r-2)',
        padding: '1rem 1.25rem',
        display: 'flex',
        flexDirection: 'column',
        gap: '0.65rem',
        position: 'relative',
        transition: 'transform 0.15s ease, border-color 0.15s ease',
        ...style,
      }}
      className={`sp-alert-item ${className}`}
    >
      {/* Top Header Row: Category, Location, Severity badge */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '0.5rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap' }}>
          <span
            style={{
              fontSize: 'var(--text-2xs)',
              fontFamily: 'var(--font-mono)',
              fontWeight: 700,
              letterSpacing: '0.12em',
              textTransform: 'uppercase',
              color: meta.color,
            }}
          >
            {category}
          </span>
          <span style={{ color: 'var(--border-subtle)', fontSize: 'var(--text-xs)' }}>/</span>
          <span
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '0.25rem',
              fontSize: 'var(--text-xs)',
              fontFamily: 'var(--font-mono)',
              fontWeight: 600,
              color: 'var(--text-primary)',
            }}
          >
            <MapPin size={11} color="var(--teal)" />
            {location}
          </span>
        </div>

        <span
          style={{
            fontSize: 'var(--text-2xs)',
            fontFamily: 'var(--font-mono)',
            fontWeight: 700,
            padding: '0.15rem 0.45rem',
            borderRadius: 'var(--r-1)',
            backgroundColor: meta.bg,
            color: meta.badgeColor,
            letterSpacing: '0.04em',
            border: `1px solid ${meta.color}40`,
          }}
        >
          {meta.label}
        </span>
      </div>

      {/* Main Headline */}
      <div
        style={{
          fontSize: 'var(--text-base)',
          fontWeight: 700,
          color: 'var(--text-primary)',
          fontFamily: 'var(--font-sans)',
          lineHeight: 1.3,
          letterSpacing: '-0.01em',
        }}
      >
        {headline}
      </div>

      {/* Optional Narrative Summary */}
      {summary && (
        <div
          style={{
            fontSize: 'var(--text-xs)',
            color: 'var(--text-secondary)',
            lineHeight: 1.5,
          }}
        >
          {summary}
        </div>
      )}

      {/* Bottom Footer: Freshness, Source & Action */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          paddingTop: '0.5rem',
          borderTop: '1px solid var(--border-hairline)',
          marginTop: '0.2rem',
          flexWrap: 'wrap',
          gap: '0.5rem',
        }}
      >
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '0.5rem',
            fontFamily: 'var(--font-mono)',
            fontSize: 'var(--text-2xs)',
            color: 'var(--text-muted)',
          }}
        >
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.25rem' }}>
            <Clock size={11} color="var(--teal)" />
            Updated {timestamp}
          </span>
          <span>·</span>
          <span>{source}</span>
        </div>

        {onExplore && (
          <Button
            variant="ghost"
            size="xs"
            onClick={onExplore}
            withArrow
            style={{
              padding: '0.15rem 0.4rem',
              color: 'var(--teal)',
              fontFamily: 'var(--font-mono)',
              fontSize: 'var(--text-2xs)',
              letterSpacing: '0.04em',
            }}
          >
            EXPLORE EVENT
          </Button>
        )}
      </div>
    </div>
  );
};
