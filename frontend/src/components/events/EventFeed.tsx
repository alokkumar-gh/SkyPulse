/**
 * EventFeed — Phase 7
 * Real-time weather event stream.
 * Displays live incoming events, quick category filters, search input,
 * and empty/loading states.
 */
import { useState, useMemo } from 'react';
import type { WeatherEvent } from '../../types';
import { EventCard } from './EventCard';
import { SkeletonCard } from '../ui/Skeleton';
import { EmptyState } from '../ui/States';
import { Search, Flame, ShieldAlert, CheckCircle2, Zap } from 'lucide-react';
import { EmergingEventsPanel } from './EmergingEventsPanel';

interface EventFeedProps {
  events: WeatherEvent[];
  selectedEventId?: string | null;
  onSelectEvent: (event: WeatherEvent) => void;
  loading?: boolean;
}

type QuickFilter = 'all' | 'severe' | 'unverified' | 'verified';

export const EventFeed: React.FC<EventFeedProps> = ({
  events,
  selectedEventId,
  onSelectEvent,
  loading = false,
}) => {
  const [viewMode, setViewMode] = useState<'canonical' | 'emerging'>('canonical');
  const [search, setSearch] = useState('');
  const [quickFilter, setQuickFilter] = useState<QuickFilter>('all');

  const filteredEvents = useMemo(() => {
    return events.filter((ev) => {
      // Search matching
      if (search.trim()) {
        const query = search.toLowerCase();
        const matchesTitle = ev.title?.toLowerCase().includes(query);
        const matchesCategory = ev.category.toLowerCase().includes(query);
        const matchesState = ev.state?.toLowerCase().includes(query);
        const matchesDistrict = ev.district?.toLowerCase().includes(query);
        if (!matchesTitle && !matchesCategory && !matchesState && !matchesDistrict) {
          return false;
        }
      }

      // Quick filter
      if (quickFilter === 'severe') {
        return ev.severity >= 3;
      }
      if (quickFilter === 'unverified') {
        return ev.verification_status === 'UNVERIFIED' || ev.verification_status === 'UNDER_REVIEW';
      }
      if (quickFilter === 'verified') {
        return ev.verification_status === 'VERIFIED';
      }

      return true;
    });
  }, [events, search, quickFilter]);

  const severeCount = events.filter((e) => e.severity >= 3).length;
  const unverifiedCount = events.filter(
    (e) => e.verification_status === 'UNVERIFIED' || e.verification_status === 'UNDER_REVIEW'
  ).length;

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        height: '100%',
        backgroundColor: 'var(--bg-surface)',
        borderLeft: '1px solid var(--bg-border)',
        overflow: 'hidden',
      }}
    >
      {/* Feed Header */}
      <div
        style={{
          padding: '1rem',
          borderBottom: '1px solid var(--bg-border)',
          display: 'flex',
          flexDirection: 'column',
          gap: '0.75rem',
        }}
      >
        {/* Mode Switcher */}
        <div style={{ display: 'flex', backgroundColor: 'var(--bg-primary)', borderRadius: 'var(--radius-md)', padding: '2px', border: '1px solid var(--bg-border)' }}>
          <button
            onClick={() => setViewMode('canonical')}
            style={{
              flex: 1,
              padding: '0.35rem 0.5rem',
              borderRadius: 'var(--radius-sm)',
              border: 'none',
              cursor: 'pointer',
              fontSize: 'var(--text-xs)',
              fontWeight: viewMode === 'canonical' ? 600 : 400,
              backgroundColor: viewMode === 'canonical' ? 'var(--bg-elevated)' : 'transparent',
              color: viewMode === 'canonical' ? 'var(--text-primary)' : 'var(--text-secondary)',
              transition: 'all 0.15s ease',
            }}
          >
            Live Events ({events.length})
          </button>
          <button
            onClick={() => setViewMode('emerging')}
            style={{
              flex: 1,
              padding: '0.35rem 0.5rem',
              borderRadius: 'var(--radius-sm)',
              border: 'none',
              cursor: 'pointer',
              fontSize: 'var(--text-xs)',
              fontWeight: viewMode === 'emerging' ? 600 : 400,
              backgroundColor: viewMode === 'emerging' ? 'rgba(249, 115, 22, 0.15)' : 'transparent',
              color: viewMode === 'emerging' ? '#f97316' : 'var(--text-secondary)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '0.25rem',
              transition: 'all 0.15s ease',
            }}
          >
            <Zap size={12} />
            <span>Emerging Signals</span>
          </button>
        </div>

        {viewMode === 'canonical' && (
          <>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <span
                  style={{
                    width: 8,
                    height: 8,
                    borderRadius: '50%',
                    backgroundColor: 'var(--severity-1)',
                    animation: 'pulse 1.5s infinite',
                  }}
                />
                <h3 style={{ margin: 0, fontSize: 'var(--text-base)', fontWeight: 600, color: 'var(--text-primary)' }}>
                  Live Event Feed
                </h3>
              </div>
              <span
                style={{
                  fontSize: 'var(--text-xs)',
                  padding: '0.15rem 0.5rem',
                  borderRadius: 'var(--radius-full)',
                  backgroundColor: 'var(--bg-elevated)',
                  color: 'var(--text-secondary)',
                }}
              >
                {filteredEvents.length} events
              </span>
            </div>

            {/* Search */}
            <div style={{ position: 'relative' }}>
              <Search
                size={14}
                style={{ position: 'absolute', left: '0.65rem', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }}
              />
              <input
                type="text"
                placeholder="Search state, district, type..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                style={{
                  width: '100%',
                  backgroundColor: 'var(--bg-primary)',
                  border: '1px solid var(--bg-border)',
                  borderRadius: 'var(--radius-md)',
                  color: 'var(--text-primary)',
                  padding: '0.4rem 0.6rem 0.4rem 2rem',
                  fontSize: 'var(--text-xs)',
                  outline: 'none',
                }}
              />
            </div>

            {/* Filter Pills */}
            <div style={{ display: 'flex', gap: '0.35rem', overflowX: 'auto', paddingBottom: '2px' }}>
              <button
                onClick={() => setQuickFilter('all')}
                style={{
                  padding: '0.25rem 0.55rem',
                  borderRadius: 'var(--radius-full)',
                  fontSize: 'var(--text-xs)',
                  fontWeight: 500,
                  border: 'none',
                  cursor: 'pointer',
                  backgroundColor: quickFilter === 'all' ? 'var(--brand-blue)' : 'var(--bg-elevated)',
                  color: quickFilter === 'all' ? '#fff' : 'var(--text-secondary)',
                  whiteSpace: 'nowrap',
                }}
              >
                All ({events.length})
              </button>

              <button
                onClick={() => setQuickFilter('severe')}
                style={{
                  padding: '0.25rem 0.55rem',
                  borderRadius: 'var(--radius-full)',
                  fontSize: 'var(--text-xs)',
                  fontWeight: 500,
                  border: 'none',
                  cursor: 'pointer',
                  backgroundColor: quickFilter === 'severe' ? 'var(--severity-4)' : 'var(--bg-elevated)',
                  color: quickFilter === 'severe' ? '#fff' : 'var(--severity-4)',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.25rem',
                  whiteSpace: 'nowrap',
                }}
              >
                <Flame size={12} />
                Severe ({severeCount})
              </button>

              <button
                onClick={() => setQuickFilter('unverified')}
                style={{
                  padding: '0.25rem 0.55rem',
                  borderRadius: 'var(--radius-full)',
                  fontSize: 'var(--text-xs)',
                  fontWeight: 500,
                  border: 'none',
                  cursor: 'pointer',
                  backgroundColor: quickFilter === 'unverified' ? 'var(--status-review)' : 'var(--bg-elevated)',
                  color: quickFilter === 'unverified' ? '#fff' : 'var(--status-review)',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.25rem',
                  whiteSpace: 'nowrap',
                }}
              >
                <ShieldAlert size={12} />
                Review ({unverifiedCount})
              </button>

              <button
                onClick={() => setQuickFilter('verified')}
                style={{
                  padding: '0.25rem 0.55rem',
                  borderRadius: 'var(--radius-full)',
                  fontSize: 'var(--text-xs)',
                  fontWeight: 500,
                  border: 'none',
                  cursor: 'pointer',
                  backgroundColor: quickFilter === 'verified' ? 'var(--status-verified)' : 'var(--bg-elevated)',
                  color: quickFilter === 'verified' ? '#fff' : 'var(--status-verified)',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.25rem',
                  whiteSpace: 'nowrap',
                }}
              >
                <CheckCircle2 size={12} />
                Verified
              </button>
            </div>
          </>
        )}
      </div>

      {/* Body Content */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '0.75rem' }}>
        {viewMode === 'emerging' ? (
          <EmergingEventsPanel />
        ) : (
          <>
            {loading && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                <SkeletonCard />
                <SkeletonCard />
                <SkeletonCard />
              </div>
            )}

            {!loading && filteredEvents.length === 0 && (
              <EmptyState
                title="No Events Found"
                description={
                  search
                    ? `No weather events matching "${search}".`
                    : 'No weather events match the selected filters.'
                }
              />
            )}

            {!loading && filteredEvents.length > 0 && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                {filteredEvents.map((ev) => (
                  <EventCard
                    key={ev.id}
                    event={ev}
                    isSelected={selectedEventId === ev.id}
                    onClick={() => onSelectEvent(ev)}
                  />
                ))}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
};

