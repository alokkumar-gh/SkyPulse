import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { useAuthStore, hasRole, canAnalyst, canAdmin } from '../store/authStore';
import { Sidebar } from '../components/layout/Sidebar';
import { authAPI } from '../utils/api';

vi.mock('../utils/api', () => ({
  authAPI: {
    login: vi.fn(),
    logout: vi.fn().mockResolvedValue({}),
    me: vi.fn(),
  },
}));

describe('Auth & RBAC Evaluation', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    sessionStorage.clear();
    useAuthStore.setState({
      user: null,
      token: null,
      isAuthenticated: false,
      error: null,
    });
  });

  describe('Role hierarchy functions', () => {
    it('evaluates hasRole properly according to role hierarchy', () => {
      // Hierarchy: PUBLIC < CITIZEN < ANALYST < GOVERNMENT < ADMIN
      expect(hasRole('PUBLIC', 'PUBLIC')).toBe(true);
      expect(hasRole('PUBLIC', 'CITIZEN')).toBe(false);
      expect(hasRole('PUBLIC', 'ANALYST')).toBe(false);

      expect(hasRole('CITIZEN', 'CITIZEN')).toBe(true);
      expect(hasRole('CITIZEN', 'ANALYST')).toBe(false);

      expect(hasRole('ANALYST', 'CITIZEN')).toBe(true);
      expect(hasRole('ANALYST', 'ANALYST')).toBe(true);
      expect(hasRole('ANALYST', 'ADMIN')).toBe(false);

      expect(hasRole('ADMIN', 'PUBLIC')).toBe(true);
      expect(hasRole('ADMIN', 'ANALYST')).toBe(true);
      expect(hasRole('ADMIN', 'ADMIN')).toBe(true);
    });

    it('evaluates canAnalyst and canAdmin helpers', () => {
      expect(canAnalyst('PUBLIC')).toBe(false);
      expect(canAnalyst('CITIZEN')).toBe(false);
      expect(canAnalyst('ANALYST')).toBe(true);
      expect(canAnalyst('GOVERNMENT')).toBe(true);
      expect(canAnalyst('ADMIN')).toBe(true);

      expect(canAdmin('PUBLIC')).toBe(false);
      expect(canAdmin('ANALYST')).toBe(false);
      expect(canAdmin('GOVERNMENT')).toBe(false);
      expect(canAdmin('ADMIN')).toBe(true);
    });
  });

  describe('Auth Store State Transitions', () => {
    it('sets demo user session on loginAsDemo', () => {
      useAuthStore.getState().loginAsDemo('ANALYST');

      const state = useAuthStore.getState();
      expect(state.isAuthenticated).toBe(true);
      expect(state.user?.role).toBe('ANALYST');
      expect(state.user?.email).toBe('analyst@skypulse.gov.in');
      expect(sessionStorage.getItem('skypulse_token')).toBe('demo-jwt-token-active');
    });

    it('clears session and removes token on logout', () => {
      useAuthStore.getState().loginAsDemo('ADMIN');
      expect(useAuthStore.getState().isAuthenticated).toBe(true);

      useAuthStore.getState().logout();

      const state = useAuthStore.getState();
      expect(state.isAuthenticated).toBe(false);
      expect(state.user).toBeNull();
      expect(state.token).toBeNull();
      expect(sessionStorage.getItem('skypulse_token')).toBeNull();
    });

    it('authenticates successfully via authAPI.login', async () => {
      (authAPI.login as any).mockResolvedValue({
        access_token: 'jwt-xyz-123',
        user: {
          id: 'user-001',
          email: 'analyst1@skypulse.gov.in',
          display_name: 'Lead Analyst',
          role: 'ANALYST',
        },
      });

      const success = await useAuthStore.getState().login('analyst1@skypulse.gov.in', 'password123');
      expect(success).toBe(true);

      const state = useAuthStore.getState();
      expect(state.isAuthenticated).toBe(true);
      expect(state.token).toBe('jwt-xyz-123');
      expect(state.user?.email).toBe('analyst1@skypulse.gov.in');
      expect(sessionStorage.getItem('skypulse_token')).toBe('jwt-xyz-123');
    });
  });

  describe('Role-Based Sidebar Navigation Filtering', () => {
    it('hides Evidence Graph, Verify Queue, and Admin from CITIZEN role', () => {
      useAuthStore.setState({
        user: { id: 'cit-1', email: 'cit@skypulse.in', display_name: 'Citizen', role: 'CITIZEN' },
        isAuthenticated: true,
      });

      render(
        <MemoryRouter initialEntries={['/']}>
          <Sidebar />
        </MemoryRouter>
      );

      // Common items visible
      expect(screen.getByText('Dashboard')).toBeInTheDocument();
      expect(screen.getByText('Live Map')).toBeInTheDocument();
      expect(screen.getByText('Events')).toBeInTheDocument();

      // Analyst & Admin items hidden
      expect(screen.queryByText('Evidence Graph')).not.toBeInTheDocument();
      expect(screen.queryByText('Verify Queue')).not.toBeInTheDocument();
      expect(screen.queryByText('Admin')).not.toBeInTheDocument();
    });

    it('shows Evidence Graph and Verify Queue for ANALYST, but hides Admin', () => {
      useAuthStore.setState({
        user: { id: 'an-1', email: 'analyst@skypulse.in', display_name: 'Analyst', role: 'ANALYST' },
        isAuthenticated: true,
      });

      render(
        <MemoryRouter initialEntries={['/']}>
          <Sidebar />
        </MemoryRouter>
      );

      expect(screen.getByText('Evidence Graph')).toBeInTheDocument();
      expect(screen.getByText('Verify Queue')).toBeInTheDocument();
      expect(screen.queryByText('Admin')).not.toBeInTheDocument();
    });

    it('shows all links including Admin, Users, Audit Log for ADMIN', () => {
      useAuthStore.setState({
        user: { id: 'adm-1', email: 'admin@skypulse.in', display_name: 'Administrator', role: 'ADMIN' },
        isAuthenticated: true,
      });

      render(
        <MemoryRouter initialEntries={['/']}>
          <Sidebar />
        </MemoryRouter>
      );

      expect(screen.getByText('Evidence Graph')).toBeInTheDocument();
      expect(screen.getByText('Verify Queue')).toBeInTheDocument();
      expect(screen.getByText('Admin')).toBeInTheDocument();
      expect(screen.getByText('Audit Log')).toBeInTheDocument();
      expect(screen.getByText('System Health')).toBeInTheDocument();
    });
  });
});
