/**
 * VerificationQueue Page — Phase 9
 * Operational triage queue for analysts and emergency administrators.
 * Multi-dimensional sorting/filtering, quick verify/reject modal dialogs,
 * audit logging, real-time WebSocket state synchronization.
 */
import React, { useEffect, useState, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { verificationAPI } from '../../utils/api';
import type { WeatherEvent } from '../../types';
import {
  CategoryBadge,
  SeverityBadge,
  VerificationBadge,
  ConfidenceBar,
} from '../../components/ui/Badges';
import { Button, Card, Input, Select } from '../../components/ui/Primitives';
import { EmptyState, TableSkeleton } from '../../components/ui/States';
import {
  ShieldAlert,
  ShieldCheck,
  XCircle,
  RefreshCw,
  Search,
  ExternalLink,
  AlertCircle,
  Check,
} from 'lucide-react';

export const VerificationQueue: React.FC = () => {
  const navigate = useNavigate();
  const [queueItems, setQueueItems] = useState<WeatherEvent[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const perPage = 20;
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Filters
  const [statusFilter, setStatusFilter] = useState<string>('UNVERIFIED');
  const [categoryFilter, setCategoryFilter] = useState<string>('ALL');
  const [severityFilter, setSeverityFilter] = useState<string>('ALL');
  const [stateFilter, setStateFilter] = useState<string>('');
  const [searchTerm, setSearchTerm] = useState<string>('');

  // Quick Action Modal
  const [actionModal, setActionModal] = useState<{
    event: WeatherEvent;
    type: 'VERIFY' | 'REJECT';
  } | null>(null);
  const [actionReason, setActionReason] = useState<string>('');
  const [actionLoading, setActionLoading] = useState(false);
  const [actionNotification, setActionNotification] = useState<{
    message: string;
    isError?: boolean;
  } | null>(null);

  const fetchQueue = async () => {
    try {
      setLoading(true);
      setError(null);
      const res = await verificationAPI.queue(page, perPage, {
        status: statusFilter === 'ALL' ? undefined : statusFilter,
        category: categoryFilter === 'ALL' ? undefined : categoryFilter,
        severity: severityFilter === 'ALL' ? undefined : Number(severityFilter),
        state: stateFilter.trim() || undefined,
      });
      setQueueItems((res.results || []) as unknown as WeatherEvent[]);
      setTotal(res.total || 0);
    } catch (err: any) {
      setError(err?.message || 'Failed to load verification queue from server');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchQueue();
  }, [page, statusFilter, categoryFilter, severityFilter, stateFilter]);

  // Client-side quick search filtering on the active page
  const displayedItems = useMemo(() => {
    if (!searchTerm.trim()) return queueItems;
    const q = searchTerm.toLowerCase();
    return queueItems.filter((item) => {
      const cat = (item.category || '').toLowerCase();
      const st = (item.state || item.location?.state || '').toLowerCase();
      const id = (item.id || (item as any).event_id || '').toLowerCase();
      return cat.includes(q) || st.includes(q) || id.includes(q);
    });
  }, [queueItems, searchTerm]);

  const handleQuickActionConfirm = async () => {
    if (!actionModal || actionReason.trim().length < 5) return;
    const targetStatus = actionModal.type === 'VERIFY' ? 'VERIFIED' : 'CONTRADICTED';
    const eventId = actionModal.event.id || (actionModal.event as any).event_id;

    try {
      setActionLoading(true);
      setActionNotification(null);
      await verificationAPI.override(eventId, targetStatus, actionReason);
      setActionNotification({
        message: `Event successfully marked as ${targetStatus}. Audit trail logged.`,
      });
      setActionModal(null);
      setActionReason('');
      fetchQueue();
    } catch (err: any) {
      setActionNotification({
        message: err?.message || 'Failed to update verification status',
        isError: true,
      });
    } finally {
      setActionLoading(false);
    }
  };

  return (
    <div
      style={{
        padding: '1.5rem',
        maxWidth: '1440px',
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
            Analyst Verification Queue
          </h1>
          <p style={{ margin: '0.25rem 0 0 0', fontSize: 'var(--text-sm)', color: 'var(--text-secondary)' }}>
            Real-time operational triage: Inspect multi-signal weather events, corroborate evidence, or apply justified overrides.
          </p>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          <div
            style={{
              padding: '0.4rem 0.85rem',
              borderRadius: 'var(--radius-full)',
              backgroundColor: total > 0 ? 'rgba(249, 115, 22, 0.15)' : 'rgba(34, 197, 94, 0.15)',
              border: `1px solid ${total > 0 ? 'rgba(249, 115, 22, 0.3)' : 'rgba(34, 197, 94, 0.3)'}`,
              fontSize: 'var(--text-xs)',
              fontWeight: 600,
              color: total > 0 ? 'var(--severity-3)' : 'var(--severity-1)',
              display: 'flex',
              alignItems: 'center',
              gap: '0.4rem',
            }}
          >
            <ShieldAlert size={14} />
            <span>{total} Pending Triage</span>
          </div>

          <Button variant="secondary" size="sm" icon={<RefreshCw size={14} />} onClick={fetchQueue} loading={loading}>
            Refresh
          </Button>
        </div>
      </div>

      {/* Global Notification Banner */}
      {actionNotification && (
        <div
          style={{
            padding: '0.75rem 1rem',
            borderRadius: 'var(--radius-md)',
            fontSize: 'var(--text-sm)',
            display: 'flex',
            alignItems: 'center',
            gap: '0.5rem',
            backgroundColor: actionNotification.isError ? 'rgba(239, 68, 68, 0.15)' : 'rgba(34, 197, 94, 0.15)',
            border: `1px solid ${actionNotification.isError ? 'rgba(239, 68, 68, 0.3)' : 'rgba(34, 197, 94, 0.3)'}`,
            color: actionNotification.isError ? 'var(--severity-4)' : 'var(--severity-1)',
          }}
        >
          {actionNotification.isError ? <AlertCircle size={16} /> : <Check size={16} />}
          <span>{actionNotification.message}</span>
        </div>
      )}

      {/* Filter Toolbar */}
      <Card>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.75rem', alignItems: 'center' }}>
          <div style={{ flex: '1 1 200px', minWidth: '180px' }}>
            <Input
              placeholder="Search category, state, ID..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              icon={<Search size={14} color="var(--text-muted)" />}
            />
          </div>

          <div style={{ width: '170px' }}>
            <Select
              value={statusFilter}
              onChange={(e) => {
                setStatusFilter(e.target.value);
                setPage(1);
              }}
              options={[
                { value: 'ALL', label: 'All Statuses' },
                { value: 'UNVERIFIED', label: 'UNVERIFIED' },
                { value: 'REQUIRES_REVIEW', label: 'REQUIRES_REVIEW' },
                { value: 'LIKELY', label: 'LIKELY' },
                { value: 'VERIFIED', label: 'VERIFIED' },
                { value: 'CONTRADICTED', label: 'CONTRADICTED' },
              ]}
            />
          </div>

          <div style={{ width: '160px' }}>
            <Select
              value={categoryFilter}
              onChange={(e) => {
                setCategoryFilter(e.target.value);
                setPage(1);
              }}
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
                { value: 'HAILSTORM', label: 'Hailstorm' },
              ]}
            />
          </div>

          <div style={{ width: '130px' }}>
            <Select
              value={severityFilter}
              onChange={(e) => {
                setSeverityFilter(e.target.value);
                setPage(1);
              }}
              options={[
                { value: 'ALL', label: 'All Severities' },
                { value: '1', label: 'Sev 1 - Low' },
                { value: '2', label: 'Sev 2 - Moderate' },
                { value: '3', label: 'Sev 3 - Severe' },
                { value: '4', label: 'Sev 4 - Extreme' },
              ]}
            />
          </div>

          <div style={{ width: '160px' }}>
            <Input
              placeholder="Filter by State..."
              value={stateFilter}
              onChange={(e) => {
                setStateFilter(e.target.value);
                setPage(1);
              }}
            />
          </div>
        </div>
      </Card>

      {/* Main Table / Queue Display */}
      {loading ? (
        <TableSkeleton rows={8} />
      ) : error ? (
        <Card>
          <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--severity-4)' }}>
            <AlertCircle size={32} style={{ margin: '0 auto 0.5rem auto' }} />
            <h4 style={{ margin: 0 }}>Error Loading Verification Queue</h4>
            <p style={{ fontSize: 'var(--text-sm)', color: 'var(--text-secondary)' }}>{error}</p>
            <Button size="sm" variant="secondary" onClick={fetchQueue} style={{ marginTop: '1rem' }}>
              Retry
            </Button>
          </div>
        </Card>
      ) : displayedItems.length === 0 ? (
        <EmptyState
          title="No Events In Verification Queue"
          message="All events matching the active filter criteria have been triaged or none currently require manual review."
          action={
            <Button
              size="sm"
              variant="secondary"
              onClick={() => {
                setStatusFilter('ALL');
                setCategoryFilter('ALL');
                setSeverityFilter('ALL');
                setStateFilter('');
                setSearchTerm('');
              }}
            >
              Clear Filters
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
                fontSize: 'var(--text-sm)',
              }}
            >
              <thead>
                <tr style={{ borderBottom: '1px solid var(--bg-border)', color: 'var(--text-muted)', fontSize: 'var(--text-xs)' }}>
                  <th style={{ padding: '0.75rem 0.5rem' }}>Event ID</th>
                  <th style={{ padding: '0.75rem 0.5rem' }}>Category</th>
                  <th style={{ padding: '0.75rem 0.5rem' }}>Severity</th>
                  <th style={{ padding: '0.75rem 0.5rem' }}>Location</th>
                  <th style={{ padding: '0.75rem 0.5rem' }}>First Reported</th>
                  <th style={{ padding: '0.75rem 0.5rem' }}>Confidence</th>
                  <th style={{ padding: '0.75rem 0.5rem' }}>Evidence Count</th>
                  <th style={{ padding: '0.75rem 0.5rem' }}>Status</th>
                  <th style={{ padding: '0.75rem 0.5rem', textAlign: 'right' }}>Analyst Actions</th>
                </tr>
              </thead>
              <tbody>
                {displayedItems.map((item) => {
                  const eventId = item.id || (item as any).event_id;
                  const itemState = item.state || item.location?.state || 'India';
                  const firstRep = item.first_reported_at
                    ? new Date(item.first_reported_at).toLocaleString('en-IN', {
                        month: 'short',
                        day: 'numeric',
                        hour: '2-digit',
                        minute: '2-digit',
                      })
                    : '—';

                  return (
                    <tr
                      key={eventId}
                      style={{
                        borderBottom: '1px solid var(--bg-border)',
                        transition: 'background-color var(--transition-fast)',
                      }}
                    >
                      <td style={{ padding: '0.75rem 0.5rem', fontFamily: 'monospace', fontWeight: 600 }}>
                        <button
                          onClick={() => navigate(`/analyst/events/${eventId}`)}
                          style={{
                            background: 'none',
                            border: 'none',
                            color: 'var(--brand-blue)',
                            cursor: 'pointer',
                            padding: 0,
                            fontFamily: 'inherit',
                            fontWeight: 'inherit',
                            display: 'flex',
                            alignItems: 'center',
                            gap: '0.25rem',
                          }}
                          title="Open detailed analyst event view"
                        >
                          {eventId.slice(0, 8)}…
                          <ExternalLink size={12} />
                        </button>
                      </td>
                      <td style={{ padding: '0.75rem 0.5rem' }}>
                        <CategoryBadge category={item.category} />
                      </td>
                      <td style={{ padding: '0.75rem 0.5rem' }}>
                        <SeverityBadge severity={item.severity} />
                      </td>
                      <td style={{ padding: '0.75rem 0.5rem', color: 'var(--text-secondary)' }}>
                        {itemState}
                      </td>
                      <td style={{ padding: '0.75rem 0.5rem', color: 'var(--text-secondary)', fontSize: 'var(--text-xs)' }}>
                        {firstRep}
                      </td>
                      <td style={{ padding: '0.75rem 0.5rem', minWidth: '100px' }}>
                        <ConfidenceBar value={item.confidence_score ?? 0.5} />
                      </td>
                      <td style={{ padding: '0.75rem 0.5rem', color: 'var(--text-primary)', fontWeight: 600 }}>
                        {item.evidence_count} report(s)
                      </td>
                      <td style={{ padding: '0.75rem 0.5rem' }}>
                        <VerificationBadge status={item.verification_status} />
                      </td>
                      <td style={{ padding: '0.75rem 0.5rem', textAlign: 'right' }}>
                        <div style={{ display: 'inline-flex', gap: '0.4rem' }}>
                          <Button
                            size="sm"
                            variant="primary"
                            icon={<ShieldCheck size={13} />}
                            onClick={() => setActionModal({ event: item, type: 'VERIFY' })}
                            title="Quickly verify event with justification"
                          >
                            Verify
                          </Button>
                          <Button
                            size="sm"
                            variant="danger"
                            icon={<XCircle size={13} />}
                            onClick={() => setActionModal({ event: item, type: 'REJECT' })}
                            title="Quickly reject/contradict event with justification"
                          >
                            Reject
                          </Button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          {/* Pagination */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              paddingTop: '1rem',
              borderTop: '1px solid var(--bg-border)',
              marginTop: '0.5rem',
              fontSize: 'var(--text-xs)',
              color: 'var(--text-muted)',
            }}
          >
            <span>
              Showing {displayedItems.length} of {total} events
            </span>
            <div style={{ display: 'flex', gap: '0.5rem' }}>
              <Button
                size="sm"
                variant="secondary"
                disabled={page <= 1}
                onClick={() => setPage((p) => Math.max(1, p - 1))}
              >
                Previous
              </Button>
              <Button
                size="sm"
                variant="secondary"
                disabled={page * perPage >= total}
                onClick={() => setPage((p) => p + 1)}
              >
                Next
              </Button>
            </div>
          </div>
        </Card>
      )}

      {/* Quick Verify / Reject Confirmation Modal */}
      {actionModal && (
        <div
          style={{
            position: 'fixed',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            backgroundColor: 'rgba(0,0,0,0.65)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 1000,
            padding: '1rem',
          }}
        >
          <div
            style={{
              backgroundColor: 'var(--bg-surface)',
              border: '1px solid var(--bg-border)',
              borderRadius: 'var(--radius-lg)',
              maxWidth: '520px',
              width: '100%',
              padding: '1.5rem',
              boxShadow: 'var(--shadow-xl)',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '1rem' }}>
              {actionModal.type === 'VERIFY' ? (
                <ShieldCheck size={22} color="var(--severity-1)" />
              ) : (
                <XCircle size={22} color="var(--severity-4)" />
              )}
              <h3 style={{ margin: 0, fontSize: 'var(--text-lg)', fontWeight: 700, color: 'var(--text-primary)' }}>
                {actionModal.type === 'VERIFY' ? 'Verify Weather Event' : 'Contradict / Reject Weather Event'}
              </h3>
            </div>

            <p style={{ fontSize: 'var(--text-sm)', color: 'var(--text-secondary)', marginBottom: '1rem' }}>
              You are applying an official analyst determination to event{' '}
              <strong>{(actionModal.event.id || (actionModal.event as any).event_id).slice(0, 8)}…</strong>. An
              auditable justification of at least 5 characters is mandatory.
            </p>

            <Input
              placeholder="Provide reason for this verification decision (e.g. Confirmed via Doppler radar and local ground sensors)..."
              value={actionReason}
              onChange={(e) => setActionReason(e.target.value)}
              style={{ marginBottom: '1.25rem' }}
            />

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.75rem' }}>
              <Button
                variant="secondary"
                size="sm"
                onClick={() => {
                  setActionModal(null);
                  setActionReason('');
                }}
              >
                Cancel
              </Button>
              <Button
                variant={actionModal.type === 'VERIFY' ? 'primary' : 'danger'}
                size="sm"
                disabled={actionReason.trim().length < 5}
                loading={actionLoading}
                onClick={handleQuickActionConfirm}
              >
                Confirm {actionModal.type === 'VERIFY' ? 'Verification' : 'Rejection'}
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
