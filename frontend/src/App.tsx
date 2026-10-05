/**
 * SkyPulse Main Application Component — Phase 7
 * React Router setup, global layout structure, WebSocket live connection,
 * route-level lazy loading and vendor code-splitting across views.
 */
import { lazy, Suspense } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AppLayout } from './components/layout/AppLayout';
import { ErrorBoundary } from './components/ui/ErrorBoundary';

// Route-level code splitting
const Dashboard = lazy(() => import('./pages/Dashboard').then((m) => ({ default: m.Dashboard })));
const LiveMap = lazy(() => import('./pages/LiveMap').then((m) => ({ default: m.LiveMap })));
const Events = lazy(() => import('./pages/Events').then((m) => ({ default: m.Events })));
const Analytics = lazy(() => import('./pages/Analytics').then((m) => ({ default: m.Analytics })));
const Alerts = lazy(() => import('./pages/Alerts').then((m) => ({ default: m.Alerts })));
const Reports = lazy(() => import('./pages/Reports').then((m) => ({ default: m.Reports })));
const Sources = lazy(() => import('./pages/Sources').then((m) => ({ default: m.Sources })));
const DWEGView = lazy(() => import('./pages/DWEGView').then((m) => ({ default: m.DWEGView })));
const VerificationQueue = lazy(() => import('./pages/VerificationQueue').then((m) => ({ default: m.VerificationQueue })));
const SubmitReport = lazy(() => import('./pages/SubmitReport').then((m) => ({ default: m.SubmitReport })));
const Login = lazy(() => import('./pages/Login').then((m) => ({ default: m.Login })));

// Phase 9: Analyst & Admin Route Split
const AnalystLayout = lazy(() => import('./layouts/AnalystLayout').then((m) => ({ default: m.AnalystLayout })));
const AdminLayout = lazy(() => import('./layouts/AdminLayout').then((m) => ({ default: m.AdminLayout })));
const AnalystQueue = lazy(() => import('./pages/analyst/VerificationQueue').then((m) => ({ default: m.VerificationQueue })));
const AnalystEventDetail = lazy(() => import('./pages/analyst/AnalystEventDetail').then((m) => ({ default: m.AnalystEventDetail })));
const SystemHealthPage = lazy(() => import('./pages/admin/SystemHealth').then((m) => ({ default: m.SystemHealthPage })));
const ConnectorManagement = lazy(() => import('./pages/admin/ConnectorManagement').then((m) => ({ default: m.ConnectorManagement })));
const UserManagement = lazy(() => import('./pages/admin/UserManagement').then((m) => ({ default: m.UserManagement })));
const AuditLogPage = lazy(() => import('./pages/admin/AuditLog').then((m) => ({ default: m.AuditLogPage })));
const FlaggedReportsPage = lazy(() => import('./pages/admin/FlaggedReports').then((m) => ({ default: m.FlaggedReportsPage })));

function PageLoader() {
  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        height: 'calc(100vh - var(--topbar-height, 56px))',
        backgroundColor: 'var(--bg-primary)',
        color: 'var(--text-secondary)',
        fontSize: 'var(--text-sm)',
        fontFamily: 'var(--font-mono, monospace)',
        letterSpacing: '0.04em',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
        <span className="pulse-live" style={{ width: 6, height: 6 }} />
        <span>Loading intelligence view...</span>
      </div>
    </div>
  );
}

export default function App() {
  return (
    <ErrorBoundary fallbackTitle="Application Interface Error">
      <BrowserRouter>
        <Suspense fallback={<PageLoader />}>
          <Routes>
            {/* Public Login Route */}
            <Route path="/login" element={<Login />} />

            {/* Phase 9: Dedicated Analyst Layout & Routes */}
            <Route path="/analyst" element={<AnalystLayout />}>
              <Route index element={<Navigate to="/analyst/queue" replace />} />
              <Route path="queue" element={<AnalystQueue />} />
              <Route path="events" element={<Events />} />
              <Route path="events/:eventId" element={<AnalystEventDetail />} />
              <Route path="clusters" element={<AnalystQueue />} />
              <Route path="alerts" element={<Alerts />} />
            </Route>

            {/* Phase 9: Dedicated Admin Layout & Routes */}
            <Route path="/admin" element={<AdminLayout />}>
              <Route index element={<Navigate to="/admin/health" replace />} />
              <Route path="health" element={<SystemHealthPage />} />
              <Route path="connectors" element={<ConnectorManagement />} />
              <Route path="users" element={<UserManagement />} />
              <Route path="audit" element={<AuditLogPage />} />
              <Route path="flagged-reports" element={<FlaggedReportsPage />} />
            </Route>

            {/* Core Layout Routes */}
            <Route element={<AppLayout />}>
              <Route path="/" element={<Dashboard />} />
              <Route path="/map" element={<LiveMap />} />
              <Route path="/events" element={<Events />} />
              <Route path="/events/:eventId" element={<AnalystEventDetail />} />
              <Route path="/analytics" element={<Analytics />} />
              <Route path="/alerts" element={<Alerts />} />
              <Route path="/reports" element={<Reports />} />
              <Route path="/sources" element={<Sources />} />
              <Route path="/dweg" element={<DWEGView />} />
              <Route path="/verification" element={<VerificationQueue />} />
              <Route path="/submit" element={<SubmitReport />} />
            </Route>

            {/* Catch-all redirect */}
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </Suspense>
      </BrowserRouter>
    </ErrorBoundary>
  );
}
