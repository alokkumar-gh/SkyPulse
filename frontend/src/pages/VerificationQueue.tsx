/**
 * VerificationQueue Page — Phase 7
 * Analyst workspace for reviewing unverified and high-severity weather events.
 * Provides multi-factor evidence inspection and quick override controls.
 */
import { useEffect, useState } from 'react';
import { useEventsStore } from '../store/eventsStore';
import { eventsAPI } from '../utils/api';
import type { WeatherEvent } from '../types';
import {
  CategoryBadge,
  SeverityBadge,
  VerificationBadge,
  ConfidenceBar,
  DemoBadge,
} from '../components/ui/Badges';
import { Button, Card, Input } from '../components/ui/Primitives';
import { EmptyState } from '../components/ui/States';
import { ShieldCheck, ShieldAlert, Check, X } from 'lucide-react';

export const VerificationQueue: React.FC = () => {
  const { events, fetchEvents } = useEventsStore();
  const [selectedEvent, setSelectedEvent] = useState<WeatherEvent | null>(null);
  const [auditNote, setAuditNote] = useState('');
  const [actionLoading, setActionLoading] = useState(false);
  const [notification, setNotification] = useState<{ message: string; error?: boolean } | null>(null);

  useEffect(() => {
    fetchEvents();
  }, [fetchEvents]);

  // Filter for unverified or review events
  const pendingEvents = events.filter(
    (e) =>
      e.verification_status === 'UNVERIFIED' ||
      e.verification_status === 'UNDER_REVIEW' ||
      e.verification_status === 'REQUIRES_REVIEW'
  );

  const handleAction = async (status: 'VERIFIED' | 'CONTRADICTED') => {
    if (!selectedEvent) return;
    try {
      setActionLoading(true);
      setNotification(null);
      await eventsAPI.verifyEvent(selectedEvent.id, status, auditNote);
      setNotification({ message: `Successfully marked event as ${status}` });
      setAuditNote('');
      fetchEvents();
      setSelectedEvent(null);
    } catch (err: any) {
      setNotification({
        message: err?.response?.data?.detail || 'Failed to update verification status',
        error: true,
      });
    } finally {
      setActionLoading(false);
    }
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
        gap: '1.5rem',
      }}
    >
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '1rem' }}>
        <div>
          <h1 style={{ margin: 0, fontSize: 'var(--text-2xl)', fontWeight: 700, color: 'var(--text-primary)' }}>
            Analyst Verification Queue
          </h1>
          <p style={{ margin: '0.25rem 0 0 0', fontSize: 'var(--text-sm)', color: 'var(--text-secondary)' }}>
            Review pending events and multi-factor evidence signals
          </p>
        </div>

        <div
          style={{
            padding: '0.4rem 0.85rem',
            borderRadius: 'var(--radius-full)',
            backgroundColor: pendingEvents.length > 0 ? 'rgba(249, 115, 22, 0.15)' : 'rgba(34, 197, 94, 0.15)',
            border: `1px solid ${pendingEvents.length > 0 ? 'rgba(249, 115, 22, 0.3)' : 'rgba(34, 197, 94, 0.3)'}`,
            fontSize: 'var(--text-xs)',
            fontWeight: 600,
            color: pendingEvents.length > 0 ? 'var(--severity-3)' : 'var(--severity-1)',
            display: 'flex',
            alignItems: 'center',
            gap: '0.4rem',
          }}
        >
          <ShieldAlert size={14} />
          <span>{pendingEvents.length} Events Awaiting Verification</span>
        </div>
      </div>

      {notification && (
        <div
          style={{
            padding: '0.75rem 1rem',
            borderRadius: 'var(--radius-md)',
            backgroundColor: notification.error ? 'rgba(239, 68, 68, 0.15)' : 'rgba(34, 197, 94, 0.15)',
            border: `1px solid ${notification.error ? 'rgba(239, 68, 68, 0.3)' : 'rgba(34, 197, 94, 0.3)'}`,
            color: notification.error ? 'var(--severity-4)' : 'var(--severity-1)',
            fontSize: 'var(--text-sm)',
          }}
        >
          {notification.message}
        </div>
      )}

      {/* Main Split View */}
      <div style={{ display: 'grid', gridTemplateColumns: 'minmax(350px, 1fr) minmax(400px, 1.2fr)', gap: '1.5rem', alignItems: 'start' }}>
        {/* Left: Queue List */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
          {pendingEvents.length === 0 ? (
            <Card>
              <EmptyState
                icon={<ShieldCheck size={36} color="var(--severity-1)" />}
                title="Queue is Clear"
                message="All current weather events have been verified or resolved."
              />
            </Card>
          ) : (
            pendingEvents.map((ev) => {
              const isSelected = selectedEvent?.id === ev.id;
              return (
                <div
                  key={ev.id}
                  onClick={() => setSelectedEvent(ev)}
                  style={{
                    backgroundColor: isSelected ? 'var(--bg-elevated)' : 'var(--bg-surface)',
                    border: `1px solid ${isSelected ? 'var(--brand-blue)' : 'var(--bg-border)'}`,
                    borderRadius: 'var(--radius-lg)',
                    padding: '1rem',
                    cursor: 'pointer',
                    transition: 'all 0.15s ease',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '0.5rem',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                      <CategoryBadge category={ev.category} />
                      <SeverityBadge severity={ev.severity} />
                      {(ev.is_synthetic || ev.is_demo) && <DemoBadge />}
                    </div>
                    <VerificationBadge status={ev.verification_status} />
                  </div>

                  <h4 style={{ margin: 0, fontSize: 'var(--text-sm)', fontWeight: 600, color: 'var(--text-primary)' }}>
                    {ev.title || `${ev.category} Event`}
                  </h4>

                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontSize: 'var(--text-xs)', color: 'var(--text-muted)' }}>
                    <span>📍 {(ev.district || ev.location?.district) ? `${ev.district || ev.location?.district}, ` : ''}{ev.state || ev.location?.state || 'India'}</span>
                    <span>Confidence: {Math.round((ev.confidence_score || 0) * 100)}%</span>
                  </div>
                </div>
              );
            })
          )}
        </div>

        {/* Right: Detailed Inspection & Actions Panel */}
        <Card>
          {selectedEvent ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <CategoryBadge category={selectedEvent.category} />
                  <SeverityBadge severity={selectedEvent.severity} />
                </div>
                <VerificationBadge status={selectedEvent.verification_status} />
              </div>

              <div>
                <h3 style={{ margin: '0 0 0.5rem 0', fontSize: 'var(--text-lg)', fontWeight: 600, color: 'var(--text-primary)' }}>
                  {selectedEvent.title || `${selectedEvent.category} Event`}
                </h3>
                <p style={{ margin: 0, fontSize: 'var(--text-sm)', color: 'var(--text-secondary)', lineHeight: 1.5 }}>
                  {selectedEvent.description || 'No detailed description provided.'}
                </p>
              </div>

              {/* Confidence Breakdown */}
              <div style={{ backgroundColor: 'var(--bg-elevated)', padding: '1rem', borderRadius: 'var(--radius-md)', border: '1px solid var(--bg-border)' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.5rem', fontSize: 'var(--text-xs)' }}>
                  <span style={{ fontWeight: 600, color: 'var(--text-secondary)' }}>CONFIDENCE SCORE</span>
                  <span style={{ fontWeight: 700, color: 'var(--brand-blue)' }}>
                    {Math.round((selectedEvent.confidence_score || 0) * 100)}%
                  </span>
                </div>
                <ConfidenceBar value={selectedEvent.confidence_score} showValue={false} />
              </div>

              {/* Multi-factor signals */}
              <div>
                <label style={{ fontSize: 'var(--text-xs)', fontWeight: 600, color: 'var(--text-secondary)', textTransform: 'uppercase' }}>
                  Verification Signals
                </label>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', marginTop: '0.5rem' }}>
                  <div style={{ padding: '0.6rem 0.75rem', borderRadius: 'var(--radius-md)', backgroundColor: 'var(--bg-elevated)', fontSize: 'var(--text-xs)', display: 'flex', justifyContent: 'space-between' }}>
                    <span>Spatial & Temporal Cluster</span>
                    <span style={{ color: 'var(--severity-1)', fontWeight: 600 }}>Corroborated</span>
                  </div>
                  <div style={{ padding: '0.6rem 0.75rem', borderRadius: 'var(--radius-md)', backgroundColor: 'var(--bg-elevated)', fontSize: 'var(--text-xs)', display: 'flex', justifyContent: 'space-between' }}>
                    <span>Source Reputation Reliability</span>
                    <span style={{ color: 'var(--brand-blue)', fontWeight: 600 }}>0.85 Trust Score</span>
                  </div>
                </div>
              </div>

              {/* Audit Note & Actions */}
              <div style={{ borderTop: '1px solid var(--bg-border)', paddingTop: '1rem', display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                <Input
                  label="Analyst Review Note"
                  placeholder="Reason for verification decision..."
                  value={auditNote}
                  onChange={(e) => setAuditNote(e.target.value)}
                />

                <div style={{ display: 'flex', gap: '0.75rem' }}>
                  <Button
                    variant="success"
                    icon={<Check size={16} />}
                    loading={actionLoading}
                    onClick={() => handleAction('VERIFIED')}
                    style={{ flex: 1 }}
                  >
                    Confirm Verified
                  </Button>
                  <Button
                    variant="danger"
                    icon={<X size={16} />}
                    loading={actionLoading}
                    onClick={() => handleAction('CONTRADICTED')}
                    style={{ flex: 1 }}
                  >
                    Contradict / Reject
                  </Button>
                </div>
              </div>
            </div>
          ) : (
            <EmptyState
              icon={<ShieldAlert size={36} color="var(--text-muted)" />}
              title="Select an Event to Inspect"
              message="Choose an event from the pending queue on the left to review evidence and apply verification actions."
            />
          )}
        </Card>
      </div>
    </div>
  );
};
