/**
 * WeatherEventDNA Component — Signature Feature
 * ============================================
 * Deep operational and explainable DNA inspection for Weather Events:
 * - Persistent Event Identity & Geographic Footprint
 * - Multi-Source Evidence Fingerprint (IMD, Citizen, ERA5, etc.)
 * - Confidence Factor Decomposition & Multi-Dimensional Evidence Coverage
 * - Dynamic Weather Evidence Graph (DWEG) Kinematic Propagation Profile
 * - Chronological Event Milestone Journey
 * - Related Linked Events & Compact JSON Snapshot
 */
import React, { useEffect, useState } from 'react';
import type { EventDNAResponse } from '../../types';
import { eventsAPI } from '../../utils/api';
import {
  CategoryBadge,
  SeverityBadge,
  VerificationBadge,
  ConfidenceBar,
} from '../ui/Badges';
import { Button } from '../ui/Primitives';
import {
  Dna,
  ShieldCheck,
  Compass,
  Clock,
  Layers,
  Link2,
  Copy,
  Check,
  AlertTriangle,
  Info,
} from 'lucide-react';

interface WeatherEventDNAProps {
  eventId: string;
  initialData?: EventDNAResponse | null;
  onRefresh?: () => void;
  compact?: boolean;
}

export const WeatherEventDNA: React.FC<WeatherEventDNAProps> = ({
  eventId,
  initialData,
  compact = false,
}) => {
  const [dna, setDna] = useState<EventDNAResponse | null>(initialData || null);
  const [loading, setLoading] = useState<boolean>(!initialData);
  const [error, setError] = useState<string | null>(null);
  const [activeSection, setActiveSection] = useState<'fingerprint' | 'confidence' | 'timeline' | 'propagation' | 'snapshot'>('fingerprint');
  const [copied, setCopied] = useState<boolean>(false);

  useEffect(() => {
    let isMounted = true;
    const fetchDNA = async () => {
      try {
        setLoading(true);
        setError(null);
        const data = await eventsAPI.getDNA(eventId);
        if (isMounted) {
          setDna(data);
        }
      } catch (err: any) {
        if (isMounted) {
          setError(err?.message || 'Failed to load Event DNA profile');
        }
      } finally {
        if (isMounted) {
          setLoading(false);
        }
      }
    };

    fetchDNA();
    return () => {
      isMounted = false;
    };
  }, [eventId]);

  const handleCopySnapshot = () => {
    if (!dna) return;
    navigator.clipboard.writeText(JSON.stringify(dna.snapshot, null, 2));
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  if (loading) {
    return (
      <div style={{ padding: '1rem', display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: 'var(--brand-blue)' }}>
          <Dna className="animate-spin" size={18} />
          <span style={{ fontSize: 'var(--text-xs)', fontWeight: 600 }}>Sequencing Event DNA...</span>
        </div>
        <div style={{ height: '80px', backgroundColor: 'var(--bg-elevated)', borderRadius: 'var(--radius-md)' }} />
        <div style={{ height: '140px', backgroundColor: 'var(--bg-elevated)', borderRadius: 'var(--radius-md)' }} />
      </div>
    );
  }

  if (error || !dna) {
    return (
      <div style={{ padding: '1rem', backgroundColor: 'rgba(239, 68, 68, 0.08)', borderRadius: 'var(--radius-md)', border: '1px solid rgba(239, 68, 68, 0.2)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: 'var(--severity-4)', marginBottom: '0.25rem' }}>
          <AlertTriangle size={16} />
          <span style={{ fontSize: 'var(--text-xs)', fontWeight: 600 }}>DNA Extraction Failed</span>
        </div>
        <p style={{ margin: 0, fontSize: 'var(--text-xs)', color: 'var(--text-secondary)' }}>
          {error || 'Unable to retrieve genetic weather fingerprint.'}
        </p>
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem', width: '100%' }}>
      {/* ── DNA Identity Header ────────────────────────────────────────── */}
      <div
        style={{
          backgroundColor: 'var(--bg-elevated)',
          border: '1px solid var(--bg-border)',
          borderRadius: 'var(--radius-lg)',
          padding: '1rem',
          display: 'flex',
          flexDirection: 'column',
          gap: '0.75rem',
          background: 'linear-gradient(145deg, rgba(14, 165, 233, 0.06) 0%, rgba(30, 41, 59, 0.4) 100%)',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '0.5rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <Dna size={18} color="var(--brand-blue)" />
            <span style={{ fontSize: 'var(--text-sm)', fontWeight: 700, color: 'var(--text-primary)', letterSpacing: '0.02em' }}>
              EVENT DNA: <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--brand-blue)' }}>{dna.event_id.slice(0, 8)}</span>
            </span>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
            <CategoryBadge category={dna.event_type as any} />
            <SeverityBadge severity={dna.severity} />
            <VerificationBadge status={dna.status as any} />
          </div>
        </div>

        {/* Key Metrics Grid */}
        <div style={{ display: 'grid', gridTemplateColumns: compact ? '1fr 1fr' : 'repeat(auto-fit, minmax(100px, 1fr))', gap: '0.5rem' }}>
          {/* Confidence */}
          <div style={{ padding: '0.5rem', backgroundColor: 'var(--bg-primary)', borderRadius: 'var(--radius-md)', border: '1px solid var(--bg-border)' }}>
            <div style={{ fontSize: '10px', color: 'var(--text-muted)', textTransform: 'uppercase', fontWeight: 600 }}>Confidence</div>
            <div style={{ fontSize: 'var(--text-sm)', fontWeight: 700, color: 'var(--brand-blue)', fontFamily: 'var(--font-mono)' }}>
              {Math.round(dna.confidence.final_confidence * 100)}%
            </div>
            <ConfidenceBar value={dna.confidence.final_confidence} showValue={false} />
          </div>

          {/* Evidence Coverage */}
          <div style={{ padding: '0.5rem', backgroundColor: 'var(--bg-primary)', borderRadius: 'var(--radius-md)', border: '1px solid var(--bg-border)' }}>
            <div style={{ fontSize: '10px', color: 'var(--text-muted)', textTransform: 'uppercase', fontWeight: 600 }}>Coverage</div>
            <div style={{ fontSize: 'var(--text-sm)', fontWeight: 700, color: 'var(--severity-1)', fontFamily: 'var(--font-mono)' }}>
              {Math.round(dna.evidence_coverage.overall_coverage_score * 100)}%
            </div>
            <div style={{ height: '4px', width: '100%', backgroundColor: 'rgba(255,255,255,0.1)', borderRadius: '2px', overflow: 'hidden', marginTop: '4px' }}>
              <div style={{ width: `${Math.round(dna.evidence_coverage.overall_coverage_score * 100)}%`, height: '100%', backgroundColor: 'var(--severity-1)' }} />
            </div>
          </div>

          {/* Lifecycle */}
          <div style={{ padding: '0.5rem', backgroundColor: 'var(--bg-primary)', borderRadius: 'var(--radius-md)', border: '1px solid var(--bg-border)' }}>
            <div style={{ fontSize: '10px', color: 'var(--text-muted)', textTransform: 'uppercase', fontWeight: 600 }}>Lifecycle</div>
            <div style={{ fontSize: 'var(--text-xs)', fontWeight: 600, color: 'var(--text-primary)', marginTop: '2px' }}>
              {dna.lifecycle_phase}
            </div>
          </div>

          {/* Footprint */}
          <div style={{ padding: '0.5rem', backgroundColor: 'var(--bg-primary)', borderRadius: 'var(--radius-md)', border: '1px solid var(--bg-border)' }}>
            <div style={{ fontSize: '10px', color: 'var(--text-muted)', textTransform: 'uppercase', fontWeight: 600 }}>Footprint</div>
            <div style={{ fontSize: 'var(--text-xs)', fontWeight: 600, color: 'var(--text-primary)', marginTop: '2px', fontFamily: 'var(--font-mono)' }}>
              {dna.spatial_radius_km.toFixed(1)} km
            </div>
          </div>
        </div>
      </div>

      {/* ── Sub-Navigation Tabs ────────────────────────────────────────── */}
      <div
        style={{
          display: 'flex',
          gap: '0.25rem',
          borderBottom: '1px solid var(--bg-border)',
          overflowX: 'auto',
          paddingBottom: '0.25rem',
        }}
      >
        {[
          { id: 'fingerprint', label: 'Fingerprint', icon: <Layers size={13} />, count: dna.evidence.total_evidence_count },
          { id: 'confidence', label: 'Decomposition', icon: <ShieldCheck size={13} /> },
          { id: 'timeline', label: 'Milestones', icon: <Clock size={13} />, count: dna.timeline.length },
          { id: 'propagation', label: 'Propagation', icon: <Compass size={13} />, count: dna.propagation.stage_count },
          { id: 'snapshot', label: 'Snapshot', icon: <Copy size={13} /> },
        ].map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveSection(tab.id as any)}
            style={{
              background: activeSection === tab.id ? 'var(--bg-elevated)' : 'none',
              border: 'none',
              borderBottom: `2px solid ${activeSection === tab.id ? 'var(--brand-blue)' : 'transparent'}`,
              color: activeSection === tab.id ? 'var(--brand-blue)' : 'var(--text-secondary)',
              padding: '0.45rem 0.65rem',
              fontSize: 'var(--text-xs)',
              fontWeight: activeSection === tab.id ? 600 : 400,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '0.35rem',
              borderRadius: 'var(--radius-sm) var(--radius-sm) 0 0',
              whiteSpace: 'nowrap',
            }}
          >
            {tab.icon}
            <span>{tab.label}</span>
            {tab.count !== undefined && (
              <span
                style={{
                  fontSize: '10px',
                  padding: '1px 5px',
                  borderRadius: '10px',
                  backgroundColor: activeSection === tab.id ? 'rgba(59, 130, 246, 0.2)' : 'var(--bg-elevated)',
                  color: activeSection === tab.id ? 'var(--brand-blue)' : 'var(--text-muted)',
                }}
              >
                {tab.count}
              </span>
            )}
          </button>
        ))}
      </div>

      {/* ── Tab 1: Evidence Fingerprint ─────────────────────────────────── */}
      {activeSection === 'fingerprint' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
          {/* Multi-source Corroboration Badge */}
          <div
            style={{
              padding: '0.6rem 0.8rem',
              borderRadius: 'var(--radius-md)',
              backgroundColor: dna.evidence.cross_source_corroborated ? 'rgba(34, 197, 94, 0.08)' : 'rgba(234, 179, 8, 0.08)',
              border: `1px solid ${dna.evidence.cross_source_corroborated ? 'rgba(34, 197, 94, 0.25)' : 'rgba(234, 179, 8, 0.25)'}`,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              fontSize: 'var(--text-xs)',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
              <ShieldCheck size={15} color={dna.evidence.cross_source_corroborated ? 'var(--severity-1)' : 'var(--severity-2)'} />
              <span style={{ fontWeight: 600, color: 'var(--text-primary)' }}>
                {dna.evidence.cross_source_corroborated ? 'Cross-Source Corroborated' : 'Single / Isolated Source Stream'}
              </span>
            </div>
            <span style={{ color: 'var(--text-muted)', fontSize: '11px' }}>
              {dna.evidence.unique_sources_count} source provider(s)
            </span>
          </div>

          {/* Evidence Count Breakdown Summary */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '0.4rem', textAlign: 'center' }}>
            <div style={{ backgroundColor: 'var(--bg-elevated)', padding: '0.4rem', borderRadius: 'var(--radius-sm)' }}>
              <div style={{ fontSize: '10px', color: 'var(--text-muted)' }}>Total</div>
              <div style={{ fontSize: 'var(--text-xs)', fontWeight: 700, color: 'var(--text-primary)' }}>
                {dna.evidence.total_evidence_count}
              </div>
            </div>
            <div style={{ backgroundColor: 'var(--bg-elevated)', padding: '0.4rem', borderRadius: 'var(--radius-sm)' }}>
              <div style={{ fontSize: '10px', color: 'var(--severity-1)' }}>Support</div>
              <div style={{ fontSize: 'var(--text-xs)', fontWeight: 700, color: 'var(--severity-1)' }}>
                {dna.evidence.supporting_evidence_count}
              </div>
            </div>
            <div style={{ backgroundColor: 'var(--bg-elevated)', padding: '0.4rem', borderRadius: 'var(--radius-sm)' }}>
              <div style={{ fontSize: '10px', color: 'var(--severity-4)' }}>Conflict</div>
              <div style={{ fontSize: 'var(--text-xs)', fontWeight: 700, color: 'var(--severity-4)' }}>
                {dna.evidence.contradicting_evidence_count}
              </div>
            </div>
            <div style={{ backgroundColor: 'var(--bg-elevated)', padding: '0.4rem', borderRadius: 'var(--radius-sm)' }}>
              <div style={{ fontSize: '10px', color: 'var(--text-muted)' }}>Duplicates</div>
              <div style={{ fontSize: 'var(--text-xs)', fontWeight: 700, color: 'var(--text-muted)' }}>
                {dna.evidence.duplicate_count}
              </div>
            </div>
          </div>

          {/* Source Breakdown Cards */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
            <div style={{ fontSize: '11px', fontWeight: 600, color: 'var(--text-secondary)', textTransform: 'uppercase' }}>
              Observed Source Streams
            </div>

            {Object.entries(dna.evidence.sources).map(([srcType, srcData]) => (
              <div
                key={srcType}
                style={{
                  backgroundColor: 'var(--bg-elevated)',
                  border: '1px solid var(--bg-border)',
                  borderRadius: 'var(--radius-md)',
                  padding: '0.65rem 0.8rem',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '0.35rem',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <span style={{ fontSize: 'var(--text-xs)', fontWeight: 600, color: 'var(--text-primary)' }}>
                    {srcType}
                  </span>
                  <span style={{ fontSize: '11px', color: 'var(--brand-blue)', fontWeight: 600 }}>
                    Weight: {(srcData.confidence_weight * 100).toFixed(0)}%
                  </span>
                </div>

                {/* Progress bar showing supporting vs contradicting */}
                <div style={{ display: 'flex', height: '6px', borderRadius: '3px', overflow: 'hidden', backgroundColor: 'rgba(255,255,255,0.08)' }}>
                  <div
                    style={{
                      width: `${(srcData.supporting_observations / Math.max(1, srcData.total_observations)) * 100}%`,
                      backgroundColor: 'var(--severity-1)',
                    }}
                  />
                  <div
                    style={{
                      width: `${(srcData.contradicting_observations / Math.max(1, srcData.total_observations)) * 100}%`,
                      backgroundColor: 'var(--severity-4)',
                    }}
                  />
                  <div
                    style={{
                      width: `${(srcData.unverified_observations / Math.max(1, srcData.total_observations)) * 100}%`,
                      backgroundColor: 'var(--text-muted)',
                    }}
                  />
                </div>

                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '10px', color: 'var(--text-muted)' }}>
                  <span>{srcData.total_observations} report(s)</span>
                  <span>Spatial: {srcData.spatial_coverage_km.toFixed(1)} km</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── Tab 2: Confidence Factor Decomposition ────────────────────── */}
      {activeSection === 'confidence' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
          {/* Explanation Banner */}
          <div style={{ padding: '0.65rem', backgroundColor: 'var(--bg-elevated)', borderRadius: 'var(--radius-md)', border: '1px solid var(--bg-border)', fontSize: 'var(--text-xs)', color: 'var(--text-secondary)' }}>
            <div style={{ fontWeight: 600, color: 'var(--text-primary)', marginBottom: '0.2rem', display: 'flex', alignItems: 'center', gap: '0.3rem' }}>
              <Info size={13} color="var(--brand-blue)" /> Rationale & Decomposition
            </div>
            {dna.confidence.explanation}
          </div>

          {/* Factor Breakdown Bars */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
            {[
              { label: 'Source Reliability', val: dna.confidence.source_reliability_score, max: 0.35, color: 'var(--brand-blue)' },
              { label: 'Cross-Source Support', val: dna.confidence.cross_source_support_score, max: 0.25, color: '#38bdf8' },
              { label: 'Spatial Consistency', val: dna.confidence.spatial_consistency_score, max: 0.15, color: '#4ade80' },
              { label: 'Temporal Consistency', val: dna.confidence.temporal_consistency_score, max: 0.15, color: '#a3e635' },
              { label: 'Meteorological Agreement', val: dna.confidence.meteorological_score, max: 0.10, color: '#facc15' },
              { label: 'Media Corroboration', val: dna.confidence.media_score, max: 0.10, color: '#c084fc' },
            ].map((factor) => (
              <div key={factor.label} style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px' }}>
                  <span style={{ color: 'var(--text-secondary)' }}>{factor.label}</span>
                  <span style={{ fontWeight: 600, color: 'var(--text-primary)', fontFamily: 'var(--font-mono)' }}>
                    +{(factor.val * 100).toFixed(1)}%
                  </span>
                </div>
                <div style={{ height: '4px', width: '100%', backgroundColor: 'rgba(255,255,255,0.08)', borderRadius: '2px', overflow: 'hidden' }}>
                  <div style={{ width: `${Math.min(100, (factor.val / factor.max) * 100)}%`, height: '100%', backgroundColor: factor.color }} />
                </div>
              </div>
            ))}

            {dna.confidence.contradiction_penalty > 0 && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '2px', marginTop: '0.25rem' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px', color: 'var(--severity-4)' }}>
                  <span>Contradiction Penalty</span>
                  <span style={{ fontWeight: 700, fontFamily: 'var(--font-mono)' }}>
                    -{(dna.confidence.contradiction_penalty * 100).toFixed(1)}%
                  </span>
                </div>
                <div style={{ height: '4px', width: '100%', backgroundColor: 'rgba(255,255,255,0.08)', borderRadius: '2px', overflow: 'hidden' }}>
                  <div style={{ width: `${Math.min(100, dna.confidence.contradiction_penalty * 100)}%`, height: '100%', backgroundColor: 'var(--severity-4)' }} />
                </div>
              </div>
            )}
          </div>

          {/* Multi-Dimensional Evidence Coverage Breakdown */}
          <div style={{ marginTop: '0.5rem', padding: '0.75rem', backgroundColor: 'var(--bg-elevated)', borderRadius: 'var(--radius-md)', border: '1px solid var(--bg-border)' }}>
            <div style={{ fontSize: '11px', fontWeight: 600, color: 'var(--text-primary)', marginBottom: '0.4rem', textTransform: 'uppercase' }}>
              6-Dimension Evidence Coverage ({dna.evidence_coverage.active_dimensions_count}/6 Active)
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.4rem', fontSize: '10px' }}>
              <div>• Temporal: {(dna.evidence_coverage.temporal_coverage * 100).toFixed(0)}%</div>
              <div>• Spatial: {(dna.evidence_coverage.spatial_coverage * 100).toFixed(0)}%</div>
              <div>• Diversity: {(dna.evidence_coverage.source_diversity_coverage * 100).toFixed(0)}%</div>
              <div>• Met-Model: {(dna.evidence_coverage.meteorological_coverage * 100).toFixed(0)}%</div>
              <div>• Official: {(dna.evidence_coverage.official_validation_coverage * 100).toFixed(0)}%</div>
              <div>• Corroboration: {(dna.evidence_coverage.corroboration_coverage * 100).toFixed(0)}%</div>
            </div>
          </div>
        </div>
      )}

      {/* ── Tab 3: Milestone Journey Timeline ─────────────────────────── */}
      {activeSection === 'timeline' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
          <div style={{ fontSize: '11px', fontWeight: 600, color: 'var(--text-secondary)', textTransform: 'uppercase' }}>
            Event Genesis & Evolution
          </div>

          <div style={{ position: 'relative', paddingLeft: '1.25rem', display: 'flex', flexDirection: 'column', gap: '1rem' }}>
            {/* Timeline vertical bar */}
            <div
              style={{
                position: 'absolute',
                left: '5px',
                top: '4px',
                bottom: '4px',
                width: '2px',
                backgroundColor: 'rgba(59, 130, 246, 0.3)',
              }}
            />

            {dna.timeline.map((entry, idx) => (
              <div key={idx} style={{ position: 'relative', display: 'flex', flexDirection: 'column', gap: '0.2rem' }}>
                {/* Milestone Node Dot */}
                <div
                  style={{
                    position: 'absolute',
                    left: '-1.25rem',
                    top: '2px',
                    width: '8px',
                    height: '8px',
                    borderRadius: '50%',
                    backgroundColor: idx === 0 ? 'var(--brand-blue)' : idx === dna.timeline.length - 1 ? 'var(--severity-1)' : 'var(--text-muted)',
                    boxShadow: '0 0 0 2px var(--bg-surface)',
                  }}
                />

                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <span style={{ fontSize: 'var(--text-xs)', fontWeight: 600, color: 'var(--text-primary)' }}>
                    {entry.title}
                  </span>
                  <span style={{ fontSize: '10px', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
                    {new Date(entry.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                  </span>
                </div>

                <p style={{ margin: 0, fontSize: '11px', color: 'var(--text-secondary)', lineHeight: 1.4 }}>
                  {entry.description}
                </p>

                {entry.confidence_at_step !== null && entry.confidence_at_step !== undefined && (
                  <div style={{ fontSize: '10px', color: 'var(--brand-blue)', fontWeight: 500 }}>
                    Confidence at step: {Math.round(entry.confidence_at_step * 100)}%
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── Tab 4: Kinematic Propagation Profile ───────────────────────── */}
      {activeSection === 'propagation' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
          {dna.propagation.has_propagation ? (
            <>
              {/* Overall Vector Card */}
              <div
                style={{
                  backgroundColor: 'var(--bg-elevated)',
                  border: '1px solid var(--bg-border)',
                  borderRadius: 'var(--radius-md)',
                  padding: '0.75rem',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                }}
              >
                <div>
                  <div style={{ fontSize: '10px', color: 'var(--text-muted)', textTransform: 'uppercase' }}>Propagation Vector</div>
                  <div style={{ fontSize: 'var(--text-sm)', fontWeight: 700, color: 'var(--brand-blue)' }}>
                    {dna.propagation.overall_direction} @ {dna.propagation.average_speed_kmh.toFixed(1)} km/h
                  </div>
                </div>
                <div style={{ textAlign: 'right' }}>
                  <div style={{ fontSize: '10px', color: 'var(--text-muted)', textTransform: 'uppercase' }}>Total Distance</div>
                  <div style={{ fontSize: 'var(--text-sm)', fontWeight: 700, color: 'var(--text-primary)', fontFamily: 'var(--font-mono)' }}>
                    {dna.propagation.total_distance_km.toFixed(1)} km
                  </div>
                </div>
              </div>

              {/* Stage Cards */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
                <div style={{ fontSize: '11px', fontWeight: 600, color: 'var(--text-secondary)', textTransform: 'uppercase' }}>
                  Tracked Spatial Stages
                </div>

                {dna.propagation.stages.map((stage) => (
                  <div
                    key={stage.stage_number}
                    style={{
                      backgroundColor: 'var(--bg-primary)',
                      border: '1px solid var(--bg-border)',
                      borderRadius: 'var(--radius-sm)',
                      padding: '0.5rem 0.65rem',
                      display: 'flex',
                      flexDirection: 'column',
                      gap: '0.2rem',
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 'var(--text-xs)' }}>
                      <span style={{ fontWeight: 600, color: 'var(--text-primary)' }}>
                        Stage {stage.stage_number}: {stage.direction_name}
                      </span>
                      <span style={{ color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', fontSize: '10px' }}>
                        {new Date(stage.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                      </span>
                    </div>
                    <div style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>
                      {stage.stage_description}
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '10px', color: 'var(--text-muted)' }}>
                      <span>Lat: {stage.center_latitude.toFixed(2)}, Lon: {stage.center_longitude.toFixed(2)}</span>
                      <span>{stage.distance_from_origin_km.toFixed(1)} km from origin</span>
                    </div>
                  </div>
                ))}
              </div>
            </>
          ) : (
            <div style={{ padding: '1.25rem', textAlign: 'center', backgroundColor: 'var(--bg-elevated)', borderRadius: 'var(--radius-md)' }}>
              <Compass size={24} color="var(--text-muted)" style={{ margin: '0 auto 0.5rem auto' }} />
              <div style={{ fontSize: 'var(--text-xs)', fontWeight: 600, color: 'var(--text-primary)' }}>
                Stationary / Single-Point Event
              </div>
              <p style={{ margin: '0.25rem 0 0 0', fontSize: '11px', color: 'var(--text-secondary)' }}>
                No cross-region spatial propagation vector detected for this event cluster.
              </p>
            </div>
          )}

          {/* Related Events Link */}
          {dna.related_events && dna.related_events.length > 0 && (
            <div style={{ marginTop: '0.5rem' }}>
              <div style={{ fontSize: '11px', fontWeight: 600, color: 'var(--text-secondary)', textTransform: 'uppercase', marginBottom: '0.35rem' }}>
                Related Topological Events ({dna.related_events.length})
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.35rem' }}>
                {dna.related_events.map((rel) => (
                  <div
                    key={rel.event_id}
                    style={{
                      padding: '0.45rem 0.6rem',
                      borderRadius: 'var(--radius-sm)',
                      backgroundColor: 'var(--bg-elevated)',
                      border: '1px solid var(--bg-border)',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      fontSize: '11px',
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
                      <Link2 size={12} color="var(--brand-blue)" />
                      <span style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{rel.category}</span>
                      <span style={{ color: 'var(--text-muted)' }}>({rel.relationship_type})</span>
                    </div>
                    <span style={{ color: 'var(--text-secondary)', fontFamily: 'var(--font-mono)' }}>
                      {rel.distance_km ? `${rel.distance_km.toFixed(1)} km` : 'Co-located'}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* ── Tab 5: Compact Snapshot ────────────────────────────────────── */}
      {activeSection === 'snapshot' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ fontSize: '11px', fontWeight: 600, color: 'var(--text-secondary)', textTransform: 'uppercase' }}>
              Persistent DNA Snapshot
            </span>
            <Button size="sm" variant="secondary" onClick={handleCopySnapshot} style={{ padding: '2px 8px', fontSize: '10px' }}>
              {copied ? <Check size={12} color="var(--severity-1)" /> : <Copy size={12} />}
              <span style={{ marginLeft: '4px' }}>{copied ? 'Copied' : 'Copy JSON'}</span>
            </Button>
          </div>

          <pre
            style={{
              backgroundColor: 'var(--bg-primary)',
              border: '1px solid var(--bg-border)',
              borderRadius: 'var(--radius-md)',
              padding: '0.75rem',
              fontSize: '11px',
              fontFamily: 'var(--font-mono)',
              color: 'var(--text-secondary)',
              overflowX: 'auto',
              margin: 0,
              maxHeight: '220px',
            }}
          >
            {JSON.stringify(dna.snapshot, null, 2)}
          </pre>
        </div>
      )}
    </div>
  );
};
