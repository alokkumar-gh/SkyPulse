/**
 * PropagationTimeline Component — Phase 10
 * Interactive spatio-temporal propagation scrubber and animation controller.
 * Displays step-by-step cross-district progression, direction vectors, and time deltas.
 */

import React, { useEffect, useState } from 'react';
import { Play, Pause, SkipBack, SkipForward, ArrowRight, Compass, Clock } from 'lucide-react';
import type { PropagationTimelineResponse, PropagationStep } from '../../types';


interface PropagationTimelineProps {
  timeline: PropagationTimelineResponse | null;
  currentStepIndex?: number;
  onStepChange?: (index: number) => void;
  autoPlayIntervalMs?: number;
}

export const PropagationTimeline: React.FC<PropagationTimelineProps> = ({
  timeline,
  currentStepIndex: controlledIndex,
  onStepChange,
  autoPlayIntervalMs = 2500,
}) => {
  const [internalIndex, setInternalIndex] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);
  const [playbackSpeed, setPlaybackSpeed] = useState<number>(1);

  const steps = timeline?.propagation_steps || [];
  const currentIndex = controlledIndex !== undefined ? controlledIndex : internalIndex;

  const handleSetIndex = (newIdx: number) => {
    const clamped = Math.max(0, Math.min(newIdx, steps.length - 1));
    setInternalIndex(clamped);
    onStepChange?.(clamped);
  };

  // Playback loop
  useEffect(() => {
    if (!isPlaying || steps.length <= 1) return;

    const interval = setInterval(() => {
      setInternalIndex((prev) => {
        const next = (prev + 1) % steps.length;
        onStepChange?.(next);
        return next;
      });
    }, autoPlayIntervalMs / playbackSpeed);

    return () => clearInterval(interval);
  }, [isPlaying, steps.length, autoPlayIntervalMs, playbackSpeed, onStepChange]);

  const activeStep: PropagationStep | undefined = steps[currentIndex];

  if (!steps.length) {
    return (
      <div
        style={{
          padding: '1.25rem',
          backgroundColor: 'var(--bg-surface, #0f172a)',
          borderRadius: 'var(--radius-lg, 8px)',
          border: '1px solid var(--bg-border, #334155)',
          color: 'var(--text-muted, #64748b)',
          textAlign: 'center',
          fontSize: '13px',
        }}
      >
        No spatial propagation sequence recorded for this weather event.
      </div>
    );
  }

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        gap: '1rem',
        padding: '1.25rem',
        backgroundColor: 'var(--bg-surface, #0f172a)',
        borderRadius: 'var(--radius-lg, 8px)',
        border: '1px solid var(--bg-border, #334155)',
      }}
    >
      {/* Header and Controls */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '0.75rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <Compass size={18} color="var(--brand-blue, #38bdf8)" />
          <span style={{ fontSize: 'var(--text-sm, 14px)', fontWeight: 600, color: 'var(--text-primary, #f1f5f9)' }}>
            Propagation Trajectory Timeline
          </span>
          {timeline?.is_still_propagating && (
            <span
              style={{
                fontSize: '10px',
                fontWeight: 600,
                color: '#f97316',
                backgroundColor: 'rgba(249, 115, 22, 0.15)',
                padding: '2px 8px',
                borderRadius: '4px',
                border: '1px solid rgba(249, 115, 22, 0.3)',
              }}
            >
              ACTIVE PROPAGATION
            </span>
          )}
        </div>

        {/* Media Controls */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
          <button
            onClick={() => handleSetIndex(currentIndex - 1)}
            disabled={currentIndex === 0}
            style={{
              padding: '4px 8px',
              borderRadius: '4px',
              backgroundColor: 'var(--bg-elevated, #1e293b)',
              border: '1px solid var(--bg-border, #334155)',
              color: currentIndex === 0 ? 'var(--text-muted, #64748b)' : 'var(--text-primary, #f1f5f9)',
              cursor: currentIndex === 0 ? 'not-allowed' : 'pointer',
            }}
            title="Previous Step"
          >
            <SkipBack size={14} />
          </button>

          <button
            onClick={() => setIsPlaying(!isPlaying)}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '4px',
              padding: '4px 12px',
              borderRadius: '4px',
              backgroundColor: isPlaying ? 'var(--cat-rainfall, #3b82f6)' : 'var(--bg-elevated, #1e293b)',
              border: '1px solid var(--bg-border, #334155)',
              color: '#ffffff',
              fontSize: '12px',
              fontWeight: 500,
              cursor: 'pointer',
            }}
          >
            {isPlaying ? <Pause size={14} /> : <Play size={14} />}
            <span>{isPlaying ? 'Pause' : 'Play'}</span>
          </button>

          <button
            onClick={() => handleSetIndex(currentIndex + 1)}
            disabled={currentIndex === steps.length - 1}
            style={{
              padding: '4px 8px',
              borderRadius: '4px',
              backgroundColor: 'var(--bg-elevated, #1e293b)',
              border: '1px solid var(--bg-border, #334155)',
              color: currentIndex === steps.length - 1 ? 'var(--text-muted, #64748b)' : 'var(--text-primary, #f1f5f9)',
              cursor: currentIndex === steps.length - 1 ? 'not-allowed' : 'pointer',
            }}
            title="Next Step"
          >
            <SkipForward size={14} />
          </button>

          <button
            onClick={() => setPlaybackSpeed((s) => (s === 1 ? 2 : 1))}
            style={{
              padding: '4px 8px',
              borderRadius: '4px',
              backgroundColor: 'var(--bg-elevated, #1e293b)',
              border: '1px solid var(--bg-border, #334155)',
              color: 'var(--text-secondary, #94a3b8)',
              fontSize: '11px',
              fontWeight: 600,
              cursor: 'pointer',
              marginLeft: '4px',
            }}
          >
            {playbackSpeed}x
          </button>
        </div>
      </div>

      {/* Progress Track / Scrubber */}
      <div style={{ position: 'relative', margin: '0.75rem 0' }}>
        <input
          type="range"
          min={0}
          max={steps.length - 1}
          value={currentIndex}
          onChange={(e) => handleSetIndex(parseInt(e.target.value, 10))}
          style={{
            width: '100%',
            cursor: 'pointer',
            accentColor: 'var(--cat-rainfall, #3b82f6)',
          }}
        />

        {/* Milestone Steps Bar */}
        <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: '0.25rem' }}>
          {steps.map((st, idx) => {
            const isSelected = idx === currentIndex;
            const locName = st.location?.district || st.location?.state || `Step ${st.step}`;
            return (
              <button
                key={idx}
                onClick={() => handleSetIndex(idx)}
                style={{
                  background: 'none',
                  border: 'none',
                  cursor: 'pointer',
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  padding: '2px',
                }}
              >
                <div
                  style={{
                    width: isSelected ? 12 : 8,
                    height: isSelected ? 12 : 8,
                    borderRadius: '50%',
                    backgroundColor: isSelected ? '#38bdf8' : '#64748b',
                    boxShadow: isSelected ? '0 0 8px #38bdf8' : undefined,
                    transition: 'all 0.2s',
                  }}
                />
                <span
                  style={{
                    fontSize: '10px',
                    color: isSelected ? '#38bdf8' : '#94a3b8',
                    fontWeight: isSelected ? 600 : 400,
                    marginTop: '4px',
                    maxWidth: '80px',
                    whiteSpace: 'nowrap',
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                  }}
                >
                  {locName}
                </span>
              </button>
            );
          })}
        </div>
      </div>

      {/* Active Step Detail Card */}
      {activeStep && (
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))',
            gap: '0.75rem',
            padding: '0.75rem',
            backgroundColor: 'var(--bg-elevated, #1e293b)',
            borderRadius: '6px',
            border: '1px solid var(--bg-border, #334155)',
            fontSize: '12px',
          }}
        >
          <div>
            <div style={{ color: 'var(--text-muted, #64748b)', fontSize: '11px' }}>Current Location</div>
            <div style={{ fontWeight: 600, color: 'var(--text-primary, #f1f5f9)', marginTop: '2px' }}>
              {activeStep.location?.district ? `${activeStep.location.district}, ` : ''}
              {activeStep.location?.state || 'Target Region'}
            </div>
          </div>

          <div>
            <div style={{ color: 'var(--text-muted, #64748b)', fontSize: '11px' }}>Propagation Vector</div>
            <div style={{ fontWeight: 600, color: '#f97316', marginTop: '2px', display: 'flex', alignItems: 'center', gap: '4px' }}>
              <ArrowRight size={14} />
              {activeStep.propagation_direction || 'Origin Vector'}
            </div>
          </div>

          <div>
            <div style={{ color: 'var(--text-muted, #64748b)', fontSize: '11px' }}>Corroborating Evidence</div>
            <div style={{ fontWeight: 600, color: '#10b981', marginTop: '2px' }}>
              {activeStep.evidence_count} field report(s)
            </div>
          </div>

          <div>
            <div style={{ color: 'var(--text-muted, #64748b)', fontSize: '11px' }}>Time Elapsed</div>
            <div style={{ fontWeight: 600, color: 'var(--text-secondary, #94a3b8)', marginTop: '2px', display: 'flex', alignItems: 'center', gap: '4px' }}>
              <Clock size={12} />
              +{activeStep.time_delta_minutes || 0} mins
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
