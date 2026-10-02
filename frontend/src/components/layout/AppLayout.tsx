/**
 * App Layout Shell — Phase 7
 * Wraps all authenticated/public pages with Topbar + Sidebar + content area.
 * Handles offline banner via WebSocket connection state.
 */
import { Outlet } from 'react-router-dom';
import { Topbar } from './Topbar';
import { Sidebar } from './Sidebar';
import { OfflineBanner } from '../ui/States';
import { useWebSocket } from '../../hooks/useWebSocket';

export function AppLayout() {
  const { connectionState } = useWebSocket();
  const isOffline = connectionState === 'DISCONNECTED' || connectionState === 'FAILED';

  return (
    <div style={{ minHeight: '100vh', backgroundColor: 'var(--bg-primary)' }}>
      <Topbar />
      {isOffline && <OfflineBanner />}
      <Sidebar />
      <main
        id="main-content"
        style={{
          marginLeft: 'var(--sidebar-width)',
          marginTop: 'var(--topbar-height)',
          minHeight: 'calc(100vh - var(--topbar-height))',
          overflow: 'auto',
          transition: 'margin-left var(--transition-normal)',
        }}
        aria-label="Main content"
      >
        <Outlet />
      </main>
    </div>
  );
}
