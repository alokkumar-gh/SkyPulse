/**
 * AnalystLayout — Phase 9
 * Layout shell dedicated to operational analyst triage workflows.
 * Protects routes requiring ANALYST or ADMIN role.
 * Shows analyst-specific navigation sidebar while preserving Topbar and design system.
 */
import React, { useState } from 'react';
import { NavLink, Outlet, useLocation, Navigate } from 'react-router-dom';
import { Topbar } from '../components/layout/Topbar';
import { OfflineBanner } from '../components/ui/States';
import { useWebSocket } from '../hooks/useWebSocket';
import { useAuthStore, canAnalyst } from '../store/authStore';
import {
  ShieldCheck,
  Zap,
  GitMerge,
  Bell,
  ChevronLeft,
  ChevronRight,
  ArrowLeft,
  FileQuestion,
} from 'lucide-react';

interface NavItem {
  to: string;
  icon: React.ReactNode;
  label: string;
}

const ANALYST_NAV_ITEMS: NavItem[] = [
  { to: '/analyst/queue', icon: <ShieldCheck size={18} />, label: 'Verification Queue' },
  { to: '/analyst/events', icon: <Zap size={18} />, label: 'Events Triage' },
  { to: '/analyst/clusters', icon: <GitMerge size={18} />, label: 'Duplicate Clusters' },
  { to: '/analyst/alerts', icon: <Bell size={18} />, label: 'Priority Alerts' },
];

export const AnalystLayout: React.FC = () => {
  const { user, isAuthenticated } = useAuthStore();
  const { connectionState } = useWebSocket();
  const location = useLocation();
  const [collapsed, setCollapsed] = useState(false);

  // RBAC enforcement: ANALYST, ADMIN, GOVERNMENT can access analyst triage
  if (!isAuthenticated && !sessionStorage.getItem('skypulse_token')) {
    return <Navigate to="/login" replace state={{ from: location }} />;
  }

  if (!canAnalyst(user?.role)) {
    return (
      <div
        style={{
          minHeight: '100vh',
          backgroundColor: 'var(--bg-primary)',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          padding: '2rem',
          color: 'var(--text-primary)',
        }}
      >
        <FileQuestion size={48} color="var(--severity-4)" style={{ marginBottom: '1rem' }} />
        <h2 style={{ fontSize: 'var(--text-xl)', fontWeight: 700, margin: '0 0 0.5rem 0' }}>
          Analyst Authorization Required
        </h2>
        <p style={{ color: 'var(--text-secondary)', fontSize: 'var(--text-sm)', maxWidth: '420px', textAlign: 'center' }}>
          Your current account role (<strong>{user?.role || 'PUBLIC'}</strong>) does not have permission
          to access the operational weather analyst triage interface.
        </p>
        <NavLink
          to="/"
          style={{
            marginTop: '1.5rem',
            padding: '0.5rem 1rem',
            backgroundColor: 'var(--brand-blue)',
            color: '#fff',
            borderRadius: 'var(--radius-md)',
            textDecoration: 'none',
            fontSize: 'var(--text-sm)',
            fontWeight: 600,
          }}
        >
          Return to Dashboard
        </NavLink>
      </div>
    );
  }

  const isOffline = connectionState === 'DISCONNECTED' || connectionState === 'FAILED';

  return (
    <div style={{ minHeight: '100vh', backgroundColor: 'var(--bg-primary)' }}>
      <Topbar />
      {isOffline && <OfflineBanner />}

      {/* Analyst Dedicated Sidebar */}
      <nav
        id="analyst-sidebar"
        aria-label="Analyst triage navigation"
        style={{
          position: 'fixed',
          top: 'var(--topbar-height)',
          left: 0,
          bottom: 0,
          width: collapsed ? 56 : 'var(--sidebar-width)',
          backgroundColor: 'var(--bg-surface)',
          borderRight: '1px solid var(--bg-border)',
          display: 'flex',
          flexDirection: 'column',
          transition: 'width var(--transition-normal)',
          overflow: 'hidden',
          zIndex: 90,
        }}
      >
        {/* Back to main portal link */}
        <div style={{ padding: '0.75rem 0.75rem 0.5rem 0.75rem', borderBottom: '1px solid var(--bg-border)' }}>
          <NavLink
            to="/"
            title="Return to National Portal"
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '0.5rem',
              fontSize: 'var(--text-xs)',
              color: 'var(--text-muted)',
              textDecoration: 'none',
              padding: '0.4rem 0.5rem',
              borderRadius: 'var(--radius-sm)',
              transition: 'color var(--transition-fast)',
            }}
          >
            <ArrowLeft size={14} />
            {!collapsed && <span>National Portal</span>}
          </NavLink>
        </div>

        {/* Section header */}
        {!collapsed && (
          <div
            style={{
              padding: '0.75rem 1rem 0.25rem 1rem',
              fontSize: '11px',
              fontWeight: 700,
              textTransform: 'uppercase',
              letterSpacing: '0.05em',
              color: 'var(--brand-blue)',
            }}
          >
            Analyst Console
          </div>
        )}

        {/* Nav items */}
        <div style={{ flex: 1, overflowY: 'auto', padding: '0.5rem 0' }}>
          {ANALYST_NAV_ITEMS.map((item) => {
            const isActive = location.pathname === item.to || location.pathname.startsWith(item.to + '/');

            return (
              <NavLink
                key={item.to}
                to={item.to}
                title={collapsed ? item.label : undefined}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.75rem',
                  padding: collapsed ? '0.625rem 0' : '0.625rem 1rem',
                  justifyContent: collapsed ? 'center' : 'flex-start',
                  marginBottom: 2,
                  fontSize: 'var(--text-sm)',
                  fontWeight: isActive ? 600 : 400,
                  color: isActive ? 'var(--brand-blue)' : 'var(--text-secondary)',
                  backgroundColor: isActive ? 'var(--brand-blue-dim)' : 'transparent',
                  borderLeft: isActive ? '2px solid var(--brand-blue)' : '2px solid transparent',
                  borderRadius: collapsed ? 0 : '0 var(--radius-sm) var(--radius-sm) 0',
                  textDecoration: 'none',
                  transition: 'all var(--transition-fast)',
                  whiteSpace: 'nowrap',
                  overflow: 'hidden',
                }}
                aria-current={isActive ? 'page' : undefined}
              >
                <span style={{ flexShrink: 0 }}>{item.icon}</span>
                {!collapsed && <span>{item.label}</span>}
              </NavLink>
            );
          })}
        </div>

        {/* Collapse toggle */}
        <button
          onClick={() => setCollapsed((v) => !v)}
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: '0.75rem',
            borderTop: '1px solid var(--bg-border)',
            color: 'var(--text-muted)',
            cursor: 'pointer',
            fontSize: 'var(--text-xs)',
            gap: '0.4rem',
            background: 'transparent',
            border: 'none',
            borderTopColor: 'var(--bg-border)',
            borderTopStyle: 'solid',
            borderTopWidth: 1,
            width: '100%',
          }}
          aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
        >
          {collapsed ? <ChevronRight size={16} /> : (
            <>
              <ChevronLeft size={16} />
              <span>Collapse</span>
            </>
          )}
        </button>
      </nav>

      {/* Main Content */}
      <main
        id="analyst-main-content"
        style={{
          marginLeft: collapsed ? 56 : 'var(--sidebar-width)',
          marginTop: 'var(--topbar-height)',
          minHeight: 'calc(100vh - var(--topbar-height))',
          overflow: 'auto',
          transition: 'margin-left var(--transition-normal)',
          backgroundColor: 'var(--bg-primary)',
        }}
        aria-label="Analyst operations"
      >
        <Outlet />
      </main>
    </div>
  );
};
