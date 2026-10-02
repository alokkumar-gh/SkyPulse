/**
 * Sidebar — Phase 7
 * Role-dependent navigation sidebar.
 * Collapses to icons on tablet; hidden on mobile.
 */
import React, { useState } from 'react';
import { NavLink, useLocation } from 'react-router-dom';
import {
  LayoutDashboard,
  Map,
  Zap,
  BarChart2,
  GitBranch,
  Bell,
  Database,
  FileText,
  Settings,
  ChevronLeft,
  ChevronRight,
  Shield,
  Users,
  Activity,
  ClipboardList,
} from 'lucide-react';
import { useAuthStore, canAnalyst, canAdmin } from '../../store/authStore';

interface NavItem {
  to: string;
  icon: React.ReactNode;
  label: string;
  badge?: number;
  requireAnalyst?: boolean;
  requireAdmin?: boolean;
}

const NAV_ITEMS: NavItem[] = [
  { to: '/', icon: <LayoutDashboard size={18} />, label: 'Dashboard' },
  { to: '/map', icon: <Map size={18} />, label: 'Live Map' },
  { to: '/events', icon: <Zap size={18} />, label: 'Events' },
  { to: '/analytics', icon: <BarChart2 size={18} />, label: 'Analytics' },
  { to: '/alerts', icon: <Bell size={18} />, label: 'Alerts' },
  { to: '/reports', icon: <FileText size={18} />, label: 'Reports' },
  { to: '/sources', icon: <Database size={18} />, label: 'Sources' },
  // Analyst+
  { to: '/dweg', icon: <GitBranch size={18} />, label: 'Evidence Graph', requireAnalyst: true },
  { to: '/analyst/queue', icon: <Shield size={18} />, label: 'Verify Queue', requireAnalyst: true },
  // Admin+
  { to: '/admin', icon: <Settings size={18} />, label: 'Admin', requireAdmin: true },
  { to: '/admin/health', icon: <Activity size={18} />, label: 'System Health', requireAdmin: true },
  { to: '/admin/connectors', icon: <Database size={18} />, label: 'Connectors', requireAdmin: true },
  { to: '/admin/users', icon: <Users size={18} />, label: 'Users', requireAdmin: true },
  { to: '/admin/audit', icon: <ClipboardList size={18} />, label: 'Audit Log', requireAdmin: true },
  { to: '/admin/flagged-reports', icon: <Settings size={18} />, label: 'Flagged Reports', requireAdmin: true },
];

export function Sidebar() {
  const { user } = useAuthStore();
  const location = useLocation();
  const [collapsed, setCollapsed] = useState(false);

  const role = user?.role;
  const visibleItems = NAV_ITEMS.filter((item) => {
    if (item.requireAdmin && !canAdmin(role)) return false;
    if (item.requireAnalyst && !canAnalyst(role)) return false;
    return true;
  });

  return (
    <nav
      id="sidebar"
      aria-label="Primary navigation"
      style={{
        position: 'fixed',
        top: 'var(--topbar-height)',
        left: 0,
        bottom: 0,
        width: collapsed ? 52 : 'var(--sidebar-width)',
        backgroundColor: 'var(--bg-surface)',
        borderRight: '1px solid var(--bg-border)',
        display: 'flex',
        flexDirection: 'column',
        transition: 'width var(--transition-normal)',
        overflow: 'hidden',
        zIndex: 90,
      }}
    >
      {/* Nav items */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '0.5rem 0', paddingTop: '0.75rem' }}>
        {visibleItems.map((item) => {
          const isActive =
            item.to === '/'
              ? location.pathname === '/'
              : location.pathname.startsWith(item.to);

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
  );
}
