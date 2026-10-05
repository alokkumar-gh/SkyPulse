import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import React from 'react';
import { SkyPulseMap } from '../components/map/SkyPulseMap';
import { ConfidenceFieldLayer } from '../components/dweg/ConfidenceFieldLayer';
import type { WeatherEvent, ConfidenceFieldResponse } from '../types';

// Mock @vis.gl/react-google-maps
vi.mock('@vis.gl/react-google-maps', () => {
  return {
    APIProvider: ({ children }: any) => <div data-testid="api-provider">{children}</div>,
    Map: ({ children }: any) => <div data-testid="google-map">{children}</div>,
    AdvancedMarker: ({ children, onClick, title }: any) => (
      <div data-testid="google-marker" title={title} onClick={onClick}>
        {children}
      </div>
    ),
    InfoWindow: ({ children }: any) => <div data-testid="info-window">{children}</div>,
    useMap: () => ({
      panTo: vi.fn(),
      setZoom: vi.fn(),
      getZoom: vi.fn(() => 5),
    }),
    useMapsLibrary: () => ({
      HeatmapLayer: class {
        setData = vi.fn();
        setMap = vi.fn();
      },
    }),
  };
});

describe('Google Maps Weather Map Suite — Step 1 Migration', () => {
  const sampleEvents: WeatherEvent[] = [
    {
      id: 'evt-1',
      category: 'FLOODING',
      severity: 3,
      confidence_score: 0.88,
      verification_status: 'VERIFIED',
      latitude: 19.076,
      longitude: 72.8777,
      district: 'Mumbai',
      state: 'Maharashtra',
      title: 'Severe Urban Inundation in Mumbai',
      evidence_count: 5,
      is_active: true,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    },
    {
      id: 'evt-2',
      category: 'THUNDERSTORM',
      severity: 2,
      confidence_score: 0.75,
      verification_status: 'UNVERIFIED',
      latitude: 12.9716,
      longitude: 77.5946,
      district: 'Bengaluru Urban',
      state: 'Karnataka',
      title: 'Thunderstorm with Gusty Winds',
      evidence_count: 2,
      is_active: true,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    },
  ];

  beforeEach(() => {
    vi.clearAllMocks();
    // Default mock environment with API key
    (import.meta as any).env = {
      VITE_GOOGLE_MAPS_API_KEY: 'test-google-maps-api-key',
    };
  });

  it('renders Google Maps with markers when API key is provided', () => {
    const handleSelect = vi.fn();
    render(
      <SkyPulseMap
        events={sampleEvents}
        selectedEventId={null}
        onSelectEvent={handleSelect}
        apiKey="test-google-maps-api-key"
      />
    );

    expect(screen.getByTestId('google-map')).toBeInTheDocument();
    const markers = screen.getAllByTestId('google-marker');
    expect(markers.length).toBe(2);

    // Verify severity legend
    expect(screen.getByText('MAP INTELLIGENCE')).toBeInTheDocument();
    expect(screen.getByText('1 Minor')).toBeInTheDocument();
    expect(screen.getByText('4 Extreme')).toBeInTheDocument();
    expect(screen.getByText('CAP Zone')).toBeInTheDocument();
  });

  it('handles marker click and triggers onSelectEvent callback', () => {
    const handleSelect = vi.fn();
    render(
      <SkyPulseMap
        events={sampleEvents}
        selectedEventId={null}
        onSelectEvent={handleSelect}
        apiKey="test-google-maps-api-key"
      />
    );

    const markers = screen.getAllByTestId('google-marker');
    fireEvent.click(markers[0]);

    expect(handleSelect).toHaveBeenCalledTimes(1);
    expect(handleSelect).toHaveBeenCalledWith(sampleEvents[0]);
  });

  it('displays graceful fallback when Google Maps API key is missing', () => {
    const handleSelect = vi.fn();
    render(
      <SkyPulseMap
        events={sampleEvents}
        selectedEventId={null}
        onSelectEvent={handleSelect}
        apiKey=""
      />
    );

    expect(screen.getByText(/Google Maps API Key Required/i)).toBeInTheDocument();
    expect(screen.getByText(/Tracking/i)).toBeInTheDocument();
    expect(screen.getByText(/mapped weather event\(s\)/i)).toBeInTheDocument();
  });

  it('renders ConfidenceFieldLayer with Google Maps heatmap and evidence points', () => {
    const sampleConfidenceField: ConfidenceFieldResponse = {
      type: 'FeatureCollection',
      features: [
        {
          type: 'Feature',
          geometry: { type: 'Point', coordinates: [73.8567, 18.5204] },
          properties: { weight: 1.0, is_centroid: true, category: 'THUNDERSTORM', source_type: 'RADAR' },
        },
        {
          type: 'Feature',
          geometry: { type: 'Point', coordinates: [73.86, 18.53] },
          properties: { weight: 0.8, is_centroid: false, category: 'THUNDERSTORM', source_type: 'CITIZEN' },
        },
      ],
    };

    render(
      <ConfidenceFieldLayer
        confidenceField={sampleConfidenceField}
        height={400}
        apiKey="test-google-maps-api-key"
      />
    );

    expect(screen.getByTestId('google-map')).toBeInTheDocument();
    expect(screen.getByText('Evidence Density Field')).toBeInTheDocument();
    expect(screen.getByText('Low (0%)')).toBeInTheDocument();
    expect(screen.getByText('High (100%)')).toBeInTheDocument();

    const markers = screen.getAllByTestId('google-marker');
    expect(markers.length).toBe(2);
    expect(screen.getByText('★')).toBeInTheDocument(); // Centroid icon
    expect(screen.getByText('80%')).toBeInTheDocument(); // Evidence weight label
  });

  it('renders CAP multi-vertex hazard polygon and handles polygon selection', () => {
    const handleSelect = vi.fn();
    const eventWithPolygon: WeatherEvent = {
      id: 'cap-evt-1',
      category: 'CYCLONE',
      severity: 4,
      confidence_score: 0.95,
      verification_status: 'OFFICIAL_ALERT',
      latitude: 19.81,
      longitude: 85.83,
      district: 'Puri',
      state: 'Odisha',
      title: 'Cyclone Alert with Hazard Polygon',
      evidence_count: 3,
      is_active: true,
      has_polygon: true,
      hazard_polygon: {
        type: 'Polygon',
        coordinates: [
          [
            [85.83, 19.81],
            [86.20, 20.15],
            [85.90, 20.30],
            [85.83, 19.81],
          ],
        ],
      },
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    };

    render(
      <SkyPulseMap
        events={[...sampleEvents, eventWithPolygon]}
        selectedEventId={null}
        onSelectEvent={handleSelect}
        apiKey="test-google-maps-api-key"
      />
    );

    // Verify polygon layer rendered
    expect(screen.getByTestId('hazard-polygons-layer')).toBeInTheDocument();
    const polyElement = screen.getByTestId('hazard-polygon-element');
    expect(polyElement).toBeInTheDocument();
    expect(polyElement).toHaveAttribute('data-event-id', 'cap-evt-1');

    // Verify polygon count badge
    expect(screen.getByText(/1 CAP hazard zone/i)).toBeInTheDocument();

    // Click polygon triggers onSelectEvent
    fireEvent.click(polyElement);
    expect(handleSelect).toHaveBeenCalledWith(eventWithPolygon);
  });

  it('handles events without polygon gracefully without crashing', () => {
    const handleSelect = vi.fn();
    render(
      <SkyPulseMap
        events={sampleEvents}
        selectedEventId={null}
        onSelectEvent={handleSelect}
        apiKey="test-google-maps-api-key"
      />
    );

    expect(screen.getByTestId('hazard-polygons-layer')).toBeInTheDocument();
    // No polygons rendered for sampleEvents (has_polygon is false/undefined)
    expect(screen.queryByTestId('hazard-polygon-element')).toBeNull();
  });
});

