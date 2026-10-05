import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { KPIBar } from '../components/dashboard/KPIBar';
import type { WeatherEvent } from '../types';

const mockEvents: WeatherEvent[] = [
  {
    id: 'ev-1',
    category: 'FLOODING',
    severity: 3,
    confidence_score: 0.95,
    verification_status: 'VERIFIED',
    location: { state: 'Maharashtra', district: 'Mumbai' },
    first_reported_at: '2026-10-01T08:00:00Z',
    last_updated_at: '2026-10-01T08:30:00Z',
    evidence_count: 3,
    is_anomalous: false,
    is_active: true,
    is_demo: false,
  },
  {
    id: 'ev-2',
    category: 'CYCLONE',
    severity: 4,
    confidence_score: 0.88,
    verification_status: 'VERIFIED',
    location: { state: 'Odisha', district: 'Puri' },
    first_reported_at: '2026-10-01T07:00:00Z',
    last_updated_at: '2026-10-01T08:00:00Z',
    evidence_count: 8,
    is_anomalous: true,
    is_active: true,
    is_demo: false,
  },
  {
    id: 'ev-3',
    category: 'RAINFALL',
    severity: 1,
    confidence_score: 0.72,
    verification_status: 'UNVERIFIED',
    location: { state: 'Karnataka', district: 'Bengaluru' },
    first_reported_at: '2026-10-01T08:15:00Z',
    last_updated_at: '2026-10-01T08:15:00Z',
    evidence_count: 1,
    is_anomalous: false,
    is_active: true,
    is_demo: false,
  },
];

describe('KPIBar Component', () => {
  it('renders all four KPI metrics computed from live events', () => {
    render(<KPIBar events={mockEvents} totalReportsCount={1240} />);

    // Active Events: 3
    expect(screen.getByText('ACTIVE WEATHER EVENTS')).toBeInTheDocument();
    expect(screen.getByText('3')).toBeInTheDocument();

    // Severe Alerts (Sev 3 and 4): 2 (ev-1 is 3, ev-2 is 4)
    expect(screen.getByText('SEVERE CIVIL WARNINGS')).toBeInTheDocument();
    expect(screen.getByText('2')).toBeInTheDocument();

    // Verification Rate: 2 out of 3 = 67%
    expect(screen.getByText('GROUND TRUTH RATE')).toBeInTheDocument();
    expect(screen.getByText('67%')).toBeInTheDocument();

    // Ingested Reports: 1,240
    expect(screen.getByText('INGESTED OBSERVATIONS')).toBeInTheDocument();
    expect(screen.getByText('1,240')).toBeInTheDocument();
  });

  it('renders 0% and 0 counts gracefully when events array is empty', () => {
    render(<KPIBar events={[]} totalReportsCount={0} />);

    expect(screen.getByText('0%')).toBeInTheDocument();
    const zeros = screen.getAllByText('0');
    expect(zeros.length).toBeGreaterThanOrEqual(2);
  });

  it('renders dash placeholder when loading is true', () => {
    render(<KPIBar events={[]} loading={true} />);
    const dashes = screen.getAllByText('—');
    expect(dashes.length).toBe(4);
  });
});
