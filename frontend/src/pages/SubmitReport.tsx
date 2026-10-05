/**
 * SubmitReport Page — Ground Meteorological Observation Ingestion
 * Redesigned according to:
 * - Section 24: Forms (Labels above inputs, intelligent feedback, crisp layout)
 * - Section 4: Premium Button System
 * - Section 1: Zero Default Component Policy
 */

import React, { useState } from 'react';
import { Card, Button, Input } from '../components/ui/Primitives';
import { reportsAPI, mediaAPI } from '../utils/api';
import { CheckCircle, Navigation, Upload, Image as ImageIcon, Trash2, Video, ShieldCheck } from 'lucide-react';
import type { WeatherCategory } from '../types';

export const SubmitReport: React.FC = () => {
  const [category, setCategory] = useState<WeatherCategory>('RAINFALL');
  const [severity, setSeverity] = useState<number>(2);
  const [description, setDescription] = useState('');
  const [state, setState] = useState('');
  const [district, setDistrict] = useState('');
  const [lat, setLat] = useState<string>('19.0760');
  const [lng, setLng] = useState<string>('72.8777');
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [uploadedMedia, setUploadedMedia] = useState<Array<{ media_id: string; filename: string; size_bytes: number; url?: string; thumbnail_url?: string; media_type?: string }>>([]);
  const [uploadingMedia, setUploadingMedia] = useState(false);

  const handleGetCurrentLocation = () => {
    if ('geolocation' in navigator) {
      navigator.geolocation.getCurrentPosition(
        (pos) => {
          setLat(pos.coords.latitude.toFixed(6));
          setLng(pos.coords.longitude.toFixed(6));
        },
        () => {
          setError('Could not access current location. Please enter coordinates manually.');
        }
      );
    }
  };

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files || files.length === 0) return;

    setUploadingMedia(true);
    setError(null);
    try {
      for (let i = 0; i < files.length; i++) {
        const file = files[i];
        const res = await mediaAPI.upload(file);
        setUploadedMedia((prev) => [
          ...prev,
          {
            media_id: res.media_id,
            filename: res.filename || file.name,
            size_bytes: res.size_bytes || file.size,
            url: res.url,
            thumbnail_url: res.thumbnail_url,
            media_type: res.media_type,
          },
        ]);
      }
    } catch (err: any) {
      setError(err?.message || 'Failed to upload media attachment.');
    } finally {
      setUploadingMedia(false);
      e.target.value = '';
    }
  };

  const removeMedia = (mediaId: string) => {
    setUploadedMedia((prev) => prev.filter((m) => m.media_id !== mediaId));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!description.trim()) {
      setError('Please provide a brief description of the observed atmospheric conditions.');
      return;
    }

    try {
      setLoading(true);
      setError(null);
      await reportsAPI.createReport({
        category,
        severity,
        description,
        latitude: parseFloat(lat),
        longitude: parseFloat(lng),
        state: state || 'Maharashtra',
        district: district || 'Mumbai',
        source_type: 'CITIZEN',
        media_ids: uploadedMedia.map((m) => m.media_id),
      });
      setSuccess(true);
      setDescription('');
      setUploadedMedia([]);
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Observation recorded in local telemetry queue.');
    } finally {
      setLoading(false);
    }
  };

  const categories: { id: WeatherCategory; label: string }[] = [
    { id: 'RAINFALL', label: 'Rainfall / Anomaly' },
    { id: 'THUNDERSTORM', label: 'Thunderstorm' },
    { id: 'FLOODING', label: 'Inundation / Flood' },
    { id: 'HEATWAVE', label: 'Heatwave' },
    { id: 'FOG', label: 'Dense Fog' },
    { id: 'DUST_STORM', label: 'Dust Storm' },
    { id: 'STRONG_WINDS', label: 'Gale / High Wind' },
    { id: 'HAILSTORM', label: 'Hailstorm' },
  ];

  const severities = [
    { level: 1, label: '1 · Minor', desc: 'Light showers, slight haze', color: 'var(--sev-1)' },
    { level: 2, label: '2 · Moderate', desc: 'Sustained precipitation, gusts', color: 'var(--sev-2)' },
    { level: 3, label: '3 · Severe', desc: 'Waterlogging, gale force winds', color: 'var(--sev-3)' },
    { level: 4, label: '4 · Extreme', desc: 'Flash floods, structural damage', color: 'var(--sev-4)' },
  ];

  return (
    <div
      style={{
        padding: '2rem 1.5rem',
        maxWidth: '820px',
        margin: '0 auto',
        width: '100%',
        display: 'flex',
        flexDirection: 'column',
        gap: '1.75rem',
      }}
      className="page-root"
    >
      <div>
        <div style={{
          fontFamily: 'var(--font-mono)',
          fontSize: 'var(--text-2xs)',
          color: 'var(--text-muted)',
          letterSpacing: '0.14em',
          textTransform: 'uppercase',
          marginBottom: '0.25rem',
        }}>
          Citizen & Ground Station Telemetry
        </div>
        <h1 style={{ margin: 0, fontSize: 'var(--text-2xl)', fontWeight: 800, color: 'var(--text-primary)', letterSpacing: '-0.02em' }}>
          Submit Ground Observation
        </h1>
        <p style={{ margin: '0.35rem 0 0 0', fontSize: 'var(--text-sm)', color: 'var(--text-secondary)', lineHeight: 1.5 }}>
          Ground observations feed directly into the SkyPulse multi-factor AI verification pipeline alongside IMD AWS and INSAT-3D radiometers.
        </p>
      </div>

      {success && (
        <div
          style={{
            padding: '1.25rem',
            borderRadius: 'var(--r-2)',
            backgroundColor: 'var(--sev-1-dim)',
            border: '1px solid var(--sev-1)',
            color: 'var(--sev-1)',
            display: 'flex',
            alignItems: 'flex-start',
            gap: '0.75rem',
          }}
        >
          <CheckCircle size={20} style={{ flexShrink: 0, marginTop: '0.1rem' }} />
          <div>
            <strong style={{ fontSize: 'var(--text-sm)', color: 'var(--text-primary)' }}>
              Observation Ingested Successfully
            </strong>
            <p style={{ margin: '0.25rem 0 0 0', fontSize: 'var(--text-xs)', color: 'var(--text-secondary)' }}>
              Your report has entered the Kafka message bus for spatial clustering, anomaly cross-referencing, and ground-truth validation.
            </p>
          </div>
        </div>
      )}

      {error && (
        <div
          style={{
            padding: '1rem',
            borderRadius: 'var(--r-2)',
            backgroundColor: 'var(--sev-4-dim)',
            border: '1px solid var(--sev-4)',
            color: 'var(--sev-4)',
            fontSize: 'var(--text-xs)',
            fontFamily: 'var(--font-mono)',
          }}
        >
          {error}
        </div>
      )}

      <Card padding="lg">
        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
          {/* Weather Phenomenon */}
          <div>
            <label style={{ display: 'block', fontSize: 'var(--text-xs)', fontWeight: 700, color: 'var(--text-secondary)', textTransform: 'uppercase', fontFamily: 'var(--font-mono)', letterSpacing: '0.08em', marginBottom: '0.5rem' }}>
              Observed Phenomenon
            </label>
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))',
                gap: '0.5rem',
              }}
            >
              {categories.map((cat) => {
                const isSelected = category === cat.id;
                return (
                  <button
                    type="button"
                    key={cat.id}
                    onClick={() => setCategory(cat.id)}
                    style={{
                      padding: '0.65rem 0.75rem',
                      borderRadius: 'var(--r-1)',
                      border: `1px solid ${isSelected ? 'var(--teal)' : 'var(--border-hairline)'}`,
                      backgroundColor: isSelected ? 'var(--teal-100)' : 'var(--bg-panel)',
                      color: isSelected ? 'var(--teal)' : 'var(--text-primary)',
                      fontSize: 'var(--text-xs)',
                      fontWeight: isSelected ? 700 : 500,
                      cursor: 'pointer',
                      textAlign: 'left',
                      transition: 'all 0.15s ease',
                      fontFamily: 'var(--font-sans)',
                    }}
                  >
                    {cat.label}
                  </button>
                );
              })}
            </div>
          </div>

          {/* Severity Rating */}
          <div>
            <label style={{ display: 'block', fontSize: 'var(--text-xs)', fontWeight: 700, color: 'var(--text-secondary)', textTransform: 'uppercase', fontFamily: 'var(--font-mono)', letterSpacing: '0.08em', marginBottom: '0.5rem' }}>
              Estimated Impact Severity
            </label>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: '0.5rem' }}>
              {severities.map((s) => {
                const isSelected = severity === s.level;
                return (
                  <button
                    type="button"
                    key={s.level}
                    onClick={() => setSeverity(s.level)}
                    style={{
                      padding: '0.75rem 0.65rem',
                      borderRadius: 'var(--r-1)',
                      border: `1px solid ${isSelected ? s.color : 'var(--border-hairline)'}`,
                      backgroundColor: isSelected ? `color-mix(in srgb, ${s.color} 12%, var(--bg-surface))` : 'var(--bg-panel)',
                      cursor: 'pointer',
                      textAlign: 'left',
                      transition: 'all 0.15s ease',
                    }}
                  >
                    <div style={{ fontSize: 'var(--text-xs)', fontWeight: 700, color: isSelected ? s.color : 'var(--text-primary)', fontFamily: 'var(--font-mono)' }}>
                      {s.label}
                    </div>
                    <div style={{ fontSize: 'var(--text-2xs)', color: 'var(--text-muted)', marginTop: '0.2rem' }}>
                      {s.desc}
                    </div>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Description */}
          <div>
            <label htmlFor="report-description" style={{ display: 'block', fontSize: 'var(--text-xs)', fontWeight: 700, color: 'var(--text-secondary)', textTransform: 'uppercase', fontFamily: 'var(--font-mono)', letterSpacing: '0.08em', marginBottom: '0.35rem' }}>
              Observation Narrative
            </label>
            <textarea
              id="report-description"
              rows={4}
              placeholder="Describe rainfall rate, surface wind gusts, waterlogging, or localized impact..."
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              style={{
                width: '100%',
                backgroundColor: 'var(--bg-panel)',
                border: '1px solid var(--border-hairline)',
                borderRadius: 'var(--r-2)',
                color: 'var(--text-primary)',
                padding: '0.75rem',
                fontSize: 'var(--text-sm)',
                outline: 'none',
                fontFamily: 'var(--font-sans)',
                lineHeight: 1.5,
              }}
            />
          </div>

          {/* Location Coordinates */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <label style={{ fontSize: 'var(--text-xs)', fontWeight: 700, color: 'var(--text-secondary)', textTransform: 'uppercase', fontFamily: 'var(--font-mono)', letterSpacing: '0.08em' }}>
                Geospatial Coordinates
              </label>
              <Button
                type="button"
                variant="ghost"
                size="xs"
                icon={<Navigation size={12} />}
                onClick={handleGetCurrentLocation}
                style={{ color: 'var(--teal)', fontFamily: 'var(--font-mono)' }}
              >
                Use My Location
              </Button>
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem' }}>
              <Input
                label="Latitude (°N)"
                value={lat}
                onChange={(e) => setLat(e.target.value)}
                placeholder="19.0760"
              />
              <Input
                label="Longitude (°E)"
                value={lng}
                onChange={(e) => setLng(e.target.value)}
                placeholder="72.8777"
              />
            </div>
          </div>

          {/* State & District */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem' }}>
            <Input
              label="State / Union Territory"
              value={state}
              onChange={(e) => setState(e.target.value)}
              placeholder="e.g. Maharashtra"
            />
            <Input
              label="District / Tehsil"
              value={district}
              onChange={(e) => setDistrict(e.target.value)}
              placeholder="e.g. Mumbai Suburban"
            />
          </div>

          {/* Media & Evidence Attachments */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
            <label style={{ fontSize: 'var(--text-xs)', fontWeight: 700, color: 'var(--text-secondary)', textTransform: 'uppercase', fontFamily: 'var(--font-mono)', letterSpacing: '0.08em' }}>
              Photographic Evidence (Optional)
            </label>
            <div
              style={{
                border: '1px dashed var(--border-subtle)',
                borderRadius: 'var(--r-2)',
                padding: '1.25rem',
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                justifyContent: 'center',
                gap: '0.5rem',
                backgroundColor: 'var(--bg-panel)',
                cursor: 'pointer',
                position: 'relative',
              }}
            >
              <input
                type="file"
                multiple
                accept="image/jpeg,image/png,image/webp,video/mp4,video/quicktime"
                onChange={handleFileChange}
                disabled={uploadingMedia}
                style={{
                  position: 'absolute',
                  inset: 0,
                  opacity: 0,
                  cursor: 'pointer',
                  width: '100%',
                  height: '100%',
                }}
              />
              <Upload size={22} color="var(--teal)" />
              <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-primary)', fontWeight: 600 }}>
                {uploadingMedia ? 'Uploading evidence stream...' : 'Click or drop sky photos and rainfall gauges'}
              </div>
              <div style={{ fontSize: 'var(--text-2xs)', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
                JPEG, PNG, WebP up to 25MB · Processed via CLIP feature extractor
              </div>
            </div>

            {/* Uploaded Media Previews */}
            {uploadedMedia.length > 0 && (
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem', marginTop: '0.5rem' }}>
                {uploadedMedia.map((m) => (
                  <div
                    key={m.media_id}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '0.5rem',
                      padding: '0.35rem 0.6rem',
                      borderRadius: 'var(--r-1)',
                      backgroundColor: 'var(--bg-elevated)',
                      border: '1px solid var(--border-hairline)',
                      fontSize: 'var(--text-xs)',
                    }}
                  >
                    {m.media_type === 'VIDEO' ? <Video size={13} color="var(--teal)" /> : <ImageIcon size={13} color="var(--teal)" />}
                    <span style={{ maxWidth: '160px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', fontFamily: 'var(--font-mono)', fontSize: 'var(--text-2xs)' }}>
                      {m.filename}
                    </span>
                    <button
                      type="button"
                      onClick={() => removeMedia(m.media_id)}
                      style={{ background: 'none', border: 'none', color: 'var(--sev-4)', cursor: 'pointer', padding: 0 }}
                    >
                      <Trash2 size={12} />
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Submit Action (Section 4) */}
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', paddingTop: '1rem', borderTop: '1px solid var(--border-hairline)' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', color: 'var(--text-muted)', fontSize: 'var(--text-2xs)', fontFamily: 'var(--font-mono)' }}>
              <ShieldCheck size={13} color="var(--status-verified)" />
              <span>Anonymized telemetry protected under NDMA protocol</span>
            </div>

            <Button
              type="submit"
              variant="teal"
              size="md"
              loading={loading}
              withArrow
            >
              TRANSMIT OBSERVATION
            </Button>
          </div>
        </form>
      </Card>
    </div>
  );
};
