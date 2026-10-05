import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import React from 'react';
import { MemoryRouter } from 'react-router-dom';
import { Dashboard } from '../pages/Dashboard';
import { useEventsStore } from '../store/eventsStore';
import { useFiltersStore } from '../store/filtersStore';
import * as apiModule from '../utils/api';

describe('Data Integrity & Synchronization Audit Suite', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useEventsStore.setState({
      events: [],
      mapEvents: [],
      observations: [],
      loading: false,
      selectedEvent: null,
      selectedEventId: null,
    });
  });

  it('reconciles Dashboard KPIs, map synchronicity, and honest telemetry without fake data', async () => {
    const mockCanonicalEvents: any[] = [
      {
        id: 'evt-mumbai-flood-01',
        title: 'Flooding reported in Mumbai, Maharashtra',
        category: 'FLOODING',
        severity: 3,
        confidence_score: 0.94,
        verification_status: 'VERIFIED',
        city: 'Mumbai',
        district: 'Mumbai City',
        state: 'Maharashtra',
        latitude: 19.0178,
        longitude: 72.8478,
        evidence_count: 5,
        sources_count: 3,
        publishers: ['IMD Doppler', 'NDMA SACHET'],
        is_active: true,
        first_reported_at: '2026-10-03T12:00:00Z',
        last_updated_at: '2026-10-04T12:00:00Z',
      },
      {
        id: 'evt-delhi-smog-02',
        title: 'Severe Smog reported in Delhi',
        category: 'SMOG',
        severity: 2,
        confidence_score: 0.88,
        verification_status: 'UNVERIFIED',
        city: 'New Delhi',
        district: 'New Delhi',
        state: 'Delhi',
        latitude: 28.6139,
        longitude: 77.2090,
        evidence_count: 3,
        sources_count: 2,
        publishers: ['CPCB Feed'],
        is_active: true,
        first_reported_at: '2026-10-03T10:00:00Z',
        last_updated_at: '2026-10-04T10:00:00Z',
      },
    ];

    const listSpy = vi.spyOn(apiModule.eventsAPI, 'list').mockResolvedValue({
      total: 2,
      page: 1,
      per_page: 25,
      pages: 1,
      results: mockCanonicalEvents,
    });

    const mapSpy = vi.spyOn(apiModule.eventsAPI, 'map').mockResolvedValue({
      type: 'FeatureCollection',
      features: [
        {
          type: 'Feature',
          geometry: { type: 'Point', coordinates: [72.8478, 19.0178] },
          properties: {
            id: 'evt-mumbai-flood-01',
            event_id: 'evt-mumbai-flood-01',
            title: 'Flooding reported in Mumbai, Maharashtra',
            category: 'FLOODING',
            severity: 3,
          },
        },
      ],
    } as any);

    const nationalSpy = vi.spyOn(apiModule.analyticsAPI, 'national').mockResolvedValue({
      total_events: 2,
      active_events: 2,
      total_reports: 3024,
      by_category: { FLOODING: 1, SMOG: 1 },
      by_verification_status: { VERIFIED: 1, UNVERIFIED: 1 },
      by_severity: { 2: 1, 3: 1 },
      top_affected_states: [{ state: 'Maharashtra', count: 1 }],
      period: { from_date: '2026-10-03T00:00:00Z', to_date: '2026-10-04T00:00:00Z' },
    });

    render(
      <MemoryRouter>
        <Dashboard />
      </MemoryRouter>
    );

    // 1. Check API calls
    await waitFor(() => {
      expect(listSpy).toHaveBeenCalled();
      expect(mapSpy).toHaveBeenCalled();
      expect(nationalSpy).toHaveBeenCalled();
    });

    // 2. Wait for loading to finish
    await waitFor(() => {
      expect(screen.getByText('ACTIVE WEATHER EVENTS')).toBeInTheDocument();
      expect(screen.queryByText('—')).not.toBeInTheDocument();
    });

    console.log('RENDERED METRIC CARDS:\n', document.querySelector('.sp-editorial-metric')?.parentElement?.innerHTML);

    // 4. Ingested observations reflects real 3,024 reports from backend
    await waitFor(() => {
      expect(screen.getByText('3,024')).toBeInTheDocument();
      expect(screen.getByText(/3,024 pts/i)).toBeInTheDocument();
    });

    // 5. NO fabricated '1,420 AWS' string
    expect(screen.queryByText(/1,420 AWS/i)).not.toBeInTheDocument();

    // 6. NO fabricated Odisha cyclonic activity / 27% deficit text
    expect(screen.queryByText(/cyclonic activity developing along the Odisha coast/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/27% precipitation deficit/i)).not.toBeInTheDocument();

    // 7. Grounded AI insight and Feed derived from real top hazard (Mumbai flood)
    await waitFor(() => {
      const floodElements = screen.getAllByText(/Flooding reported in Mumbai, Maharashtra/i);
      expect(floodElements.length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText(/IMD Doppler/i).length).toBeGreaterThanOrEqual(1);
    });
  });
});
