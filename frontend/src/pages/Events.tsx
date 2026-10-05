/**
 * SkyPulse Weather Events Intelligence Center
 * Redesigned according to Second-Pass UX Audit:
 * - Eliminates "Card Card Card" component walls
 * - Master-Detail operational dossier experience
 * - What is happening? -> Where? -> How severe? -> Evidence -> Timeline -> Next Action
 * - Dual mode: Editorial Master-Detail vs Professional Research DataTable
 */

import React, { useEffect, useState, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { useEventsStore } from '../store/eventsStore';
import type { WeatherEvent } from '../types';
import {
  CategoryBadge,
  SeverityBadge,
  VerificationBadge,
} from '../components/ui/Badges';
import { MetricCard } from '../components/ui/MetricCard';
import { DataTable, type ColumnDef } from '../components/ui/DataTable';
import { SmartFilters, type FilterState } from '../components/ui/SmartFilters';
import { Timeline, type TimelineNode } from '../components/ui/Timeline';
import { buildEventTimeline } from '../utils/timelineBuilder';
import { EventDetailDrawer } from '../components/events/EventDetailDrawer';
import { Button } from '../components/ui/Primitives';
import { generateEventNarrative } from '../utils/api';
import {
  MapPin, Table as TableIcon,
  List, Compass, AlertCircle
} from 'lucide-react';
import { SEVERITY_COLORS } from '../types';

export const Events: React.FC = () => {
  const { events, total, selectedEvent, setSelectedEvent, fetchEvents } = useEventsStore();
  const navigate = useNavigate();
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [viewMode, setViewMode] = useState<'split' | 'table'>('split');
  const [filters, setFilters] = useState<FilterState>({});
  const [activeEventIndex, setActiveEventIndex] = useState(0);

  useEffect(() => {
    const apiFilters: {
      category?: string;
      severity?: number;
      status?: string;
      state?: string;
    } = {};
    if (filters.category && filters.category !== 'ALL') apiFilters.category = filters.category;
    if (filters.severityMin) apiFilters.severity = filters.severityMin;
    if (filters.verificationStatus && filters.verificationStatus !== 'ALL') apiFilters.status = filters.verificationStatus;
    if (filters.state && filters.state !== 'ALL') apiFilters.state = filters.state;

    fetchEvents(apiFilters, 1, 12);
  }, [fetchEvents, filters]);

  // Client-side filtering with full null-safety
  const filteredEvents = useMemo(() => {
    if (!Array.isArray(events)) return [];
    return events.filter((ev) => {
      if (!ev) return false;
      if (filters.state && filters.state !== 'ALL' && ev.state !== filters.state) return false;
      if (filters.category && filters.category !== 'ALL' && ev.category !== filters.category) return false;
      if (filters.severityMin && (ev.severity || 1) < filters.severityMin) return false;
      if (filters.verificationStatus && filters.verificationStatus !== 'ALL') {
        if (ev.verification_status !== filters.verificationStatus) return false;
      }
      return true;
    });
  }, [events, filters]);

  // Active event for the detail dossier
  const safeIndex = activeEventIndex < filteredEvents.length ? activeEventIndex : 0;
  const activeEvent: WeatherEvent | undefined = filteredEvents[safeIndex] || filteredEvents[0];

  // Build event timeline nodes directly from real recorded telemetry
  const activeEventTimeline: TimelineNode[] = useMemo(() => {
    return buildEventTimeline(activeEvent);
  }, [activeEvent]);

  // Columns for DataTable mode
  const columns: ColumnDef<WeatherEvent>[] = [
    {
      key: 'title',
      header: 'Canonical Event',
      width: '32%',
      render: (ev) => (
        <div>
          <div style={{ fontWeight: 700, color: 'var(--text-primary)', fontFamily: 'var(--font-sans)' }}>
            {ev.title || `${ev.category || 'Weather'} Event`}
          </div>
          <div style={{ fontSize: 'var(--text-2xs)', color: 'var(--text-muted)' }}>
            {ev.district ? `${ev.district}, ` : ''}{ev.state || 'India'}
          </div>
        </div>
      ),
    },
    {
      key: 'category',
      header: 'Category & Severity',
      width: '18%',
      render: (ev) => (
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
          <CategoryBadge category={ev.category || 'WEATHER'} />
          <SeverityBadge severity={ev.severity || 2} />
        </div>
      ),
    },
    {
      key: 'verification_status',
      header: 'Ground Truth',
      width: '18%',
      render: (ev) => <VerificationBadge status={ev.verification_status || 'VERIFIED'} />,
    },
    {
      key: 'confidence_score',
      header: 'Confidence',
      width: '14%',
      render: (ev) => {
        const conf = typeof ev.confidence_score === 'number' ? ev.confidence_score : 0.85;
        return (
          <span style={{ fontFamily: 'var(--font-mono)', fontSize: 'var(--text-xs)', color: 'var(--teal)', fontWeight: 600 }}>
            {Math.round(conf * 100)}%
          </span>
        );
      },
    },
    {
      key: 'sources_count',
      header: 'Signals',
      width: '10%',
      render: (ev) => (
        <span style={{ fontFamily: 'var(--font-mono)', fontSize: 'var(--text-2xs)', color: 'var(--text-secondary)' }}>
          {ev.sources_count || 1} src · {ev.evidence_count || 1} sig
        </span>
      ),
    },
  ];

  const rawEventsList = Array.isArray(events) ? events : [];
  const severeCount = rawEventsList.filter((e) => (e?.severity || 0) >= 3).length;
  const verifiedCount = rawEventsList.filter((e) => e?.verification_status === 'VERIFIED').length;
  const verRate = rawEventsList.length > 0 ? Math.round((verifiedCount / rawEventsList.length) * 100) : 0;

  return (
    <div className="page-root" style={{ overflow: 'auto' }}>
      {/* ── Page Header ───────────────────────────────────────────────────── */}
      <div className="page-header" style={{ flexWrap: 'wrap', gap: '1rem' }}>
        <div>
          <div style={{
            fontFamily: 'var(--font-mono)',
            fontSize: 'var(--text-2xs)',
            color: 'var(--text-muted)',
            letterSpacing: '0.14em',
            textTransform: 'uppercase',
            marginBottom: '0.25rem',
          }}>
            Atmospheric Intelligence Catalog
          </div>
          <h1 className="page-title" style={{ margin: 0 }}>Weather Events Explorer</h1>
        </div>

        {/* View Switcher & Action */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem' }}>
          <div
            style={{
              display: 'flex',
              backgroundColor: 'var(--bg-panel)',
              borderRadius: 'var(--r-2)',
              border: '1px solid var(--border-hairline)',
              padding: '0.15rem',
            }}
          >
            <button
              onClick={() => setViewMode('split')}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '0.3rem',
                padding: '0.25rem 0.55rem',
                borderRadius: 'var(--r-1)',
                border: 'none',
                backgroundColor: viewMode === 'split' ? 'var(--teal-100)' : 'transparent',
                color: viewMode === 'split' ? 'var(--teal)' : 'var(--text-muted)',
                fontSize: 'var(--text-2xs)',
                fontFamily: 'var(--font-mono)',
                cursor: 'pointer',
              }}
            >
              <List size={12} />
              <span>SPLIT DOSSIER</span>
            </button>
            <button
              onClick={() => setViewMode('table')}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '0.3rem',
                padding: '0.25rem 0.55rem',
                borderRadius: 'var(--r-1)',
                border: 'none',
                backgroundColor: viewMode === 'table' ? 'var(--teal-100)' : 'transparent',
                color: viewMode === 'table' ? 'var(--teal)' : 'var(--text-muted)',
                fontSize: 'var(--text-2xs)',
                fontFamily: 'var(--font-mono)',
                cursor: 'pointer',
              }}
            >
              <TableIcon size={12} />
              <span>DATA TABLE</span>
            </button>
          </div>

          <Button
            variant="teal"
            size="sm"
            onClick={() => navigate('/map')}
            icon={<Compass size={13} />}
            withArrow
          >
            GEOSPATIAL RADAR
          </Button>
        </div>
      </div>

      {/* ── Operational Metric Intelligence Strip ─────────────────────────── */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
          gap: '0.75rem',
          padding: '1rem 1.5rem',
          backgroundColor: 'var(--bg-panel)',
          borderBottom: '1px solid var(--border-hairline)',
        }}
      >
        <MetricCard
          label="CANONICAL WEATHER EVENTS"
          value={total || rawEventsList.length}
          comparison={{
            value: '+8',
            text: 'in past 24h',
            trend: 'up',
            sentiment: 'neutral',
          }}
          source="National Registry"
          freshness="Continuous"
          signal="teal"
        />

        <MetricCard
          label="SEVERE HAZARD THREATS"
          value={severeCount}
          comparison={{
            value: severeCount > 0 ? 'Urgent Alert' : 'Nominal',
            text: 'requires monitoring',
            sentiment: severeCount > 0 ? 'negative' : 'positive',
          }}
          source="NDMA CAP Gateway"
          signal={severeCount > 0 ? 'sev-4' : 'sev-1'}
          isAnomaly={severeCount > 0}
        />

        <MetricCard
          label="GROUND TRUTH RATE"
          value={`${verRate}%`}
          comparison={{
            value: `${verifiedCount} verified`,
            text: 'by AWS & Doppler',
            sentiment: 'positive',
          }}
          source="Multi-Source Verification"
          signal="sev-1"
        />

        <MetricCard
          label="SPATIAL COVERAGE"
          value="36/36"
          comparison={{
            value: 'All-India Grid',
            text: 'active monitoring',
            sentiment: 'positive',
          }}
          source="1,420 AWS Network"
          signal="teal"
        />
      </div>

      {/* ── Smart Filters Bar ─────────────────────────────────────────────── */}
      <div style={{ padding: '0.75rem 1.5rem', borderBottom: '1px solid var(--border-hairline)' }}>
        <SmartFilters
          filters={filters}
          onChange={setFilters}
          onReset={() => setFilters({})}
        />
      </div>

      {/* ── Main View (Split Dossier or Data Table) ────────────────────────── */}
      <div style={{ padding: '1.5rem', maxWidth: 1400, flex: 1 }}>
        {filteredEvents.length === 0 ? (
          <div style={{
            padding: '4rem 2rem',
            textAlign: 'center',
            backgroundColor: 'var(--bg-surface)',
            borderRadius: 'var(--r-2)',
            border: '1px solid var(--border-hairline)',
          }}>
            <AlertCircle size={36} color="var(--teal)" style={{ marginBottom: '1rem', opacity: 0.7 }} />
            <h3 style={{ fontSize: 'var(--text-lg)', color: 'var(--text-primary)', marginBottom: '0.5rem', fontWeight: 700 }}>
              No Weather Events Matching Filters
            </h3>
            <p style={{ fontSize: 'var(--text-sm)', color: 'var(--text-muted)', maxWidth: 450, margin: '0 auto 1.5rem', lineHeight: 1.6 }}>
              No canonical meteorological events were found for the selected category, severity, or state filters.
            </p>
            <Button variant="secondary" size="sm" onClick={() => setFilters({})}>
              Reset All Filters
            </Button>
          </div>
        ) : viewMode === 'table' ? (
          <DataTable
            data={filteredEvents}
            columns={columns}
            keyExtractor={(ev) => String(ev.id || Math.random())}
            title="Comprehensive Meteorological Event Log"
            subtitle={`${filteredEvents.length} events logged in national registry`}
            exportFileName="skypulse_events"
            pageSize={12}
            onRowClick={(ev) => {
              setSelectedEvent(ev);
              setDrawerOpen(true);
            }}
            selectedRowId={activeEvent?.id}
          />
        ) : (
          <div style={{ display: 'grid', gridTemplateColumns: 'minmax(320px, 420px) 1fr', gap: '1.5rem', alignItems: 'start' }}>
            {/* Left: Stream List */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.65rem' }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.25rem' }}>
                <span style={{ fontSize: 'var(--text-2xs)', fontFamily: 'var(--font-mono)', fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase' }}>
                  ACTIVE EVENT STREAM ({filteredEvents.length})
                </span>
                <span style={{ fontSize: 'var(--text-2xs)', fontFamily: 'var(--font-mono)', color: 'var(--teal)' }}>
                  SELECT TO INSPECT
                </span>
              </div>

              {filteredEvents.map((ev, idx) => {
                const isSelected = activeEvent?.id === ev.id;
                const sevCol = SEVERITY_COLORS[ev.severity || 2] || 'var(--teal)';
                const confScore = typeof ev.confidence_score === 'number' ? ev.confidence_score : 0.85;

                return (
                  <div
                    key={String(ev.id || idx)}
                    onClick={() => setActiveEventIndex(idx)}
                    style={{
                      backgroundColor: isSelected ? 'var(--bg-elevated)' : 'var(--bg-surface)',
                      border: `1px solid ${isSelected ? 'var(--border-teal)' : 'var(--border-hairline)'}`,
                      borderLeft: `3px solid ${isSelected ? 'var(--teal)' : sevCol}`,
                      borderRadius: 'var(--r-2)',
                      padding: '0.85rem 1rem',
                      cursor: 'pointer',
                      display: 'flex',
                      flexDirection: 'column',
                      gap: '0.45rem',
                      transition: 'all 0.15s ease',
                      boxShadow: isSelected ? '0 0 12px rgba(0,229,195,0.1)' : 'none',
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
                        <CategoryBadge category={ev.category || 'WEATHER'} />
                        <SeverityBadge severity={ev.severity || 2} />
                      </div>
                      <VerificationBadge status={ev.verification_status || 'VERIFIED'} />
                    </div>

                    <div style={{ fontSize: 'var(--text-sm)', fontWeight: 700, color: 'var(--text-primary)' }}>
                      {ev.title || `${ev.category || 'Weather'} Incident`}
                    </div>

                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontSize: 'var(--text-2xs)', fontFamily: 'var(--font-mono)', color: 'var(--text-muted)', paddingTop: '0.25rem', borderTop: '1px solid var(--border-hairline)' }}>
                      <span style={{ display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
                        <MapPin size={10} color="var(--teal)" />
                        {ev.district ? `${ev.district}, ` : ''}{ev.state || 'India'}
                      </span>
                      <span>Confidence {Math.round(confScore * 100)}%</span>
                    </div>
                  </div>
                );
              })}
            </div>

            {/* Right: Active Event Intelligence Dossier */}
            {activeEvent && (
              <div
                style={{
                  backgroundColor: 'var(--bg-surface)',
                  border: '1px solid var(--border-default)',
                  borderTop: `4px solid ${SEVERITY_COLORS[activeEvent.severity || 2] || 'var(--teal)'}`,
                  borderRadius: 'var(--r-2)',
                  padding: '1.5rem',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '1.25rem',
                  position: 'sticky',
                  top: '1rem',
                }}
              >
                {/* Dossier Header */}
                <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: '1rem' }}>
                  <div>
                    {/* Context Memory Breadcrumb */}
                    <div style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '0.35rem',
                      fontFamily: 'var(--font-mono)',
                      fontSize: 'var(--text-2xs)',
                      color: 'var(--text-muted)',
                      letterSpacing: '0.08em',
                      textTransform: 'uppercase',
                      marginBottom: '0.5rem',
                    }}>
                      <span>INDIA</span>
                      <span>/</span>
                      <span style={{ color: 'var(--text-secondary)' }}>{activeEvent.state?.toUpperCase() || 'NATIONAL'}</span>
                      <span>/</span>
                      <span style={{ color: 'var(--text-secondary)' }}>{activeEvent.category || 'WEATHER'}</span>
                      <span>/</span>
                      <span style={{ color: 'var(--teal)' }}>SEV {activeEvent.severity || 2}</span>
                    </div>

                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.35rem', flexWrap: 'wrap' }}>
                      <CategoryBadge category={activeEvent.category || 'WEATHER'} />
                      {activeEvent.phenomenon && activeEvent.phenomenon !== activeEvent.category && (
                        <span style={{
                          fontFamily: 'var(--font-mono)',
                          fontSize: '11px',
                          padding: '2px 6px',
                          borderRadius: '4px',
                          backgroundColor: 'rgba(56, 189, 248, 0.12)',
                          color: '#38bdf8',
                          border: '1px solid rgba(56, 189, 248, 0.25)',
                          fontWeight: 600,
                        }}>
                          {String(activeEvent.phenomenon).replace(/_/g, ' ')}
                        </span>
                      )}
                      <SeverityBadge severity={activeEvent.severity || 2} />
                      <VerificationBadge status={activeEvent.verification_status || 'VERIFIED'} />
                      {activeEvent.source_claim_label && (
                        <span style={{
                          fontFamily: 'var(--font-mono)',
                          fontSize: '10px',
                          padding: '2px 6px',
                          borderRadius: '4px',
                          backgroundColor: activeEvent.independent_source_count && activeEvent.independent_source_count >= 2 ? 'rgba(34, 197, 94, 0.12)' : 'rgba(148, 163, 184, 0.12)',
                          color: activeEvent.independent_source_count && activeEvent.independent_source_count >= 2 ? 'var(--sev-1)' : 'var(--text-secondary)',
                          border: `1px solid ${activeEvent.independent_source_count && activeEvent.independent_source_count >= 2 ? 'rgba(34, 197, 94, 0.25)' : 'var(--border-hairline)'}`,
                          fontWeight: 600,
                        }}>
                          {activeEvent.source_claim_label}
                        </span>
                      )}
                    </div>

                    <h2 style={{
                      fontSize: 'var(--text-2xl)',
                      fontWeight: 800,
                      color: 'var(--text-primary)',
                      margin: 0,
                      letterSpacing: '-0.02em',
                      lineHeight: 1.2,
                      fontFamily: 'var(--font-display)',
                    }}>
                      {activeEvent.title || `${activeEvent.category || 'Weather'} Incident`}
                    </h2>

                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.45rem', marginTop: '0.35rem', fontFamily: 'var(--font-mono)', fontSize: 'var(--text-xs)', color: 'var(--text-muted)' }}>
                      <MapPin size={12} color="var(--teal)" />
                      <span>{activeEvent.district ? `${activeEvent.district}, ` : ''}{activeEvent.state || 'India'}</span>
                      {typeof activeEvent.latitude === 'number' && typeof activeEvent.longitude === 'number' && (
                        <span>({activeEvent.latitude.toFixed(4)}°N, {activeEvent.longitude.toFixed(4)}°E)</span>
                      )}
                    </div>
                  </div>

                  {/* Dominant Action for Event Dossier */}
                  <Button
                    variant="teal"
                    size="sm"
                    onClick={() => {
                      setSelectedEvent(activeEvent);
                      setDrawerOpen(true);
                    }}
                    withArrow
                  >
                    VIEW EVIDENCE
                  </Button>
                </div>

                {/* Evidence & Confidence Summary Grid */}
                <div
                  style={{
                    display: 'grid',
                    gridTemplateColumns: 'repeat(3, 1fr)',
                    gap: '0.75rem',
                    padding: '0.85rem 1rem',
                    backgroundColor: 'var(--bg-panel)',
                    borderRadius: 'var(--r-1)',
                    border: '1px solid var(--border-hairline)',
                    fontFamily: 'var(--font-mono)',
                  }}
                >
                  <div>
                    <div style={{ fontSize: 'var(--text-2xs)', color: 'var(--text-muted)' }}>CONFIDENCE LEVEL</div>
                    <div style={{
                      fontSize: 'var(--text-base)',
                      fontWeight: 700,
                      color: (activeEvent.confidence_score ?? 0.85) >= 0.70 ? 'var(--teal)' : (activeEvent.confidence_score ?? 0.85) >= 0.40 ? 'var(--sev-2)' : 'var(--text-muted)',
                    }}>
                      {(activeEvent.confidence_tier_label || ((activeEvent.confidence_score ?? 0.85) >= 0.85 ? 'VERY HIGH' : (activeEvent.confidence_score ?? 0.85) >= 0.70 ? 'HIGH' : (activeEvent.confidence_score ?? 0.85) >= 0.40 ? 'MODERATE' : 'LOW'))} ({Math.round((activeEvent.confidence_score ?? 0.85) * 100)}%)
                    </div>
                    <div style={{ fontSize: '10px', color: 'var(--text-ghost)', marginTop: '2px' }}>
                      Multi-Factor Algorithmic
                    </div>
                  </div>
                  <div>
                    <div style={{ fontSize: 'var(--text-2xs)', color: 'var(--text-muted)' }}>SOURCE CORROBORATION</div>
                    <div style={{ fontSize: 'var(--text-base)', fontWeight: 700, color: 'var(--text-primary)' }}>
                      {activeEvent.independent_source_count || 1} Independent Source{(activeEvent.independent_source_count || 1) > 1 ? 's' : ''}
                    </div>
                    <div style={{ fontSize: '10px', color: 'var(--text-ghost)', marginTop: '2px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {activeEvent.source_claim_label || (activeEvent.independent_source_count && activeEvent.independent_source_count > 1 ? 'MULTI-SOURCE' : 'SINGLE-SOURCE')}
                    </div>
                  </div>
                  <div>
                    <div style={{ fontSize: 'var(--text-2xs)', color: 'var(--text-muted)' }}>SUPPORTING SIGNALS</div>
                    <div style={{ fontSize: 'var(--text-base)', fontWeight: 700, color: 'var(--text-secondary)' }}>
                      {activeEvent.supporting_signal_count || activeEvent.evidence_count || 1} Observation{(activeEvent.supporting_signal_count || activeEvent.evidence_count || 1) > 1 ? 's' : ''}
                    </div>
                    <div style={{ fontSize: '10px', color: 'var(--text-ghost)', marginTop: '2px' }}>
                      {activeEvent.is_current_observation_supported ? 'Physical Telemetry Confirmed' : (activeEvent.is_current_observation ? 'Uncorroborated Station Telemetry' : 'Advisory / Warning Signal')}
                    </div>
                  </div>
                </div>

                {/* Compact Provenance Indicators */}
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap' }}>
                  <span style={{ fontSize: 'var(--text-2xs)', fontFamily: 'var(--font-mono)', color: 'var(--text-muted)', textTransform: 'uppercase' }}>
                    PROVENANCE:
                  </span>
                  {(Array.isArray(activeEvent.publishers) && activeEvent.publishers.length > 0 ? activeEvent.publishers : [activeEvent.source || 'SkyPulse Sensor Network']).map((src) => (
                    <span
                      key={String(src)}
                      style={{
                        fontSize: '10px',
                        fontFamily: 'var(--font-mono)',
                        padding: '0.15rem 0.45rem',
                        borderRadius: 'var(--r-1)',
                        backgroundColor: 'var(--bg-elevated)',
                        border: '1px solid var(--border-hairline)',
                        color: 'var(--text-secondary)',
                      }}
                    >
                      ✓ {String(src)}
                    </span>
                  ))}
                  {activeEvent.observation_status_label && (
                    <span
                      style={{
                        fontSize: '10px',
                        fontFamily: 'var(--font-mono)',
                        padding: '0.15rem 0.45rem',
                        borderRadius: 'var(--r-1)',
                        backgroundColor: activeEvent.is_current_observation_supported ? 'rgba(34, 197, 94, 0.12)' : 'rgba(234, 179, 8, 0.12)',
                        border: `1px solid ${activeEvent.is_current_observation_supported ? 'rgba(34, 197, 94, 0.3)' : 'rgba(234, 179, 8, 0.3)'}`,
                        color: activeEvent.is_current_observation_supported ? 'var(--sev-1)' : 'var(--sev-2)',
                        fontWeight: 600,
                      }}
                    >
                      {activeEvent.observation_status_label}
                    </span>
                  )}
                </div>

                {/* Observation Narrative */}
                <div>
                  <div style={{ fontSize: 'var(--text-2xs)', fontFamily: 'var(--font-mono)', color: 'var(--text-muted)', textTransform: 'uppercase', marginBottom: '0.35rem' }}>
                    SITUATION NARRATIVE
                  </div>
                  <div style={{ fontSize: 'var(--text-sm)', color: 'var(--text-body)', lineHeight: 1.6 }}>
                    {activeEvent.description || activeEvent.summary || generateEventNarrative(activeEvent)}
                  </div>
                </div>

                {/* Event Temporal Timeline */}
                <Timeline
                  title="EVENT EVOLUTION TIMELINE"
                  nodes={activeEventTimeline}
                  activeNodeId="t-3"
                />

                {/* Next Action Exploration Controls */}
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', paddingTop: '0.75rem', borderTop: '1px solid var(--border-hairline)' }}>
                  <span style={{ fontSize: 'var(--text-2xs)', fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>
                    ID: {String(activeEvent.id || '').slice(0, 16)}...
                  </span>

                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    <Button
                      variant="secondary"
                      size="sm"
                      onClick={() => navigate(`/map?query=${encodeURIComponent(activeEvent.state || 'India')}`)}
                      icon={<Compass size={12} />}
                    >
                      View on GIS Map
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => navigate(`/reports?state=${encodeURIComponent(activeEvent.state || '')}&category=${encodeURIComponent(activeEvent.category || '')}`)}
                    >
                      Compare Historical Reports
                    </Button>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Full Telemetry Drawer */}
      {drawerOpen && selectedEvent && (
        <EventDetailDrawer
          event={selectedEvent}
          onClose={() => setDrawerOpen(false)}
          onEventUpdated={(upd) => setSelectedEvent(upd)}
        />
      )}
    </div>
  );
};
