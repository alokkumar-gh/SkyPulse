/**
 * KPIBar — National Meteorological Intelligence Strip
 * Re-architected with Section 7 Editorial Metric standards.
 * "The metric should feel like a piece of intelligence. Use typography to create importance."
 */

import React from 'react';
import type { WeatherEvent } from '../../types';
import { MetricCard } from '../ui/MetricCard';

interface KPIBarProps {
  events: WeatherEvent[];
  totalReportsCount?: number;
  loading?: boolean;
  onExploreActive?: () => void;
  onExploreSevere?: () => void;
  onExploreVerified?: () => void;
}

export const KPIBar: React.FC<KPIBarProps> = ({
  events,
  totalReportsCount = 0,
  loading = false,
  onExploreActive,
  onExploreSevere,
  onExploreVerified,
}) => {
  const activeCount = events.filter((e) => e.is_active !== false).length;
  const severeCount = events.filter((e) => e.severity >= 3).length;
  const verifiedCount = events.filter((e) => e.verification_status === 'VERIFIED').length;
  const verificationRate = activeCount > 0 ? Math.round((verifiedCount / activeCount) * 100) : 0;

  return (
    <div
      style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
        gap: '0.75rem',
      }}
      className="sp-kpibar-grid"
    >
      {/* 1. Active Anomalies */}
      <MetricCard
        label="ACTIVE WEATHER EVENTS"
        value={loading ? '—' : activeCount}
        unit="events"
        comparison={{
          value: '+4',
          text: 'in last 24h',
          trend: 'up',
          sentiment: 'neutral',
        }}
        source="IMD & ERA5"
        freshness="Live Sync"
        signal="teal"
        onClick={onExploreActive}
      />

      {/* 2. Severe Alerts */}
      <MetricCard
        label="SEVERE CIVIL WARNINGS"
        value={loading ? '—' : severeCount}
        unit="active"
        comparison={{
          value: severeCount > 0 ? 'Urgent' : 'Nominal',
          text: severeCount > 0 ? 'requires monitoring' : 'no extreme events',
          sentiment: severeCount > 0 ? 'negative' : 'positive',
        }}
        source="NDMA CAP Feed"
        freshness="Updated 2m ago"
        signal={severeCount > 0 ? 'sev-4' : 'sev-1'}
        isAnomaly={severeCount > 0}
        onClick={onExploreSevere}
      />

      {/* 3. Verification Confidence Rate */}
      <MetricCard
        label="GROUND TRUTH RATE"
        value={loading ? '—' : `${verificationRate}%`}
        comparison={{
          value: `${verifiedCount} verified`,
          text: `of ${activeCount} active incidents`,
          trend: 'neutral',
          sentiment: verificationRate > 70 ? 'positive' : 'warning',
        }}
        source="Analyst & AWS"
        freshness="Continuous"
        signal="sev-1"
        onClick={onExploreVerified}
      />

      {/* 4. Multi-Source Ingestion Volume */}
      <MetricCard
        label="INGESTED OBSERVATIONS"
        value={loading ? '—' : (totalReportsCount > 0 ? totalReportsCount.toLocaleString() : '—')}
        unit="telemetry pts"
        comparison={{
          value: totalReportsCount > 0 ? `${totalReportsCount.toLocaleString()} pts` : 'Multi-Source',
          text: 'reporting across India',
          sentiment: 'neutral',
        }}
        source="National Data Mesh"
        freshness="Live Telemetry"
        signal="teal"
      />
    </div>
  );
};
