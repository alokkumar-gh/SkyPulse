/**
 * Frontend Unit Tests for Weather Source Reputation Graph
 * =======================================================
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import React from 'react';
import {
  SourceReputationPanel,
  ReputationStateBadge,
  CategoryReliabilityPill,
} from '../components/sources/SourceReputationPanel';
import { sourcesAPI } from '../utils/api';
import type { SourceReputation, CategoryReputationDetail } from '../types';

vi.mock('../utils/api', () => ({
  sourcesAPI: {
    reputation: vi.fn(),
    getTimeline: vi.fn(),
  },
}));

const mockSourceReputation: SourceReputation = {
  source_id: 'src-1234-abcd',
  source_name: 'IMD Bengaluru Doppler Radar',
  source_type: 'GOVERNMENT_API',
  current_trust: 0.92,
  reputation_state: 'TRUSTED',
  observation_count: 48,
  verified_count: 42,
  supported_count: 45,
  contradicted_count: 0,
  duplicate_count: 2,
  corroboration_rate: 0.85,
  contradiction_rate: 0.0,
  verification_support_rate: 0.94,
  duplicate_rate: 0.04,
  category_breakdown: {
    RAINFALL: {
      category: 'RAINFALL',
      observation_count: 30,
      verified_count: 28,
      contradicted_count: 0,
      supported_count: 29,
      support_rate: 0.97,
      contradiction_rate: 0.0,
      reliability_level: 'STRONG_EVIDENCE',
    },
    THUNDERSTORM: {
      category: 'THUNDERSTORM',
      observation_count: 18,
      verified_count: 14,
      contradicted_count: 0,
      supported_count: 16,
      support_rate: 0.89,
      contradiction_rate: 0.0,
      reliability_level: 'STRONG_EVIDENCE',
    },
  },
  factors: {
    verification_support_rate: 0.94,
    contradiction_rate: 0.0,
    corroboration_rate: 0.85,
    duplicate_rate: 0.04,
    temporal_consistency: 0.95,
    spatial_consistency: 0.98,
    category_consistency: 0.88,
    evidence_volume_score: 1.0,
    recency_score: 0.92,
  },
  temporal_accuracy: 0.95,
  spatial_accuracy: 0.98,
  explanation: [
    'Official institutional weather data feed with high baseline trust',
    '48 eligible observations evaluated (2 duplicates identified and deduplicated)',
    '42 observations supported verification outcomes (94% support rate)',
    'Zero contradicted observations recorded across active history',
    'Strong historical reliability in: RAINFALL (30 obs, 97% support), THUNDERSTORM (18 obs, 89% support)',
  ],
  is_official: true,
  is_active: true,
  reputation_updated_at: new Date().toISOString(),
};

describe('Weather Source Reputation Graph Suite', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders reputation state badges with proper labels and colors', () => {
    const states: Array<'NEW' | 'INSUFFICIENT_EVIDENCE' | 'ESTABLISHED' | 'TRUSTED' | 'WATCH' | 'LOW_RELIABILITY'> = [
      'NEW',
      'INSUFFICIENT_EVIDENCE',
      'ESTABLISHED',
      'TRUSTED',
      'WATCH',
      'LOW_RELIABILITY',
    ];

    const { unmount } = render(
      <div>
        {states.map((st) => (
          <ReputationStateBadge key={st} state={st} />
        ))}
      </div>
    );

    expect(screen.getByText('NEW')).toBeInTheDocument();
    expect(screen.getByText('INSUFFICIENT EVIDENCE')).toBeInTheDocument();
    expect(screen.getByText('ESTABLISHED')).toBeInTheDocument();
    expect(screen.getByText('TRUSTED')).toBeInTheDocument();
    expect(screen.getByText('WATCH')).toBeInTheDocument();
    expect(screen.getByText('LOW RELIABILITY')).toBeInTheDocument();

    unmount();
  });

  it('renders category reliability pills with category and observation metrics', () => {
    const detail: CategoryReputationDetail = {
      category: 'RAINFALL',
      observation_count: 24,
      verified_count: 22,
      contradicted_count: 1,
      supported_count: 23,
      support_rate: 0.96,
      contradiction_rate: 0.04,
      reliability_level: 'STRONG_EVIDENCE',
    };

    render(<CategoryReliabilityPill detail={detail} />);
    expect(screen.getByText('RAINFALL')).toBeInTheDocument();
    expect(screen.getByText('24 obs')).toBeInTheDocument();
    expect(screen.getByText('96% Verified')).toBeInTheDocument();
  });

  it('renders source reputation panel with cards, metrics, and state badge', async () => {
    vi.mocked(sourcesAPI.reputation).mockResolvedValueOnce({
      items: [mockSourceReputation],
      total: 1,
      timestamp: new Date().toISOString(),
    });

    render(<SourceReputationPanel />);

    await waitFor(() => {
      expect(screen.getByText('IMD Bengaluru Doppler Radar')).toBeInTheDocument();
    });

    expect(screen.getAllByText('TRUSTED').length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText('92%')).toBeInTheDocument(); // Trust score
    expect(screen.getByText('94%')).toBeInTheDocument(); // Support rate
    expect(screen.getByText('85%')).toBeInTheDocument(); // Corroboration rate
  });

  it('expands source card to reveal WHY THIS REPUTATION explanation and category matrix', async () => {
    vi.mocked(sourcesAPI.reputation).mockResolvedValueOnce({
      items: [mockSourceReputation],
      total: 1,
      timestamp: new Date().toISOString(),
    });

    vi.mocked(sourcesAPI.getTimeline).mockResolvedValueOnce({
      source_id: mockSourceReputation.source_id,
      source_name: mockSourceReputation.source_name,
      current_state: 'TRUSTED',
      timeline: [
        {
          milestone_id: 'm1',
          timestamp: new Date().toISOString(),
          event_type: 'SOURCE_REGISTERED',
          title: 'Source Registered',
          description: 'Initialized with baseline trust',
          trust_score: 0.9,
        },
      ],
    });

    render(<SourceReputationPanel />);

    await waitFor(() => {
      expect(screen.getByText('IMD Bengaluru Doppler Radar')).toBeInTheDocument();
    });

    // Toggle expand button
    const toggleBtn = screen.getByLabelText('Toggle explanation and evidence');
    fireEvent.click(toggleBtn);

    await waitFor(() => {
      expect(screen.getByText('WHY THIS REPUTATION?')).toBeInTheDocument();
      expect(screen.getByText('CATEGORY-SPECIFIC RELIABILITY MATRIX')).toBeInTheDocument();
    });

    expect(
      screen.getByText(/48 eligible observations evaluated/i)
    ).toBeInTheDocument();
  });

  it('renders empty state when no sources match filter', async () => {
    vi.mocked(sourcesAPI.reputation).mockResolvedValueOnce({
      items: [],
      total: 0,
      timestamp: new Date().toISOString(),
    });

    render(<SourceReputationPanel />);

    await waitFor(() => {
      expect(screen.getByText('No Sources Found')).toBeInTheDocument();
    });
  });
});
