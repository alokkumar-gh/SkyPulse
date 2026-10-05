/**
 * DWEGView Page — Phase 10
 * =======================
 * Dynamic Weather Evidence Graph (DWEG) & Weather Event DNA Intelligence Center.
 * Integrates:
 * - Event Header (Category, Severity, Status, Confidence, Location, ID, Evidence/Source counts)
 * - Interactive Force-Directed Topology Graph (D3.js with zoom/pan/drag/markers/filters)
 * - Deep Weather Event DNA Profiler (Decomposition, 6D Coverage, Genesis, Kinematics)
 * - MapLibre Confidence Field Heatmap
 * - Spatio-Temporal Kinematic Propagation Timeline & Vector
 * - Explainable Multi-Source Evidence Chain Narrative & Step Provenance
 * - Source Reputation & Telemetry Provenance Breakdown
 * - Real-Time Node Inspector for Evidence Reports, Sources, Locations, and Events
 */

import React, { useEffect, useState, useMemo } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import {
  GitBranch,
  Dna,
  Layers,
  Compass,
  Database,
  AlertTriangle,
  ArrowLeft,
  RefreshCw,
  Activity,
  MapPin,
  Clock,
  Copy,
  Check,
  Filter,
} from 'lucide-react';
import { Card, Button } from '../components/ui/Primitives';
import {
  CategoryBadge,
  SeverityBadge,
  VerificationBadge,
  ConfidenceBar,
  DemoBadge,
} from '../components/ui/Badges';
import { EvidenceGraph } from '../components/dweg/EvidenceGraph';
import { ConfidenceFieldLayer } from '../components/dweg/ConfidenceFieldLayer';
import { PropagationTimeline } from '../components/dweg/PropagationTimeline';
import { EvidenceChainPanel } from '../components/dweg/EvidenceChainPanel';
import { WeatherEventDNA } from '../components/events/WeatherEventDNA';
import { normalizeEvent } from '../store/eventsStore';
import { dwegAPI, eventsAPI } from '../utils/api';
import type {
  WeatherEvent,
  DWEGNode,
  DWEGGraphResponse,
  ConfidenceFieldResponse,
  PropagationTimelineResponse,
  EvidenceChainResponse,
  PropagationAlert,
} from '../types';

type DWEGTab = 'GRAPH' | 'DNA' | 'HEATMAP' | 'PROPAGATION' | 'SOURCES';

export const DWEGView: React.FC = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();

  // Active events list & selected event
  const [activeEvents, setActiveEvents] = useState<WeatherEvent[]>([]);
  const [selectedEventId, setSelectedEventId] = useState<string>('');
  const [selectedEvent, setSelectedEvent] = useState<WeatherEvent | null>(null);

  // DWEG Data States
  const [graphData, setGraphData] = useState<DWEGGraphResponse | null>(null);
  const [confidenceField, setConfidenceField] = useState<ConfidenceFieldResponse | null>(null);
  const [timeline, setTimeline] = useState<PropagationTimelineResponse | null>(null);
  const [evidenceChain, setEvidenceChain] = useState<EvidenceChainResponse | null>(null);
  const [propagationAlerts, setPropagationAlerts] = useState<PropagationAlert[]>([]);

  // UI States
  const [activeTab, setActiveTab] = useState<DWEGTab>('GRAPH');
  const [selectedNode, setSelectedNode] = useState<DWEGNode | null>(null);
  const [nodeTypeFilter, setNodeTypeFilter] = useState<string>('ALL');
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [copiedId, setCopiedId] = useState<boolean>(false);

  // 1. Initial Load: Fetch active events and alerts
  useEffect(() => {
    let isMounted = true;
    async function loadInitialData() {
      try {
        const [eventsRes, alertsRes] = await Promise.all([
          eventsAPI.list(undefined, 1, 50),
          dwegAPI.propagationAlerts(),
        ]);

        if (!isMounted) return;

        const rawList = eventsRes?.results || [];
        const eventsList: WeatherEvent[] = rawList.map(normalizeEvent).filter(Boolean);
        setActiveEvents(eventsList);
        setPropagationAlerts(alertsRes?.alerts || []);

        // Pick event from URL param or first available
        const paramId = searchParams.get('eventId');
        if (paramId && eventsList.some((e) => e.id === paramId)) {
          setSelectedEventId(paramId);
        } else if (eventsList.length > 0) {
          setSelectedEventId(eventsList[0].id);
          setSearchParams({ eventId: eventsList[0].id }, { replace: true });
        }
      } catch (err: any) {
        console.error('Failed to load initial DWEG events:', err);
      }
    }

    loadInitialData();
    return () => {
      isMounted = false;
    };
  }, []);

  // 2. Fetch DWEG Intelligence data when selectedEventId changes
  useEffect(() => {
    if (!selectedEventId) return;

    let isMounted = true;
    setIsLoading(true);
    setSelectedNode(null);

    // Update selected event entity
    const foundEvt = activeEvents.find((e) => e.id === selectedEventId) || null;
    setSelectedEvent(foundEvt);

    async function fetchDWEGData() {
      try {
        const [graphRes, confRes, timeRes, chainRes] = await Promise.allSettled([
          dwegAPI.graph(selectedEventId),
          dwegAPI.confidenceField(selectedEventId),
          dwegAPI.propagationTimeline(selectedEventId),
          dwegAPI.evidenceChain(selectedEventId),
        ]);

        if (!isMounted) return;

        if (graphRes.status === 'fulfilled' && graphRes.value) setGraphData(graphRes.value);
        if (confRes.status === 'fulfilled' && confRes.value) setConfidenceField(confRes.value);
        if (timeRes.status === 'fulfilled' && timeRes.value) setTimeline(timeRes.value);
        if (chainRes.status === 'fulfilled' && chainRes.value) setEvidenceChain(chainRes.value);
      } catch (err: any) {
        console.error('Error loading DWEG graph intelligence:', err);
      } finally {
        if (isMounted) setIsLoading(false);
      }
    }

    fetchDWEGData();
    return () => {
      isMounted = false;
    };
  }, [selectedEventId, activeEvents]);

  const handleSelectEvent = (eventId: string) => {
    setSelectedEventId(eventId);
    setSearchParams({ eventId });
  };

  const handleCopyId = (id: string) => {
    navigator.clipboard.writeText(id);
    setCopiedId(true);
    setTimeout(() => setCopiedId(false), 2000);
  };

  // Identify propagation warning for current event
  const activeAlertForEvent = useMemo(() => {
    return propagationAlerts.find((a) => a.event_id === selectedEventId);
  }, [propagationAlerts, selectedEventId]);

  // Filter graph nodes
  const filteredNodes = useMemo(() => {
    if (!graphData?.nodes) return [];
    if (nodeTypeFilter === 'ALL') return graphData.nodes;
    return graphData.nodes.filter((n) => n.type === nodeTypeFilter);
  }, [graphData, nodeTypeFilter]);

  // Extract source nodes for Source Reputation Breakdown
  const sourceNodes = useMemo(() => {
    if (!graphData?.nodes) return [];
    return graphData.nodes.filter((n) => n.type === 'Source');
  }, [graphData]);

  return (
    <div
      style={{
        padding: '1.25rem 1.5rem',
        maxWidth: '1680px',
        margin: '0 auto',
        width: '100%',
        display: 'flex',
        flexDirection: 'column',
        gap: '1.25rem',
        boxSizing: 'border-box',
      }}
    >
      {/* ── TOP ACTION & SELECTOR BAR ─────────────────────────────────── */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: '1rem',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => navigate(selectedEventId ? `/events/${selectedEventId}` : '/events')}
            style={{ display: 'flex', alignItems: 'center', gap: '6px' }}
          >
            <ArrowLeft size={16} />
            <span>Events Feed</span>
          </Button>

          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <GitBranch size={20} color="var(--brand-blue, #38bdf8)" />
              <h1
                style={{
                  margin: 0,
                  fontSize: 'var(--text-xl, 20px)',
                  fontWeight: 700,
                  color: 'var(--text-primary, #f1f5f9)',
                  letterSpacing: '0.01em',
                }}
              >
                DWEG Intelligence: Dynamic Weather Evidence Graph (DWEG) & DNA
              </h1>
            </div>
            <p
              style={{
                margin: '0.2rem 0 0 0',
                fontSize: 'var(--text-xs, 12px)',
                color: 'var(--text-secondary, #94a3b8)',
              }}
            >
              Real-time relational multi-hop corroboration network, genomic factor decomposition & storm kinematics
            </p>
          </div>
        </div>

        {/* Event Selector */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          <span style={{ fontSize: '12px', color: 'var(--text-secondary, #94a3b8)', fontWeight: 500 }}>
            Inspect Event:
          </span>
          <select
            value={selectedEventId}
            onChange={(e) => handleSelectEvent(e.target.value)}
            style={{
              padding: '6px 12px',
              borderRadius: '6px',
              backgroundColor: 'var(--bg-elevated, #1e293b)',
              border: '1px solid var(--bg-border, #334155)',
              color: 'var(--text-primary, #f1f5f9)',
              fontSize: '13px',
              cursor: 'pointer',
              minWidth: '280px',
            }}
          >
            {activeEvents.map((evt) => (
              <option key={evt.id} value={evt.id}>
                [{evt.category.toUpperCase()} - SEV {evt.severity}] {evt.district || evt.state || 'India'} (
                {Math.round((evt.confidence_score || 0) * 100)}%)
              </option>
            ))}
          </select>

          <Button
            variant="secondary"
            size="sm"
            onClick={() => handleSelectEvent(selectedEventId)}
            title="Refresh Graph & Telemetry"
          >
            <RefreshCw size={14} className={isLoading ? 'animate-spin' : ''} />
          </Button>
        </div>
      </div>

      {/* ── PART 3: COMPREHENSIVE EVENT HEADER ────────────────────────── */}
      {selectedEvent && (
        <Card
          style={{
            padding: '1.25rem',
            backgroundColor: 'var(--bg-surface, #0f172a)',
            border: '1px solid var(--bg-border, #334155)',
            borderRadius: 'var(--radius-lg, 8px)',
            background:
              'linear-gradient(135deg, rgba(56, 189, 248, 0.05) 0%, rgba(15, 23, 42, 0.8) 100%)',
            display: 'flex',
            flexDirection: 'column',
            gap: '1rem',
          }}
        >
          {/* Row 1: Badges, Title & Persistent ID */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              flexWrap: 'wrap',
              gap: '0.75rem',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', flexWrap: 'wrap' }}>
              <CategoryBadge category={selectedEvent.category} />
              <SeverityBadge severity={selectedEvent.severity} />
              <VerificationBadge status={selectedEvent.verification_status} />
              {selectedEvent.is_synthetic && <DemoBadge />}

              <h2
                style={{
                  margin: '0 0 0 0.5rem',
                  fontSize: 'var(--text-lg, 18px)',
                  fontWeight: 700,
                  color: 'var(--text-primary, #f1f5f9)',
                }}
              >
                {selectedEvent.title || `${selectedEvent.category} Weather Incident`}
              </h2>
            </div>

            {/* Persistent ID */}
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '0.4rem',
                backgroundColor: 'var(--bg-elevated, #1e293b)',
                border: '1px solid var(--bg-border, #334155)',
                padding: '4px 8px',
                borderRadius: '6px',
                fontSize: '11px',
              }}
            >
              <span style={{ color: 'var(--text-muted, #64748b)' }}>UUID:</span>
              <span style={{ fontFamily: 'var(--font-mono, monospace)', color: 'var(--brand-blue, #38bdf8)' }}>
                {selectedEvent.id}
              </span>
              <button
                onClick={() => handleCopyId(selectedEvent.id)}
                title="Copy Persistent Event ID"
                style={{
                  background: 'none',
                  border: 'none',
                  color: copiedId ? 'var(--severity-1, #10b981)' : 'var(--text-secondary, #94a3b8)',
                  cursor: 'pointer',
                  padding: '2px',
                  display: 'flex',
                  alignItems: 'center',
                }}
              >
                {copiedId ? <Check size={13} /> : <Copy size={13} />}
              </button>
            </div>
          </div>

          {/* Row 2: Metrics Grid */}
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
              gap: '0.75rem',
            }}
          >
            {/* Confidence */}
            <div
              style={{
                padding: '0.65rem 0.85rem',
                backgroundColor: 'var(--bg-elevated, #1e293b)',
                borderRadius: '6px',
                border: '1px solid var(--bg-border, #334155)',
              }}
            >
              <div
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  fontSize: '11px',
                  color: 'var(--text-muted, #64748b)',
                  marginBottom: '4px',
                }}
              >
                <span>CONFIDENCE</span>
                <span style={{ fontWeight: 700, color: 'var(--brand-blue, #38bdf8)' }}>
                  {Math.round((selectedEvent.confidence_score || 0) * 100)}%
                </span>
              </div>
              <ConfidenceBar value={selectedEvent.confidence_score} showValue={false} />
            </div>

            {/* Location & Coordinates */}
            <div
              style={{
                padding: '0.65rem 0.85rem',
                backgroundColor: 'var(--bg-elevated, #1e293b)',
                borderRadius: '6px',
                border: '1px solid var(--bg-border, #334155)',
              }}
            >
              <div style={{ fontSize: '11px', color: 'var(--text-muted, #64748b)', marginBottom: '2px' }}>
                LOCATION & COORDINATES
              </div>
              <div
                style={{
                  fontSize: '12px',
                  fontWeight: 600,
                  color: 'var(--text-primary, #f1f5f9)',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '4px',
                }}
              >
                <MapPin size={13} color="var(--brand-blue, #38bdf8)" />
                {selectedEvent.district ? `${selectedEvent.district}, ` : ''}
                {selectedEvent.state || 'India'}
              </div>
              <div
                style={{
                  fontSize: '10px',
                  color: 'var(--text-secondary, #94a3b8)',
                  fontFamily: 'var(--font-mono, monospace)',
                  marginTop: '2px',
                }}
              >
                {selectedEvent.latitude?.toFixed(4)}° N, {selectedEvent.longitude?.toFixed(4)}° E
              </div>
            </div>

            {/* Timestamps */}
            <div
              style={{
                padding: '0.65rem 0.85rem',
                backgroundColor: 'var(--bg-elevated, #1e293b)',
                borderRadius: '6px',
                border: '1px solid var(--bg-border, #334155)',
              }}
            >
              <div style={{ fontSize: '11px', color: 'var(--text-muted, #64748b)', marginBottom: '2px' }}>
                DETECTION & REFRESH
              </div>
              <div
                style={{
                  fontSize: '12px',
                  fontWeight: 600,
                  color: 'var(--text-primary, #f1f5f9)',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '4px',
                }}
              >
                <Clock size={13} color="var(--brand-blue, #38bdf8)" />
                {selectedEvent.created_at
                  ? new Date(selectedEvent.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
                  : 'Recent'}
              </div>
              <div style={{ fontSize: '10px', color: 'var(--text-secondary, #94a3b8)', marginTop: '2px' }}>
                Updated: {selectedEvent.updated_at ? new Date(selectedEvent.updated_at).toLocaleTimeString() : 'Live'}
              </div>
            </div>

            {/* Evidence & Unique Sources Counts */}
            <div
              style={{
                padding: '0.65rem 0.85rem',
                backgroundColor: 'var(--bg-elevated, #1e293b)',
                borderRadius: '6px',
                border: '1px solid var(--bg-border, #334155)',
              }}
            >
              <div style={{ fontSize: '11px', color: 'var(--text-muted, #64748b)', marginBottom: '2px' }}>
                EVIDENCE PROVENANCE
              </div>
              <div style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-primary, #f1f5f9)' }}>
                {selectedEvent.report_count || graphData?.nodes?.filter((n) => n.type === 'EvidenceReport').length || 1} Evidence Report(s)
              </div>
              <div style={{ fontSize: '10px', color: 'var(--severity-1, #10b981)', marginTop: '2px' }}>
                {sourceNodes.length || 1} Independent Source Stream(s)
              </div>
            </div>
          </div>
        </Card>
      )}

      {/* ── Propagation Alert Banner (if event is actively propagating) ── */}
      {(activeAlertForEvent || timeline?.is_still_propagating) && (
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: '0.85rem 1.25rem',
            backgroundColor: 'rgba(249, 115, 22, 0.12)',
            border: '1px solid rgba(249, 115, 22, 0.4)',
            borderRadius: 'var(--radius-md, 6px)',
            color: '#fed7aa',
            fontSize: '13px',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
            <AlertTriangle size={20} color="#f97316" />
            <div>
              <span style={{ fontWeight: 700, color: '#f97316', marginRight: '6px' }}>
                DWEG PROPAGATION ALERT:
              </span>
              <span>
                {activeAlertForEvent?.message ||
                  `Storm system is actively propagating across district boundaries with increasing spatial expansion.`}
              </span>
            </div>
          </div>

          <Button
            variant="secondary"
            size="sm"
            onClick={() => setActiveTab('PROPAGATION')}
            style={{ borderColor: 'rgba(249, 115, 22, 0.4)', color: '#f97316' }}
          >
            Inspect Kinematic Vector
          </Button>
        </div>
      )}

      {/* ── MAIN TABS NAVIGATION ───────────────────────────────────────── */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '0.5rem',
          borderBottom: '1px solid var(--bg-border, #334155)',
          overflowX: 'auto',
          paddingBottom: '0.25rem',
        }}
      >
        {[
          {
            id: 'GRAPH' as DWEGTab,
            label: 'Evidence Graph Topology',
            icon: <GitBranch size={16} />,
            badge: graphData?.nodes?.length || 0,
          },
          {
            id: 'DNA' as DWEGTab,
            label: 'Weather Event DNA',
            icon: <Dna size={16} />,
            badge: 'Genomic',
          },
          {
            id: 'HEATMAP' as DWEGTab,
            label: 'Confidence Field Heatmap',
            icon: <Layers size={16} />,
            badge: `${confidenceField?.features?.length || 0} pts`,
          },
          {
            id: 'PROPAGATION' as DWEGTab,
            label: 'Kinematic Propagation',
            icon: <Compass size={16} />,
            badge: timeline?.propagation_steps?.length ? `${timeline.propagation_steps.length} stages` : undefined,
          },
          {
            id: 'SOURCES' as DWEGTab,
            label: 'Source Provenance',
            icon: <Database size={16} />,
            badge: sourceNodes.length ? `${sourceNodes.length} streams` : undefined,
          },
        ].map((tab) => {
          const isActive = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                padding: '8px 16px',
                borderRadius: '6px 6px 0 0',
                border: 'none',
                borderBottom: `2px solid ${isActive ? 'var(--brand-blue, #38bdf8)' : 'transparent'}`,
                backgroundColor: isActive ? 'var(--bg-elevated, #1e293b)' : 'transparent',
                color: isActive ? 'var(--brand-blue, #38bdf8)' : 'var(--text-secondary, #94a3b8)',
                fontWeight: isActive ? 600 : 400,
                fontSize: '13px',
                cursor: 'pointer',
                transition: 'all 0.15s ease',
                whiteSpace: 'nowrap',
              }}
            >
              {tab.icon}
              <span>{tab.label}</span>
              {tab.badge !== undefined && (
                <span
                  style={{
                    fontSize: '10px',
                    backgroundColor: isActive ? 'rgba(56, 189, 248, 0.2)' : 'rgba(255, 255, 255, 0.06)',
                    color: isActive ? 'var(--brand-blue, #38bdf8)' : 'var(--text-muted, #64748b)',
                    padding: '1px 6px',
                    borderRadius: '10px',
                    fontWeight: 600,
                  }}
                >
                  {tab.badge}
                </span>
              )}
            </button>
          );
        })}
      </div>

      {/* ── TAB BODIES ─────────────────────────────────────────────────── */}

      {/* 1. GRAPH TOPOLOGY & EVIDENCE CHAIN TAB */}
      {activeTab === 'GRAPH' && (
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'minmax(500px, 1.8fr) minmax(360px, 1.2fr)',
            gap: '1.25rem',
            alignItems: 'start',
          }}
        >
          {/* Left: Interactive Canvas + Filter Toolbar */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
            <Card style={{ padding: '1rem', display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
              {/* Filter controls toolbar */}
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  flexWrap: 'wrap',
                  gap: '0.5rem',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <Filter size={14} color="var(--text-muted, #64748b)" />
                  <span style={{ fontSize: '11px', color: 'var(--text-muted, #64748b)', fontWeight: 600 }}>
                    FILTER NODES:
                  </span>
                  {['ALL', 'WeatherEvent', 'EvidenceReport', 'Location', 'Source'].map((f) => (
                    <button
                      key={f}
                      onClick={() => setNodeTypeFilter(f)}
                      style={{
                        padding: '2px 8px',
                        borderRadius: '4px',
                        border: '1px solid var(--bg-border, #334155)',
                        backgroundColor: nodeTypeFilter === f ? 'var(--brand-blue, #38bdf8)' : 'var(--bg-elevated, #1e293b)',
                        color: nodeTypeFilter === f ? '#000000' : 'var(--text-secondary, #94a3b8)',
                        fontSize: '11px',
                        fontWeight: nodeTypeFilter === f ? 700 : 500,
                        cursor: 'pointer',
                      }}
                    >
                      {f === 'ALL' ? 'All Types' : f}
                    </button>
                  ))}
                </div>

                <div style={{ fontSize: '11px', color: 'var(--text-muted, #64748b)' }}>
                  Drag nodes to anchor • Scroll to zoom • Click to inspect
                </div>
              </div>

              {/* Force-directed SVG Graph */}
              <EvidenceGraph
                nodes={filteredNodes}
                edges={graphData?.edges || []}
                selectedNodeId={selectedNode?.id}
                onSelectNode={(node) => setSelectedNode(node)}
                height={560}
              />
            </Card>

            {/* Propagation Timeline below graph */}
            <PropagationTimeline timeline={timeline} />
          </div>

          {/* Right: Selected Node Inspector & Evidence Chain */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
            {/* Node Inspector Card */}
            {selectedNode ? (
              <Card
                style={{
                  padding: '1.25rem',
                  border: '1px solid var(--brand-blue, #38bdf8)',
                  backgroundColor: 'var(--bg-surface, #0f172a)',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '0.75rem',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <Activity size={16} color="var(--brand-blue, #38bdf8)" />
                    <span style={{ fontSize: '13px', fontWeight: 700, color: 'var(--text-primary, #f1f5f9)' }}>
                      Selected Node Inspector
                    </span>
                  </div>
                  <Button variant="ghost" size="sm" onClick={() => setSelectedNode(null)}>
                    Clear Selection
                  </Button>
                </div>

                {/* Node Type & Label Header */}
                <div
                  style={{
                    padding: '0.75rem',
                    backgroundColor: 'var(--bg-elevated, #1e293b)',
                    borderRadius: '6px',
                    border: '1px solid var(--bg-border, #334155)',
                  }}
                >
                  <div style={{ fontSize: '10px', color: 'var(--text-muted, #64748b)', textTransform: 'uppercase', fontWeight: 600 }}>
                    {selectedNode.type} NODE
                  </div>
                  <div style={{ fontSize: '14px', fontWeight: 700, color: '#ffffff', marginTop: '2px' }}>
                    {selectedNode.label}
                  </div>
                  <div style={{ fontSize: '10px', color: 'var(--brand-blue, #38bdf8)', fontFamily: 'var(--font-mono, monospace)', marginTop: '2px' }}>
                    ID: {selectedNode.id}
                  </div>
                </div>

                {/* Properties table */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', fontSize: '12px' }}>
                  {Object.entries(selectedNode.properties || {}).map(([key, val]) => (
                    <div
                      key={key}
                      style={{
                        display: 'flex',
                        justifyContent: 'space-between',
                        padding: '5px 0',
                        borderBottom: '1px solid var(--bg-border, #334155)',
                        gap: '12px',
                      }}
                    >
                      <span style={{ color: 'var(--text-secondary, #94a3b8)', textTransform: 'capitalize' }}>
                        {key.replace(/_/g, ' ')}:
                      </span>
                      <span
                        style={{
                          color: 'var(--text-primary, #f1f5f9)',
                          fontWeight: 500,
                          textAlign: 'right',
                          wordBreak: 'break-all',
                        }}
                      >
                        {typeof val === 'boolean' ? (val ? 'Yes' : 'No') : String(val ?? 'N/A')}
                      </span>
                    </div>
                  ))}
                </div>
              </Card>
            ) : (
              <Card
                style={{
                  padding: '1rem',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px',
                  color: 'var(--text-muted, #64748b)',
                  fontSize: '12px',
                  backgroundColor: 'var(--bg-surface, #0f172a)',
                }}
              >
                <GitBranch size={16} />
                <span>Click any node in the topology graph to inspect attributes, confidence, and telemetry.</span>
              </Card>
            )}

            {/* Evidence Chain Narrative & Provenance Steps */}
            <EvidenceChainPanel evidenceChain={evidenceChain} isLoading={isLoading} />
          </div>
        </div>
      )}

      {/* 2. WEATHER EVENT DNA TAB */}
      {activeTab === 'DNA' && selectedEventId && (
        <Card style={{ padding: '1.25rem', backgroundColor: 'var(--bg-surface, #0f172a)' }}>
          <div style={{ marginBottom: '1rem' }}>
            <h3 style={{ margin: 0, fontSize: '16px', fontWeight: 700, color: 'var(--text-primary, #f1f5f9)' }}>
              Weather Event DNA Profiler
            </h3>
            <p style={{ margin: '0.2rem 0 0 0', fontSize: '12px', color: 'var(--text-secondary, #94a3b8)' }}>
              Deep genetic decomposition of confidence weights, 6-dimensional evidence coverage, and journey timeline.
            </p>
          </div>
          <WeatherEventDNA eventId={selectedEventId} compact={false} />
        </Card>
      )}

      {/* 3. CONFIDENCE FIELD HEATMAP TAB */}
      {activeTab === 'HEATMAP' && (
        <Card style={{ padding: '1rem', backgroundColor: 'var(--bg-surface, #0f172a)' }}>
          <div style={{ marginBottom: '0.75rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div>
              <h3 style={{ margin: 0, fontSize: '16px', fontWeight: 700, color: 'var(--text-primary, #f1f5f9)' }}>
                Confidence Field Gradient Heatmap
              </h3>
              <p style={{ margin: '0.2rem 0 0 0', fontSize: '12px', color: 'var(--text-secondary, #94a3b8)' }}>
                Spatial continuous confidence field representing density of corroborating multi-source observations.
              </p>
            </div>
            <div style={{ fontSize: '12px', color: 'var(--brand-blue, #38bdf8)', fontWeight: 600 }}>
              {confidenceField?.features?.length || 0} Observation Points
            </div>
          </div>

          <ConfidenceFieldLayer confidenceField={confidenceField} height={600} />
        </Card>
      )}

      {/* 4. KINEMATIC PROPAGATION TIMELINE TAB */}
      {activeTab === 'PROPAGATION' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
          <Card style={{ padding: '1.25rem', backgroundColor: 'var(--bg-surface, #0f172a)' }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1rem' }}>
              <div>
                <h3 style={{ margin: 0, fontSize: '16px', fontWeight: 700, color: 'var(--text-primary, #f1f5f9)' }}>
                  Kinematic Storm Propagation & Spatial Vector
                </h3>
                <p style={{ margin: '0.2rem 0 0 0', fontSize: '12px', color: 'var(--text-secondary, #94a3b8)' }}>
                  Cross-district storm motion vectors derived from spatio-temporal clustering and DWEG edges.
                </p>
              </div>

              {timeline?.is_still_propagating && (
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '6px',
                    padding: '4px 10px',
                    borderRadius: '4px',
                    backgroundColor: 'rgba(249, 115, 22, 0.2)',
                    color: '#f97316',
                    fontSize: '12px',
                    fontWeight: 700,
                  }}
                >
                  <AlertTriangle size={14} />
                  <span>ACTIVE STORM SPREAD</span>
                </div>
              )}
            </div>

            <PropagationTimeline timeline={timeline} />
          </Card>
        </div>
      )}

      {/* 5. SOURCE REPUTATION & PROVENANCE TAB */}
      {activeTab === 'SOURCES' && (
        <Card style={{ padding: '1.25rem', backgroundColor: 'var(--bg-surface, #0f172a)' }}>
          <div style={{ marginBottom: '1rem' }}>
            <h3 style={{ margin: 0, fontSize: '16px', fontWeight: 700, color: 'var(--text-primary, #f1f5f9)' }}>
              Source Reputation & Ingestion Provenance Breakdown
            </h3>
            <p style={{ margin: '0.2rem 0 0 0', fontSize: '12px', color: 'var(--text-secondary, #94a3b8)' }}>
              Reputation weights, historic reliability, and corroboration metrics for all data sources feeding this event.
            </p>
          </div>

          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))',
              gap: '1rem',
            }}
          >
            {sourceNodes.length > 0 ? (
              sourceNodes.map((src) => {
                const props = src.properties || {};
                const trustScore = props.trust_score !== undefined ? Number(props.trust_score) : 0.8;
                return (
                  <div
                    key={src.id}
                    style={{
                      padding: '1rem',
                      backgroundColor: 'var(--bg-elevated, #1e293b)',
                      border: '1px solid var(--bg-border, #334155)',
                      borderRadius: '8px',
                      display: 'flex',
                      flexDirection: 'column',
                      gap: '0.5rem',
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <span style={{ fontSize: '14px', fontWeight: 700, color: 'var(--text-primary, #f1f5f9)' }}>
                        {src.label || props.name || 'Weather Source'}
                      </span>
                      <span
                        style={{
                          fontSize: '10px',
                          fontWeight: 700,
                          padding: '2px 8px',
                          borderRadius: '4px',
                          backgroundColor: 'rgba(56, 189, 248, 0.15)',
                          color: '#38bdf8',
                        }}
                      >
                        {props.source_type || 'TELEMETRY'}
                      </span>
                    </div>

                    <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', marginTop: '4px' }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '12px' }}>
                        <span style={{ color: 'var(--text-secondary, #94a3b8)' }}>Trust Score:</span>
                        <span style={{ fontWeight: 700, color: '#10b981' }}>{Math.round(trustScore * 100)}%</span>
                      </div>
                      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '12px' }}>
                        <span style={{ color: 'var(--text-secondary, #94a3b8)' }}>Status:</span>
                        <span style={{ color: props.is_active !== false ? '#10b981' : '#ef4444' }}>
                          {props.is_active !== false ? 'Active Stream' : 'Inactive'}
                        </span>
                      </div>
                      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '12px' }}>
                        <span style={{ color: 'var(--text-secondary, #94a3b8)' }}>Reputation Tier:</span>
                        <span style={{ color: 'var(--brand-blue, #38bdf8)', fontWeight: 600 }}>
                          {props.tier || (trustScore >= 0.85 ? 'Official Tier 1' : 'Trusted Partner')}
                        </span>
                      </div>
                    </div>
                  </div>
                );
              })
            ) : (
              <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-muted, #64748b)' }}>
                No external source metadata nodes in current sub-graph.
              </div>
            )}
          </div>
        </Card>
      )}
    </div>
  );
};

export default DWEGView;
