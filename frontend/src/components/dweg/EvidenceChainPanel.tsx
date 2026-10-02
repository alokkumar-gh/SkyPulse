/**
 * EvidenceChainPanel Component — Phase 10
 * Explainable multi-source evidence provenance chain and synthetic narrative.
 * Displays step-by-step signals that corroborate the event.
 */

import React from 'react';
import { ShieldCheck, Clock, MapPin, Sparkles } from 'lucide-react';
import type { EvidenceChainResponse, EvidenceChainStep } from '../../types';


interface EvidenceChainPanelProps {
  evidenceChain: EvidenceChainResponse | null;
  isLoading?: boolean;
}

const SOURCE_BADGE_COLORS: Record<string, { bg: string; text: string; border: string }> = {
  CITIZEN: { bg: 'rgba(245, 158, 11, 0.15)', text: '#f59e0b', border: 'rgba(245, 158, 11, 0.3)' },
  CITIZEN_REPORT: { bg: 'rgba(245, 158, 11, 0.15)', text: '#f59e0b', border: 'rgba(245, 158, 11, 0.3)' },
  GOVERNMENT_API: { bg: 'rgba(16, 185, 129, 0.15)', text: '#10b981', border: 'rgba(16, 185, 129, 0.3)' },
  WEATHER_API: { bg: 'rgba(56, 189, 248, 0.15)', text: '#38bdf8', border: 'rgba(56, 189, 248, 0.3)' },
  IOT_SENSOR: { bg: 'rgba(168, 85, 247, 0.15)', text: '#a855f7', border: 'rgba(168, 85, 247, 0.3)' },
  SOCIAL_MEDIA: { bg: 'rgba(236, 72, 153, 0.15)', text: '#ec4899', border: 'rgba(236, 72, 153, 0.3)' },
  PROPAGATION_DETECTED: { bg: 'rgba(249, 115, 22, 0.15)', text: '#f97316', border: 'rgba(249, 115, 22, 0.3)' },
};

export const EvidenceChainPanel: React.FC<EvidenceChainPanelProps> = ({
  evidenceChain,
  isLoading = false,
}) => {
  if (isLoading) {
    return (
      <div
        style={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          padding: '2rem',
          backgroundColor: 'var(--bg-surface, #0f172a)',
          borderRadius: 'var(--radius-lg, 8px)',
          border: '1px solid var(--bg-border, #334155)',
          color: 'var(--text-muted, #64748b)',
          fontSize: '13px',
          gap: '0.5rem',
        }}
      >
        <Sparkles size={20} className="animate-spin" color="var(--brand-blue, #38bdf8)" />
        Reconstructing evidence chain narrative...
      </div>
    );
  }

  if (!evidenceChain) {
    return (
      <div
        style={{
          padding: '1.5rem',
          backgroundColor: 'var(--bg-surface, #0f172a)',
          borderRadius: 'var(--radius-lg, 8px)',
          border: '1px solid var(--bg-border, #334155)',
          color: 'var(--text-muted, #64748b)',
          textAlign: 'center',
          fontSize: '13px',
        }}
      >
        No evidence chain available for this event.
      </div>
    );
  }

  const confidencePercent = Math.round(evidenceChain.confidence * 100);

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        gap: '1.25rem',
        backgroundColor: 'var(--bg-surface, #0f172a)',
        borderRadius: 'var(--radius-lg, 8px)',
        border: '1px solid var(--bg-border, #334155)',
        padding: '1.25rem',
      }}
    >
      {/* Narrative Synthesis Card */}
      <div
        style={{
          backgroundColor: 'var(--bg-elevated, #1e293b)',
          borderRadius: 'var(--radius-md, 6px)',
          border: '1px solid var(--bg-border, #334155)',
          padding: '1rem',
          position: 'relative',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', color: 'var(--brand-blue, #38bdf8)', fontSize: '12px', fontWeight: 600 }}>
            <Sparkles size={15} />
            <span>EXPLAINABLE EVIDENCE NARRATIVE</span>
          </div>

          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '4px',
              backgroundColor: confidencePercent >= 75 ? 'rgba(16, 185, 129, 0.15)' : 'rgba(245, 158, 11, 0.15)',
              color: confidencePercent >= 75 ? '#10b981' : '#f59e0b',
              padding: '2px 8px',
              borderRadius: '4px',
              fontSize: '11px',
              fontWeight: 600,
            }}
          >
            <ShieldCheck size={12} />
            <span>{confidencePercent}% Confidence</span>
          </div>
        </div>

        <p
          style={{
            margin: 0,
            fontSize: '13px',
            lineHeight: 1.6,
            color: 'var(--text-primary, #f1f5f9)',
          }}
        >
          {evidenceChain.narrative}
        </p>
      </div>

      {/* Structured Chronological Steps */}
      <div>
        <h4 style={{ margin: '0 0 0.75rem 0', fontSize: '13px', fontWeight: 600, color: 'var(--text-secondary, #94a3b8)' }}>
          CORROBORATION PROVENANCE CHAIN ({evidenceChain.evidence_chain.length} STEPS)
        </h4>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.6rem' }}>
          {evidenceChain.evidence_chain.map((step: EvidenceChainStep) => {
            const badgeStyle = SOURCE_BADGE_COLORS[step.type] || SOURCE_BADGE_COLORS[step.source] || {
              bg: 'rgba(100, 116, 139, 0.15)',
              text: '#94a3b8',
              border: 'rgba(100, 116, 139, 0.3)',
            };

            const isProp = step.type === 'PROPAGATION_DETECTED';

            return (
              <div
                key={step.step}
                style={{
                  display: 'flex',
                  gap: '0.75rem',
                  alignItems: 'flex-start',
                  padding: '0.75rem',
                  backgroundColor: isProp ? 'rgba(249, 115, 22, 0.08)' : 'var(--bg-elevated, #1e293b)',
                  borderRadius: '6px',
                  border: isProp ? '1px solid rgba(249, 115, 22, 0.3)' : '1px solid var(--bg-border, #334155)',
                }}
              >
                {/* Step Index Badge */}
                <div
                  style={{
                    width: '24px',
                    height: '24px',
                    borderRadius: '50%',
                    backgroundColor: isProp ? '#f97316' : 'var(--bg-surface, #0f172a)',
                    border: '1px solid var(--bg-border, #334155)',
                    color: isProp ? '#ffffff' : '#94a3b8',
                    fontSize: '11px',
                    fontWeight: 700,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    flexShrink: 0,
                  }}
                >
                  {step.step}
                </div>

                {/* Step Body */}
                <div style={{ flex: 1 }}>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '0.4rem' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                      <span
                        style={{
                          fontSize: '10px',
                          fontWeight: 700,
                          padding: '1px 6px',
                          borderRadius: '4px',
                          backgroundColor: badgeStyle.bg,
                          color: badgeStyle.text,
                          border: `1px solid ${badgeStyle.border}`,
                        }}
                      >
                        {step.source || step.type}
                      </span>

                      {step.location && (
                        <span style={{ fontSize: '11px', color: 'var(--text-secondary, #94a3b8)', display: 'flex', alignItems: 'center', gap: '2px' }}>
                          <MapPin size={11} />
                          {step.location}
                        </span>
                      )}
                    </div>

                    {step.at && (
                      <span style={{ fontSize: '11px', color: 'var(--text-muted, #64748b)', display: 'flex', alignItems: 'center', gap: '3px' }}>
                        <Clock size={11} />
                        {new Date(step.at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                      </span>
                    )}
                  </div>

                  <div style={{ marginTop: '0.35rem', fontSize: '12px', color: 'var(--text-primary, #f1f5f9)', lineHeight: 1.4 }}>
                    {step.value}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};
