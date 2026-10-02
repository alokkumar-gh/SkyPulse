/**
 * LiveMap Page — Geographic Intelligence Console
 * =================================================
 * A map-dominant (85%) view of all active weather events across India.
 * - Full-viewport SkyPulse Map with Google Maps / D3 Radar dual-mode
 * - Compact 280px right panel with event list + quick filters
 * - Category and severity filter chips
 * - Event count badge
 * - No KPI stats, no heavy chrome — pure spatial intelligence
 */
import { useEffect, useState, useMemo } from 'react';
import { SkyPulseMap } from '../components/map/SkyPulseMap';
import { useEventsStore } from '../store/eventsStore';
import { useWebSocket } from '../hooks/useWebSocket';
import type { WeatherEvent } from '../types';
import { SEVERITY_COLORS, CATEGORY_COLORS } from '../types';
import { Radio, Filter, RefreshCw, MapPin, X } from 'lucide-react';

const CATEGORIES = ['CYCLONE', 'FLOOD', 'HEATWAVE', 'LANDSLIDE', 'EARTHQUAKE', 'DROUGHT', 'THUNDERSTORM', 'RAINFALL'];
const SEVERITY_LEVELS = [1, 2, 3, 4];

export const LiveMap: React.FC = () => {
  const { events, selectedEvent, setSelectedEvent, fetchEvents, loading } = useEventsStore();
  const { connectionState } = useWebSocket();
  const [activeCategoryFilter, setActiveCategoryFilter] = useState<string | null>(null);
  const [activeSeverityFilter, setActiveSeverityFilter] = useState<number | null>(null);

  useEffect(() => {
    fetchEvents();
  }, [fetchEvents]);

  const handleSelectEvent = (event: WeatherEvent) => {
    setSelectedEvent(event);
  };

  const filteredEvents = useMemo(() => {
    return events.filter((ev) => {
      if (activeCategoryFilter && ev.category !== activeCategoryFilter) return false;
      if (activeSeverityFilter && ev.severity !== activeSeverityFilter) return false;
      return true;
    });
  }, [events, activeCategoryFilter, activeSeverityFilter]);

  const geoEvents = useMemo(() => {
    return events.filter(
      (ev) => ev.latitude !== undefined && ev.longitude !== undefined && !isNaN(ev.latitude) && !isNaN(ev.longitude)
    );
  }, [events]);

  const isLive = connectionState === 'CONNECTED';

  return (
    <div
      style={{
        display: 'flex',
        height: 'calc(100vh - var(--topbar-height, 56px))',
        backgroundColor: 'var(--bg-primary)',
        overflow: 'hidden',
      }}
    >
      {/* MAP AREA (dominant ~85%) */}
      <div style={{ flex: 1, position: 'relative', overflow: 'hidden' }}>
        {/* Map header bar */}
        <div
          style={{
            position: 'absolute',
            top: 0,
            left: 0,
            right: 0,
            zIndex: 20,
            padding: '0.45rem 1rem',
            backgroundColor: 'rgba(7, 11, 20, 0.85)',
            borderBottom: '1px solid rgba(56, 189, 248, 0.15)',
            backdropFilter: 'blur(8px)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: '0.75rem',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
            <MapPin size={13} style={{ color: '#38bdf8', flexShrink: 0 }} />
            <span
              style={{
                fontSize: '11px',
                fontWeight: 700,
                color: 'var(--text-primary)',
                textTransform: 'uppercase',
                letterSpacing: '0.08em',
              }}
            >
              India Geographic Intelligence
            </span>
            <span style={{ fontSize: '10px', color: 'var(--text-muted)', fontFamily: 'monospace' }}>
              {geoEvents.length} events plotted
            </span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            {isLive && (
              <span
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '0.3rem',
                  fontSize: '10px',
                  fontWeight: 700,
                  color: '#22c55e',
                  fontFamily: 'monospace',
                }}
              >
                <Radio size={10} />
                LIVE
              </span>
            )}
            <button
              onClick={() => fetchEvents()}
              disabled={loading}
              title="Refresh events"
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                backgroundColor: 'rgba(15, 23, 42, 0.6)',
                border: '1px solid var(--bg-border, #334155)',
                borderRadius: '4px',
                color: 'var(--text-primary)',
                padding: '0.3rem',
                cursor: loading ? 'not-allowed' : 'pointer',
              }}
            >
              <RefreshCw
                size={12}
                style={{ animation: loading ? 'spin 1s linear infinite' : 'none' }}
              />
            </button>
          </div>
        </div>

        {/* The Map — full height */}
        <SkyPulseMap
          events={events}
          selectedEventId={selectedEvent?.id}
          onSelectEvent={handleSelectEvent}
        />
      </div>

      {/* RIGHT EVENT PANEL (~280px) */}
      <div
        style={{
          width: '280px',
          flexShrink: 0,
          height: '100%',
          display: 'flex',
          flexDirection: 'column',
          backgroundColor: 'var(--bg-surface)',
          borderLeft: '1px solid var(--bg-border)',
          overflow: 'hidden',
        }}
      >
        {/* Panel header + filters */}
        <div
          style={{
            padding: '0.75rem 1rem',
            borderBottom: '1px solid var(--bg-border)',
            flexShrink: 0,
          }}
        >
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              marginBottom: '0.5rem',
            }}
          >
            <span
              style={{
                fontSize: '11px',
                fontWeight: 700,
                color: 'var(--text-primary)',
                textTransform: 'uppercase',
                letterSpacing: '0.07em',
              }}
            >
              Active Events
            </span>
            <span
              style={{
                fontSize: '10px',
                fontWeight: 700,
                color: '#38bdf8',
                backgroundColor: 'rgba(56, 189, 248, 0.1)',
                border: '1px solid rgba(56, 189, 248, 0.25)',
                borderRadius: '10px',
                padding: '1px 7px',
              }}
            >
              {filteredEvents.length}
            </span>
          </div>

          {/* Severity filter */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', marginBottom: '0.5rem' }}>
            <Filter size={10} style={{ color: 'var(--text-muted)', flexShrink: 0 }} />
            {SEVERITY_LEVELS.map((sev) => (
              <button
                key={sev}
                onClick={() => setActiveSeverityFilter(activeSeverityFilter === sev ? null : sev)}
                title={`Severity ${sev}`}
                style={{
                  width: 20,
                  height: 20,
                  borderRadius: '50%',
                  backgroundColor:
                    activeSeverityFilter === sev ? (SEVERITY_COLORS[sev] || '#eab308') : 'transparent',
                  border: `2px solid ${SEVERITY_COLORS[sev] || '#eab308'}`,
                  color:
                    activeSeverityFilter === sev ? '#fff' : (SEVERITY_COLORS[sev] || '#eab308'),
                  fontSize: '9px',
                  fontWeight: 800,
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  transition: 'background-color 0.1s ease',
                }}
              >
                {sev}
              </button>
            ))}
          </div>

          {/* Category filter chips */}
          <div style={{ display: 'flex', gap: '0.25rem', flexWrap: 'wrap' }}>
            {CATEGORIES.slice(0, 6).map((cat) => (
              <button
                key={cat}
                onClick={() => setActiveCategoryFilter(activeCategoryFilter === cat ? null : cat)}
                style={{
                  fontSize: '9px',
                  fontWeight: 600,
                  padding: '1px 5px',
                  borderRadius: '3px',
                  border: `1px solid ${
                    activeCategoryFilter === cat
                      ? (CATEGORY_COLORS[cat] || '#60a5fa')
                      : 'var(--bg-border)'
                  }`,
                  backgroundColor:
                    activeCategoryFilter === cat
                      ? `${CATEGORY_COLORS[cat] || '#60a5fa'}20`
                      : 'transparent',
                  color:
                    activeCategoryFilter === cat
                      ? (CATEGORY_COLORS[cat] || '#60a5fa')
                      : 'var(--text-muted)',
                  cursor: 'pointer',
                  textTransform: 'uppercase',
                  letterSpacing: '0.04em',
                }}
              >
                {cat.slice(0, 5)}
              </button>
            ))}
          </div>

          {(activeCategoryFilter || activeSeverityFilter) && (
            <button
              onClick={() => {
                setActiveCategoryFilter(null);
                setActiveSeverityFilter(null);
              }}
              style={{
                marginTop: '0.4rem',
                display: 'flex',
                alignItems: 'center',
                gap: '0.25rem',
                fontSize: '10px',
                color: 'var(--text-muted)',
                cursor: 'pointer',
                border: 'none',
                backgroundColor: 'transparent',
                padding: 0,
              }}
            >
              <X size={10} /> Clear filters
            </button>
          )}
        </div>

        {/* Event list */}
        <div style={{ flex: 1, overflowY: 'auto' }}>
          {loading && filteredEvents.length === 0 ? (
            <div
              style={{
                padding: '1.5rem',
                textAlign: 'center',
                fontSize: '11px',
                color: 'var(--text-muted)',
              }}
            >
              Loading events…
            </div>
          ) : filteredEvents.length === 0 ? (
            <div
              style={{
                padding: '1.5rem',
                textAlign: 'center',
                fontSize: '11px',
                color: 'var(--text-muted)',
              }}
            >
              No events match filters.
            </div>
          ) : (
            filteredEvents.map((ev) => {
              const isSelected = selectedEvent?.id === ev.id;
              const severityColor = SEVERITY_COLORS[ev.severity] || '#eab308';
              const hasCoords =
                ev.latitude !== undefined &&
                ev.longitude !== undefined &&
                !isNaN(ev.latitude) &&
                !isNaN(ev.longitude);

              return (
                <div
                  key={ev.id}
                  onClick={() => handleSelectEvent(ev)}
                  style={{
                    padding: '0.6rem 1rem',
                    borderBottom: '1px solid var(--bg-border)',
                    cursor: 'pointer',
                    backgroundColor: isSelected
                      ? 'rgba(56, 189, 248, 0.06)'
                      : 'transparent',
                    borderLeft: isSelected
                      ? `2px solid ${severityColor}`
                      : '2px solid transparent',
                    transition: 'background-color 0.1s ease',
                  }}
                >
                  <div
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      marginBottom: '2px',
                    }}
                  >
                    <span
                      style={{
                        fontSize: '9px',
                        fontWeight: 700,
                        color: CATEGORY_COLORS[ev.category] || '#60a5fa',
                        textTransform: 'uppercase',
                        letterSpacing: '0.05em',
                      }}
                    >
                      {ev.category}
                    </span>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.3rem' }}>
                      {!hasCoords && (
                        <span
                          title="No coordinates — not on map"
                          style={{ fontSize: '9px', color: 'var(--text-muted)', opacity: 0.5 }}
                        >
                          no GPS
                        </span>
                      )}
                      <span
                        style={{
                          width: 16,
                          height: 16,
                          borderRadius: '50%',
                          backgroundColor: severityColor,
                          color: '#fff',
                          fontSize: '9px',
                          fontWeight: 800,
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          flexShrink: 0,
                        }}
                      >
                        {ev.severity}
                      </span>
                    </div>
                  </div>
                  <div
                    style={{
                      fontSize: '11px',
                      fontWeight: 600,
                      color: 'var(--text-primary)',
                      lineHeight: 1.3,
                      marginBottom: '2px',
                      whiteSpace: 'nowrap',
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                    }}
                  >
                    {ev.title || `${ev.category} Event`}
                  </div>
                  <div style={{ fontSize: '10px', color: 'var(--text-muted)' }}>
                    📍 {ev.district ? `${ev.district}, ` : ''}
                    {ev.state || 'India'}
                  </div>
                  <div
                    style={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      marginTop: '3px',
                      fontSize: '9px',
                      color: 'var(--text-muted)',
                    }}
                  >
                    <span>
                      {Math.round((ev.confidence_score || 0) * 100)}% conf
                    </span>
                    <span
                      style={{
                        color:
                          ev.verification_status === 'VERIFIED'
                            ? '#22c55e'
                            : ev.verification_status === 'CONTRADICTED'
                            ? '#ef4444'
                            : '#f59e0b',
                        fontWeight: 600,
                      }}
                    >
                      {ev.verification_status}
                    </span>
                  </div>
                </div>
              );
            })
          )}
        </div>
      </div>
    </div>
  );
};
