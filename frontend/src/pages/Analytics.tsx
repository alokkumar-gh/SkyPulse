/**
 * Analytics Page — Phase 7 & 9
 * National weather intelligence charts and metrics using Recharts.
 * Consumes real backend aggregation from GET /analytics/national and GET /analytics/timeseries.
 */
import { useEffect, useState, useMemo, useCallback } from 'react';
import {
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
  AreaChart,
  Area,
  CartesianGrid,
} from 'recharts';
import { analyticsAPI } from '../utils/api';
import { Card, Button } from '../components/ui/Primitives';
import { EmptyState, LoadingState } from '../components/ui/States';
import type { NationalAnalytics, TimeseriesSeries } from '../types';
import { SEVERITY_COLORS, CATEGORY_COLORS } from '../types';
import {
  BarChart3,
  PieChart as PieIcon,
  TrendingUp,
  Map,
  ShieldCheck,
  AlertTriangle,
  Layers,
  FileText,
  RefreshCw,
} from 'lucide-react';

export const Analytics: React.FC = () => {
  const [nationalData, setNationalData] = useState<NationalAnalytics | null>(null);
  const [timeseriesData, setTimeseriesData] = useState<TimeseriesSeries | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [timeseriesMetric, setTimeseriesMetric] = useState<'events' | 'reports'>('events');
  const [timeseriesInterval, setTimeseriesInterval] = useState<'hourly' | 'daily'>('hourly');

  const fetchAnalytics = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [nat, ts] = await Promise.all([
        analyticsAPI.national(),
        analyticsAPI.timeseries(timeseriesMetric, timeseriesInterval, 7),
      ]);
      setNationalData(nat);
      setTimeseriesData(ts);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to load backend analytics';
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, [timeseriesMetric, timeseriesInterval]);

  useEffect(() => {
    fetchAnalytics();
  }, [fetchAnalytics]);

  // 1. Category Distribution from backend
  const categoryData = useMemo(() => {
    if (!nationalData?.by_category) return [];
    return Object.entries(nationalData.by_category)
      .filter(([_, count]) => count > 0)
      .map(([name, value]) => ({
        name,
        value,
        color: CATEGORY_COLORS[name] || '#60a5fa',
      }));
  }, [nationalData]);

  // 2. Severity Breakdown from backend
  const severityData = useMemo(() => {
    const sevMap = nationalData?.by_severity || {};
    return [
      { name: '1 - Minor', count: sevMap['1'] ?? sevMap['s1'] ?? 0, color: SEVERITY_COLORS[1] },
      { name: '2 - Moderate', count: sevMap['2'] ?? sevMap['s2'] ?? 0, color: SEVERITY_COLORS[2] },
      { name: '3 - Severe', count: sevMap['3'] ?? sevMap['s3'] ?? 0, color: SEVERITY_COLORS[3] },
      { name: '4 - Extreme', count: sevMap['4'] ?? sevMap['s4'] ?? 0, color: SEVERITY_COLORS[4] },
    ];
  }, [nationalData]);

  // 3. State-wise Top Activity from backend
  const stateData = useMemo(() => {
    if (!nationalData?.top_states?.length) return [];
    return nationalData.top_states
      .map((s) => ({ name: s.state, count: s.event_count }))
      .sort((a, b) => b.count - a.count)
      .slice(0, 8);
  }, [nationalData]);

  // 4. Verification Status Breakdown from backend
  const verificationData = useMemo(() => {
    const vMap = nationalData?.by_verification_status || {};
    return Object.entries(vMap).map(([status, count]) => ({
      status,
      count,
    }));
  }, [nationalData]);

  // 5. Timeline trend from real backend timeseries
  const timelineData = useMemo(() => {
    if (!timeseriesData?.series?.length) return [];
    return timeseriesData.series.map((pt) => {
      const d = new Date(pt.timestamp);
      const label =
        timeseriesInterval === 'daily'
          ? d.toLocaleDateString([], { month: 'short', day: 'numeric' })
          : `${d.toLocaleDateString([], { month: 'short', day: 'numeric' })} ${d.getHours()}:00`;
      return {
        time: label,
        count: pt.value,
      };
    });
  }, [timeseriesData, timeseriesInterval]);

  return (
    <div
      style={{
        padding: '1.5rem',
        maxWidth: '1400px',
        margin: '0 auto',
        width: '100%',
        display: 'flex',
        flexDirection: 'column',
        gap: '1.5rem',
      }}
    >
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '1rem' }}>
        <div>
          <h1 style={{ margin: 0, fontSize: 'var(--text-2xl)', fontWeight: 700, color: 'var(--text-primary)' }}>
            National Weather Analytics & Intelligence
          </h1>
          <p style={{ margin: '0.25rem 0 0 0', fontSize: 'var(--text-sm)', color: 'var(--text-secondary)' }}>
            Live aggregated metrics, category vectors, and temporal trend analyses from backend
          </p>
        </div>

        <Button
          variant="secondary"
          size="sm"
          onClick={fetchAnalytics}
          disabled={loading}
          style={{ display: 'inline-flex', alignItems: 'center', gap: '0.4rem' }}
        >
          <RefreshCw size={14} style={{ animation: loading ? 'spin 1s linear infinite' : 'none' }} />
          <span>Refresh</span>
        </Button>
      </div>

      {error && (
        <div
          style={{
            padding: '0.75rem 1rem',
            borderRadius: 'var(--radius-md)',
            backgroundColor: 'rgba(239, 68, 68, 0.1)',
            border: '1px solid rgba(239, 68, 68, 0.3)',
            color: 'var(--text-danger)',
            fontSize: 'var(--text-sm)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}
        >
          <span>Error loading backend analytics: {error}</span>
          <Button variant="ghost" size="sm" onClick={fetchAnalytics}>
            Retry
          </Button>
        </div>
      )}

      {/* KPI Stats Ribbon */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '1rem' }}>
        <Card>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div>
              <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-muted)', fontWeight: 600 }}>TOTAL WEATHER EVENTS</div>
              <div style={{ fontSize: 'var(--text-2xl)', fontWeight: 700, color: 'var(--text-primary)', marginTop: '0.25rem' }}>
                {nationalData?.total_events ?? 0}
              </div>
            </div>
            <div style={{ padding: '0.5rem', borderRadius: 'var(--radius-md)', backgroundColor: 'rgba(59, 130, 246, 0.15)' }}>
              <Layers size={20} color="var(--brand-blue)" />
            </div>
          </div>
        </Card>

        <Card>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div>
              <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-muted)', fontWeight: 600 }}>ACTIVE EVENTS</div>
              <div style={{ fontSize: 'var(--text-2xl)', fontWeight: 700, color: 'var(--severity-1)', marginTop: '0.25rem' }}>
                {nationalData?.active_events ?? 0}
              </div>
            </div>
            <div style={{ padding: '0.5rem', borderRadius: 'var(--radius-md)', backgroundColor: 'rgba(34, 197, 94, 0.15)' }}>
              <TrendingUp size={20} color="var(--severity-1)" />
            </div>
          </div>
        </Card>

        <Card>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div>
              <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-muted)', fontWeight: 600 }}>TOTAL INGESTED REPORTS</div>
              <div style={{ fontSize: 'var(--text-2xl)', fontWeight: 700, color: 'var(--text-primary)', marginTop: '0.25rem' }}>
                {nationalData?.total_reports ?? 0}
              </div>
            </div>
            <div style={{ padding: '0.5rem', borderRadius: 'var(--radius-md)', backgroundColor: 'rgba(168, 85, 247, 0.15)' }}>
              <FileText size={20} color="#a855f7" />
            </div>
          </div>
        </Card>

        <Card>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div>
              <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-muted)', fontWeight: 600 }}>ANOMALOUS EVENTS</div>
              <div style={{ fontSize: 'var(--text-2xl)', fontWeight: 700, color: 'var(--severity-3)', marginTop: '0.25rem' }}>
                {nationalData?.anomalous_events ?? 0}
              </div>
            </div>
            <div style={{ padding: '0.5rem', borderRadius: 'var(--radius-md)', backgroundColor: 'rgba(249, 115, 22, 0.15)' }}>
              <AlertTriangle size={20} color="var(--severity-3)" />
            </div>
          </div>
        </Card>
      </div>

      {loading && !nationalData ? (
        <LoadingState message="Loading aggregated national meteorological analytics..." />
      ) : (
        <>
          {/* Top 2 Charts Grid */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(400px, 1fr))', gap: '1.25rem' }}>
            {/* Category Breakdown Donut */}
            <Card>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '1rem' }}>
                <PieIcon size={18} color="var(--brand-blue)" />
                <h3 style={{ margin: 0, fontSize: 'var(--text-base)', fontWeight: 600 }}>Category Distribution</h3>
              </div>
              <div style={{ height: 280 }}>
                {categoryData.length === 0 ? (
                  <EmptyState title="No Category Data" description="No events recorded in this period." />
                ) : (
                  <ResponsiveContainer width="100%" height="100%">
                    <PieChart>
                      <Pie
                        data={categoryData}
                        cx="50%"
                        cy="50%"
                        innerRadius={65}
                        outerRadius={95}
                        paddingAngle={3}
                        dataKey="value"
                      >
                        {categoryData.map((entry, index) => (
                          <Cell key={`cell-${index}`} fill={entry.color} />
                        ))}
                      </Pie>
                      <Tooltip
                        contentStyle={{
                          backgroundColor: 'var(--bg-elevated)',
                          border: '1px solid var(--bg-border)',
                          borderRadius: 'var(--radius-md)',
                          color: 'var(--text-primary)',
                          fontSize: '12px',
                        }}
                      />
                      <Legend
                        formatter={(value) => <span style={{ color: 'var(--text-secondary)', fontSize: '11px' }}>{value}</span>}
                      />
                    </PieChart>
                  </ResponsiveContainer>
                )}
              </div>
            </Card>

            {/* Severity Distribution Bar */}
            <Card>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '1rem' }}>
                <BarChart3 size={18} color="var(--severity-3)" />
                <h3 style={{ margin: 0, fontSize: 'var(--text-base)', fontWeight: 600 }}>Severity Level Distribution</h3>
              </div>
              <div style={{ height: 280 }}>
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={severityData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
                    <XAxis dataKey="name" stroke="var(--text-muted)" fontSize={11} />
                    <YAxis stroke="var(--text-muted)" fontSize={11} allowDecimals={false} />
                    <Tooltip
                      contentStyle={{
                        backgroundColor: 'var(--bg-elevated)',
                        border: '1px solid var(--bg-border)',
                        borderRadius: 'var(--radius-md)',
                        color: 'var(--text-primary)',
                        fontSize: '12px',
                      }}
                    />
                    <Bar dataKey="count" radius={[4, 4, 0, 0]}>
                      {severityData.map((entry, index) => (
                        <Cell key={`sev-${index}`} fill={entry.color} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </Card>
          </div>

          {/* Bottom 2 Charts Grid */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(400px, 1fr))', gap: '1.25rem' }}>
            {/* Real Timeseries Trend Area Chart */}
            <Card>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1rem', flexWrap: 'wrap', gap: '0.5rem' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <TrendingUp size={18} color="var(--brand-blue)" />
                  <h3 style={{ margin: 0, fontSize: 'var(--text-base)', fontWeight: 600 }}>Activity Timeseries Trend</h3>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <select
                    value={timeseriesMetric}
                    onChange={(e) => setTimeseriesMetric(e.target.value as 'events' | 'reports')}
                    style={{
                      backgroundColor: 'var(--bg-elevated)',
                      border: '1px solid var(--bg-border)',
                      color: 'var(--text-primary)',
                      borderRadius: 'var(--radius-sm)',
                      padding: '0.2rem 0.5rem',
                      fontSize: 'var(--text-xs)',
                    }}
                  >
                    <option value="events">Events</option>
                    <option value="reports">Reports</option>
                  </select>
                  <select
                    value={timeseriesInterval}
                    onChange={(e) => setTimeseriesInterval(e.target.value as 'hourly' | 'daily')}
                    style={{
                      backgroundColor: 'var(--bg-elevated)',
                      border: '1px solid var(--bg-border)',
                      color: 'var(--text-primary)',
                      borderRadius: 'var(--radius-sm)',
                      padding: '0.2rem 0.5rem',
                      fontSize: 'var(--text-xs)',
                    }}
                  >
                    <option value="hourly">Hourly</option>
                    <option value="daily">Daily</option>
                  </select>
                </div>
              </div>
              <div style={{ height: 280 }}>
                {timelineData.length === 0 ? (
                  <EmptyState title="No Timeseries Data" description="No frequency data for selected period." />
                ) : (
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={timelineData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                      <defs>
                        <linearGradient id="colorTotal" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%" stopColor="var(--brand-blue)" stopOpacity={0.4} />
                          <stop offset="95%" stopColor="var(--brand-blue)" stopOpacity={0.0} />
                        </linearGradient>
                      </defs>
                      <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
                      <XAxis dataKey="time" stroke="var(--text-muted)" fontSize={11} />
                      <YAxis stroke="var(--text-muted)" fontSize={11} allowDecimals={false} />
                      <Tooltip
                        contentStyle={{
                          backgroundColor: 'var(--bg-elevated)',
                          border: '1px solid var(--bg-border)',
                          borderRadius: 'var(--radius-md)',
                          color: 'var(--text-primary)',
                          fontSize: '12px',
                        }}
                      />
                      <Area
                        type="monotone"
                        dataKey="count"
                        stroke="var(--brand-blue)"
                        fillOpacity={1}
                        fill="url(#colorTotal)"
                        name={timeseriesMetric === 'events' ? 'Weather Events' : 'Reports'}
                      />
                      <Legend formatter={(value) => <span style={{ color: 'var(--text-secondary)', fontSize: '11px' }}>{value}</span>} />
                    </AreaChart>
                  </ResponsiveContainer>
                )}
              </div>
            </Card>

            {/* State-wise Distribution */}
            <Card>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '1rem' }}>
                <Map size={18} color="var(--cat-thunderstorm)" />
                <h3 style={{ margin: 0, fontSize: 'var(--text-base)', fontWeight: 600 }}>Top Impacted States</h3>
              </div>
              <div style={{ height: 280 }}>
                {stateData.length === 0 ? (
                  <EmptyState title="No State Distribution" description="No state breakdown available." />
                ) : (
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={stateData} layout="vertical" margin={{ top: 5, right: 20, left: 40, bottom: 5 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
                      <XAxis type="number" stroke="var(--text-muted)" fontSize={11} allowDecimals={false} />
                      <YAxis type="category" dataKey="name" stroke="var(--text-muted)" fontSize={11} width={80} />
                      <Tooltip
                        contentStyle={{
                          backgroundColor: 'var(--bg-elevated)',
                          border: '1px solid var(--bg-border)',
                          borderRadius: 'var(--radius-md)',
                          color: 'var(--text-primary)',
                          fontSize: '12px',
                        }}
                      />
                      <Bar dataKey="count" fill="var(--cat-thunderstorm)" radius={[0, 4, 4, 0]} name="Events" />
                    </BarChart>
                  </ResponsiveContainer>
                )}
              </div>
            </Card>
          </div>

          {/* Verification Status Distribution Section */}
          {verificationData.length > 0 && (
            <Card>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '1rem' }}>
                <ShieldCheck size={18} color="var(--brand-blue)" />
                <h3 style={{ margin: 0, fontSize: 'var(--text-base)', fontWeight: 600 }}>Verification Status Breakdown</h3>
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: '0.75rem' }}>
                {verificationData.map(({ status, count }) => (
                  <div
                    key={status}
                    style={{
                      padding: '0.75rem',
                      borderRadius: 'var(--radius-md)',
                      backgroundColor: 'var(--bg-elevated)',
                      border: '1px solid var(--bg-border)',
                    }}
                  >
                    <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-muted)', fontWeight: 600 }}>{status}</div>
                    <div style={{ fontSize: 'var(--text-xl)', fontWeight: 700, color: 'var(--text-primary)', marginTop: '0.2rem' }}>
                      {count}
                    </div>
                  </div>
                ))}
              </div>
            </Card>
          )}
        </>
      )}
    </div>
  );
};
