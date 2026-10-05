/**
 * SkyPulse Live Geographic Weather Intelligence Map — Third-Pass Polish
 * "An instrument for understanding India's atmosphere."
 *
 * Implements:
 * - 70/30 Spatial Instrument layout
 * - Region / Incident Selection -> Context panel instant update & telemetry highlight
 * - Streamlined top instrument bar (calm, zero visual noise)
 * - Breadcrumb context trail (GEOSPATIAL / INDIA / [STATE])
 * - Single dominant action per state
 */

import React, { useEffect, useState, useMemo, useRef } from 'react';
import { SkyPulseMap } from '../components/map/SkyPulseMap';
import { useEventsStore } from '../store/eventsStore';
import { ErrorBoundary } from '../components/ui/ErrorBoundary';
import { EventDetailDrawer } from '../components/events/EventDetailDrawer';
import { WeatherObservationDrawer } from '../components/events/WeatherObservationDrawer';
import { EventCard } from '../components/events/EventCard';
import { Button } from '../components/ui/Primitives';
import {
  CategoryBadge,
  SeverityBadge,
  VerificationBadge,
} from '../components/ui/Badges';
import type { WeatherEvent, WeatherObservationFeature } from '../types';
import { SEVERITY_COLORS } from '../types';
import {
  MapPin, RefreshCw, PanelRightClose, PanelRightOpen, X,
} from 'lucide-react';

const CATEGORIES = ['CYCLONE', 'FLOODING', 'HEATWAVE', 'THUNDERSTORM', 'RAINFALL', 'FOG', 'STRONG_WINDS'];
const SEVERITY_LEVELS = [1, 2, 3, 4];

export const LiveMap: React.FC = () => {
  const {
    events = [],
    mapEvents = [],
    observations = [],
    coverage,
    selectedEvent,
    selectedEventId,
    setSelectedEvent,
    fetchEvents,
    fetchMapEvents,
    fetchObservations,
    fetchCoverage,
    loading,
  } = useEventsStore();
  const [selectedObservation, setSelectedObservation] = useState<WeatherObservationFeature | null>(null);
  const [layerMode, setLayerMode] = useState<'ALL' | 'EVENTS' | 'WEATHER' | 'WARNINGS' | 'NEWS'>('ALL');
  const [timeRange, setTimeRange] = useState<string>('live');
  const [activeCategoryFilter, setActiveCategoryFilter] = useState<string | null>(null);
  const [activeSeverityFilter, setActiveSeverityFilter] = useState<number | null>(null);
  const [regionalNotice, setRegionalNotice] = useState<string | null>(null);
  const [isMobile, setIsMobile] = useState(() => typeof window !== 'undefined' && window.innerWidth < 768);
  const [feedOpen, setFeedOpen] = useState(() => typeof window === 'undefined' || window.innerWidth >= 768);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const activeCardRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const handleResize = () => setIsMobile(window.innerWidth < 768);
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  useEffect(() => {
    fetchEvents();
    fetchMapEvents({
      time_range: timeRange,
      layers: layerMode === 'ALL' ? undefined : layerMode,
    });
    fetchObservations();
    fetchCoverage();
  }, [fetchEvents, fetchMapEvents, fetchObservations, fetchCoverage, timeRange, layerMode]);

  // Auto-scroll selected card into view
  useEffect(() => {
    if (activeCardRef.current) {
      activeCardRef.current.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }
  }, [selectedEventId]);

  const handleSelectEvent = (event: WeatherEvent) => {
    setSelectedEvent(event);
    const hasCoords =
      event.latitude !== undefined &&
      event.longitude !== undefined &&
      !isNaN(event.latitude) &&
      !isNaN(event.longitude);
    if (!hasCoords) {
      setRegionalNotice(`Regional event (${event.state || 'India'}) · no localized GPS point available.`);
      setTimeout(() => setRegionalNotice(null), 4000);
    } else {
      setRegionalNotice(null);
    }
  };

  const safeEvents = Array.isArray(events) ? events : [];
  const safeMapEvents = Array.isArray(mapEvents) ? mapEvents : [];
  const baseEventsList = safeMapEvents.length > 0 ? safeMapEvents : safeEvents;

  const displayMapEvents = useMemo(() => {
    const now = Date.now();
    let maxAgeMs = Infinity;
    if (timeRange === '1h') maxAgeMs = 1 * 3600 * 1000;
    else if (timeRange === '6h') maxAgeMs = 6 * 3600 * 1000;
    else if (timeRange === '24h' || timeRange === 'live') maxAgeMs = 24 * 3600 * 1000;
    else if (timeRange === '7d') maxAgeMs = 7 * 86400 * 1000;

    return baseEventsList.filter((ev) => {
      if (!ev || !ev.id) return false;
      if (maxAgeMs !== Infinity && ev.first_reported_at) {
        const evTime = new Date(ev.first_reported_at).getTime();
        if (!isNaN(evTime) && now - evTime > maxAgeMs) return false;
      }
      return true;
    });
  }, [baseEventsList, timeRange]);

  const filteredEvents = useMemo(() => {
    const seenIds = new Set<string>();
    return displayMapEvents.filter((ev) => {
      if (!ev || !ev.id) return false;
      if (seenIds.has(ev.id)) return false;
      seenIds.add(ev.id);
      if (activeCategoryFilter && ev.category !== activeCategoryFilter) return false;
      if (activeSeverityFilter && ev.severity !== activeSeverityFilter) return false;
      return true;
    });
  }, [displayMapEvents, activeCategoryFilter, activeSeverityFilter]);

  const plottableCount = displayMapEvents.length;
  const totalActive = coverage?.active_events_count || plottableCount || safeEvents.length;

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'row',
        height: 'calc(100vh - var(--topbar-height))',
        backgroundColor: 'var(--bg-void)',
        overflow: 'hidden',
        position: 'relative',
        width: '100%',
      }}
      className="page-root"
    >
      {/* ── MAP AREA (Dominant 70% viewport) ───────────────────────────────── */}
      <div style={{ flex: 1, position: 'relative', overflow: 'hidden', height: '100%', minWidth: 0 }}>
        {/* Streamlined Top Floating Instrument Bar (Section 11) */}
        <div
          style={{
            position: 'absolute',
            top: '0.75rem',
            left: '0.75rem',
            right: isMobile ? '0.75rem' : '0.75rem',
            zIndex: 20,
            padding: '0.45rem 0.85rem',
            backgroundColor: 'rgba(11, 13, 13, 0.88)',
            border: '1px solid var(--border-hairline)',
            borderRadius: 'var(--r-2)',
            backdropFilter: 'blur(8px)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: '0.5rem',
            boxShadow: '0 8px 32px rgba(0, 0, 0, 0.6)',
          }}
        >
          {/* Left: Atmospheric Instrument Status & Breadcrumb */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
              <span className="pulse-live" style={{ width: 6, height: 6 }} />
              <span
                style={{
                  fontSize: 'var(--text-xs)',
                  fontWeight: 700,
                  color: 'var(--text-primary)',
                  letterSpacing: '0.04em',
                  fontFamily: 'var(--font-sans)',
                  textTransform: 'uppercase',
                }}
              >
                India Geospatial Radar
              </span>
            </div>

            <span style={{ color: 'var(--border-subtle)' }}>/</span>

            <span
              style={{
                fontFamily: 'var(--font-mono)',
                fontSize: 'var(--text-2xs)',
                color: 'var(--teal)',
                fontWeight: 600,
              }}
            >
              {coverage?.active_events_count ?? plottableCount} ACTIVE EVENTS
            </span>

            <span className="hide-mobile" style={{ color: 'var(--border-subtle)' }}>·</span>

            <span
              className="hide-mobile"
              style={{
                fontFamily: 'var(--font-mono)',
                fontSize: 'var(--text-2xs)',
                color: 'var(--text-secondary)',
              }}
            >
              {coverage?.current_observations_count ?? observations.length} AWS STATIONS
            </span>

            <span className="hide-tablet" style={{ color: 'var(--border-subtle)' }}>·</span>

            <span
              className="hide-tablet"
              style={{
                fontFamily: 'var(--font-mono)',
                fontSize: 'var(--text-2xs)',
                color: 'var(--text-muted)',
              }}
            >
              {coverage?.states_represented ?? coverage?.states_covered ?? 36}/36 STATES ACTIVE
            </span>
          </div>

          {/* Right: Layer Mode [ ALL | EVENTS | WEATHER | WARNINGS | NEWS ] + Time Filter [ LIVE | 1H | 6H | 24H | 7D | ALL ] */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap' }}>
            {/* Time Filter Presets (Section 32) */}
            <div
              className="hide-mobile"
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '2px',
                backgroundColor: 'var(--bg-panel)',
                padding: '2px',
                borderRadius: 'var(--r-1)',
                border: '1px solid var(--border-hairline)',
              }}
            >
              {[
                { id: 'live', label: 'LIVE' },
                { id: '1h', label: '1H' },
                { id: '6h', label: '6H' },
                { id: '24h', label: '24H' },
                { id: '7d', label: '7D' },
                { id: 'all', label: 'ALL' },
              ].map((t) => {
                const isSelected = timeRange === t.id;
                return (
                  <button
                    key={t.id}
                    onClick={() => setTimeRange(t.id)}
                    style={{
                      padding: '0.15rem 0.45rem',
                      borderRadius: 'var(--r-1)',
                      border: 'none',
                      backgroundColor: isSelected ? 'var(--teal-100)' : 'transparent',
                      color: isSelected ? 'var(--teal)' : 'var(--text-muted)',
                      fontSize: 'var(--text-2xs)',
                      fontFamily: 'var(--font-mono)',
                      fontWeight: isSelected ? 700 : 500,
                      cursor: 'pointer',
                      transition: 'all 0.12s ease',
                    }}
                    title={`Time window: ${t.label}`}
                  >
                    {t.label}
                  </button>
                );
              })}
            </div>

            {/* Layer Mode Toggle (Section 21: [ ALL | EVENTS | WEATHER | WARNINGS | NEWS ]) */}
            <div
              className="hide-mobile"
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '2px',
                backgroundColor: 'var(--bg-panel)',
                padding: '2px',
                borderRadius: 'var(--r-1)',
                border: '1px solid var(--border-hairline)',
              }}
            >
              {(['ALL', 'EVENTS', 'WEATHER', 'WARNINGS', 'NEWS'] as const).map((mode) => {
                const isSelected = layerMode === mode;
                return (
                  <button
                    key={mode}
                    onClick={() => setLayerMode(mode)}
                    style={{
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: '4px',
                      backgroundColor: isSelected ? 'var(--teal-100)' : 'transparent',
                      border: 'none',
                      borderRadius: 'var(--r-1)',
                      color: isSelected ? 'var(--teal)' : 'var(--text-muted)',
                      padding: '0.15rem 0.45rem',
                      fontSize: 'var(--text-2xs)',
                      cursor: 'pointer',
                      fontFamily: 'var(--font-mono)',
                      fontWeight: isSelected ? 700 : 500,
                    }}
                  >
                    <span>●</span>
                    <span>{mode}</span>
                  </button>
                );
              })}
            </div>

            <button
              onClick={() => {
                fetchEvents();
                fetchMapEvents({
                  time_range: timeRange,
                  layers: layerMode === 'ALL' ? undefined : layerMode,
                });
                fetchObservations();
                fetchCoverage();
              }}
              disabled={loading}
              title="Refresh national telemetry"
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                backgroundColor: 'var(--bg-elevated)',
                border: '1px solid var(--border-hairline)',
                borderRadius: 'var(--r-1)',
                color: 'var(--text-primary)',
                padding: '0.3rem',
                cursor: loading ? 'not-allowed' : 'pointer',
              }}
            >
              <RefreshCw
                size={12}
                className={loading ? 'sp-spin' : ''}
              />
            </button>

            {/* Toggle Feed Panel */}
            <button
              onClick={() => setFeedOpen(!feedOpen)}
              title={feedOpen ? 'Collapse side panel' : 'Expand side panel'}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '0.3rem',
                padding: '0.25rem 0.55rem',
                borderRadius: 'var(--r-1)',
                backgroundColor: feedOpen ? 'var(--teal-100)' : 'var(--bg-elevated)',
                border: `1px solid ${feedOpen ? 'var(--border-teal)' : 'var(--border-hairline)'}`,
                color: feedOpen ? 'var(--teal)' : 'var(--text-secondary)',
                fontSize: 'var(--text-2xs)',
                fontFamily: 'var(--font-mono)',
                cursor: 'pointer',
              }}
            >
              {feedOpen ? <PanelRightClose size={12} /> : <PanelRightOpen size={12} />}
              <span>{feedOpen ? 'FEED' : 'EXPAND'}</span>
            </button>
          </div>
        </div>

        {/* Regional Notice Floating Banner */}
        {regionalNotice && (
          <div
            style={{
              position: 'absolute',
              top: '3.5rem',
              left: '50%',
              transform: 'translateX(-50%)',
              zIndex: 30,
              padding: '0.4rem 0.9rem',
              backgroundColor: 'var(--bg-elevated)',
              border: '1px solid var(--border-subtle)',
              borderRadius: 'var(--r-full)',
              color: 'var(--text-secondary)',
              fontSize: 'var(--text-xs)',
              fontFamily: 'var(--font-mono)',
              boxShadow: '0 8px 24px rgba(0, 0, 0, 0.6)',
              animation: 'fade-in 0.15s ease-out',
            }}
          >
            {regionalNotice}
          </div>
        )}

        {/* Map Canvas */}
        <ErrorBoundary isolate fallbackTitle="Geographic Intelligence Map Error">
          <SkyPulseMap
            events={displayMapEvents}
            observations={observations}
            showObservations={layerMode === 'ALL' || layerMode === 'WEATHER'}
            showIncidents={layerMode === 'ALL' || layerMode === 'EVENTS'}
            showWarnings={layerMode === 'ALL' || layerMode === 'WARNINGS'}
            totalEventsCount={totalActive}
            selectedEventId={selectedEventId}
            selectedObservation={selectedObservation}
            onSelectEvent={handleSelectEvent}
            onSelectObservation={(obs) => {
              setSelectedObservation(obs);
              setSelectedEvent(null);
            }}
          />
        </ErrorBoundary>
      </div>

      {/* ── CONTEXTUAL INTELLIGENCE PANEL (30% viewport or mobile drawer) ───────────────────── */}
      <div
        style={{
          width: isMobile ? (feedOpen ? 'min(360px, 94vw)' : 0) : (feedOpen ? '360px' : 0),
          position: isMobile ? 'absolute' : 'relative',
          top: 0,
          right: 0,
          bottom: 0,
          flexShrink: 0,
          height: '100%',
          display: 'flex',
          flexDirection: 'column',
          backgroundColor: 'var(--bg-surface)',
          borderLeft: feedOpen ? '1px solid var(--border-hairline)' : 'none',
          overflow: 'hidden',
          transition: 'width 0.22s var(--ease-out-expo)',
          zIndex: 35,
          boxShadow: isMobile && feedOpen ? '-8px 0 32px rgba(0, 0, 0, 0.8)' : 'none',
        }}
      >
        {/* Contextual Breadcrumb Header */}
        <div
          style={{
            padding: '0.75rem 1rem',
            borderBottom: '1px solid var(--border-hairline)',
            backgroundColor: 'var(--bg-panel)',
            display: 'flex',
            flexDirection: 'column',
            gap: '0.5rem',
            flexShrink: 0,
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', fontFamily: 'var(--font-mono)', fontSize: 'var(--text-2xs)', color: 'var(--text-muted)' }}>
              <span>GEOSPATIAL</span>
              <span>/</span>
              <span style={{ color: 'var(--teal)' }}>INDIA HAZARDS</span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <span
                style={{
                  fontFamily: 'var(--font-mono)',
                  fontSize: 'var(--text-2xs)',
                  fontWeight: 700,
                  color: 'var(--text-secondary)',
                }}
              >
                {filteredEvents.length} INCIDENTS
              </span>
              {isMobile && (
                <button
                  onClick={() => setFeedOpen(false)}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    padding: '0.2rem',
                    background: 'none',
                    border: 'none',
                    color: 'var(--text-muted)',
                    cursor: 'pointer',
                  }}
                  aria-label="Close panel"
                >
                  <X size={14} />
                </button>
              )}
            </div>
          </div>

          {/* Quick Filter Strip: Severity & Categories */}
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '0.5rem' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
              <span style={{ fontSize: 'var(--text-2xs)', fontFamily: 'var(--font-mono)', color: 'var(--text-muted)', marginRight: '2px' }}>
                SEV:
              </span>
              {SEVERITY_LEVELS.map((sev) => {
                const isSelected = activeSeverityFilter === sev;
                const col = SEVERITY_COLORS[sev] || 'var(--teal)';
                return (
                  <button
                    key={sev}
                    onClick={() => setActiveSeverityFilter(isSelected ? null : sev)}
                    style={{
                      width: 20,
                      height: 20,
                      borderRadius: 'var(--r-1)',
                      backgroundColor: isSelected ? col : 'var(--bg-surface)',
                      border: `1px solid ${col}`,
                      color: isSelected ? 'var(--ink)' : col,
                      fontSize: 'var(--text-2xs)',
                      fontWeight: 800,
                      cursor: 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      transition: 'all 0.12s ease',
                    }}
                    title={`Severity ${sev}`}
                  >
                    {sev}
                  </button>
                );
              })}
            </div>

            <div style={{ display: 'flex', gap: '0.2rem', overflowX: 'auto' }}>
              {CATEGORIES.slice(0, 3).map((cat) => {
                const isSelected = activeCategoryFilter === cat;
                return (
                  <button
                    key={cat}
                    onClick={() => setActiveCategoryFilter(isSelected ? null : cat)}
                    style={{
                      padding: '0.1rem 0.4rem',
                      borderRadius: 'var(--r-1)',
                      fontSize: 'var(--text-2xs)',
                      fontFamily: 'var(--font-mono)',
                      fontWeight: isSelected ? 700 : 500,
                      cursor: 'pointer',
                      backgroundColor: isSelected ? 'var(--teal-100)' : 'transparent',
                      border: `1px solid ${isSelected ? 'var(--border-teal)' : 'var(--border-hairline)'}`,
                      color: isSelected ? 'var(--teal)' : 'var(--text-secondary)',
                    }}
                  >
                    {cat}
                  </button>
                );
              })}
            </div>
          </div>
        </div>

        {/* Selected Incident Intelligence Card (Mandate 12: Region Selected Experience) */}
        {selectedEvent && (
          <div
            style={{
              padding: '1rem',
              backgroundColor: 'var(--bg-elevated)',
              borderBottom: '1px solid var(--border-subtle)',
              borderLeft: `3px solid ${SEVERITY_COLORS[selectedEvent.severity] || 'var(--teal)'}`,
              display: 'flex',
              flexDirection: 'column',
              gap: '0.5rem',
              animation: 'fade-in 0.15s ease-out',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
                <CategoryBadge category={selectedEvent.category} />
                <SeverityBadge severity={selectedEvent.severity} />
              </div>
              <VerificationBadge status={selectedEvent.verification_status} />
            </div>

            <div style={{ fontSize: 'var(--text-sm)', fontWeight: 700, color: 'var(--text-primary)', fontFamily: 'var(--font-sans)', lineHeight: 1.3 }}>
              {selectedEvent.title || `${selectedEvent.category} Incident`}
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: '0.45rem', fontSize: 'var(--text-2xs)', fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>
              <MapPin size={11} color="var(--teal)" />
              <span>{selectedEvent.district ? `${selectedEvent.district}, ` : ''}{selectedEvent.state || 'India'}</span>
              <span>·</span>
              <span>Confidence {Math.round(selectedEvent.confidence_score * 100)}%</span>
            </div>

            {/* Dominant Action for Map Inspector */}
            <div style={{ marginTop: '0.25rem' }}>
              <Button
                variant="teal"
                size="xs"
                onClick={() => setDrawerOpen(true)}
                withArrow
                style={{ width: '100%', justifyContent: 'center' }}
              >
                INSPECT FULL DOSSIER
              </Button>
            </div>
          </div>
        )}

        {/* Scrollable Event & Observation Feed */}
        <div style={{ flex: 1, overflowY: 'auto', padding: '0.75rem' }} className="scroll-area">
          {layerMode === 'WEATHER' ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.6rem' }}>
              <div style={{ fontSize: 'var(--text-2xs)', fontFamily: 'var(--font-mono)', color: 'var(--teal)', fontWeight: 700, paddingBottom: '0.25rem' }}>
                LIVE WEATHER TELEMETRY ({observations.length} STATIONS)
              </div>
              {observations.map((obs) => (
                <div
                  key={`obs-feed-${obs.id}`}
                  onClick={() => setSelectedObservation(obs)}
                  style={{
                    padding: '0.75rem',
                    backgroundColor: 'var(--bg-elevated)',
                    border: '1px solid var(--border-hairline)',
                    borderRadius: 'var(--r-1)',
                    borderLeft: '3px solid var(--teal)',
                    cursor: 'pointer',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '0.4rem',
                    transition: 'all 0.12s ease',
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <span style={{ fontWeight: 700, fontSize: 'var(--text-xs)', color: 'var(--text-primary)' }}>
                      {obs.name || obs.city || 'Station'}, {obs.state}
                    </span>
                    <span style={{ fontSize: 'var(--text-2xs)', fontFamily: 'var(--font-mono)', color: 'var(--teal)', fontWeight: 700 }}>
                      {obs.weather_icon || '⛅'} {obs.temp_label}
                    </span>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 'var(--text-2xs)', fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>
                    <span>{obs.condition || 'Fair'} · {obs.humidity_percent != null ? `${obs.humidity_percent}% hum` : ''}</span>
                    <span>{obs.freshness_label || 'Live'}</span>
                  </div>
                </div>
              ))}
            </div>
          ) : filteredEvents.length === 0 ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', padding: '0.5rem 0.25rem' }}>
              {/* Fallback Meteorological Observation Card (Requirements 20 & 22) */}
              {observations.length > 0 ? (
                (() => {
                  const fallbackObs = selectedObservation || observations[0];
                  return (
                    <div
                      style={{
                        padding: '1rem',
                        backgroundColor: 'var(--bg-elevated)',
                        border: '1px solid var(--border-hairline)',
                        borderRadius: 'var(--r-2)',
                        borderLeft: '3px solid var(--teal)',
                        display: 'flex',
                        flexDirection: 'column',
                        gap: '0.65rem',
                      }}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                        <span style={{ fontSize: 'var(--text-2xs)', fontFamily: 'var(--font-mono)', fontWeight: 700, color: 'var(--teal)', letterSpacing: '0.08em' }}>
                          ROUTINE WEATHER TELEMETRY
                        </span>
                        <span style={{ fontSize: 'var(--text-2xs)', fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>
                          {fallbackObs.freshness_label || 'Observed recently'}
                        </span>
                      </div>

                      <div style={{ fontSize: 'var(--text-sm)', fontWeight: 700, color: 'var(--text-primary)', fontFamily: 'var(--font-sans)' }}>
                        {fallbackObs.name || fallbackObs.city || 'Regional Station'}, {fallbackObs.state}
                      </div>

                      <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-secondary)' }}>
                        No active severe weather incidents. Displaying live station telemetry:
                      </div>

                      <div style={{
                        display: 'grid',
                        gridTemplateColumns: 'repeat(2, 1fr)',
                        gap: '0.5rem',
                        backgroundColor: 'var(--bg-panel)',
                        padding: '0.6rem 0.75rem',
                        borderRadius: 'var(--r-1)',
                        border: '1px solid var(--border-hairline)',
                        fontSize: 'var(--text-xs)',
                        fontFamily: 'var(--font-mono)',
                      }}>
                        <div>Temp: <strong style={{ color: 'var(--text-primary)' }}>{fallbackObs.temperature_c != null ? `${fallbackObs.temperature_c}°C` : '--'}</strong></div>
                        <div>Humidity: <strong style={{ color: 'var(--text-primary)' }}>{fallbackObs.humidity_percent != null ? `${fallbackObs.humidity_percent}%` : '--'}</strong></div>
                        <div>Wind: <strong style={{ color: 'var(--text-primary)' }}>{fallbackObs.wind_speed_kmh != null ? `${fallbackObs.wind_speed_kmh} km/h` : '--'}</strong></div>
                        <div>Rainfall: <strong style={{ color: 'var(--text-primary)' }}>{fallbackObs.rain_mm != null ? `${fallbackObs.rain_mm} mm` : '0.0 mm'}</strong></div>
                      </div>

                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontSize: 'var(--text-2xs)', fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>
                        <span>Condition: {fallbackObs.weather_icon || '⛅'} {fallbackObs.condition || 'Fair'}</span>
                        <span>Source: {fallbackObs.source || 'Open-Meteo'}</span>
                      </div>
                    </div>
                  );
                })()
              ) : (
                <div
                  style={{
                    padding: '2.5rem 1rem',
                    textAlign: 'center',
                    backgroundColor: 'var(--bg-panel)',
                    borderRadius: 'var(--r-2)',
                    border: '1px solid var(--border-hairline)',
                  }}
                >
                  <div style={{ fontSize: 'var(--text-xs)', fontFamily: 'var(--font-mono)', color: 'var(--text-secondary)', fontWeight: 700, letterSpacing: '0.08em' }}>
                    NO CURRENT TELEMETRY
                  </div>
                  <div style={{ fontSize: 'var(--text-2xs)', color: 'var(--text-muted)', marginTop: '0.35rem' }}>
                    No active severe weather incidents or routine observations available for current criteria.
                  </div>
                </div>
              )}
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.6rem' }}>
              {filteredEvents.map((ev) => {
                const isSelected = selectedEventId === ev.id || selectedEvent?.id === ev.id;
                return (
                  <div
                    key={ev.id}
                    ref={isSelected ? activeCardRef : null}
                    style={{ position: 'relative' }}
                  >
                    <EventCard
                      event={ev}
                      isSelected={isSelected}
                      onClick={handleSelectEvent}
                      compact
                    />
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>

      {/* Drawers */}
      {drawerOpen && selectedEvent && (
        <ErrorBoundary isolate fallbackTitle="Event Detail Drawer Error">
          <EventDetailDrawer
            event={selectedEvent}
            onClose={() => setDrawerOpen(false)}
            onEventUpdated={(upd) => setSelectedEvent(upd)}
          />
        </ErrorBoundary>
      )}

      {selectedObservation && (
        <ErrorBoundary isolate fallbackTitle="Observation Detail Drawer Error">
          <WeatherObservationDrawer
            observation={selectedObservation}
            isOpen={Boolean(selectedObservation)}
            onClose={() => setSelectedObservation(null)}
          />
        </ErrorBoundary>
      )}
    </div>
  );
};
