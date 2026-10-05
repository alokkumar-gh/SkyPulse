/**
 * SkyPulse Alerts — National Meteorological Warning Center
 * Redesigned according to Section 22:
 * "Alerts should be calm but unmistakable.
 *  Severity should be communicated through:
 *  Typography, Signal bar, Small semantic color — not giant red backgrounds."
 */

import React, { useState, useMemo } from 'react';
import { useEventsStore } from '../store/eventsStore';
import { AlertItem } from '../components/ui/AlertItem';
import { MetricCard } from '../components/ui/MetricCard';
import { SmartFilters, type FilterState } from '../components/ui/SmartFilters';
import { Timeline, type TimelineNode } from '../components/ui/Timeline';
import { buildEventTimeline } from '../utils/timelineBuilder';
import { EventDetailDrawer } from '../components/events/EventDetailDrawer';
import { LiveStatus } from '../components/ui/LiveStatus';
import { AlertTriangle, BellOff, Zap } from 'lucide-react';
import type { WeatherEvent } from '../types';

export const Alerts: React.FC = () => {
  const { events, setSelectedEvent } = useEventsStore();

  const [filters, setFilters] = useState<FilterState>({
    severityMin: 2,
  });
  const [selectedEventForDrawer, setSelectedEventForDrawer] = useState<WeatherEvent | null>(null);

  // Filter events
  const filteredEvents = useMemo(() => {
    return events.filter((e) => {
      if (filters.state && e.state !== filters.state) return false;
      if (filters.category && e.category !== filters.category) return false;
      if (filters.severityMin && e.severity < filters.severityMin) return false;
      return true;
    }).sort((a, b) => b.severity - a.severity);
  }, [events, filters]);

  const extremeCount = events.filter((e) => e.severity === 4).length;
  const severeCount = events.filter((e) => e.severity === 3).length;
  const watchCount = events.filter((e) => e.severity === 2).length;

  // Timeline representation of the highest priority alert sequence from real data
  const topAlert = filteredEvents[0];
  const alertTimelineNodes: TimelineNode[] = useMemo(() => {
    return buildEventTimeline(topAlert);
  }, [topAlert]);

  const handleExplore = (event: WeatherEvent) => {
    setSelectedEvent(event);
    setSelectedEventForDrawer(event);
  };

  return (
    <div className="page-root" style={{ overflow: 'auto' }}>
      {/* ── Page Header ───────────────────────────────────────────────────── */}
      <div className="page-header" style={{ flexWrap: 'wrap', gap: '1rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
          <div>
            <div style={{
              fontFamily: 'var(--font-mono)',
              fontSize: 'var(--text-2xs)',
              color: 'var(--text-muted)',
              letterSpacing: '0.14em',
              textTransform: 'uppercase',
              marginBottom: '0.25rem',
            }}>
              National Civil Warning Center
            </div>
            <h1 className="page-title" style={{ margin: 0 }}>Alert Operations</h1>
          </div>

          <LiveStatus state="LIVE" lastUpdated={new Date()} />
        </div>

        {/* Severity Counts Strip */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: '0.35rem',
            padding: '0.25rem 0.65rem',
            borderRadius: 'var(--r-2)',
            backgroundColor: 'var(--sev-4-dim)',
            border: '1px solid rgba(239,68,68,0.3)',
            color: 'var(--sev-4)',
            fontFamily: 'var(--font-mono)',
            fontSize: 'var(--text-xs)',
            fontWeight: 700,
          }}>
            <AlertTriangle size={12} />
            <span>{extremeCount} EXTREME</span>
          </div>

          <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: '0.35rem',
            padding: '0.25rem 0.65rem',
            borderRadius: 'var(--r-2)',
            backgroundColor: 'var(--sev-3-dim)',
            border: '1px solid rgba(249,115,22,0.3)',
            color: 'var(--sev-3)',
            fontFamily: 'var(--font-mono)',
            fontSize: 'var(--text-xs)',
            fontWeight: 700,
          }}>
            <span>{severeCount} SEVERE</span>
          </div>

          <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: '0.35rem',
            padding: '0.25rem 0.65rem',
            borderRadius: 'var(--r-2)',
            backgroundColor: 'var(--sev-2-dim)',
            border: '1px solid rgba(234,179,8,0.3)',
            color: 'var(--sev-2)',
            fontFamily: 'var(--font-mono)',
            fontSize: 'var(--text-xs)',
            fontWeight: 700,
          }}>
            <span>{watchCount} WATCH</span>
          </div>
        </div>
      </div>

      {/* ── Operational Metric Summary (Section 7) ────────────────────────── */}
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
          label="ACTIVE SEVERE ALERTS"
          value={extremeCount + severeCount}
          comparison={{
            value: 'Level 3 & 4',
            text: 'urgent monitoring',
            sentiment: extremeCount > 0 ? 'negative' : 'warning',
          }}
          source="NDMA CAP Gateway"
          signal={extremeCount > 0 ? 'sev-4' : 'sev-3'}
        />

        <MetricCard
          label="DISASTER WATCHES"
          value={watchCount}
          comparison={{
            value: 'Moderate Hazards',
            text: 'coastal & hilly belts',
            sentiment: 'neutral',
          }}
          source="IMD Cyclone & Flood"
          signal="sev-2"
        />

        <MetricCard
          label="POPULATION AT RISK"
          value="4.2M"
          comparison={{
            value: 'Coastal Districts',
            text: 'Odisha & Andhra',
            sentiment: 'warning',
          }}
          source="Census 2026 Grid"
          signal="teal"
        />

        <MetricCard
          label="STATION CORROBORATION"
          value="94%"
          comparison={{
            value: 'Multi-radar lock',
            text: 'verified signals',
            sentiment: 'positive',
          }}
          source="Ground Radar Network"
          signal="sev-1"
        />
      </div>

      {/* ── Smart Filters (Section 9) ───────────────────────────────────────── */}
      <div style={{ padding: '0.75rem 1.5rem', borderBottom: '1px solid var(--border-hairline)' }}>
        <SmartFilters
          filters={filters}
          onChange={setFilters}
          onReset={() => setFilters({ severityMin: 2 })}
        />
      </div>

      {/* ── Main Content Area ──────────────────────────────────────────────── */}
      <div style={{ padding: '1.5rem', display: 'flex', flexDirection: 'column', gap: '1.5rem', maxWidth: 1080 }}>
        {/* Temporal Evolution Timeline for Top Active Threat */}
        {topAlert && (
          <Timeline
            title={`THREAT EVOLUTION TIMELINE — ${topAlert.title || topAlert.category}`}
            nodes={alertTimelineNodes}
            activeNodeId="node-3"
          />
        )}

        {/* Alerts Feed */}
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.85rem' }}>
            <Zap size={14} color="var(--sev-4)" />
            <span
              style={{
                fontFamily: 'var(--font-mono)',
                fontSize: 'var(--text-xs)',
                fontWeight: 700,
                letterSpacing: '0.1em',
                textTransform: 'uppercase',
                color: 'var(--text-secondary)',
              }}
            >
              Active Meteorological Warnings ({filteredEvents.length})
            </span>
          </div>

          {filteredEvents.length === 0 ? (
            <div
              style={{
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                justifyContent: 'center',
                gap: '0.75rem',
                padding: '4rem 2rem',
                backgroundColor: 'var(--bg-surface)',
                border: '1px solid var(--border-hairline)',
                borderRadius: 'var(--r-2)',
                textAlign: 'center',
              }}
            >
              <BellOff size={28} color="var(--status-verified)" />
              <div style={{ fontSize: 'var(--text-base)', fontWeight: 700, color: 'var(--text-primary)' }}>
                No Active Warnings Matching Filters
              </div>
              <div style={{ fontSize: 'var(--text-xs)', fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>
                All systems nominal across selected parameters. Monitoring continues.
              </div>
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
              {filteredEvents.map((ev) => (
                <AlertItem
                  key={ev.id}
                  id={ev.id}
                  category={ev.category}
                  location={[ev.district, ev.state || 'India'].filter(Boolean).join(', ')}
                  headline={ev.title || `${ev.category} Advisory`}
                  summary={ev.description || `Automated radar detection confirmed severe conditions with confidence index of ${Math.round(ev.confidence_score * 100)}%.`}
                  severity={ev.severity as any}
                  timestamp={ev.updated_at ? new Date(ev.updated_at).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' }) + ' IST' : 'Live'}
                  source={ev.sources_count ? `${ev.sources_count} multi-source feeds` : 'IMD Doppler Radar'}
                  onExplore={() => handleExplore(ev)}
                />
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Contextual Detail Drawer */}
      {selectedEventForDrawer && (
        <EventDetailDrawer
          event={selectedEventForDrawer}
          onClose={() => setSelectedEventForDrawer(null)}
          onEventUpdated={(upd) => setSelectedEventForDrawer(upd)}
        />
      )}
    </div>
  );
};
