/**
 * SkyPulse Operations Topbar — Redesign
 * "National Weather Intelligence" command header.
 *
 * Design:
 * - Ink black surface with warm ivory typography
 * - Left: SkyPulse wordmark + IST clock (monospace)
 * - Centre: Universal Search Palette trigger (CTRL+K) + National situation bar
 * - Right: WebSocket state, notifications, user menu
 * - Bottom edge: Teal signal scan line (brand signature)
 */
import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Bell, LogOut, User, ChevronDown,
  AlertTriangle, Wifi, Search,
} from 'lucide-react';
import { useAuthStore } from '../../store/authStore';
import { useNotificationsStore } from '../../store/notificationsStore';
import { useWebSocket } from '../../hooks/useWebSocket';
import { useEventsStore } from '../../store/eventsStore';
import { openCommandPalette } from '../ui/CommandPalette';

const ROLE_META: Record<string, { color: string; label: string }> = {
  PUBLIC:     { color: 'var(--text-muted)',   label: 'PUBLIC' },
  CITIZEN:    { color: 'var(--teal)',          label: 'CITIZEN' },
  ANALYST:    { color: 'var(--teal-soft)',     label: 'ANALYST' },
  GOVERNMENT: { color: 'var(--sev-3)',         label: 'GOV' },
  ADMIN:      { color: 'var(--sev-4)',         label: 'ADMIN' },
};

function useISTClock() {
  const [now, setNow] = useState(new Date());
  useEffect(() => {
    const t = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(t);
  }, []);
  const timeStr = now.toLocaleTimeString('en-IN', {
    hour: '2-digit', minute: '2-digit', second: '2-digit',
    hour12: false, timeZone: 'Asia/Kolkata',
  });
  const dateStr = now.toLocaleDateString('en-IN', {
    day: '2-digit', month: 'short', year: 'numeric',
    timeZone: 'Asia/Kolkata',
  });
  return { timeStr, dateStr };
}

// Minimal SkyPulse logomark — radar-like concentric arcs
function SkyPulseMark() {
  return (
    <svg width="22" height="22" viewBox="0 0 22 22" fill="none" aria-hidden="true">
      <path
        d="M11 3 A8 8 0 0 1 19 11"
        stroke="var(--teal)"
        strokeWidth="1.5"
        strokeLinecap="round"
        opacity="0.4"
      />
      <path
        d="M11 5.5 A5.5 5.5 0 0 1 16.5 11"
        stroke="var(--teal)"
        strokeWidth="1.5"
        strokeLinecap="round"
        opacity="0.65"
      />
      <circle cx="11" cy="11" r="2" fill="var(--teal)" />
    </svg>
  );
}

export function Topbar() {
  const { user, isAuthenticated, logout } = useAuthStore();
  const { unreadCount } = useNotificationsStore();
  const { connectionState } = useWebSocket();
  const { events } = useEventsStore();
  const { timeStr, dateStr } = useISTClock();
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);
  const navigate = useNavigate();

  useEffect(() => {
    if (!menuOpen) return;
    const handler = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setMenuOpen(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [menuOpen]);

  const isLive = connectionState === 'CONNECTED' || connectionState === 'AUTHENTICATED';
  const isReconnecting = connectionState === 'RECONNECTING' || connectionState === 'CONNECTING';

  const sev4 = events.filter((e) => e.severity === 4).length;
  const sev3 = events.filter((e) => e.severity === 3).length;
  const sev2 = events.filter((e) => e.severity === 2).length;
  const sev1 = events.filter((e) => e.severity === 1).length;
  const totalActive = events.filter((e) => e.is_active !== false).length;

  const roleMeta = ROLE_META[user?.role ?? 'PUBLIC'] ?? ROLE_META['PUBLIC'];

  return (
    <header
      id="topbar"
      className="topbar-scanner"
      aria-label="SkyPulse operations header"
      style={{
        position: 'fixed',
        top: 0, left: 0, right: 0,
        height: 'var(--topbar-height)',
        backgroundColor: 'var(--bg-surface)',
        borderBottom: '1px solid var(--border-hairline)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '0 1.25rem',
        zIndex: 100,
        gap: '1rem',
        overflow: 'hidden',
      }}
    >
      {/* ── LEFT: Brand + Clock ────────────────────────────────────────────── */}
      <div
        style={{ display: 'flex', alignItems: 'center', gap: '1rem', cursor: 'pointer', flexShrink: 0 }}
        onClick={() => navigate('/')}
        role="link"
        aria-label="Go to dashboard"
      >
        {/* Logo mark */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <SkyPulseMark />
          <div>
            <div style={{
              fontFamily: 'var(--font-sans)',
              fontWeight: 800,
              fontSize: '0.875rem',
              letterSpacing: '-0.02em',
              lineHeight: 1.1,
              color: 'var(--text-primary)',
            }}>
              SkyPulse
            </div>
            <div style={{
              fontFamily: 'var(--font-mono)',
              fontSize: 'var(--text-2xs)',
              color: 'var(--text-muted)',
              letterSpacing: '0.12em',
              textTransform: 'uppercase',
              lineHeight: 1,
            }}>
              NWI · INDIA
            </div>
          </div>
        </div>

        {/* Vertical hairline */}
        <div className="hide-mobile" style={{ width: 1, height: 24, background: 'var(--border-hairline)', flexShrink: 0 }} />

        {/* IST Clock */}
        <div className="hide-mobile" style={{
          fontFamily: 'var(--font-mono)',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'flex-start',
          lineHeight: 1.2,
        }}>
          <span style={{ fontSize: 'var(--text-xs)', fontWeight: 500, color: 'var(--text-body)', letterSpacing: '0.04em' }}>
            {timeStr}
          </span>
          <span style={{ fontSize: 'var(--text-2xs)', color: 'var(--text-muted)', letterSpacing: '0.06em' }}>
            {dateStr} IST
          </span>
        </div>
      </div>


      {/* ── CENTRE: Universal Search Trigger + Situation bar ───────────────── */}
      <div className="hide-mobile" style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', flexShrink: 0 }}>
        {/* Universal Search Trigger (CTRL + K) */}
        <button
          onClick={openCommandPalette}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '0.5rem',
            padding: '0.28rem 0.75rem',
            borderRadius: 'var(--r-2)',
            border: '1px solid var(--border-hairline)',
            backgroundColor: 'var(--bg-panel)',
            color: 'var(--text-secondary)',
            fontSize: 'var(--text-xs)',
            cursor: 'pointer',
            transition: 'border-color 0.15s ease, background-color 0.15s ease',
          }}
          className="sp-topbar-search"
          aria-label="Universal search (Ctrl+K)"
        >
          <Search size={12} color="var(--teal)" />
          <span style={{ fontFamily: 'var(--font-sans)', color: 'var(--text-secondary)' }}>
            Search intelligence...
          </span>
          <kbd style={{
            fontFamily: 'var(--font-mono)',
            fontSize: 'var(--text-2xs)',
            padding: '0.1rem 0.35rem',
            borderRadius: 'var(--r-1)',
            backgroundColor: 'var(--bg-elevated)',
            border: '1px solid var(--border-hairline)',
            color: 'var(--teal-soft)',
            letterSpacing: '0.05em',
          }}>
            CTRL K
          </kbd>
        </button>

        {/* Situation Bar */}
        <div className="hide-tablet" style={{
          display: 'flex',
          alignItems: 'center',
          gap: '0.125rem',
          flexShrink: 0,
          padding: '0.25rem 0.75rem',
          border: '1px solid var(--border-hairline)',
          borderRadius: 'var(--r-2)',
          background: 'var(--bg-panel)',
        }}>
          <span style={{
            fontFamily: 'var(--font-mono)',
            fontSize: 'var(--text-2xs)',
            color: 'var(--text-ghost)',
            marginRight: '0.5rem',
            letterSpacing: '0.04em',
          }}>
            {totalActive} active
          </span>

          {[
            { count: sev4, color: 'var(--sev-4)', label: 'EX' },
            { count: sev3, color: 'var(--sev-3)', label: 'SV' },
            { count: sev2, color: 'var(--sev-2)', label: 'MD' },
            { count: sev1, color: 'var(--sev-1)', label: 'MN' },
          ].map(({ count, color, label }) => (
            <div key={label} style={{
              display: 'flex',
              alignItems: 'center',
              gap: '0.2rem',
              padding: '0.15rem 0.4rem',
              borderRadius: 'var(--r-1)',
              background: count > 0 ? `color-mix(in srgb, ${color} 12%, transparent)` : 'transparent',
              opacity: count > 0 ? 1 : 0.3,
            }}>
              <span style={{
                fontFamily: 'var(--font-mono)',
                fontSize: 'var(--text-2xs)',
                fontWeight: 600,
                color,
                letterSpacing: '0.08em',
              }}>
                {label}
              </span>
              <span style={{
                fontFamily: 'var(--font-mono)',
                fontSize: 'var(--text-xs)',
                fontWeight: 600,
                color: count > 0 ? 'var(--text-primary)' : 'var(--text-ghost)',
              }}>
                {count}
              </span>
            </div>
          ))}

          {sev4 > 0 && (
            <AlertTriangle
              size={12}
              color="var(--sev-4)"
              style={{ marginLeft: '0.25rem', animation: 'pulse-core 1.5s ease infinite' }}
              aria-hidden="true"
            />
          )}
        </div>
      </div>

      {/* ── RIGHT: Connection + Notifications + User ───────────────────────── */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexShrink: 0 }}>

        {/* WebSocket state */}
        <div style={{
          display: 'flex', alignItems: 'center', gap: '0.3rem',
          padding: '0.2rem 0.55rem',
          borderRadius: 'var(--r-2)',
          background: isLive ? 'rgba(0,229,195,0.06)' : isReconnecting ? 'var(--sev-2-dim)' : 'rgba(249,115,22,0.12)',
          border: `1px solid ${isLive ? 'rgba(0,229,195,0.18)' : isReconnecting ? 'rgba(234,179,8,0.18)' : 'rgba(249,115,22,0.25)'}`,
        }}
        aria-live="polite"
        aria-label={`Connection: ${isLive ? 'LIVE' : isReconnecting ? 'SYNCING' : 'DEGRADED (POLLING)'}`}
        title={isLive ? 'Live event stream active' : isReconnecting ? 'Syncing stream connection...' : 'Realtime disconnected · Polling fallback active'}
        >
          {isLive ? (
            <span className="pulse-live" style={{ width: 6, height: 6 }} />
          ) : isReconnecting ? (
            <Wifi size={11} color="var(--sev-2)" style={{ animation: 'pulse-core 1s ease infinite' }} />
          ) : (
            <span style={{ display: 'inline-block', width: 6, height: 6, borderRadius: '50%', backgroundColor: 'var(--sev-3)' }} />
          )}
          <span style={{
            fontFamily: 'var(--font-mono)',
            fontSize: 'var(--text-2xs)',
            fontWeight: 600,
            letterSpacing: '0.1em',
            color: isLive ? 'var(--teal)' : isReconnecting ? 'var(--sev-2)' : 'var(--sev-3)',
          }}>
            {isLive ? 'LIVE' : isReconnecting ? 'SYNCING' : 'DEGRADED'}
          </span>
        </div>

        {/* Notification bell */}
        {isAuthenticated && (
          <button
            id="topbar-notifications"
            onClick={() => navigate('/alerts')}
            style={{
              position: 'relative',
              padding: '0.35rem',
              borderRadius: 'var(--r-2)',
              color: unreadCount > 0 ? 'var(--sev-3)' : 'var(--text-muted)',
              transition: 'color var(--t-fast)',
              background: 'none',
              border: 'none',
              cursor: 'pointer',
            }}
            aria-label={`${unreadCount} unread alerts`}
          >
            <Bell size={15} />
            {unreadCount > 0 && (
              <span style={{
                position: 'absolute',
                top: 2, right: 2,
                width: 12, height: 12,
                borderRadius: '50%',
                background: 'var(--sev-4)',
                color: '#fff',
                fontSize: '0.5rem',
                fontWeight: 700,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
              }}>
                {unreadCount > 9 ? '9+' : unreadCount}
              </span>
            )}
          </button>
        )}

        {/* User menu */}
        {isAuthenticated && user ? (
          <div ref={menuRef} style={{ position: 'relative' }}>
            <button
              id="topbar-user-menu"
              onClick={() => setMenuOpen((v) => !v)}
              style={{
                display: 'flex', alignItems: 'center', gap: '0.35rem',
                padding: '0.25rem 0.5rem',
                borderRadius: 'var(--r-2)',
                border: '1px solid var(--border-hairline)',
                background: menuOpen ? 'var(--bg-elevated)' : 'transparent',
                color: 'var(--text-body)',
                fontSize: 'var(--text-xs)',
                cursor: 'pointer',
                transition: 'background var(--t-fast)',
              }}
              aria-haspopup="menu"
              aria-expanded={menuOpen}
            >
              <div style={{
                width: 18, height: 18,
                borderRadius: '50%',
                background: `color-mix(in srgb, ${roleMeta.color} 15%, var(--bg-elevated))`,
                border: `1px solid ${roleMeta.color}`,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                flexShrink: 0,
              }}>
                <User size={9} color={roleMeta.color} />
              </div>
              <span style={{
                maxWidth: 100, overflow: 'hidden',
                textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                color: 'var(--text-body)',
                fontFamily: 'var(--font-sans)',
                fontSize: 'var(--text-xs)',
              }}>
                {user.display_name}
              </span>
              <span style={{
                fontSize: 'var(--text-2xs)',
                fontWeight: 600,
                color: roleMeta.color,
                letterSpacing: '0.08em',
                fontFamily: 'var(--font-mono)',
              }}>
                {roleMeta.label}
              </span>
              <ChevronDown size={10} color="var(--text-muted)" style={{
                transform: menuOpen ? 'rotate(180deg)' : 'none',
                transition: 'transform var(--t-fast)',
              }} />
            </button>

            {menuOpen && (
              <div
                role="menu"
                style={{
                  position: 'absolute',
                  top: 'calc(100% + 6px)',
                  right: 0,
                  minWidth: 192,
                  background: 'var(--bg-elevated)',
                  border: '1px solid var(--border-subtle)',
                  borderRadius: 'var(--r-3)',
                  overflow: 'hidden',
                  zIndex: 500,
                  boxShadow: 'var(--shadow-lg)',
                  animation: 'modal-enter 0.15s var(--ease-out-expo) both',
                }}
              >
                <div style={{ padding: '0.875rem 1rem', borderBottom: '1px solid var(--border-hairline)' }}>
                  <div style={{
                    fontFamily: 'var(--font-mono)',
                    fontSize: 'var(--text-2xs)',
                    color: 'var(--text-muted)',
                    letterSpacing: '0.08em',
                    textTransform: 'uppercase',
                    marginBottom: '0.2rem',
                  }}>
                    Signed in as
                  </div>
                  <div style={{
                    fontSize: 'var(--text-sm)',
                    fontWeight: 600,
                    color: 'var(--text-primary)',
                    wordBreak: 'break-all',
                    fontFamily: 'var(--font-mono)',
                  }}>
                    {user.email}
                  </div>
                </div>
                <button
                  role="menuitem"
                  onClick={() => { setMenuOpen(false); logout(); navigate('/login'); }}
                  style={{
                    width: '100%',
                    display: 'flex', alignItems: 'center', gap: '0.6rem',
                    padding: '0.625rem 1rem',
                    fontSize: 'var(--text-sm)',
                    color: 'var(--sev-4)',
                    cursor: 'pointer',
                    transition: 'background var(--t-fast)',
                    fontFamily: 'var(--font-sans)',
                    background: 'transparent',
                    border: 'none',
                  }}
                  onMouseEnter={(e) => { (e.currentTarget as HTMLButtonElement).style.background = 'var(--sev-4-dim)'; }}
                  onMouseLeave={(e) => { (e.currentTarget as HTMLButtonElement).style.background = 'transparent'; }}
                >
                  <LogOut size={13} />
                  Sign out
                </button>
              </div>
            )}
          </div>
        ) : (
          <button
            id="topbar-sign-in"
            onClick={() => navigate('/login')}
            style={{
              padding: '0.3rem 0.875rem',
              borderRadius: 'var(--r-2)',
              border: '1px solid var(--border-teal)',
              background: 'var(--teal-100)',
              color: 'var(--teal)',
              fontSize: 'var(--text-xs)',
              fontWeight: 600,
              cursor: 'pointer',
              fontFamily: 'var(--font-mono)',
              letterSpacing: '0.04em',
            }}
          >
            Sign In
          </button>
        )}
      </div>
    </header>
  );
}
