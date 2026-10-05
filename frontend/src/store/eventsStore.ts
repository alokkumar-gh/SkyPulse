import { create } from 'zustand';
import { eventsAPI, STATE_CENTROIDS, generateEventNarrative } from '../utils/api';
import { mergeEventsWithDemo, mergeObservationsWithDemo, generateSyntheticEvents, isDemoModeActive } from '../utils/demoDataLayer';
import type { WeatherEvent, DashboardFilters, PaginatedResponse, CoverageReport, WeatherObservationFeature } from '../types';

interface EventsState {
  events: WeatherEvent[];
  mapEvents: WeatherEvent[];
  observations: WeatherObservationFeature[];
  showObservations: boolean;
  coverage: CoverageReport | null;
  total: number;
  page: number;
  perPage: number;
  isLoading: boolean;
  loading: boolean;
  error: string | null;
  selectedEventId: string | null;
  selectedEvent: WeatherEvent | null;
  isLoadingDetail: boolean;
  serverTime: string | null;
  lastSyncRevision: number | null;
  lastSyncAt: string | null;

  // Actions
  fetchEvents: (filters?: Partial<DashboardFilters> & { status?: string; category?: string; state?: string; district?: string; severity?: number; is_active?: boolean }, page?: number, perPage?: number) => Promise<void>;
  fetchMapEvents: (filters?: { category?: string; severity?: number; state?: string; district?: string; hours?: number; time_range?: string; layers?: string; zoom?: number }) => Promise<void>;
  fetchObservations: (zoom?: number) => Promise<void>;
  toggleShowObservations: () => void;
  fetchCoverage: () => Promise<void>;
  fetchEventDetail: (eventId: string) => Promise<void>;
  selectEvent: (eventId: string | null) => void;
  setSelectedEvent: (event: WeatherEvent | null) => void;
  addOrUpdateEvent: (event: WeatherEvent) => void;
  removeEvent: (eventId: string) => void;
  updateObservation: (obs: any) => void;
  updateObservationBatch: (obsList: any[]) => void;
  expireOldEvents: () => void;
  applyDeltaSync: (delta: { created?: any[]; updated?: any[]; expired?: string[]; deactivated?: string[]; server_time?: string; revision?: number }) => void;
  updateEventVerification: (eventId: string, status: string, confidence: number) => void;
  markEventAnomalous: (eventId: string, zScore?: number) => void;
  clearError: () => void;
}

export function normalizeMapFeature(f: any): WeatherEvent {
  const props = f?.properties || {};
  const geom = f?.geometry || {};
  const id = props.event_id || props.id || f.id || `map-${Math.random().toString(36).slice(2, 9)}`;
  const isPoint = geom.type === 'Point' && Array.isArray(geom.coordinates) && geom.coordinates.length >= 2;
  let lon = isPoint ? Number(geom.coordinates[0]) : (typeof props.longitude === 'number' ? props.longitude : undefined);
  let lat = isPoint ? Number(geom.coordinates[1]) : (typeof props.latitude === 'number' ? props.latitude : undefined);
  const state = props.state || '';
  const district = props.district || '';
  const city = props.city || '';
  const locParts = [city, district, state].filter(Boolean);
  const locStr = props.location_name || (locParts.length > 0 ? Array.from(new Set(locParts)).join(', ') : 'India');

  // Fallback to state centroid if lat/lon is missing
  if ((lat === undefined || lon === undefined || isNaN(lat) || isNaN(lon)) && state && STATE_CENTROIDS[state]) {
    const [cLat, cLon] = STATE_CENTROIDS[state];
    const hash = (id || '').split('').reduce((acc: number, char: string) => acc + char.charCodeAt(0), 0);
    lat = Number((cLat + ((hash % 17) - 8) * 0.08).toFixed(4));
    lon = Number((cLon + (((hash >> 2) % 17) - 8) * 0.08).toFixed(4));
  }

  let rawCat = (props.category || 'WEATHER').toUpperCase();
  const cat = rawCat as WeatherEvent['category'];
  const catTitle = cat.charAt(0).toUpperCase() + cat.slice(1).toLowerCase();

  const supporting_signal_count = Number(props.supporting_signal_count) || Number(props.evidence_count) || Number(props.signal_count) || 1;
  const independent_source_count = Number(props.independent_source_count) || Number(props.sources_count) || Number(props.source_count) || 1;
  const corroborating_source_count = Number(props.corroborating_source_count) || (independent_source_count > 1 ? independent_source_count : 0);

  const rawStatus = (props.verification_status || props.status || props.event_nature || 'UNVERIFIED').toUpperCase();
  const verification_status = (['VERIFIED', 'LIKELY', 'UNVERIFIED', 'CONTRADICTED', 'REQUIRES_REVIEW', 'UNDER_REVIEW'].includes(rawStatus)
    ? rawStatus
    : 'UNVERIFIED') as WeatherEvent['verification_status'];

  const confidence_score = typeof props.confidence_score === 'number' && !isNaN(props.confidence_score) ? props.confidence_score : 0.54;

  const source_claim_label = props.source_claim_label || (
    independent_source_count >= 2 && corroborating_source_count >= 2
      ? 'MULTI-SOURCE INTELLIGENCE'
      : independent_source_count >= 2
      ? 'LIMITED CORROBORATION'
      : 'SINGLE-SOURCE SIGNAL'
  );

  const narrative = generateEventNarrative({
    category: cat,
    city,
    district,
    state,
    verification_status,
    independent_source_count,
    evidence_count: supporting_signal_count,
    confidence_score,
  });

  const title = props.title || `${catTitle} reported in ${locStr}`;
  const summary = props.summary || narrative;
  const description = props.description || narrative;

  const confidence_tier = props.confidence_tier || props.confidence_tier_label || (
    confidence_score >= 0.85 ? 'VERY HIGH' : confidence_score >= 0.70 ? 'HIGH' : confidence_score >= 0.40 ? 'MODERATE' : 'LOW'
  );

  return {
    id,
    category: cat,
    sub_category: props.sub_category,
    phenomenon: props.phenomenon,
    title,
    summary,
    description,
    latitude: lat,
    longitude: lon,
    state,
    district,
    city,
    location: {
      state,
      district,
      city,
      lat,
      lon,
      confidence: lat !== undefined ? 'HIGH' : 'LOW',
    },
    severity: Number(props.severity) || 2,
    confidence_score,
    confidence_tier,
    confidence_tier_label: confidence_tier,
    verification_status,
    event_nature: verification_status,
    evidence_count: supporting_signal_count,
    signal_count: supporting_signal_count,
    supporting_signal_count,
    sources_count: independent_source_count,
    independent_source_count,
    corroborating_source_count,
    source_claim_label,
    signal_type: props.signal_type || 'EVENT',
    layer_type: props.layer_type || 'WEATHER_EVENT',
    valid_from: props.valid_from,
    valid_until: props.valid_until,
    telemetry: props.telemetry,
    temperature_c: props.temperature_c,
    apparent_temperature_c: props.apparent_temperature_c,
    temp_label: props.temp_label,
    weather_icon: props.weather_icon,
    condition: props.condition || props.weather_condition,
    weather_condition: props.weather_condition || props.condition,
    is_current_observation: props.is_current_observation !== undefined ? Boolean(props.is_current_observation) : true,
    is_current_observation_supported: props.is_current_observation_supported,
    observation_summary: props.observation_summary,
    observation_status_label: props.observation_status_label,
    icon: props.icon,
    label: props.label,
    is_anomalous: Boolean(props.is_anomalous),
    is_active: true,
    is_demo: false,
    first_reported_at: props.first_reported_at || props.last_updated_at || new Date().toISOString(),
    last_updated_at: props.last_updated_at || new Date().toISOString(),
    observed_at: props.observed_at || props.first_reported_at,
    ingested_at: props.ingested_at,
    last_seen_at: props.last_seen_at,
    expires_at: props.expires_at,
    lifecycle_status: props.lifecycle_status || props.status,
    freshness_label: props.freshness_label,
    freshness_category: props.freshness_category,
    has_polygon: Boolean(props.has_polygon),
    hazard_polygon: props.hazard_polygon || (geom.type === 'Polygon' || geom.type === 'MultiPolygon' ? geom : undefined),
    source: props.source || 'National Sensor Array',
  };
}

export function normalizeEvent(ev: any): WeatherEvent {
  if (!ev) return ev;
  const id = ev.id || ev.event_id || `ev-${Math.random().toString(36).slice(2, 9)}`;
  const loc = ev.location;
  const rawLat = ev.latitude ?? loc?.lat ?? ev.centroid_lat;
  const rawLon = ev.longitude ?? loc?.lon ?? ev.centroid_lon;
  const numLat = typeof rawLat === 'number' ? rawLat : typeof rawLat === 'string' && rawLat !== '' ? parseFloat(rawLat) : undefined;
  const numLon = typeof rawLon === 'number' ? rawLon : typeof rawLon === 'string' && rawLon !== '' ? parseFloat(rawLon) : undefined;
  const isValidLat = numLat !== undefined && !isNaN(numLat) && numLat >= -90 && numLat <= 90;
  const isValidLon = numLon !== undefined && !isNaN(numLon) && numLon >= -180 && numLon <= 180;
  let lat = isValidLat ? numLat : undefined;
  let lon = isValidLon ? numLon : undefined;

  const state = ev.state ?? loc?.state ?? ev.primary_state ?? '';
  const district = ev.district ?? loc?.district ?? ev.primary_district ?? '';
  const city = ev.city ?? loc?.city ?? ev.primary_city ?? '';
  const locParts = [city, district, state].filter(Boolean);
  const locStr = ev.location_name || (locParts.length > 0 ? Array.from(new Set(locParts)).join(', ') : 'India');

  // Fallback to state centroid if lat/lon is missing
  if ((lat === undefined || lon === undefined) && state && STATE_CENTROIDS[state]) {
    const [cLat, cLon] = STATE_CENTROIDS[state];
    const hash = (id || '').split('').reduce((acc: number, char: string) => acc + char.charCodeAt(0), 0);
    lat = Number((cLat + ((hash % 17) - 8) * 0.08).toFixed(4));
    lon = Number((cLon + (((hash >> 2) % 17) - 8) * 0.08).toFixed(4));
  }

  let rawCat = (ev.category || ev.hazard_type || '').toUpperCase();
  if (!rawCat || rawCat === 'UNKNOWN') {
    rawCat = 'WEATHER';
  }
  const cat = rawCat as WeatherEvent['category'];
  const catTitle = cat.charAt(0).toUpperCase() + cat.slice(1).toLowerCase();

  const rawConf = ev.confidence_score ?? ev.confidence;
  const confidence_score = typeof rawConf === 'number' && !isNaN(rawConf) ? Math.max(0, Math.min(1, rawConf)) : 0.54;

  const rawStatus = (ev.verification_status || ev.status || ev.event_nature || 'UNVERIFIED').toUpperCase();
  const verification_status = (['VERIFIED', 'LIKELY', 'UNVERIFIED', 'CONTRADICTED', 'REQUIRES_REVIEW', 'UNDER_REVIEW'].includes(rawStatus)
    ? rawStatus
    : 'UNVERIFIED') as WeatherEvent['verification_status'];

  const severity = typeof ev.severity === 'number' ? Math.max(1, Math.min(4, ev.severity)) : 2;
  const supporting_signal_count = Number(ev.supporting_signal_count) || Number(ev.signal_count) || Number(ev.evidence_count) || (Array.isArray(ev.evidence) ? ev.evidence.length : (Array.isArray(ev.evidence_reports) ? ev.evidence_reports.length : 1));
  const independent_source_count = Number(ev.independent_source_count) || (Array.isArray(ev.publishers) && ev.publishers.length > 0 ? ev.publishers.length : (Array.isArray(ev.sources) ? ev.sources.length : (Number(ev.sources_count) || 1)));
  const corroborating_source_count = Number(ev.corroborating_source_count) || (independent_source_count > 1 ? independent_source_count : 0);
  
  const source_claim_label = ev.source_claim_label || (
    independent_source_count >= 2 && corroborating_source_count >= 2
      ? 'MULTI-SOURCE INTELLIGENCE'
      : independent_source_count >= 2
      ? 'LIMITED CORROBORATION'
      : 'SINGLE-SOURCE SIGNAL'
  );

  const narrative = generateEventNarrative({
    category: cat,
    city,
    district,
    state,
    verification_status,
    independent_source_count,
    evidence_count: supporting_signal_count,
    confidence_score,
  });

  const title =
    ev.title ||
    ev.headline ||
    `${catTitle} reported in ${locStr}`;

  const summary = ev.summary || ev.headline || narrative;
  const description = ev.description || narrative;

  const confidence_tier = ev.confidence_tier || ev.confidence_tier_label || (
    confidence_score >= 0.85 ? 'VERY HIGH' : confidence_score >= 0.70 ? 'HIGH' : confidence_score >= 0.40 ? 'MODERATE' : 'LOW'
  );

  const defaultSource = independent_source_count >= 2 ? 'Multi-Source Intelligence' : (ev.publishers?.[0] || 'Single-Source Signal');
  const source = ev.source || ev.source_name || (ev.evidence && ev.evidence[0]?.source_name) || defaultSource;

  const is_current_observation = ev.is_current_observation !== undefined ? Boolean(ev.is_current_observation) : true;
  const is_current_observation_supported = ev.is_current_observation_supported !== undefined ? Boolean(ev.is_current_observation_supported) : (verification_status === 'VERIFIED');
  const observation_status_label = ev.observation_status_label || (
    is_current_observation_supported
      ? 'CURRENT SUPPORTING OBSERVATION: YES'
      : is_current_observation
      ? 'CURRENT WEATHER OBSERVATION: YES | EVENT CORROBORATION: NO'
      : 'NO CURRENT OBSERVATION'
  );

  return {
    ...ev,
    id,
    category: cat,
    title,
    summary,
    description,
    latitude: lat,
    longitude: lon,
    state,
    district,
    city,
    location: {
      state,
      district,
      city,
      lat,
      lon,
      confidence: lat !== undefined ? 'HIGH' : 'LOW',
    },
    severity,
    confidence_score,
    confidence_tier,
    confidence_tier_label: confidence_tier,
    verification_status: verification_status as WeatherEvent['verification_status'],
    event_nature: verification_status,
    evidence_count: supporting_signal_count,
    signal_count: supporting_signal_count,
    supporting_signal_count,
    sources_count: independent_source_count,
    independent_source_count,
    corroborating_source_count,
    source_claim_label,
    is_current_observation,
    is_current_observation_supported,
    observation_summary: ev.observation_summary,
    observation_status_label,
    publishers: ev.publishers || [],
    sources: ev.sources || [],
    evidence: ev.evidence || ev.evidence_reports || [],
    evidence_reports: ev.evidence_reports || [],
    affected_districts: ev.affected_districts || (district ? [district] : []),
    affected_states: ev.affected_states || (state ? [state] : []),
    affected_district_count: ev.affected_district_count || (ev.affected_districts ? ev.affected_districts.length : (district ? 1 : 0)),
    source_published_at: ev.source_published_at || ev.published_at || ev.observed_at || ev.first_reported_at,
    source_updated_at: ev.source_updated_at || ev.last_updated_at,
    freshness_status: ev.freshness_status || ev.freshness_bucket || 'RECENT',
    location_resolution: ev.location_resolution || (city ? 'CITY' : district ? 'DISTRICT' : state ? 'STATE' : 'UNKNOWN'),
    is_anomalous: Boolean(ev.is_anomalous),
    is_active: ev.is_active !== false,
    is_demo: Boolean(ev.is_demo || ev.is_synthetic),
    first_reported_at: ev.source_published_at || ev.published_at || ev.first_reported_at || ev.first_seen_at || ev.created_at || ev.timestamp || new Date().toISOString(),
    last_updated_at: ev.source_updated_at || ev.last_updated_at || ev.last_seen_at || ev.updated_at || ev.timestamp || new Date().toISOString(),
    observed_at: ev.source_published_at || ev.observed_at || ev.first_reported_at,
    ingested_at: ev.ingested_at,
    last_seen_at: ev.last_seen_at,
    expires_at: ev.expires_at,
    lifecycle_status: ev.lifecycle_status || ev.status,
    freshness_label: ev.freshness_label,
    freshness_category: ev.freshness_status || ev.freshness_category || ev.freshness_bucket || 'RECENT',
    source,
  };
}

export const useEventsStore = create<EventsState>((set, get) => ({
  events: [],
  mapEvents: [],
  observations: [],
  showObservations: true,
  coverage: null,
  total: 0,
  page: 1,
  perPage: 25,
  isLoading: false,
  loading: false,
  error: null,
  selectedEventId: null,
  selectedEvent: null,
  isLoadingDetail: false,
  serverTime: null,
  lastSyncRevision: null,
  lastSyncAt: null,

  fetchEvents: async (filters = {}, page = 1, perPage = 25) => {
    set({ isLoading: true, loading: true, error: null });
    try {
      const data: PaginatedResponse<WeatherEvent> = await eventsAPI.list(filters, page, perPage);
      const rawResults = Array.isArray(data?.results)
        ? data.results
        : Array.isArray((data as any)?.events)
        ? (data as any).events
        : Array.isArray(data)
        ? data
        : [];

      const normalizedEvents: WeatherEvent[] = rawResults.map(normalizeEvent).filter(Boolean);
      const mergedEvents: WeatherEvent[] = mergeEventsWithDemo(normalizedEvents, filters);

      const currentMapEvents = get().mapEvents;
      let updatedMapEvents = currentMapEvents;
      if (currentMapEvents.length < mergedEvents.length) {
        const mapById = new Map<string, WeatherEvent>(currentMapEvents.map((e) => [e.id, e]));
        for (const ev of mergedEvents) {
          if (ev.latitude !== undefined && ev.longitude !== undefined && !mapById.has(ev.id)) {
            mapById.set(ev.id, ev);
          }
        }
        updatedMapEvents = Array.from(mapById.values());
      }

      set({
        events: mergedEvents,
        mapEvents: updatedMapEvents,
        total: (data?.total ?? normalizedEvents.length) + (mergedEvents.length - normalizedEvents.length),
        page: data?.page ?? page,
        perPage: data?.per_page ?? perPage,
        isLoading: false,
        loading: false,
      });
    } catch (err) {
      // In demo mode, if backend is temporarily unreachable, fallback gracefully to demo events
      if (isDemoModeActive()) {
        const demoEvents = mergeEventsWithDemo([], filters);
        set({
          events: demoEvents,
          mapEvents: demoEvents,
          total: demoEvents.length,
          page: 1,
          perPage,
          isLoading: false,
          loading: false,
        });
      } else {
        set({
          isLoading: false,
          loading: false,
          error: err instanceof Error ? err.message : 'Failed to load events',
        });
      }
    }
  },

  fetchMapEvents: async (filters = {}) => {
    try {
      const data = await eventsAPI.map(filters);
      let mapped: WeatherEvent[] = [];
      const obsFeatures: WeatherObservationFeature[] = [];
      if (data && Array.isArray(data.features)) {
        const mapById = new Map<string, WeatherEvent>();
        for (const feat of data.features) {
          const ev = normalizeMapFeature(feat);
          if (ev.latitude !== undefined && ev.longitude !== undefined && !isNaN(ev.latitude) && !isNaN(ev.longitude)) {
            if (!mapById.has(ev.id)) {
              mapById.set(ev.id, ev);
            } else {
              const existing = mapById.get(ev.id)!;
              if (ev.hazard_polygon && !existing.hazard_polygon) {
                existing.hazard_polygon = ev.hazard_polygon;
                existing.has_polygon = true;
              }
            }

            // If feature is an observation, also sync into observations array
            if (feat.properties?.signal_type === 'OBSERVATION' || feat.properties?.layer_type === 'WEATHER_OBSERVATION') {
              const p = feat.properties;
              obsFeatures.push({
                id: p.id || (feat as any).id || `obs-${p.district || p.city}`,
                name: p.district || p.city || p.name || 'District',
                city: p.city,
                state: p.state || 'India',
                latitude: ev.latitude,
                longitude: ev.longitude,
                temperature_c: p.temperature_c,
                temp_label: p.temp_label || (p.temperature_c != null ? `${Math.round(p.temperature_c)}°C` : '--'),
                weather_icon: p.weather_icon || p.icon || '⛅',
                condition: p.condition || p.weather_condition || 'Fair',
                humidity_percent: p.humidity_percent,
                rain_mm: p.rain_mm,
                wind_speed_kmh: p.wind_speed_kmh,
                source: p.source || 'Open-Meteo',
                model: p.model,
                observed_at: p.observed_at || new Date().toISOString(),
                freshness_label: p.freshness_label,
                freshness_category: p.freshness_category,
                warning_status: p.warning_status || 'NORMAL',
                incident_count: p.incident_count || 0,
                layer_type: 'WEATHER_OBSERVATION',
              });
            }
          }
        }

        // Also merge existing normalized events from store if missing
        for (const ev of get().events) {
          if (ev.latitude !== undefined && ev.longitude !== undefined && !mapById.has(ev.id)) {
            mapById.set(ev.id, ev);
          }
        }

        mapped = Array.from(mapById.values());
      } else if (data && Array.isArray((data as any).points)) {
        mapped = (data as any).points.map(normalizeEvent).filter((ev: any) => ev.latitude !== undefined && ev.longitude !== undefined);
      }

      const mergedMapEvents = mergeEventsWithDemo(mapped, filters);
      const mergedObs = mergeObservationsWithDemo(obsFeatures);

      const updates: Partial<EventsState> = { mapEvents: mergedMapEvents };
      if ((data as any)?.coverage) {
        updates.coverage = (data as any).coverage;
      }
      if (mergedObs.length > 0) {
        updates.observations = mergedObs;
      }
      set(updates as any);
    } catch (err) {
      if (isDemoModeActive()) {
        const demoEvents = mergeEventsWithDemo([], filters);
        const demoObs = mergeObservationsWithDemo([]);
        set({ mapEvents: demoEvents, observations: demoObs });
      } else {
        console.error('Failed to load map features:', err);
      }
    }
  },

  fetchObservations: async (zoom = 5) => {
    try {
      const data = typeof eventsAPI?.observationsMap === 'function' ? await eventsAPI.observationsMap(zoom) : null;
      let obsList: WeatherObservationFeature[] = [];
      if (data && Array.isArray(data.features)) {
        obsList = data.features.map((f: any) => ({
          id: f.id || f.properties?.id,
          name: f.properties?.name || 'District',
          city: f.properties?.city,
          state: f.properties?.state || 'India',
          latitude: f.geometry?.coordinates?.[1] ?? f.properties?.latitude,
          longitude: f.geometry?.coordinates?.[0] ?? f.properties?.longitude,
          temperature_c: f.properties?.temperature_c,
          temp_label: f.properties?.temp_label || (f.properties?.temperature_c ? `${Math.round(f.properties.temperature_c)}°C` : '--'),
          weather_icon: f.properties?.weather_icon || '⛅',
          condition: f.properties?.condition || 'Fair',
          humidity_percent: f.properties?.humidity_percent,
          rain_mm: f.properties?.rain_mm,
          wind_speed_kmh: f.properties?.wind_speed_kmh,
          source: f.properties?.source || 'Open-Meteo',
          model: f.properties?.model,
          observed_at: f.properties?.observed_at || new Date().toISOString(),
          warning_status: f.properties?.warning_status || 'NORMAL',
          incident_count: f.properties?.incident_count || 0,
          layer_type: 'WEATHER_OBSERVATION',
        })).filter((o: any) => o.latitude !== undefined && o.longitude !== undefined);
      }
      const mergedObsList = mergeObservationsWithDemo(obsList);
      set({ observations: mergedObsList });
    } catch (err) {
      if (isDemoModeActive()) {
        const mergedObsList = mergeObservationsWithDemo([]);
        set({ observations: mergedObsList });
      } else {
        console.error('Failed to load observations:', err);
      }
    }
  },

  toggleShowObservations: () => {
    set((state) => ({ showObservations: !state.showObservations }));
  },

  fetchCoverage: async () => {
    try {
      const cov = await eventsAPI.coverage();
      set({ coverage: cov });
    } catch (err) {
      console.error('Failed to load coverage data:', err);
    }
  },

  fetchEventDetail: async (eventId) => {
    set({ isLoadingDetail: true });
    try {
      if (eventId && eventId.startsWith('demo-ev-')) {
        const demoEvents = generateSyntheticEvents();
        const found = demoEvents.find((e) => e.id === eventId);
        if (found) {
          if (get().selectedEventId === eventId) {
            set({ selectedEvent: found, isLoadingDetail: false });
          }
          return;
        }
      }
      const event = await eventsAPI.get(eventId);
      const normalized = normalizeEvent(event);
      if (get().selectedEventId === eventId) {
        set({ selectedEvent: normalized, isLoadingDetail: false });
      }
    } catch (err) {
      if (get().selectedEventId === eventId) {
        set({
          isLoadingDetail: false,
          error: err instanceof Error ? err.message : 'Failed to load event detail',
        });
      }
    }
  },

  selectEvent: (eventId) => {
    set({ selectedEventId: eventId });
    if (eventId) {
      const existing = get().events.find((e) => e.id === eventId) || get().mapEvents.find((e) => e.id === eventId);
      if (existing) set({ selectedEvent: existing });
      get().fetchEventDetail(eventId);
    } else {
      set({ selectedEvent: null });
    }
  },

  setSelectedEvent: (event) => {
    set({ selectedEvent: event, selectedEventId: event ? event.id : null });
    if (event?.id) {
      get().fetchEventDetail(event.id);
    }
  },

  addOrUpdateEvent: (event) => {
    set((state) => {
      const idx = state.events.findIndex((e) => e.id === event.id);
      let events = [...state.events];
      if (idx >= 0) {
        events[idx] = { ...events[idx], ...event };
      } else {
        events = [event, ...events];
      }

      const now = new Date();
      const isExpired = event.lifecycle_status === 'EXPIRED' ||
        event.is_active === false ||
        (event.expires_at ? now >= new Date(event.expires_at) : false);

      let mapEvents = [...state.mapEvents];
      const mIdx = mapEvents.findIndex((e) => e.id === event.id);

      if (isExpired) {
        if (mIdx >= 0) {
          mapEvents.splice(mIdx, 1);
        }
      } else if (event.latitude !== undefined && event.longitude !== undefined && !isNaN(event.latitude) && !isNaN(event.longitude)) {
        if (mIdx >= 0) {
          mapEvents[mIdx] = { ...mapEvents[mIdx], ...event };
        } else {
          mapEvents = [event, ...mapEvents];
        }
      }

      return {
        events,
        mapEvents,
        total: idx >= 0 ? state.total : state.total + 1,
      };
    });
  },

  removeEvent: (eventId: string) => {
    set((state) => ({
      events: state.events.filter((e) => e.id !== eventId),
      mapEvents: state.mapEvents.filter((e) => e.id !== eventId),
      total: Math.max(0, state.total - (state.events.some((e) => e.id === eventId) ? 1 : 0)),
      selectedEvent: state.selectedEvent?.id === eventId ? null : state.selectedEvent,
      selectedEventId: state.selectedEventId === eventId ? null : state.selectedEventId,
    }));
  },

  updateObservation: (obs: any) => {
    set((state) => {
      const obsId = obs.id || obs.district_id;
      const idx = state.observations.findIndex((o) =>
        (obsId && o.id === obsId) ||
        (o.state === obs.state && (o.name === obs.district || o.name === obs.name))
      );
      let observations = [...state.observations];
      if (idx >= 0) {
        observations[idx] = { ...observations[idx], ...obs };
      } else if (obs.latitude !== undefined && obs.longitude !== undefined) {
        observations = [obs, ...observations];
      }
      return { observations };
    });
  },

  updateObservationBatch: (obsList: any[]) => {
    set((state) => {
      let observations = [...state.observations];
      for (const obs of obsList) {
        const obsId = obs.id || obs.district_id;
        const idx = observations.findIndex((o) =>
          (obsId && o.id === obsId) ||
          (o.state === obs.state && (o.name === obs.district || o.name === obs.name))
        );
        if (idx >= 0) {
          observations[idx] = { ...observations[idx], ...obs };
        } else if (obs.latitude !== undefined && obs.longitude !== undefined) {
          observations.push(obs);
        }
      }
      return { observations };
    });
  },

  expireOldEvents: () => {
    const now = new Date();
    set((state) => {
      const freshMapEvents = state.mapEvents.filter((e) => {
        if (e.is_active === false) return false;
        if (e.lifecycle_status === 'EXPIRED') return false;
        if (e.expires_at) {
          const exp = new Date(e.expires_at);
          if (!isNaN(exp.getTime()) && now >= exp) {
            return false;
          }
        }
        return true;
      });
      if (freshMapEvents.length !== state.mapEvents.length) {
        return { mapEvents: freshMapEvents };
      }
      return state;
    });
  },

  applyDeltaSync: (delta) => {
    const { created = [], updated = [], expired = [], deactivated = [], server_time, revision } = delta;
    set((state) => {
      let events = [...state.events];
      let mapEvents = [...state.mapEvents];
      const expiredSet = new Set([...expired, ...deactivated]);

      if (expiredSet.size > 0) {
        events = events.filter((e) => !expiredSet.has(e.id));
        mapEvents = mapEvents.filter((e) => !expiredSet.has(e.id));
      }

      for (const item of updated) {
        const norm = normalizeEvent(item);
        if (norm) {
          const eIdx = events.findIndex((e) => e.id === norm.id);
          if (eIdx >= 0) events[eIdx] = { ...events[eIdx], ...norm };
          else events = [norm, ...events];

          const mIdx = mapEvents.findIndex((e) => e.id === norm.id);
          if (norm.lifecycle_status === 'EXPIRED' || norm.is_active === false) {
            if (mIdx >= 0) mapEvents.splice(mIdx, 1);
          } else if (norm.latitude !== undefined && norm.longitude !== undefined) {
            if (mIdx >= 0) mapEvents[mIdx] = { ...mapEvents[mIdx], ...norm };
            else mapEvents = [norm, ...mapEvents];
          }
        }
      }

      for (const item of created) {
        const norm = normalizeEvent(item);
        if (norm && !expiredSet.has(norm.id)) {
          if (!events.some((e) => e.id === norm.id)) {
            events = [norm, ...events];
          }
          if (norm.latitude !== undefined && norm.longitude !== undefined && !mapEvents.some((e) => e.id === norm.id)) {
            mapEvents = [norm, ...mapEvents];
          }
        }
      }

      return {
        events,
        mapEvents,
        serverTime: server_time || state.serverTime,
        lastSyncRevision: revision || state.lastSyncRevision,
        lastSyncAt: new Date().toISOString(),
      };
    });
  },

  updateEventVerification: (eventId, status, confidence) => {
    set((state) => ({
      events: state.events.map((e) =>
        e.id === eventId
          ? { ...e, verification_status: status as WeatherEvent['verification_status'], confidence_score: confidence }
          : e,
      ),
      selectedEvent:
        state.selectedEvent?.id === eventId
          ? {
              ...state.selectedEvent,
              verification_status: status as WeatherEvent['verification_status'],
              confidence_score: confidence,
            }
          : state.selectedEvent,
    }));
  },

  markEventAnomalous: (eventId, zScore) => {
    set((state) => ({
      events: state.events.map((e) =>
        e.id === eventId ? { ...e, is_anomalous: true, anomaly_z_score: zScore } : e,
      ),
    }));
  },

  clearError: () => set({ error: null }),
}));
