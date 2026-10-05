/**
 * SkyPulse Navigation Sidebar — Redesign
 * "Intelligence Operations" vertical navigation.
 *
 * Design:
 * - Warm-dark surface with editorial typography
 * - Active state: thin teal left accent + subtle teal fill
 * - Section labels: monospace, restrained
 * - Collapsible to 48px icon rail
 * - Quiet by design — never competes with content
 */
import React, { useState } from 'react';
import { NavLink, useLocation } from 'react-router-dom';
import {
  LayoutDashboard, Map, Zap, BarChart2, GitBranch,
  Bell, Database, FileText, Shield, Users, Activity,
  ClipboardList, Settings, ChevronLeft, ChevronRight,
  Radio, Layers,
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

interface NavSection {
  id: string;
  label: string;
  items: NavItem[];
}

const NAV_SECTIONS: NavSection[] = [
  {
    id: 'core',
    label: 'Command',
    items: [
      { to: '/',          icon: <LayoutDashboard size={15} />, label: 'Dashboard' },
      { to: '/map',       icon: <Map size={15} />,             label: 'Live Map' },
      { to: '/events',    icon: <Zap size={15} />,             label: 'Events' },
      { to: '/alerts',    icon: <Bell size={15} />,            label: 'Alerts' },
    ],
  },
  {
    id: 'intelligence',
    label: 'Intelligence',
    items: [
      { to: '/analytics',    icon: <BarChart2 size={15} />,  label: 'Analytics' },
      { to: '/sources',      icon: <Database size={15} />,   label: 'Sources' },
      { to: '/reports',      icon: <FileText size={15} />,   label: 'Reports' },
      { to: '/submit',       icon: <Layers size={15} />,     label: 'Submit Report' },
      {
        to: '/dweg',
        icon: <GitBranch size={15} />,
        label: 'Evidence Graph',
        requireAnalyst: true,
      },
      {
        to: '/analyst/queue',
        icon: <Shield size={15} />,
        label: 'Verify Queue',
        requireAnalyst: true,
      },
    ],
  },
  {
    id: 'admin',
    label: 'Admin',
    items: [
      { to: '/admin/health',          icon: <Activity size={15} />,      label: 'System Health',   requireAdmin: true },
      { to: '/admin/connectors',      icon: <Radio size={15} />,         label: 'Connectors',      requireAdmin: true },
      { to: '/admin/users',           icon: <Users size={15} />,         label: 'Users',           requireAdmin: true },
      { to: '/admin/audit',           icon: <ClipboardList size={15} />, label: 'Audit Log',       requireAdmin: true },
      { to: '/admin/flagged-reports', icon: <Settings size={15} />,      label: 'Flagged Reports', requireAdmin: true },
    ],
  },
];

export function Sidebar() {
  const { user } = useAuthStore();
  const location = useLocation();
  const [collapsed, setCollapsed] = useState(() => typeof window !== 'undefined' && window.innerWidth < 1024);
  const role = user?.role;

  React.useEffect(() => {
    const handleResize = () => {
      if (window.innerWidth < 1024) {
        setCollapsed(true);
      }
    };
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  const isVisible = (item: NavItem) => {
    if (item.requireAdmin && !canAdmin(role)) return false;
    if (item.requireAnalyst && !canAnalyst(role)) return false;
    return true;
  };

  const isActive = (to: string) =>
    to === '/' ? location.pathname === '/' : location.pathname.startsWith(to);

  return (
    <nav
      id="sidebar"
      aria-label="Primary navigation"
      style={{
        position: 'relative',
        width: collapsed ? 'var(--sidebar-collapsed)' : 'var(--sidebar-width)',
        backgroundColor: 'var(--bg-surface)',
        borderRight: '1px solid var(--border-hairline)',
        display: 'flex',
        flexDirection: 'column',
        transition: 'width 0.2s var(--ease-out-expo)',
        overflow: 'hidden',
        zIndex: 90,
        flexShrink: 0,
        height: '100%',
      }}
    >
      {/* Nav sections */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '0.75rem 0' }} className="scroll-area">
        {NAV_SECTIONS.map((section) => {
          const visibleItems = section.items.filter(isVisible);
          if (visibleItems.length === 0) return null;

          return (
            <div key={section.id} style={{ marginBottom: '0.125rem' }}>
              {/* Section label */}
              {!collapsed && (
                <div style={{
                  padding: '0.75rem 1rem 0.3rem',
                  fontFamily: 'var(--font-mono)',
                  fontSize: 'var(--text-2xs)',
                  fontWeight: 500,
                  color: 'var(--text-ghost)',
                  letterSpacing: '0.14em',
                  textTransform: 'uppercase',
                }}>
                  {section.label}
                </div>
              )}

              {/* Nav items */}
              {visibleItems.map((item) => {
                const active = isActive(item.to);
                return (
                  <NavLink
                    key={item.to}
                    to={item.to}
                    title={collapsed ? item.label : undefined}
                    aria-current={active ? 'page' : undefined}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '0.55rem',
                      padding: collapsed ? '0.6rem 0' : '0.45rem 1rem',
                      justifyContent: collapsed ? 'center' : 'flex-start',
                      marginBottom: 1,
                      fontFamily: 'var(--font-sans)',
                      fontSize: 'var(--text-sm)',
                      fontWeight: active ? 600 : 400,
                      color: active ? 'var(--text-primary)' : 'var(--text-secondary)',
                      backgroundColor: active ? 'rgba(0,229,195,0.06)' : 'transparent',
                      borderLeft: active ? '2px solid var(--teal)' : '2px solid transparent',
                      textDecoration: 'none',
                      transition: 'all var(--t-fast)',
                      whiteSpace: 'nowrap',
                      overflow: 'hidden',
                      position: 'relative',
                    }}
                    onMouseEnter={(e) => {
                      if (!active) {
                        (e.currentTarget as HTMLAnchorElement).style.backgroundColor = 'var(--bg-hover)';
                        (e.currentTarget as HTMLAnchorElement).style.color = 'var(--text-body)';
                      }
                    }}
                    onMouseLeave={(e) => {
                      if (!active) {
                        (e.currentTarget as HTMLAnchorElement).style.backgroundColor = 'transparent';
                        (e.currentTarget as HTMLAnchorElement).style.color = 'var(--text-secondary)';
                      }
                    }}
                  >
                    <span style={{
                      flexShrink: 0,
                      display: 'flex',
                      color: active ? 'var(--teal)' : 'inherit',
                    }}>
                      {item.icon}
                    </span>
                    {!collapsed && (
                      <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', letterSpacing: '-0.01em' }}>
                        {item.label}
                      </span>
                    )}
                    {!collapsed && item.badge != null && item.badge > 0 && (
                      <span style={{
                        marginLeft: 'auto',
                        fontFamily: 'var(--font-mono)',
                        fontSize: 'var(--text-2xs)',
                        fontWeight: 700,
                        padding: '0.1rem 0.35rem',
                        borderRadius: 'var(--r-full)',
                        background: 'var(--sev-4-dim)',
                        color: 'var(--sev-4)',
                      }}>
                        {item.badge}
                      </span>
                    )}
                  </NavLink>
                );
              })}

              {/* Section separator — thin hairline */}
              {!collapsed && section.id !== 'admin' && (
                <div style={{ height: 1, background: 'var(--border-hairline)', margin: '0.5rem 1rem' }} />
              )}
            </div>
          );
        })}
      </div>

      {/* Collapse toggle */}
      <button
        onClick={() => setCollapsed((v) => !v)}
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: collapsed ? 'center' : 'flex-start',
          gap: '0.5rem',
          padding: collapsed ? '0.75rem 0' : '0.65rem 1rem',
          color: 'var(--text-ghost)',
          cursor: 'pointer',
          fontFamily: 'var(--font-mono)',
          fontSize: 'var(--text-2xs)',
          letterSpacing: '0.08em',
          textTransform: 'uppercase',
          transition: 'all var(--t-fast)',
          flexShrink: 0,
          background: 'none',
          border: 'none',
          borderTop: '1px solid var(--border-hairline)',
        }}
        onMouseEnter={(e) => { (e.currentTarget as HTMLButtonElement).style.color = 'var(--text-muted)'; }}
        onMouseLeave={(e) => { (e.currentTarget as HTMLButtonElement).style.color = 'var(--text-ghost)'; }}
        aria-label={collapsed ? 'Expand navigation' : 'Collapse navigation'}
      >
        {collapsed ? <ChevronRight size={13} /> : (
          <>
            <ChevronLeft size={13} />
            <span>Collapse</span>
          </>
        )}
      </button>
    </nav>
  );
}
