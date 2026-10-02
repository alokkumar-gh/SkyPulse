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

    // Verify severity numbers rendered inside markers
    expect(screen.getByText('3')).toBeInTheDocument();
    expect(screen.getByText('2')).toBeInTheDocument();

    // Verify severity legend
    expect(screen.getByText('SEVERITY SCALE')).toBeInTheDocument();
    expect(screen.getByText('1 Minor')).toBeInTheDocument();
    expect(screen.getByText('4 Extreme')).toBeInTheDocument();
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
    expect(screen.getByText(/VITE_GOOGLE_MAPS_API_KEY/i)).toBeInTheDocument();
    expect(screen.getByText(/Tracking 2 active weather event\(s\)/i)).toBeInTheDocument();
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
});
