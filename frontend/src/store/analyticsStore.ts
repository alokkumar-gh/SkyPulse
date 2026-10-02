/**
 * Analytics Store — Phase 7
 * Manages national/state analytics data fetched from backend.
 */
import { create } from 'zustand';
import { analyticsAPI } from '../utils/api';
import type { NationalAnalytics, StateAnalytics, TimeseriesSeries } from '../types';

interface AnalyticsState {
  national: NationalAnalytics | null;
  timeseries: TimeseriesSeries | null;
  selectedState: string | null;
  stateAnalytics: StateAnalytics | null;
  isLoading: boolean;
  isLoadingState: boolean;
  error: string | null;

  fetchNational: (fromDate?: string, toDate?: string) => Promise<void>;
  fetchTimeseries: (metric?: 'events' | 'reports', interval?: 'hourly' | 'daily', days?: number) => Promise<void>;
  selectState: (state: string | null) => void;
  fetchStateAnalytics: (state: string, fromDate?: string, toDate?: string) => Promise<void>;
  clearError: () => void;
}

export const useAnalyticsStore = create<AnalyticsState>((set) => ({
  national: null,
  timeseries: null,
  selectedState: null,
  stateAnalytics: null,
  isLoading: false,
  isLoadingState: false,
  error: null,

  fetchNational: async (fromDate, toDate) => {
    set({ isLoading: true, error: null });
    try {
      const data = await analyticsAPI.national(fromDate, toDate);
      set({ national: data, isLoading: false });
    } catch (err) {
      set({
        isLoading: false,
        error: err instanceof Error ? err.message : 'Failed to load analytics',
      });
    }
  },

  fetchTimeseries: async (metric = 'events', interval = 'hourly', days = 7) => {
    try {
      const data = await analyticsAPI.timeseries(metric, interval, days);
      set({ timeseries: data });
    } catch {
      // Non-critical; don't update error state
    }
  },

  selectState: (state) => {
    set({ selectedState: state, stateAnalytics: null });
  },

  fetchStateAnalytics: async (state, fromDate, toDate) => {
    set({ isLoadingState: true });
    try {
      const data = await analyticsAPI.state(state, fromDate, toDate);
      set({ stateAnalytics: data, isLoadingState: false });
    } catch {
      set({ isLoadingState: false });
    }
  },

  clearError: () => set({ error: null }),
}));
