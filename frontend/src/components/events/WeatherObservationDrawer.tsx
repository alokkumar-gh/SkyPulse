/**
 * WeatherObservationDrawer — Routine Meteorological Telemetry Detail Panel
 * ========================================================================
 * Visualizes authoritative continuous weather measurements (temp, humidity, rain,
 * wind, pressure, WMO weather codes) with full source & model provenance.
 * Strictly separates routine physical telemetry from severe hazard incidents.
 */

import React from 'react';
import type { WeatherObservationFeature } from '../../types';
import { X, MapPin, Wind, Droplets, CloudRain, Thermometer, Radio, ShieldCheck } from 'lucide-react';

interface WeatherObservationDrawerProps {
  observation: WeatherObservationFeature | null;
  isOpen: boolean;
  onClose: () => void;
}

export const WeatherObservationDrawer: React.FC<WeatherObservationDrawerProps> = ({
  observation,
  isOpen,
  onClose,
}) => {
  if (!isOpen || !observation) return null;

  const locName = observation.city || observation.name || 'District Observation';
  const stateName = observation.state || 'India';
  const obsDate = observation.observed_at ? new Date(observation.observed_at) : new Date();

  return (
    <div
      style={{
        position: 'fixed',
        top: 'var(--topbar-height, 56px)',
        right: 0,
        bottom: 0,
        width: '380px',
        maxWidth: '90vw',
        backgroundColor: 'rgba(10, 15, 29, 0.98)',
        borderLeft: '1px solid rgba(56, 189, 248, 0.3)',
        boxShadow: '-8px 0 32px rgba(0, 0, 0, 0.8)',
        zIndex: 100,
        display: 'flex',
        flexDirection: 'column',
        backdropFilter: 'blur(12px)',
        animation: 'slideInRight 0.25s ease-out',
      }}
    >
      <style>{`
        @keyframes slideInRight {
          from { transform: translateX(100%); }
          to { transform: translateX(0); }
        }
      `}</style>

      {/* Header */}
      <div
        style={{
          padding: '1rem 1.25rem',
          borderBottom: '1px solid rgba(56, 189, 248, 0.2)',
          display: 'flex',
          alignItems: 'flex-start',
          justifyContent: 'space-between',
          backgroundColor: 'rgba(15, 23, 42, 0.8)',
        }}
      >
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '4px' }}>
            <span
              style={{
                fontSize: '10px',
                fontWeight: 700,
                color: '#38bdf8',
                textTransform: 'uppercase',
                letterSpacing: '0.08em',
                backgroundColor: 'rgba(56, 189, 248, 0.15)',
                border: '1px solid rgba(56, 189, 248, 0.35)',
                borderRadius: '4px',
                padding: '2px 6px',
                display: 'inline-flex',
                alignItems: 'center',
                gap: '4px',
              }}
            >
              <Radio size={10} />
              METEOROLOGICAL OBSERVATION
            </span>
          </div>
          <h2 style={{ fontSize: '18px', fontWeight: 700, color: '#f8fafc', margin: 0 }}>
            {locName}
          </h2>
          <div style={{ fontSize: '12px', color: '#94a3b8', display: 'flex', alignItems: 'center', gap: '4px', marginTop: '2px' }}>
            <MapPin size={12} color="#38bdf8" />
            <span>{stateName} · {observation.latitude.toFixed(4)}°N, {observation.longitude.toFixed(4)}°E</span>
          </div>
        </div>

        <button
          onClick={onClose}
          style={{
            background: 'none',
            border: 'none',
            color: '#94a3b8',
            cursor: 'pointer',
            padding: '4px',
            borderRadius: '4px',
            display: 'flex',
          }}
          title="Close observation details"
        >
          <X size={18} />
        </button>
      </div>

      {/* Content */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '1.25rem', display: 'flex', flexDirection: 'column', gap: '1rem' }}>
        {/* Main Temperature & Condition Card */}
        <div
          style={{
            backgroundColor: 'rgba(15, 23, 42, 0.65)',
            border: '1px solid rgba(56, 189, 248, 0.25)',
            borderRadius: '8px',
            padding: '1.25rem',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            boxShadow: '0 4px 16px rgba(0,0,0,0.4)',
          }}
        >
          <div>
            <div style={{ fontSize: '32px', fontWeight: 800, color: '#38bdf8', lineHeight: 1 }}>
              {observation.temp_label}
            </div>
            <div style={{ fontSize: '13px', fontWeight: 600, color: '#f1f5f9', marginTop: '6px' }}>
              {observation.condition}
            </div>
            <div style={{ fontSize: '11px', color: '#64748b', marginTop: '2px' }}>
              Continuous physical ground/model telemetry
            </div>
          </div>
          <div style={{ fontSize: '42px', lineHeight: 1 }}>
            {observation.weather_icon || '⛅'}
          </div>
        </div>

        {/* Meteorological Parameters Grid */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem' }}>
          {/* Humidity */}
          <div
            style={{
              backgroundColor: 'rgba(15, 23, 42, 0.5)',
              border: '1px solid #1e293b',
              borderRadius: '6px',
              padding: '0.75rem',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '5px', color: '#60a5fa', fontSize: '11px', fontWeight: 600, marginBottom: '4px' }}>
              <Droplets size={14} />
              <span>RELATIVE HUMIDITY</span>
            </div>
            <div style={{ fontSize: '16px', fontWeight: 700, color: '#f8fafc' }}>
              {observation.humidity_percent !== undefined ? `${observation.humidity_percent}%` : '--'}
            </div>
          </div>

          {/* Wind Speed */}
          <div
            style={{
              backgroundColor: 'rgba(15, 23, 42, 0.5)',
              border: '1px solid #1e293b',
              borderRadius: '6px',
              padding: '0.75rem',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '5px', color: '#34d399', fontSize: '11px', fontWeight: 600, marginBottom: '4px' }}>
              <Wind size={14} />
              <span>WIND SPEED (10M)</span>
            </div>
            <div style={{ fontSize: '16px', fontWeight: 700, color: '#f8fafc' }}>
              {observation.wind_speed_kmh !== undefined ? `${observation.wind_speed_kmh} km/h` : '--'}
            </div>
          </div>

          {/* Precipitation / Rain */}
          <div
            style={{
              backgroundColor: 'rgba(15, 23, 42, 0.5)',
              border: '1px solid #1e293b',
              borderRadius: '6px',
              padding: '0.75rem',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '5px', color: '#38bdf8', fontSize: '11px', fontWeight: 600, marginBottom: '4px' }}>
              <CloudRain size={14} />
              <span>PRECIPITATION</span>
            </div>
            <div style={{ fontSize: '16px', fontWeight: 700, color: '#f8fafc' }}>
              {observation.rain_mm !== undefined ? `${observation.rain_mm} mm` : '0.0 mm'}
            </div>
          </div>

          {/* Temperature in Celsius */}
          <div
            style={{
              backgroundColor: 'rgba(15, 23, 42, 0.5)',
              border: '1px solid #1e293b',
              borderRadius: '6px',
              padding: '0.75rem',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '5px', color: '#f59e0b', fontSize: '11px', fontWeight: 600, marginBottom: '4px' }}>
              <Thermometer size={14} />
              <span>AIR TEMPERATURE</span>
            </div>
            <div style={{ fontSize: '16px', fontWeight: 700, color: '#f8fafc' }}>
              {observation.temperature_c !== undefined ? `${observation.temperature_c.toFixed(1)}°C` : '--'}
            </div>
          </div>
        </div>

        {/* Source & Provenance Metadata */}
        <div
          style={{
            backgroundColor: 'rgba(15, 23, 42, 0.65)',
            border: '1px solid #1e293b',
            borderRadius: '8px',
            padding: '1rem',
          }}
        >
          <div style={{ fontSize: '11px', fontWeight: 700, color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '0.75rem', display: 'flex', alignItems: 'center', gap: '6px' }}>
            <ShieldCheck size={14} color="#38bdf8" />
            <span>SOURCE & METEOROLOGICAL PROVENANCE</span>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', fontSize: '11px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ color: '#64748b' }}>Primary Telemetry Source:</span>
              <span style={{ color: '#f1f5f9', fontWeight: 600 }}>{observation.source || 'Open-Meteo'}</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ color: '#64748b' }}>Numerical Weather Model:</span>
              <span style={{ color: '#f1f5f9', fontWeight: 500 }}>{observation.model || 'ECMWF IFS / GFS Seamless Grid'}</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ color: '#64748b' }}>Observation Timestamp:</span>
              <span style={{ color: '#cbd5e1', fontFamily: 'monospace' }}>
                {obsDate.toLocaleString()}
              </span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ color: '#64748b' }}>Data Classification:</span>
              <span style={{ color: '#22c55e', fontWeight: 600 }}>Continuous Routine Baseline</span>
            </div>
          </div>
        </div>

        {/* Separation Notice */}
        <div
          style={{
            backgroundColor: 'rgba(56, 189, 248, 0.08)',
            border: '1px dashed rgba(56, 189, 248, 0.3)',
            borderRadius: '6px',
            padding: '0.75rem',
            fontSize: '11px',
            color: '#94a3b8',
            lineHeight: 1.4,
          }}
        >
          ℹ️ <strong>Routine Observation Layer</strong>: Displays physical parameters at district centroids. These continuous measurements do not constitute severe hazard events unless confirmed by official disaster bulletins or severe weather triggers.
        </div>
      </div>
    </div>
  );
};
