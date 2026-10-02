/**
 * SourceReputationPanel Component — Signature Intelligence Feature
 * ================================================================
 * "Trust should evolve from evidence, not from a fixed label."
 *
 * Capabilities:
 * - Dynamic Weather Source Reputation Graph
 * - State Badges (NEW, INSUFFICIENT_EVIDENCE, ESTABLISHED, TRUSTED, WATCH, LOW_RELIABILITY)
 * - Transparent 9-Factor Decomposition & Metric Gauges
 * - Category-Specific Reliability Matrix (RAINFALL, THUNDERSTORM, FLOOD, HEATWAVE, etc.)
 * - Expandable "WHY THIS REPUTATION?" Machine-Readable Rationale
 * - Historical Audit & Verification Outcome Timeline
 * - Neutral Evidence Comparison Tool (no arbitrary rankings)
 */

import React, { useEffect, useState, useMemo } from 'react';
import type {
  SourceReputation,
  ReputationState,
  ReputationTimelineEntry,
  CategoryReputationDetail,
} from '../../types';
import { sourcesAPI } from '../../utils/api';
import { Button } from '../ui/Primitives';
import {
  Shield,
  ShieldCheck,
  ShieldAlert,
  AlertTriangle,
  HelpCircle,
  Clock,
  RefreshCw,
  ChevronDown,
  ChevronUp,
  Layers,
  Info,
  Scale,
  Sparkles,
} from 'lucide-react';

export const REPUTATION_STATE_CONFIG: Record<
  ReputationState,
  { label: string; color: string; bg: string; border: string; icon: typeof Shield }
> = {
  NEW: {
    label: 'NEW',
    color: '#94a3b8',
    bg: 'rgba(148, 163, 184, 0.12)',
    border: 'rgba(148, 163, 184, 0.3)',
    icon: Sparkles,
  },
  INSUFFICIENT_EVIDENCE: {
    label: 'INSUFFICIENT EVIDENCE',
    color: '#eab308',
    bg: 'rgba(234, 179, 8, 0.12)',
    border: 'rgba(234, 179, 8, 0.3)',
    icon: HelpCircle,
  },
  ESTABLISHED: {
    label: 'ESTABLISHED',
    color: '#38bdf8',
    bg: 'rgba(56, 189, 248, 0.12)',
    border: 'rgba(56, 189, 248, 0.3)',
    icon: ShieldCheck,
  },
  TRUSTED: {
    label: 'TRUSTED',
    color: '#10b981',
    bg: 'rgba(16, 185, 129, 0.15)',
    border: 'rgba(16, 185, 129, 0.35)',
    icon: ShieldCheck,
  },
  WATCH: {
    label: 'WATCH',
    color: '#f59e0b',
    bg: 'rgba(245, 158, 11, 0.15)',
    border: 'rgba(245, 158, 11, 0.35)',
    icon: AlertTriangle,
  },
  LOW_RELIABILITY: {
    label: 'LOW RELIABILITY',
    color: '#ef4444',
    bg: 'rgba(239, 68, 68, 0.15)',
    border: 'rgba(239, 68, 68, 0.35)',
    icon: ShieldAlert,
  },
};

export const ReputationStateBadge: React.FC<{
  state: ReputationState;
  size?: 'sm' | 'md';
}> = ({ state, size = 'md' }) => {
  const cfg = REPUTATION_STATE_CONFIG[state] || REPUTATION_STATE_CONFIG.NEW;
  const Icon = cfg.icon;
  const isSm = size === 'sm';

  return (
    <span
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: '4px',
        padding: isSm ? '2px 6px' : '3px 8px',
        borderRadius: 'var(--radius-sm)',
        fontSize: isSm ? '10px' : '11px',
        fontWeight: 700,
        fontFamily: 'var(--font-mono)',
        color: cfg.color,
        backgroundColor: cfg.bg,
        border: `1px solid ${cfg.border}`,
        letterSpacing: '0.04em',
        textTransform: 'uppercase',
      }}
    >
      <Icon size={isSm ? 11 : 13} />
      {cfg.label}
    </span>
  );
};

export const CategoryReliabilityPill: React.FC<{
  detail: CategoryReputationDetail;
}> = ({ detail }) => {
  const getLevelStyle = (level: string) => {
    switch (level) {
      case 'STRONG_EVIDENCE':
        return { color: '#10b981', bg: 'rgba(16, 185, 129, 0.12)', border: 'rgba(16, 185, 129, 0.3)' };
      case 'CONTRADICTED_PATTERN':
        return { color: '#ef4444', bg: 'rgba(239, 68, 68, 0.12)', border: 'rgba(239, 68, 68, 0.3)' };
      case 'LIMITED_EVIDENCE':
        return { color: '#eab308', bg: 'rgba(234, 179, 8, 0.12)', border: 'rgba(234, 179, 8, 0.3)' };
      case 'MODERATE_EVIDENCE':
        return { color: '#38bdf8', bg: 'rgba(56, 189, 248, 0.12)', border: 'rgba(56, 189, 248, 0.3)' };
      default:
        return { color: 'var(--text-muted)', bg: 'var(--bg-elevated)', border: 'var(--border-subtle)' };
    }
  };

  const style = getLevelStyle(detail.reliability_level);

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        padding: '6px 10px',
        borderRadius: 'var(--radius-sm)',
        backgroundColor: style.bg,
        border: `1px solid ${style.border}`,
        fontSize: '11px',
        minWidth: '110px',
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '2px' }}>
        <span style={{ fontWeight: 700, color: 'var(--text-primary)', fontSize: '10px' }}>
          {detail.category}
        </span>
        <span style={{ fontWeight: 600, color: style.color, fontSize: '9px', fontFamily: 'var(--font-mono)' }}>
          {detail.observation_count} obs
        </span>
      </div>
      <span style={{ fontSize: '9px', color: style.color, fontWeight: 600, textTransform: 'uppercase' }}>
        {detail.support_rate !== null ? `${Math.round(detail.support_rate * 100)}% Verified` : 'No Data'}
      </span>
    </div>
  );
};

export const SourceReputationPanel: React.FC<{
  onSelectSource?: (sourceId: string) => void;
  selectedSourceId?: string;
}> = ({ onSelectSource, selectedSourceId }) => {
  const [sources, setSources] = useState<SourceReputation[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [activeStateFilter, setActiveStateFilter] = useState<string>('ALL');
  const [activeTypeFilter, setActiveTypeFilter] = useState<string>('ALL');
  const [compareMode, setCompareMode] = useState<boolean>(false);
  const [selectedForCompare, setSelectedForCompare] = useState<string[]>([]);
  const [timelineData, setTimelineData] = useState<Record<string, ReputationTimelineEntry[]>>({});
  const [loadingTimeline, setLoadingTimeline] = useState<string | null>(null);

  const fetchReputations = async () => {
    try {
      setLoading(true);
      setError(null);
      const res = await sourcesAPI.reputation({
        reputation_state: activeStateFilter === 'ALL' ? undefined : activeStateFilter,
        source_type: activeTypeFilter === 'ALL' ? undefined : activeTypeFilter,
      });
      if (res && res.items) {
        setSources(res.items);
      } else {
        setSources([]);
      }
    } catch (err: any) {
      setError(err?.message || 'Failed to load source reputation data');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchReputations();
  }, [activeStateFilter, activeTypeFilter]);

  const toggleExpand = async (sourceId: string) => {
    if (expandedId === sourceId) {
      setExpandedId(null);
    } else {
      setExpandedId(sourceId);
      if (!timelineData[sourceId]) {
        try {
          setLoadingTimeline(sourceId);
          const tRes = await sourcesAPI.getTimeline(sourceId);
          if (tRes && tRes.timeline) {
            setTimelineData((prev) => ({ ...prev, [sourceId]: tRes.timeline }));
          }
        } catch {
          // ignore
        } finally {
          setLoadingTimeline(null);
        }
      }
    }
  };

  const toggleCompareSelect = (sourceId: string) => {
    setSelectedForCompare((prev) =>
      prev.includes(sourceId) ? prev.filter((id) => id !== sourceId) : [...prev, sourceId]
    );
  };

  const comparedSources = useMemo(() => {
    return sources.filter((s) => selectedForCompare.includes(s.source_id));
  }, [sources, selectedForCompare]);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem', width: '100%' }}>
      {/* Header & Controls */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: '0.75rem',
          paddingBottom: '0.75rem',
          borderBottom: '1px solid var(--border-subtle)',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              width: '32px',
              height: '32px',
              borderRadius: 'var(--radius-md)',
              backgroundColor: 'rgba(56, 189, 248, 0.15)',
              color: 'var(--brand-blue)',
            }}
          >
            <Shield size={18} />
          </div>
          <div>
            <h2 style={{ margin: 0, fontSize: 'var(--text-base)', fontWeight: 700, color: 'var(--text-primary)' }}>
              Weather Source Reputation Graph
            </h2>
            <span style={{ fontSize: 'var(--text-xs)', color: 'var(--text-muted)' }}>
              Historical evidence-based reliability tracking & transparent audit trails
            </span>
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <Button
            size="sm"
            variant={compareMode ? 'primary' : 'secondary'}
            onClick={() => setCompareMode(!compareMode)}
          >
            <Scale size={14} />
            {compareMode ? 'Exit Comparison' : 'Compare Evidence'}
          </Button>
          <Button
            size="sm"
            variant="secondary"
            onClick={fetchReputations}
            loading={loading}
            aria-label="Refresh reputations"
          >
            <RefreshCw size={14} />
          </Button>
        </div>
      </div>

      {/* State & Type Filters */}
      <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', alignItems: 'center' }}>
        <span style={{ fontSize: '11px', fontWeight: 600, color: 'var(--text-muted)' }}>State:</span>
        {['ALL', 'TRUSTED', 'ESTABLISHED', 'WATCH', 'LOW_RELIABILITY', 'INSUFFICIENT_EVIDENCE', 'NEW'].map((st) => (
          <button
            key={st}
            type="button"
            onClick={() => setActiveStateFilter(st)}
            style={{
              padding: '3px 8px',
              fontSize: '10px',
              fontWeight: 600,
              borderRadius: '9999px',
              border: '1px solid',
              borderColor: activeStateFilter === st ? 'var(--brand-blue)' : 'var(--border-subtle)',
              backgroundColor: activeStateFilter === st ? 'rgba(56, 189, 248, 0.15)' : 'transparent',
              color: activeStateFilter === st ? 'var(--brand-blue)' : 'var(--text-muted)',
              cursor: 'pointer',
              transition: 'all 0.15s ease',
            }}
          >
            {st}
          </button>
        ))}
      </div>

      <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', alignItems: 'center' }}>
        <span style={{ fontSize: '11px', fontWeight: 600, color: 'var(--text-muted)' }}>Type:</span>
        {['ALL', 'GOVERNMENT_API', 'WEATHER_API', 'CITIZEN', 'PUBLIC_DATASET', 'RSS_FEED'].map((tp) => (
          <button
            key={tp}
            type="button"
            onClick={() => setActiveTypeFilter(tp)}
            style={{
              padding: '3px 8px',
              fontSize: '10px',
              fontWeight: 600,
              borderRadius: '9999px',
              border: '1px solid',
              borderColor: activeTypeFilter === tp ? 'var(--brand-purple)' : 'var(--border-subtle)',
              backgroundColor: activeTypeFilter === tp ? 'rgba(168, 85, 247, 0.15)' : 'transparent',
              color: activeTypeFilter === tp ? '#a855f7' : 'var(--text-muted)',
              cursor: 'pointer',
              transition: 'all 0.15s ease',
            }}
          >
            {tp}
          </button>
        ))}
      </div>

      {/* Side-by-Side Evidence Comparison Drawer */}
      {compareMode && (
        <div
          style={{
            padding: '1rem',
            backgroundColor: 'var(--bg-card)',
            borderRadius: 'var(--radius-lg)',
            border: '1px solid var(--border-default)',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.75rem' }}>
            <h3 style={{ margin: 0, fontSize: 'var(--text-sm)', fontWeight: 700, color: 'var(--text-primary)' }}>
              Source Evidence Comparison ({selectedForCompare.length} selected)
            </h3>
            <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
              Neutral metric comparison — no synthetic ranking
            </span>
          </div>

          {comparedSources.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '1rem', color: 'var(--text-muted)', fontSize: '12px' }}>
              Select sources below using checkboxes to compare their historical evidence.
            </div>
          ) : (
            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '12px', textAlign: 'left' }}>
                <thead>
                  <tr style={{ borderBottom: '1px solid var(--border-subtle)', color: 'var(--text-muted)' }}>
                    <th style={{ padding: '6px 8px' }}>Metric</th>
                    {comparedSources.map((s) => (
                      <th key={s.source_id} style={{ padding: '6px 8px', color: 'var(--text-primary)' }}>
                        {s.source_name}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  <tr style={{ borderBottom: '1px solid var(--border-subtle)' }}>
                    <td style={{ padding: '6px 8px', fontWeight: 600 }}>Reputation State</td>
                    {comparedSources.map((s) => (
                      <td key={s.source_id} style={{ padding: '6px 8px' }}>
                        <ReputationStateBadge state={s.reputation_state} size="sm" />
                      </td>
                    ))}
                  </tr>
                  <tr style={{ borderBottom: '1px solid var(--border-subtle)' }}>
                    <td style={{ padding: '6px 8px', fontWeight: 600 }}>Operational Trust</td>
                    {comparedSources.map((s) => (
                      <td key={s.source_id} style={{ padding: '6px 8px', fontFamily: 'var(--font-mono)' }}>
                        {(s.current_trust * 100).toFixed(0)}%
                      </td>
                    ))}
                  </tr>
                  <tr style={{ borderBottom: '1px solid var(--border-subtle)' }}>
                    <td style={{ padding: '6px 8px', fontWeight: 600 }}>Total Observations</td>
                    {comparedSources.map((s) => (
                      <td key={s.source_id} style={{ padding: '6px 8px', fontFamily: 'var(--font-mono)' }}>
                        {s.observation_count}
                      </td>
                    ))}
                  </tr>
                  <tr style={{ borderBottom: '1px solid var(--border-subtle)' }}>
                    <td style={{ padding: '6px 8px', fontWeight: 600 }}>Verification Support</td>
                    {comparedSources.map((s) => (
                      <td key={s.source_id} style={{ padding: '6px 8px', fontFamily: 'var(--font-mono)', color: '#10b981' }}>
                        {s.verification_support_rate !== null ? `${Math.round(s.verification_support_rate * 100)}%` : '—'}
                      </td>
                    ))}
                  </tr>
                  <tr style={{ borderBottom: '1px solid var(--border-subtle)' }}>
                    <td style={{ padding: '6px 8px', fontWeight: 600 }}>Contradictions</td>
                    {comparedSources.map((s) => (
                      <td key={s.source_id} style={{ padding: '6px 8px', fontFamily: 'var(--font-mono)', color: '#ef4444' }}>
                        {s.contradiction_rate !== null ? `${Math.round(s.contradiction_rate * 100)}% (${s.contradicted_count})` : '0%'}
                      </td>
                    ))}
                  </tr>
                  <tr style={{ borderBottom: '1px solid var(--border-subtle)' }}>
                    <td style={{ padding: '6px 8px', fontWeight: 600 }}>Corroboration Rate</td>
                    {comparedSources.map((s) => (
                      <td key={s.source_id} style={{ padding: '6px 8px', fontFamily: 'var(--font-mono)', color: '#38bdf8' }}>
                        {s.corroboration_rate !== null ? `${Math.round(s.corroboration_rate * 100)}%` : '—'}
                      </td>
                    ))}
                  </tr>
                  <tr>
                    <td style={{ padding: '6px 8px', fontWeight: 600 }}>Duplicate Rate</td>
                    {comparedSources.map((s) => (
                      <td key={s.source_id} style={{ padding: '6px 8px', fontFamily: 'var(--font-mono)' }}>
                        {s.duplicate_rate !== null ? `${Math.round(s.duplicate_rate * 100)}% (${s.duplicate_count})` : '0%'}
                      </td>
                    ))}
                  </tr>
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* Loading Skeleton */}
      {loading && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
          <div style={{ height: '90px', backgroundColor: 'var(--bg-elevated)', borderRadius: 'var(--radius-md)' }} />
          <div style={{ height: '90px', backgroundColor: 'var(--bg-elevated)', borderRadius: 'var(--radius-md)' }} />
        </div>
      )}

      {/* Error Banner */}
      {error && !loading && (
        <div style={{ padding: '0.75rem', backgroundColor: 'rgba(239, 68, 68, 0.1)', borderRadius: 'var(--radius-md)', border: '1px solid rgba(239, 68, 68, 0.25)' }}>
          <span style={{ color: 'var(--severity-4)', fontSize: 'var(--text-xs)', fontWeight: 600 }}>{error}</span>
        </div>
      )}

      {/* Empty State */}
      {!loading && !error && sources.length === 0 && (
        <div style={{ textAlign: 'center', padding: '2rem', backgroundColor: 'var(--bg-card)', borderRadius: 'var(--radius-lg)' }}>
          <Shield size={32} style={{ color: 'var(--text-muted)', marginBottom: '0.5rem' }} />
          <p style={{ margin: 0, fontWeight: 600, color: 'var(--text-primary)' }}>No Sources Found</p>
          <p style={{ margin: '4px 0 0', fontSize: '11px', color: 'var(--text-muted)' }}>No data sources match the current filter criteria.</p>
        </div>
      )}

      {/* Source Reputation Cards Feed */}
      {!loading && !error && sources.map((source) => {
        const isExpanded = expandedId === source.source_id;
        const isSelected = selectedSourceId === source.source_id;
        const isChecked = selectedForCompare.includes(source.source_id);

        return (
          <div
            key={source.source_id}
            onClick={() => onSelectSource && onSelectSource(source.source_id)}
            style={{
              padding: '1rem',
              backgroundColor: 'var(--bg-card)',
              borderRadius: 'var(--radius-lg)',
              border: `1px solid ${isSelected ? 'var(--brand-blue)' : 'var(--border-default)'}`,
              cursor: onSelectSource ? 'pointer' : 'default',
              transition: 'all 0.15s ease',
            }}
          >
            {/* Top Row: Identity & State Badge */}
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '0.5rem', marginBottom: '0.75rem' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                {compareMode && (
                  <input
                    type="checkbox"
                    checked={isChecked}
                    onChange={(e) => {
                      e.stopPropagation();
                      toggleCompareSelect(source.source_id);
                    }}
                    style={{ cursor: 'pointer' }}
                  />
                )}
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                    <h3 style={{ margin: 0, fontSize: 'var(--text-sm)', fontWeight: 700, color: 'var(--text-primary)' }}>
                      {source.source_name}
                    </h3>
                    <span style={{ fontSize: '10px', color: 'var(--text-muted)', padding: '1px 5px', borderRadius: '4px', backgroundColor: 'var(--bg-elevated)' }}>
                      {source.source_type}
                    </span>
                  </div>
                  <span style={{ fontSize: '10px', color: 'var(--text-muted)' }}>
                    ID: {source.source_id.slice(0, 8)}...
                  </span>
                </div>
              </div>

              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <ReputationStateBadge state={source.reputation_state} />
                <button
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation();
                    toggleExpand(source.source_id);
                  }}
                  style={{
                    background: 'none',
                    border: 'none',
                    color: 'var(--text-muted)',
                    cursor: 'pointer',
                    padding: '2px',
                  }}
                  aria-label="Toggle explanation and evidence"
                >
                  {isExpanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
                </button>
              </div>
            </div>

            {/* Metric Tiles Grid */}
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(110px, 1fr))',
                gap: '0.5rem',
                marginBottom: '0.75rem',
              }}
            >
              {/* Trust Score */}
              <div style={{ padding: '6px 8px', borderRadius: 'var(--radius-sm)', backgroundColor: 'var(--bg-elevated)', border: '1px solid var(--border-subtle)' }}>
                <span style={{ fontSize: '9px', color: 'var(--text-muted)', textTransform: 'uppercase', fontWeight: 600 }}>Operational Trust</span>
                <div style={{ fontSize: '13px', fontWeight: 700, color: 'var(--text-primary)', fontFamily: 'var(--font-mono)' }}>
                  {(source.current_trust * 100).toFixed(0)}%
                </div>
              </div>

              {/* Observation Volume */}
              <div style={{ padding: '6px 8px', borderRadius: 'var(--radius-sm)', backgroundColor: 'var(--bg-elevated)', border: '1px solid var(--border-subtle)' }}>
                <span style={{ fontSize: '9px', color: 'var(--text-muted)', textTransform: 'uppercase', fontWeight: 600 }}>Observations</span>
                <div style={{ fontSize: '13px', fontWeight: 700, color: 'var(--text-primary)', fontFamily: 'var(--font-mono)' }}>
                  {source.observation_count} <span style={{ fontSize: '10px', color: 'var(--text-muted)', fontWeight: 400 }}>({source.duplicate_count} dup)</span>
                </div>
              </div>

              {/* Verification Support Rate */}
              <div style={{ padding: '6px 8px', borderRadius: 'var(--radius-sm)', backgroundColor: 'var(--bg-elevated)', border: '1px solid var(--border-subtle)' }}>
                <span style={{ fontSize: '9px', color: 'var(--text-muted)', textTransform: 'uppercase', fontWeight: 600 }}>Verification Support</span>
                <div style={{ fontSize: '13px', fontWeight: 700, color: '#10b981', fontFamily: 'var(--font-mono)' }}>
                  {source.verification_support_rate !== null ? `${Math.round(source.verification_support_rate * 100)}%` : '—'}
                </div>
              </div>

              {/* Contradiction Rate */}
              <div style={{ padding: '6px 8px', borderRadius: 'var(--radius-sm)', backgroundColor: 'var(--bg-elevated)', border: '1px solid var(--border-subtle)' }}>
                <span style={{ fontSize: '9px', color: 'var(--text-muted)', textTransform: 'uppercase', fontWeight: 600 }}>Contradiction Rate</span>
                <div style={{ fontSize: '13px', fontWeight: 700, color: source.contradicted_count > 0 ? '#ef4444' : 'var(--text-primary)', fontFamily: 'var(--font-mono)' }}>
                  {source.contradiction_rate !== null ? `${Math.round(source.contradiction_rate * 100)}%` : '0%'}
                </div>
              </div>

              {/* Corroboration Rate */}
              <div style={{ padding: '6px 8px', borderRadius: 'var(--radius-sm)', backgroundColor: 'var(--bg-elevated)', border: '1px solid var(--border-subtle)' }}>
                <span style={{ fontSize: '9px', color: 'var(--text-muted)', textTransform: 'uppercase', fontWeight: 600 }}>Corroboration</span>
                <div style={{ fontSize: '13px', fontWeight: 700, color: '#38bdf8', fontFamily: 'var(--font-mono)' }}>
                  {source.corroboration_rate !== null ? `${Math.round(source.corroboration_rate * 100)}%` : '—'}
                </div>
              </div>
            </div>

            {/* Expandable Explanation & Breakdown */}
            {isExpanded && (
              <div
                style={{
                  marginTop: '0.75rem',
                  paddingTop: '0.75rem',
                  borderTop: '1px dashed var(--border-default)',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '0.75rem',
                }}
              >
                {/* WHY THIS REPUTATION? Section */}
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.3rem', marginBottom: '0.4rem', color: 'var(--text-primary)', fontSize: '11px', fontWeight: 700, letterSpacing: '0.04em' }}>
                    <Info size={13} color="var(--brand-blue)" />
                    WHY THIS REPUTATION?
                  </div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '3px' }}>
                    {source.explanation.map((reason, idx) => (
                      <div key={idx} style={{ display: 'flex', alignItems: 'flex-start', gap: '0.4rem', fontSize: '11px', color: 'var(--text-secondary)' }}>
                        <span style={{ color: 'var(--brand-blue)', lineHeight: '1.2' }}>•</span>
                        <span>{reason}</span>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Category-Specific Reliability Matrix */}
                {source.category_breakdown && Object.keys(source.category_breakdown).length > 0 && (
                  <div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.3rem', marginBottom: '0.4rem', color: 'var(--text-primary)', fontSize: '11px', fontWeight: 700, letterSpacing: '0.04em' }}>
                      <Layers size={13} color="var(--brand-orange)" />
                      CATEGORY-SPECIFIC RELIABILITY MATRIX
                    </div>
                    <div style={{ display: 'flex', gap: '0.4rem', flexWrap: 'wrap' }}>
                      {Object.values(source.category_breakdown).map((catDetail) => (
                        <CategoryReliabilityPill key={catDetail.category} detail={catDetail} />
                      ))}
                    </div>
                  </div>
                )}

                {/* Historical Audit Timeline */}
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.3rem', marginBottom: '0.4rem', color: 'var(--text-primary)', fontSize: '11px', fontWeight: 700, letterSpacing: '0.04em' }}>
                    <Clock size={13} color="var(--brand-purple)" />
                    EVIDENCE AUDIT TIMELINE
                  </div>
                  {loadingTimeline === source.source_id ? (
                    <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Loading timeline audit events...</span>
                  ) : timelineData[source.source_id] && timelineData[source.source_id].length > 0 ? (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', borderLeft: '2px solid var(--border-subtle)', paddingLeft: '8px', marginLeft: '4px' }}>
                      {timelineData[source.source_id].map((m) => (
                        <div key={m.milestone_id} style={{ display: 'flex', flexDirection: 'column', gap: '1px' }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                            <span style={{ fontSize: '10px', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
                              {new Date(m.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                            </span>
                            <span style={{ fontSize: '11px', fontWeight: 600, color: 'var(--text-primary)' }}>
                              {m.title}
                            </span>
                          </div>
                          <span style={{ fontSize: '10px', color: 'var(--text-secondary)' }}>
                            {m.description}
                          </span>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>No historical milestone records available.</span>
                  )}
                </div>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
};
