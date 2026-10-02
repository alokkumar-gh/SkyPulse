/**
 * ConfidenceFieldLayer Component — Migrated to Google Maps JavaScript API (Phase 10)
 * Renders spatial confidence field heatmap layer and evidence corroboration circles.
 * Visualizes multi-source evidence concentration, report density, and event centroid focus.
 */

import React, { useEffect, useState, useMemo } from 'react';
import {
  APIProvider,
  Map,
  AdvancedMarker,
  InfoWindow,
  useMap,
  useMapsLibrary,
} from '@vis.gl/react-google-maps';
import type { ConfidenceFieldResponse, ConfidenceFieldFeature } from '../../types';
import { GOOGLE_MAPS_DARK_STYLE } from '../map/mapStyles';
import { AlertCircle } from 'lucide-react';

interface ConfidenceFieldLayerProps {
  confidenceField: ConfidenceFieldResponse | null;
  height?: number | string;
  center?: [number, number]; // [lon, lat]
  zoom?: number;
  apiKey?: string;
}

const INDIA_CENTER: google.maps.LatLngLiteral = { lat: 20.5937, lng: 78.9629 };

/**
 * Inner controller for Google Maps Confidence Field Heatmap & Markers
 */
const ConfidenceFieldInner: React.FC<{
  confidenceField: ConfidenceFieldResponse | null;
  initialCenter: google.maps.LatLngLiteral;
  zoom: number;
}> = ({ confidenceField, initialCenter, zoom }) => {
  const map = useMap();
  const visualization = useMapsLibrary('visualization');
  const [hoveredFeature, setHoveredFeature] = useState<ConfidenceFieldFeature | null>(null);
  const [heatmapLayer, setHeatmapLayer] = useState<any>(null);

  const features = useMemo(() => {
    return confidenceField?.features || [];
  }, [confidenceField]);

  // Find centroid feature
  const centroidFeature = useMemo(() => {
    return features.find((f) => f.properties?.is_centroid) || features[0] || null;
  }, [features]);

  // Auto-pan/zoom to centroid when confidence field changes
  useEffect(() => {
    if (!map) return;

    if (centroidFeature && centroidFeature.geometry?.coordinates) {
      const [lon, lat] = centroidFeature.geometry.coordinates;
      if (!isNaN(lat) && !isNaN(lon)) {
        map.panTo({ lat, lng: lon });
        if ((map.getZoom() || 0) < zoom) {
          map.setZoom(zoom);
        }
      }
    } else {
      map.panTo(initialCenter);
      map.setZoom(zoom);
    }
  }, [map, centroidFeature, initialCenter, zoom]);

  // Build and render Google Maps Heatmap Layer
  useEffect(() => {
    if (!map || !visualization) return;

    if (features.length > 0) {
      const data = features
        .filter((f) => f.geometry?.coordinates && !isNaN(f.geometry.coordinates[0]) && !isNaN(f.geometry.coordinates[1]))
        .map((f) => {
          const lat = f.geometry.coordinates[1];
          const lng = f.geometry.coordinates[0];
          const location = typeof google !== 'undefined' && (google.maps as any)?.LatLng
            ? new (google.maps as any).LatLng(lat, lng)
            : ({ lat, lng } as any);
          return {
            location,
            weight: Math.max(0.1, f.properties.weight || 0.5) * 3,
          };
        });

      if (heatmapLayer) {
        heatmapLayer.setData?.(data);
        heatmapLayer.setMap?.(map);
      } else {
        const layer = new (visualization.HeatmapLayer as any)({
          data,
          map,
          radius: 40,
          opacity: 0.8,
          gradient: [
            'rgba(33, 102, 172, 0)',
            'rgb(103, 169, 207)',
            'rgb(209, 229, 240)',
            'rgb(253, 219, 199)',
            'rgb(239, 138, 98)',
            'rgb(178, 24, 43)',
          ],
        });
        setHeatmapLayer(layer);
      }
    } else if (heatmapLayer) {
      heatmapLayer.setMap?.(null);
    }

    return () => {
      if (heatmapLayer) {
        heatmapLayer.setMap?.(null);
      }
    };
  }, [map, visualization, features]);

  return (
    <>
      {/* Evidence Point Markers */}
      {features.map((f, idx) => {
        const [lon, lat] = f.geometry.coordinates;
        if (isNaN(lat) || isNaN(lon)) return null;

        const isCentroid = f.properties.is_centroid;
        const weight = f.properties.weight || 0.5;
        const size = isCentroid ? 28 : Math.max(14, Math.round(weight * 24));
        const color = isCentroid ? '#f59e0b' : '#38bdf8';

        return (
          <AdvancedMarker
            key={`conf-feat-${idx}`}
            position={{ lat, lng: lon }}
            zIndex={isCentroid ? 500 : 100}
            onClick={() => setHoveredFeature(f)}
          >
            <div
              onMouseEnter={() => setHoveredFeature(f)}
              onMouseLeave={() => setHoveredFeature(null)}
              style={{
                position: 'relative',
                width: `${size}px`,
                height: `${size}px`,
                borderRadius: '50%',
                backgroundColor: color,
                border: '2px solid #ffffff',
                boxShadow: isCentroid
                  ? '0 0 16px rgba(245, 158, 11, 0.8), 0 0 4px #ffffff'
                  : '0 0 8px rgba(56, 189, 248, 0.6)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                cursor: 'pointer',
                transition: 'transform 0.15s ease',
              }}
            >
              {isCentroid && (
                <div
                  style={{
                    position: 'absolute',
                    inset: '-6px',
                    borderRadius: '50%',
                    border: '2px solid #f59e0b',
                    animation: 'ping 2s cubic-bezier(0, 0, 0.2, 1) infinite',
                    pointerEvents: 'none',
                  }}
                />
              )}
              <span
                style={{
                  fontSize: isCentroid ? '10px' : '8px',
                  fontWeight: 700,
                  color: '#0f172a',
                  lineHeight: 1,
                  userSelect: 'none',
                }}
              >
                {isCentroid ? '★' : `${Math.round(weight * 100)}%`}
              </span>
            </div>
          </AdvancedMarker>
        );
      })}

      {/* Hover InfoWindow */}
      {hoveredFeature && (
        <InfoWindow
          position={{
            lat: hoveredFeature.geometry.coordinates[1],
            lng: hoveredFeature.geometry.coordinates[0],
          }}
          onCloseClick={() => setHoveredFeature(null)}
          pixelOffset={[0, -18]}
          headerDisabled
        >
          <div
            style={{
              padding: '6px 8px',
              minWidth: '170px',
              color: '#0f172a',
              fontFamily: 'system-ui, -apple-system, sans-serif',
              fontSize: '11px',
            }}
          >
            <div
              style={{
                fontWeight: 700,
                fontSize: '12px',
                color: hoveredFeature.properties.is_centroid ? '#d97706' : '#0284c7',
                marginBottom: '4px',
              }}
            >
              {hoveredFeature.properties.is_centroid ? 'Event Centroid Focus' : 'Evidence Signal'}
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '3px' }}>
              <span style={{ color: '#64748b' }}>Weight / Corroboration:</span>
              <strong style={{ color: '#0f172a' }}>
                {Math.round((hoveredFeature.properties.weight || 0) * 100)}%
              </strong>
            </div>
            {hoveredFeature.properties.source_type && (
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '3px' }}>
                <span style={{ color: '#64748b' }}>Source Type:</span>
                <span style={{ fontWeight: 600 }}>{hoveredFeature.properties.source_type}</span>
              </div>
            )}
            {hoveredFeature.properties.category && (
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ color: '#64748b' }}>Category:</span>
                <span style={{ fontWeight: 600 }}>{hoveredFeature.properties.category}</span>
              </div>
            )}
          </div>
        </InfoWindow>
      )}
    </>
  );
};

/**
 * Exported ConfidenceFieldLayer Component
 */
export const ConfidenceFieldLayer: React.FC<ConfidenceFieldLayerProps> = ({
  confidenceField,
  height = 480,
  center,
  zoom = 6.5,
  apiKey: propApiKey,
}) => {
  const apiKey = propApiKey !== undefined ? propApiKey : (import.meta.env?.VITE_GOOGLE_MAPS_API_KEY || '');

  // Initial center calculation
  const computedCenter: google.maps.LatLngLiteral = useMemo(() => {
    if (center) {
      return { lat: center[1], lng: center[0] };
    }
    if (confidenceField?.features && confidenceField.features.length > 0) {
      const centroid = confidenceField.features.find((f) => f.properties.is_centroid);
      if (centroid?.geometry?.coordinates) {
        return { lat: centroid.geometry.coordinates[1], lng: centroid.geometry.coordinates[0] };
      }
      return {
        lat: confidenceField.features[0].geometry.coordinates[1],
        lng: confidenceField.features[0].geometry.coordinates[0],
      };
    }
    return INDIA_CENTER;
  }, [center, confidenceField]);

  // Handle missing Google Maps API key
  if (!apiKey) {
    return (
      <div
        style={{
          position: 'relative',
          width: '100%',
          height: typeof height === 'number' ? `${height}px` : height,
          borderRadius: 'var(--radius-lg, 8px)',
          overflow: 'hidden',
          border: '1px solid var(--bg-border, #334155)',
          backgroundColor: '#0a0e1a',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          padding: '1.5rem',
          textAlign: 'center',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: '#eab308', marginBottom: '0.5rem' }}>
          <AlertCircle size={20} />
          <span style={{ fontWeight: 700, fontSize: '13px' }}>Google Maps Key Not Set</span>
        </div>
        <p style={{ color: '#94a3b8', fontSize: '12px', maxWidth: '400px', margin: '0 0 0.75rem 0' }}>
          Set <code>VITE_GOOGLE_MAPS_API_KEY</code> to render the DWEG confidence field heatmap layer.
        </p>
        <div style={{ fontSize: '11px', color: '#64748b' }}>
          Evidence density field contains {confidenceField?.features?.length || 0} spatial points.
        </div>
      </div>
    );
  }

  return (
    <div
      style={{
        position: 'relative',
        width: '100%',
        height: typeof height === 'number' ? `${height}px` : height,
        borderRadius: 'var(--radius-lg, 8px)',
        overflow: 'hidden',
        border: '1px solid var(--bg-border, #334155)',
      }}
    >
      <APIProvider apiKey={apiKey} libraries={['visualization', 'marker']}>
        <Map
          defaultCenter={computedCenter}
          defaultZoom={zoom}
          minZoom={3}
          maxZoom={18}
          styles={GOOGLE_MAPS_DARK_STYLE}
          disableDefaultUI={true}
          gestureHandling="greedy"
          style={{ width: '100%', height: '100%' }}
        >
          <ConfidenceFieldInner
            confidenceField={confidenceField}
            initialCenter={computedCenter}
            zoom={zoom}
          />
        </Map>
      </APIProvider>

      {/* Heatmap Gradient Legend */}
      <div
        style={{
          position: 'absolute',
          bottom: '16px',
          right: '16px',
          zIndex: 10,
          backgroundColor: 'rgba(15, 23, 42, 0.92)',
          backdropFilter: 'blur(8px)',
          padding: '8px 12px',
          borderRadius: '6px',
          border: '1px solid var(--bg-border, #334155)',
          fontSize: '11px',
          color: 'var(--text-secondary, #94a3b8)',
          boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.4)',
        }}
      >
        <div style={{ fontWeight: 600, color: 'var(--text-primary, #f1f5f9)', marginBottom: '4px' }}>
          Evidence Density Field
        </div>
        <div
          style={{
            height: '8px',
            width: '140px',
            borderRadius: '4px',
            background:
              'linear-gradient(to right, rgb(33, 102, 172), rgb(103, 169, 207), rgb(253, 219, 199), rgb(239, 138, 98), rgb(178, 24, 43))',
            marginBottom: '4px',
          }}
        />
        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '10px' }}>
          <span>Low (0%)</span>
          <span>High (100%)</span>
        </div>
      </div>
    </div>
  );
};
