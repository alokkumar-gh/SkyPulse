/**
 * Filters Store — Phase 7
 * Global dashboard filter state shared across all views.
 * Time range, categories, states, verification status, severity, confidence.
 */
import { create } from 'zustand';
import type { DashboardFilters, WeatherCategory, VerificationStatus, TimeRangePreset } from '../types';

function buildDateRange(preset: TimeRangePreset): { dateFrom: string; dateTo: string } {
  const now = new Date();
  const dateTo = now.toISOString();
  let dateFrom: string;

  switch (preset) {
    case '1h':
      dateFrom = new Date(now.getTime() - 60 * 60 * 1000).toISOString();
      break;
    case '6h':
      dateFrom = new Date(now.getTime() - 6 * 60 * 60 * 1000).toISOString();
      break;
    case '24h':
      dateFrom = new Date(now.getTime() - 24 * 60 * 60 * 1000).toISOString();
      break;
    case '7d':
      dateFrom = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000).toISOString();
      break;
    default:
      dateFrom = new Date(now.getTime() - 24 * 60 * 60 * 1000).toISOString();
  }

  return { dateFrom, dateTo };
}

const DEFAULT_PRESET: TimeRangePreset = '24h';
const { dateFrom, dateTo } = buildDateRange(DEFAULT_PRESET);

const DEFAULT_FILTERS: DashboardFilters = {
  timeRange: DEFAULT_PRESET,
  dateFrom,
  dateTo,
  categories: [],
  states: [],
  verificationStatuses: [],
  severityMin: 1,
  severityMax: 4,
  confidenceMin: 0,
  showDemoData: true,
  sourceTypes: [],
};

interface FiltersState {
  filters: DashboardFilters;
  timeRange: TimeRangePreset;

  setTimeRange: (preset: TimeRangePreset, from?: string, to?: string) => void;
  toggleCategory: (category: WeatherCategory) => void;
  setCategories: (categories: WeatherCategory[]) => void;
  toggleState: (state: string) => void;
  setStates: (states: string[]) => void;
  toggleVerificationStatus: (status: VerificationStatus) => void;
  setSeverityRange: (min: number, max: number) => void;
  setConfidenceMin: (min: number) => void;
  setShowDemoData: (show: boolean) => void;
  resetFilters: () => void;

  // Computed: active filter count for UI badge
  activeFilterCount: () => number;
}

export const useFiltersStore = create<FiltersState>((set, get) => ({
  filters: DEFAULT_FILTERS,
  timeRange: DEFAULT_PRESET,

  setTimeRange: (preset, from, to) => {
    if (preset === 'custom' && from && to) {
      set((state) => ({
        timeRange: preset,
        filters: { ...state.filters, timeRange: preset, dateFrom: from, dateTo: to },
      }));
    } else if (preset !== 'custom') {
      const { dateFrom, dateTo } = buildDateRange(preset);
      set((state) => ({
        timeRange: preset,
        filters: { ...state.filters, timeRange: preset, dateFrom, dateTo },
      }));
    }
  },

  toggleCategory: (category) => {
    set((state) => {
      const cats = state.filters.categories;
      const next = cats.includes(category)
        ? cats.filter((c) => c !== category)
        : [...cats, category];
      return { filters: { ...state.filters, categories: next } };
    });
  },

  setCategories: (categories) => {
    set((state) => ({ filters: { ...state.filters, categories } }));
  },

  toggleState: (stateName) => {
    set((state) => {
      const states = state.filters.states;
      const next = states.includes(stateName)
        ? states.filter((s) => s !== stateName)
        : [...states, stateName];
      return { filters: { ...state.filters, states: next } };
    });
  },

  setStates: (states) => {
    set((state) => ({ filters: { ...state.filters, states } }));
  },

  toggleVerificationStatus: (status) => {
    set((state) => {
      const statuses = state.filters.verificationStatuses;
      const next = statuses.includes(status)
        ? statuses.filter((s) => s !== status)
        : [...statuses, status];
      return { filters: { ...state.filters, verificationStatuses: next } };
    });
  },

  setSeverityRange: (min, max) => {
    set((state) => ({ filters: { ...state.filters, severityMin: min, severityMax: max } }));
  },

  setConfidenceMin: (min) => {
    set((state) => ({ filters: { ...state.filters, confidenceMin: min } }));
  },

  setShowDemoData: (show) => {
    set((state) => ({ filters: { ...state.filters, showDemoData: show } }));
  },

  resetFilters: () => {
    const { dateFrom, dateTo } = buildDateRange(DEFAULT_PRESET);
    set({ filters: { ...DEFAULT_FILTERS, dateFrom, dateTo } });
  },

  activeFilterCount: () => {
    const f = get().filters;
    let count = 0;
    if (f.categories.length) count += f.categories.length;
    if (f.states.length) count += f.states.length;
    if (f.verificationStatuses.length) count += f.verificationStatuses.length;
    if (f.severityMin > 1 || f.severityMax < 4) count++;
    if (f.confidenceMin > 0) count++;
    if (!f.showDemoData) count++;
    return count;
  },
}));
