/**
 * Reports Page — Phase 7
 * Catalog of ingested citizen and sensor reports, with action to submit new ground report.
 */
import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, Button } from '../components/ui/Primitives';
import { reportsAPI } from '../utils/api';
import { CategoryBadge, SeverityBadge } from '../components/ui/Badges';
import { EmptyState } from '../components/ui/States';
import { PlusCircle, FileText, MapPin, Clock } from 'lucide-react';

export const Reports: React.FC = () => {
  const navigate = useNavigate();
  const [reports, setReports] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const fetchReports = async () => {
      try {
        setLoading(true);
        const res = await reportsAPI.getReports({}, 1, 20);
        if (res.data?.items) {
          setReports(res.data.items);
        }
      } catch {
        // fallback
      } finally {
        setLoading(false);
      }
    };
    fetchReports();
  }, []);

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
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '1rem' }}>
        <div>
          <h1 style={{ margin: 0, fontSize: 'var(--text-2xl)', fontWeight: 700, color: 'var(--text-primary)' }}>
            Weather Reports Feed
          </h1>
          <p style={{ margin: '0.25rem 0 0 0', fontSize: 'var(--text-sm)', color: 'var(--text-secondary)' }}>
            Citizen, IoT, and API reports ingested into the SkyPulse pipeline
          </p>
        </div>

        <Button
          variant="primary"
          icon={<PlusCircle size={16} />}
          onClick={() => navigate('/submit')}
        >
          Submit Ground Report
        </Button>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
        {loading ? (
          <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-secondary)' }}>
            Loading weather reports...
          </div>
        ) : reports.length === 0 ? (
          <Card>
            <EmptyState
              icon={<FileText size={36} color="var(--text-muted)" />}
              title="No Raw Reports"
              message="No raw ground weather reports currently in cache. Use 'Submit Ground Report' to add one."
            />
          </Card>
        ) : (
          reports.map((r) => (
            <Card key={r.id}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <CategoryBadge category={r.category} />
                  <SeverityBadge severity={r.severity} />
                  <span style={{ fontSize: '11px', color: 'var(--text-muted)', backgroundColor: 'var(--bg-elevated)', padding: '2px 6px', borderRadius: '4px' }}>
                    {r.source_type}
                  </span>
                </div>
                <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: '0.3rem' }}>
                  <Clock size={12} />
                  {r.created_at ? new Date(r.created_at).toLocaleTimeString() : 'Recent'}
                </div>
              </div>

              <p style={{ margin: '0 0 0.5rem 0', fontSize: 'var(--text-sm)', color: 'var(--text-primary)' }}>
                {r.description || 'Raw ground observation received.'}
              </p>

              <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-secondary)', display: 'flex', alignItems: 'center', gap: '0.3rem' }}>
                <MapPin size={12} />
                {r.district ? `${r.district}, ` : ''}{r.state || 'India'}
              </div>
            </Card>
          ))
        )}
      </div>
    </div>
  );
};
