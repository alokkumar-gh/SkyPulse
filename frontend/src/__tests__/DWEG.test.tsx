import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import React from 'react';
import { BrowserRouter } from 'react-router-dom';
import { EvidenceGraph } from '../components/dweg/EvidenceGraph';
import { PropagationTimeline } from '../components/dweg/PropagationTimeline';
import { EvidenceChainPanel } from '../components/dweg/EvidenceChainPanel';
import { DWEGView } from '../pages/DWEGView';
import type {
  DWEGNode,
  DWEGEdge,
  PropagationTimelineResponse,
  EvidenceChainResponse,
} from '../types';

// Mock @vis.gl/react-google-maps for jsdom environment
vi.mock('@vis.gl/react-google-maps', () => {
  return {
    APIProvider: ({ children }: any) => <div data-testid="api-provider">{children}</div>,
    Map: ({ children }: any) => <div data-testid="google-map">{children}</div>,
    AdvancedMarker: ({ children, onClick }: any) => (
      <div data-testid="google-marker" onClick={onClick}>
        {children}
      </div>
    ),
    InfoWindow: ({ children }: any) => <div data-testid="info-window">{children}</div>,
    useMap: () => ({
      panTo: vi.fn(),
      setZoom: vi.fn(),
      getZoom: vi.fn(() => 6),
    }),
    useMapsLibrary: () => ({
      HeatmapLayer: class {
        setData = vi.fn();
        setMap = vi.fn();
      },
    }),
  };
});

// Mock api client
vi.mock('../utils/api', () => ({
  generateEventNarrative: vi.fn((ev: any) => `${ev?.category || 'Weather'} reported in ${ev?.state || 'India'}.`),
  STATE_CENTROIDS: {
    'Kerala': [10.8505, 76.2711],
  },
  eventsAPI: {
    list: vi.fn().mockResolvedValue({
      results: [
        {
          id: '11111111-1111-1111-1111-111111111111',
          category: 'FLOODING',
          severity: 3,
          location: { district: 'Wayanad', state: 'Kerala' },
        },
      ],
    }),
  },
  dwegAPI: {
    graph: vi.fn().mockResolvedValue({
      event_id: '11111111-1111-1111-1111-111111111111',
      nodes: [
        { id: 'event_1', type: 'WeatherEvent', label: 'Flooding in Wayanad', properties: { severity: 3 } },
        { id: 'loc_wayanad', type: 'Location', label: 'Wayanad', properties: { state: 'Kerala' } },
      ],
      edges: [
        { source: 'event_1', target: 'loc_wayanad', type: 'LOCATED_AT', properties: {} },
      ],
      generated_at: new Date().toISOString(),
    }),
    confidenceField: vi.fn().mockResolvedValue({
      type: 'FeatureCollection',
      features: [
        {
          type: 'Feature',
          geometry: { type: 'Point', coordinates: [76.13, 11.68] },
          properties: { weight: 0.9, is_centroid: true },
        },
      ],
    }),
    propagationTimeline: vi.fn().mockResolvedValue({
      event_id: '11111111-1111-1111-1111-111111111111',
      propagation_steps: [
        {
          step: 1,
          timestamp: new Date().toISOString(),
          location: { district: 'Wayanad', state: 'Kerala' },
          evidence_count: 3,
          severity: 3,
          propagation_direction: 'ORIGIN',
          time_delta_minutes: 0,
        },
      ],
      is_still_propagating: true,
    }),
    evidenceChain: vi.fn().mockResolvedValue({
      event_id: '11111111-1111-1111-1111-111111111111',
      narrative: 'Severe Flooding occurred in Wayanad corroborated by multiple citizen and radar reports.',
      evidence_chain: [
        {
          step: 1,
          type: 'CITIZEN_REPORT',
          source: 'CITIZEN',
          at: new Date().toISOString(),
          location: 'Wayanad',
          value: 'Heavy water logging observed near river bank.',
        },
      ],
      confidence: 0.88,
      generated_at: new Date().toISOString(),
    }),
    propagationAlerts: vi.fn().mockResolvedValue({
      alerts: [
        {
          id: 'alert-1',
          event_id: '11111111-1111-1111-1111-111111111111',
          event_category: 'FLOODING',
          alert_type: 'PROPAGATION_WARNING',
          message: 'Flooding propagating Eastward towards adjacent district.',
          created_at: new Date().toISOString(),
        },
      ],
    }),
  },
}));

describe('DWEG Component & Page Suite — Phase 10', () => {
  it('renders EvidenceGraph SVG canvas with nodes and legend', () => {
    const sampleNodes: DWEGNode[] = [
      { id: 'e1', type: 'WeatherEvent', label: 'Cyclone Alert', properties: { severity: 4 } },
      { id: 'r1', type: 'EvidenceReport', label: 'Radar Corroboration', properties: { confidence: 0.9 } },
    ];
    const sampleEdges: DWEGEdge[] = [
      { source: 'r1', target: 'e1', type: 'CORROBORATES', properties: {} },
    ];

    const { container } = render(<EvidenceGraph nodes={sampleNodes} edges={sampleEdges} />);
    expect(container.querySelector('svg')).toBeInTheDocument();
    expect(screen.getByText('Weather Event')).toBeInTheDocument();
    expect(screen.getByText('Evidence Report')).toBeInTheDocument();
  });

  it('renders PropagationTimeline with scrubber controls and step data', () => {
    const timelineData: PropagationTimelineResponse = {
      event_id: 'test-evt',
      is_still_propagating: true,
      propagation_steps: [
        {
          step: 1,
          location: { district: 'Puri', state: 'Odisha' },
          evidence_count: 4,
          severity: 3,
          propagation_direction: 'ORIGIN',
          time_delta_minutes: 0,
        },
        {
          step: 2,
          location: { district: 'Cuttack', state: 'Odisha' },
          evidence_count: 6,
          severity: 4,
          propagation_direction: 'NORTHWARD',
          time_delta_minutes: 90,
        },
      ],
    };

    render(<PropagationTimeline timeline={timelineData} />);
    expect(screen.getByText('Propagation Trajectory Timeline')).toBeInTheDocument();
    expect(screen.getByText('ACTIVE PROPAGATION')).toBeInTheDocument();
    expect(screen.getByText('Play')).toBeInTheDocument();
  });

  it('renders EvidenceChainPanel with narrative and structured steps', () => {
    const chainData: EvidenceChainResponse = {
      event_id: 'test-evt',
      narrative: 'High confidence thunderstorm tracked across Maharashtra.',
      confidence: 0.92,
      generated_at: new Date().toISOString(),
      evidence_chain: [
        {
          step: 1,
          type: 'CITIZEN_REPORT',
          source: 'CITIZEN',
          at: '2026-10-01T10:00:00Z',
          location: 'Pune',
          value: 'Hailstorm and lightning observed',
        },
      ],
    };

    render(<EvidenceChainPanel evidenceChain={chainData} />);
    expect(screen.getByText('EXPLAINABLE EVIDENCE NARRATIVE')).toBeInTheDocument();
    expect(screen.getByText('92% Confidence')).toBeInTheDocument();
    expect(screen.getByText('High confidence thunderstorm tracked across Maharashtra.')).toBeInTheDocument();
    expect(screen.getByText('Hailstorm and lightning observed')).toBeInTheDocument();
  });

  it('renders DWEGView page with tabs and propagation alert banner', async () => {
    render(
      <BrowserRouter>
        <DWEGView />
      </BrowserRouter>
    );

    // Check title
    expect(screen.getByText(/DWEG Intelligence/i)).toBeInTheDocument();

    // Check tabs
    expect(screen.getByText(/Evidence Graph Topology/i)).toBeInTheDocument();
    expect(screen.getByText(/Confidence Field Heatmap/i)).toBeInTheDocument();

    // Check alert banner
    await waitFor(() => {
      expect(screen.getByText(/DWEG PROPAGATION ALERT/i)).toBeInTheDocument();
    });
  });
});
