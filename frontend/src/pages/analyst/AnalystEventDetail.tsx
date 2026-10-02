/**
 * AnalystEventDetail Page — Phase 9
 * Full event operational triage view for analysts.
 * Combines canonical event inspection, multi-signal evidence, override controls,
 * and duplicate cluster splitting / merging.
 */
import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { eventsAPI, verificationAPI } from '../../utils/api';
import type { WeatherEvent, VerificationResult, DuplicateCluster } from '../../types';
import {
  CategoryBadge,
  SeverityBadge,
  VerificationBadge,
  ConfidenceBar,
} from '../../components/ui/Badges';
import { Button, Card, Input, Select } from '../../components/ui/Primitives';
import { DuplicateClusterPanel } from '../../components/analyst/DuplicateClusterPanel';
import { WeatherEventDNA } from '../../components/events/WeatherEventDNA';
import { DetailSkeleton } from '../../components/ui/States';
import {
  ShieldCheck,
  ArrowLeft,
  MapPin,
  CheckCircle,
  AlertTriangle,
  FileText,
  Send,
} from 'lucide-react';

export const AnalystEventDetail: React.FC = () => {
  const { eventId } = useParams<{ eventId: string }>();
  const navigate = useNavigate();

  const [event, setEvent] = useState<WeatherEvent | null>(null);
  const [verification, setVerification] = useState<VerificationResult | null>(null);
  const [cluster, setCluster] = useState<DuplicateCluster | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Override Form State
  const [overrideStatus, setOverrideStatus] = useState<string>('VERIFIED');
  const [overrideReason, setOverrideReason] = useState<string>('');
  const [overrideLoading, setOverrideLoading] = useState(false);
  const [overrideSuccess, setOverrideSuccess] = useState<string | null>(null);

  const loadData = async () => {
    if (!eventId) return;
    try {
      setLoading(true);
      setError(null);
      const [evData, verData, clustersData] = await Promise.all([
        eventsAPI.get(eventId),
        verificationAPI.get(eventId).catch(() => null),
        verificationAPI.clusters(eventId, 1).catch(() => []),
      ]);
      setEvent(evData);
      setVerification(verData);
      setCluster(clustersData && clustersData.length > 0 ? clustersData[0] : null);
    } catch (err: any) {
      setError(err?.message || 'Failed to load event details');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [eventId]);

  const handleApplyOverride = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!eventId || overrideReason.trim().length < 5) return;
    try {
      setOverrideLoading(true);
      setOverrideSuccess(null);
      const res = await verificationAPI.override(eventId, overrideStatus, overrideReason);
      setVerification(res);
      if (event) {
        setEvent({
          ...event,
          verification_status: res.status,
          confidence_score: res.confidence_score,
        });
      }
      setOverrideSuccess(`Successfully updated status to ${res.status}.`);
      setOverrideReason('');
    } catch (err: any) {
      setError(err?.message || 'Failed to apply manual override');
    } finally {
      setOverrideLoading(false);
    }
  };

  if (loading) {
    return (
      <div style={{ padding: '1.5rem', maxWidth: '1280px', margin: '0 auto' }}>
        <DetailSkeleton />
      </div>
    );
  }

  if (error || !event) {
    return (
      <div style={{ padding: '2rem', textAlign: 'center', maxWidth: '600px', margin: '2rem auto' }}>
        <AlertTriangle size={36} color="var(--severity-4)" style={{ marginBottom: '1rem' }} />
        <h3 style={{ margin: '0 0 0.5rem 0', color: 'var(--text-primary)' }}>Event Not Found or Error</h3>
        <p style={{ color: 'var(--text-secondary)', fontSize: 'var(--text-sm)' }}>
          {error || `Weather event ${eventId} could not be loaded.`}
        </p>
        <Button variant="secondary" onClick={() => navigate('/analyst/queue')} style={{ marginTop: '1rem' }}>
          Back to Verification Queue
        </Button>
      </div>
    );
  }

  const locationStr =
    [event.location?.city, event.location?.district, event.location?.state].filter(Boolean).join(', ') ||
    event.state ||
    'India';

  return (
    <div
      style={{
        padding: '1.5rem',
        maxWidth: '1360px',
        margin: '0 auto',
        width: '100%',
        display: 'flex',
        flexDirection: 'column',
        gap: '1.5rem',
      }}
    >
      {/* Top Nav / Actions */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '1rem' }}>
        <Button
          size="sm"
          variant="secondary"
          icon={<ArrowLeft size={14} />}
          onClick={() => navigate('/analyst/queue')}
        >
          Verification Queue
        </Button>

        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          <CategoryBadge category={event.category} />
          <SeverityBadge severity={event.severity} />
          <VerificationBadge status={event.verification_status} />
        </div>
      </div>

      {/* Overview Card */}
      <Card>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '1.5rem' }}>
          <div>
            <h1 style={{ margin: '0 0 0.5rem 0', fontSize: 'var(--text-xl)', fontWeight: 700, color: 'var(--text-primary)' }}>
              {event.title || `${event.category} Event in ${locationStr}`}
            </h1>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: 'var(--text-secondary)', fontSize: 'var(--text-xs)', marginBottom: '0.75rem' }}>
              <MapPin size={14} color="var(--brand-blue)" />
              <span>{locationStr}</span>
              {event.location?.lat && event.location?.lon && (
                <span style={{ color: 'var(--text-muted)' }}>
                  ({event.location.lat.toFixed(3)}, {event.location.lon.toFixed(3)})
                </span>
              )}
            </div>

            <p style={{ fontSize: 'var(--text-sm)', color: 'var(--text-secondary)', margin: 0 }}>
              {event.description || 'Continuous observation synthesized from correlated multi-source weather telemetry.'}
            </p>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', justifyContent: 'center' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 'var(--text-xs)', color: 'var(--text-secondary)' }}>
              <span>First Reported</span>
              <span style={{ color: 'var(--text-primary)', fontWeight: 500 }}>
                {event.first_reported_at ? new Date(event.first_reported_at).toLocaleString('en-IN') : '—'}
              </span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 'var(--text-xs)', color: 'var(--text-secondary)' }}>
              <span>Corroborating Evidence</span>
              <span style={{ color: 'var(--text-primary)', fontWeight: 600 }}>
                {event.evidence_count} report(s)
              </span>
            </div>
            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 'var(--text-xs)', marginBottom: '0.25rem' }}>
                <span style={{ color: 'var(--text-secondary)' }}>Verification Confidence</span>
                <span style={{ fontWeight: 600, color: 'var(--text-primary)' }}>
                  {Math.round((event.confidence_score ?? 0.5) * 100)}%
                </span>
              </div>
              <ConfidenceBar value={event.confidence_score ?? 0.5} />
            </div>
          </div>
        </div>
      </Card>

      {/* Weather Event DNA Section */}
      <Card>
        <WeatherEventDNA eventId={event.id} />
      </Card>

      {/* Middle Row: Verification Signals & Analyst Override Form */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(380px, 1fr))', gap: '1.5rem' }}>
        {/* Verification Signals & Explanation */}
        <Card>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '1rem' }}>
            <ShieldCheck size={18} color="var(--brand-blue)" />
            <h3 style={{ margin: 0, fontSize: 'var(--text-base)', fontWeight: 600, color: 'var(--text-primary)' }}>
              AI Multi-Signal Verification
            </h3>
          </div>

          <div style={{ marginBottom: '1rem', padding: '0.75rem', borderRadius: 'var(--radius-md)', backgroundColor: 'var(--bg-elevated)', border: '1px solid var(--bg-border)' }}>
            <div style={{ fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase', fontWeight: 600, marginBottom: '0.25rem' }}>
              Verification Rationale
            </div>
            <p style={{ margin: 0, fontSize: 'var(--text-xs)', color: 'var(--text-secondary)' }}>
              {verification?.explanation_text || 'Multi-source consensus evaluation pending automated corroboration cycle.'}
            </p>
          </div>

          <div style={{ fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase', fontWeight: 600, marginBottom: '0.5rem' }}>
            Signal Contributions
          </div>

          {verification?.evidence_items && verification.evidence_items.length > 0 ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
              {verification.evidence_items.map((item, idx) => (
                <div
                  key={idx}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    padding: '0.4rem 0.6rem',
                    borderRadius: 'var(--radius-sm)',
                    backgroundColor: 'var(--bg-primary)',
                    fontSize: 'var(--text-xs)',
                  }}
                >
                  <div>
                    <span style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{item.evidence_type}</span>
                    <span style={{ color: 'var(--text-muted)', marginLeft: '0.4rem' }}>{item.source_name}</span>
                  </div>
                  <span style={{ color: 'var(--brand-blue)', fontWeight: 600 }}>
                    {item.weight_contribution ? `+${(item.weight_contribution * 100).toFixed(0)}%` : '100%'}
                  </span>
                </div>
              ))}
            </div>
          ) : (
            <div style={{ color: 'var(--text-muted)', fontSize: 'var(--text-xs)', fontStyle: 'italic' }}>
              No individual evidence signals captured.
            </div>
          )}
        </Card>

        {/* Analyst Override Form */}
        <Card>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '1rem' }}>
            <FileText size={18} color="var(--severity-3)" />
            <h3 style={{ margin: 0, fontSize: 'var(--text-base)', fontWeight: 600, color: 'var(--text-primary)' }}>
              Manual Override Decision
            </h3>
          </div>

          {overrideSuccess && (
            <div
              style={{
                padding: '0.625rem 0.75rem',
                borderRadius: 'var(--radius-md)',
                backgroundColor: 'rgba(34, 197, 94, 0.15)',
                border: '1px solid rgba(34, 197, 94, 0.3)',
                color: 'var(--severity-1)',
                fontSize: 'var(--text-xs)',
                display: 'flex',
                alignItems: 'center',
                gap: '0.5rem',
                marginBottom: '1rem',
              }}
            >
              <CheckCircle size={14} />
              <span>{overrideSuccess}</span>
            </div>
          )}

          <form onSubmit={handleApplyOverride} style={{ display: 'flex', flexDirection: 'column', gap: '0.85rem' }}>
            <div>
              <label style={{ display: 'block', fontSize: 'var(--text-xs)', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '0.35rem' }}>
                Target Verification Status
              </label>
              <Select
                value={overrideStatus}
                onChange={(e) => setOverrideStatus(e.target.value)}
                options={[
                  { value: 'VERIFIED', label: 'VERIFIED - Formally Confirmed' },
                  { value: 'LIKELY', label: 'LIKELY - Strong Supporting Signals' },
                  { value: 'UNVERIFIED', label: 'UNVERIFIED - Insufficient Corroboration' },
                  { value: 'REQUIRES_REVIEW', label: 'REQUIRES_REVIEW - Needs More Evidence' },
                  { value: 'CONTRADICTED', label: 'CONTRADICTED - Rejected / Disproven' },
                ]}
              />
            </div>

            <div>
              <label style={{ display: 'block', fontSize: 'var(--text-xs)', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '0.35rem' }}>
                Operational Justification (Required)
              </label>
              <Input
                placeholder="Reason for manual override (minimum 5 characters)..."
                value={overrideReason}
                onChange={(e) => setOverrideReason(e.target.value)}
                style={{ width: '100%' }}
              />
            </div>

            <Button
              type="submit"
              variant="primary"
              disabled={overrideReason.trim().length < 5}
              loading={overrideLoading}
              icon={<Send size={14} />}
              style={{ alignSelf: 'flex-start', marginTop: '0.25rem' }}
            >
              Submit Override & Audit Log
            </Button>
          </form>
        </Card>
      </div>

      {/* Duplicate Cluster Panel (Split / Merge Operations) */}
      <DuplicateClusterPanel
        cluster={cluster}
        eventId={eventId}
        onClusterUpdated={loadData}
      />
    </div>
  );
};
