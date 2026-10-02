import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { useAuthStore } from '../store/authStore';
import { AnalystLayout } from '../layouts/AnalystLayout';
import { VerificationQueue } from '../pages/analyst/VerificationQueue';
import { AnalystEventDetail } from '../pages/analyst/AnalystEventDetail';
import { DuplicateClusterPanel } from '../components/analyst/DuplicateClusterPanel';
import { verificationAPI, eventsAPI } from '../utils/api';

vi.mock('../utils/api', () => ({
  verificationAPI: {
    queue: vi.fn(),
    override: vi.fn(),
    clusters: vi.fn(),
    splitCluster: vi.fn(),
    mergeClusters: vi.fn(),
    get: vi.fn(),
  },
  eventsAPI: {
    get: vi.fn(),
  },
  authAPI: {
    login: vi.fn(),
    logout: vi.fn(),
    me: vi.fn(),
  },
}));

describe('Analyst Interface Workflows', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useAuthStore.setState({
      user: {
        id: 'usr-analyst-1',
        email: 'analyst@skypulse.gov.in',
        name: 'Lead Weather Analyst',
        role: 'ANALYST',
        is_active: true,
      },
      token: 'demo-token',
      isAuthenticated: true,
      error: null,
    });
  });

  describe('AnalystLayout', () => {
    it('renders analyst navigation links for authorized ANALYST', () => {
      render(
        <MemoryRouter initialEntries={['/analyst/queue']}>
          <AnalystLayout />
        </MemoryRouter>
      );

      expect(screen.getByText('Analyst Console')).toBeInTheDocument();
      expect(screen.getByText('Verification Queue')).toBeInTheDocument();
      expect(screen.getByText('Events Triage')).toBeInTheDocument();
      expect(screen.getByText('Duplicate Clusters')).toBeInTheDocument();
      expect(screen.getByText('Priority Alerts')).toBeInTheDocument();
    });

    it('blocks unauthorized citizen user with Authorization Required', () => {
      useAuthStore.setState({
        user: {
          id: 'usr-citizen-1',
          email: 'citizen@example.com',
          name: 'Citizen User',
          role: 'CITIZEN',
          is_active: true,
        },
      });

      render(
        <MemoryRouter initialEntries={['/analyst/queue']}>
          <AnalystLayout />
        </MemoryRouter>
      );

      expect(screen.getByText('Analyst Authorization Required')).toBeInTheDocument();
      expect(screen.queryByText('Verification Queue')).not.toBeInTheDocument();
    });
  });

  describe('VerificationQueue', () => {
    const mockQueueItems = [
      {
        id: 'evt-test-1',
        title: 'Severe Flash Flood Alert',
        category: 'FLOODING',
        severity: 4,
        state: 'Kerala',
        district: 'Wayanad',
        timestamp: '2026-10-01T08:00:00Z',
        confidence_score: 0.88,
        verification_status: 'UNVERIFIED',
        evidence_count: 5,
        first_reported_at: '2026-10-01T08:00:00Z',
      },
      {
        id: 'evt-test-2',
        title: 'High Wind Velocity',
        category: 'CYCLONE',
        severity: 3,
        state: 'Odisha',
        district: 'Puri',
        timestamp: '2026-10-01T09:30:00Z',
        confidence_score: 0.65,
        verification_status: 'UNVERIFIED',
        evidence_count: 2,
        first_reported_at: '2026-10-01T09:30:00Z',
      },
    ];

    it('fetches and renders queue items with confidence and priority', async () => {
      vi.mocked(verificationAPI.queue).mockResolvedValue({
        results: mockQueueItems as any,
        total: 2,
        page: 1,
        per_page: 20,
      });

      render(
        <MemoryRouter>
          <VerificationQueue />
        </MemoryRouter>
      );

      expect(screen.getByText('Analyst Verification Queue')).toBeInTheDocument();

      await waitFor(() => {
        expect(screen.getByText('Flooding')).toBeInTheDocument();
        expect(screen.getByText('Cyclone')).toBeInTheDocument();
        expect(screen.getByText('Kerala')).toBeInTheDocument();
        expect(screen.getByText('Odisha')).toBeInTheDocument();
      });
    });

    it('triggers quick verify modal and executes verification override', async () => {
      vi.mocked(verificationAPI.queue).mockResolvedValue({
        results: mockQueueItems as any,
        total: 2,
        page: 1,
        per_page: 20,
      });
      vi.mocked(verificationAPI.override).mockResolvedValueOnce({
        event_id: 'evt-test-1',
        status: 'VERIFIED',
        confidence_score: 0.95,
        explanation_text: 'Verified by analyst',
        evidence_items: [],
        signals: {},
        updated_at: '2026-10-01T10:00:00Z',
      });

      render(
        <MemoryRouter>
          <VerificationQueue />
        </MemoryRouter>
      );

      await waitFor(() => {
        expect(screen.getByText('Flooding')).toBeInTheDocument();
      });

      const verifyButtons = screen.getAllByRole('button', { name: /^Verify$/i });
      fireEvent.click(verifyButtons[0]);

      expect(screen.getByText('Verify Weather Event')).toBeInTheDocument();

      const notesInput = screen.getByPlaceholderText(/Provide reason for this verification decision/i);
      fireEvent.change(notesInput, { target: { value: 'Confirmed by doppler radar imagery.' } });

      const confirmButton = screen.getByRole('button', { name: 'Confirm Verification' });
      fireEvent.click(confirmButton);

      await waitFor(() => {
        expect(verificationAPI.override).toHaveBeenCalledWith(
          'evt-test-1',
          'VERIFIED',
          'Confirmed by doppler radar imagery.'
        );
      });
    });

    it('triggers quick reject modal requiring reason', async () => {
      vi.mocked(verificationAPI.queue).mockResolvedValue({
        results: mockQueueItems as any,
        total: 2,
        page: 1,
        per_page: 20,
      });
      vi.mocked(verificationAPI.override).mockResolvedValueOnce({
        event_id: 'evt-test-2',
        status: 'CONTRADICTED',
        confidence_score: 0.1,
        explanation_text: 'Rejected by analyst',
        evidence_items: [],
        signals: {},
        updated_at: '2026-10-01T10:00:00Z',
      });

      render(
        <MemoryRouter>
          <VerificationQueue />
        </MemoryRouter>
      );

      await waitFor(() => {
        expect(screen.getByText('Cyclone')).toBeInTheDocument();
      });

      const rejectButtons = screen.getAllByRole('button', { name: /^Reject$/i });
      fireEvent.click(rejectButtons[1]);

      expect(screen.getByText('Contradict / Reject Weather Event')).toBeInTheDocument();

      const reasonInput = screen.getByPlaceholderText(/Provide reason for this verification decision/i);
      fireEvent.change(reasonInput, { target: { value: 'Social media rumor with no sensor corroboration.' } });

      const confirmRejectBtn = screen.getByRole('button', { name: 'Confirm Rejection' });
      fireEvent.click(confirmRejectBtn);

      await waitFor(() => {
        expect(verificationAPI.override).toHaveBeenCalledWith(
          'evt-test-2',
          'CONTRADICTED',
          'Social media rumor with no sensor corroboration.'
        );
      });
    });
  });

  describe('AnalystEventDetail', () => {
    const mockEvent = {
      id: 'evt-test-100',
      title: 'Urban Waterlogging at MG Road',
      category: 'FLOOD',
      severity: 4,
      status: 'ACTIVE',
      verification_status: 'UNVERIFIED',
      confidence_score: 0.76,
      state: 'Karnataka',
      district: 'Bengaluru Urban',
      first_reported_at: '2026-10-01T07:15:00Z',
      evidence_count: 4,
      description: 'Severe waterlogging reported from multiple citizen sensors.',
      location: { latitude: 12.9716, longitude: 77.5946, state: 'Karnataka', district: 'Bengaluru Urban' },
    };

    it('renders event overview and allows manual override submission', async () => {
      vi.mocked(eventsAPI.get).mockResolvedValueOnce(mockEvent as any);
      vi.mocked(verificationAPI.get).mockResolvedValueOnce({
        event_id: 'evt-test-100',
        status: 'UNVERIFIED',
        confidence_score: 0.76,
        explanation_text: 'Pending analyst corroboration',
        evidence_items: [],
        signals: {},
        updated_at: '2026-10-01T07:15:00Z',
      });
      vi.mocked(verificationAPI.clusters).mockResolvedValueOnce([]);
      vi.mocked(verificationAPI.override).mockResolvedValueOnce({
        event_id: 'evt-test-100',
        status: 'VERIFIED',
        confidence_score: 0.99,
        explanation_text: 'Manual analyst confirmation',
        evidence_items: [],
        signals: {},
        updated_at: '2026-10-01T08:00:00Z',
      });

      render(
        <MemoryRouter initialEntries={['/analyst/events/evt-test-100']}>
          <Routes>
            <Route path="/analyst/events/:eventId" element={<AnalystEventDetail />} />
          </Routes>
        </MemoryRouter>
      );

      await waitFor(() => {
        expect(screen.getByText('Urban Waterlogging at MG Road')).toBeInTheDocument();
        expect(screen.getByText('Manual Override Decision')).toBeInTheDocument();
      });

      const reasonField = screen.getByPlaceholderText(/Reason for manual override/i);
      fireEvent.change(reasonField, { target: { value: 'Verified with city traffic CCTV camera feeds.' } });

      const commitBtn = screen.getByRole('button', { name: /Submit Override & Audit Log/i });
      fireEvent.click(commitBtn);

      await waitFor(() => {
        expect(verificationAPI.override).toHaveBeenCalledWith(
          'evt-test-100',
          'VERIFIED',
          'Verified with city traffic CCTV camera feeds.'
        );
      });
    });
  });

  describe('DuplicateClusterPanel', () => {
    const mockCluster = {
      id: 'cl-1',
      canonical_event_id: 'evt-test-100',
      similarity_score: 0.91,
      created_at: '2026-10-01T08:00:00Z',
      reports: [
        {
          id: 'rep-1',
          category: 'FLOOD',
          severity: 3,
          location_district: 'Bengaluru',
          location_state: 'Karnataka',
          description: 'Flooding near metro pillar 12',
          source_type: 'CITIZEN',
          created_at: '2026-10-01T07:45:00Z',
        },
        {
          id: 'rep-2',
          category: 'FLOOD',
          severity: 4,
          location_district: 'Bengaluru',
          location_state: 'Karnataka',
          description: 'Huge water buildup on MG Road',
          source_type: 'TWITTER',
          created_at: '2026-10-01T07:50:00Z',
        },
      ],
    };

    it('renders duplicate clusters and executes split operation', async () => {
      vi.mocked(verificationAPI.splitCluster).mockResolvedValueOnce({
        message: 'Successfully split reports',
        removed_count: 1,
      });

      render(
        <MemoryRouter>
          <DuplicateClusterPanel cluster={mockCluster as any} eventId="evt-test-100" />
        </MemoryRouter>
      );

      expect(screen.getByText('Duplicate Event Cluster')).toBeInTheDocument();
      expect(screen.getByText('Flooding near metro pillar 12')).toBeInTheDocument();

      const checkboxes = screen.getAllByRole('checkbox');
      // checkboxes[0] is select all, checkboxes[1] is rep-1
      fireEvent.click(checkboxes[1]);

      const splitBtn = screen.getByRole('button', { name: /Split Selected \(1\)/i });
      fireEvent.click(splitBtn);

      expect(screen.getByText('Confirm Decouple & Split Cluster')).toBeInTheDocument();
      const reasonInput = screen.getByPlaceholderText(/Operational reason for splitting cluster/i);
      fireEvent.change(reasonInput, { target: { value: 'Separate water accumulation event 2km upstream.' } });

      const confirmBtn = screen.getByRole('button', { name: 'Confirm Split' });
      fireEvent.click(confirmBtn);

      await waitFor(() => {
        expect(verificationAPI.splitCluster).toHaveBeenCalledWith(
          ['rep-1'],
          'Separate water accumulation event 2km upstream.'
        );
      });
    });

    it('executes merge operation with target event ID', async () => {
      vi.mocked(verificationAPI.mergeClusters).mockResolvedValueOnce({
        message: 'Merged successfully',
        primary_event_id: 'evt-target-500',
      });

      render(
        <MemoryRouter>
          <DuplicateClusterPanel cluster={mockCluster as any} eventId="evt-test-100" />
        </MemoryRouter>
      );

      const mergeModalBtn = screen.getByRole('button', { name: /Merge Clusters/i });
      fireEvent.click(mergeModalBtn);

      expect(screen.getByText('Merge Cluster Into Secondary Canonical Event')).toBeInTheDocument();

      const targetInput = screen.getByPlaceholderText(/Secondary event UUID/i);
      fireEvent.change(targetInput, { target: { value: 'evt-target-500' } });

      const reasonInput = screen.getByPlaceholderText(/Justification for merging events/i);
      fireEvent.change(reasonInput, { target: { value: 'Identical incident verified by ground teams.' } });

      const confirmMergeBtn = screen.getByRole('button', { name: 'Confirm Merge' });
      fireEvent.click(confirmMergeBtn);

      await waitFor(() => {
        expect(verificationAPI.mergeClusters).toHaveBeenCalledWith(
          'evt-test-100',
          'evt-target-500',
          'Identical incident verified by ground teams.'
        );
      });
    });
  });
});
