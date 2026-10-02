import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { EmergingEventsPanel, EmergenceBadge } from '../components/events/EmergingEventsPanel';
import { emergingEventsAPI } from '../utils/api';
import type { EmergingEvent } from '../types';

vi.mock('../utils/api', () => ({
  emergingEventsAPI: {
    list: vi.fn(),
    get: vi.fn(),
    signals: vi.fn(),
    timeline: vi.fn(),
    evidence: vi.fn(),
  },
}));

const mockEmergingEvent: EmergingEvent = {
  id: 'emg-78421903',
  dominant_category: 'THUNDERSTORM',
  severity: 3,
  state: 'EMERGING',
  emergence_score: 0.82,
  confidence_score: 0.74,
  evidence_count: 7,
  source_count: 4,
  unique_source_types: ['IMD', 'CITIZEN', 'WEATHER_STATION', 'RADAR'],
  spatial_centroid_lat: 22.5726,
  spatial_centroid_lon: 88.3639,
  spatial_radius_km: 24.5,
  spatial_footprint_km2: 1885.7,
  temporal_window_minutes: 120,
  acceleration_indicator: 1.8,
  location_summary: 'Kolkata, West Bengal',
  state_name: 'West Bengal',
  district: 'Kolkata',
  first_signal_at: '2026-04-10T14:00:00Z',
  latest_signal_at: '2026-04-10T14:45:00Z',
  factors: {
    spatial_convergence_score: 0.85,
    temporal_acceleration_score: 0.90,
    source_diversity_score: 0.80,
    category_consistency_score: 0.88,
    meteorological_support_score: 0.75,
    anomaly_strength_score: 0.70,
    dweg_connectivity_score: 0.65,
    evidence_freshness_score: 0.95,
    contradiction_penalty: 0.0,
    final_emergence_score: 0.82,
    explanation_bullets: [
      '7 compatible signals observed in the last 120 minutes.',
      '4 independent source streams corroborating (IMD, CITIZEN, WEATHER_STATION, RADAR).',
      'Spatial footprint bounded within 24.5 km radius around (22.573, 88.364).',
      'Temporal velocity accelerating (+80% incoming rate increase).',
      '1 official meteorological reading confirms signal baseline.',
    ],
  },
  signals: [],
  timeline: [],
  canonical_event_id: 'ev-canon-101',
  event_dna_id: 'ev-canon-101',
  dweg_node_id: 'node-emg-78421903',
  detected_at: '2026-04-10T14:00:00Z',
  updated_at: '2026-04-10T14:45:00Z',
};

describe('Emerging Events Intelligence Suite', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders emergence state badges correctly with distinct states', () => {
    const { rerender } = render(<EmergenceBadge state="SIGNAL" />);
    expect(screen.getByText(/SIGNAL/i)).toBeInTheDocument();

    rerender(<EmergenceBadge state="DEVELOPING" />);
    expect(screen.getByText(/DEVELOPING/i)).toBeInTheDocument();

    rerender(<EmergenceBadge state="EMERGING" />);
    expect(screen.getByText(/EMERGING/i)).toBeInTheDocument();

    rerender(<EmergenceBadge state="CONFIRMED" />);
    expect(screen.getByText(/CONFIRMED/i)).toBeInTheDocument();
  });

  it('renders active emerging events with scores, location, and source diversity tags', async () => {
    (emergingEventsAPI.list as any).mockResolvedValue({
      total: 1,
      active_count: 1,
      items: [mockEmergingEvent],
    });

    render(<EmergingEventsPanel />);

    await waitFor(() => {
      expect(screen.getByText('Emerging Event Detector')).toBeInTheDocument();
      expect(screen.getByText('Kolkata, West Bengal')).toBeInTheDocument();
      expect(screen.getByText('82%')).toBeInTheDocument();
      expect(screen.getByText('74%')).toBeInTheDocument();
      expect(screen.getByText(/7 signal\(s\)/i)).toBeInTheDocument();
      expect(screen.getByText('IMD')).toBeInTheDocument();
      expect(screen.getByText('CITIZEN')).toBeInTheDocument();
      expect(screen.getByText('WEATHER_STATION')).toBeInTheDocument();
      expect(screen.getByText('RADAR')).toBeInTheDocument();
    });
  });

  it('expands and displays evidence-driven "WHY EMERGING" explanation bullets', async () => {
    (emergingEventsAPI.list as any).mockResolvedValue({
      total: 1,
      active_count: 1,
      items: [mockEmergingEvent],
    });

    render(<EmergingEventsPanel />);

    await waitFor(() => {
      expect(screen.getByText('Why Emerging')).toBeInTheDocument();
    });

    const whyBtn = screen.getByText('Why Emerging');
    fireEvent.click(whyBtn);

    expect(
      screen.getByText(/Evidence-Driven Emergence Rationale/i)
    ).toBeInTheDocument();
    expect(
      screen.getByText(/7 compatible signals observed in the last 120 minutes/i)
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Temporal velocity accelerating/i)
    ).toBeInTheDocument();
    expect(
      screen.getByText(/1 official meteorological reading confirms signal baseline/i)
    ).toBeInTheDocument();
  });

  it('handles empty state when no signal convergence is detected', async () => {
    (emergingEventsAPI.list as any).mockResolvedValue({
      total: 0,
      active_count: 0,
      items: [],
    });

    render(<EmergingEventsPanel />);

    await waitFor(() => {
      expect(
        screen.getByText(/No Emerging Signal Convergence Detected/i)
      ).toBeInTheDocument();
    });
  });

  it('handles API error state gracefully', async () => {
    (emergingEventsAPI.list as any).mockRejectedValue(
      new Error('Failed to connect to emerging events gateway')
    );

    render(<EmergingEventsPanel />);

    await waitFor(() => {
      expect(screen.getByText('Detection Offline')).toBeInTheDocument();
      expect(
        screen.getByText('Failed to connect to emerging events gateway')
      ).toBeInTheDocument();
    });
  });
});
