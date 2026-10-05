/**
 * App Layout Shell — National Weather Intelligence System
 * Wraps all pages with Topbar + Sidebar + main content + Global Command Palette.
 */
import { Outlet } from 'react-router-dom';
import { Topbar } from './Topbar';
import { Sidebar } from './Sidebar';
import { OfflineBanner } from '../ui/States';
import { CommandPalette } from '../ui/CommandPalette';
import { useWebSocket } from '../../hooks/useWebSocket';

export function AppLayout() {
  const { connectionState } = useWebSocket();
  const isOffline = connectionState === 'DISCONNECTED' || connectionState === 'FAILED';

  return (
    <div
      style={{
        height: '100vh',
        maxHeight: '100vh',
        backgroundColor: 'var(--bg-primary)',
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden',
      }}
    >
      <Topbar />
      {isOffline && <OfflineBanner />}
      <div style={{ display: 'flex', flex: 1, overflow: 'hidden', marginTop: 'var(--topbar-height)', minHeight: 0 }}>
        <Sidebar />
        <main
          id="main-content"
          style={{
            flex: 1,
            display: 'flex',
            flexDirection: 'column',
            minHeight: 0,
            height: '100%',
            overflowY: 'auto',
            overflowX: 'hidden',
            background: 'var(--bg-primary)',
            position: 'relative',
          }}
          aria-label="Main content"
        >
          <Outlet />
        </main>
      </div>

      {/* Global Universal Search (CTRL + K) */}
      <CommandPalette />
    </div>
  );
}
