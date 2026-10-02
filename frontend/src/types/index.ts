// SkyPulse Core Types — Phase 7
// Aligns with backend API responses

export type WeatherCategory =
  | 'RAINFALL'
  | 'THUNDERSTORM'
  | 'FLOODING'
  | 'HEATWAVE'
  | 'FOG'
  | 'DUST_STORM'
  | 'STRONG_WINDS'
  | 'SNOWFALL'
  | 'HAILSTORM'
  | 'CYCLONE'
  | 'SMOG'
  | 'UNKNOWN';

export type VerificationStatus =
  | 'VERIFIED'
  | 'LIKELY'
  | 'UNVERIFIED'
  | 'CONTRADICTED'
  | 'REQUIRES_REVIEW'
  | 'UNDER_REVIEW';

export type SourceType =
  | 'CITIZEN'
  | 'WEATHER_API'
  | 'SOCIAL_MEDIA'
  | 'GOVERNMENT_API'
  | 'RSS_FEED'
  | 'IOT_SENSOR'
  | 'DEMO_SYNTHETIC';

export type UserRole = 'PUBLIC' | 'CITIZEN' | 'ANALYST' | 'ADMIN' | 'GOVERNMENT';

export type AlertPriority = 'INFO' | 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';
export type AlertStatus = 'CREATED' | 'DELIVERED' | 'ACKNOWLEDGED' | 'EXPIRED' | 'CANCELLED';

// Time range presets
export type TimeRangePreset = '1h' | '6h' | '24h' | '7d' | 'custom';

// ── API Response Types ──────────────────────────────────────────────────

export interface EventLocation {
  state?: string;
  district?: string;
  city?: string;
  lat?: number;
  lon?: number;
  confidence?: string;
}

export interface WeatherEvent {
  id: string;
  category: WeatherCategory;
  sub_category?: string;
  severity: number; // 1-4
  confidence_score: number; // 0.0-1.0
  verification_status: VerificationStatus;
  location: EventLocation;
  first_reported_at: string;
  last_updated_at: string;
  resolved_at?: string | null;
  evidence_count: number;
  is_anomalous: boolean;
  anomaly_z_score?: number | null;
  is_active: boolean;
  is_demo: boolean;
  // Convenience compatibility fields
  title?: string;
  description?: string;
  latitude?: number;
  longitude?: number;
  state?: string;
  district?: string;
  created_at?: string;
  updated_at?: string;
  report_count?: number;
  is_synthetic?: boolean;
  // Optional full detail fields
  verification?: VerificationResult;
  evidence_reports?: EvidenceReport[];
}

export interface EvidenceReport {
  id: string;
  source_type: SourceType;
  event_time: string;
  severity: number;
  confidence_score?: number;
  location?: EventLocation;
  summary?: string;
  normalized_text?: string;
}

export interface VerificationResult {
  status: VerificationStatus;
  confidence_score: number;
  explanation_text?: string;
  evidence_items: VerificationEvidenceItem[];
  signal_scores?: SignalScores;
  method: string;
  is_manual_override: boolean;
  created_at: string;
}

export interface VerificationEvidenceItem {
  evidence_type: string;
  source_name: string;
  description: string;
  weight_contribution: number;
}

export interface SignalScores {
  official_api?: number;
  nearby_reports?: number;
  source_trust?: number;
  image_evidence?: number;
  temporal_consistency?: number;
  historical_baseline?: number;
  spatial_consistency?: number;
  corroboration?: number;
  media_confidence?: number;
}

export interface Source {
  id: string;
  name: string;
  source_type: SourceType;
  trust_score: number;
  is_active: boolean;
  is_demo: boolean;
  last_success_at?: string;
  health_status?: string;
  records_ingested_last_hour?: number;
  description?: string;
}

export interface NationalAnalytics {
  period: { from: string; to: string };
  total_events: number;
  active_events: number;
  total_reports: number;
  by_category: Record<string, number>;
  by_verification_status: Record<string, number>;
  by_severity: Record<string, number>;
  anomalous_events: number;
  top_states: Array<{ state: string; event_count: number }>;
}

export interface StateAnalytics {
  state: string;
  period: { from: string; to: string };
  total_events: number;
  active_events: number;
  total_reports: number;
  by_category: Record<string, number>;
  by_verification_status: Record<string, number>;
  by_severity: Record<string, number>;
  top_districts: Array<{ district: string; event_count: number }>;
}

export interface TimeseriesPoint {
  timestamp: string;
  value: number;
}

export interface TimeseriesSeries {
  metric: string;
  interval: string;
  series: TimeseriesPoint[];
}

export interface AppAlert {
  id: string;
  event_id?: string;
  alert_type: string;
  priority: AlertPriority;
  status: AlertStatus;
  title: string;
  message: string;
  location_city?: string;
  location_district?: string;
  location_state?: string;
  location_lat?: number;
  location_lon?: number;
  severity: number;
  confidence?: number;
  created_at: string;
  expires_at?: string;
  acknowledged_at?: string;
}

export interface AppNotification {
  id: string;
  type: string;
  title: string;
  body: string;
  data: Record<string, unknown>;
  is_read: boolean;
  created_at: string;
  read_at?: string;
}

export interface SystemHealth {
  status: string;
  app?: string;
  version?: string;
  environment?: string;
  demo_mode?: boolean;
  // Extended admin health
  database_status?: string;
  kafka_status?: string;
  redis_status?: string;
  opensearch_status?: string;
  neo4j_status?: string;
  ai_worker_status?: string;
  ingestion_rate_per_minute?: number;
  processing_queue_depth?: number;
  error_rate_last_hour?: number;
  components?: {
    database?: { status: string; latency_ms?: number };
    redis?: { status: string; latency_ms?: number };
    redpanda?: { status: string; latency_ms?: number };
    neo4j?: { status: string; latency_ms?: number };
    [key: string]: any;
  };
}

export interface DWEGNode {
  id: string;
  type: 'WeatherEvent' | 'EvidenceReport' | 'Location' | 'Source' | string;
  label: string;
  properties: Record<string, any>;
  x?: number;
  y?: number;
  vx?: number;
  vy?: number;
  fx?: number | null;
  fy?: number | null;
}

export interface DWEGEdge {
  source: any;
  target: any;
  type: string;
  properties: Record<string, any>;
}

export interface DWEGGraph {
  event_id: string;
  nodes: DWEGNode[];
  edges: DWEGEdge[];
  generated_at: string;
}

export interface EvidenceChainStep {
  step: number;
  type: string;
  source: string;
  at: string;
  location?: string;
  value?: string;
}

export interface EvidenceChain {
  event_id: string;
  narrative: string;
  evidence_chain: EvidenceChainStep[];
  confidence: number;
  generated_at: string;
}

export interface PropagationStep {
  step: number;
  timestamp?: string;
  location?: {
    district?: string;
    state?: string;
    city?: string;
    lat?: number;
    lon?: number;
  };
  evidence_count: number;
  severity?: number;
  propagation_direction?: string;
  time_delta_minutes?: number;
}

export interface PropagationTimeline {
  event_id: string;
  propagation_steps: PropagationStep[];
  is_still_propagating: boolean;
}

export interface GeoJSONFeature {
  type: 'Feature';
  geometry: { type: string; coordinates: any };
  properties: Record<string, any>;
}

export interface GeoJSONFeatureCollection {
  type: 'FeatureCollection';
  features: GeoJSONFeature[];
  metadata?: Record<string, any>;
}

export interface PropagationAlert {
  id: string;
  event_id: string;
  event_category: string;
  alert_type: string;
  message: string;
  new_district?: string;
  severity_trend?: string;
  created_at: string;
}

export interface PropagationAlertsResponse {
  alerts: PropagationAlert[];
}

export type DWEGGraphResponse = DWEGGraph;
export type EvidenceChainResponse = EvidenceChain;
export type PropagationTimelineResponse = PropagationTimeline;
export type ConfidenceFieldResponse = GeoJSONFeatureCollection;
export type ConfidenceFieldFeature = GeoJSONFeature;


export interface PaginatedResponse<T> {
  total: number;
  page: number;
  per_page: number;
  pages: number;
  results: T[];
}

export interface WeatherReport {
  id: string;
  primary_category: WeatherCategory;
  sub_category?: string;
  severity: number;
  confidence_score: number;
  classification_confidence: number;
  location: EventLocation;
  event_time: string;
  ingested_at: string;
  canonical_event_id?: string;
  verification_status: VerificationStatus;
  source: { id: string; name: string; type: SourceType; trust_score: number };
  media_count: number;
  is_demo: boolean;
  is_anomalous?: boolean;
}

// ── Filter State ──────────────────────────────────────────────────────────
export interface DashboardFilters {
  timeRange: TimeRangePreset;
  dateFrom?: string;
  dateTo?: string;
  categories: WeatherCategory[];
  states: string[];
  verificationStatuses: VerificationStatus[];
  severityMin: number;
  severityMax: number;
  confidenceMin: number;
  showDemoData: boolean;
  sourceTypes: SourceType[];
}

export const SEVERITY_COLORS: Record<number, string> = {
  1: '#22c55e',
  2: '#eab308',
  3: '#f97316',
  4: '#ef4444',
};

export const CATEGORY_COLORS: Record<string, string> = {
  RAINFALL: '#60a5fa',
  THUNDERSTORM: '#a78bfa',
  FLOODING: '#2563eb',
  HEATWAVE: '#f97316',
  FOG: '#94a3b8',
  DUST_STORM: '#d97706',
  STRONG_WINDS: '#34d399',
  SNOWFALL: '#e0f2fe',
  HAILSTORM: '#c084fc',
  CYCLONE: '#f43f5e',
  SMOG: '#64748b',
  UNKNOWN: '#94a3b8',
};

// ── Phase 9: Analyst & Admin Types ────────────────────────────────────────

export interface ClusterReportItem {
  id: string;
  category?: string;
  severity?: number;
  source_type?: string;
  event_time?: string;
  location_state?: string;
  location_district?: string;
  normalized_text?: string;
  description?: string;
  text?: string;
  is_duplicate?: boolean;
}

export interface DuplicateCluster {
  id: string;
  canonical_event_id?: string;
  member_count: number;
  state?: string;
  created_at?: string;
  reports: ClusterReportItem[];
}

export interface AdminUser {
  id: string;
  email: string;
  display_name: string;
  role: UserRole;
  is_active: boolean;
  created_at: string;
  last_login_at?: string | null;
}

export interface AuditLogRecord {
  id: number;
  created_at: string;
  user_id?: string | null;
  action_type: string;
  entity_type: string;
  entity_id?: string | null;
  old_value?: Record<string, unknown> | null;
  new_value?: Record<string, unknown> | null;
  ip_address?: string | null;
}

export interface FlaggedReport {
  id: string;
  category?: string;
  sub_category?: string;
  severity?: number;
  confidence_score?: number;
  status: string;
  location_state?: string;
  location_district?: string;
  source_id: string;
  source_name?: string;
  raw_content?: string;
  normalized_text?: string;
  event_time?: string;
  ingested_at: string;
  is_duplicate: boolean;
  canonical_event_id?: string;
  is_demo: boolean;
}

// ── Weather Event DNA Types ───────────────────────────────────────────────

export interface EvidenceFingerprintSource {
  source_type: string;
  total_observations: number;
  supporting_observations: number;
  contradicting_observations: number;
  unverified_observations: number;
  latest_observation_at?: string | null;
  spatial_coverage_km: number;
  confidence_weight: number;
}

export interface EvidenceFingerprint {
  total_evidence_count: number;
  supporting_evidence_count: number;
  contradicting_evidence_count: number;
  unverified_evidence_count: number;
  duplicate_count: number;
  unique_sources_count: number;
  sources: Record<string, EvidenceFingerprintSource>;
  cross_source_corroborated: boolean;
}

export interface ConfidenceFactorBreakdown {
  source_reliability_score: number;
  cross_source_support_score: number;
  spatial_consistency_score: number;
  temporal_consistency_score: number;
  meteorological_score: number;
  media_score: number;
  contradiction_penalty: number;
  final_confidence: number;
  explanation: string;
}

export interface EvidenceCoverageBreakdown {
  overall_coverage_score: number;
  temporal_coverage: number;
  spatial_coverage: number;
  source_diversity_coverage: number;
  meteorological_coverage: number;
  official_validation_coverage: number;
  corroboration_coverage: number;
  active_dimensions_count: number;
  explanation: string;
}

export interface DNAPropagationStage {
  stage_number: number;
  timestamp: string;
  center_latitude: number;
  center_longitude: number;
  direction_name: string;
  direction_deg?: number | null;
  estimated_speed_kmh: number;
  distance_from_origin_km: number;
  confidence: number;
  supporting_evidence_count: number;
  stage_description: string;
}

export interface DNAPropagationProfile {
  has_propagation: boolean;
  stage_count: number;
  stages: DNAPropagationStage[];
  overall_direction: string;
  average_speed_kmh: number;
  total_distance_km: number;
}

export interface DNATimelineEntry {
  timestamp: string;
  phase: string;
  title: string;
  description: string;
  source_type?: string | null;
  source_name?: string | null;
  confidence_at_step?: number | null;
  evidence_count_at_step?: number | null;
  location_summary?: string | null;
}

export interface RelatedEventLink {
  event_id: string;
  category: string;
  severity: number;
  verification_status: string;
  relationship_type: string;
  distance_km?: number | null;
  time_delta_minutes?: number | null;
  confidence: number;
  evidence_count: number;
}

export interface EventDNASnapshot {
  event_id: string;
  event_type: string;
  status: string;
  severity: number;
  source_count: number;
  evidence_count: number;
  conflict_count: number;
  duplicate_count: number;
  propagation_stages: number;
  confidence_score: number;
  evidence_coverage_score: number;
  first_observed_at: string;
  last_updated_at: string;
}

export interface EventDNAResponse {
  event_id: string;
  event_type: string;
  sub_category?: string | null;
  status: string;
  lifecycle_phase: string;
  severity: number;
  first_observed_at: string;
  last_observed_at: string;
  resolved_at?: string | null;
  origin_latitude?: number | null;
  origin_longitude?: number | null;
  current_latitude?: number | null;
  current_longitude?: number | null;
  primary_city?: string | null;
  primary_district?: string | null;
  primary_state?: string | null;
  spatial_radius_km: number;
  spatial_footprint_km: number;
  confidence: ConfidenceFactorBreakdown;
  evidence_coverage: EvidenceCoverageBreakdown;
  evidence: EvidenceFingerprint;
  propagation: DNAPropagationProfile;
  timeline: DNATimelineEntry[];
  related_events: RelatedEventLink[];
  dweg_node_id?: string | null;
  snapshot: EventDNASnapshot;
  created_at: string;
  updated_at: string;
}

// ── Emerging Weather Events Types ─────────────────────────────────────────

export type EmergenceState =
  | 'SIGNAL'
  | 'DEVELOPING'
  | 'EMERGING'
  | 'CONFIRMED'
  | 'DISSIPATING'
  | 'EXPIRED';

export interface EmergenceFactorBreakdown {
  spatial_convergence_score: number;
  temporal_acceleration_score: number;
  source_diversity_score: number;
  category_consistency_score: number;
  meteorological_support_score: number;
  anomaly_strength_score: number;
  dweg_connectivity_score: number;
  evidence_freshness_score: number;
  contradiction_penalty: number;
  final_emergence_score: number;
  explanation_bullets: string[];
}

export interface EmergingSignalItem {
  report_id: string;
  source_id?: string | null;
  source_name: string;
  source_type: string;
  source_trust_score: number;
  category: string;
  severity: number;
  latitude: number;
  longitude: number;
  location_name?: string | null;
  event_time: string;
  ingested_at: string;
  raw_text?: string | null;
  confidence_score: number;
  is_contradictory: boolean;
  weight: number;
  distance_from_centroid_km: number;
}

export interface EmergingTimelineMilestone {
  timestamp: string;
  state: EmergenceState;
  title: string;
  description: string;
  emergence_score: number;
  signal_count: number;
}

export interface EmergingEvent {
  id: string;
  dominant_category: WeatherCategory;
  sub_category?: string | null;
  severity: number;
  state: EmergenceState;
  emergence_score: number;
  confidence_score: number;
  evidence_count: number;
  source_count: number;
  unique_source_types: string[];
  spatial_centroid_lat: number;
  spatial_centroid_lon: number;
  spatial_radius_km: number;
  spatial_footprint_km2: number;
  temporal_window_minutes: number;
  acceleration_indicator: number;
  location_summary?: string | null;
  state_name?: string | null;
  district?: string | null;
  first_signal_at: string;
  latest_signal_at: string;
  factors: EmergenceFactorBreakdown;
  signals: EmergingSignalItem[];
  timeline: EmergingTimelineMilestone[];
  canonical_event_id?: string | null;
  event_dna_id?: string | null;
  dweg_node_id?: string | null;
  detected_at: string;
  updated_at: string;
}

export interface EmergingEventListResponse {
  total: number;
  active_count: number;
  items: EmergingEvent[];
}

export interface EmergingEventSignalsResponse {
  emerging_event_id: string;
  total_signals: number;
  dominant_category: string;
  signals: EmergingSignalItem[];
}

export interface EmergingEventTimelineResponse {
  emerging_event_id: string;
  state: EmergenceState;
  milestones: EmergingTimelineMilestone[];
}

export interface EmergingEventEvidenceResponse {
  emerging_event_id: string;
  emergence_score: number;
  confidence_score: number;
  source_diversity: Record<string, number>;
  supporting_signals_count: number;
  contradicting_signals_count: number;
  factors: EmergenceFactorBreakdown;
}

// ── Weather Source Reputation Graph Types ──────────────────────────────

export type ReputationState =
  | 'NEW'
  | 'INSUFFICIENT_EVIDENCE'
  | 'ESTABLISHED'
  | 'TRUSTED'
  | 'WATCH'
  | 'LOW_RELIABILITY';

export interface CategoryReputationDetail {
  category: string;
  observation_count: number;
  verified_count: number;
  contradicted_count: number;
  supported_count: number;
  support_rate: number | null;
  contradiction_rate: number | null;
  reliability_level: 'STRONG_EVIDENCE' | 'LIMITED_EVIDENCE' | 'INSUFFICIENT_EVIDENCE' | 'CONTRADICTED_PATTERN' | 'MODERATE_EVIDENCE';
}

export interface ReputationFactorsBreakdown {
  verification_support_rate: number | null;
  contradiction_rate: number | null;
  corroboration_rate: number | null;
  duplicate_rate: number | null;
  temporal_consistency: number | null;
  spatial_consistency: number | null;
  category_consistency: number | null;
  evidence_volume_score: number;
  recency_score: number;
}

export interface ReputationTimelineEntry {
  milestone_id: string;
  timestamp: string;
  event_type: string;
  title: string;
  description: string;
  old_state?: string | null;
  new_state?: string | null;
  trust_score: number;
  triggering_event_id?: string | null;
}

export interface SourceReputation {
  source_id: string;
  source_name: string;
  source_type: string;
  current_trust: number;
  reputation_state: ReputationState;
  observation_count: number;
  verified_count: number;
  supported_count: number;
  contradicted_count: number;
  duplicate_count: number;
  corroboration_rate: number | null;
  contradiction_rate: number | null;
  verification_support_rate: number | null;
  duplicate_rate: number | null;
  category_breakdown: Record<string, CategoryReputationDetail>;
  factors: ReputationFactorsBreakdown;
  temporal_accuracy: number | null;
  spatial_accuracy: number | null;
  explanation: string[];
  is_official: boolean;
  is_active: boolean;
  last_observed_at?: string | null;
  reputation_updated_at: string;
}

export interface SourceReputationListResponse {
  items: SourceReputation[];
  total: number;
  timestamp: string;
}

export interface SourceReputationTimelineResponse {
  source_id: string;
  source_name: string;
  current_state: ReputationState;
  timeline: ReputationTimelineEntry[];
}

export interface SourceReputationCategoriesResponse {
  source_id: string;
  source_name: string;
  categories: Record<string, CategoryReputationDetail>;
}

export interface SourceReputationEvidenceResponse {
  source_id: string;
  source_name: string;
  evidence_count: number;
  items: Array<{
    report_id: string;
    event_id?: string | null;
    category: string;
    status: string;
    corroboration_type?: string;
    is_duplicate: boolean;
    location: {
      lat?: number;
      lon?: number;
      city?: string;
      state?: string;
    };
    event_time?: string | null;
    ingested_at?: string | null;
  }>;
}

// ── Social & Web Weather Intelligence Connector Types ─────────────────────

export interface SocialWebSourceDetail {
  provider_id: string;
  name: string;
  source_type: string;
  status: string;
  config: Record<string, any>;
  metrics: {
    records_fetched: number;
    records_accepted: number;
    records_rejected: number;
    weather_relevant?: number;
    accepted_for_pipeline?: number;
    accepted_india?: number;
    rejected_non_weather?: number;
    quarantined_foreign?: number;
    quarantined_unknown_location?: number;
    duplicates?: number;
    errors?: number;
    last_successful_fetch?: string | null;
    last_error?: string | null;
    last_error_at?: string | null;
    processing_latency_ms: number;
    [key: string]: any;
  };
}

export interface SocialWebConnectorOverview {
  connector_name: string;
  connector_version: string;
  status: string;
  supported_source_types: string[];
  default_weather_hashtags: string[];
  default_weather_keywords: string[];
  active_sources_count: number;
  sources: SocialWebSourceDetail[];
  timestamp: string;
}

export interface SocialWebConnectorStatus {
  connector_name: string;
  status: string;
  is_running: boolean;
  is_demo: boolean;
  records_fetched: number;
  records_accepted: number;
  records_rejected: number;
  weather_relevant?: number;
  accepted_for_pipeline?: number;
  accepted_india?: number;
  rejected_non_weather?: number;
  quarantined_foreign?: number;
  quarantined_unknown_location?: number;
  duplicates?: number;
  reposts?: number;
  rate_limits?: number;
  errors?: number;
  last_poll_at?: string | null;
  last_successful_fetch?: string | null;
  last_error?: string | null;
  last_error_at?: string | null;
  processing_latency_ms: number;
  sources_count: number;
  configured_hashtags?: string[];
  sources_status: SocialWebSourceDetail[];
  timestamp: string;
}

export interface SocialWebTestSourceRequest {
  source_type: string;
  url?: string;
  api_key?: string;
  api_token?: string;
  http_method?: string;
  record_path?: string;
  field_mapping?: Record<string, string>;
  queries?: string[];
}

export interface SocialWebTestSourceResponse {
  status: string;
  source_type: string;
  tested_url?: string | null;
  success: boolean;
  records_found: number;
  records_fetched?: number;
  weather_relevant?: number;
  accepted_for_pipeline?: number;
  accepted_india?: number;
  rejected_non_weather?: number;
  quarantined_foreign?: number;
  quarantined_unknown_location?: number;
  duplicates?: number;
  reposts?: number;
  rate_limits?: number;
  errors?: number;
  sample_records: Array<Record<string, any>>;
  latency_ms: number;
  error_message?: string | null;
  timestamp: string;
}

export interface SocialWebSourcesListResponse {
  total: number;
  sources: SocialWebSourceDetail[];
  timestamp: string;
}


