/**
 * Dashboard Page — Phase 7
 * Primary operational view for SkyPulse: India's Real-Time Pulse of Weather Intelligence.
 * Composes:
 * - Top KPI Bar (Active Events, Severe Alerts, Verification Rate, Ingestion Volume)
 * - Google Maps JavaScript API Interactive India Map
 * - Live Event Feed with quick filters & search
 * - Event Detail Drawer with DWEG signals & analyst verification controls
 */
import { useEffect, useState } from 'react';
import { SkyPulseMap } from '../components/map/SkyPulseMap';
import { EventFeed } from '../components/events/EventFeed';
import { EventDetailDrawer } from '../components/events/EventDetailDrawer';
import { KPIBar } from '../components/dashboard/KPIBar';
import { TimeRangeSelector } from '../components/ui/Filters';
import { useEventsStore } from '../store/eventsStore';
import { useFiltersStore } from '../store/filtersStore';
import { useWebSocket } from '../hooks/useWebSocket';
import type { WeatherEvent } from '../types';
import { RefreshCw, Radio } from 'lucide-react';

export const Dashboard: React.FC = () => {
  const { events, selectedEvent, setSelectedEvent, fetchEvents, loading } = useEventsStore();
  const { filters, timeRange, setTimeRange } = useFiltersStore();
  const [drawerOpen, setDrawerOpen] = useState(false);

  // Initialize WebSocket connection for live updates
  const { isConnected } = useWebSocket();

  useEffect(() => {
    fetchEvents(filters);
  }, [fetchEvents, filters]);

  const handleSelectEvent = (event: WeatherEvent) => {
    setSelectedEvent(event);
    setDrawerOpen(true);
  };

  const handleCloseDrawer = () => {
    setDrawerOpen(false);
  };

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        height: 'calc(100vh - var(--topbar-height, 56px))',
        backgroundColor: 'var(--bg-primary)',
        overflow: 'hidden',
      }}
    >
      {/* Top Filter & Control Header */}
      <div
        style={{
          padding: '0.75rem 1.25rem',
          backgroundColor: 'var(--bg-surface)',
          borderBottom: '1px solid var(--bg-border)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: '1rem',
          flexWrap: 'wrap',
          zIndex: 5,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
          <div>
            <h2 style={{ margin: 0, fontSize: 'var(--text-lg)', fontWeight: 700, color: 'var(--text-primary)' }}>
              National Weather Situation Room
            </h2>
            <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-muted)' }}>
              India Real-Time Spatial Radar & Multi-Source Intelligence
            </div>
          </div>
          {isConnected && (
            <span
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '0.35rem',
                fontSize: 'var(--text-xs)',
                color: 'var(--severity-1)',
                padding: '0.2rem 0.5rem',
                borderRadius: 'var(--radius-full)',
                backgroundColor: 'rgba(34, 197, 94, 0.12)',
                border: '1px solid rgba(34, 197, 94, 0.3)',
              }}
            >
              <Radio size={12} />
              <span>Live Stream Active</span>
            </span>
          )}
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          <TimeRangeSelector value={timeRange} onChange={setTimeRange} />

          <button
            onClick={() => fetchEvents()}
            disabled={loading}
            title="Refresh events"
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              backgroundColor: 'var(--bg-elevated)',
              border: '1px solid var(--bg-border)',
              borderRadius: 'var(--radius-md)',
              color: 'var(--text-primary)',
              padding: '0.45rem',
              cursor: loading ? 'not-allowed' : 'pointer',
            }}
          >
            <RefreshCw
              size={14}
              style={{
                animation: loading ? 'spin 1s linear infinite' : 'none',
              }}
            />
          </button>
        </div>
      </div>

      {/* KPI Stats Ribbon */}
      <div style={{ padding: '0.75rem 1.25rem', borderBottom: '1px solid var(--bg-border)' }}>
        <KPIBar events={events} loading={loading} />
      </div>

      {/* Main Content: Map + Live Event Feed */}
      <div style={{ display: 'flex', flex: 1, position: 'relative', overflow: 'hidden' }}>
        {/* Map Area */}
        <div style={{ flex: 1, position: 'relative', height: '100%' }}>
          <SkyPulseMap
            events={events}
            selectedEventId={selectedEvent?.id}
            onSelectEvent={handleSelectEvent}
          />
        </div>

        {/* Live Event Feed Docked to Right */}
        <div style={{ width: '380px', height: '100%', zIndex: 10 }}>
          <EventFeed
            events={events}
            selectedEventId={selectedEvent?.id}
            onSelectEvent={handleSelectEvent}
            loading={loading}
          />
        </div>

        {/* Slide-out Event Detail Drawer */}
        {drawerOpen && selectedEvent && (
          <EventDetailDrawer
            event={selectedEvent}
            onClose={handleCloseDrawer}
            onEventUpdated={(upd) => setSelectedEvent(upd)}
          />
        )}
      </div>
    </div>
  );
};
