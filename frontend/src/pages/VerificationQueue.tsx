/**
 * SkyPulse Analyst Verification Operations Queue
 * Redesigned according to Second-Pass UX Audit:
 * - Operational triage workflow for analysts
 * - Multi-factor evidence inspection (Doppler, AWS, Satellite)
 * - Restrained, authoritative decision actions (Confirm vs Reject with audit notes)
 * - Full alignment with SkyPulse Design Tokens
 */

import React, { useEffect, useState, useMemo } from 'react';
import { useEventsStore } from '../store/eventsStore';
import { eventsAPI } from '../utils/api';
import type { WeatherEvent } from '../types';
import {
  CategoryBadge,
  SeverityBadge,
  VerificationBadge,
} from '../components/ui/Badges';
import { Button } from '../components/ui/Primitives';
import { MetricCard } from '../components/ui/MetricCard';
import { LiveStatus } from '../components/ui/LiveStatus';
import {
  ShieldCheck, Check, X,
  MapPin, RefreshCw,
} from 'lucide-react';
import { SEVERITY_COLORS } from '../types';

export const VerificationQueue: React.FC = () => {
  const { events, fetchEvents, loading } = useEventsStore();
  const [selectedEvent, setSelectedEvent] = useState<WeatherEvent | null>(null);
  const [auditNote, setAuditNote] = useState('');
  const [actionLoading, setActionLoading] = useState(false);
  const [notification, setNotification] = useState<{ message: string; error?: boolean } | null>(null);

  useEffect(() => {
    fetchEvents();
  }, [fetchEvents]);

  // Filter for unverified or review events
  const pendingEvents = useMemo(() => {
    return events.filter(
      (e) =>
        e.verification_status === 'UNVERIFIED' ||
        e.verification_status === 'UNDER_REVIEW' ||
        e.verification_status === 'REQUIRES_REVIEW'
    ).sort((a, b) => b.severity - a.severity);
  }, [events]);

  const activeSelected = selectedEvent || pendingEvents[0] || null;

  const handleAction = async (status: 'VERIFIED' | 'CONTRADICTED') => {
    if (!activeSelected) return;
    try {
      setActionLoading(true);
      setNotification(null);
      await eventsAPI.verifyEvent(activeSelected.id, status, auditNote);
      setNotification({ message: `Successfully authenticated event as ${status} under operator signature.` });
      setAuditNote('');
      fetchEvents();
      setSelectedEvent(null);
    } catch (err: any) {
      setNotification({
        message: err?.response?.data?.detail || 'Failed to update verification record in telemetry store.',
        error: true,
      });
    } finally {
      setActionLoading(false);
    }
  };

  const highSevPending = pendingEvents.filter((e) => e.severity >= 3).length;

  return (
    <div className="page-root" style={{ overflow: 'auto' }}>
      {/* ── Page Header ───────────────────────────────────────────────────── */}
      <div className="page-header" style={{ flexWrap: 'wrap', gap: '1rem' }}>
        <div>
          <div style={{
            fontFamily: 'var(--font-mono)',
            fontSize: 'var(--text-2xs)',
            color: 'var(--text-muted)',
            letterSpacing: '0.14em',
            textTransform: 'uppercase',
            marginBottom: '0.25rem',
          }}>
            Operational Triage & Validation
          </div>
          <h1 className="page-title" style={{ margin: 0 }}>Ground Truth Verification Queue</h1>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem' }}>
          <LiveStatus state="LIVE" />
          <Button
            variant="secondary"
            size="sm"
            onClick={() => fetchEvents()}
            icon={<RefreshCw size={12} className={loading ? 'sp-spin' : ''} />}
          >
            SYNC QUEUE
          </Button>
        </div>
      </div>

      {/* ── Operational Triage Metrics (Section 7) ─────────────────────────── */}
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
          label="PENDING TRIAGE QUEUE"
          value={pendingEvents.length}
          comparison={{
            value: `${highSevPending} severe`,
            text: 'requiring operator review',
            sentiment: highSevPending > 0 ? 'warning' : 'neutral',
          }}
          source="Ingestion Mesh"
          signal={pendingEvents.length > 0 ? 'teal' : 'sev-1'}
        />

        <MetricCard
          label="HIGH-PRIORITY HAZARDS"
          value={highSevPending}
          comparison={{
            value: 'Severity 3 & 4',
            text: 'NDMA warning threshold',
            sentiment: highSevPending > 0 ? 'negative' : 'positive',
          }}
          source="CAP Gateway"
          signal={highSevPending > 0 ? 'sev-4' : 'sev-1'}
          isAnomaly={highSevPending > 0}
        />

        <MetricCard
          label="ALGORITHMIC CONFIDENCE"
          value="87.4%"
          comparison={{
            value: 'Multi-Source',
            text: 'CLIP + AWS corroboration',
            sentiment: 'positive',
          }}
          source="AI Verification Pipeline"
          signal="teal"
        />

        <MetricCard
          label="OPERATIONAL SLA"
          value="< 4 min"
          comparison={{
            value: 'Nominal',
            text: 'triage response latency',
            sentiment: 'positive',
          }}
          source="Desk Telemetry"
          signal="sev-1"
        />
      </div>

      {notification && (
        <div
          style={{
            margin: '1rem 1.5rem 0',
            padding: '0.75rem 1rem',
            borderRadius: 'var(--r-2)',
            backgroundColor: notification.error ? 'var(--sev-4-dim)' : 'var(--sev-1-dim)',
            border: `1px solid ${notification.error ? 'var(--sev-4)' : 'var(--sev-1)'}`,
            color: notification.error ? 'var(--sev-4)' : 'var(--sev-1)',
            fontSize: 'var(--text-xs)',
            fontFamily: 'var(--font-mono)',
          }}
        >
          {notification.message}
        </div>
      )}

      {/* ── Main Triage Split View ─────────────────────────────────────────── */}
      <div style={{ padding: '1.5rem', display: 'grid', gridTemplateColumns: 'minmax(340px, 440px) 1fr', gap: '1.5rem', alignItems: 'start', maxWidth: 1400 }}>

        {/* Left: Pending Queue List */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.65rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.25rem' }}>
            <span style={{ fontSize: 'var(--text-2xs)', fontFamily: 'var(--font-mono)', fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase' }}>
              PENDING VALIDATION ITEMS ({pendingEvents.length})
            </span>
            <span style={{ fontSize: 'var(--text-2xs)', fontFamily: 'var(--font-mono)', color: 'var(--teal)' }}>
              SELECT FOR DOSSIER
            </span>
          </div>

          {pendingEvents.length === 0 ? (
            <div
              style={{
                backgroundColor: 'var(--bg-surface)',
                border: '1px solid var(--border-hairline)',
                borderRadius: 'var(--r-2)',
                padding: '3rem 1.5rem',
                textAlign: 'center',
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                gap: '0.75rem',
              }}
            >
              <ShieldCheck size={32} color="var(--status-verified)" />
              <div style={{ fontSize: 'var(--text-base)', fontWeight: 700, color: 'var(--text-primary)' }}>
                Triage Queue Clear
              </div>
              <div style={{ fontSize: 'var(--text-xs)', fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>
                All ingested atmospheric events have been verified against multi-source radar and AWS ground truth.
              </div>
            </div>
          ) : (
            pendingEvents.map((ev) => {
              const isSelected = activeSelected?.id === ev.id;
              const sevCol = SEVERITY_COLORS[ev.severity] || 'var(--teal)';

              return (
                <div
                  key={ev.id}
                  onClick={() => setSelectedEvent(ev)}
                  style={{
                    backgroundColor: isSelected ? 'var(--bg-elevated)' : 'var(--bg-surface)',
                    border: `1px solid ${isSelected ? 'var(--border-teal)' : 'var(--border-hairline)'}`,
                    borderLeft: `3px solid ${isSelected ? 'var(--teal)' : sevCol}`,
                    borderRadius: 'var(--r-2)',
                    padding: '0.85rem 1rem',
                    cursor: 'pointer',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '0.4rem',
                    transition: 'all 0.15s ease',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
                      <CategoryBadge category={ev.category} />
                      <SeverityBadge severity={ev.severity} />
                    </div>
                    <VerificationBadge status={ev.verification_status} />
                  </div>

                  <div style={{ fontSize: 'var(--text-sm)', fontWeight: 700, color: 'var(--text-primary)' }}>
                    {ev.title || `${ev.category} Advisory`}
                  </div>

                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontSize: 'var(--text-2xs)', fontFamily: 'var(--font-mono)', color: 'var(--text-muted)', paddingTop: '0.25rem', borderTop: '1px solid var(--border-hairline)' }}>
                    <span style={{ display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
                      <MapPin size={10} color="var(--teal)" />
                      {ev.district ? `${ev.district}, ` : ''}{ev.state || 'India'}
                    </span>
                    <span>AI Confidence: {Math.round(ev.confidence_score * 100)}%</span>
                  </div>
                </div>
              );
            })
          )}
        </div>

        {/* Right: Multi-Factor Evidence & Decision Workspace */}
        {activeSelected && (
          <div
            style={{
              backgroundColor: 'var(--bg-surface)',
              border: '1px solid var(--border-default)',
              borderTop: `4px solid ${SEVERITY_COLORS[activeSelected.severity] || 'var(--teal)'}`,
              borderRadius: 'var(--r-2)',
              padding: '1.5rem',
              display: 'flex',
              flexDirection: 'column',
              gap: '1.25rem',
              position: 'sticky',
              top: '1rem',
            }}
          >
            {/* Header */}
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.35rem' }}>
                <CategoryBadge category={activeSelected.category} />
                <SeverityBadge severity={activeSelected.severity} />
                <span
                  style={{
                    fontSize: 'var(--text-2xs)',
                    fontFamily: 'var(--font-mono)',
                    backgroundColor: 'var(--sev-3-dim)',
                    color: 'var(--sev-3)',
                    padding: '0.1rem 0.45rem',
                    borderRadius: 'var(--r-1)',
                    fontWeight: 700,
                  }}
                >
                  AWAITING OPERATOR VERIFICATION
                </span>
              </div>
              <h2 style={{ fontSize: 'var(--text-2xl)', fontWeight: 800, color: 'var(--text-primary)', margin: 0, letterSpacing: '-0.02em' }}>
                {activeSelected.title || `${activeSelected.category} Ingestion Event`}
              </h2>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.45rem', marginTop: '0.35rem', fontFamily: 'var(--font-mono)', fontSize: 'var(--text-xs)', color: 'var(--text-muted)' }}>
                <MapPin size={12} color="var(--teal)" />
                <span>{activeSelected.district ? `${activeSelected.district}, ` : ''}{activeSelected.state || 'India'}</span>
                <span>·</span>
                <span>Ingested {activeSelected.updated_at ? new Date(activeSelected.updated_at).toLocaleTimeString('en-IN') : 'Just now'}</span>
              </div>
            </div>

            {/* Evidence Telemetry Cross-Validation */}
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(3, 1fr)',
                gap: '0.75rem',
                padding: '0.85rem 1rem',
                backgroundColor: 'var(--bg-panel)',
                borderRadius: 'var(--r-1)',
                border: '1px solid var(--border-hairline)',
                fontFamily: 'var(--font-mono)',
              }}
            >
              <div>
                <div style={{ fontSize: 'var(--text-2xs)', color: 'var(--text-muted)' }}>AI CONFIDENCE</div>
                <div style={{ fontSize: 'var(--text-lg)', fontWeight: 700, color: 'var(--teal)' }}>
                  {Math.round(activeSelected.confidence_score * 100)}%
                </div>
              </div>
              <div>
                <div style={{ fontSize: 'var(--text-2xs)', color: 'var(--text-muted)' }}>SOURCE ACCREDITATION</div>
                <div style={{ fontSize: 'var(--text-lg)', fontWeight: 700, color: 'var(--text-primary)' }}>
                  {activeSelected.sources_count || 3} Feeds
                </div>
              </div>
              <div>
                <div style={{ fontSize: 'var(--text-2xs)', color: 'var(--text-muted)' }}>CROSS-SIGNALS</div>
                <div style={{ fontSize: 'var(--text-lg)', fontWeight: 700, color: 'var(--text-secondary)' }}>
                  {activeSelected.evidence_count || 8} Observations
                </div>
              </div>
            </div>

            {/* Ingested Description Narrative */}
            <div>
              <div style={{ fontSize: 'var(--text-2xs)', fontFamily: 'var(--font-mono)', color: 'var(--text-muted)', textTransform: 'uppercase', marginBottom: '0.35rem' }}>
                OBSERVATION TELEMETRY NARRATIVE
              </div>
              <div style={{ fontSize: 'var(--text-sm)', color: 'var(--text-body)', lineHeight: 1.6, padding: '0.75rem', backgroundColor: 'var(--bg-panel)', borderRadius: 'var(--r-1)', border: '1px solid var(--border-hairline)' }}>
                {activeSelected.description || activeSelected.summary || 'Automated multi-spectral anomaly ingestion triggered by radar reflectivity threshold crossing and localized ground pressure shift.'}
              </div>
            </div>

            {/* Operator Signature & Audit Note */}
            <div>
              <label
                htmlFor="verification-audit-note"
                style={{
                  display: 'block',
                  fontSize: 'var(--text-2xs)',
                  fontFamily: 'var(--font-mono)',
                  color: 'var(--text-secondary)',
                  fontWeight: 700,
                  textTransform: 'uppercase',
                  letterSpacing: '0.08em',
                  marginBottom: '0.35rem',
                }}
              >
                Operator Audit Justification & Notes (Optional)
              </label>
              <textarea
                id="verification-audit-note"
                rows={3}
                value={auditNote}
                onChange={(e) => setAuditNote(e.target.value)}
                placeholder="Document radar corroboration, AWS station IDs, or reason for rejection..."
                style={{
                  width: '100%',
                  backgroundColor: 'var(--bg-panel)',
                  border: '1px solid var(--border-hairline)',
                  borderRadius: 'var(--r-1)',
                  color: 'var(--text-primary)',
                  padding: '0.65rem',
                  fontSize: 'var(--text-xs)',
                  fontFamily: 'var(--font-sans)',
                  outline: 'none',
                }}
              />
            </div>

            {/* Action Buttons */}
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: '0.75rem', paddingTop: '0.75rem', borderTop: '1px solid var(--border-hairline)' }}>
              <Button
                variant="danger"
                size="md"
                onClick={() => handleAction('CONTRADICTED')}
                loading={actionLoading}
                icon={<X size={14} />}
              >
                MARK CONTRADICTED
              </Button>

              <Button
                variant="teal"
                size="md"
                onClick={() => handleAction('VERIFIED')}
                loading={actionLoading}
                icon={<Check size={14} />}
                withArrow
              >
                CONFIRM GROUND TRUTH
              </Button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
