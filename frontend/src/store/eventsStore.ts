/**
 * Events Store — Phase 7
 * Manages weather event state, selection, real-time updates from WebSocket.
 */
import { create } from 'zustand';
import { eventsAPI } from '../utils/api';
import type { WeatherEvent, DashboardFilters, PaginatedResponse } from '../types';

interface EventsState {
  events: WeatherEvent[];
  total: number;
  page: number;
  perPage: number;
  isLoading: boolean;
  loading: boolean;
  error: string | null;
  selectedEventId: string | null;
  selectedEvent: WeatherEvent | null;
  isLoadingDetail: boolean;

  // Actions
  fetchEvents: (filters?: Partial<DashboardFilters> & { status?: string; category?: string; state?: string; district?: string; severity?: number; is_active?: boolean }, page?: number, perPage?: number) => Promise<void>;
  fetchEventDetail: (eventId: string) => Promise<void>;
  selectEvent: (eventId: string | null) => void;
  setSelectedEvent: (event: WeatherEvent | null) => void;
  addOrUpdateEvent: (event: WeatherEvent) => void;
  updateEventVerification: (eventId: string, status: string, confidence: number) => void;
  markEventAnomalous: (eventId: string, zScore?: number) => void;
  clearError: () => void;
}

export const useEventsStore = create<EventsState>((set, get) => ({
  events: [],
  total: 0,
  page: 1,
  perPage: 25,
  isLoading: false,
  loading: false,
  error: null,
  selectedEventId: null,
  selectedEvent: null,
  isLoadingDetail: false,

  fetchEvents: async (filters = {}, page = 1, perPage = 25) => {
    set({ isLoading: true, loading: true, error: null });
    try {
      const data: PaginatedResponse<WeatherEvent> = await eventsAPI.list(filters, page, perPage);

      // Normalize: flatten location.lat/lon → latitude/longitude for SkyPulseMap
      const normalizedEvents: WeatherEvent[] = data.results.map((ev) => {
        const loc = ev.location;
        return {
          ...ev,
          latitude: ev.latitude ?? loc?.lat,
          longitude: ev.longitude ?? loc?.lon,
          state: ev.state ?? loc?.state,
          district: ev.district ?? loc?.district,
          title: ev.title ?? (ev.category ? `${ev.category} Event` : undefined),
        };
      });

      set({
        events: normalizedEvents,
        total: data.total,
        page: data.page,
        perPage: data.per_page,
        isLoading: false,
        loading: false,
      });
    } catch (err) {
      set({
        isLoading: false,
        loading: false,
        error: err instanceof Error ? err.message : 'Failed to load events',
      });
    }
  },


  fetchEventDetail: async (eventId) => {
    set({ isLoadingDetail: true });
    try {
      const event = await eventsAPI.get(eventId);
      const loc = event.location;
      const normalized: WeatherEvent = {
        ...event,
        latitude: event.latitude ?? loc?.lat,
        longitude: event.longitude ?? loc?.lon,
        state: event.state ?? loc?.state,
        district: event.district ?? loc?.district,
        title: event.title ?? (event.category ? `${event.category} Event` : undefined),
      };
      set({ selectedEvent: normalized, isLoadingDetail: false });
    } catch (err) {
      set({
        isLoadingDetail: false,
        error: err instanceof Error ? err.message : 'Failed to load event detail',
      });
    }
  },


  selectEvent: (eventId) => {
    set({ selectedEventId: eventId });
    if (eventId) get().fetchEventDetail(eventId);
    else set({ selectedEvent: null });
  },

  setSelectedEvent: (event) => {
    set({ selectedEvent: event, selectedEventId: event ? event.id : null });
  },

  addOrUpdateEvent: (event) => {
    set((state) => {
      const idx = state.events.findIndex((e) => e.id === event.id);
      if (idx >= 0) {
        const events = [...state.events];
        events[idx] = { ...events[idx], ...event };
        return { events };
      }
      // Prepend new event
      return { events: [event, ...state.events], total: state.total + 1 };
    });
  },

  updateEventVerification: (eventId, status, confidence) => {
    set((state) => ({
      events: state.events.map((e) =>
        e.id === eventId
          ? { ...e, verification_status: status as WeatherEvent['verification_status'], confidence_score: confidence }
          : e,
      ),
      selectedEvent:
        state.selectedEvent?.id === eventId
          ? {
              ...state.selectedEvent,
              verification_status: status as WeatherEvent['verification_status'],
              confidence_score: confidence,
            }
          : state.selectedEvent,
    }));
  },

  markEventAnomalous: (eventId, zScore) => {
    set((state) => ({
      events: state.events.map((e) =>
        e.id === eventId ? { ...e, is_anomalous: true, anomaly_z_score: zScore } : e,
      ),
    }));
  },

  clearError: () => set({ error: null }),
}));
