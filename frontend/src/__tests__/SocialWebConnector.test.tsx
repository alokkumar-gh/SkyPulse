import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { ConnectorManagement } from '../pages/admin/ConnectorManagement';
import { sourcesAPI, socialWebAPI } from '../utils/api';
import { useAuthStore } from '../store/authStore';

vi.mock('../utils/api', () => ({
  sourcesAPI: {
    list: vi.fn(),
    toggleActive: vi.fn(),
    createConnector: vi.fn(),
    updateConnector: vi.fn(),
  },
  socialWebAPI: {
    overview: vi.fn(),
    status: vi.fn(),
    sources: vi.fn(),
    testSource: vi.fn(),
  },
}));

describe('Social & Web Weather Intelligence Connector UI', () => {
  const mockSocialSources = [
    {
      provider_id: 'sw-rss-1',
      name: 'IMD Official Warnings RSS',
      source_type: 'RSS_FEED',
      status: 'HEALTHY',
      config: { feed_url: 'https://mausam.imd.gov.in/rss/alerts.xml' },
      metrics: {
        records_fetched: 85,
        records_accepted: 82,
        records_rejected: 3,
        duplicates: 12,
        last_successful_fetch: '2026-10-01T12:00:00Z',
        last_error: null,
        processing_latency_ms: 120.5,
      },
    },
    {
      provider_id: 'sw-api-2',
      name: 'Authorized Twitter/X Weather Stream',
      source_type: 'SOCIAL_API',
      status: 'NOT_CONFIGURED',
      config: { base_url: null, api_token: '***MASKED***' },
      metrics: {
        records_fetched: 0,
        records_accepted: 0,
        records_rejected: 0,
        duplicates: 0,
        last_successful_fetch: null,
        last_error: 'Missing base_url or credentials',
        processing_latency_ms: 0,
      },
    },
  ];

  beforeEach(() => {
    vi.clearAllMocks();
    useAuthStore.setState({
      user: {
        id: 'usr-admin-1',
        email: 'admin@skypulse.gov.in',
        name: 'System Admin',
        role: 'ADMIN',
        is_active: true,
      },
      token: 'admin-token',
      isAuthenticated: true,
      error: null,
    });
  });

  it('renders Social & Web sources table with metrics, duplicate count, and health', async () => {
    vi.mocked(sourcesAPI.list).mockResolvedValue([]);
    vi.mocked(socialWebAPI.sources).mockResolvedValue({
      total: 2,
      sources: mockSocialSources as any,
      timestamp: new Date().toISOString(),
    });

    render(
      <MemoryRouter>
        <ConnectorManagement />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('SOCIAL MEDIA & WEB HASHTAG INGESTION')).toBeInTheDocument();
      expect(screen.getByText('IMD Official Warnings RSS')).toBeInTheDocument();
      expect(screen.getByText('Authorized Twitter/X Weather Stream')).toBeInTheDocument();
    });

    // Check status badges
    expect(screen.getByText('HEALTHY')).toBeInTheDocument();
    expect(screen.getByText('NOT_CONFIGURED')).toBeInTheDocument();
    // Check duplicate count
    expect(screen.getByText('12')).toBeInTheDocument();
  });

  it('opens Smoke Test modal and executes live source validation', async () => {
    vi.mocked(sourcesAPI.list).mockResolvedValue([]);
    vi.mocked(socialWebAPI.sources).mockResolvedValue({
      total: 2,
      sources: mockSocialSources as any,
      timestamp: new Date().toISOString(),
    });
    vi.mocked(socialWebAPI.testSource).mockResolvedValueOnce({
      status: 'HEALTHY',
      source_type: 'RSS_FEED',
      tested_url: 'https://mausam.imd.gov.in/rss/alerts.xml',
      success: true,
      records_found: 5,
      sample_records: [{ text: 'Heavy rainfall alert for Mumbai #HeavyRain', primary_category: 'RAINFALL' }],
      latency_ms: 85.4,
      error_message: null,
      timestamp: new Date().toISOString(),
    });

    render(
      <MemoryRouter>
        <ConnectorManagement />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('IMD Official Warnings RSS')).toBeInTheDocument();
    });

    // Click smoke test button
    const testButtons = screen.getAllByRole('button', { name: /Smoke Test Source|Test/i });
    fireEvent.click(testButtons[0]);

    await waitFor(() => {
      expect(screen.getByText('Social & Web Source Live Smoke Test')).toBeInTheDocument();
    });

    const urlInput = screen.getByPlaceholderText(/e\.g\. https:\/\/mausam\.imd\.gov\.in/i);
    fireEvent.change(urlInput, { target: { value: 'https://mausam.imd.gov.in/rss/alerts.xml' } });

    const execBtn = screen.getByRole('button', { name: 'Execute Smoke Test' });
    fireEvent.click(execBtn);

    await waitFor(() => {
      expect(socialWebAPI.testSource).toHaveBeenCalledWith(
        expect.objectContaining({
          source_type: 'RSS_FEED',
          url: 'https://mausam.imd.gov.in/rss/alerts.xml',
        })
      );
      expect(screen.getByText(/LIVE SOURCE TEST = HEALTHY/i)).toBeInTheDocument();
      expect(screen.getByText(/Latency: 85.4ms/i)).toBeInTheDocument();
    });
  });
});
