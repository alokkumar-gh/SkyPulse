/**
 * Sources Page — Signature Intelligence Feature: Weather Source Reputation Graph
 * =============================================================================
 * "Trust should evolve from evidence, not from a fixed label."
 */
import React, { useState } from 'react';
import { SourceReputationPanel } from '../components/sources/SourceReputationPanel';
import { Card, Button } from '../components/ui/Primitives';
import { Shield, Radio, Globe, Smartphone, ShieldCheck, Activity } from 'lucide-react';

export const Sources: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'reputation' | 'connectors'>('reputation');

  const connectorOverview = [
    {
      name: 'IMD National Radar Network',
      type: 'Official Meteorological Feed',
      trustScore: 0.95,
      frequency: 'Every 10 minutes',
      status: 'OPERATIONAL',
      icon: <Radio size={20} color="var(--brand-blue)" />,
    },
    {
      name: 'WeatherAPI Global Streams',
      type: 'Commercial API Feed',
      trustScore: 0.88,
      frequency: 'Every 15 minutes',
      status: 'OPERATIONAL',
      icon: <Globe size={20} color="var(--cat-thunderstorm)" />,
    },
    {
      name: 'Citizen Mobile Ground Network',
      type: 'Crowdsourced Reports',
      trustScore: 0.76,
      frequency: 'Real-time Event Driven',
      status: 'OPERATIONAL',
      icon: <Smartphone size={20} color="var(--severity-1)" />,
    },
    {
      name: 'State Disaster Management Units (SDMA)',
      type: 'Government Emergency Webhook',
      trustScore: 0.98,
      frequency: 'Instant Alerts',
      status: 'OPERATIONAL',
      icon: <ShieldCheck size={20} color="var(--severity-4)" />,
    },
  ];

  return (
    <div
      style={{
        padding: '1.5rem',
        maxWidth: '1280px',
        margin: '0 auto',
        width: '100%',
        display: 'flex',
        flexDirection: 'column',
        gap: '1.25rem',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '0.75rem' }}>
        <div>
          <h1 style={{ margin: 0, fontSize: 'var(--text-2xl)', fontWeight: 700, color: 'var(--text-primary)' }}>
            Data Sources & Reputation Graph
          </h1>
          <p style={{ margin: '0.25rem 0 0 0', fontSize: 'var(--text-sm)', color: 'var(--text-secondary)' }}>
            Dynamic evidence-based reliability tracking, historical verification outcomes, and connector health
          </p>
        </div>

        {/* View Switcher Tabs */}
        <div style={{ display: 'flex', gap: '0.25rem', padding: '3px', backgroundColor: 'var(--bg-elevated)', borderRadius: 'var(--radius-md)' }}>
          <Button
            size="sm"
            variant={activeTab === 'reputation' ? 'primary' : 'ghost'}
            onClick={() => setActiveTab('reputation')}
          >
            <Shield size={14} />
            Reputation Graph
          </Button>
          <Button
            size="sm"
            variant={activeTab === 'connectors' ? 'primary' : 'ghost'}
            onClick={() => setActiveTab('connectors')}
          >
            <Activity size={14} />
            Connectors Overview
          </Button>
        </div>
      </div>

      {/* Main Content View */}
      {activeTab === 'reputation' ? (
        <SourceReputationPanel />
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: '1.25rem' }}>
          {connectorOverview.map((src) => (
            <Card key={src.name}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1rem' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                  <div style={{ padding: '0.5rem', backgroundColor: 'var(--bg-elevated)', borderRadius: 'var(--radius-md)' }}>
                    {src.icon}
                  </div>
                  <div>
                    <h3 style={{ margin: 0, fontSize: 'var(--text-base)', fontWeight: 600 }}>{src.name}</h3>
                    <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-muted)' }}>{src.type}</div>
                  </div>
                </div>
                <span style={{ fontSize: '10px', color: 'var(--severity-1)', fontWeight: 700, backgroundColor: 'rgba(34, 197, 94, 0.15)', padding: '2px 6px', borderRadius: '4px' }}>
                  {src.status}
                </span>
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', fontSize: 'var(--text-xs)', borderTop: '1px solid var(--border-subtle)', paddingTop: '0.75rem' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span style={{ color: 'var(--text-secondary)' }}>Trust Score</span>
                  <span style={{ color: 'var(--brand-blue)', fontWeight: 600 }}>{Math.round(src.trustScore * 100)}%</span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span style={{ color: 'var(--text-secondary)' }}>Ingestion Cadence</span>
                  <span style={{ color: 'var(--text-primary)' }}>{src.frequency}</span>
                </div>
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
};
