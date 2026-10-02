/**
 * Auth Store — Phase 7
 * Manages user session, authentication state, JWT token.
 */
import { create } from 'zustand';
import { authAPI, APIError } from '../utils/api';
import type { UserRole } from '../types';

interface AuthUser {
  id: string;
  email: string;
  display_name: string;
  role: UserRole;
}

interface AuthState {
  user: AuthUser | null;
  token: string | null;
  isLoading: boolean;
  loading: boolean;
  isAuthenticated: boolean;
  error: string | null;

  login: (email: string, password: string) => Promise<boolean>;
  loginAsDemo: (role: UserRole) => void;
  logout: () => void;
  loadFromStorage: () => Promise<void>;
  clearError: () => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  token: null,
  isLoading: false,
  loading: false,
  isAuthenticated: false,
  error: null,

  login: async (email, password) => {
    set({ isLoading: true, loading: true, error: null });
    try {
      const data = await authAPI.login(email, password);
      sessionStorage.setItem('skypulse_token', data.access_token);
      set({
        token: data.access_token,
        user: {
          id: data.user.id,
          email: data.user.email,
          display_name: data.user.display_name,
          role: data.user.role as UserRole,
        },
        isAuthenticated: true,
        isLoading: false,
        loading: false,
      });
      return true;
    } catch (err) {
      const message = err instanceof APIError ? err.message : 'Login failed';
      set({ isLoading: false, loading: false, error: message });
      return false;
    }
  },

  loginAsDemo: (role: UserRole) => {
    const demoUser: AuthUser = {
      id: `demo-${role.toLowerCase()}-01`,
      email: `${role.toLowerCase()}@skypulse.gov.in`,
      display_name: `Demo ${role.charAt(0) + role.slice(1).toLowerCase()}`,
      role,
    };
    sessionStorage.setItem('skypulse_token', 'demo-jwt-token-active');
    set({
      token: 'demo-jwt-token-active',
      user: demoUser,
      isAuthenticated: true,
      isLoading: false,
      loading: false,
      error: null,
    });
  },

  logout: () => {
    authAPI.logout().catch(() => {});
    sessionStorage.removeItem('skypulse_token');
    set({ user: null, token: null, isAuthenticated: false, error: null });
  },

  loadFromStorage: async () => {
    const token = sessionStorage.getItem('skypulse_token');
    if (!token) return;
    set({ isLoading: true });
    try {
      const user = await authAPI.me();
      set({
        token,
        user: {
          id: user.id,
          email: user.email,
          display_name: user.display_name,
          role: user.role as UserRole,
        },
        isAuthenticated: true,
        isLoading: false,
      });
    } catch {
      sessionStorage.removeItem('skypulse_token');
      set({ isLoading: false, user: null, token: null, isAuthenticated: false });
    }
  },

  clearError: () => set({ error: null }),
}));

// Role-based permission helpers
export function hasRole(userRole: UserRole | undefined, minimumRole: UserRole): boolean {
  const ROLE_ORDER: UserRole[] = ['PUBLIC', 'CITIZEN', 'ANALYST', 'GOVERNMENT', 'ADMIN'];
  const userIndex = ROLE_ORDER.indexOf(userRole ?? 'PUBLIC');
  const minIndex = ROLE_ORDER.indexOf(minimumRole);
  return userIndex >= minIndex;
}

export function canAnalyst(role: UserRole | undefined): boolean {
  return hasRole(role, 'ANALYST');
}

export function canAdmin(role: UserRole | undefined): boolean {
  return hasRole(role, 'ADMIN');
}
