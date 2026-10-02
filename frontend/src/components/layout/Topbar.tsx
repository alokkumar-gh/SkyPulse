/**
 * Topbar — Phase 7
 * Fixed header with SkyPulse brand, live connection state, date/time,
 * notification bell, user role chip, system health indicator.
 */
import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Bell, Radio, LogOut, User, ChevronDown } from 'lucide-react';
import { useAuthStore } from '../../store/authStore';
import { useNotificationsStore } from '../../store/notificationsStore';
import { useWebSocket } from '../../hooks/useWebSocket';
import { PulseDot } from '../ui/Badges';

const ROLE_COLORS: Record<string, string> = {
  PUBLIC: 'var(--text-muted)',
  CITIZEN: 'var(--status-likely)',
  ANALYST: 'var(--cat-thunderstorm)',
  GOVERNMENT: 'var(--severity-3)',
  ADMIN: 'var(--severity-4)',
};

function formatTime(date: Date): string {
  return date.toLocaleTimeString('en-IN', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
    timeZone: 'Asia/Kolkata',
  });
}

function formatDate(date: Date): string {
  return date.toLocaleDateString('en-IN', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    timeZone: 'Asia/Kolkata',
  });
}

export function Topbar() {
  const { user, isAuthenticated, logout } = useAuthStore();
  const { unreadCount } = useNotificationsStore();
  const { connectionState } = useWebSocket();
  const [now, setNow] = useState(new Date());
  const [menuOpen, setMenuOpen] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    const timer = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(timer);
  }, []);

  // Connection state display
  const connState = {
    CONNECTED: { label: 'LIVE', color: 'var(--severity-1)', dot: true },
    CONNECTING: { label: 'CONNECTING…', color: 'var(--severity-2)', dot: false },
    RECONNECTING: { label: 'RECONNECTING…', color: 'var(--severity-3)', dot: false },
    DISCONNECTED: { label: 'OFFLINE', color: 'var(--severity-4)', dot: false },
    ERROR: { label: 'OFFLINE', color: 'var(--severity-4)', dot: false },
  }[connectionState as string] ?? { label: connectionState, color: 'var(--text-muted)', dot: false };

  return (
    <header
      id="topbar"
      style={{
        position: 'fixed',
        top: 0,
        left: 0,
        right: 0,
        height: 'var(--topbar-height)',
        backgroundColor: 'var(--bg-surface)',
        borderBottom: '1px solid var(--bg-border)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '0 1.25rem',
        zIndex: 100,
        gap: '1rem',
      }}
    >
      {/* LEFT: Brand */}
      <div
        style={{ display: 'flex', alignItems: 'center', gap: '0.625rem', cursor: 'pointer' }}
        onClick={() => navigate('/')}
      >
        <div
          style={{
            width: 30,
            height: 30,
            borderRadius: 'var(--radius-md)',
            backgroundColor: 'var(--brand-blue)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            boxShadow: '0 0 10px var(--brand-blue-glow)',
            flexShrink: 0,
          }}
        >
          <Radio size={16} color="#fff" />
        </div>
        <div>
          <div style={{ fontWeight: 700, fontSize: '1rem', letterSpacing: '-0.02em', lineHeight: 1.2 }}>
            SkyPulse
          </div>
          <div
            style={{
              fontSize: '0.6rem',
              color: 'var(--text-muted)',
              letterSpacing: '0.1em',
              textTransform: 'uppercase',
              lineHeight: 1,
            }}
          >
            National Weather Intelligence
          </div>
        </div>
      </div>

      {/* RIGHT: Status bar */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
        {/* Live connection state */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '0.35rem',
            fontSize: 'var(--text-xs)',
            fontWeight: 700,
            color: connState.color,
            fontFamily: 'var(--font-mono)',
          }}
          aria-live="polite"
          aria-label={`Connection status: ${connState.label}`}
        >
          {connState.dot ? <PulseDot color={connState.color} /> : (
            <span style={{ width: 8, height: 8, borderRadius: '50%', backgroundColor: connState.color, display: 'inline-block' }} />
          )}
          {connState.label}
        </div>

        {/* Date/time */}
        <div
          style={{
            fontSize: 'var(--text-xs)',
            color: 'var(--text-muted)',
            fontFamily: 'var(--font-mono)',
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'flex-end',
            lineHeight: 1.3,
          }}
        >
          <span style={{ color: 'var(--text-secondary)', fontWeight: 500 }}>{formatTime(now)}</span>
          <span style={{ fontSize: '0.65rem' }}>{formatDate(now)} IST</span>
        </div>

        {/* Notification bell */}
        {isAuthenticated && (
          <button
            onClick={() => navigate('/alerts')}
            style={{
              position: 'relative',
              padding: '0.4rem',
              borderRadius: 'var(--radius-md)',
              color: unreadCount > 0 ? 'var(--severity-3)' : 'var(--text-muted)',
              transition: 'color var(--transition-fast)',
            }}
            aria-label={`Notifications: ${unreadCount} unread`}
          >
            <Bell size={18} />
            {unreadCount > 0 && (
              <span
                style={{
                  position: 'absolute',
                  top: 2,
                  right: 2,
                  width: 14,
                  height: 14,
                  borderRadius: '50%',
                  backgroundColor: 'var(--severity-4)',
                  color: '#fff',
                  fontSize: '0.55rem',
                  fontWeight: 700,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                }}
              >
                {unreadCount > 9 ? '9+' : unreadCount}
              </span>
            )}
          </button>
        )}

        {/* User menu */}
        {isAuthenticated && user ? (
          <div style={{ position: 'relative' }}>
            <button
              onClick={() => setMenuOpen((v) => !v)}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '0.4rem',
                padding: '0.3rem 0.6rem',
                borderRadius: 'var(--radius-md)',
                border: '1px solid var(--bg-border)',
                backgroundColor: 'var(--bg-elevated)',
                color: 'var(--text-primary)',
                fontSize: 'var(--text-xs)',
                cursor: 'pointer',
              }}
              aria-haspopup="true"
              aria-expanded={menuOpen}
            >
              <User size={14} />
              <span style={{ maxWidth: 120, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {user.display_name}
              </span>
              <span
                style={{
                  fontSize: '0.6rem',
                  fontWeight: 700,
                  color: ROLE_COLORS[user.role] ?? 'var(--text-muted)',
                  letterSpacing: '0.05em',
                }}
              >
                {user.role}
              </span>
              <ChevronDown size={12} />
            </button>
            {menuOpen && (
              <div
                style={{
                  position: 'absolute',
                  top: 'calc(100% + 4px)',
                  right: 0,
                  minWidth: 160,
                  backgroundColor: 'var(--bg-elevated)',
                  border: '1px solid var(--bg-border)',
                  borderRadius: 'var(--radius-md)',
                  overflow: 'hidden',
                  zIndex: 200,
                  boxShadow: '0 4px 20px rgba(0,0,0,0.4)',
                }}
                role="menu"
              >
                <div
                  style={{ padding: '0.75rem 1rem', borderBottom: '1px solid var(--bg-border)' }}
                >
                  <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-muted)' }}>Signed in as</div>
                  <div style={{ fontSize: 'var(--text-sm)', fontWeight: 600, marginTop: 2 }}>{user.email}</div>
                </div>
                <button
                  onClick={() => { setMenuOpen(false); logout(); navigate('/login'); }}
                  style={{
                    width: '100%',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '0.5rem',
                    padding: '0.625rem 1rem',
                    fontSize: 'var(--text-sm)',
                    color: 'var(--severity-4)',
                    cursor: 'pointer',
                  }}
                  role="menuitem"
                >
                  <LogOut size={14} />
                  Sign out
                </button>
              </div>
            )}
          </div>
        ) : (
          <button
            onClick={() => navigate('/login')}
            style={{
              padding: '0.3rem 0.75rem',
              borderRadius: 'var(--radius-md)',
              border: '1px solid var(--brand-blue)',
              backgroundColor: 'transparent',
              color: 'var(--brand-blue)',
              fontSize: 'var(--text-xs)',
              fontWeight: 600,
              cursor: 'pointer',
            }}
          >
            Sign In
          </button>
        )}
      </div>
    </header>
  );
}
