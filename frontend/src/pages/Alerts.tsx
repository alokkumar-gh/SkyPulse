/**
 * Alerts Page — Phase 7
 * National weather warning bulletin and active high-severity alerts.
 */
import { useEventsStore } from '../store/eventsStore';
import { Card } from '../components/ui/Primitives';
import { CategoryBadge, SeverityBadge, VerificationBadge } from '../components/ui/Badges';
import { EmptyState } from '../components/ui/States';
import { AlertTriangle, Bell } from 'lucide-react';

export const Alerts: React.FC = () => {
  const { events } = useEventsStore();
  const severeEvents = events.filter((e) => e.severity >= 3);

  return (
    <div
      style={{
        padding: '1.5rem',
        maxWidth: '1200px',
        margin: '0 auto',
        width: '100%',
        display: 'flex',
        flexDirection: 'column',
        gap: '1.5rem',
      }}
    >
      <div>
        <h1 style={{ margin: 0, fontSize: 'var(--text-2xl)', fontWeight: 700, color: 'var(--text-primary)' }}>
          Active Weather Alerts & Bulletins
        </h1>
        <p style={{ margin: '0.25rem 0 0 0', fontSize: 'var(--text-sm)', color: 'var(--text-secondary)' }}>
          High-priority warnings (Severity 3 & 4) dispatched to government and emergency agencies
        </p>
      </div>

      {severeEvents.length === 0 ? (
        <Card>
          <EmptyState
            icon={<Bell size={36} color="var(--severity-1)" />}
            title="No Severe Weather Warnings"
            message="No extreme weather events (Severity 3 or 4) are currently active across India."
          />
        </Card>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          {severeEvents.map((alert) => (
            <div
              key={alert.id}
              style={{
                backgroundColor: 'rgba(239, 68, 68, 0.08)',
                border: '1px solid rgba(239, 68, 68, 0.35)',
                borderRadius: 'var(--radius-lg)',
                padding: '1.25rem',
                display: 'flex',
                flexDirection: 'column',
                gap: '0.75rem',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '0.5rem' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <AlertTriangle size={18} color="var(--severity-4)" />
                  <CategoryBadge category={alert.category} />
                  <SeverityBadge severity={alert.severity} />
                </div>
                <VerificationBadge status={alert.verification_status} />
              </div>

              <div>
                <h3 style={{ margin: 0, fontSize: 'var(--text-lg)', fontWeight: 700, color: 'var(--severity-4)' }}>
                  {alert.title}
                </h3>
                <p style={{ margin: '0.35rem 0 0 0', fontSize: 'var(--text-sm)', color: 'var(--text-primary)', lineHeight: 1.4 }}>
                  {alert.description}
                </p>
              </div>

              <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', fontSize: 'var(--text-xs)', color: 'var(--text-secondary)', borderTop: '1px solid rgba(239, 68, 68, 0.15)', paddingTop: '0.5rem' }}>
                <span>📍 {alert.district ? `${alert.district}, ` : ''}{alert.state || 'India'}</span>
                <span>🕒 {alert.created_at ? new Date(alert.created_at).toLocaleString() : 'Active'}</span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
