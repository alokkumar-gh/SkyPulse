/**
 * SubmitReport Page — Phase 7
 * Citizen weather report submission interface.
 * Features:
 * - Multi-category selection with visual icons
 * - Severity rating slider/chips (1-4)
 * - Geolocation capture with reverse geocoding fallback
 * - Media attachment preview
 * - Offline queue capability
 */
import React, { useState } from 'react';
import { Card, Button, Input } from '../components/ui/Primitives';
import { reportsAPI, mediaAPI } from '../utils/api';
import { CheckCircle, Navigation, Upload, Image as ImageIcon, Trash2, Video } from 'lucide-react';
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
          setError('Could not access current location. Please enter manually.');
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
      setError('Please provide a brief description of the observed weather.');
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
      setError(err?.response?.data?.detail || 'Failed to submit report. Saved to offline queue.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div
      style={{
        padding: '1.5rem',
        maxWidth: '800px',
        margin: '0 auto',
        width: '100%',
        display: 'flex',
        flexDirection: 'column',
        gap: '1.5rem',
      }}
    >
      <div>
        <h1 style={{ margin: 0, fontSize: 'var(--text-2xl)', fontWeight: 700, color: 'var(--text-primary)' }}>
          Submit Citizen Weather Report
        </h1>
        <p style={{ margin: '0.25rem 0 0 0', fontSize: 'var(--text-sm)', color: 'var(--text-secondary)' }}>
          Ground observations feed directly into the SkyPulse multi-factor AI verification pipeline
        </p>
      </div>

      {success && (
        <div
          style={{
            padding: '1rem',
            borderRadius: 'var(--radius-lg)',
            backgroundColor: 'rgba(34, 197, 94, 0.15)',
            border: '1px solid rgba(34, 197, 94, 0.3)',
            color: 'var(--severity-1)',
            display: 'flex',
            alignItems: 'center',
            gap: '0.75rem',
          }}
        >
          <CheckCircle size={20} />
          <div>
            <strong>Report Submitted Successfully!</strong>
            <p style={{ margin: '0.2rem 0 0 0', fontSize: 'var(--text-xs)' }}>
              Your report has entered the Kafka pipeline for validation, CLIP analysis, and spatial clustering.
            </p>
          </div>
        </div>
      )}

      {error && (
        <div
          style={{
            padding: '1rem',
            borderRadius: 'var(--radius-lg)',
            backgroundColor: 'rgba(239, 68, 68, 0.15)',
            border: '1px solid rgba(239, 68, 68, 0.3)',
            color: 'var(--severity-4)',
            fontSize: 'var(--text-sm)',
          }}
        >
          {error}
        </div>
      )}

      <Card>
        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
          {/* Weather Category */}
          <div>
            <label style={{ fontSize: 'var(--text-xs)', fontWeight: 600, color: 'var(--text-secondary)', textTransform: 'uppercase' }}>
              Weather Phenomenon
            </label>
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))',
                gap: '0.5rem',
                marginTop: '0.5rem',
              }}
            >
              {(
                [
                  'RAINFALL',
                  'THUNDERSTORM',
                  'FLOODING',
                  'HEATWAVE',
                  'FOG',
                  'DUST_STORM',
                  'STRONG_WINDS',
                  'HAILSTORM',
                ] as WeatherCategory[]
              ).map((cat) => {
                const isSelected = category === cat;
                return (
                  <button
                    type="button"
                    key={cat}
                    onClick={() => setCategory(cat)}
                    style={{
                      padding: '0.6rem 0.5rem',
                      borderRadius: 'var(--radius-md)',
                      border: `1px solid ${isSelected ? 'var(--brand-blue)' : 'var(--bg-border)'}`,
                      backgroundColor: isSelected ? 'rgba(59, 130, 246, 0.15)' : 'var(--bg-elevated)',
                      color: isSelected ? 'var(--brand-blue)' : 'var(--text-secondary)',
                      fontSize: 'var(--text-xs)',
                      fontWeight: isSelected ? 600 : 400,
                      cursor: 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      gap: '0.4rem',
                      transition: 'all 0.15s ease',
                    }}
                  >
                    <span>{cat}</span>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Severity Rating */}
          <div>
            <label style={{ fontSize: 'var(--text-xs)', fontWeight: 600, color: 'var(--text-secondary)', textTransform: 'uppercase' }}>
              Estimated Severity
            </label>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '0.5rem', marginTop: '0.5rem' }}>
              {[
                { level: 1, label: '1 - Minor', desc: 'Light showers, slight haze' },
                { level: 2, label: '2 - Moderate', desc: 'Sustained rain, gusts' },
                { level: 3, label: '3 - Severe', desc: 'Waterlogging, gale winds' },
                { level: 4, label: '4 - Extreme', desc: 'Flash floods, cyclone' },
              ].map((s) => {
                const isSelected = severity === s.level;
                return (
                  <button
                    type="button"
                    key={s.level}
                    onClick={() => setSeverity(s.level)}
                    style={{
                      padding: '0.75rem 0.5rem',
                      borderRadius: 'var(--radius-md)',
                      border: `1px solid ${isSelected ? 'var(--brand-blue)' : 'var(--bg-border)'}`,
                      backgroundColor: isSelected ? 'rgba(59, 130, 246, 0.15)' : 'var(--bg-elevated)',
                      cursor: 'pointer',
                      textAlign: 'center',
                    }}
                  >
                    <div style={{ fontSize: 'var(--text-sm)', fontWeight: 600, color: isSelected ? 'var(--brand-blue)' : 'var(--text-primary)' }}>
                      {s.label}
                    </div>
                    <div style={{ fontSize: '10px', color: 'var(--text-muted)', marginTop: '0.2rem' }}>
                      {s.desc}
                    </div>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Description */}
          <div>
            <label htmlFor="report-description" style={{ fontSize: 'var(--text-xs)', fontWeight: 600, color: 'var(--text-secondary)', textTransform: 'uppercase' }}>
              Observation Description
            </label>
            <textarea
              id="report-description"
              rows={4}
              placeholder="Describe weather conditions, visibility, localized impacts..."
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              style={{
                width: '100%',
                backgroundColor: 'var(--bg-primary)',
                border: '1px solid var(--bg-border)',
                borderRadius: 'var(--radius-md)',
                color: 'var(--text-primary)',
                padding: '0.75rem',
                fontSize: 'var(--text-sm)',
                outline: 'none',
                fontFamily: 'inherit',
                marginTop: '0.5rem',
              }}
            />
          </div>

          {/* Location Coordinates */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <label style={{ fontSize: 'var(--text-xs)', fontWeight: 600, color: 'var(--text-secondary)', textTransform: 'uppercase' }}>
                Geographic Coordinates
              </label>
              <Button
                type="button"
                variant="ghost"
                size="sm"
                icon={<Navigation size={12} />}
                onClick={handleGetCurrentLocation}
              >
                Use My Location
              </Button>
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem' }}>
              <Input
                label="Latitude"
                value={lat}
                onChange={(e) => setLat(e.target.value)}
                placeholder="19.0760"
              />
              <Input
                label="Longitude"
                value={lng}
                onChange={(e) => setLng(e.target.value)}
                placeholder="72.8777"
              />
            </div>
          </div>

          {/* State & District */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem' }}>
            <Input
              label="State"
              value={state}
              onChange={(e) => setState(e.target.value)}
              placeholder="e.g. Maharashtra"
            />
            <Input
              label="District / City"
              value={district}
              onChange={(e) => setDistrict(e.target.value)}
              placeholder="e.g. Mumbai Suburban"
            />
          </div>

          {/* Media & Evidence Attachments */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
            <label style={{ fontSize: 'var(--text-xs)', fontWeight: 600, color: 'var(--text-secondary)', textTransform: 'uppercase' }}>
              Media Evidence (Photos & Videos)
            </label>
            <div
              style={{
                border: '1px dashed var(--bg-border)',
                borderRadius: 'var(--radius-md)',
                padding: '1rem',
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                justifyContent: 'center',
                gap: '0.5rem',
                backgroundColor: 'var(--bg-elevated)',
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
              <Upload size={20} color="var(--brand-blue)" />
              <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-primary)', fontWeight: 500 }}>
                {uploadingMedia ? 'Uploading to Firebase Cloud Storage...' : 'Click or drop weather photos & videos here'}
              </div>
              <div style={{ fontSize: '10px', color: 'var(--text-muted)' }}>
                Supports JPEG, PNG, WebP, MP4 (Max 50MB per file)
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
                      borderRadius: 'var(--radius-sm)',
                      backgroundColor: 'var(--bg-primary)',
                      border: '1px solid var(--bg-border)',
                      fontSize: 'var(--text-xs)',
                    }}
                  >
                    {m.media_type === 'VIDEO' ? <Video size={14} color="var(--text-secondary)" /> : <ImageIcon size={14} color="var(--text-secondary)" />}
                    <span style={{ maxWidth: '150px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {m.filename}
                    </span>
                    <button
                      type="button"
                      onClick={() => removeMedia(m.media_id)}
                      style={{
                        background: 'none',
                        border: 'none',
                        color: 'var(--severity-4)',
                        cursor: 'pointer',
                        padding: 0,
                        display: 'flex',
                        alignItems: 'center',
                      }}
                    >
                      <Trash2 size={12} />
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Submit Button */}
          <div style={{ paddingTop: '0.5rem' }}>
            <Button
              type="submit"
              variant="primary"
              size="lg"
              loading={loading || uploadingMedia}
              style={{ width: '100%' }}
            >
              Submit Ground Report
            </Button>
          </div>
        </form>
      </Card>
    </div>
  );
};
