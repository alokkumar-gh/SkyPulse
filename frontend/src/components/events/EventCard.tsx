/**
 * EventCard — National Weather Intelligence Event Card
 * Implements:
 * - Section 6: Premium Cards (Fine hairline border, small radius, zero floating glass)
 * - Section 3: Visual Hierarchy (Level 1: What is happening, Level 2: Severity/Confidence, Level 3: Evidence & Freshness)
 * - Section 32: Microinteractions (hover background shift, compression, active states)
 */

import React from 'react';
import type { WeatherEvent } from '../../types';
import { CATEGORY_COLORS, SEVERITY_COLORS } from '../../types';
import { CategoryBadge, SeverityBadge, VerificationBadge, PhenomenonBadge } from '../ui/Badges';
import { MapPin, Clock, Database, AlertTriangle } from 'lucide-react';

interface EventCardProps {
  event: WeatherEvent;
  isSelected?: boolean;
  onClick?: (event: WeatherEvent) => void;
  compact?: boolean;
  isNew?: boolean;
}

function relativeTime(ts?: string): string {
  if (!ts) return 'now';
  const diff = Math.floor((Date.now() - new Date(ts).getTime()) / 1000);
  if (diff < 60) return `${Math.max(1, diff)}s ago`;
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return `${Math.floor(diff / 86400)}d ago`;
}

function confidenceColor(v: number): string {
  if (v >= 0.75) return 'var(--sev-1)';
  if (v >= 0.5) return 'var(--teal)';
  if (v >= 0.25) return 'var(--sev-2)';
  return 'var(--sev-4)';
}

export const EventCard: React.FC<EventCardProps> = ({
  event,
  isSelected = false,
  onClick,
  compact = false,
  isNew = false,
}) => {
  const isExtreme = event.severity === 4;
  const catColor = CATEGORY_COLORS[event.category] ?? 'var(--text-muted)';
  const sevColor = SEVERITY_COLORS[event.severity] ?? 'var(--text-muted)';
  const confColor = confidenceColor(event.confidence_score);

  const location = [event.district, event.state || 'India'].filter(Boolean).join(', ');
  const timestamp = event.first_reported_at || event.created_at || event.updated_at;

  return (
    <div
      role="button"
      tabIndex={onClick ? 0 : undefined}
      onClick={() => onClick?.(event)}
      onKeyDown={(e) => { if (e.key === 'Enter') onClick?.(event); }}
      style={{
        background: isSelected ? 'var(--bg-elevated)' : 'var(--bg-surface)',
        border: `1px solid ${isSelected ? 'var(--border-teal)' : isExtreme ? 'rgba(239,68,68,0.3)' : 'var(--border-hairline)'}`,
        borderLeft: `3px solid ${isSelected ? 'var(--teal)' : sevColor}`,
        borderRadius: 'var(--r-2)',
        padding: compact ? '0.65rem 0.85rem' : '0.85rem 1rem',
        cursor: onClick ? 'pointer' : 'default',
        transition: 'all 0.16s cubic-bezier(0.16, 1, 0.3, 1)',
        display: 'flex',
        flexDirection: 'column',
        gap: '0.5rem',
        position: 'relative',
        overflow: 'hidden',
        animation: isNew
          ? 'slide-in-right 0.3s var(--ease-out-expo) both'
          : isExtreme
          ? 'alert-flash 3s ease infinite'
          : 'none',
        boxShadow: isSelected ? '0 0 12px rgba(0, 229, 195, 0.12)' : 'none',
      }}
      className={`sp-event-card ${isSelected ? 'sp-event-selected' : ''}`}
      aria-selected={isSelected}
      aria-label={`Weather event: ${event.category} in ${location}`}
    >
      {/* Top indicator dot */}
      <div
        style={{
          position: 'absolute',
          top: '0.65rem',
          right: '0.65rem',
          width: 7,
          height: 7,
          borderRadius: '50%',
          background: sevColor,
          opacity: 0.85,
        }}
        aria-hidden="true"
      />

      {/* Row 1: Category + Severity + Anomaly Indicator */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', flexWrap: 'wrap', paddingRight: '1rem' }}>
        <CategoryBadge category={event.category} />
        {event.phenomenon && event.phenomenon !== event.category && (
          <PhenomenonBadge phenomenon={event.phenomenon} />
        )}
        <SeverityBadge severity={event.severity} />
        {event.is_anomalous && (
          <span
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '0.2rem',
              padding: '0.1rem 0.35rem',
              borderRadius: 'var(--r-1)',
              fontSize: 'var(--text-2xs)',
              fontWeight: 700,
              fontFamily: 'var(--font-mono)',
              letterSpacing: '0.05em',
              background: 'rgba(249,115,22,0.12)',
              color: 'var(--sev-3)',
              border: '1px solid rgba(249,115,22,0.2)',
            }}
          >
            <AlertTriangle size={9} />
            ANOMALY
          </span>
        )}
      </div>

      {/* Row 2: Headline / Title */}
      <div
        style={{
          fontSize: compact ? 'var(--text-xs)' : 'var(--text-sm)',
          fontWeight: 700,
          color: 'var(--text-primary)',
          lineHeight: 1.3,
          letterSpacing: '-0.01em',
          fontFamily: 'var(--font-sans)',
        }}
      >
        {event.title || `${event.category} · ${location}`}
      </div>

      {/* Row 3: Confidence Rail & Ground Truth Status */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
        {/* Track bar */}
        <div
          style={{
            flex: 1,
            height: 3,
            background: 'var(--bg-overlay)',
            borderRadius: 'var(--r-full)',
            overflow: 'hidden',
          }}
        >
          <div
            style={{
              height: '100%',
              width: `${Math.round(event.confidence_score * 100)}%`,
              background: confColor,
              borderRadius: 'var(--r-full)',
              transition: 'width 0.4s ease',
            }}
          />
        </div>

        {/* Confidence metric value */}
        <span
          style={{
            fontFamily: 'var(--font-mono)',
            fontSize: 'var(--text-2xs)',
            fontWeight: 600,
            color: confColor,
            minWidth: 28,
            textAlign: 'right',
          }}
        >
          {Math.round(event.confidence_score * 100)}%
        </span>

        {/* Ground Truth Status */}
        <VerificationBadge status={event.verification_status} />
      </div>

      {/* Row 4: Geographic Location & Multi-Source Signal Freshness */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: '0.5rem',
          paddingTop: '0.35rem',
          borderTop: '1px solid var(--border-hairline)',
          fontFamily: 'var(--font-mono)',
          fontSize: 'var(--text-2xs)',
          color: 'var(--text-muted)',
        }}
      >
        {/* Location with category color marker */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.25rem', overflow: 'hidden', flex: 1 }}>
          <MapPin size={10} color={catColor} style={{ flexShrink: 0 }} />
          <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {location}
          </span>
        </div>

        {/* Time + multi-source count */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.45rem', flexShrink: 0 }}>
          <span style={{ display: 'flex', alignItems: 'center', gap: '0.2rem', color: 'var(--text-ghost)' }}>
            <Database size={9} />
            {event.sources_count && event.sources_count > 1 ? `${event.sources_count} src · ` : ''}
            {event.evidence_count || 1} sig
          </span>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.2rem' }}>
            <Clock size={9} />
            <span>{event.freshness_label || relativeTime(timestamp)}</span>
          </div>
        </div>
      </div>
    </div>
  );
};
