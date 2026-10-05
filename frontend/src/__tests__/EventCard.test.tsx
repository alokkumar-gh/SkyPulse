import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { EventCard } from '../components/events/EventCard';
import type { WeatherEvent } from '../types';

const mockEvent: WeatherEvent = {
  id: 'ev-test-101',
  category: 'FLOODING',
  severity: 3,
  confidence_score: 0.92,
  verification_status: 'VERIFIED',
  location: {
    state: 'Maharashtra',
    district: 'Mumbai',
    city: 'Mumbai',
    lat: 19.076,
    lon: 72.877,
  },
  title: 'Severe Urban Inundation in Dadar',
  description: 'Water levels reaching 3 feet on major transit corridors.',
  state: 'Maharashtra',
  district: 'Mumbai',
  first_reported_at: new Date().toISOString(),
  last_updated_at: new Date().toISOString(),
  evidence_count: 5,
  is_anomalous: false,
  is_active: true,
  is_demo: false,
  report_count: 14,
};

describe('EventCard Component', () => {
  it('renders weather event title, location, category and severity', () => {
    render(<EventCard event={mockEvent} />);

    expect(screen.getByText('Severe Urban Inundation in Dadar')).toBeInTheDocument();
    expect(screen.getByText(/FLOODING/i)).toBeInTheDocument();
    expect(screen.getByText(/●\s*3/)).toBeInTheDocument();
    expect(screen.getByText(/VERIFIED/)).toBeInTheDocument();
    expect(screen.getByText(/Mumbai/)).toBeInTheDocument();
  });

  it('triggers onClick handler when card is clicked', () => {
    const handleClick = vi.fn();
    render(<EventCard event={mockEvent} onClick={handleClick} />);

    const card = screen.getByText('Severe Urban Inundation in Dadar');
    fireEvent.click(card);

    expect(handleClick).toHaveBeenCalledTimes(1);
    expect(handleClick).toHaveBeenCalledWith(mockEvent);
  });

  it('renders synthetic event cleanly without breaking UI', () => {
    const syntheticEvent: WeatherEvent = {
      ...mockEvent,
      id: 'ev-syn-1',
      is_synthetic: true,
    };

    render(<EventCard event={syntheticEvent} />);
    expect(screen.getByText('Severe Urban Inundation in Dadar')).toBeInTheDocument();
  });
});
