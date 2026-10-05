/**
 * EmergingEventsPanel Component — Signature Intelligence Feature
 * =============================================================
 * Detects the signal before the event becomes obvious.
 * Displays:
 * - Deterministic Emergence States (SIGNAL -> DEVELOPING -> EMERGING -> CONFIRMED)
 * - Transparent 9-Factor Emergence Score decomposition vs Confidence Score
 * - Expandable "WHY EMERGING" real-data evidence rationales
 * - Multi-source stream diversity & temporal velocity acceleration indicators
 * - Individual constituent signal explorer
 */

import React, { useEffect, useState } from 'react';
import type { EmergingEvent, EmergenceState } from '../../types';
import { emergingEventsAPI } from '../../utils/api';
import {
  CategoryBadge,
  SeverityBadge,
} from '../ui/Badges';
import { Button } from '../ui/Primitives';
import {
  Zap,
  Radio,
  MapPin,
  ChevronDown,
  ChevronUp,
  AlertTriangle,
  RefreshCw,
  Info,
} from 'lucide-react';

export const EMERGENCE_STATE_CONFIG: Record<
  EmergenceState,
  { label: string; color: string; bg: string; border: string; icon: string }
> = {
  SIGNAL: {
    label: 'SIGNAL',
    color: '#38bdf8',
    bg: 'rgba(56, 189, 248, 0.1)',
    border: 'rgba(56, 189, 248, 0.3)',
    icon: '●',
  },
  DEVELOPING: {
    label: 'DEVELOPING',
    color: '#fbbf24',
    bg: 'rgba(251, 191, 36, 0.1)',
    border: 'rgba(251, 191, 36, 0.3)',
    icon: '▲',
  },
  EMERGING: {
    label: 'EMERGING',
    color: '#f97316',
    bg: 'rgba(249, 115, 22, 0.12)',
    border: 'rgba(249, 115, 22, 0.35)',
    icon: '⚡',
  },
  CONFIRMED: {
    label: 'CONFIRMED',
    color: '#22c55e',
    bg: 'rgba(34, 197, 94, 0.12)',
    border: 'rgba(34, 197, 94, 0.35)',
    icon: '✓',
  },
  DISSIPATING: {
    label: 'DISSIPATING',
    color: '#94a3b8',
    bg: 'rgba(148, 163, 184, 0.1)',
    border: 'rgba(148, 163, 184, 0.25)',
    icon: '▼',
  },
  EXPIRED: {
    label: 'EXPIRED',
    color: '#64748b',
    bg: 'rgba(100, 116, 139, 0.08)',
    border: 'rgba(100, 116, 139, 0.2)',
    icon: '✕',
  },
};

export const EmergenceBadge: React.FC<{ state: EmergenceState; size?: 'sm' | 'md' }> = ({
  state,
  size = 'sm',
}) => {
  const conf = EMERGENCE_STATE_CONFIG[state] || EMERGENCE_STATE_CONFIG.SIGNAL;
  return (
    <span
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: '0.3rem',
        padding: size === 'sm' ? '2px 7px' : '3px 9px',
        borderRadius: 'var(--radius-full, 9999px)',
        fontSize: size === 'sm' ? '10px' : '11px',
        fontWeight: 700,
        color: conf.color,
        backgroundColor: conf.bg,
        border: `1px solid ${conf.border}`,
        fontFamily: 'var(--font-mono)',
        textTransform: 'uppercase',
        letterSpacing: '0.04em',
      }}
    >
      <span>{conf.icon}</span>
      <span>{conf.label}</span>
    </span>
  );
};

interface EmergingEventsPanelProps {
  onSelectEvent?: (event: EmergingEvent) => void;
  selectedEventId?: string | null;
  compact?: boolean;
}

export const EmergingEventsPanel: React.FC<EmergingEventsPanelProps> = ({
  onSelectEvent,
  selectedEventId,
  compact = false,
}) => {
  const [events, setEvents] = useState<EmergingEvent[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [activeCategoryFilter, setActiveCategoryFilter] = useState<string>('ALL');

  const fetchEmergingEvents = async () => {
    try {
      setLoading(true);
      setError(null);
      const res = await emergingEventsAPI.list({
        category: activeCategoryFilter === 'ALL' ? undefined : activeCategoryFilter,
      });
      if (res && res.items) {
        setEvents(res.items);
      } else {
        setEvents([]);
      }
    } catch (err: any) {
      setError(err?.message || 'Failed to detect emerging weather events');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchEmergingEvents();
  }, [activeCategoryFilter]);

  const toggleExpand = (id: string, e?: React.MouseEvent) => {
    if (e) e.stopPropagation();
    setExpandedId((prev) => (prev === id ? null : id));
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: compact ? '0.5rem' : '0.75rem', width: '100%' }}>
      {/* Header Bar */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: '0.5rem',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              width: '28px',
              height: '28px',
              borderRadius: 'var(--radius-md)',
              backgroundColor: 'rgba(249, 115, 22, 0.15)',
              color: '#f97316',
            }}
          >
            <Zap size={16} />
          </div>
          <div>
            <h3 style={{ margin: 0, fontSize: 'var(--text-sm)', fontWeight: 700, color: 'var(--text-primary)' }}>
              Emerging Event Detector
            </h3>
            <span style={{ fontSize: '10px', color: 'var(--text-muted)' }}>
              Early spatiotemporal convergence intelligence
            </span>
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <span
            style={{
              padding: '2px 8px',
              borderRadius: 'var(--radius-sm)',
              backgroundColor: 'var(--bg-elevated)',
              fontSize: '11px',
              color: 'var(--brand-blue)',
              fontWeight: 600,
              fontFamily: 'var(--font-mono)',
            }}
          >
            {events.length} Active Signal Cluster(s)
          </span>
          <Button
            size="sm"
            variant="secondary"
            onClick={fetchEmergingEvents}
            loading={loading}
            aria-label="Refresh emerging events"
          >
            <RefreshCw size={13} />
          </Button>
        </div>
      </div>

      {/* Category Filter Pills */}
      <div style={{ display: 'flex', gap: '0.25rem', overflowX: 'auto', paddingBottom: '2px' }}>
        {['ALL', 'RAINFALL', 'THUNDERSTORM', 'FLOODING', 'HEATWAVE', 'STRONG_WINDS', 'CYCLONE'].map((cat) => (
          <button
            key={cat}
            type="button"
            onClick={() => setActiveCategoryFilter(cat)}
            style={{
              padding: '2px 8px',
              fontSize: '10px',
              fontWeight: 600,
              borderRadius: '9999px',
              border: '1px solid',
              borderColor: activeCategoryFilter === cat ? 'var(--brand-orange)' : 'var(--border-subtle)',
              backgroundColor: activeCategoryFilter === cat ? 'rgba(249, 115, 22, 0.15)' : 'transparent',
              color: activeCategoryFilter === cat ? '#f97316' : 'var(--text-muted)',
              cursor: 'pointer',
              transition: 'all 0.15s ease',
            }}
          >
            {cat}
          </button>
        ))}
      </div>

      {/* Loading State */}
      {loading && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
          <div style={{ height: '70px', backgroundColor: 'var(--bg-elevated)', borderRadius: 'var(--radius-md)' }} />
          <div style={{ height: '70px', backgroundColor: 'var(--bg-elevated)', borderRadius: 'var(--radius-md)' }} />
        </div>
      )}

      {/* Error State */}
      {error && !loading && (
        <div style={{ padding: '0.75rem', backgroundColor: 'rgba(239, 68, 68, 0.1)', borderRadius: 'var(--radius-md)', border: '1px solid rgba(239, 68, 68, 0.25)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', color: 'var(--severity-4)', fontSize: 'var(--text-xs)', fontWeight: 600 }}>
            <AlertTriangle size={14} />
            <span>Detection Offline</span>
          </div>
          <p style={{ margin: '0.2rem 0 0 0', fontSize: '11px', color: 'var(--text-secondary)' }}>{error}</p>
        </div>
      )}

      {/* Empty State */}
      {!loading && !error && events.length === 0 && (
        <div
          style={{
            padding: '1.5rem',
            textAlign: 'center',
            backgroundColor: 'var(--bg-elevated)',
            borderRadius: 'var(--radius-md)',
            border: '1px solid var(--bg-border)',
          }}
        >
          <Radio size={24} color="var(--text-muted)" style={{ margin: '0 auto 0.5rem auto' }} />
          <div style={{ fontSize: 'var(--text-xs)', fontWeight: 600, color: 'var(--text-primary)' }}>
            No Emerging Signal Convergence Detected
          </div>
          <p style={{ margin: '0.25rem 0 0 0', fontSize: '11px', color: 'var(--text-muted)' }}>
            Current observations indicate stable meteorological baseline without multi-source convergence.
          </p>
        </div>
      )}

      {/* Emerging Events List */}
      {!loading && !error && events.length > 0 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.65rem' }}>
          {events.map((emg) => {
            const isSelected = selectedEventId === emg.id;
            const isExpanded = expandedId === emg.id;
            const stateConf = EMERGENCE_STATE_CONFIG[emg.state] || EMERGENCE_STATE_CONFIG.SIGNAL;

            return (
              <div
                key={emg.id}
                onClick={() => onSelectEvent?.(emg)}
                style={{
                  backgroundColor: isSelected ? 'var(--bg-elevated)' : 'var(--bg-surface)',
                  border: `1px solid ${isSelected ? 'var(--brand-blue)' : 'var(--bg-border)'}`,
                  borderRadius: 'var(--radius-md)',
                  padding: '0.85rem',
                  cursor: 'pointer',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '0.65rem',
                  transition: 'all 0.15s ease',
                  boxShadow: isSelected ? '0 0 0 1px var(--brand-blue)' : 'none',
                }}
              >
                {/* Top Row: Category, State Badge, & Emergence Score */}
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '0.4rem' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                    <CategoryBadge category={emg.dominant_category} />
                    <SeverityBadge severity={emg.severity} />
                    <EmergenceBadge state={emg.state} />
                  </div>

                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                    {/* Emergence Score */}
                    <div style={{ textAlign: 'right' }}>
                      <div style={{ fontSize: '10px', color: 'var(--text-muted)', textTransform: 'uppercase', fontWeight: 600 }}>Emergence</div>
                      <div style={{ fontSize: 'var(--text-xs)', fontWeight: 700, color: stateConf.color, fontFamily: 'var(--font-mono)' }}>
                        {Math.round(emg.emergence_score * 100)}%
                      </div>
                    </div>

                    {/* Confidence Score */}
                    <div style={{ textAlign: 'right' }}>
                      <div style={{ fontSize: '10px', color: 'var(--text-muted)', textTransform: 'uppercase', fontWeight: 600 }}>Confidence</div>
                      <div style={{ fontSize: 'var(--text-xs)', fontWeight: 700, color: 'var(--brand-blue)', fontFamily: 'var(--font-mono)' }}>
                        {Math.round(emg.confidence_score * 100)}%
                      </div>
                    </div>
                  </div>
                </div>

                {/* Location & Velocity Metrics */}
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontSize: 'var(--text-xs)', color: 'var(--text-secondary)' }}>
                  <span style={{ display: 'flex', alignItems: 'center', gap: '0.3rem' }}>
                    <MapPin size={13} color="var(--brand-blue)" />
                    <span style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{emg.location_summary}</span>
                  </span>

                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', fontSize: '11px', fontFamily: 'var(--font-mono)' }}>
                    <span>{emg.evidence_count} signal(s)</span>
                    <span>{emg.source_count} source(s)</span>
                    <span style={{ color: emg.acceleration_indicator > 1.2 ? 'var(--severity-3)' : 'var(--text-muted)' }}>
                      {emg.acceleration_indicator.toFixed(1)}x accel
                    </span>
                  </div>
                </div>

                {/* Footprint & Stream diversity tags */}
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '0.5rem', flexWrap: 'wrap' }}>
                  <div style={{ display: 'flex', gap: '0.3rem', flexWrap: 'wrap' }}>
                    {emg.unique_source_types.map((src) => (
                      <span
                        key={src}
                        style={{
                          fontSize: '9px',
                          padding: '1px 5px',
                          borderRadius: 'var(--radius-sm)',
                          backgroundColor: 'var(--bg-elevated)',
                          border: '1px solid var(--bg-border)',
                          color: 'var(--text-secondary)',
                        }}
                      >
                        {src}
                      </span>
                    ))}
                  </div>

                  <button
                    onClick={(e) => toggleExpand(emg.id, e)}
                    style={{
                      background: 'none',
                      border: 'none',
                      color: 'var(--brand-blue)',
                      fontSize: '11px',
                      fontWeight: 600,
                      cursor: 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '0.2rem',
                      padding: 0,
                    }}
                  >
                    <span>{isExpanded ? 'Hide Rationale' : 'Why Emerging'}</span>
                    {isExpanded ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
                  </button>
                </div>

                {/* Expandable "WHY EMERGING" Rationale Panel */}
                {isExpanded && (
                  <div
                    style={{
                      marginTop: '0.25rem',
                      padding: '0.75rem',
                      backgroundColor: 'var(--bg-elevated)',
                      borderRadius: 'var(--radius-sm)',
                      border: '1px solid var(--bg-border)',
                      display: 'flex',
                      flexDirection: 'column',
                      gap: '0.5rem',
                    }}
                  >
                    <div style={{ fontSize: '11px', fontWeight: 700, color: 'var(--text-primary)', textTransform: 'uppercase', display: 'flex', alignItems: 'center', gap: '0.3rem' }}>
                      <Info size={13} color="var(--brand-blue)" />
                      <span>Evidence-Driven Emergence Rationale</span>
                    </div>

                    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
                      {emg.factors.explanation_bullets.map((bullet, idx) => (
                        <div key={idx} style={{ fontSize: '11px', color: 'var(--text-secondary)', display: 'flex', alignItems: 'flex-start', gap: '0.35rem' }}>
                          <span style={{ color: 'var(--brand-blue)', marginTop: '2px' }}>•</span>
                          <span>{bullet}</span>
                        </div>
                      ))}
                    </div>

                    {/* Factor Breakdown Bars */}
                    <div style={{ marginTop: '0.4rem', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.4rem', fontSize: '10px' }}>
                      <div>Spatial Convergence: {(emg.factors.spatial_convergence_score * 100).toFixed(0)}%</div>
                      <div>Temporal Accel: {(emg.factors.temporal_acceleration_score * 100).toFixed(0)}%</div>
                      <div>Source Diversity: {(emg.factors.source_diversity_score * 100).toFixed(0)}%</div>
                      <div>Category Harmony: {(emg.factors.category_consistency_score * 100).toFixed(0)}%</div>
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};
