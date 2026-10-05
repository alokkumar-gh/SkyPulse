/**
 * SkyPulse Live Status & Data Freshness System
 * Implements Sections 18 & 19:
 * "The status should communicate actual system state. Never fake real-time status."
 * "Every important weather observation should communicate freshness."
 */

import React, { useState, useEffect } from 'react';
import { Clock } from 'lucide-react';

export type SystemLiveState = 'LIVE' | 'SYNCING' | 'DELAYED' | 'OFFLINE';

interface LiveStatusProps {
  state?: SystemLiveState;
  lastUpdated?: Date | string | number;
  showIcon?: boolean;
  className?: string;
  style?: React.CSSProperties;
}

export function formatTimeAgo(dateInput?: Date | string | number): string {
  if (!dateInput) return 'just now';
  const date = typeof dateInput === 'object' ? dateInput : new Date(dateInput);
  const now = new Date();
  const diffSec = Math.floor((now.getTime() - date.getTime()) / 1000);

  if (diffSec < 0 || isNaN(diffSec)) return 'just now';
  if (diffSec < 5) return 'just now';
  if (diffSec < 60) return `${diffSec} seconds ago`;
  const diffMin = Math.floor(diffSec / 60);
  if (diffMin === 1) return '1 min ago';
  if (diffMin < 60) return `${diffMin} min ago`;
  const diffHrs = Math.floor(diffMin / 60);
  if (diffHrs === 1) return '1 hour ago';
  if (diffHrs < 24) return `${diffHrs} hours ago`;
  return `${Math.floor(diffHrs / 24)}d ago`;
}

export const LiveStatus: React.FC<LiveStatusProps> = ({
  state = 'LIVE',
  lastUpdated,
  showIcon = true,
  className = '',
  style,
}) => {
  const [, setTick] = useState(0);

  // Update time display every 5 seconds
  useEffect(() => {
    const timer = setInterval(() => setTick((t: number) => t + 1), 5000);
    return () => clearInterval(timer);
  }, []);

  const getStatusMeta = () => {
    switch (state) {
      case 'LIVE':
        return {
          color: 'var(--teal)',
          bg: 'var(--teal-100)',
          border: 'var(--border-teal)',
          dotClass: 'pulse-live',
          label: 'LIVE',
          subtext: lastUpdated ? `Updated ${formatTimeAgo(lastUpdated)}` : 'Live stream active',
        };
      case 'SYNCING':
        return {
          color: 'var(--sev-2)',
          bg: 'var(--sev-2-dim)',
          border: 'rgba(234, 179, 8, 0.25)',
          dotClass: 'sp-spin',
          label: 'SYNCING',
          subtext: lastUpdated ? `Sync in progress · Last: ${formatTimeAgo(lastUpdated)}` : 'Ingesting streams...',
        };
      case 'DELAYED':
        return {
          color: 'var(--sev-3)',
          bg: 'var(--sev-3-dim)',
          border: 'rgba(249, 115, 22, 0.25)',
          dotClass: '',
          label: 'DELAYED',
          subtext: lastUpdated ? `Last update: ${formatTimeAgo(lastUpdated)}` : 'Feed latency detected',
        };
      case 'OFFLINE':
      default:
        return {
          color: 'var(--sev-4)',
          bg: 'var(--sev-4-dim)',
          border: 'rgba(239, 68, 68, 0.25)',
          dotClass: '',
          label: 'OFFLINE',
          subtext: 'Telemetry disconnected',
        };
    }
  };

  const meta = getStatusMeta();

  return (
    <div
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: '0.45rem',
        padding: '0.2rem 0.6rem',
        borderRadius: 'var(--r-1)',
        backgroundColor: meta.bg,
        border: `1px solid ${meta.border}`,
        fontFamily: 'var(--font-mono)',
        fontSize: 'var(--text-2xs)',
        ...style,
      }}
      className={`sp-live-status ${className}`}
      title={meta.subtext}
    >
      {/* Live pulse dot or status indicator */}
      {showIcon && (
        <span
          style={{
            width: 6,
            height: 6,
            borderRadius: '50%',
            backgroundColor: meta.color,
            display: 'inline-block',
            flexShrink: 0,
          }}
          className={meta.dotClass}
        />
      )}
      <span style={{ fontWeight: 700, color: meta.color, letterSpacing: '0.08em' }}>
        {meta.label}
      </span>
      <span style={{ color: 'var(--border-subtle)' }}>|</span>
      <span style={{ color: 'var(--text-muted)', letterSpacing: '0.02em' }}>
        {meta.subtext}
      </span>
    </div>
  );
};

// ==========================================
// DATA FRESHNESS PILL (Section 19)
// ==========================================
interface DataFreshnessProps {
  source?: string;
  timestamp: Date | string | number;
  value?: string | number;
  unit?: string;
  style?: React.CSSProperties;
}

export const DataFreshness: React.FC<DataFreshnessProps> = ({
  source,
  timestamp,
  value,
  unit,
  style,
}) => {
  const [, setTick] = useState(0);

  useEffect(() => {
    const timer = setInterval(() => setTick((t: number) => t + 1), 10000);
    return () => clearInterval(timer);
  }, []);

  return (
    <div
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: '0.35rem',
        fontFamily: 'var(--font-mono)',
        fontSize: 'var(--text-2xs)',
        color: 'var(--text-muted)',
        letterSpacing: '0.02em',
        ...style,
      }}
    >
      {value !== undefined && (
        <span style={{ fontWeight: 700, color: 'var(--text-primary)' }}>
          {value} {unit}
        </span>
      )}
      {value !== undefined && <span>·</span>}
      {source && (
        <>
          <span style={{ color: 'var(--text-secondary)', fontWeight: 600 }}>{source}</span>
          <span>·</span>
        </>
      )}
      <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.2rem' }}>
        <Clock size={10} color="var(--teal)" />
        {formatTimeAgo(timestamp)}
      </span>
    </div>
  );
};
