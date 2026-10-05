import { describe, it, expect } from 'vitest';
import {
  calculateHeatIndex,
  calculateWeatherSeverityIndex,
  generateSyntheticObservations,
  generateSyntheticEvents,
  INDIAN_STATION_CATALOG,
  mergeEventsWithDemo,
  mergeObservationsWithDemo,
} from '../utils/demoDataLayer';
import type { WeatherEvent, WeatherObservationFeature } from '../types';

describe('Synthetic Weather Telemetry & Demo Data Layer Suite', () => {
  it('calculates meteorologically accurate Heat Index based on Rothfusz equation', () => {
    // 38°C at 50% relative humidity
    const hi1 = calculateHeatIndex(38, 50);
    expect(hi1).toBeGreaterThan(45); // Extreme heat stress

    // Moderate temp below 26.7°C returns original temp
    const hi2 = calculateHeatIndex(24, 70);
    expect(hi2).toBe(24);
  });

  it('calculates deterministic SkyPulse Weather Severity Index within 0-100 bounds', () => {
    const res = calculateWeatherSeverityIndex({
      temperatureC: 38,
      humidityPct: 80,
      rainMm: 45,
      windSpeedKmh: 35,
      windGustKmh: 50,
      pressureHpa: 1005,
    });

    expect(res.severityIndex).toBeGreaterThanOrEqual(0);
    expect(res.severityIndex).toBeLessThanOrEqual(100);
    expect(['LOW', 'MODERATE', 'ELEVATED', 'SEVERE', 'EXTREME']).toContain(res.riskTier);
    expect(res.severityIndex).toBeGreaterThan(50); // Severe weather conditions
  });

  it('generates deterministic observations across nationwide Indian stations', () => {
    const obsPass1 = generateSyntheticObservations();
    const obsPass2 = generateSyntheticObservations();

    expect(obsPass1.length).toBeGreaterThanOrEqual(200);

    // Verify determinism (pass 1 matches pass 2 exactly)
    expect(obsPass1[0].temperature_c).toBe(obsPass2[0].temperature_c);
    expect(obsPass1[0].humidity_percent).toBe(obsPass2[0].humidity_percent);
    expect(obsPass1[0].rain_mm).toBe(obsPass2[0].rain_mm);

    // Verify tagging
    expect(obsPass1[0].source).toBe('National Mesonet Array');
    expect(obsPass1[0].layer_type).toBe('WEATHER_OBSERVATION');

    // Check spatial diversity (North, South, East, West, Central, Northeast)
    const states = new Set(obsPass1.map((o) => o.state));
    expect(states.has('Maharashtra')).toBe(true);
    expect(states.has('Delhi')).toBe(true);
    expect(states.has('Karnataka')).toBe(true);
    expect(states.has('West Bengal')).toBe(true);
    expect(states.has('Odisha')).toBe(true);
    expect(states.has('Assam')).toBe(true);
    expect(states.has('Meghalaya')).toBe(true);
    expect(states.has('Jammu and Kashmir') || states.has('Ladakh')).toBe(true);
  });

  it('generates distributed synthetic events with nationwide coverage', () => {
    const events = generateSyntheticEvents();

    expect(events.length).toBeGreaterThanOrEqual(60);
    for (const ev of events) {
      expect(ev.is_synthetic).toBe(true);
      expect(ev.source).toBe('National Sensor Array');
      expect(ev.latitude).toBeDefined();
      expect(ev.longitude).toBeDefined();
      expect(ev.category).toBeDefined();
      expect(ev.severity).toBeGreaterThanOrEqual(1);
      expect(ev.severity).toBeLessThanOrEqual(4);
    }
  });

  it('performs additive merging without mutating existing backend data', () => {
    const realBackendEvent: WeatherEvent = {
      id: 'real-backend-event-001',
      title: 'Real Ingested Flood in Assam',
      category: 'FLOODING',
      severity: 3,
      confidence_score: 0.95,
      verification_status: 'VERIFIED',
      state: 'Assam',
      latitude: 26.14,
      longitude: 91.73,
      is_active: true,
      evidence_count: 3,
      sources_count: 2,
    };

    const realObs: WeatherObservationFeature = {
      id: 'real-obs-1',
      name: 'Real IMD Station',
      state: 'Odisha',
      latitude: 20.29,
      longitude: 85.82,
      temp_label: '31°C',
      weather_icon: '⛅',
      condition: 'Partly Cloudy',
      source: 'IMD Station Network',
      observed_at: new Date().toISOString(),
      warning_status: 'NORMAL',
      incident_count: 0,
      layer_type: 'WEATHER_OBSERVATION',
    };

    // When demo mode is not active or active, real backend items are preserved
    const mergedEvents = mergeEventsWithDemo([realBackendEvent]);
    expect(mergedEvents.some((e) => e.id === 'real-backend-event-001')).toBe(true);

    const mergedObs = mergeObservationsWithDemo([realObs]);
    expect(mergedObs.some((o) => o.id === 'real-obs-1')).toBe(true);
  });
});
