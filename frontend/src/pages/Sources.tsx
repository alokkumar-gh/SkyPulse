/**
 * SkyPulse Sources — Redesign
 * "Weather Source Reputation & Connector Health"
 *
 * Design:
 * - Trust-first layout: status indicators are restrained dots, not cards
 * - Tab rail uses monospace uppercase labels
 * - Editorial page header with section label
 */
import React, { useState } from 'react';
import { SourceReputationPanel } from '../components/sources/SourceReputationPanel';
import { SocialWebPanel } from '../components/sources/SocialWebPanel';
import { ConnectorManagementPanel } from '../components/sources/ConnectorManagementPanel';
import { Shield, Radio, Globe } from 'lucide-react';

type Tab = 'reputation' | 'connectors' | 'social';

const TABS: { id: Tab; label: string; icon: React.ReactNode; title: string; sub: string }[] = [
  {
    id: 'reputation',
    label: 'Reputation Graph',
    icon: <Shield size={13} />,
    title: 'Source Reputation Intelligence',
    sub: 'Evidence-based reliability scores, historical verification outcomes, contradiction tracking',
  },
  {
    id: 'connectors',
    label: 'Connectors',
    icon: <Radio size={13} />,
    title: 'Ingestion Connectors',
    sub: 'Live health, throughput, and configuration for all data source adapters',
  },
  {
    id: 'social',
    label: 'Social & Web',
    icon: <Globe size={13} />,
    title: 'Social & Web Intelligence',
    sub: 'Google News RSS, regional feeds, and social signal discovery channels',
  },
];

export const Sources: React.FC = () => {
  const [activeTab, setActiveTab] = useState<Tab>('reputation');
  const current = TABS.find((t) => t.id === activeTab)!;

  return (
    <div className="page-root" style={{ overflowY: 'auto', overflowX: 'hidden' }}>

      {/* ── Page Header ──────────────────────────────────────────── */}
      <div className="page-header" style={{ flexDirection: 'column', alignItems: 'flex-start', gap: '0.875rem', padding: '1rem 1.5rem', flexShrink: 0 }}>
        <div>
          <div style={{
            fontFamily: 'var(--font-mono)',
            fontSize: 'var(--text-2xs)',
            color: 'var(--text-muted)',
            letterSpacing: '0.14em',
            textTransform: 'uppercase',
            marginBottom: '0.25rem',
          }}>
            Data Ecosystem
          </div>
          <h1 className="page-title">{current.title}</h1>
          <div className="page-subtitle">{current.sub}</div>
        </div>

        {/* Tab rail */}
        <div className="tab-rail" style={{ padding: '0', width: '100%', borderBottom: 'none', overflowX: 'auto', flexWrap: 'wrap', gap: '0.25rem' }}>
          {TABS.map((tab) => {
            const isActive = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                className={`tab-item ${isActive ? 'active' : ''}`}
                onClick={() => setActiveTab(tab.id)}
                style={{ background: 'none', border: 'none' }}
              >
                {tab.icon}
                {tab.label}
              </button>
            );
          })}
        </div>
      </div>

      {/* Hairline separator */}
      <div style={{ height: 1, background: 'var(--border-hairline)', flexShrink: 0 }} />

      {/* ── Content ──────────────────────────────────────────────── */}
      <div style={{ flex: 1, padding: '1.25rem 1.5rem 3rem', minHeight: 0, width: '100%' }}>
        {activeTab === 'reputation'  && <SourceReputationPanel />}
        {activeTab === 'connectors' && <ConnectorManagementPanel />}
        {activeTab === 'social'     && <SocialWebPanel />}
      </div>
    </div>
  );
};
