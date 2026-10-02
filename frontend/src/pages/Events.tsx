/**
 * Events Explorer Page — Phase 7
 * Full table and grid view of all weather events across India.
 * Advanced filtering, sorting, pagination, and inspection drawer.
 */
import { useEffect, useState } from 'react';
import { useEventsStore } from '../store/eventsStore';
import type { WeatherEvent } from '../types';
import {
  CategoryBadge,
  SeverityBadge,
  VerificationBadge,
  ConfidenceBar,
  DemoBadge,
} from '../components/ui/Badges';
import { Button, Input, Select } from '../components/ui/Primitives';
import { EventDetailDrawer } from '../components/events/EventDetailDrawer';
import { EmptyState } from '../components/ui/States';
import { Search, ChevronLeft, ChevronRight, Eye } from 'lucide-react';

export const Events: React.FC = () => {
  const { events, total, selectedEvent, setSelectedEvent, fetchEvents } = useEventsStore();
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedCategory, setSelectedCategory] = useState<string>('ALL');
  const [selectedSeverity, setSelectedSeverity] = useState<string>('ALL');
  const [selectedStatus, setSelectedStatus] = useState<string>('ALL');
  const [currentPage, setCurrentPage] = useState(1);
  const itemsPerPage = 12;

  useEffect(() => {
    const filters: {
      category?: string;
      severity?: number;
      status?: string;
      state?: string;
    } = {};

    if (selectedCategory !== 'ALL') filters.category = selectedCategory;
    if (selectedSeverity !== 'ALL') filters.severity = Number(selectedSeverity);
    if (selectedStatus !== 'ALL') filters.status = selectedStatus;
    if (searchTerm.trim()) filters.state = searchTerm.trim();

    fetchEvents(filters, currentPage, itemsPerPage);
  }, [fetchEvents, currentPage, selectedCategory, selectedSeverity, selectedStatus, searchTerm]);

  // Pagination
  const totalPages = Math.max(1, Math.ceil((total || events.length) / itemsPerPage));

  const handleOpenDetail = (event: WeatherEvent) => {
    setSelectedEvent(event);
    setDrawerOpen(true);
  };

  return (
    <div
      style={{
        padding: '1.5rem',
        maxWidth: '1400px',
        margin: '0 auto',
        width: '100%',
        display: 'flex',
        flexDirection: 'column',
        gap: '1.25rem',
      }}
    >
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '1rem' }}>
        <div>
          <h1 style={{ margin: 0, fontSize: 'var(--text-2xl)', fontWeight: 700, color: 'var(--text-primary)' }}>
            Weather Events Explorer
          </h1>
          <p style={{ margin: '0.25rem 0 0 0', fontSize: 'var(--text-sm)', color: 'var(--text-secondary)' }}>
            Historical and real-time canonical weather events catalog
          </p>
        </div>

        <span
          style={{
            padding: '0.35rem 0.75rem',
            borderRadius: 'var(--radius-full)',
            backgroundColor: 'var(--bg-elevated)',
            border: '1px solid var(--bg-border)',
            fontSize: 'var(--text-xs)',
            color: 'var(--text-secondary)',
          }}
        >
          Total: <strong style={{ color: 'var(--text-primary)' }}>{total || events.length}</strong> events
        </span>
      </div>

      {/* Filter Toolbar */}
      <div
        style={{
          backgroundColor: 'var(--bg-surface)',
          border: '1px solid var(--bg-border)',
          borderRadius: 'var(--radius-lg)',
          padding: '1rem',
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
          gap: '0.75rem',
          alignItems: 'end',
        }}
      >
        <Input
          label="Search Events"
          placeholder="Filter by title, state, district..."
          value={searchTerm}
          onChange={(e) => {
            setSearchTerm(e.target.value);
            setCurrentPage(1);
          }}
          icon={<Search size={14} />}
        />

        <Select
          label="Category"
          value={selectedCategory}
          onChange={(e) => {
            setSelectedCategory(e.target.value);
            setCurrentPage(1);
          }}
          options={[
            { label: 'All Categories', value: 'ALL' },
            { label: 'Rainfall', value: 'RAINFALL' },
            { label: 'Thunderstorm', value: 'THUNDERSTORM' },
            { label: 'Flooding', value: 'FLOODING' },
            { label: 'Heatwave', value: 'HEATWAVE' },
            { label: 'Fog', value: 'FOG' },
            { label: 'Dust Storm', value: 'DUST_STORM' },
            { label: 'Strong Winds', value: 'STRONG_WINDS' },
            { label: 'Hailstorm', value: 'HAILSTORM' },
            { label: 'Cyclone', value: 'CYCLONE' },
          ]}
        />

        <Select
          label="Severity"
          value={selectedSeverity}
          onChange={(e) => {
            setSelectedSeverity(e.target.value);
            setCurrentPage(1);
          }}
          options={[
            { label: 'All Severities', value: 'ALL' },
            { label: '1 - Minor', value: '1' },
            { label: '2 - Moderate', value: '2' },
            { label: '3 - Severe', value: '3' },
            { label: '4 - Extreme', value: '4' },
          ]}
        />

        <Select
          label="Verification"
          value={selectedStatus}
          onChange={(e) => {
            setSelectedStatus(e.target.value);
            setCurrentPage(1);
          }}
          options={[
            { label: 'All Statuses', value: 'ALL' },
            { label: 'Verified', value: 'VERIFIED' },
            { label: 'Likely', value: 'LIKELY' },
            { label: 'Unverified', value: 'UNVERIFIED' },
            { label: 'Under Review', value: 'UNDER_REVIEW' },
            { label: 'Contradicted', value: 'CONTRADICTED' },
          ]}
        />
      </div>

      {/* Events Table */}
      <div
        style={{
          backgroundColor: 'var(--bg-surface)',
          border: '1px solid var(--bg-border)',
          borderRadius: 'var(--radius-lg)',
          overflow: 'hidden',
        }}
      >
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: 'var(--text-sm)' }}>
            <thead>
              <tr style={{ backgroundColor: 'var(--bg-elevated)', borderBottom: '1px solid var(--bg-border)' }}>
                <th style={{ padding: '0.75rem 1rem', fontWeight: 600, color: 'var(--text-secondary)' }}>Category</th>
                <th style={{ padding: '0.75rem 1rem', fontWeight: 600, color: 'var(--text-secondary)' }}>Severity</th>
                <th style={{ padding: '0.75rem 1rem', fontWeight: 600, color: 'var(--text-secondary)' }}>Event / Title</th>
                <th style={{ padding: '0.75rem 1rem', fontWeight: 600, color: 'var(--text-secondary)' }}>Location</th>
                <th style={{ padding: '0.75rem 1rem', fontWeight: 600, color: 'var(--text-secondary)' }}>Confidence</th>
                <th style={{ padding: '0.75rem 1rem', fontWeight: 600, color: 'var(--text-secondary)' }}>Verification</th>
                <th style={{ padding: '0.75rem 1rem', fontWeight: 600, color: 'var(--text-secondary)' }}>Time</th>
                <th style={{ padding: '0.75rem 1rem', fontWeight: 600, color: 'var(--text-secondary)', textAlign: 'right' }}>Action</th>
              </tr>
            </thead>
            <tbody>
              {events.length === 0 ? (
                <tr>
                  <td colSpan={8} style={{ padding: '2rem', textAlign: 'center' }}>
                    <EmptyState title="No events found" description="Try relaxing your search terms or filter criteria." />
                  </td>
                </tr>
              ) : (
                events.map((ev) => (
                  <tr
                    key={ev.id}
                    style={{
                      borderBottom: '1px solid var(--bg-border)',
                      transition: 'background-color 0.15s ease',
                      cursor: 'pointer',
                    }}
                    onClick={() => handleOpenDetail(ev)}
                    onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = 'var(--bg-elevated)')}
                    onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = 'transparent')}
                  >
                    <td style={{ padding: '0.75rem 1rem' }}>
                      <CategoryBadge category={ev.category} />
                    </td>
                    <td style={{ padding: '0.75rem 1rem' }}>
                      <SeverityBadge severity={ev.severity} />
                    </td>
                    <td style={{ padding: '0.75rem 1rem', maxWidth: '300px' }}>
                      <div style={{ fontWeight: 600, color: 'var(--text-primary)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        {ev.title || `${ev.category} event`}
                      </div>
                      {(ev.is_synthetic || ev.is_demo) && <DemoBadge />}
                    </td>
                    <td style={{ padding: '0.75rem 1rem', color: 'var(--text-secondary)' }}>
                      {(ev.district || ev.location?.district) ? `${ev.district || ev.location?.district}, ` : ''}{ev.state || ev.location?.state || 'India'}
                    </td>
                    <td style={{ padding: '0.75rem 1rem', width: '120px' }}>
                      <ConfidenceBar value={ev.confidence_score} showValue />
                    </td>
                    <td style={{ padding: '0.75rem 1rem' }}>
                      <VerificationBadge status={ev.verification_status} />
                    </td>
                    <td style={{ padding: '0.75rem 1rem', color: 'var(--text-muted)', fontSize: 'var(--text-xs)' }}>
                      {new Date(ev.created_at || ev.first_reported_at || Date.now()).toLocaleDateString()}
                    </td>
                    <td style={{ padding: '0.75rem 1rem', textAlign: 'right' }}>
                      <Button
                        variant="ghost"
                        size="sm"
                        icon={<Eye size={14} />}
                        onClick={(e) => {
                          e.stopPropagation();
                          handleOpenDetail(ev);
                        }}
                      >
                        Inspect
                      </Button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination controls */}
        {totalPages > 1 && (
          <div
            style={{
              padding: '0.75rem 1rem',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              borderTop: '1px solid var(--bg-border)',
              backgroundColor: 'var(--bg-elevated)',
            }}
          >
            <span style={{ fontSize: 'var(--text-xs)', color: 'var(--text-secondary)' }}>
              Page {currentPage} of {totalPages}
            </span>
            <div style={{ display: 'flex', gap: '0.5rem' }}>
              <Button
                variant="secondary"
                size="sm"
                icon={<ChevronLeft size={14} />}
                disabled={currentPage <= 1}
                onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
              >
                Prev
              </Button>
              <Button
                variant="secondary"
                size="sm"
                icon={<ChevronRight size={14} />}
                disabled={currentPage >= totalPages}
                onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
              >
                Next
              </Button>
            </div>
          </div>
        )}
      </div>

      {/* Drawer */}
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
