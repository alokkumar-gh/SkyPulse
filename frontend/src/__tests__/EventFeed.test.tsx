import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { EventFeed } from '../components/events/EventFeed';
import type { WeatherEvent } from '../types';

const mockEvents: WeatherEvent[] = [
  {
    id: 'ev-1',
    event_id: 'ev-1',
    title: 'Severe Cyclone Amphan',
    category: 'CYCLONE',
    severity: 4,
    verification_status: 'VERIFIED',
    confidence_score: 0.95,
    state: 'Odisha',
    district: 'Puri',
    latitude: 19.8135,
    longitude: 85.8312,
    created_at: '2026-04-10T12:00:00Z',
    is_synthetic: false,
    report_count: 12,
  },
  {
    id: 'ev-2',
    event_id: 'ev-2',
    title: 'Flash Flood Warning',
    category: 'FLOODING',
    severity: 3,
    verification_status: 'UNVERIFIED',
    confidence_score: 0.65,
    state: 'Assam',
    district: 'Guwahati',
    latitude: 26.1445,
    longitude: 91.7362,
    created_at: '2026-04-10T12:30:00Z',
    is_synthetic: true,
    report_count: 3,
  },
  {
    id: 'ev-3',
    event_id: 'ev-3',
    title: 'Mild Heatwave',
    category: 'HEATWAVE',
    severity: 2,
    verification_status: 'UNVERIFIED',
    confidence_score: 0.72,
    state: 'Rajasthan',
    district: 'Jaipur',
    latitude: 26.9124,
    longitude: 75.7873,
    created_at: '2026-04-10T13:00:00Z',
    is_synthetic: false,
    report_count: 5,
  },
];

describe('EventFeed Component', () => {
  it('renders list of events and total counts', () => {
    const handleSelect = vi.fn();
    render(
      <EventFeed
        events={mockEvents}
        selectedEventId={null}
        onSelectEvent={handleSelect}
        loading={false}
      />
    );

    expect(screen.getByText('Live Event Feed')).toBeInTheDocument();
    expect(screen.getByText('Severe Cyclone Amphan')).toBeInTheDocument();
    expect(screen.getByText('Flash Flood Warning')).toBeInTheDocument();
    expect(screen.getByText('Mild Heatwave')).toBeInTheDocument();
  });

  it('filters events by search query across title, category, or state', () => {
    const handleSelect = vi.fn();
    render(
      <EventFeed
        events={mockEvents}
        selectedEventId={null}
        onSelectEvent={handleSelect}
      />
    );

    const searchInput = screen.getByPlaceholderText(/search state/i);
    fireEvent.change(searchInput, { target: { value: 'Assam' } });

    expect(screen.getByText('Flash Flood Warning')).toBeInTheDocument();
    expect(screen.queryByText('Severe Cyclone Amphan')).not.toBeInTheDocument();
    expect(screen.queryByText('Mild Heatwave')).not.toBeInTheDocument();
  });

  it('filters events by quick filter "severe"', () => {
    const handleSelect = vi.fn();
    render(
      <EventFeed
        events={mockEvents}
        selectedEventId={null}
        onSelectEvent={handleSelect}
      />
    );

    const severeButton = screen.getByRole('button', { name: /severe/i });
    fireEvent.click(severeButton);

    // ev-1 (sev 4) and ev-2 (sev 3) should match; ev-3 (sev 2) filtered out
    expect(screen.getByText('Severe Cyclone Amphan')).toBeInTheDocument();
    expect(screen.getByText('Flash Flood Warning')).toBeInTheDocument();
    expect(screen.queryByText('Mild Heatwave')).not.toBeInTheDocument();
  });

  it('filters events by quick filter "verified"', () => {
    const handleSelect = vi.fn();
    render(
      <EventFeed
        events={mockEvents}
        selectedEventId={null}
        onSelectEvent={handleSelect}
      />
    );

    const verifiedButton = screen.getByRole('button', { name: /verified/i });
    fireEvent.click(verifiedButton);

    // Only ev-1 is VERIFIED
    expect(screen.getByText('Severe Cyclone Amphan')).toBeInTheDocument();
    expect(screen.queryByText('Flash Flood Warning')).not.toBeInTheDocument();
    expect(screen.queryByText('Mild Heatwave')).not.toBeInTheDocument();
  });

  it('invokes onSelectEvent callback when an event card is clicked', () => {
    const handleSelect = vi.fn();
    render(
      <EventFeed
        events={mockEvents}
        selectedEventId={null}
        onSelectEvent={handleSelect}
      />
    );

    const card = screen.getByText('Severe Cyclone Amphan');
    fireEvent.click(card);

    expect(handleSelect).toHaveBeenCalledWith(mockEvents[0]);
  });

  it('renders empty state when no events match the search query', () => {
    const handleSelect = vi.fn();
    render(
      <EventFeed
        events={mockEvents}
        selectedEventId={null}
        onSelectEvent={handleSelect}
      />
    );

    const searchInput = screen.getByPlaceholderText(/search state/i);
    fireEvent.change(searchInput, { target: { value: 'NonexistentRegion' } });

    expect(screen.getByText(/no events found/i)).toBeInTheDocument();
  });
});
