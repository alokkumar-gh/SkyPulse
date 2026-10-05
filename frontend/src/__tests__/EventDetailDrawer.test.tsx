import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { EventDetailDrawer } from '../components/events/EventDetailDrawer';
import { useAuthStore } from '../store/authStore';
import { eventsAPI } from '../utils/api';
import type { WeatherEvent } from '../types';

vi.mock('../utils/api', () => ({
  eventsAPI: {
    verifyEvent: vi.fn(),
    getDNA: vi.fn().mockResolvedValue({
      event_id: 'ev-detail-101',
      event_type: 'THUNDERSTORM',
      status: 'UNDER_REVIEW',
      lifecycle_phase: 'ACTIVE',
      severity: 3,
      first_observed_at: '2026-04-10T14:00:00Z',
      last_observed_at: '2026-04-10T14:30:00Z',
      spatial_radius_km: 12.5,
      spatial_footprint_km: 490.8,
      confidence: {
        source_reliability_score: 0.28,
        cross_source_support_score: 0.22,
        spatial_consistency_score: 0.14,
        temporal_consistency_score: 0.14,
        meteorological_score: 0.08,
        media_score: 0.05,
        contradiction_penalty: 0.0,
        final_confidence: 0.88,
        explanation: 'Strong multi-source radar and citizen alignment.',
      },
      evidence_coverage: {
        overall_coverage_score: 0.82,
        temporal_coverage: 0.85,
        spatial_coverage: 0.80,
        source_diversity_coverage: 0.75,
        meteorological_coverage: 0.90,
        official_validation_coverage: 0.80,
        corroboration_coverage: 0.85,
        active_dimensions_count: 6,
        explanation: 'Comprehensive multi-source coverage.',
      },
      evidence: {
        total_evidence_count: 8,
        supporting_evidence_count: 8,
        contradicting_evidence_count: 0,
        unverified_evidence_count: 0,
        duplicate_count: 1,
        unique_sources_count: 3,
        sources: {},
        cross_source_corroborated: true,
      },
      propagation: {
        has_propagation: true,
        stage_count: 2,
        stages: [],
        overall_direction: 'NE',
        average_speed_kmh: 18.5,
        total_distance_km: 24.2,
      },
      timeline: [],
      related_events: [],
      snapshot: {
        event_id: 'ev-detail-101',
        event_type: 'THUNDERSTORM',
        status: 'UNDER_REVIEW',
        severity: 3,
        source_count: 3,
        evidence_count: 8,
        conflict_count: 0,
        duplicate_count: 1,
        propagation_stages: 2,
        confidence_score: 0.88,
        evidence_coverage_score: 0.82,
        first_observed_at: '2026-04-10T14:00:00Z',
        last_updated_at: '2026-04-10T14:30:00Z',
      },
      created_at: '2026-04-10T14:00:00Z',
      updated_at: '2026-04-10T14:30:00Z',
    }),
  },
}));

const mockEvent: WeatherEvent = {
  id: 'ev-detail-101',
  event_id: 'ev-detail-101',
  title: 'Severe Thunderstorm in Kolkata',
  category: 'THUNDERSTORM',
  severity: 3,
  verification_status: 'UNDER_REVIEW',
  confidence_score: 0.88,
  state: 'West Bengal',
  district: 'Kolkata',
  latitude: 22.5726,
  longitude: 88.3639,
  created_at: '2026-04-10T14:00:00Z',
  description: 'Intense lightning, wind gusts up to 75 km/h recorded.',
  report_count: 8,
};

describe('EventDetailDrawer Component', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useAuthStore.setState({
      user: null,
      token: null,
      isAuthenticated: false,
    });
  });

  it('renders nothing when event is null', () => {
    const { container } = render(
      <EventDetailDrawer event={null} onClose={vi.fn()} />
    );
    expect(container.firstChild).toBeNull();
  });

  it('renders event overview details, badges, coordinates and confidence', () => {
    render(<EventDetailDrawer event={mockEvent} onClose={vi.fn()} />);

    expect(screen.getByText('Severe Thunderstorm in Kolkata')).toBeInTheDocument();
    expect(screen.getAllByText(/THUNDERSTORM/i).length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText(/REVIEW/i)).toBeInTheDocument();
    expect(screen.getByText(/88%/)).toBeInTheDocument();
    expect(screen.getByText('22.5726')).toBeInTheDocument();
    expect(screen.getByText('88.3639')).toBeInTheDocument();
    expect(
      screen.getByText('Intense lightning, wind gusts up to 75 km/h recorded.')
    ).toBeInTheDocument();
  });

  it('switches between Overview, Signals & Evidence, and DWEG Graph tabs', () => {
    render(<EventDetailDrawer event={mockEvent} onClose={vi.fn()} />);

    // Switch to Signals & Evidence
    const evidenceTab = screen.getByRole('button', { name: /signals & evidence/i });
    fireEvent.click(evidenceTab);
    expect(screen.getByText(/contributing to this canonical event/i)).toBeInTheDocument();

    // Switch to DWEG Graph
    const dwegTab = screen.getByRole('button', { name: /dweg graph/i });
    fireEvent.click(dwegTab);
    expect(screen.getByText(/Dynamic Weather Evidence Graph/i)).toBeInTheDocument();
    expect(screen.getByText('ev-detail-101')).toBeInTheDocument();
    expect(screen.getByText(/Connected Ingestion Reports/i)).toBeInTheDocument();

    // Switch to Event DNA
    const dnaTab = screen.getByRole('button', { name: /event dna/i });
    fireEvent.click(dnaTab);
    expect(eventsAPI.getDNA).toHaveBeenCalledWith('ev-detail-101');
  });

  it('does NOT show analyst override controls for unauthenticated or CITIZEN user', () => {
    useAuthStore.setState({
      user: {
        id: 'u-cit-1',
        email: 'cit@skypulse.gov.in',
        display_name: 'Citizen User',
        role: 'CITIZEN',
      },
      isAuthenticated: true,
      token: 'tok-1',
    });

    render(<EventDetailDrawer event={mockEvent} onClose={vi.fn()} />);
    expect(screen.queryByText(/ANALYST VERIFICATION OVERRIDE/i)).not.toBeInTheDocument();
  });

  it('shows analyst override controls for ANALYST or ADMIN user and triggers API call', async () => {
    useAuthStore.setState({
      user: {
        id: 'u-an-1',
        email: 'analyst@skypulse.gov.in',
        display_name: 'Senior Analyst',
        role: 'ANALYST',
      },
      isAuthenticated: true,
      token: 'tok-2',
    });

    (eventsAPI.verifyEvent as any).mockResolvedValue({
      data: { ...mockEvent, verification_status: 'VERIFIED' },
    });

    const handleUpdated = vi.fn();
    render(
      <EventDetailDrawer
        event={mockEvent}
        onClose={vi.fn()}
        onEventUpdated={handleUpdated}
      />
    );

    expect(screen.getByText(/ANALYST VERIFICATION OVERRIDE/i)).toBeInTheDocument();

    const noteInput = screen.getByPlaceholderText(/audit reason \/ notes/i);
    fireEvent.change(noteInput, { target: { value: 'Confirmed via Doppler radar' } });

    const verifyBtn = screen.getByRole('button', { name: /^Verify$/i });
    fireEvent.click(verifyBtn);

    await waitFor(() => {
      expect(eventsAPI.verifyEvent).toHaveBeenCalledWith(
        'ev-detail-101',
        'VERIFIED',
        'Confirmed via Doppler radar'
      );
      expect(screen.getByText(/Event status updated to VERIFIED/i)).toBeInTheDocument();
      expect(handleUpdated).toHaveBeenCalledWith(
        expect.objectContaining({ verification_status: 'VERIFIED' })
      );
    });
  });
});
