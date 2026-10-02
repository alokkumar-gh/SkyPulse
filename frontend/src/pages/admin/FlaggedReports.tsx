/**
 * FlaggedReports Page — Phase 9
 * Displays observational reports flagged by AI semantic extraction,
 * anomalous variance, or duplicate detection.
 * Allows navigation into canonical events and detailed report review.
 */
import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { adminAPI } from '../../utils/api';
import type { FlaggedReport } from '../../types';
import { Card, Button, Input, Select } from '../../components/ui/Primitives';
import { CategoryBadge, SeverityBadge } from '../../components/ui/Badges';
import { TableSkeleton, EmptyState } from '../../components/ui/States';
import {
  Flag,
  Search,
  RefreshCw,
  ExternalLink,
  AlertTriangle,
} from 'lucide-react';

export const FlaggedReportsPage: React.FC = () => {
  const navigate = useNavigate();
  const [reports, setReports] = useState<FlaggedReport[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Filters
  const [categoryFilter, setCategoryFilter] = useState('ALL');
  const [stateFilter, setStateFilter] = useState('');
  const [searchTerm, setSearchTerm] = useState('');

  const fetchFlagged = async () => {
    try {
      setLoading(true);
      setError(null);
      const cat = categoryFilter === 'ALL' ? undefined : categoryFilter;
      const st = stateFilter.trim() || undefined;
      const res = await adminAPI.flaggedReports(cat, st, 100);
      setReports(res);
    } catch (err: any) {
      setError(err?.message || 'Failed to retrieve flagged reports');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchFlagged();
  }, [categoryFilter, stateFilter]);

  const displayedReports = reports.filter((r) => {
    if (!searchTerm.trim()) return true;
    const q = searchTerm.toLowerCase();
    const id = r.id.toLowerCase();
    const cat = (r.category || '').toLowerCase();
    const text = (r.normalized_text || r.raw_content || '').toLowerCase();
    const state = (r.location_state || '').toLowerCase();
    return id.includes(q) || cat.includes(q) || text.includes(q) || state.includes(q);
  });

  return (
    <div
      style={{
        padding: '1.5rem',
        maxWidth: '1400px',
        margin: '0 auto',
        width: '100%',
        display: 'flex',
        flexDirection: 'column',
        gap: '1.5rem',
      }}
    >
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '1rem' }}>
        <div>
          <h1 style={{ margin: 0, fontSize: 'var(--text-2xl)', fontWeight: 700, color: 'var(--text-primary)' }}>
            Flagged & Anomalous Reports
          </h1>
          <p style={{ margin: '0.25rem 0 0 0', fontSize: 'var(--text-sm)', color: 'var(--text-secondary)' }}>
            Observational reports flagged by AI semantic extraction, confidence thresholds, or duplicate clustering
          </p>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          <div
            style={{
              padding: '0.35rem 0.75rem',
              borderRadius: 'var(--radius-full)',
              backgroundColor: reports.length > 0 ? 'rgba(239, 68, 68, 0.15)' : 'rgba(34, 197, 94, 0.15)',
              border: `1px solid ${reports.length > 0 ? 'rgba(239, 68, 68, 0.3)' : 'rgba(34, 197, 94, 0.3)'}`,
              fontSize: 'var(--text-xs)',
              fontWeight: 600,
              color: reports.length > 0 ? 'var(--severity-4)' : 'var(--severity-1)',
              display: 'flex',
              alignItems: 'center',
              gap: '0.4rem',
            }}
          >
            <Flag size={14} />
            <span>{reports.length} Flagged Reports</span>
          </div>

          <Button variant="secondary" size="sm" icon={<RefreshCw size={14} />} onClick={fetchFlagged} loading={loading}>
            Refresh
          </Button>
        </div>
      </div>

      {/* Filters Toolbar */}
      <Card>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '1rem', alignItems: 'center' }}>
          <div style={{ flex: '1 1 240px' }}>
            <Input
              placeholder="Search content, report ID, category..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              icon={<Search size={14} color="var(--text-muted)" />}
            />
          </div>

          <div style={{ width: '180px' }}>
            <Select
              value={categoryFilter}
              onChange={(e) => setCategoryFilter(e.target.value)}
              options={[
                { value: 'ALL', label: 'All Categories' },
                { value: 'RAINFALL', label: 'Rainfall' },
                { value: 'THUNDERSTORM', label: 'Thunderstorm' },
                { value: 'FLOODING', label: 'Flooding' },
                { value: 'HEATWAVE', label: 'Heatwave' },
                { value: 'CYCLONE', label: 'Cyclone' },
                { value: 'STRONG_WINDS', label: 'Strong Winds' },
                { value: 'FOG', label: 'Fog' },
                { value: 'DUST_STORM', label: 'Dust Storm' },
              ]}
            />
          </div>

          <div style={{ width: '180px' }}>
            <Input
              placeholder="Filter by State..."
              value={stateFilter}
              onChange={(e) => setStateFilter(e.target.value)}
            />
          </div>
        </div>
      </Card>

      {/* Flagged Reports Table */}
      {loading ? (
        <TableSkeleton rows={8} />
      ) : error ? (
        <Card>
          <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--severity-4)' }}>
            <AlertTriangle size={32} style={{ margin: '0 auto 0.5rem auto' }} />
            <h4 style={{ margin: 0 }}>Error Fetching Flagged Reports</h4>
            <p style={{ fontSize: 'var(--text-sm)', color: 'var(--text-secondary)' }}>{error}</p>
          </div>
        </Card>
      ) : displayedReports.length === 0 ? (
        <EmptyState
          title="No Flagged Reports"
          message="No weather reports are currently flagged for review."
          action={
            <Button
              size="sm"
              variant="secondary"
              onClick={() => {
                setCategoryFilter('ALL');
                setStateFilter('');
                setSearchTerm('');
              }}
            >
              Reset Filters
            </Button>
          }
        />
      ) : (
        <Card>
          <div style={{ overflowX: 'auto' }}>
            <table
              style={{
                width: '100%',
                borderCollapse: 'collapse',
                textAlign: 'left',
                fontSize: 'var(--text-xs)',
              }}
            >
              <thead>
                <tr style={{ borderBottom: '1px solid var(--bg-border)', color: 'var(--text-muted)' }}>
                  <th style={{ padding: '0.625rem 0.5rem' }}>Report ID</th>
                  <th style={{ padding: '0.625rem 0.5rem' }}>Category</th>
                  <th style={{ padding: '0.625rem 0.5rem' }}>Severity</th>
                  <th style={{ padding: '0.625rem 0.5rem' }}>Source</th>
                  <th style={{ padding: '0.625rem 0.5rem' }}>Location</th>
                  <th style={{ padding: '0.625rem 0.5rem' }}>Observation Text</th>
                  <th style={{ padding: '0.625rem 0.5rem' }}>Flag Reason</th>
                  <th style={{ padding: '0.625rem 0.5rem', textAlign: 'right' }}>Canonical Event</th>
                </tr>
              </thead>
              <tbody>
                {displayedReports.map((r) => {
                  return (
                    <tr
                      key={r.id}
                      style={{
                        borderBottom: '1px solid var(--bg-border)',
                      }}
                    >
                      <td style={{ padding: '0.625rem 0.5rem', fontFamily: 'monospace', fontWeight: 600, color: 'var(--text-primary)' }}>
                        {r.id.slice(0, 8)}…
                      </td>
                      <td style={{ padding: '0.625rem 0.5rem' }}>
                        {r.category ? <CategoryBadge category={r.category as any} /> : '—'}
                      </td>
                      <td style={{ padding: '0.625rem 0.5rem' }}>
                        {r.severity ? <SeverityBadge severity={r.severity} /> : '—'}
                      </td>
                      <td style={{ padding: '0.625rem 0.5rem', color: 'var(--text-secondary)' }}>
                        {r.source_name || r.source_id.slice(0, 8)}
                      </td>
                      <td style={{ padding: '0.625rem 0.5rem', color: 'var(--text-secondary)' }}>
                        {[r.location_district, r.location_state].filter(Boolean).join(', ') || 'India'}
                      </td>
                      <td
                        style={{
                          padding: '0.625rem 0.5rem',
                          maxWidth: '300px',
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                          whiteSpace: 'nowrap',
                          color: 'var(--text-secondary)',
                        }}
                        title={r.normalized_text || r.raw_content || ''}
                      >
                        {r.normalized_text || r.raw_content || '—'}
                      </td>
                      <td style={{ padding: '0.625rem 0.5rem' }}>
                        <span
                          style={{
                            padding: '0.15rem 0.45rem',
                            borderRadius: 'var(--radius-sm)',
                            fontSize: '10px',
                            fontWeight: 700,
                            backgroundColor: r.status === 'FLAGGED' ? 'rgba(239, 68, 68, 0.15)' : 'rgba(234, 179, 8, 0.15)',
                            color: r.status === 'FLAGGED' ? 'var(--severity-4)' : 'var(--severity-2)',
                          }}
                        >
                          {r.status === 'FLAGGED' ? 'AI FLAGGED' : 'DUPLICATE MATCH'}
                        </span>
                      </td>
                      <td style={{ padding: '0.625rem 0.5rem', textAlign: 'right' }}>
                        {r.canonical_event_id ? (
                          <Button
                            size="sm"
                            variant="secondary"
                            icon={<ExternalLink size={12} />}
                            onClick={() => navigate(`/analyst/events/${r.canonical_event_id}`)}
                          >
                            Inspect Event
                          </Button>
                        ) : (
                          <span style={{ color: 'var(--text-muted)' }}>Unlinked</span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </div>
  );
};
