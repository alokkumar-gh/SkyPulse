import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { SubmitReport } from '../pages/SubmitReport';
import { VerificationQueue } from '../pages/VerificationQueue';
import { reportsAPI, eventsAPI } from '../utils/api';
import { useEventsStore } from '../store/eventsStore';
import type { WeatherEvent } from '../types';

vi.mock('../utils/api', () => ({
  reportsAPI: {
    createReport: vi.fn(),
  },
  eventsAPI: {
    list: vi.fn(),
    get: vi.fn(),
    verifyEvent: vi.fn(),
  },
}));

describe('Workflows Component Suite', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('Citizen Report Submission Workflow (SubmitReport)', () => {
    it('renders form inputs and handles missing description validation', async () => {
      render(<SubmitReport />);

      expect(screen.getByText('Submit Ground Observation')).toBeInTheDocument();

      const submitButton = screen.getByRole('button', { name: /transmit observation/i });
      fireEvent.click(submitButton);

      expect(
        screen.getByText(/please provide a brief description/i)
      ).toBeInTheDocument();
      expect(reportsAPI.createReport).not.toHaveBeenCalled();
    });

    it('submits valid citizen report and shows success message', async () => {
      (reportsAPI.createReport as any).mockResolvedValue({
        id: 'rep-cit-101',
        category: 'FLOODING',
        severity: 3,
        status: 'SUBMITTED',
      });

      render(<SubmitReport />);

      const descTextarea = screen.getByLabelText(/observation narrative/i);
      fireEvent.change(descTextarea, {
        target: { value: 'Waterlogging over 2 feet near local market, traffic halted.' },
      });

      const submitButton = screen.getByRole('button', { name: /transmit observation/i });
      fireEvent.click(submitButton);

      await waitFor(() => {
        expect(reportsAPI.createReport).toHaveBeenCalledWith(
          expect.objectContaining({
            description: 'Waterlogging over 2 feet near local market, traffic halted.',
            source_type: 'CITIZEN',
          })
        );
        expect(
          screen.getByText(/observation ingested successfully/i)
        ).toBeInTheDocument();
      });
    });
  });

  describe('Analyst Verification Workflow (VerificationQueue)', () => {
    const mockPendingEvents: WeatherEvent[] = [
      {
        id: 'ev-queue-1',
        event_id: 'ev-queue-1',
        title: 'Flash Flood Reported in Cuttack',
        category: 'FLOODING',
        severity: 3,
        verification_status: 'REQUIRES_REVIEW',
        confidence_score: 0.62,
        state: 'Odisha',
        district: 'Cuttack',
        latitude: 20.4625,
        longitude: 85.883,
        created_at: '2026-04-10T10:00:00Z',
        report_count: 4,
      },
    ];

    it('renders pending events requiring analyst verification', async () => {
      useEventsStore.setState({
        events: mockPendingEvents,
        total: 1,
        isLoading: false,
        loading: false,
      });

      render(<VerificationQueue />);

      expect(screen.getByText('Ground Truth Verification Queue')).toBeInTheDocument();
      expect(
        screen.getByText(/PENDING VALIDATION ITEMS \(1\)/i)
      ).toBeInTheDocument();
      expect(
        screen.getAllByText('Flash Flood Reported in Cuttack').length
      ).toBeGreaterThanOrEqual(1);
    });

    it('allows analyst to inspect an event and perform verification action', async () => {
      useEventsStore.setState({
        events: mockPendingEvents,
        total: 1,
        isLoading: false,
        loading: false,
      });

      (eventsAPI.verifyEvent as any).mockResolvedValue({
        data: { ...mockPendingEvents[0], verification_status: 'VERIFIED' },
      });

      render(<VerificationQueue />);

      const eventItem = screen.getAllByText('Flash Flood Reported in Cuttack')[0];
      fireEvent.click(eventItem);

      expect(screen.getByText(/Operator Audit Justification/i)).toBeInTheDocument();

      const verifyBtn = screen.getByRole('button', { name: /confirm ground truth/i });
      fireEvent.click(verifyBtn);

      await waitFor(() => {
        expect(eventsAPI.verifyEvent).toHaveBeenCalledWith(
          'ev-queue-1',
          'VERIFIED',
          ''
        );
      });
    });
  });
});
