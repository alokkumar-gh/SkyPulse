/**
 * SkyPulse Weather Intelligence Timeline
 * Implements Section 17 & Part 6:
 * Answers:
 * - WHAT HAPPENED?
 * - WHEN?
 * - WHERE?
 * - HOW DID IT ESCALATE?
 * - WHAT EVIDENCE APPEARED?
 * - WHEN WAS IT VERIFIED?
 *
 * Preferred structure:
 *               EVENT TIMELINE
 * 06:00
 * │
 * ● Initial signal detected
 * │   Radar reflectivity spike
 * 09:30
 * │
 * ● Threshold exceeded
 * │   +45 mm/hr
 * 12:15
 * │
 * ● Civil warning issued
 * │   Flooding reported
 * 14:32
 * │
 * ● Ground truth verification
 * │   Corroborated by 3 AWS
 * │
 * NOW (Live Tracking)
 */

import React, { useState } from 'react';
import {
  TrendingUp, AlertTriangle, ShieldCheck,
  Radio, CheckCircle2,
  Clock
} from 'lucide-react';

export interface TimelineNode {
  id: string;
  time: string;
  date?: string;
  title: string;
  category: 'observation' | 'alert' | 'metric_shift' | 'verification' | 'forecast';
  value?: string;
  source?: string;
  location?: string;
  description?: string;
  severity?: 1 | 2 | 3 | 4;
  evidence_count?: number;
}

interface TimelineProps {
  nodes: TimelineNode[];
  title?: string;
  activeNodeId?: string;
  onSelectNode?: (node: TimelineNode) => void;
  orientation?: 'horizontal' | 'vertical';
  showNowIndicator?: boolean;
}

export const Timeline: React.FC<TimelineProps> = ({
  nodes,
  title = 'WEATHER INTELLIGENCE TIMELINE',
  activeNodeId,
  onSelectNode,
  orientation: _orientation = 'vertical',
  showNowIndicator = true,
}) => {
  const [hoveredNodeId, setHoveredNodeId] = useState<string | null>(null);

  const getNodeTheme = (node: TimelineNode) => {
    if (node.category === 'verification') {
      return {
        color: '#10b981',
        bg: 'rgba(16, 185, 129, 0.12)',
        border: 'rgba(16, 185, 129, 0.45)',
        icon: <ShieldCheck size={13} />,
        badge: 'GROUND TRUTH',
      };
    }
    if (node.severity === 4 || node.category === 'alert') {
      return {
        color: '#f43f5e',
        bg: 'rgba(244, 63, 94, 0.12)',
        border: 'rgba(244, 63, 94, 0.45)',
        icon: <AlertTriangle size={13} />,
        badge: 'CRITICAL WARNING',
      };
    }
    if (node.severity === 3 || node.category === 'metric_shift') {
      return {
        color: '#f59e0b',
        bg: 'rgba(245, 158, 11, 0.12)',
        border: 'rgba(245, 158, 11, 0.45)',
        icon: <TrendingUp size={13} />,
        badge: 'ESCALATION',
      };
    }
    return {
      color: '#00f0ff',
      bg: 'rgba(0, 240, 255, 0.12)',
      border: 'rgba(0, 240, 255, 0.45)',
      icon: <Radio size={13} />,
      badge: 'DETECTION',
    };
  };

  return (
    <div
      style={{
        backgroundColor: 'var(--bg-surface)',
        border: '1px solid var(--border-hairline)',
        borderRadius: 'var(--r-2)',
        padding: '1.25rem 1.5rem',
      }}
      className="sp-intelligence-timeline"
    >
      {/* Header */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          paddingBottom: '1rem',
          marginBottom: '1.25rem',
          borderBottom: '1px solid var(--border-hairline)',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <Clock size={13} color="var(--teal)" />
          <span
            style={{
              fontFamily: 'var(--font-mono)',
              fontSize: 'var(--text-xs)',
              fontWeight: 700,
              letterSpacing: '0.14em',
              color: 'var(--text-primary)',
              textTransform: 'uppercase',
            }}
          >
            {title}
          </span>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
          <span
            style={{
              fontFamily: 'var(--font-mono)',
              fontSize: 'var(--text-2xs)',
              color: 'var(--teal)',
              backgroundColor: 'rgba(0, 240, 255, 0.08)',
              padding: '0.15rem 0.5rem',
              borderRadius: 'var(--r-1)',
              border: '1px solid rgba(0, 240, 255, 0.25)',
            }}
          >
            {nodes.length} SEQUENCED SIGNALS
          </span>
        </div>
      </div>

      {/* Vertical Timeline Stem */}
      <div style={{ position: 'relative', paddingLeft: '0.5rem' }}>
        {nodes.map((node, index) => {
          const theme = getNodeTheme(node);
          const isSelected = activeNodeId === node.id;
          const isHovered = hoveredNodeId === node.id;
          const isLast = index === nodes.length - 1;

          return (
            <div
              key={node.id}
              onClick={() => onSelectNode?.(node)}
              onMouseEnter={() => setHoveredNodeId(node.id)}
              onMouseLeave={() => setHoveredNodeId(null)}
              style={{
                position: 'relative',
                display: 'flex',
                gap: '1.25rem',
                cursor: onSelectNode ? 'pointer' : 'default',
              }}
            >
              {/* Left Column: Time & Step Marker */}
              <div
                style={{
                  width: '90px',
                  flexShrink: 0,
                  textAlign: 'right',
                  paddingTop: '0.15rem',
                }}
              >
                <div
                  style={{
                    fontFamily: 'var(--font-mono)',
                    fontSize: 'var(--text-xs)',
                    fontWeight: 700,
                    color: isSelected || isHovered ? theme.color : 'var(--text-primary)',
                  }}
                >
                  {node.time}
                </div>
                <div
                  style={{
                    fontFamily: 'var(--font-mono)',
                    fontSize: '9px',
                    letterSpacing: '0.08em',
                    color: theme.color,
                    textTransform: 'uppercase',
                    marginTop: '0.15rem',
                  }}
                >
                  {node.date || theme.badge}
                </div>
              </div>

              {/* Center Stem Line & Node Dot */}
              <div
                style={{
                  position: 'relative',
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  width: '24px',
                  flexShrink: 0,
                }}
              >
                {/* Node Circle */}
                <div
                  style={{
                    width: '22px',
                    height: '22px',
                    borderRadius: '50%',
                    backgroundColor: theme.bg,
                    border: `2px solid ${theme.color}`,
                    color: theme.color,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    zIndex: 2,
                    boxShadow: isSelected || isHovered ? `0 0 14px ${theme.color}` : 'none',
                    transition: 'all 0.2s ease',
                  }}
                >
                  {theme.icon}
                </div>

                {/* Line downwards */}
                <div
                  style={{
                    flex: 1,
                    width: '2px',
                    backgroundColor: 'var(--border-subtle)',
                    minHeight: isLast && !showNowIndicator ? '0px' : '48px',
                    margin: '4px 0',
                    zIndex: 1,
                  }}
                />
              </div>

              {/* Right Column: Intelligence Payload */}
              <div
                style={{
                  flex: 1,
                  paddingBottom: isLast ? '1rem' : '1.75rem',
                  paddingTop: '0.05rem',
                }}
              >
                {/* Title */}
                <div
                  style={{
                    fontSize: 'var(--text-sm)',
                    fontWeight: 700,
                    color: 'var(--text-primary)',
                    fontFamily: 'var(--font-sans)',
                    letterSpacing: '-0.01em',
                  }}
                >
                  {node.title}
                </div>

                {/* Highlight Value / Metric Evidence Banner */}
                {node.value && (
                  <div
                    style={{
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: '0.4rem',
                      marginTop: '0.35rem',
                      padding: '0.25rem 0.65rem',
                      backgroundColor: theme.bg,
                      border: `1px solid ${theme.border}`,
                      borderRadius: 'var(--r-1)',
                      fontFamily: 'var(--font-mono)',
                      fontSize: 'var(--text-xs)',
                      fontWeight: 600,
                      color: theme.color,
                    }}
                  >
                    <span>{node.value}</span>
                  </div>
                )}

                {/* Description Narrative */}
                {node.description && (
                  <div
                    style={{
                      fontSize: 'var(--text-xs)',
                      color: 'var(--text-secondary)',
                      lineHeight: 1.55,
                      marginTop: '0.35rem',
                      maxWidth: '540px',
                    }}
                  >
                    {node.description}
                  </div>
                )}

                {/* Attribution Tags */}
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '0.65rem',
                    flexWrap: 'wrap',
                    marginTop: '0.45rem',
                    fontFamily: 'var(--font-mono)',
                    fontSize: '10px',
                    color: 'var(--text-muted)',
                  }}
                >
                  {node.source && (
                    <span style={{ display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
                      SOURCE: <strong style={{ color: 'var(--text-secondary)' }}>{node.source}</strong>
                    </span>
                  )}
                  {node.location && (
                    <span style={{ display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
                      LOCUS: <strong style={{ color: 'var(--text-secondary)' }}>{node.location}</strong>
                    </span>
                  )}
                  {node.evidence_count !== undefined && node.evidence_count > 0 && (
                    <span style={{ color: 'var(--teal)', display: 'flex', alignItems: 'center', gap: '0.2rem' }}>
                      <CheckCircle2 size={10} />
                      {node.evidence_count} CORROBORATING FEEDS
                    </span>
                  )}
                </div>
              </div>
            </div>
          );
        })}

        {/* NOW Terminal Indicator */}
        {showNowIndicator && (
          <div
            style={{
              position: 'relative',
              display: 'flex',
              gap: '1.25rem',
              alignItems: 'center',
            }}
          >
            {/* Left Column: NOW label */}
            <div
              style={{
                width: '90px',
                flexShrink: 0,
                textAlign: 'right',
                fontFamily: 'var(--font-mono)',
                fontSize: 'var(--text-xs)',
                fontWeight: 800,
                color: 'var(--teal)',
                letterSpacing: '0.05em',
              }}
            >
              NOW
            </div>

            {/* Pulsing Dot */}
            <div
              style={{
                position: 'relative',
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                width: '24px',
                flexShrink: 0,
              }}
            >
              <div
                style={{
                  width: '14px',
                  height: '14px',
                  borderRadius: '50%',
                  backgroundColor: 'var(--teal)',
                  boxShadow: '0 0 12px var(--teal)',
                  animation: 'pulse 2s infinite',
                }}
              />
            </div>

            {/* Right Column: Live monitoring status */}
            <div
              style={{
                fontFamily: 'var(--font-mono)',
                fontSize: 'var(--text-xs)',
                color: 'var(--text-muted)',
                letterSpacing: '0.04em',
              }}
            >
              CONTINUOUS SPATIO-TEMPORAL MONITORING ACTIVE
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
