/**
 * SkyPulse Floating Map Controls & Miniature Intelligence Popups
 * Implements Sections 11 & 12:
 * "Use a refined floating control system. Controls should remain visually quiet until needed."
 * "Map popups must feel like miniature intelligence reports."
 */

import React, { useState } from 'react';
import {
  Layers, CloudRain, Thermometer, Wind,
  AlertTriangle, RotateCcw, ZoomIn, ZoomOut,
  ChevronDown, ChevronUp, ArrowRight,
} from 'lucide-react';

export type WeatherLayerType = 'rainfall' | 'temperature' | 'wind' | 'events' | 'radar';

interface MapControlsProps {
  activeLayer: WeatherLayerType;
  onLayerChange: (layer: WeatherLayerType) => void;
  onZoomIn: () => void;
  onZoomOut: () => void;
  onResetView: () => void;
  className?: string;
  style?: React.CSSProperties;
}

export const MapControls: React.FC<MapControlsProps> = ({
  activeLayer,
  onLayerChange,
  onZoomIn,
  onZoomOut,
  onResetView,
  className = '',
  style,
}) => {
  const [collapsed, setCollapsed] = useState(false);

  const layers: { id: WeatherLayerType; label: string; icon: React.ReactNode }[] = [
    { id: 'rainfall', label: 'Rainfall', icon: <CloudRain size={12} /> },
    { id: 'temperature', label: 'Temperature', icon: <Thermometer size={12} /> },
    { id: 'wind', label: 'Surface Wind', icon: <Wind size={12} /> },
    { id: 'events', label: 'Hazard Events', icon: <AlertTriangle size={12} /> },
    { id: 'radar', label: 'Doppler Radar', icon: <Layers size={12} /> },
  ];

  return (
    <div
      style={{
        position: 'absolute',
        top: '1rem',
        left: '1rem',
        zIndex: 20,
        display: 'flex',
        flexDirection: 'column',
        gap: '0.5rem',
        ...style,
      }}
      className={`sp-map-floating-controls ${className}`}
    >
      {/* Refined Weather Layer Selector */}
      <div
        style={{
          backgroundColor: 'rgba(19, 22, 19, 0.92)',
          backdropFilter: 'blur(8px)',
          border: '1px solid var(--border-subtle)',
          borderRadius: 'var(--r-2)',
          boxShadow: '0 8px 24px rgba(0,0,0,0.5)',
          overflow: 'hidden',
          width: '180px',
          transition: 'all 0.2s ease',
        }}
      >
        {/* Header */}
        <div
          onClick={() => setCollapsed(!collapsed)}
          style={{
            padding: '0.5rem 0.75rem',
            borderBottom: collapsed ? 'none' : '1px solid var(--border-hairline)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            cursor: 'pointer',
            userSelect: 'none',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
            <Layers size={12} color="var(--teal)" />
            <span
              style={{
                fontSize: 'var(--text-2xs)',
                fontFamily: 'var(--font-mono)',
                fontWeight: 700,
                letterSpacing: '0.1em',
                textTransform: 'uppercase',
                color: 'var(--text-secondary)',
              }}
            >
              WEATHER LAYERS
            </span>
          </div>
          {collapsed ? <ChevronDown size={12} color="var(--text-muted)" /> : <ChevronUp size={12} color="var(--text-muted)" />}
        </div>

        {/* Options list */}
        {!collapsed && (
          <div style={{ padding: '0.35rem 0' }}>
            {layers.map((layer) => {
              const isActive = activeLayer === layer.id;
              return (
                <div
                  key={layer.id}
                  onClick={() => onLayerChange(layer.id)}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    padding: '0.35rem 0.75rem',
                    cursor: 'pointer',
                    backgroundColor: isActive ? 'var(--teal-100)' : 'transparent',
                    color: isActive ? 'var(--text-primary)' : 'var(--text-secondary)',
                    fontSize: 'var(--text-xs)',
                    fontFamily: 'var(--font-sans)',
                    transition: 'all 0.12s ease',
                  }}
                  className="sp-layer-option"
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.45rem' }}>
                    <span style={{ color: isActive ? 'var(--teal)' : 'var(--text-muted)' }}>
                      {layer.icon}
                    </span>
                    <span style={{ fontWeight: isActive ? 600 : 400 }}>{layer.label}</span>
                  </div>

                  {/* Bullet indicator */}
                  <span
                    style={{
                      width: 6,
                      height: 6,
                      borderRadius: '50%',
                      backgroundColor: isActive ? 'var(--teal)' : 'var(--border-subtle)',
                      boxShadow: isActive ? '0 0 6px var(--teal)' : 'none',
                    }}
                  />
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Floating Zoom & Extent controls */}
      <div
        style={{
          display: 'flex',
          flexDirection: 'column',
          backgroundColor: 'rgba(19, 22, 19, 0.92)',
          backdropFilter: 'blur(8px)',
          border: '1px solid var(--border-subtle)',
          borderRadius: 'var(--r-2)',
          width: '32px',
          boxShadow: '0 8px 24px rgba(0,0,0,0.5)',
          overflow: 'hidden',
        }}
      >
        <button
          onClick={onZoomIn}
          style={{
            background: 'none',
            border: 'none',
            borderBottom: '1px solid var(--border-hairline)',
            color: 'var(--text-secondary)',
            padding: '0.45rem',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}
          title="Zoom in"
          aria-label="Zoom in"
        >
          <ZoomIn size={14} />
        </button>
        <button
          onClick={onZoomOut}
          style={{
            background: 'none',
            border: 'none',
            borderBottom: '1px solid var(--border-hairline)',
            color: 'var(--text-secondary)',
            padding: '0.45rem',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}
          title="Zoom out"
          aria-label="Zoom out"
        >
          <ZoomOut size={14} />
        </button>
        <button
          onClick={onResetView}
          style={{
            background: 'none',
            border: 'none',
            color: 'var(--teal)',
            padding: '0.45rem',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}
          title="Reset to All-India View"
          aria-label="Reset to India view"
        >
          <RotateCcw size={13} />
        </button>
      </div>
    </div>
  );
};

// ==========================================
// 12. MAP POPUP (Miniature Intelligence Report)
// ==========================================
export interface MapPopupIntelligenceProps {
  location: string;
  anomalyTitle: string;
  metricValue: string;
  metricUnit?: string;
  observed: string;
  expected: string;
  deviationPercent?: string;
  source?: string;
  timestamp?: string;
  severity?: 1 | 2 | 3 | 4;
  onExplore: () => void;
  onClose?: () => void;
}

export const MapPopupIntelligence: React.FC<MapPopupIntelligenceProps> = ({
  location,
  anomalyTitle,
  metricValue,
  metricUnit,
  observed,
  expected,
  deviationPercent,
  source = 'IMD',
  timestamp = '14:32 IST',
  severity = 3,
  onExplore,
  onClose,
}) => {
  const getSeverityColor = () => {
    if (severity === 4) return 'var(--sev-4)';
    if (severity === 3) return 'var(--sev-3)';
    if (severity === 2) return 'var(--sev-2)';
    return 'var(--sev-1)';
  };

  return (
    <div
      style={{
        backgroundColor: 'var(--bg-surface)',
        border: '1px solid var(--border-default)',
        borderLeft: `3px solid ${getSeverityColor()}`,
        borderRadius: 'var(--r-2)',
        padding: '0.9rem 1.1rem',
        width: '260px',
        boxShadow: '0 16px 32px rgba(0,0,0,0.65)',
        display: 'flex',
        flexDirection: 'column',
        gap: '0.45rem',
        animation: 'scale-up 0.15s ease-out',
        position: 'relative',
      }}
      className="sp-map-popup"
    >
      {onClose && (
        <button
          onClick={onClose}
          style={{
            position: 'absolute',
            top: 6,
            right: 8,
            background: 'none',
            border: 'none',
            color: 'var(--text-muted)',
            cursor: 'pointer',
            fontSize: '12px',
          }}
        >
          ✕
        </button>
      )}

      {/* Header: Location & Anomaly Type */}
      <div style={{ paddingRight: '1rem' }}>
        <div
          style={{
            fontSize: 'var(--text-2xs)',
            fontFamily: 'var(--font-mono)',
            fontWeight: 700,
            letterSpacing: '0.12em',
            textTransform: 'uppercase',
            color: 'var(--teal)',
          }}
        >
          {location}
        </div>
        <div
          style={{
            fontSize: 'var(--text-xs)',
            fontWeight: 700,
            color: 'var(--text-primary)',
            fontFamily: 'var(--font-sans)',
            textTransform: 'uppercase',
            letterSpacing: '0.04em',
            marginTop: '0.1rem',
          }}
        >
          {anomalyTitle}
        </div>
      </div>

      {/* Big Anomaly Metric */}
      <div style={{ display: 'flex', alignItems: 'baseline', gap: '0.4rem', margin: '0.2rem 0' }}>
        <span
          style={{
            fontSize: 'var(--text-2xl)',
            fontWeight: 700,
            fontFamily: 'var(--font-mono)',
            color: getSeverityColor(),
            letterSpacing: '-0.02em',
            lineHeight: 1,
          }}
        >
          {metricValue}
        </span>
        {metricUnit && (
          <span style={{ fontSize: 'var(--text-xs)', fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>
            {metricUnit}
          </span>
        )}
        {deviationPercent && (
          <span style={{ fontSize: 'var(--text-xs)', fontFamily: 'var(--font-mono)', color: getSeverityColor(), fontWeight: 600 }}>
            {deviationPercent}
          </span>
        )}
      </div>

      {/* Observed vs Expected Comparison Grid */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: '1fr 1fr',
          gap: '0.5rem',
          padding: '0.35rem 0.5rem',
          backgroundColor: 'var(--bg-panel)',
          borderRadius: 'var(--r-1)',
          border: '1px solid var(--border-hairline)',
          fontSize: 'var(--text-2xs)',
          fontFamily: 'var(--font-mono)',
        }}
      >
        <div>
          <span style={{ color: 'var(--text-muted)' }}>Observed: </span>
          <span style={{ color: 'var(--text-primary)', fontWeight: 600 }}>{observed}</span>
        </div>
        <div>
          <span style={{ color: 'var(--text-muted)' }}>Expected: </span>
          <span style={{ color: 'var(--text-secondary)' }}>{expected}</span>
        </div>
      </div>

      {/* Source & Timestamp */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          fontSize: 'var(--text-2xs)',
          fontFamily: 'var(--font-mono)',
          color: 'var(--text-muted)',
          paddingTop: '0.25rem',
        }}
      >
        <span>{source}</span>
        <span>{timestamp}</span>
      </div>

      {/* Explore Anomaly CTA */}
      <div style={{ marginTop: '0.2rem' }}>
        <button
          onClick={onExplore}
          style={{
            width: '100%',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: '0.35rem',
            padding: '0.4rem',
            backgroundColor: 'var(--bg-elevated)',
            border: '1px solid var(--border-subtle)',
            borderRadius: 'var(--r-1)',
            color: 'var(--teal)',
            fontSize: 'var(--text-xs)',
            fontFamily: 'var(--font-mono)',
            fontWeight: 600,
            cursor: 'pointer',
            transition: 'all 0.15s ease',
          }}
          className="sp-explore-popup-btn"
        >
          <span>Explore anomaly</span>
          <ArrowRight size={12} />
        </button>
      </div>
    </div>
  );
};
