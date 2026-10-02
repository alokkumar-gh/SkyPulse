/**
 * SkyPulse Design System — Badge Components
 * Severity, Verification, Category, Demo badges
 * Consistent visual encoding across all views.
 */
import type { WeatherCategory, VerificationStatus } from '../../types';

// ── Severity Badge ─────────────────────────────────────────────────────────
const SEVERITY_COLORS: Record<number, string> = {
  1: 'var(--severity-1)',
  2: 'var(--severity-2)',
  3: 'var(--severity-3)',
  4: 'var(--severity-4)',
};

const SEVERITY_LABELS: Record<number, string> = {
  1: 'Minor',
  2: 'Moderate',
  3: 'Severe',
  4: 'Extreme',
};

interface SeverityBadgeProps {
  severity: number;
  showLabel?: boolean;
  size?: 'sm' | 'md';
}

export function SeverityBadge({ severity, showLabel = false, size = 'sm' }: SeverityBadgeProps) {
  const color = SEVERITY_COLORS[severity] ?? 'var(--text-muted)';
  const label = SEVERITY_LABELS[severity] ?? 'Unknown';
  const fontSize = size === 'sm' ? 'var(--text-xs)' : 'var(--text-sm)';

  return (
    <span
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: '0.25rem',
        fontSize,
        fontWeight: 600,
        color,
        fontFamily: 'var(--font-mono)',
      }}
      aria-label={`Severity ${severity}: ${label}`}
    >
      ●{severity}
      {showLabel && <span style={{ fontFamily: 'var(--font-sans)', fontWeight: 500 }}>{label}</span>}
    </span>
  );
}

// ── Verification Status Badge ───────────────────────────────────────────────
const STATUS_CONFIG: Record<VerificationStatus, { color: string; icon: string; label: string }> = {
  VERIFIED: { color: 'var(--status-verified)', icon: '✓', label: 'Verified' },
  LIKELY: { color: 'var(--status-likely)', icon: '~', label: 'Likely' },
  UNVERIFIED: { color: 'var(--status-unverified)', icon: '?', label: 'Unverified' },
  CONTRADICTED: { color: 'var(--status-contradicted)', icon: '✗', label: 'Contradicted' },
  REQUIRES_REVIEW: { color: 'var(--status-review)', icon: '⚠', label: 'Review' },
  UNDER_REVIEW: { color: 'var(--status-review)', icon: '⚠', label: 'Review' },
};

interface VerificationBadgeProps {
  status: VerificationStatus;
  showIcon?: boolean;
  pill?: boolean;
}

export function VerificationBadge({ status, showIcon = true, pill = false }: VerificationBadgeProps) {
  const config = STATUS_CONFIG[status] ?? STATUS_CONFIG.UNVERIFIED;

  if (pill) {
    return (
      <span
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: '0.2rem',
          padding: '0.15rem 0.5rem',
          borderRadius: 'var(--radius-full)',
          fontSize: 'var(--text-xs)',
          fontWeight: 600,
          color: config.color,
          backgroundColor: `${config.color}18`,
          border: `1px solid ${config.color}40`,
        }}
        aria-label={config.label}
      >
        {showIcon && config.icon} {config.label.toUpperCase()}
      </span>
    );
  }

  return (
    <span
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: '0.25rem',
        fontSize: 'var(--text-xs)',
        fontWeight: 600,
        color: config.color,
      }}
      aria-label={config.label}
    >
      {showIcon && config.icon} {config.label.toUpperCase()}
    </span>
  );
}

// ── Category Badge ──────────────────────────────────────────────────────────
const CATEGORY_CONFIG: Record<string, { color: string; icon: string; label: string }> = {
  RAINFALL: { color: 'var(--cat-rainfall)', icon: '🌧', label: 'Rainfall' },
  THUNDERSTORM: { color: 'var(--cat-thunderstorm)', icon: '⛈', label: 'Thunderstorm' },
  FLOODING: { color: 'var(--cat-flooding)', icon: '🌊', label: 'Flooding' },
  HEATWAVE: { color: 'var(--cat-heatwave)', icon: '🌡', label: 'Heatwave' },
  FOG: { color: 'var(--cat-fog)', icon: '🌫', label: 'Fog' },
  DUST_STORM: { color: 'var(--cat-dust-storm)', icon: '🌪', label: 'Dust Storm' },
  STRONG_WINDS: { color: 'var(--cat-strong-winds)', icon: '💨', label: 'Strong Winds' },
  SNOWFALL: { color: '#e0f2fe', icon: '❄', label: 'Snowfall' },
  HAILSTORM: { color: '#c084fc', icon: '🧊', label: 'Hailstorm' },
  CYCLONE: { color: '#f43f5e', icon: '🌀', label: 'Cyclone' },
  SMOG: { color: '#78716c', icon: '😶‍🌫️', label: 'Smog' },
  UNKNOWN: { color: 'var(--text-muted)', icon: '❓', label: 'Unknown' },
};

export function getCategoryConfig(category: WeatherCategory | string) {
  return CATEGORY_CONFIG[category] ?? CATEGORY_CONFIG.UNKNOWN;
}

interface CategoryBadgeProps {
  category: WeatherCategory | string;
  showIcon?: boolean;
  showLabel?: boolean;
}

export function CategoryBadge({ category, showIcon = true, showLabel = true }: CategoryBadgeProps) {
  const config = getCategoryConfig(category);
  return (
    <span
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: '0.25rem',
        fontSize: 'var(--text-xs)',
        fontWeight: 600,
        color: config.color,
      }}
    >
      {showIcon && config.icon}
      {showLabel && config.label.toUpperCase()}
    </span>
  );
}

// ── Demo Badge ──────────────────────────────────────────────────────────────
export function DemoBadge() {
  return (
    <span
      style={{
        padding: '0.1rem 0.4rem',
        borderRadius: 'var(--radius-full)',
        fontSize: '0.625rem',
        fontWeight: 700,
        letterSpacing: '0.05em',
        backgroundColor: 'rgba(124, 58, 237, 0.12)',
        color: 'var(--demo-badge)',
        border: '1px solid rgba(124, 58, 237, 0.25)',
      }}
    >
      DEMO
    </span>
  );
}

// ── Confidence Bar ──────────────────────────────────────────────────────────
interface ConfidenceBarProps {
  value: number; // 0.0 - 1.0
  size?: 'sm' | 'md';
  showPct?: boolean;
  showValue?: boolean;
}

export function ConfidenceBar({ value, size = 'sm', showPct, showValue }: ConfidenceBarProps) {
  const isShown = showValue !== undefined ? showValue : (showPct ?? true);
  const pct = Math.round((value ?? 0) * 100);
  const barColor =
    pct >= 80 ? 'var(--status-verified)' :
    pct >= 60 ? 'var(--status-likely)' :
    pct >= 40 ? 'var(--severity-2)' :
    'var(--severity-4)';
  const height = size === 'sm' ? 4 : 6;

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
      <div
        style={{
          flex: 1,
          height,
          backgroundColor: 'var(--bg-border)',
          borderRadius: 'var(--radius-full)',
          overflow: 'hidden',
        }}
        role="meter"
        aria-valuenow={pct}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label={`Confidence ${pct}%`}
      >
        <div
          style={{
            height: '100%',
            width: `${pct}%`,
            backgroundColor: barColor,
            borderRadius: 'var(--radius-full)',
            transition: 'width 0.5s ease',
          }}
        />
      </div>
      {isShown && (
        <span
          style={{
            fontSize: 'var(--text-xs)',
            fontWeight: 600,
            color: barColor,
            fontFamily: 'var(--font-mono)',
            minWidth: '3rem',
            textAlign: 'right',
          }}
        >
          {pct}%
        </span>
      )}
    </div>
  );
}

// ── Pulse Dot (live indicator) ──────────────────────────────────────────────
interface PulseDotProps {
  color?: string;
  size?: number;
}

export function PulseDot({ color = 'var(--severity-1)', size = 8 }: PulseDotProps) {
  return (
    <span
      style={{
        display: 'inline-block',
        width: size,
        height: size,
        borderRadius: '50%',
        backgroundColor: color,
        boxShadow: `0 0 0 0 ${color}`,
        animation: 'pulse-ring 2s infinite',
        flexShrink: 0,
      }}
      role="status"
      aria-label="Live"
    />
  );
}
