/**
 * EventCard — Phase 7
 * Renders an operational weather event card with consistent visual encoding:
 * - Category badge with tailored color
 * - Severity badge (● 1-4)
 * - Verification status chip
 * - Confidence bar
 * - Relative time & location
 * - Corroborating signals count
 */
import type { WeatherEvent } from '../../types';
import {
  CategoryBadge,
  SeverityBadge,
  VerificationBadge,
  ConfidenceBar,
  DemoBadge,
} from '../ui/Badges';
import { MapPin, Clock, Users } from 'lucide-react';

interface EventCardProps {
  event: WeatherEvent;
  isSelected?: boolean;
  onClick?: (event: WeatherEvent) => void;
  compact?: boolean;
}

export const EventCard: React.FC<EventCardProps> = ({
  event,
  isSelected = false,
  onClick,
  compact = false,
}) => {
  const formatRelativeTime = (timestamp?: string) => {
    if (!timestamp) return 'Just now';
    const diff = Math.floor((Date.now() - new Date(timestamp).getTime()) / 1000);
    if (diff < 60) return `${Math.max(1, diff)}s ago`;
    if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
    if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
    return `${Math.floor(diff / 86400)}d ago`;
  };

  const isSevere = event.severity >= 3;

  return (
    <div
      onClick={() => onClick && onClick(event)}
      style={{
        backgroundColor: isSelected ? 'var(--bg-elevated)' : 'var(--bg-surface)',
        border: `1px solid ${isSelected ? 'var(--brand-blue)' : isSevere ? 'rgba(239, 68, 68, 0.4)' : 'var(--bg-border)'}`,
        borderLeft: isSelected ? '4px solid var(--brand-blue)' : undefined,
        borderRadius: 'var(--radius-lg)',
        padding: compact ? '0.75rem' : '1rem',
        cursor: onClick ? 'pointer' : 'default',
        transition: 'all 0.15s ease',
        display: 'flex',
        flexDirection: 'column',
        gap: '0.5rem',
        position: 'relative',
        boxShadow: isSelected ? '0 0 12px rgba(59, 130, 246, 0.2)' : 'none',
      }}
      className="sp-event-card"
    >
      {/* Top Metadata Row */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '0.5rem', flexWrap: 'wrap' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
          <CategoryBadge category={event.category} />
          <SeverityBadge severity={event.severity} />
          {event.is_synthetic && <DemoBadge />}
        </div>
        <VerificationBadge status={event.verification_status} />
      </div>

      {/* Title & Description */}
      <div>
        <h4
          style={{
            margin: '0 0 0.25rem 0',
            fontSize: compact ? 'var(--text-sm)' : 'var(--text-base)',
            fontWeight: 600,
            color: 'var(--text-primary)',
            lineHeight: 1.3,
          }}
        >
          {event.title || `${event.category} in ${event.district || event.state || 'India'}`}
        </h4>
        {!compact && event.description && (
          <p
            style={{
              margin: 0,
              fontSize: 'var(--text-xs)',
              color: 'var(--text-secondary)',
              lineHeight: 1.4,
              display: '-webkit-box',
              WebkitLineClamp: 2,
              WebkitBoxOrient: 'vertical',
              overflow: 'hidden',
            }}
          >
            {event.description}
          </p>
        )}
      </div>

      {/* Confidence Bar */}
      <div>
        <ConfidenceBar value={event.confidence_score} showValue />
      </div>

      {/* Bottom Footer Row */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          fontSize: 'var(--text-xs)',
          color: 'var(--text-muted)',
          paddingTop: '0.35rem',
          borderTop: '1px solid rgba(255, 255, 255, 0.05)',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.3rem', maxWidth: '60%' }}>
          <MapPin size={12} />
          <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {event.district ? `${event.district}, ` : ''}{event.state || 'India'}
          </span>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
            <Clock size={12} />
            <span>{formatRelativeTime(event.created_at || event.updated_at)}</span>
          </div>

          {event.report_count !== undefined && (
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
              <Users size={12} />
              <span>{event.report_count}</span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
