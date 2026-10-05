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
      // Search matching across all factual fields
      if (search.trim()) {
        const query = search.toLowerCase();
        const matches = [
          ev.title,
          ev.summary,
          ev.description,
          ev.category,
          ev.sub_category,
          ev.state,
          ev.district,
          ev.city,
          ev.source,
          ev.location?.city,
          ev.location?.district,
          ev.location?.state,
        ]
          .filter(Boolean)
          .some((val) => String(val).toLowerCase().includes(query));

        if (!matches) {
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
        overflow: 'hidden',
      }}
    >
      {/* Feed Header */}
      <div
        style={{
          padding: '0.75rem 1rem',
          borderBottom: '1px solid var(--border-hairline)',
          display: 'flex',
          flexDirection: 'column',
          gap: '0.625rem',
        }}
      >
        {/* Mode Switcher */}
        <div style={{ display: 'flex', background: 'var(--bg-panel)', borderRadius: 'var(--r-2)', padding: '2px', border: '1px solid var(--border-hairline)' }}>
          <button
            onClick={() => setViewMode('canonical')}
            style={{
              flex: 1,
              padding: '0.3rem 0.5rem',
              borderRadius: 'var(--r-1)',
              border: 'none',
              cursor: 'pointer',
              fontSize: 'var(--text-2xs)',
              fontWeight: viewMode === 'canonical' ? 600 : 400,
              fontFamily: 'var(--font-mono)',
              letterSpacing: '0.04em',
              textTransform: 'uppercase',
              backgroundColor: viewMode === 'canonical' ? 'var(--bg-elevated)' : 'transparent',
              color: viewMode === 'canonical' ? 'var(--teal)' : 'var(--text-muted)',
              transition: 'all var(--t-fast)',
            }}
          >
            Events ({events.length})
          </button>
          <button
            onClick={() => setViewMode('emerging')}
            style={{
              flex: 1,
              padding: '0.3rem 0.5rem',
              borderRadius: 'var(--r-1)',
              border: 'none',
              cursor: 'pointer',
              fontSize: 'var(--text-2xs)',
              fontWeight: viewMode === 'emerging' ? 600 : 400,
              fontFamily: 'var(--font-mono)',
              letterSpacing: '0.04em',
              textTransform: 'uppercase',
              backgroundColor: viewMode === 'emerging' ? 'var(--sev-3-dim)' : 'transparent',
              color: viewMode === 'emerging' ? 'var(--sev-3)' : 'var(--text-muted)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '0.25rem',
              transition: 'all var(--t-fast)',
            }}
          >
            <Zap size={11} />
            <span>Emerging</span>
          </button>
        </div>

        {viewMode === 'canonical' && (
          <>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                <span className="pulse-live" style={{ width: 6, height: 6 }} />
                <span style={{ fontSize: 'var(--text-xs)', fontWeight: 600, color: 'var(--text-primary)', fontFamily: 'var(--font-sans)', letterSpacing: '-0.01em' }}>
                  Live Event Feed
                </span>
              </div>
              <span
                style={{
                  fontFamily: 'var(--font-mono)',
                  fontSize: 'var(--text-2xs)',
                  padding: '0.1rem 0.45rem',
                  borderRadius: 'var(--r-full)',
                  background: 'var(--bg-elevated)',
                  border: '1px solid var(--border-hairline)',
                  color: 'var(--text-muted)',
                  letterSpacing: '0.04em',
                }}
              >
                {filteredEvents.length}
              </span>
            </div>

            {/* Search */}
            <div style={{ position: 'relative' }}>
              <Search
                size={12}
                style={{ position: 'absolute', left: '0.6rem', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }}
              />
              <input
                type="text"
                placeholder="Search state, district, type..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                style={{
                  width: '100%',
                  backgroundColor: 'var(--bg-panel)',
                  border: '1px solid var(--border-hairline)',
                  borderRadius: 'var(--r-2)',
                  color: 'var(--text-primary)',
                  padding: '0.4rem 0.6rem 0.4rem 1.875rem',
                  fontSize: 'var(--text-xs)',
                  outline: 'none',
                  fontFamily: 'var(--font-sans)',
                  transition: 'border-color var(--t-fast)',
                }}
                onFocus={(e) => { e.currentTarget.style.borderColor = 'var(--border-teal)'; }}
                onBlur={(e) => { e.currentTarget.style.borderColor = 'var(--border-hairline)'; }}
              />
            </div>

            {/* Filter Pills */}
            <div style={{ display: 'flex', gap: '0.3rem', overflowX: 'auto', paddingBottom: '2px', scrollbarWidth: 'none' }}>
              {([
                { id: 'all', label: `All ${events.length}`, icon: null, activeColor: 'var(--teal)', activeBg: 'var(--teal-100)', activeBorder: 'var(--border-teal)' },
                { id: 'severe', label: `Severe ${severeCount}`, icon: <Flame size={10} />, activeColor: 'var(--sev-4)', activeBg: 'var(--sev-4-dim)', activeBorder: 'rgba(239,68,68,0.25)' },
                { id: 'unverified', label: `Review ${unverifiedCount}`, icon: <ShieldAlert size={10} />, activeColor: 'var(--sev-3)', activeBg: 'var(--sev-3-dim)', activeBorder: 'rgba(249,115,22,0.25)' },
                { id: 'verified', label: `Verified`, icon: <CheckCircle2 size={10} />, activeColor: 'var(--sev-1)', activeBg: 'var(--sev-1-dim)', activeBorder: 'rgba(34,197,94,0.25)' },
              ] as const).map(({ id, label, icon, activeColor, activeBg, activeBorder }) => {
                const isActive = quickFilter === id;
                return (
                  <button
                    key={id}
                    onClick={() => setQuickFilter(id as QuickFilter)}
                    style={{
                      padding: '0.2rem 0.55rem',
                      borderRadius: 'var(--r-full)',
                      fontSize: 'var(--text-2xs)',
                      fontWeight: isActive ? 600 : 500,
                      fontFamily: 'var(--font-mono)',
                      letterSpacing: '0.04em',
                      border: `1px solid ${isActive ? activeBorder : 'var(--border-hairline)'}`,
                      cursor: 'pointer',
                      backgroundColor: isActive ? activeBg : 'transparent',
                      color: isActive ? activeColor : 'var(--text-muted)',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '0.2rem',
                      whiteSpace: 'nowrap',
                      transition: 'all var(--t-fast)',
                    }}
                  >
                    {icon}
                    {label}
                  </button>
                );
              })}
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

