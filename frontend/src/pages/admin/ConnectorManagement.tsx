/**
 * ConnectorManagement Page — Phase 9 & Social & Web Intelligence
 * Admin portal for managing ingestion sources and connectors.
 * Supports viewing connector health, enable/disable toggling, and add/edit connector modals.
 * Includes dedicated Social & Web Sources inspection & smoke-test verification suite.
 */
import React, { useEffect, useState } from 'react';
import { sourcesAPI, socialWebAPI } from '../../utils/api';
import type { Source, SocialWebSourceDetail, SocialWebTestSourceResponse } from '../../types';
import { Card, Button, Input, Select } from '../../components/ui/Primitives';
import { DemoBadge } from '../../components/ui/Badges';
import { TableSkeleton, EmptyState } from '../../components/ui/States';
import {
  Database,
  Plus,
  Power,
  RefreshCw,
  CheckCircle,
  AlertCircle,
  Edit,
  Radio,
  Globe,
  Smartphone,
  ShieldCheck,
  Rss,
  Share2,
  FileCode,
  Activity,
  Play,
  Info,
} from 'lucide-react';

export const ConnectorManagement: React.FC = () => {
  const [sources, setSources] = useState<Source[]>([]);
  const [socialWebSources, setSocialWebSources] = useState<SocialWebSourceDetail[]>([]);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [notification, setNotification] = useState<{ message: string; isError?: boolean } | null>(null);

  // Modal State for Core Connectors
  const [showModal, setShowModal] = useState(false);
  const [modalMode, setModalMode] = useState<'ADD' | 'EDIT'>('ADD');
  const [currentSourceId, setCurrentSourceId] = useState<string | null>(null);
  const [name, setName] = useState('');
  const [sourceType, setSourceType] = useState('WEATHER_API');
  const [connectorClass, setConnectorClass] = useState('OpenMeteoConnector');
  const [isDemo, setIsDemo] = useState(false);
  const [modalSubmitting, setModalSubmitting] = useState(false);

  // Test Modal State for Social & Web Sources
  const [showTestModal, setShowTestModal] = useState(false);
  const [testSourceType, setTestSourceType] = useState('RSS_FEED');
  const [testUrl, setTestUrl] = useState('');
  const [testApiKey, setTestApiKey] = useState('');
  const [testApiToken, setTestApiToken] = useState('');
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<SocialWebTestSourceResponse | null>(null);

  const fetchSources = async () => {
    try {
      setLoading(true);
      const [coreRes, swRes] = await Promise.all([
        sourcesAPI.list(),
        socialWebAPI.sources().catch(() => ({ total: 0, sources: [] })),
      ]);
      setSources(coreRes);
      if (swRes && swRes.sources) {
        setSocialWebSources(swRes.sources);
      }
    } catch (err: any) {
      setNotification({ message: err?.message || 'Failed to load connectors', isError: true });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchSources();
  }, []);

  const handleToggle = async (src: Source) => {
    try {
      setActionLoading(src.id);
      setNotification(null);
      await sourcesAPI.toggleActive(src.id, !src.is_active);
      setNotification({
        message: `Connector "${src.name}" successfully ${!src.is_active ? 'enabled' : 'disabled'}.`,
      });
      fetchSources();
    } catch (err: any) {
      setNotification({
        message: err?.message || 'Failed to update connector state',
        isError: true,
      });
    } finally {
      setActionLoading(null);
    }
  };

  const handleOpenAdd = () => {
    setModalMode('ADD');
    setCurrentSourceId(null);
    setName('');
    setSourceType('WEATHER_API');
    setConnectorClass('OpenMeteoConnector');
    setIsDemo(false);
    setShowModal(true);
  };

  const handleOpenEdit = (src: Source) => {
    setModalMode('EDIT');
    setCurrentSourceId(src.id);
    setName(src.name);
    setSourceType(src.source_type);
    setConnectorClass('ConfigurableConnector');
    setIsDemo(src.is_demo);
    setShowModal(true);
  };

  const handleModalSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;

    try {
      setModalSubmitting(true);
      setNotification(null);

      if (modalMode === 'ADD') {
        await sourcesAPI.createConnector({
          name: name.trim(),
          source_type: sourceType,
          connector_class: connectorClass,
          is_demo: isDemo,
        });
        setNotification({ message: `Connector "${name.trim()}" successfully created.` });
      } else if (currentSourceId) {
        await sourcesAPI.updateConnector(currentSourceId, {
          config: { modified_at: new Date().toISOString() },
        });
        setNotification({ message: `Connector "${name.trim()}" updated.` });
      }

      setShowModal(false);
      fetchSources();
    } catch (err: any) {
      setNotification({
        message: err?.message || 'Failed to save connector configuration',
        isError: true,
      });
    } finally {
      setModalSubmitting(false);
    }
  };

  const handleOpenTest = (source?: SocialWebSourceDetail) => {
    setTestResult(null);
    if (source) {
      setTestSourceType(source.source_type);
      setTestUrl(source.config?.feed_url || source.config?.base_url || source.config?.endpoint_url || source.config?.urls?.[0] || '');
    } else {
      setTestSourceType('RSS_FEED');
      setTestUrl('');
    }
    setTestApiKey('');
    setTestApiToken('');
    setShowTestModal(true);
  };

  const handleRunSmokeTest = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      setTesting(true);
      setTestResult(null);
      const res = await socialWebAPI.testSource({
        source_type: testSourceType,
        url: testUrl.trim() || undefined,
        api_key: testApiKey.trim() || undefined,
        api_token: testApiToken.trim() || undefined,
      });
      setTestResult(res);
    } catch (err: any) {
      setTestResult({
        status: 'ERROR',
        source_type: testSourceType,
        tested_url: testUrl,
        success: false,
        records_found: 0,
        sample_records: [],
        latency_ms: 0,
        error_message: err?.message || 'Smoke test request failed',
        timestamp: new Date().toISOString(),
      });
    } finally {
      setTesting(false);
    }
  };

  const getSourceIcon = (type: string) => {
    switch (type) {
      case 'CITIZEN':
        return <Smartphone size={16} color="var(--severity-1)" />;
      case 'GOVERNMENT_API':
      case 'GOVERNMENT_DATASET':
        return <ShieldCheck size={16} color="var(--severity-4)" />;
      case 'SOCIAL_API':
      case 'SOCIAL_FEED':
      case 'SOCIAL_MEDIA':
        return <Share2 size={16} color="var(--cat-thunderstorm)" />;
      case 'RSS_FEED':
        return <Rss size={16} color="#f97316" />;
      case 'PUBLIC_WEB':
        return <Globe size={16} color="var(--brand-blue)" />;
      case 'PUBLIC_JSON':
        return <FileCode size={16} color="#10b981" />;
      default:
        return <Radio size={16} color="var(--brand-blue)" />;
    }
  };

  const getStatusBadgeStyle = (status: string) => {
    const st = (status || 'HEALTHY').toUpperCase();
    if (st === 'HEALTHY') {
      return { bg: 'rgba(34, 197, 94, 0.15)', fg: 'var(--severity-1)', border: 'rgba(34, 197, 94, 0.3)' };
    }
    if (st === 'DEGRADED') {
      return { bg: 'rgba(234, 179, 8, 0.15)', fg: 'var(--severity-2)', border: 'rgba(234, 179, 8, 0.3)' };
    }
    if (st === 'NOT_CONFIGURED') {
      return { bg: 'rgba(148, 163, 184, 0.15)', fg: 'var(--text-muted)', border: 'rgba(148, 163, 184, 0.3)' };
    }
    return { bg: 'rgba(239, 68, 68, 0.15)', fg: 'var(--severity-4)', border: 'rgba(239, 68, 68, 0.3)' };
  };

  return (
    <div
      style={{
        padding: '1.5rem',
        maxWidth: '1400px',
        margin: '0 auto',
        width: '100%',
        display: 'flex',
        flexDirection: 'column',
        gap: '2rem',
      }}
    >
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '1rem' }}>
        <div>
          <h1 style={{ margin: 0, fontSize: 'var(--text-2xl)', fontWeight: 700, color: 'var(--text-primary)' }}>
            Data Ingestion Connectors
          </h1>
          <p style={{ margin: '0.25rem 0 0 0', fontSize: 'var(--text-sm)', color: 'var(--text-secondary)' }}>
            Configure real and synthetic meteorological telemetry pipelines, poll rates, and health metrics
          </p>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          <Button variant="secondary" size="sm" icon={<Play size={14} />} onClick={() => handleOpenTest()}>
            Test Social / Web Source
          </Button>
          <Button variant="secondary" size="sm" icon={<RefreshCw size={14} />} onClick={fetchSources} loading={loading}>
            Refresh
          </Button>
          <Button variant="primary" size="sm" icon={<Plus size={14} />} onClick={handleOpenAdd}>
            Add Connector
          </Button>
        </div>
      </div>

      {/* Global Notification */}
      {notification && (
        <div
          style={{
            padding: '0.75rem 1rem',
            borderRadius: 'var(--radius-md)',
            fontSize: 'var(--text-sm)',
            display: 'flex',
            alignItems: 'center',
            gap: '0.5rem',
            backgroundColor: notification.isError ? 'rgba(239, 68, 68, 0.15)' : 'rgba(34, 197, 94, 0.15)',
            border: `1px solid ${notification.isError ? 'rgba(239, 68, 68, 0.3)' : 'rgba(34, 197, 94, 0.3)'}`,
            color: notification.isError ? 'var(--severity-4)' : 'var(--severity-1)',
          }}
        >
          {notification.isError ? <AlertCircle size={16} /> : <CheckCircle size={16} />}
          <span>{notification.message}</span>
        </div>
      )}

      {/* ── Section: Social & Web Sources ── */}
      <Card>
        <div style={{ padding: '1rem 1.25rem', borderBottom: '1px solid var(--bg-border)', display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '0.5rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
            <Share2 size={18} color="var(--cat-thunderstorm)" />
            <div>
              <h2 style={{ margin: 0, fontSize: 'var(--text-base)', fontWeight: 700, color: 'var(--text-primary)' }}>
                SOCIAL MEDIA & WEB HASHTAG INGESTION
              </h2>
              <p style={{ margin: 0, fontSize: 'var(--text-xs)', color: 'var(--text-secondary)' }}>
                Automated weather signal harvesting from Mastodon, RSS/Atom bulletins, permitted web sources & JSON feeds
              </p>
            </div>
          </div>
          <div style={{ display: 'flex', gap: '0.5rem' }}>
            <Button size="sm" variant="secondary" icon={<Play size={13} />} onClick={() => handleOpenTest()}>
              Smoke Test Source
            </Button>
          </div>
        </div>

        {/* Configured Hashtags Bar */}
        <div style={{ padding: '0.75rem 1.25rem', backgroundColor: 'var(--bg-surface)', borderBottom: '1px solid var(--bg-border)' }}>
          <div style={{ fontSize: 'var(--text-xs)', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '0.4rem', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
            <span>Active Weather Hashtags Registry ({[
              '#IMD', '#Weather', '#WeatherAlert', '#HeavyRain', '#Rainfall', '#Thunderstorm',
              '#Flood', '#Heatwave', '#Fog', '#DustStorm', '#StrongWinds', '#Cyclone',
              '#Monsoon', '#IndiaWeather', '#IndianWeather', '#Monsoon2026', '#MumbaiRain',
              '#DelhiWeather', '#OdishaWeather', '#BengaluruRain', '#HyderabadRain',
              '#KolkataRain', '#ChennaiRain', '#FloodIndia', '#HeatwaveIndia'
            ].length}):</span>
          </div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.35rem' }}>
            {[
              '#IMD', '#Weather', '#WeatherAlert', '#HeavyRain', '#Rainfall', '#Thunderstorm',
              '#Flood', '#Heatwave', '#Fog', '#DustStorm', '#StrongWinds', '#Cyclone',
              '#Monsoon', '#IndiaWeather', '#IndianWeather', '#Monsoon2026', '#MumbaiRain',
              '#DelhiWeather', '#OdishaWeather', '#BengaluruRain', '#HyderabadRain',
              '#KolkataRain', '#ChennaiRain', '#FloodIndia', '#HeatwaveIndia'
            ].map((ht) => (
              <span
                key={ht}
                style={{
                  padding: '0.15rem 0.45rem',
                  borderRadius: 'var(--radius-sm)',
                  fontSize: '11px',
                  fontWeight: 600,
                  backgroundColor: 'rgba(59, 130, 246, 0.12)',
                  color: 'var(--brand-blue)',
                  border: '1px solid rgba(59, 130, 246, 0.25)',
                }}
              >
                {ht}
              </span>
            ))}
          </div>
        </div>

        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: 'var(--text-sm)' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid var(--bg-border)', color: 'var(--text-muted)', fontSize: 'var(--text-xs)' }}>
                <th style={{ padding: '0.75rem 1rem' }}>Source</th>
                <th style={{ padding: '0.75rem 1rem' }}>Type</th>
                <th style={{ padding: '0.75rem 1rem' }}>Status</th>
                <th style={{ padding: '0.75rem 1rem' }}>Last fetch</th>
                <th style={{ padding: '0.75rem 1rem' }}>Fetched</th>
                <th style={{ padding: '0.75rem 1rem' }}>Weather Rel.</th>
                <th style={{ padding: '0.75rem 1rem' }}>Accepted (India)</th>
                <th style={{ padding: '0.75rem 1rem' }}>Quarantined</th>
                <th style={{ padding: '0.75rem 1rem' }}>Rejected</th>
                <th style={{ padding: '0.75rem 1rem' }}>Duplicates</th>
                <th style={{ padding: '0.75rem 1rem' }}>Rate-limit</th>
                <th style={{ padding: '0.75rem 1rem', textAlign: 'right' }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {socialWebSources.length === 0 ? (
                <tr>
                  <td colSpan={12} style={{ padding: '2rem 1rem', textAlign: 'center', color: 'var(--text-secondary)' }}>
                    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '0.5rem' }}>
                      <Info size={24} color="var(--text-muted)" />
                      <span>No social or web providers actively registered. Use the Smoke Test tool to validate external endpoints.</span>
                    </div>
                  </td>
                </tr>
              ) : (
                socialWebSources.map((sw) => {
                  const badge = getStatusBadgeStyle(sw.status);
                  const isRateLimited = sw.status.toUpperCase() === 'DEGRADED' && (sw.metrics?.last_error || '').toLowerCase().includes('rate limit');
                  const totalQuarantined = (sw.metrics?.quarantined_foreign || 0) + (sw.metrics?.quarantined_unknown_location || 0);
                  return (
                    <tr key={sw.provider_id} style={{ borderBottom: '1px solid var(--bg-border)' }}>
                      <td style={{ padding: '0.75rem 1rem', fontWeight: 600, color: 'var(--text-primary)' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                          {getSourceIcon(sw.source_type)}
                          <span>{sw.name}</span>
                        </div>
                      </td>
                      <td style={{ padding: '0.75rem 1rem', fontSize: 'var(--text-xs)', color: 'var(--text-secondary)' }}>
                        <span style={{ padding: '0.15rem 0.5rem', borderRadius: 'var(--radius-sm)', backgroundColor: 'var(--bg-card)', border: '1px solid var(--bg-border)' }}>
                          {sw.source_type}
                        </span>
                      </td>
                      <td style={{ padding: '0.75rem 1rem' }}>
                        <span
                          style={{
                            padding: '0.15rem 0.6rem',
                            borderRadius: 'var(--radius-full)',
                            fontSize: '11px',
                            fontWeight: 700,
                            backgroundColor: badge.bg,
                            color: badge.fg,
                            border: `1px solid ${badge.border}`,
                          }}
                        >
                          {sw.status}
                        </span>
                      </td>
                      <td style={{ padding: '0.75rem 1rem', fontSize: 'var(--text-xs)', color: 'var(--text-secondary)' }}>
                        {sw.metrics?.last_successful_fetch ? new Date(sw.metrics.last_successful_fetch).toLocaleTimeString() : 'Never'}
                      </td>
                      <td style={{ padding: '0.75rem 1rem', color: 'var(--text-primary)', fontSize: 'var(--text-xs)', fontWeight: 600 }}>
                        {sw.metrics?.records_fetched || 0}
                      </td>
                      <td style={{ padding: '0.75rem 1rem', color: 'var(--brand-blue)', fontSize: 'var(--text-xs)', fontWeight: 600 }}>
                        {sw.metrics?.weather_relevant || 0}
                      </td>
                      <td style={{ padding: '0.75rem 1rem', color: 'var(--severity-1)', fontSize: 'var(--text-xs)', fontWeight: 600 }}>
                        {sw.metrics?.accepted_india || 0}
                      </td>
                      <td style={{ padding: '0.75rem 1rem', color: 'var(--severity-2)', fontSize: 'var(--text-xs)' }}>
                        <span title={`Foreign: ${sw.metrics?.quarantined_foreign || 0}, Unknown: ${sw.metrics?.quarantined_unknown_location || 0}`}>
                          {totalQuarantined}
                        </span>
                      </td>
                      <td style={{ padding: '0.75rem 1rem', color: 'var(--text-muted)', fontSize: 'var(--text-xs)' }}>
                        {sw.metrics?.rejected_non_weather || 0}
                      </td>
                      <td style={{ padding: '0.75rem 1rem', color: 'var(--text-secondary)', fontSize: 'var(--text-xs)' }}>
                        {sw.metrics?.duplicates || 0}
                      </td>
                      <td style={{ padding: '0.75rem 1rem', fontSize: 'var(--text-xs)' }}>
                        <span style={{ color: isRateLimited ? 'var(--severity-2)' : 'var(--severity-1)', fontWeight: 600 }}>
                          {isRateLimited ? 'LIMITED' : 'NORMAL'}
                        </span>
                      </td>
                      <td style={{ padding: '0.75rem 1rem', textAlign: 'right' }}>
                        <Button
                          size="sm"
                          variant="secondary"
                          icon={<Play size={12} />}
                          onClick={() => handleOpenTest(sw)}
                        >
                          Test
                        </Button>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </Card>

      {/* ── Section: Core Registered Telemetry Connectors ── */}
      <div>
        <div style={{ marginBottom: '0.75rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <Activity size={18} color="var(--brand-blue)" />
          <h2 style={{ margin: 0, fontSize: 'var(--text-lg)', fontWeight: 700, color: 'var(--text-primary)' }}>
            Core Telemetry Pipelines
          </h2>
        </div>

        {loading ? (
          <TableSkeleton rows={6} />
        ) : sources.length === 0 ? (
          <EmptyState
            title="No Connectors Registered"
            message="No active or dormant telemetry connectors found in database."
            action={
              <Button size="sm" variant="primary" onClick={handleOpenAdd}>
                Add First Connector
              </Button>
            }
          />
        ) : (
          <Card>
            <div style={{ overflowX: 'auto' }}>
              <table
                style={{
                  width: '100%',
                  borderCollapse: 'collapse',
                  textAlign: 'left',
                  fontSize: 'var(--text-sm)',
                }}
              >
                <thead>
                  <tr style={{ borderBottom: '1px solid var(--bg-border)', color: 'var(--text-muted)', fontSize: 'var(--text-xs)' }}>
                    <th style={{ padding: '0.75rem 0.5rem' }}>Connector Name</th>
                    <th style={{ padding: '0.75rem 0.5rem' }}>Source Type</th>
                    <th style={{ padding: '0.75rem 0.5rem' }}>Pipeline Mode</th>
                    <th style={{ padding: '0.75rem 0.5rem' }}>Trust Score</th>
                    <th style={{ padding: '0.75rem 0.5rem' }}>Health Status</th>
                    <th style={{ padding: '0.75rem 0.5rem' }}>Ingested (1h)</th>
                    <th style={{ padding: '0.75rem 0.5rem' }}>State</th>
                    <th style={{ padding: '0.75rem 0.5rem', textAlign: 'right' }}>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {sources.map((src) => {
                    const isHealthy = (src.health_status || 'HEALTHY').toUpperCase() === 'HEALTHY';
                    return (
                      <tr
                        key={src.id}
                        style={{
                          borderBottom: '1px solid var(--bg-border)',
                          opacity: src.is_active ? 1 : 0.65,
                        }}
                      >
                        <td style={{ padding: '0.75rem 0.5rem', fontWeight: 600, color: 'var(--text-primary)' }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                            {getSourceIcon(src.source_type)}
                            <span>{src.name}</span>
                          </div>
                        </td>
                        <td style={{ padding: '0.75rem 0.5rem', fontSize: 'var(--text-xs)', color: 'var(--text-secondary)' }}>
                          {src.source_type}
                        </td>
                        <td style={{ padding: '0.75rem 0.5rem' }}>
                          {src.is_demo ? (
                            <DemoBadge />
                          ) : (
                            <span
                              style={{
                                padding: '0.15rem 0.5rem',
                                borderRadius: 'var(--radius-sm)',
                                fontSize: '10px',
                                fontWeight: 700,
                                backgroundColor: 'rgba(34, 197, 94, 0.15)',
                                color: 'var(--severity-1)',
                              }}
                            >
                              REAL
                            </span>
                          )}
                        </td>
                        <td style={{ padding: '0.75rem 0.5rem', fontWeight: 600, color: 'var(--brand-blue)' }}>
                          {Math.round(src.trust_score * 100)}%
                        </td>
                        <td style={{ padding: '0.75rem 0.5rem' }}>
                          <span
                            style={{
                              padding: '0.15rem 0.5rem',
                              borderRadius: 'var(--radius-full)',
                              fontSize: '10px',
                              fontWeight: 700,
                              backgroundColor: isHealthy ? 'rgba(34, 197, 94, 0.15)' : 'rgba(239, 68, 68, 0.15)',
                              color: isHealthy ? 'var(--severity-1)' : 'var(--severity-4)',
                            }}
                          >
                            {src.health_status || 'HEALTHY'}
                          </span>
                        </td>
                        <td style={{ padding: '0.75rem 0.5rem', color: 'var(--text-primary)' }}>
                          {src.records_ingested_last_hour ?? 0}
                        </td>
                        <td style={{ padding: '0.75rem 0.5rem' }}>
                          <span
                            style={{
                              fontSize: '11px',
                              fontWeight: 600,
                              color: src.is_active ? 'var(--severity-1)' : 'var(--text-muted)',
                            }}
                          >
                            {src.is_active ? 'ENABLED' : 'DISABLED'}
                          </span>
                        </td>
                        <td style={{ padding: '0.75rem 0.5rem', textAlign: 'right' }}>
                          <div style={{ display: 'inline-flex', gap: '0.4rem' }}>
                            <Button
                              size="sm"
                              variant="secondary"
                              icon={<Edit size={13} />}
                              onClick={() => handleOpenEdit(src)}
                              title="Configure connector"
                            >
                              Edit
                            </Button>
                            <Button
                              size="sm"
                              variant={src.is_active ? 'danger' : 'primary'}
                              icon={<Power size={13} />}
                              loading={actionLoading === src.id}
                              onClick={() => handleToggle(src)}
                              title={src.is_active ? 'Disable connector' : 'Enable connector'}
                            >
                              {src.is_active ? 'Disable' : 'Enable'}
                            </Button>
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </Card>
        )}
      </div>

      {/* ── Add / Edit Core Connector Modal ── */}
      {showModal && (
        <div
          style={{
            position: 'fixed',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            backgroundColor: 'rgba(0,0,0,0.65)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 1000,
            padding: '1rem',
          }}
        >
          <div
            style={{
              backgroundColor: 'var(--bg-surface)',
              border: '1px solid var(--bg-border)',
              borderRadius: 'var(--radius-lg)',
              maxWidth: '500px',
              width: '100%',
              padding: '1.5rem',
              boxShadow: 'var(--shadow-xl)',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '1.25rem' }}>
              <Database size={20} color="var(--brand-blue)" />
              <h3 style={{ margin: 0, fontSize: 'var(--text-lg)', fontWeight: 700, color: 'var(--text-primary)' }}>
                {modalMode === 'ADD' ? 'Register New Data Connector' : 'Configure Connector'}
              </h3>
            </div>

            <form onSubmit={handleModalSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
              <div>
                <label style={{ display: 'block', fontSize: 'var(--text-xs)', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '0.35rem' }}>
                  Connector Name
                </label>
                <Input
                  placeholder="e.g. IMD Radar Stream Kolkata"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  required
                />
              </div>

              <div>
                <label style={{ display: 'block', fontSize: 'var(--text-xs)', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '0.35rem' }}>
                  Source Category
                </label>
                <Select
                  value={sourceType}
                  onChange={(e) => setSourceType(e.target.value)}
                  options={[
                    { value: 'WEATHER_API', label: 'Meteorological API (IMD / ECMWF)' },
                    { value: 'GOVERNMENT_API', label: 'Government Disaster Portal (NDMA)' },
                    { value: 'RSS_FEED', label: 'RSS/Atom Weather Syndication' },
                    { value: 'PUBLIC_WEB', label: 'Permitted Public Weather Webpage' },
                    { value: 'PUBLIC_JSON', label: 'Public Weather JSON Endpoint' },
                    { value: 'SOCIAL_API', label: 'Authorized Social Media API' },
                    { value: 'CITIZEN', label: 'Citizen Observational Reports' },
                  ]}
                />
              </div>

              <div>
                <label style={{ display: 'block', fontSize: 'var(--text-xs)', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '0.35rem' }}>
                  Connector Driver Class
                </label>
                <Input
                  placeholder="e.g. SocialWebConnector"
                  value={connectorClass}
                  onChange={(e) => setConnectorClass(e.target.value)}
                  required
                />
              </div>

              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <input
                  type="checkbox"
                  id="is_demo_toggle"
                  checked={isDemo}
                  onChange={(e) => setIsDemo(e.target.checked)}
                />
                <label htmlFor="is_demo_toggle" style={{ fontSize: 'var(--text-xs)', color: 'var(--text-secondary)' }}>
                  Mark as Demo / Synthetic Feed
                </label>
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.75rem', marginTop: '0.5rem' }}>
                <Button variant="secondary" size="sm" type="button" onClick={() => setShowModal(false)}>
                  Cancel
                </Button>
                <Button variant="primary" size="sm" type="submit" loading={modalSubmitting} disabled={!name.trim()}>
                  {modalMode === 'ADD' ? 'Create Connector' : 'Save Changes'}
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ── Social & Web Smoke Test Modal ── */}
      {showTestModal && (
        <div
          style={{
            position: 'fixed',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            backgroundColor: 'rgba(0,0,0,0.65)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 1000,
            padding: '1rem',
          }}
        >
          <div
            style={{
              backgroundColor: 'var(--bg-surface)',
              border: '1px solid var(--bg-border)',
              borderRadius: 'var(--radius-lg)',
              maxWidth: '650px',
              width: '100%',
              maxHeight: '90vh',
              overflowY: 'auto',
              padding: '1.5rem',
              boxShadow: 'var(--shadow-xl)',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '1.25rem' }}>
              <Play size={20} color="var(--cat-thunderstorm)" />
              <div>
                <h3 style={{ margin: 0, fontSize: 'var(--text-lg)', fontWeight: 700, color: 'var(--text-primary)' }}>
                  Social & Web Source Live Smoke Test
                </h3>
                <p style={{ margin: 0, fontSize: 'var(--text-xs)', color: 'var(--text-secondary)' }}>
                  Verify live endpoint reachability, hashtag matching, and normalization without persisting test records.
                </p>
              </div>
            </div>

            <form onSubmit={handleRunSmokeTest} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
              <div>
                <label style={{ display: 'block', fontSize: 'var(--text-xs)', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '0.35rem' }}>
                  Source Type
                </label>
                <Select
                  value={testSourceType}
                  onChange={(e) => setTestSourceType(e.target.value)}
                  options={[
                    { value: 'RSS_FEED', label: 'RSS / Atom Weather Feed' },
                    { value: 'PUBLIC_JSON', label: 'Public Weather JSON Endpoint' },
                    { value: 'PUBLIC_WEB', label: 'Permitted Public Weather Webpage' },
                    { value: 'SOCIAL_API', label: 'Authorized Social Media API (Bearer Token / Key)' },
                  ]}
                />
              </div>

              <div>
                <label style={{ display: 'block', fontSize: 'var(--text-xs)', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '0.35rem' }}>
                  Endpoint URL / Feed URL
                </label>
                <Input
                  placeholder="e.g. https://mausam.imd.gov.in/rss/alerts.xml or https://api.social.net/v1/timeline"
                  value={testUrl}
                  onChange={(e) => setTestUrl(e.target.value)}
                  required
                />
              </div>

              {testSourceType === 'SOCIAL_API' && (
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem' }}>
                  <div>
                    <label style={{ display: 'block', fontSize: 'var(--text-xs)', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '0.35rem' }}>
                      API Key (Optional)
                    </label>
                    <Input
                      type="password"
                      placeholder="X-API-Key value"
                      value={testApiKey}
                      onChange={(e) => setTestApiKey(e.target.value)}
                    />
                  </div>
                  <div>
                    <label style={{ display: 'block', fontSize: 'var(--text-xs)', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '0.35rem' }}>
                      Bearer Token (Optional)
                    </label>
                    <Input
                      type="password"
                      placeholder="Bearer token"
                      value={testApiToken}
                      onChange={(e) => setTestApiToken(e.target.value)}
                    />
                  </div>
                </div>
              )}

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.75rem', marginTop: '0.5rem' }}>
                <Button variant="secondary" size="sm" type="button" onClick={() => setShowTestModal(false)}>
                  Close
                </Button>
                <Button variant="primary" size="sm" type="submit" loading={testing} disabled={!testUrl.trim()}>
                  Execute Smoke Test
                </Button>
              </div>
            </form>

            {/* Test Result Display */}
            {testResult && (
              <div
                style={{
                  marginTop: '1.5rem',
                  padding: '1rem',
                  borderRadius: 'var(--radius-md)',
                  backgroundColor: 'var(--bg-card)',
                  border: `1px solid ${testResult.success ? 'rgba(34, 197, 94, 0.4)' : 'rgba(239, 68, 68, 0.4)'}`,
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.75rem' }}>
                  <span style={{ fontWeight: 700, fontSize: 'var(--text-sm)', color: testResult.success ? 'var(--severity-1)' : 'var(--severity-4)' }}>
                    LIVE SOURCE TEST = {testResult.status}
                  </span>
                  <span style={{ fontSize: 'var(--text-xs)', color: 'var(--text-secondary)' }}>
                    Latency: {testResult.latency_ms}ms
                  </span>
                </div>

                {/* Telemetry Breakdown Grid */}
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '0.5rem', marginBottom: '0.75rem' }}>
                  <div style={{ padding: '0.5rem', backgroundColor: 'var(--bg-surface)', borderRadius: 'var(--radius-sm)', textAlign: 'center' }}>
                    <div style={{ fontSize: '10px', color: 'var(--text-muted)' }}>FETCHED</div>
                    <div style={{ fontSize: 'var(--text-sm)', fontWeight: 700, color: 'var(--text-primary)' }}>{testResult.records_fetched ?? testResult.records_found}</div>
                  </div>
                  <div style={{ padding: '0.5rem', backgroundColor: 'var(--bg-surface)', borderRadius: 'var(--radius-sm)', textAlign: 'center' }}>
                    <div style={{ fontSize: '10px', color: 'var(--text-muted)' }}>WEATHER REL.</div>
                    <div style={{ fontSize: 'var(--text-sm)', fontWeight: 700, color: 'var(--brand-blue)' }}>{testResult.weather_relevant ?? 0}</div>
                  </div>
                  <div style={{ padding: '0.5rem', backgroundColor: 'var(--bg-surface)', borderRadius: 'var(--radius-sm)', textAlign: 'center' }}>
                    <div style={{ fontSize: '10px', color: 'var(--text-muted)' }}>ACCEPTED (INDIA)</div>
                    <div style={{ fontSize: 'var(--text-sm)', fontWeight: 700, color: 'var(--severity-1)' }}>{testResult.accepted_india ?? 0}</div>
                  </div>
                  <div style={{ padding: '0.5rem', backgroundColor: 'var(--bg-surface)', borderRadius: 'var(--radius-sm)', textAlign: 'center' }}>
                    <div style={{ fontSize: '10px', color: 'var(--text-muted)' }}>REJECTED</div>
                    <div style={{ fontSize: 'var(--text-sm)', fontWeight: 700, color: 'var(--text-muted)' }}>{testResult.rejected_non_weather ?? 0}</div>
                  </div>
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '0.5rem', marginBottom: '0.75rem' }}>
                  <div style={{ padding: '0.4rem', backgroundColor: 'var(--bg-surface)', borderRadius: 'var(--radius-sm)', textAlign: 'center' }}>
                    <div style={{ fontSize: '10px', color: 'var(--text-muted)' }}>QUARANTINED (FOREIGN)</div>
                    <div style={{ fontSize: 'var(--text-xs)', fontWeight: 700, color: 'var(--severity-2)' }}>{testResult.quarantined_foreign ?? 0}</div>
                  </div>
                  <div style={{ padding: '0.4rem', backgroundColor: 'var(--bg-surface)', borderRadius: 'var(--radius-sm)', textAlign: 'center' }}>
                    <div style={{ fontSize: '10px', color: 'var(--text-muted)' }}>QUARANTINED (UNKNOWN)</div>
                    <div style={{ fontSize: 'var(--text-xs)', fontWeight: 700, color: 'var(--severity-2)' }}>{testResult.quarantined_unknown_location ?? 0}</div>
                  </div>
                  <div style={{ padding: '0.4rem', backgroundColor: 'var(--bg-surface)', borderRadius: 'var(--radius-sm)', textAlign: 'center' }}>
                    <div style={{ fontSize: '10px', color: 'var(--text-muted)' }}>DUPLICATES</div>
                    <div style={{ fontSize: 'var(--text-xs)', fontWeight: 700, color: 'var(--text-secondary)' }}>{testResult.duplicates ?? 0}</div>
                  </div>
                </div>

                {testResult.error_message && (
                  <p style={{ margin: '0.25rem 0', fontSize: 'var(--text-xs)', color: 'var(--severity-4)' }}>
                    Error: {testResult.error_message}
                  </p>
                )}

                {testResult.sample_records && testResult.sample_records.length > 0 && (
                  <div style={{ marginTop: '0.75rem' }}>
                    <span style={{ fontSize: 'var(--text-xs)', fontWeight: 600, color: 'var(--text-secondary)' }}>
                      Normalized Sample Event Preview:
                    </span>
                    <pre
                      style={{
                        margin: '0.25rem 0 0 0',
                        padding: '0.75rem',
                        borderRadius: 'var(--radius-sm)',
                        backgroundColor: 'var(--bg-surface)',
                        fontSize: '11px',
                        overflowX: 'auto',
                        color: 'var(--text-primary)',
                      }}
                    >
                      {JSON.stringify(testResult.sample_records[0], null, 2)}
                    </pre>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
