/**
 * SkyPulse AI Intelligence & Confidence Experience
 * Implements Sections 20 & 21:
 * "AI and derived intelligence must communicate confidence clearly with evidence."
 * "AI should feel integrated into the data experience. Do NOT create generic 'Ask AI' chatbots."
 */

import React, { useState } from 'react';
import {
  Sparkles, CheckCircle2, ChevronDown, ChevronRight, ArrowRight,
} from 'lucide-react';

export interface AISourceEvidence {
  name: string;
  count: number;
  type: string;
  reliability: number; // 0 to 100
}

interface AIConfidenceProps {
  score: number; // 0 - 100
  sourcesCount?: number;
  observationsCount?: number;
  evidenceItems?: AISourceEvidence[];
  compact?: boolean;
}

export const AIConfidenceBadge: React.FC<AIConfidenceProps> = ({
  score,
  sourcesCount = 4,
  observationsCount = 1284,
  compact = false,
}) => {
  const getLevel = () => {
    if (score >= 80) return { label: 'High confidence', color: 'var(--status-verified)', bg: 'var(--sev-1-dim)' };
    if (score >= 60) return { label: 'Moderate confidence', color: 'var(--teal)', bg: 'var(--teal-100)' };
    return { label: 'Limited confidence', color: 'var(--sev-2)', bg: 'var(--sev-2-dim)' };
  };

  const level = getLevel();

  if (compact) {
    return (
      <div
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: '0.4rem',
          padding: '0.15rem 0.5rem',
          borderRadius: 'var(--r-1)',
          backgroundColor: level.bg,
          border: `1px solid ${level.color}`,
          fontFamily: 'var(--font-mono)',
          fontSize: 'var(--text-2xs)',
        }}
        title={`AI Confidence: ${score}% (${level.label})`}
      >
        <Sparkles size={10} color={level.color} />
        <span style={{ fontWeight: 700, color: level.color }}>{score}%</span>
        <span style={{ color: 'var(--text-muted)' }}>{level.label}</span>
      </div>
    );
  }

  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '0.5rem 0.85rem',
        borderRadius: 'var(--r-1)',
        backgroundColor: 'var(--bg-panel)',
        border: '1px solid var(--border-hairline)',
        fontFamily: 'var(--font-mono)',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
        <Sparkles size={13} color="var(--teal)" />
        <div>
          <span style={{ fontSize: 'var(--text-2xs)', color: 'var(--text-muted)', letterSpacing: '0.08em', textTransform: 'uppercase' }}>
            AI CONFIDENCE
          </span>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: '0.4rem' }}>
            <span style={{ fontSize: 'var(--text-base)', fontWeight: 700, color: level.color }}>
              {score}%
            </span>
            <span style={{ fontSize: 'var(--text-2xs)', color: 'var(--text-secondary)' }}>
              ({level.label})
            </span>
          </div>
        </div>
      </div>

      <div style={{ textAlign: 'right', fontSize: 'var(--text-2xs)', color: 'var(--text-muted)' }}>
        <div>Evidence Base</div>
        <div style={{ color: 'var(--text-secondary)', fontWeight: 600 }}>
          {sourcesCount} sources · {observationsCount.toLocaleString()} observations
        </div>
      </div>
    </div>
  );
};

// ==========================================
// AI INTERPRETATION CARD (Section 21)
// ==========================================
interface AIInsightProps {
  interpretation: string;
  confidenceScore: number;
  sources: string[];
  evidenceBreakdown?: {
    source: string;
    finding: string;
    pointsCount: number;
    latency: string;
  }[];
  onExploreMore?: () => void;
}

export const AIInsightCard: React.FC<AIInsightProps> = ({
  interpretation,
  confidenceScore,
  sources,
  evidenceBreakdown,
  onExploreMore,
}) => {
  const [evidenceExpanded, setEvidenceExpanded] = useState(false);

  const effectiveBreakdown = evidenceBreakdown || (sources && sources.length > 0
    ? sources.map((src) => ({
        source: src,
        finding: `Telemetry and event stream monitoring active for ${src}.`,
        pointsCount: 1,
        latency: 'Real-time',
      }))
    : [
        { source: 'National Sensor Array', finding: 'Atmospheric telemetry stream monitoring active across regional sectors.', pointsCount: 1, latency: 'Live' },
      ]);

  return (
    <div
      style={{
        backgroundColor: 'var(--bg-surface)',
        border: '1px solid var(--border-hairline)',
        borderLeft: '3px solid var(--teal)',
        borderRadius: 'var(--r-2)',
        padding: '1.25rem',
        display: 'flex',
        flexDirection: 'column',
        gap: '0.85rem',
      }}
      className="sp-ai-insight"
    >
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.45rem' }}>
          <Sparkles size={14} color="var(--teal)" />
          <span
            style={{
              fontSize: 'var(--text-2xs)',
              fontFamily: 'var(--font-mono)',
              fontWeight: 700,
              letterSpacing: '0.12em',
              textTransform: 'uppercase',
              color: 'var(--teal)',
            }}
          >
            AI INTERPRETATION
          </span>
        </div>
        <AIConfidenceBadge score={confidenceScore} compact />
      </div>

      {/* Main synthesis text */}
      <div
        style={{
          fontSize: 'var(--text-sm)',
          lineHeight: 1.55,
          color: 'var(--text-primary)',
          fontFamily: 'var(--font-sans)',
        }}
      >
        "{interpretation}"
      </div>

      {/* Action / Evidence Toggle */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', paddingTop: '0.5rem', borderTop: '1px solid var(--border-hairline)' }}>
        <button
          onClick={() => setEvidenceExpanded(!evidenceExpanded)}
          style={{
            background: 'none',
            border: 'none',
            color: 'var(--teal)',
            fontSize: 'var(--text-xs)',
            fontFamily: 'var(--font-mono)',
            fontWeight: 600,
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: '0.35rem',
            padding: 0,
            letterSpacing: '0.04em',
          }}
        >
          <span>{evidenceExpanded ? 'HIDE EVIDENCE TELEMETRY' : 'WHY? VIEW EVIDENCE TELEMETRY'}</span>
          {evidenceExpanded ? <ChevronDown size={13} /> : <ChevronRight size={13} />}
        </button>

        {/* Source Pills */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
          <span style={{ fontSize: 'var(--text-2xs)', fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>
            SOURCES:
          </span>
          {sources.map((s, idx) => (
            <span
              key={idx}
              style={{
                fontSize: 'var(--text-2xs)',
                fontFamily: 'var(--font-mono)',
                color: 'var(--text-secondary)',
                backgroundColor: 'var(--bg-panel)',
                border: '1px solid var(--border-hairline)',
                padding: '0.1rem 0.35rem',
                borderRadius: 'var(--r-1)',
              }}
            >
              {s}
            </span>
          ))}
        </div>
      </div>

      {/* Expandable Evidence Drawer */}
      {evidenceExpanded && (
        <div
          style={{
            backgroundColor: 'var(--bg-panel)',
            border: '1px solid var(--border-hairline)',
            borderRadius: 'var(--r-1)',
            padding: '0.85rem 1rem',
            display: 'flex',
            flexDirection: 'column',
            gap: '0.65rem',
            animation: 'fade-in 0.15s ease-out',
          }}
        >
          <div style={{ fontSize: 'var(--text-2xs)', fontFamily: 'var(--font-mono)', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.08em' }}>
            Multi-Source Corroborating Telemetry
          </div>
          {effectiveBreakdown.map((ev, i) => (
            <div
              key={i}
              style={{
                display: 'flex',
                alignItems: 'flex-start',
                justifyContent: 'space-between',
                paddingBottom: i < effectiveBreakdown.length - 1 ? '0.5rem' : 0,
                borderBottom: i < effectiveBreakdown.length - 1 ? '1px solid var(--border-hairline)' : 'none',
              }}
            >
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                  <CheckCircle2 size={12} color="var(--status-verified)" />
                  <span style={{ fontSize: 'var(--text-xs)', fontWeight: 600, color: 'var(--text-primary)' }}>
                    {ev.source}
                  </span>
                </div>
                <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-secondary)', marginLeft: '1.25rem', marginTop: '0.15rem' }}>
                  {ev.finding}
                </div>
              </div>
              <div style={{ textAlign: 'right', fontFamily: 'var(--font-mono)', fontSize: 'var(--text-2xs)', color: 'var(--text-muted)', flexShrink: 0 }}>
                <div>{ev.pointsCount} points</div>
                <div>latency: {ev.latency}</div>
              </div>
            </div>
          ))}

          {onExploreMore && (
            <div style={{ marginTop: '0.5rem', textAlign: 'right' }}>
              <button
                onClick={onExploreMore}
                style={{
                  background: 'none',
                  border: 'none',
                  color: 'var(--ivory)',
                  fontSize: 'var(--text-xs)',
                  cursor: 'pointer',
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '0.35rem',
                  fontFamily: 'var(--font-sans)',
                  fontWeight: 600,
                }}
              >
                Inspect raw station observations <ArrowRight size={12} />
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
