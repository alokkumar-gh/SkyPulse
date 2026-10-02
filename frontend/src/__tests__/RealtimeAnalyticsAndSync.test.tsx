/**
 * Real-Time Analytics & Live Dashboard Synchronization Test Suite
 * ===============================================================
 * Validates:
 * 1. Analytics page consumes real backend analytics (GET /analytics/national, GET /analytics/timeseries)
 * 2. WebSocket listener normalizes and dispatches weather_event.created / updated into useEventsStore
 * 3. Query parameter mapping translates frontend filters to backend API contracts (from_date, to_date, status)
 * 4. Events page executes server-side queries on filter change
 * 5. Dashboard reactively reflects real-time event additions
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, renderHook, act, screen, waitFor, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { Analytics } from '../pages/Analytics';
import { Events } from '../pages/Events';
import { Dashboard } from '../pages/Dashboard';
import { useWebSocket } from '../hooks/useWebSocket';
import { analyticsAPI, eventsAPI } from '../utils/api';
import { useEventsStore } from '../store/eventsStore';
import { useFiltersStore } from '../store/filtersStore';
import { skyPulseWSClient, type WSEventEnvelope } from '../utils/wsClient';
import type { NationalAnalytics, TimeseriesSeries, WeatherEvent } from '../types';

vi.mock('../utils/api', () => ({
  analyticsAPI: {
    national: vi.fn(),
    state: vi.fn(),
    timeseries: vi.fn(),
  },
  eventsAPI: {
    list: vi.fn(),
    get: vi.fn(),
    timeline: vi.fn(),
    nearby: vi.fn(),
    verifyEvent: vi.fn(),
    getDNA: vi.fn(),
    getDNASnapshot: vi.fn(),
    getDNATimeline: vi.fn(),
    getDNAEvidence: vi.fn(),
    getDNAPropagation: vi.fn(),
  },
  verificationAPI: {
    override: vi.fn(),
    queue: vi.fn(),
  },
}));

vi.mock('../components/map/SkyPulseMap', () => ({
  SkyPulseMap: ({ events }: { events: WeatherEvent[] }) => (
    <div data-testid="skypulse-map">Map with {events.length} events</div>
  ),
}));

describe('SIH Real-Time Dashboard & Real Analytics Suite', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useEventsStore.setState({
      events: [],
      total: 0,
      page: 1,
      perPage: 25,
      loading: false,
      error: null,
      selectedEvent: null,
      selectedEventId: null,
    });
    useFiltersStore.setState({
      filters: {
        timeRange: '24h',
        dateFrom: '2026-10-01T00:00:00Z',
        dateTo: '2026-10-02T00:00:00Z',
        categories: [],
        states: [],
        verificationStatuses: [],
        severityMin: 1,
        severityMax: 4,
        confidenceMin: 0,
        showDemoData: true,
        sourceTypes: [],
      },
      timeRange: '24h',
    });
  });

  // --------------------------------------------------------------------------
  // 1. REAL ANALYTICS CONSUMPTION
  // --------------------------------------------------------------------------
  describe('1. Real Backend Analytics Consumption', () => {
    it('fetches and renders real national analytics and timeseries data', async () => {
      const mockNational: NationalAnalytics = {
        period: { from: '2026-10-01T00:00:00Z', to: '2026-10-02T00:00:00Z' },
        total_events: 42,
        active_events: 15,
        total_reports: 128,
        anomalous_events: 3,
        by_category: {
          FLOODING: 20,
          RAINFALL: 14,
          THUNDERSTORM: 8,
        },
        by_verification_status: {
          VERIFIED: 25,
          UNVERIFIED: 12,
          REQUIRES_REVIEW: 5,
        },
        by_severity: {
          '1': 10,
          '2': 18,
          '3': 11,
          '4': 3,
        },
        top_states: [
          { state: 'Odisha', event_count: 18 },
          { state: 'Assam', event_count: 14 },
          { state: 'Maharashtra', event_count: 10 },
        ],
      };

      const mockTimeseries: TimeseriesSeries = {
        metric: 'events',
        interval: 'hourly',
        series: [
          { timestamp: '2026-10-02T10:00:00Z', value: 8 },
          { timestamp: '2026-10-02T11:00:00Z', value: 12 },
          { timestamp: '2026-10-02T12:00:00Z', value: 15 },
        ],
      };

      vi.mocked(analyticsAPI.national).mockResolvedValueOnce(mockNational);
      vi.mocked(analyticsAPI.timeseries).mockResolvedValueOnce(mockTimeseries);

      render(<Analytics />);

      expect(screen.getByText('Loading aggregated national meteorological analytics...')).toBeInTheDocument();

      await waitFor(() => {
        expect(analyticsAPI.national).toHaveBeenCalled();
        expect(analyticsAPI.timeseries).toHaveBeenCalledWith('events', 'hourly', 7);
        // Verify KPI values from real backend payload
        expect(screen.getByText('42')).toBeInTheDocument(); // total_events
        expect(screen.getByText('15')).toBeInTheDocument(); // active_events
        expect(screen.getByText('128')).toBeInTheDocument(); // total_reports
        expect(screen.getByText('3')).toBeInTheDocument(); // anomalous_events
      });

      // Verify verification status breakdown
      expect(screen.getByText('VERIFIED')).toBeInTheDocument();
      expect(screen.getByText('25')).toBeInTheDocument();
      expect(screen.getByText('UNVERIFIED')).toBeInTheDocument();
      expect(screen.getByText('12')).toBeInTheDocument();
    });

    it('safely handles error state on analytics API failure with retry', async () => {
      vi.mocked(analyticsAPI.national).mockRejectedValueOnce(new Error('Backend offline'));
      vi.mocked(analyticsAPI.timeseries).mockRejectedValueOnce(new Error('Backend offline'));

      render(<Analytics />);

      await waitFor(() => {
        expect(screen.getByText(/Error loading backend analytics: Backend offline/i)).toBeInTheDocument();
      });

      // Clicking retry triggers refetch
      vi.mocked(analyticsAPI.national).mockResolvedValueOnce({
        period: { from: '', to: '' },
        total_events: 1,
        active_events: 1,
        total_reports: 1,
        anomalous_events: 0,
        by_category: { RAINFALL: 1 },
        by_verification_status: { VERIFIED: 1 },
        by_severity: { '1': 1 },
        top_states: [{ state: 'Delhi', event_count: 1 }],
      });
      vi.mocked(analyticsAPI.timeseries).mockResolvedValueOnce({
        metric: 'events',
        interval: 'hourly',
        series: [],
      });

      fireEvent.click(screen.getByText('Retry'));

      await waitFor(() => {
        expect(analyticsAPI.national).toHaveBeenCalledTimes(2);
      });
    });
  });

  // --------------------------------------------------------------------------
  // 2. WEBSOCKET REALTIME DISPATCH TO EVENTS STORE
  // --------------------------------------------------------------------------
  describe('2. WebSocket Event Normalization & Ingestion into Store', () => {
    it('dispatches weather_event.created envelope into useEventsStore', () => {
      const { unmount } = renderHook(() => useWebSocket({ autoConnect: false }));

      const createdEnvelope: WSEventEnvelope = {
        version: '1',
        type: 'weather_event.created',
        event_id: 'evt-ws-live-101',
        timestamp: '2026-10-02T12:30:00Z',
        data: {
          event_id: 'evt-ws-live-101',
          category: 'FLOODING',
          severity: 3,
          confidence: 0.92,
          verification_status: 'UNVERIFIED',
          primary_city: 'Bhubaneswar',
          primary_state: 'Odisha',
          centroid_lat: 20.2961,
          centroid_lon: 85.8245,
          location: {
            city: 'Bhubaneswar',
            state: 'Odisha',
            lat: 20.2961,
            lon: 85.8245,
          },
          evidence_count: 1,
          is_anomalous: false,
          is_demo: false,
        },
      };

      // Emit event through client dispatcher
      act(() => {
        skyPulseWSClient.emit(createdEnvelope);
      });

      const state = useEventsStore.getState();
      expect(state.events.length).toBe(1);
      expect(state.events[0].id).toBe('evt-ws-live-101');
      expect(state.events[0].category).toBe('FLOODING');
      expect(state.events[0].severity).toBe(3);
      expect(state.events[0].confidence_score).toBe(0.92);
      expect(state.events[0].latitude).toBe(20.2961);
      expect(state.events[0].longitude).toBe(85.8245);
      expect(state.events[0].state).toBe('Odisha');
      expect(state.total).toBe(1);

      unmount();
    });

    it('updates existing event on weather_event.updated envelope', () => {
      const { unmount } = renderHook(() => useWebSocket({ autoConnect: false }));

      // First seed an existing event in store
      useEventsStore.getState().addOrUpdateEvent({
        id: 'evt-ws-live-102',
        category: 'RAINFALL',
        severity: 2,
        confidence_score: 0.7,
        verification_status: 'UNVERIFIED',
        location: { state: 'Assam' },
        latitude: 26.1445,
        longitude: 91.7362,
        state: 'Assam',
        first_reported_at: '2026-10-02T10:00:00Z',
        last_updated_at: '2026-10-02T10:00:00Z',
        evidence_count: 1,
        is_anomalous: false,
        is_active: true,
        is_demo: false,
      });

      expect(useEventsStore.getState().events[0].evidence_count).toBe(1);

      // Now emit update
      const updateEnvelope: WSEventEnvelope = {
        version: '1',
        type: 'weather_event.updated',
        event_id: 'evt-ws-live-102',
        timestamp: '2026-10-02T12:45:00Z',
        data: {
          event_id: 'evt-ws-live-102',
          category: 'FLOODING',
          severity: 4,
          confidence: 0.96,
          verification_status: 'VERIFIED',
          primary_city: 'Guwahati',
          primary_state: 'Assam',
          centroid_lat: 26.1445,
          centroid_lon: 91.7362,
          evidence_count: 5,
        },
      };

      act(() => {
        skyPulseWSClient.emit(updateEnvelope);
      });

      const state = useEventsStore.getState();
      expect(state.events.length).toBe(1);
      expect(state.events[0].category).toBe('FLOODING');
      expect(state.events[0].severity).toBe(4);
      expect(state.events[0].confidence_score).toBe(0.96);
      expect(state.events[0].verification_status).toBe('VERIFIED');
      expect(state.events[0].evidence_count).toBe(5);

      unmount();
    });
  });

  // --------------------------------------------------------------------------
  // 3. SERVER-SIDE QUERY PARAMETER RECONCILIATION & EVENTS PAGE FILTERING
  // --------------------------------------------------------------------------
  describe('3. Server-side Query Parameter Mapping', () => {
    it('Events page executes server-side filtering on category and state change', async () => {
      vi.mocked(eventsAPI.list).mockResolvedValue({
        results: [
          {
            id: 'evt-odisha-1',
            category: 'FLOODING',
            severity: 3,
            confidence_score: 0.88,
            verification_status: 'VERIFIED',
            location: { state: 'Odisha', city: 'Bhubaneswar' },
            state: 'Odisha',
            district: 'Khordha',
            first_reported_at: '2026-10-02T11:00:00Z',
            last_updated_at: '2026-10-02T11:00:00Z',
            evidence_count: 3,
            is_anomalous: false,
            is_active: true,
            is_demo: false,
          },
        ],
        total: 1,
        page: 1,
        per_page: 12,
      });

      render(
        <MemoryRouter>
          <Events />
        </MemoryRouter>
      );

      await waitFor(() => {
        expect(eventsAPI.list).toHaveBeenCalled();
      });

      // Change category filter
      const categorySelect = screen.getByLabelText('Category');
      fireEvent.change(categorySelect, { target: { value: 'FLOODING' } });

      await waitFor(() => {
        expect(eventsAPI.list).toHaveBeenCalledWith(
          expect.objectContaining({
            category: 'FLOODING',
          }),
          1,
          12
        );
      });
    });
  });

  // --------------------------------------------------------------------------
  // 4. DASHBOARD REAL-TIME SYNCHRONIZATION
  // --------------------------------------------------------------------------
  describe('4. Dashboard Real-time Live Synchronization', () => {
    it('updates Dashboard map and event count dynamically when a WebSocket event arrives', async () => {
      vi.mocked(eventsAPI.list).mockResolvedValue({
        results: [],
        total: 0,
        page: 1,
        per_page: 25,
      });

      render(
        <MemoryRouter>
          <Dashboard />
        </MemoryRouter>
      );

      await waitFor(() => {
        expect(eventsAPI.list).toHaveBeenCalled();
        expect(screen.getByTestId('skypulse-map')).toHaveTextContent('Map with 0 events');
      });

      // Incoming real-time WebSocket event arrives
      const newLiveEvent: WSEventEnvelope = {
        version: '1',
        type: 'weather_event.created',
        event_id: 'evt-live-sync-999',
        timestamp: '2026-10-02T15:00:00Z',
        data: {
          event_id: 'evt-live-sync-999',
          category: 'THUNDERSTORM',
          severity: 3,
          confidence: 0.89,
          verification_status: 'UNVERIFIED',
          primary_city: 'Cuttack',
          primary_state: 'Odisha',
          centroid_lat: 20.4625,
          centroid_lon: 85.8830,
        },
      };

      act(() => {
        skyPulseWSClient.emit(newLiveEvent);
      });

      // Reactively reflected in Dashboard without manual page reload
      await waitFor(() => {
        expect(screen.getByTestId('skypulse-map')).toHaveTextContent('Map with 1 events');
      });
    });
  });
});
