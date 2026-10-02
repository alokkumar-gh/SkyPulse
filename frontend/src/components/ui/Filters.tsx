/**
 * TimeRangeSelector — Phase 7
 * Global time range filter. Shared across all dashboard views.
 */
import type { TimeRangePreset } from '../../types';

interface TimeRangeSelectorProps {
  value: TimeRangePreset;
  onChange: (preset: TimeRangePreset) => void;
  compact?: boolean;
}

const PRESETS: { value: TimeRangePreset; label: string }[] = [
  { value: '1h', label: 'Last 1h' },
  { value: '6h', label: 'Last 6h' },
  { value: '24h', label: 'Last 24h' },
  { value: '7d', label: 'Last 7d' },
];

export function TimeRangeSelector({ value, onChange, compact = false }: TimeRangeSelectorProps) {
  return (
    <div
      style={{
        display: 'inline-flex',
        border: '1px solid var(--bg-border)',
        borderRadius: 'var(--radius-md)',
        overflow: 'hidden',
        backgroundColor: 'var(--bg-surface)',
      }}
      role="group"
      aria-label="Time range filter"
    >
      {PRESETS.map((p) => (
        <button
          key={p.value}
          onClick={() => onChange(p.value)}
          style={{
            padding: compact ? '0.25rem 0.5rem' : '0.35rem 0.75rem',
            fontSize: compact ? 'var(--text-xs)' : 'var(--text-sm)',
            fontWeight: value === p.value ? 700 : 400,
            color: value === p.value ? 'var(--brand-blue)' : 'var(--text-secondary)',
            backgroundColor: value === p.value ? 'var(--brand-blue-dim)' : 'transparent',
            borderRight: '1px solid var(--bg-border)',
            cursor: 'pointer',
            transition: 'all var(--transition-fast)',
            whiteSpace: 'nowrap',
          }}
          aria-pressed={value === p.value}
        >
          {p.label}
        </button>
      ))}
    </div>
  );
}

/**
 * CategoryFilter — Phase 7
 * Multi-select chips for weather categories.
 */
import type { WeatherCategory } from '../../types';
import { getCategoryConfig } from './Badges';

const CORE_CATEGORIES: WeatherCategory[] = [
  'RAINFALL', 'THUNDERSTORM', 'FLOODING', 'HEATWAVE', 'FOG', 'DUST_STORM', 'STRONG_WINDS',
];

interface CategoryFilterProps {
  selected: WeatherCategory[];
  onToggle: (category: WeatherCategory) => void;
}

export function CategoryFilter({ selected, onToggle }: CategoryFilterProps) {
  return (
    <div
      style={{ display: 'flex', flexWrap: 'wrap', gap: '0.35rem' }}
      role="group"
      aria-label="Category filter"
    >
      {CORE_CATEGORIES.map((cat) => {
        const config = getCategoryConfig(cat);
        const isSelected = selected.includes(cat);
        return (
          <button
            key={cat}
            onClick={() => onToggle(cat)}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '0.25rem',
              padding: '0.2rem 0.6rem',
              borderRadius: 'var(--radius-full)',
              fontSize: 'var(--text-xs)',
              fontWeight: isSelected ? 700 : 400,
              border: `1px solid ${isSelected ? config.color : 'var(--bg-border)'}`,
              backgroundColor: isSelected ? `${config.color}18` : 'transparent',
              color: isSelected ? config.color : 'var(--text-muted)',
              cursor: 'pointer',
              transition: 'all var(--transition-fast)',
            }}
            aria-pressed={isSelected}
            aria-label={`${isSelected ? 'Remove' : 'Add'} ${config.label} filter`}
          >
            <span>{config.icon}</span>
            <span>{config.label}</span>
          </button>
        );
      })}
    </div>
  );
}
