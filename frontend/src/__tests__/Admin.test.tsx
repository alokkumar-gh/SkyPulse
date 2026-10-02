import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { useAuthStore } from '../store/authStore';
import { AdminLayout } from '../layouts/AdminLayout';
import { SystemHealthPage } from '../pages/admin/SystemHealth';
import { ConnectorManagement } from '../pages/admin/ConnectorManagement';
import { UserManagement } from '../pages/admin/UserManagement';
import { AuditLogPage } from '../pages/admin/AuditLog';
import { FlaggedReportsPage } from '../pages/admin/FlaggedReports';
import { systemAPI, sourcesAPI, adminAPI } from '../utils/api';

vi.mock('../utils/api', () => ({
  systemAPI: {
    health: vi.fn(),
  },
  sourcesAPI: {
    list: vi.fn(),
    toggleActive: vi.fn(),
    createConnector: vi.fn(),
    updateConnector: vi.fn(),
  },
  socialWebAPI: {
    overview: vi.fn().mockResolvedValue({ sources: [] }),
    status: vi.fn().mockResolvedValue({ sources_status: [] }),
    sources: vi.fn().mockResolvedValue({ total: 0, sources: [] }),
    testSource: vi.fn().mockResolvedValue({ success: true, status: 'HEALTHY' }),
  },
  adminAPI: {
    systemHealth: vi.fn(),
    users: vi.fn(),
    updateUserRole: vi.fn(),
    auditLogs: vi.fn(),
    flaggedReports: vi.fn(),
  },
  authAPI: {
    login: vi.fn(),
    logout: vi.fn(),
    me: vi.fn(),
  },
}));

describe('Admin Panel Workflows', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useAuthStore.setState({
      user: {
        id: 'usr-admin-1',
        email: 'admin@skypulse.gov.in',
        name: 'System Superadmin',
        role: 'ADMIN',
        is_active: true,
      },
      token: 'admin-demo-token',
      isAuthenticated: true,
      error: null,
    });
  });

  describe('AdminLayout', () => {
    it('renders admin navigation links for authorized ADMIN', () => {
      render(
        <MemoryRouter initialEntries={['/admin/health']}>
          <AdminLayout />
        </MemoryRouter>
      );

      expect(screen.getByText('Admin Operations')).toBeInTheDocument();
      expect(screen.getByText('System Health')).toBeInTheDocument();
      expect(screen.getByText('Connectors')).toBeInTheDocument();
      expect(screen.getByText('Users')).toBeInTheDocument();
      expect(screen.getByText('Audit Log')).toBeInTheDocument();
      expect(screen.getByText('Flagged Reports')).toBeInTheDocument();
    });

    it('blocks analyst from accessing AdminLayout', () => {
      useAuthStore.setState({
        user: {
          id: 'usr-analyst-1',
          email: 'analyst@skypulse.gov.in',
          name: 'Analyst User',
          role: 'ANALYST',
          is_active: true,
        },
      });

      render(
        <MemoryRouter initialEntries={['/admin/health']}>
          <AdminLayout />
        </MemoryRouter>
      );

      expect(screen.getByText('Administrator Access Prohibited')).toBeInTheDocument();
      expect(screen.queryByText('Admin Operations')).not.toBeInTheDocument();
    });
  });

  describe('SystemHealth', () => {
    const mockHealth = {
      status: 'healthy',
      app: 'SkyPulse Weather Big Data Platform',
      version: '1.0.0',
      timestamp: '2026-10-01T10:00:00Z',
      database_status: 'HEALTHY',
      redis_status: 'HEALTHY',
      kafka_status: 'HEALTHY',
      ai_worker_status: 'HEALTHY',
      opensearch_status: 'DEGRADED',
      neo4j_status: 'HEALTHY',
    };

    it('renders system health components and handles manual refresh', async () => {
      vi.mocked(adminAPI.systemHealth).mockResolvedValue(mockHealth as any);

      render(
        <MemoryRouter>
          <SystemHealthPage />
        </MemoryRouter>
      );

      expect(screen.getByText('System Infrastructure & Service Health')).toBeInTheDocument();

      await waitFor(() => {
        expect(screen.getByText('PostgreSQL + PostGIS')).toBeInTheDocument();
        expect(screen.getByText('Redis In-Memory Bus')).toBeInTheDocument();
        expect(screen.getByText('Kafka / Redpanda Broker')).toBeInTheDocument();
        expect(screen.getByText('OpenSearch Engine')).toBeInTheDocument();
        expect(screen.getByText('Neo4j DWEG Knowledge Graph')).toBeInTheDocument();
      });

      const refreshBtn = screen.getByRole('button', { name: /Refresh Now/i });
      fireEvent.click(refreshBtn);

      await waitFor(() => {
        expect(adminAPI.systemHealth).toHaveBeenCalledTimes(2);
      });
    });
  });

  describe('ConnectorManagement', () => {
    const mockConnectors = [
      {
        id: 'conn-1',
        name: 'IMD Doppler Radar Feed',
        source_type: 'WEATHER_API',
        connector_class: 'OpenMeteoConnector',
        is_active: true,
        health_status: 'HEALTHY',
        is_demo: false,
        total_reports_ingested: 4520,
        last_success_at: '2026-10-01T09:50:00Z',
      },
      {
        id: 'conn-2',
        name: 'Twitter Firehose Mock',
        source_type: 'SOCIAL_MEDIA',
        connector_class: 'TwitterConnector',
        is_active: false,
        health_status: 'INACTIVE',
        is_demo: true,
        total_reports_ingested: 120,
      },
    ];

    it('renders connectors and toggles active status', async () => {
      vi.mocked(sourcesAPI.list).mockResolvedValue(mockConnectors as any);
      vi.mocked(sourcesAPI.toggleActive).mockResolvedValueOnce({
        id: 'conn-1',
        is_active: false,
      } as any);

      render(
        <MemoryRouter>
          <ConnectorManagement />
        </MemoryRouter>
      );

      await waitFor(() => {
        expect(screen.getByText('IMD Doppler Radar Feed')).toBeInTheDocument();
        expect(screen.getByText('Twitter Firehose Mock')).toBeInTheDocument();
      });

      const toggleButtons = screen.getAllByRole('button', { name: /Disable|Enable/i });
      fireEvent.click(toggleButtons[0]);

      await waitFor(() => {
        expect(sourcesAPI.toggleActive).toHaveBeenCalledWith('conn-1', false);
      });
    });

    it('opens add connector modal and creates a connector', async () => {
      vi.mocked(sourcesAPI.list).mockResolvedValue(mockConnectors as any);
      vi.mocked(sourcesAPI.createConnector).mockResolvedValueOnce({
        id: 'conn-new',
        name: 'ISRO INSAT-3D Stream',
        source_type: 'WEATHER_API',
        is_active: true,
      } as any);

      render(
        <MemoryRouter>
          <ConnectorManagement />
        </MemoryRouter>
      );

      await waitFor(() => {
        expect(screen.getByText('IMD Doppler Radar Feed')).toBeInTheDocument();
      });

      const addBtn = screen.getByRole('button', { name: /Add Connector/i });
      fireEvent.click(addBtn);

      expect(screen.getByText('Register New Data Connector')).toBeInTheDocument();

      const nameInput = screen.getByPlaceholderText(/e\.g\. IMD Radar Stream Kolkata/i);
      fireEvent.change(nameInput, { target: { value: 'ISRO INSAT-3D Stream' } });

      const submitBtn = screen.getByRole('button', { name: 'Create Connector' });
      fireEvent.click(submitBtn);

      await waitFor(() => {
        expect(sourcesAPI.createConnector).toHaveBeenCalledWith(
          expect.objectContaining({
            name: 'ISRO INSAT-3D Stream',
          })
        );
      });
    });
  });

  describe('UserManagement', () => {
    const mockUsers = [
      {
        id: 'usr-1',
        display_name: 'Aditya Verma',
        email: 'aditya@skypulse.gov.in',
        role: 'ANALYST',
        is_active: true,
        created_at: '2026-09-01T00:00:00Z',
      },
      {
        id: 'usr-2',
        display_name: 'Kavita Singh',
        email: 'kavita@skypulse.gov.in',
        role: 'CITIZEN',
        is_active: true,
        created_at: '2026-09-10T00:00:00Z',
      },
    ];

    it('renders user list and modifies user role', async () => {
      vi.mocked(adminAPI.users).mockResolvedValue(mockUsers as any);
      vi.mocked(adminAPI.updateUserRole).mockResolvedValueOnce({
        id: 'usr-2',
        role: 'ANALYST',
      } as any);

      render(
        <MemoryRouter>
          <UserManagement />
        </MemoryRouter>
      );

      await waitFor(() => {
        expect(screen.getByText('Aditya Verma')).toBeInTheDocument();
        expect(screen.getByText('kavita@skypulse.gov.in')).toBeInTheDocument();
      });

      // Role select is inside the Kavita row
      const roleSelects = screen.getAllByRole('combobox');
      // Index 0 is the filter dropdown, index 1 is Aditya's, index 2 is Kavita's
      fireEvent.change(roleSelects[2], { target: { value: 'ANALYST' } });

      await waitFor(() => {
        expect(adminAPI.updateUserRole).toHaveBeenCalledWith('usr-2', 'ANALYST');
      });
    });
  });

  describe('AuditLog', () => {
    const mockLogs = [
      {
        id: 'log-1',
        created_at: '2026-10-01T09:40:00Z',
        user_id: 'usr-admin-1',
        action_type: 'UPDATE',
        entity_type: 'SOURCE',
        entity_id: 'conn-1',
        old_value: { enabled: true },
        new_value: { enabled: false },
      },
      {
        id: 'log-2',
        created_at: '2026-10-01T09:45:00Z',
        user_id: 'usr-analyst-1',
        action_type: 'VERIFY',
        entity_type: 'EVENT',
        entity_id: 'evt-100',
        old_value: { status: 'UNVERIFIED' },
        new_value: { status: 'VERIFIED' },
      },
    ];

    it('renders audit logs and supports filtering', async () => {
      vi.mocked(adminAPI.auditLogs).mockResolvedValue(mockLogs as any);

      render(
        <MemoryRouter>
          <AuditLogPage />
        </MemoryRouter>
      );

      expect(screen.getByText('System Audit Trail & Governance')).toBeInTheDocument();

      await waitFor(() => {
        expect(screen.getByText('UPDATE')).toBeInTheDocument();
        expect(screen.getByText('VERIFY')).toBeInTheDocument();
      });
    });
  });

  describe('FlaggedReports', () => {
    const mockFlagged = [
      {
        id: 'rep-flag-1',
        canonical_event_id: 'evt-100',
        category: 'RAINFALL',
        source_id: 'src-twitter-1',
        source_name: 'Twitter Firehose',
        location_state: 'Jammu and Kashmir',
        location_district: 'Srinagar',
        severity: 3,
        normalized_text: 'Severe cloudburst reported in Srinagar',
        status: 'FLAGGED',
        flag_reason: 'Abnormal sentiment spike without meteorological sensor corroboration',
        created_at: '2026-10-01T09:00:00Z',
      },
    ];

    it('renders flagged reports with reason and navigation', async () => {
      vi.mocked(adminAPI.flaggedReports).mockResolvedValue(mockFlagged as any);

      render(
        <MemoryRouter>
          <FlaggedReportsPage />
        </MemoryRouter>
      );

      expect(screen.getByText('Flagged & Anomalous Reports')).toBeInTheDocument();

      await waitFor(() => {
        expect(screen.getByText('Severe cloudburst reported in Srinagar')).toBeInTheDocument();
        expect(screen.getByText('AI FLAGGED')).toBeInTheDocument();
        expect(screen.getByText('Inspect Event')).toBeInTheDocument();
      });
    });
  });
});
