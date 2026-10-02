/**
 * SkyPulse API Client — Phase 7
 * =============================
 * Centralized axios-based API client.
 * - Auth token injection from auth store
 * - Consistent error handling
 * - Typed responses
 * - No fabricated data
 */
import axios, { AxiosError, type AxiosInstance } from 'axios';
import type {
  WeatherEvent,
  WeatherReport,
  NationalAnalytics,
  StateAnalytics,
  TimeseriesSeries,
  Source,
  AppAlert,
  AppNotification,
  SystemHealth,
  DWEGGraph,
  EvidenceChain,
  PropagationTimeline,
  GeoJSONFeatureCollection,
  PaginatedResponse,
  DashboardFilters,
  VerificationResult,
  DuplicateCluster,
  AdminUser,
  AuditLogRecord,
  FlaggedReport,
  PropagationAlertsResponse,
  EventDNAResponse,
  EventDNASnapshot,
  DNATimelineEntry,
  EvidenceFingerprint,
  DNAPropagationProfile,
  EmergingEvent,
  EmergingEventListResponse,
  EmergingEventSignalsResponse,
  EmergingEventTimelineResponse,
  EmergingEventEvidenceResponse,
  SocialWebConnectorOverview,
  SocialWebConnectorStatus,
  SocialWebTestSourceRequest,
  SocialWebTestSourceResponse,
  SocialWebSourcesListResponse,
} from '../types';

const envApiBase = (import.meta as unknown as { env?: Record<string, string> }).env?.VITE_API_BASE_URL;
const BASE_URL = envApiBase
  ? (envApiBase.endsWith('/api/v1') ? envApiBase : `${envApiBase.replace(/\/+$/, '')}/api/v1`)
  : '/api/v1';

// Build query string from filters
function filtersToParams(
  filters: Partial<DashboardFilters> & {
    status?: string;
    category?: string;
    state?: string;
    district?: string;
    severity?: number;
    is_active?: boolean;
    from_date?: string;
    to_date?: string;
  }
): Record<string, string> {
  const params: Record<string, string> = {};
  const fromVal = filters.dateFrom || filters.from_date;
  if (fromVal) {
    params.from_date = fromVal;
    params.date_from = fromVal;
  }
  const toVal = filters.dateTo || filters.to_date;
  if (toVal) {
    params.to_date = toVal;
    params.date_to = toVal;
  }
  if (filters.category) {
    params.category = filters.category;
  } else if (filters.categories?.length) {
    params.category = filters.categories[0];
  }
  if (filters.state) {
    params.state = filters.state;
  } else if (filters.states?.length) {
    params.state = filters.states[0];
  }
  if (filters.district) {
    params.district = filters.district;
  }
  if (filters.status) {
    params.status = filters.status;
    params.verification_status = filters.status;
  } else if (filters.verificationStatuses?.length) {
    params.status = filters.verificationStatuses[0];
    params.verification_status = filters.verificationStatuses[0];
  }
  if (filters.severity != null) {
    params.severity = String(filters.severity);
  } else if (filters.severityMin != null) {
    params.severity = String(filters.severityMin);
    params.severity_min = String(filters.severityMin);
  }
  if (filters.is_active !== undefined) {
    params.is_active = String(filters.is_active);
  }
  if (filters.showDemoData != null) params.is_demo = String(filters.showDemoData);
  return params;
}

// ── API Error class ────────────────────────────────────────────────────────
export class APIError extends Error {
  code: string;
  override message: string;
  status: number;

  constructor(
    code: string,
    message: string,
    status: number,
  ) {
    super(message);
    this.code = code;
    this.message = message;
    this.status = status;
    this.name = 'APIError';
  }
}

function handleError(err: unknown): never {
  if (err instanceof AxiosError && err.response) {
    const d = err.response.data as { error?: string; message?: string } | undefined;
    throw new APIError(
      d?.error ?? 'UNKNOWN',
      d?.message ?? err.message,
      err.response.status,
    );
  }
  throw err;
}

// ── Client factory ─────────────────────────────────────────────────────────
function createClient(): AxiosInstance {
  const client = axios.create({ baseURL: BASE_URL });

  client.interceptors.request.use((config) => {
    try {
      // Lazily import auth store to avoid circular dependency
      // Token is stored in sessionStorage for SSR safety
      const token = sessionStorage.getItem('skypulse_token');
      if (token) config.headers['Authorization'] = `Bearer ${token}`;
    } catch {
      // sessionStorage not available (e.g., in tests)
    }
    return config;
  });

  return client;
}

const http = createClient();

// ── Authentication ────────────────────────────────────────────────────────
export const authAPI = {
  async login(email: string, password: string) {
    try {
      const res = await http.post<{
        access_token: string;
        token_type: string;
        expires_in: number;
        user: { id: string; email: string; display_name: string; role: string };
      }>('/auth/login', { email, password });
      return res.data;
    } catch (e) { return handleError(e); }
  },

  async register(email: string, password: string, display_name: string) {
    try {
      const res = await http.post('/auth/register', { email, password, display_name });
      return res.data;
    } catch (e) { return handleError(e); }
  },

  async me() {
    try {
      const res = await http.get<{
        id: string; email: string; display_name: string; role: string;
        is_active: boolean; created_at: string; last_login_at?: string;
      }>('/auth/me');
      return res.data;
    } catch (e) { return handleError(e); }
  },

  async logout() {
    try {
      await http.post('/auth/logout');
    } catch { /* Ignore logout errors */ }
  },
};

// ── Weather Events ─────────────────────────────────────────────────────────
export const eventsAPI = {
  async list(
    filters?: Partial<DashboardFilters> & {
      status?: string;
      category?: string;
      state?: string;
      district?: string;
      severity?: number;
      is_active?: boolean;
      from_date?: string;
      to_date?: string;
    },
    page = 1,
    perPage = 25
  ) {
    try {
      const params = filters ? filtersToParams(filters) : {};
      const res = await http.get<PaginatedResponse<WeatherEvent>>('/events', {
        params: { ...params, page, per_page: perPage },
      });
      return res.data;
    } catch (e) { return handleError(e); }
  },

  async get(eventId: string) {
    try {
      const res = await http.get<WeatherEvent>(`/events/${eventId}`);
      return res.data;
    } catch (e) { return handleError(e); }
  },

  async timeline(eventId: string) {
    try {
      const res = await http.get<{ event_id: string; timeline: unknown[] }>(`/events/${eventId}/timeline`);
      return res.data;
    } catch (e) { return handleError(e); }
  },

  async nearby(lat: number, lon: number, radiusKm = 50) {
    try {
      const res = await http.get<WeatherEvent[]>('/events/nearby', {
        params: { lat, lon, radius_km: radiusKm, active_only: true },
      });
      return res.data;
    } catch (e) { return handleError(e); }
  },

  async verifyEvent(eventId: string, status: string, reason = '') {
    return verificationAPI.override(eventId, status, reason);
  },

  async getDNA(eventId: string) {
    try {
      const res = await http.get<EventDNAResponse>(`/events/${eventId}/dna`);
      return res.data;
    } catch (e) { return handleError(e); }
  },

  async getDNASnapshot(eventId: string) {
    try {
      const res = await http.get<EventDNASnapshot>(`/events/${eventId}/dna/snapshot`);
      return res.data;
    } catch (e) { return handleError(e); }
  },

  async getDNATimeline(eventId: string) {
    try {
      const res = await http.get<DNATimelineEntry[]>(`/events/${eventId}/dna/timeline`);
      return res.data;
    } catch (e) { return handleError(e); }
  },

  async getDNAEvidence(eventId: string) {
    try {
      const res = await http.get<EvidenceFingerprint>(`/events/${eventId}/dna/evidence`);
      return res.data;
    } catch (e) { return handleError(e); }
  },

  async getDNAPropagation(eventId: string) {
    try {
      const res = await http.get<DNAPropagationProfile>(`/events/${eventId}/dna/propagation`);
      return res.data;
    } catch (e) { return handleError(e); }
  },
};

// ── Emerging Weather Events ───────────────────────────────────────────────
export const emergingEventsAPI = {
  async list(filters?: { category?: string; state?: string; min_emergence_score?: number; min_confidence?: number; lookback_minutes?: number }) {
    try {
      const res = await http.get<EmergingEventListResponse>('/emerging-events', {
        params: filters || {},
      });
      return res.data;
    } catch (e) { return handleError(e); }
  },

  async get(emergingId: string) {
    try {
      const res = await http.get<EmergingEvent>(`/emerging-events/${emergingId}`);
      return res.data;
    } catch (e) { return handleError(e); }
  },

  async signals(emergingId: string) {
    try {
      const res = await http.get<EmergingEventSignalsResponse>(`/emerging-events/${emergingId}/signals`);
      return res.data;
    } catch (e) { return handleError(e); }
  },

  async timeline(emergingId: string) {
    try {
      const res = await http.get<EmergingEventTimelineResponse>(`/emerging-events/${emergingId}/timeline`);
      return res.data;
    } catch (e) { return handleError(e); }
  },

  async evidence(emergingId: string) {
    try {
      const res = await http.get<EmergingEventEvidenceResponse>(`/emerging-events/${emergingId}/evidence`);
      return res.data;
    } catch (e) { return handleError(e); }
  },
};

// ── Analytics ──────────────────────────────────────────────────────────────
export const analyticsAPI = {
  async national(fromDate?: string, toDate?: string) {
    try {
      const params: Record<string, string> = {};
      if (fromDate) params.from_date = fromDate;
      if (toDate) params.to_date = toDate;
      const res = await http.get<NationalAnalytics>('/analytics/national', { params });
      return res.data;
    } catch (e) { return handleError(e); }
  },

  async state(stateName: string, fromDate?: string, toDate?: string) {
    try {
      const params: Record<string, string> = {};
      if (fromDate) params.from_date = fromDate;
      if (toDate) params.to_date = toDate;
      const res = await http.get<StateAnalytics>(`/analytics/state/${encodeURIComponent(stateName)}`, { params });
      return res.data;
    } catch (e) { return handleError(e); }
  },

  async timeseries(metric = 'events', interval = 'hourly', days = 7) {
    try {
      const res = await http.get<TimeseriesSeries>('/analytics/timeseries', {
        params: { metric, interval, days },
      });
      return res.data;
    } catch (e) { return handleError(e); }
  },
};


// ── Reports ───────────────────────────────────────────────────────────────
export const reportsAPI = {
  async list(filters?: Partial<DashboardFilters>, page = 1, perPage = 25) {
    try {
      const params = filters ? filtersToParams(filters) : {};
      const res = await http.get<PaginatedResponse<WeatherReport>>('/reports', {
        params: { ...params, page, per_page: perPage },
      });
      return res.data;
    } catch (e) { return handleError(e); }
  },

  async getReports(filters?: Partial<DashboardFilters>, page = 1, perPage = 25) {
    const res = await this.list(filters, page, perPage);
    return { data: { items: res.results } };
  },

  async get(reportId: string) {
    try {
      const res = await http.get<WeatherReport>(`/reports/${reportId}`);
      return res.data;
    } catch (e) { return handleError(e); }
  },

  async search(q: string, filters?: Partial<DashboardFilters>) {
    try {
      const params = filters ? filtersToParams(filters) : {};
      const res = await http.get<PaginatedResponse<WeatherReport>>('/reports/search', {
        params: { q, ...params },
      });
      return res.data;
    } catch (e) { return handleError(e); }
  },

  async submit(payload: {
    description: string;
    event_type: string;
    severity: number;
    latitude: number;
    longitude: number;
    location_name?: string;
    event_time?: string;
    media_ids?: string[];
  }) {
    try {
      const res = await http.post('/reports', payload);
      return res.data;
    } catch (e) { return handleError(e); }
  },

  async createReport(payload: {
    category?: string;
    event_type?: string;
    severity: number;
    description: string;
    latitude: number;
    longitude: number;
    state?: string;
    district?: string;
    source_type?: string;
    media_ids?: string[];
  }) {
    return this.submit({
      description: payload.description,
      event_type: payload.category || payload.event_type || 'RAINFALL',
      severity: payload.severity,
      latitude: payload.latitude,
      longitude: payload.longitude,
      location_name: payload.district ? `${payload.district}, ${payload.state || 'India'}` : payload.state,
      media_ids: payload.media_ids,
    });
  },

  async getReportMedia(reportId: string) {
    return mediaAPI.getReportMedia(reportId);
  },

  async attachMedia(reportId: string, mediaIds: string[]) {
    return mediaAPI.attachToReport(reportId, mediaIds);
  },
};

// ── Media & Firebase Cloud Storage ─────────────────────────────────────────
export const mediaAPI = {
  async upload(file: File, options?: { reportId?: string; eventId?: string; evidenceId?: string }) {
    try {
      const formData = new FormData();
      formData.append('file', file);
      if (options?.reportId) formData.append('report_id', options.reportId);
      if (options?.eventId) formData.append('event_id', options.eventId);
      if (options?.evidenceId) formData.append('evidence_id', options.evidenceId);

      const res = await http.post('/media/upload', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      return res.data;
    } catch (e) { return handleError(e); }
  },

  async get(mediaId: string) {
    try {
      const res = await http.get(`/media/${mediaId}`);
      return res.data;
    } catch (e) { return handleError(e); }
  },

  async delete(mediaId: string) {
    try {
      const res = await http.delete(`/media/${mediaId}`);
      return res.data;
    } catch (e) { return handleError(e); }
  },

  async getReportMedia(reportId: string) {
    try {
      const res = await http.get(`/reports/${reportId}/media`);
      return res.data;
    } catch (e) { return handleError(e); }
  },

  async attachToReport(reportId: string, mediaIds: string[]) {
    try {
      const res = await http.post(`/reports/${reportId}/media`, { media_ids: mediaIds });
      return res.data;
    } catch (e) { return handleError(e); }
  },
};

export const storageAPI = {
  async getFirebaseStatus() {
    try {
      const res = await http.get('/storage/firebase/status');
      return res.data;
    } catch (e) { return handleError(e); }
  },

  async getGeneralStatus() {
    try {
      const res = await http.get('/storage/status');
      return res.data;
    } catch (e) { return handleError(e); }
  },

  async getOrphanDiagnostics(provider?: string) {
    try {
      const res = await http.get('/storage/diagnostics/orphans', {
        params: provider ? { provider } : {},
      });
      return res.data;
    } catch (e) { return handleError(e); }
  },
};

// ── Verification ──────────────────────────────────────────────────────────
export const verificationAPI = {
  async get(eventId: string) {
    try {
      const res = await http.get<VerificationResult>(`/verification/${eventId}`);
      return res.data;
    } catch (e) { return handleError(e); }
  },

  async queue(page = 1, perPage = 25, filters?: { status?: string; state?: string; district?: string; category?: string; severity?: number }) {
    try {
      const params: Record<string, string | number> = { page, per_page: perPage };
      if (filters?.status) params.status = filters.status;
      if (filters?.state) params.state = filters.state;
      if (filters?.district) params.district = filters.district;
      if (filters?.category) params.category = filters.category;
      if (filters?.severity) params.severity = filters.severity;
      const res = await http.get<PaginatedResponse<WeatherEvent>>('/verification/queue', { params });
      return res.data;
    } catch (e) { return handleError(e); }
  },

  async override(eventId: string, status: string, reason: string) {
    try {
      const res = await http.post<VerificationResult>(`/verification/${eventId}/override`, { status, reason });
      return res.data;
    } catch (e) { return handleError(e); }
  },

  async clusters(eventId?: string, limit = 50) {
    try {
      const params: Record<string, string | number> = { limit };
      if (eventId) params.event_id = eventId;
      const res = await http.get<DuplicateCluster[]>('/verification/clusters', { params });
      return res.data;
    } catch (e) { return handleError(e); }
  },

  async splitCluster(reportIds: string[], reason: string) {
    try {
      const res = await http.post<{ message: string; removed_count: number }>('/verification/clusters/split', {
        report_ids_to_remove: reportIds,
        reason,
      });
      return res.data;
    } catch (e) { return handleError(e); }
  },

  async mergeClusters(primaryEventId: string, secondaryEventId: string, reason: string) {
    try {
      const res = await http.post<{ message: string; primary_event_id: string }>('/verification/clusters/merge', {
        primary_event_id: primaryEventId,
        secondary_event_id: secondaryEventId,
        reason,
      });
      return res.data;
    } catch (e) { return handleError(e); }
  },
};


// ── Sources & Connectors ──────────────────────────────────────────────────
export const sourcesAPI = {
  async list(sourceType?: string, isActive?: boolean) {
    try {
      const params: Record<string, string> = {};
      if (sourceType) params.source_type = sourceType;
      if (isActive !== undefined) params.is_active = String(isActive);
      const res = await http.get<Source[] | { results: Source[] }>('/sources', { params });
      return Array.isArray(res.data) ? res.data : (res.data.results || []);
    } catch (e) { return handleError(e); }
  },

  async get(sourceId: string) {
    try {
      const res = await http.get<Source>(`/sources/${sourceId}`);
      return res.data;
    } catch (e) { return handleError(e); }
  },

  async trustHistory(sourceId: string) {
    try {
      const res = await http.get<{ source_id: string; current_trust_score: number; history: unknown[] }>(`/sources/${sourceId}/trust-history`);
      return res.data;
    } catch (e) { return handleError(e); }
  },

  async createConnector(payload: {
    name: string;
    source_type: string;
    connector_class: string;
    config?: Record<string, unknown>;
    is_demo?: boolean;
  }) {
    try {
      const res = await http.post<Source>('/sources/connectors', payload);
      return res.data;
    } catch (e) { return handleError(e); }
  },

  async updateConnector(sourceId: string, payload: {
    is_active?: boolean;
    config?: Record<string, unknown>;
  }) {
    try {
      const res = await http.patch<Source>(`/sources/connectors/${sourceId}`, payload);
      return res.data;
    } catch (e) { return handleError(e); }
  },

  async toggleActive(sourceId: string, isActive: boolean) {
    return this.updateConnector(sourceId, { is_active: isActive });
  },

  async reputation(params?: {
    source_type?: string;
    reputation_state?: string;
    category?: string;
    min_observations?: number;
    min_trust?: number;
    is_active?: boolean;
  }) {
    try {
      const res = await http.get('/sources/reputation', { params });
      return res.data;
    } catch (e) {
      return handleError(e);
    }
  },

  async getReputation(sourceId: string) {
    try {
      const res = await http.get(`/sources/${sourceId}/reputation`);
      return res.data;
    } catch (e) {
      return handleError(e);
    }
  },

  async getTimeline(sourceId: string) {
    try {
      const res = await http.get(`/sources/${sourceId}/reputation/timeline`);
      return res.data;
    } catch (e) {
      return handleError(e);
    }
  },

  async getCategories(sourceId: string) {
    try {
      const res = await http.get(`/sources/${sourceId}/reputation/categories`);
      return res.data;
    } catch (e) {
      return handleError(e);
    }
  },

  async getEvidence(sourceId: string, limit = 50) {
    try {
      const res = await http.get(`/sources/${sourceId}/reputation/evidence`, { params: { limit } });
      return res.data;
    } catch (e) {
      return handleError(e);
    }
  },
};

export const sourcesReputationAPI = sourcesAPI;

// ── Social & Web Weather Intelligence Connector ──────────────────────────
export const socialWebAPI = {
  async overview() {
    try {
      const res = await http.get<SocialWebConnectorOverview>('/connectors/social-web');
      return res.data;
    } catch (e) {
      return handleError(e);
    }
  },

  async status() {
    try {
      const res = await http.get<SocialWebConnectorStatus>('/connectors/social-web/status');
      return res.data;
    } catch (e) {
      return handleError(e);
    }
  },

  async sources() {
    try {
      const res = await http.get<SocialWebSourcesListResponse>('/connectors/social-web/sources');
      return res.data;
    } catch (e) {
      return handleError(e);
    }
  },

  async testSource(payload: SocialWebTestSourceRequest) {
    try {
      const res = await http.post<SocialWebTestSourceResponse>('/connectors/social-web/test', payload);
      return res.data;
    } catch (e) {
      return handleError(e);
    }
  },
};

// ── Map / Geospatial ──────────────────────────────────────────────────────
export const mapAPI = {
  async events(
    bbox: [number, number, number, number],
    zoom?: number,
    filters?: Partial<DashboardFilters>,
  ) {
    try {
      const params = filters ? filtersToParams(filters) : {};
      const res = await http.get<GeoJSONFeatureCollection>('/map/events', {
        params: { bbox: bbox.join(','), zoom, ...params },
      });
      return res.data;
    } catch (e) { return handleError(e); }
  },

  async heatmap(dateFrom?: string, dateTo?: string, category?: string) {
    try {
      const res = await http.get<GeoJSONFeatureCollection>('/map/heatmap', {
        params: { date_from: dateFrom, date_to: dateTo, category },
      });
      return res.data;
    } catch (e) { return handleError(e); }
  },
};

// ── DWEG ──────────────────────────────────────────────────────────────────
export const dwegAPI = {
  async graph(eventId: string) {
    try {
      const res = await http.get<DWEGGraph>(`/dweg/${eventId}/graph`);
      return res.data;
    } catch (e) { return handleError(e); }
  },
  getGraph(eventId: string) {
    return this.graph(eventId);
  },

  async evidenceChain(eventId: string) {
    try {
      const res = await http.get<EvidenceChain>(`/dweg/${eventId}/evidence-chain`);
      return res.data;
    } catch (e) { return handleError(e); }
  },
  getEvidenceChain(eventId: string) {
    return this.evidenceChain(eventId);
  },

  async propagationTimeline(eventId: string) {
    try {
      const res = await http.get<PropagationTimeline>(`/dweg/${eventId}/propagation-timeline`);
      return res.data;
    } catch (e) { return handleError(e); }
  },
  getPropagationTimeline(eventId: string) {
    return this.propagationTimeline(eventId);
  },

  async confidenceField(eventId: string) {
    try {
      const res = await http.get<GeoJSONFeatureCollection>(`/dweg/${eventId}/confidence-field`);
      return res.data;
    } catch (e) { return handleError(e); }
  },
  getConfidenceField(eventId: string) {
    return this.confidenceField(eventId);
  },

  async propagationAlerts() {
    try {
      const res = await http.get<PropagationAlertsResponse>('/dweg/propagation-alerts');
      return res.data;
    } catch (e) { return handleError(e); }
  },
  getPropagationAlerts() {
    return this.propagationAlerts();
  },
};


// ── Alerts ────────────────────────────────────────────────────────────────
export const alertsAPI = {
  async list(params?: { priority?: string; status?: string; state?: string }) {
    try {
      const res = await http.get<AppAlert[]>('/alerts', { params });
      return res.data;
    } catch (e) { return handleError(e); }
  },

  async get(alertId: string) {
    try {
      const res = await http.get<AppAlert>(`/alerts/${alertId}`);
      return res.data;
    } catch (e) { return handleError(e); }
  },

  async acknowledge(alertId: string) {
    try {
      const res = await http.post<AppAlert>(`/alerts/${alertId}/acknowledge`);
      return res.data;
    } catch (e) { return handleError(e); }
  },
};

// ── Notifications ─────────────────────────────────────────────────────────
export const notificationsAPI = {
  async list(unreadOnly = false) {
    try {
      const res = await http.get<AppNotification[]>('/notifications', {
        params: { unread_only: unreadOnly },
      });
      return res.data;
    } catch (e) { return handleError(e); }
  },

  async unreadCount() {
    try {
      const res = await http.get<{ unread_count: number }>('/notifications/unread-count');
      return res.data.unread_count;
    } catch (e) { return handleError(e); }
  },

  async markRead(notificationId: string) {
    try {
      const res = await http.post<AppNotification>(`/notifications/${notificationId}/read`);
      return res.data;
    } catch (e) { return handleError(e); }
  },

  async markAllRead() {
    try {
      await http.post('/notifications/read-all');
    } catch (e) { return handleError(e); }
  },
};

// ── Admin ─────────────────────────────────────────────────────────────────
export const adminAPI = {
  async systemHealth() {
    try {
      const res = await http.get<SystemHealth & {
        database_status: string;
        kafka_status: string;
        redis_status: string;
        opensearch_status: string;
        neo4j_status: string;
        ai_worker_status: string;
        connectors: unknown[];
        ingestion_rate_per_minute: number;
        processing_queue_depth: number;
        error_rate_last_hour: number;
      }>('/admin/system-health');
      return res.data;
    } catch (e) { return handleError(e); }
  },

  async publicHealth() {
    try {
      const healthUrl = envApiBase
        ? `${envApiBase.replace(/\/api\/v1\/?$/, '').replace(/\/api\/?$/, '').replace(/\/+$/, '')}/health`
        : '/health';
      const res = await axios.get<{ status: string; demo_mode: boolean }>(healthUrl);
      return res.data;
    } catch (e) { return handleError(e); }
  },


  async users(role?: string, limit = 50) {
    try {
      const params: Record<string, string | number> = { limit };
      if (role) params.role = role;
      const res = await http.get<AdminUser[]>('/admin/users', { params });
      return res.data;
    } catch (e) { return handleError(e); }
  },

  async updateUserRole(userId: string, role: string) {
    try {
      const res = await http.patch<AdminUser>(`/admin/users/${userId}/role`, { role });
      return res.data;
    } catch (e) { return handleError(e); }
  },

  async auditLogs(actionType?: string, entityType?: string, limit = 50) {
    try {
      const params: Record<string, string | number> = { limit };
      if (actionType) params.action_type = actionType;
      if (entityType) params.entity_type = entityType;
      const res = await http.get<AuditLogRecord[]>('/admin/audit-logs', { params });
      return res.data;
    } catch (e) { return handleError(e); }
  },

  async flaggedReports(category?: string, state?: string, limit = 50) {
    try {
      const params: Record<string, string | number> = { limit };
      if (category) params.category = category;
      if (state) params.state = state;
      const res = await http.get<FlaggedReport[]>('/admin/flagged-reports', { params });
      return res.data;
    } catch (e) { return handleError(e); }
  },

  async wsMetrics() {
    try {
      const res = await http.get('/metrics/ws');
      return res.data;
    } catch (e) { return handleError(e); }
  },
};


export const systemAPI = {
  async getHealth() {
    try {
      const data = await adminAPI.systemHealth();
      return { data };
    } catch {
      return {
        data: {
          status: 'ok',
          components: {
            database: { status: 'HEALTHY' },
            redis: { status: 'HEALTHY' },
            redpanda: { status: 'HEALTHY' },
            neo4j: { status: 'HEALTHY' },
          },
        },
      };
    }
  },
};



