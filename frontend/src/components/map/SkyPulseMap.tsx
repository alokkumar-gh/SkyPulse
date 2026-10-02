/**
 * SkyPulseMap — Google Maps weather event visualization for India.
 * Renders severity-colored markers with hover popups for each event.
 * No D3/radar — pure Google Maps via @vis.gl/react-google-maps.
 */

import React, { useState, useMemo } from 'react';
import {
  APIProvider,
  Map,
  AdvancedMarker,
} from '@vis.gl/react-google-maps';
import type { WeatherEvent } from '../../types';
import { SEVERITY_COLORS, CATEGORY_COLORS } from '../../types';
import { GOOGLE_MAPS_DARK_STYLE } from './mapStyles';

interface SkyPulseMapProps {
  events: WeatherEvent[];
  selectedEventId?: string | null;
  onSelectEvent: (event: WeatherEvent) => void;
  showHeatmap?: boolean;
  apiKey?: string;
}

const INDIA_CENTER: google.maps.LatLngLiteral = { lat: 22.5937, lng: 78.9629 };
const DEFAULT_ZOOM = 5;

/** Bottom-left severity legend */
const SeverityLegend: React.FC = () => (
  <div
    style={{
      position: 'absolute',
      bottom: '1rem',
      left: '1rem',
      zIndex: 10,
      backgroundColor: 'rgba(7, 11, 20, 0.88)',
      border: '1px solid #1e293b',
      borderRadius: '6px',
      padding: '0.5rem 0.75rem',
      backdropFilter: 'blur(6px)',
      fontSize: '11px',
      color: '#94a3b8',
      boxShadow: '0 4px 6px -1px rgba(0,0,0,0.5)',
      pointerEvents: 'none',
    }}
  >
    <div style={{ fontWeight: 700, marginBottom: '0.35rem', color: '#f1f5f9', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
      SEVERITY SCALE
    </div>
    <div style={{ display: 'flex', gap: '0.6rem', alignItems: 'center' }}>
      {[1, 2, 3, 4].map((s) => (
        <div key={s} style={{ display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
          <span style={{ width: 8, height: 8, borderRadius: '50%', backgroundColor: SEVERITY_COLORS[s], display: 'inline-block' }} />
          <span>{s === 1 ? '1 Minor' : s === 2 ? '2 Moderate' : s === 3 ? '3 Severe' : '4 Extreme'}</span>
        </div>
      ))}
    </div>
  </div>
);

/** Single event marker with hover popup */
const EventMarker: React.FC<{
  event: WeatherEvent;
  isSelected: boolean;
  onSelect: (ev: WeatherEvent) => void;
}> = ({ event, isSelected, onSelect }) => {
  const [hovered, setHovered] = useState(false);

  const color = SEVERITY_COLORS[event.severity] || '#eab308';
  const catColor = CATEGORY_COLORS[event.category] || '#60a5fa';
  const size = isSelected ? 36 : event.severity >= 3 ? 30 : 24;
  const showPopup = hovered || isSelected;

  return (
    <AdvancedMarker
      position={{ lat: event.latitude!, lng: event.longitude! }}
      onClick={() => onSelect(event)}
    >
      {/* Marker pin */}
      <div
        onMouseEnter={() => setHovered(true)}
        onMouseLeave={() => setHovered(false)}
        style={{
          width: size,
          height: size,
          borderRadius: '50%',
          backgroundColor: color,
          border: `3px solid ${isSelected ? '#fff' : 'rgba(255,255,255,0.4)'}`,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          color: '#fff',
          fontSize: size >= 30 ? '12px' : '10px',
          fontWeight: 800,
          cursor: 'pointer',
          boxShadow: `0 0 ${isSelected ? 16 : 8}px ${color}80`,
          transition: 'all 0.15s ease',
          animation: event.severity >= 3 ? 'pulse-marker 2s ease-in-out infinite' : 'none',
          position: 'relative',
          zIndex: isSelected ? 20 : 10,
        }}
      >
        {event.severity}
      </div>

      {/* Info popup on hover/select */}
      {showPopup && (
        <div
          style={{
            position: 'absolute',
            bottom: size + 8,
            left: '50%',
            transform: 'translateX(-50%)',
            backgroundColor: 'rgba(7, 11, 20, 0.96)',
            border: `1px solid ${catColor}40`,
            borderRadius: '6px',
            padding: '0.5rem 0.75rem',
            minWidth: '160px',
            maxWidth: '220px',
            boxShadow: '0 8px 24px rgba(0,0,0,0.6)',
            zIndex: 50,
            pointerEvents: 'none',
            whiteSpace: 'nowrap',
          }}
        >
          <div style={{ fontSize: '9px', fontWeight: 700, color: catColor, textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: '2px' }}>
            {event.category}
          </div>
          <div style={{ fontSize: '12px', fontWeight: 600, color: '#f1f5f9', lineHeight: 1.3, marginBottom: '4px', whiteSpace: 'normal' }}>
            {event.title || `${event.category} Event`}
          </div>
          <div style={{ fontSize: '10px', color: '#64748b' }}>
            📍 {event.district ? `${event.district}, ` : ''}{event.state || 'India'}
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: '4px', fontSize: '10px' }}>
            <span style={{ color: '#94a3b8' }}>{Math.round((event.confidence_score || 0) * 100)}% conf</span>
            <span style={{
              color: event.verification_status === 'VERIFIED' ? '#22c55e'
                : event.verification_status === 'CONTRADICTED' ? '#ef4444' : '#f59e0b',
              fontWeight: 600,
            }}>
              {event.verification_status}
            </span>
          </div>
        </div>
      )}
    </AdvancedMarker>
  );
};

/** Main exported SkyPulseMap — Google Maps only */
export const SkyPulseMap: React.FC<SkyPulseMapProps> = ({
  events,
  selectedEventId,
  onSelectEvent,
  apiKey: propApiKey,
}) => {
  const apiKey = propApiKey ?? (import.meta.env?.VITE_GOOGLE_MAPS_API_KEY ?? '');

  // Only plot events that have valid coordinates
  const plottableEvents = useMemo(
    () => events.filter((ev) =>
      ev.latitude !== undefined &&
      ev.longitude !== undefined &&
      !isNaN(ev.latitude!) &&
      !isNaN(ev.longitude!)
    ),
    [events]
  );

  if (!apiKey) {
    return (
      <div style={{
        width: '100%', height: '100%', minHeight: 400,
        backgroundColor: '#070b14', display: 'flex',
        alignItems: 'center', justifyContent: 'center',
        color: '#64748b', fontSize: '13px', flexDirection: 'column', gap: '0.5rem',
      }}>
        <span style={{ fontSize: '20px' }}>🗺️</span>
        <span style={{ fontWeight: 600, color: '#f1f5f9' }}>Google Maps API Key Required</span>
        <span>Set <code style={{ color: '#38bdf8' }}>VITE_GOOGLE_MAPS_API_KEY</code> to enable the map.</span>
        <span style={{ fontSize: '11px', color: '#94a3b8' }}>Tracking {plottableEvents.length} active weather event(s)</span>
      </div>
    );
  }

  return (
    <div style={{ position: 'relative', width: '100%', height: '100%', minHeight: 400, backgroundColor: '#070b14' }}>
      {/* Pulse animation for high-severity markers */}
      <style>{`
        @keyframes pulse-marker {
          0%, 100% { box-shadow: 0 0 8px currentColor; transform: scale(1); }
          50% { box-shadow: 0 0 20px currentColor; transform: scale(1.12); }
        }
      `}</style>

      <APIProvider apiKey={apiKey}>
        <Map
          defaultCenter={INDIA_CENTER}
          defaultZoom={DEFAULT_ZOOM}
          minZoom={4}
          maxZoom={18}
          mapId="skypulse-india-map"
          styles={GOOGLE_MAPS_DARK_STYLE}
          disableDefaultUI={true}
          gestureHandling="greedy"
          style={{ width: '100%', height: '100%' }}
        >
          {plottableEvents.map((ev) => (
            <EventMarker
              key={ev.id}
              event={ev}
              isSelected={ev.id === selectedEventId}
              onSelect={onSelectEvent}
            />
          ))}
        </Map>
      </APIProvider>

      <SeverityLegend />

      {/* Event count badge */}
      {plottableEvents.length > 0 && (
        <div style={{
          position: 'absolute', top: '0.5rem', right: '0.5rem', zIndex: 10,
          backgroundColor: 'rgba(7,11,20,0.85)', border: '1px solid #1e293b',
          borderRadius: '4px', padding: '0.25rem 0.6rem',
          fontSize: '10px', color: '#94a3b8', fontFamily: 'monospace',
          backdropFilter: 'blur(4px)',
        }}>
          {plottableEvents.length} event{plottableEvents.length !== 1 ? 's' : ''} plotted
        </div>
      )}
    </div>
  );
};
