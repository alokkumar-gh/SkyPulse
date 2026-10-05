/**
 * useWebSocket — React hook for SkyPulse real-time updates
 * =========================================================
 * Connects, authenticates, subscribes, and handles reconnection
 * automatically. Integrates with Zustand stores.
 *
 * Usage:
 *   const { status, subscribe, unsubscribe } = useWebSocket();
 *
 *   // Apply subscription filters
 *   useEffect(() => {
 *     subscribe({ states: ['Odisha'], categories: ['FLOODING'] });
 *   }, []);
 */

import { useEffect, useCallback, useRef, useState } from "react";
import {
  skyPulseWSClient,
  WSConnectionStatus,
} from "../utils/wsClient";
import type {
  SubscriptionFilters,
  WSEventEnvelope,
} from "../utils/wsClient";
import { useNotificationsStore } from "../store/notificationsStore";
import { useEventsStore } from "../store/eventsStore";
import type { WeatherEvent } from "../types";

function normalizeWSEvent(event: WSEventEnvelope): WeatherEvent | null {
  const d = (event.data || {}) as Record<string, any>;
  const eventId = event.event_id || d.event_id || d.id;
  if (!eventId) return null;

  const loc = (d.location || {}) as Record<string, any>;
  const lat = d.centroid_lat ?? d.latitude ?? loc.latitude ?? loc.lat;
  const lon = d.centroid_lon ?? d.longitude ?? loc.longitude ?? loc.lon;
  const state = d.primary_state ?? d.state ?? loc.state;
  const district = d.primary_district ?? d.district ?? loc.district;
  const city = d.primary_city ?? d.city ?? loc.city;
  const confidence = d.confidence ?? d.confidence_score ?? 0.75;
  const cat = (d.category || 'UNKNOWN') as WeatherEvent['category'];

  return {
    id: String(eventId),
    category: cat,
    sub_category: d.sub_category,
    severity: Number(d.severity || 1),
    confidence_score: Number(confidence),
    verification_status: (d.verification_status || 'UNVERIFIED') as WeatherEvent['verification_status'],
    location: {
      state,
      district,
      city,
      lat: lat != null ? Number(lat) : undefined,
      lon: lon != null ? Number(lon) : undefined,
    },
    latitude: lat != null ? Number(lat) : undefined,
    longitude: lon != null ? Number(lon) : undefined,
    state,
    district,
    title: d.title || (cat ? `${cat} Event` : 'Weather Event'),
    first_reported_at: d.first_reported_at || d.created_at || event.timestamp || new Date().toISOString(),
    last_updated_at: d.last_updated_at || d.updated_at || event.timestamp || new Date().toISOString(),
    evidence_count: Number(d.evidence_count || 1),
    is_anomalous: Boolean(d.is_anomalous),
    anomaly_z_score: d.anomaly_z_score,
    is_active: d.is_active !== undefined ? Boolean(d.is_active) : true,
    is_demo: Boolean(d.is_demo),
    observed_at: d.observed_at || d.first_reported_at,
    ingested_at: d.ingested_at,
    last_seen_at: d.last_seen_at,
    expires_at: d.expires_at,
    lifecycle_status: d.lifecycle_status || d.status,
    freshness_label: d.freshness_label,
    freshness_category: d.freshness_category,
  };
}

// We import event/auth stores lazily to avoid circular dependency issues
// Callers can pass their own handlers via options.

export interface UseWebSocketOptions {
  /** JWT token — if undefined, connects as PUBLIC */
  token?: string | null;
  /** Subscription filters to apply on connect */
  filters?: SubscriptionFilters;
  /** Additional event handler (e.g., to update eventsStore) */
  onEvent?: (event: WSEventEnvelope) => void;
  /** Status change callback */
  onStatusChange?: (status: WSConnectionStatus) => void;
  /** Whether to auto-connect (default: true) */
  autoConnect?: boolean;
}

export function useWebSocket(options: UseWebSocketOptions = {}) {
  const {
    token,
    filters,
    onEvent,
    onStatusChange,
    autoConnect = true,
  } = options;

  const [status, setStatus] = useState<WSConnectionStatus>(() => skyPulseWSClient.getStatus());
  const { addNotification } = useNotificationsStore();
  const filtersRef = useRef(filters);
  filtersRef.current = filters;

  // Set token whenever it changes
  useEffect(() => {
    skyPulseWSClient.setToken(token ?? null);
  }, [token]);

  // Register status handler to keep local status state updated
  useEffect(() => {
    const cleanup = skyPulseWSClient.onStatusChange((newStatus) => {
      setStatus(newStatus);
      onStatusChange?.(newStatus);
    });
    return cleanup;
  }, [onStatusChange]);

  // Register event handler
  useEffect(() => {
    const cleanup = skyPulseWSClient.onEvent((event: WSEventEnvelope) => {
      // Handle in-app notifications delivered over WebSocket
      if (event.type === "notification.new") {
        const d = event.data as {
          notification_id: string;
          title: string;
          body: string;
          type: string;
          priority: string;
          created_at: string;
        };
        addNotification({
          id: d.notification_id,
          title: d.title,
          body: d.body,
          type: d.type,
          priority: d.priority,
          createdAt: d.created_at,
          isRead: false,
        });
      }

      // Handle DWEG propagation alert event
      if (
        event.type === "DWEG_PROPAGATION_ALERT" ||
        event.type === "weather_event.propagation_detected"
      ) {
        const d = (event.data || {}) as Record<string, any>;
        const alertId = d.alert_id || event.event_id || `prop-${Date.now()}`;
        const dir = d.direction || "adjacent district";
        const dist = d.distance_km ? ` (${d.distance_km}km)` : "";
        addNotification({
          id: alertId,
          title: "DWEG Propagation Alert",
          body: `Weather event is propagating ${dir}${dist}. Click to inspect evidence graph.`,
          type: "DWEG_PROPAGATION_ALERT",
          priority: "HIGH",
          createdAt: new Date().toISOString(),
          isRead: false,
        });
      }

      // Handle Real-time Weather Event Updates (Section 6, 7, 8)
      if (
        event.type === "EVENT_CREATED" ||
        event.type === "weather_event.created" ||
        event.type === "event.created" ||
        event.type === "EVENT_UPDATED" ||
        event.type === "weather_event.updated" ||
        event.type === "weather_event.cluster_updated" ||
        event.type === "event.updated"
      ) {
        const normalized = normalizeWSEvent(event);
        if (normalized) {
          useEventsStore.getState().addOrUpdateEvent(normalized);
        }
      }

      // Handle Event Expiration / Deactivation in Real-time (Section 6, 8, 11)
      if (
        event.type === "EVENT_EXPIRED" ||
        event.type === "weather_event.expired" ||
        event.type === "EVENT_DEACTIVATED" ||
        event.type === "weather_event.deactivated"
      ) {
        const d = (event.data || {}) as Record<string, any>;
        const eventId = event.event_id || d.event_id || d.id;
        if (eventId) {
          useEventsStore.getState().removeEvent(String(eventId));
        }
      }

      // Handle Routine Weather Observation Updates (Section 16, 23)
      if (
        event.type === "WEATHER_OBSERVATION_UPDATED" ||
        event.type === "weather_observation.updated"
      ) {
        const d = (event.data || {}) as Record<string, any>;
        if (Array.isArray(d.sample_districts)) {
          useEventsStore.getState().updateObservationBatch(d.sample_districts);
        } else if (Array.isArray(d.observations)) {
          useEventsStore.getState().updateObservationBatch(d.observations);
        } else if (d.observation) {
          useEventsStore.getState().updateObservation(d.observation);
        } else if (d.district || d.state) {
          useEventsStore.getState().updateObservation(d);
        }
      }

      // Handle Verification Status Updates in Realtime
      if (event.type === "weather_event.verified" || event.type === "weather_event.rejected") {
        const d = (event.data || {}) as Record<string, any>;
        const eventId = event.event_id || d.event_id || d.id;
        const status = d.verification_status || (event.type === "weather_event.verified" ? "VERIFIED" : "CONTRADICTED");
        const confidence = Number(d.confidence ?? d.confidence_score ?? 0.85);
        if (eventId) {
          useEventsStore.getState().updateEventVerification(String(eventId), status, confidence);
        }
      }

      // Handle Anomaly Flags in Realtime
      if (event.type === "weather_event.anomaly") {
        const d = (event.data || {}) as Record<string, any>;
        const eventId = event.event_id || d.event_id || d.id;
        if (eventId) {
          useEventsStore.getState().markEventAnomalous(String(eventId), d.z_score || d.anomaly_z_score);
        }
      }

      // Delegate to caller
      onEvent?.(event);
    });
    return cleanup;

  }, [onEvent, addNotification]);

  // Connect / disconnect lifecycle
  useEffect(() => {
    if (!autoConnect) return;
    skyPulseWSClient.connect();
    return () => {
      // Don't disconnect on unmount — singleton stays connected
    };
  }, [autoConnect]);

  // Periodic client-side auto-expiration timer (Section 12)
  useEffect(() => {
    const timer = setInterval(() => {
      useEventsStore.getState().expireOldEvents();
    }, 15000);
    return () => clearInterval(timer);
  }, []);

  const isConnected = status === WSConnectionStatus.CONNECTED || status === WSConnectionStatus.AUTHENTICATED;
  const lastSyncRef = useRef<string | null>(null);

  // Fallback Polling when WebSocket is disconnected (Section 9 & 29)
  useEffect(() => {
    if (isConnected) {
      return; // No redundant polling when live WebSocket is connected
    }

    const pollInterval = setInterval(async () => {
      try {
        const { eventsAPI } = await import("../utils/api");
        const changes = await eventsAPI.getChanges(lastSyncRef.current ?? undefined);
        if (changes) {
          if (changes.server_time) {
            lastSyncRef.current = changes.server_time;
          }
          useEventsStore.getState().applyDeltaSync(changes);
        }
      } catch (err) {
        // Polling failed quietly, retry on next tick
      }
    }, 15000);

    return () => clearInterval(pollInterval);
  }, [isConnected]);

  // Apply filters when they change
  useEffect(() => {
    if (filters && Object.keys(filters).length > 0) {
      skyPulseWSClient.subscribe(filters);
    }
  }, [JSON.stringify(filters)]); // eslint-disable-line react-hooks/exhaustive-deps

  const subscribe = useCallback((f: SubscriptionFilters) => {
    skyPulseWSClient.subscribe(f);
  }, []);

  const unsubscribe = useCallback(() => {
    skyPulseWSClient.unsubscribe();
  }, []);

  const reconnect = useCallback(() => {
    skyPulseWSClient.disconnect();
    setTimeout(() => skyPulseWSClient.connect(), 100);
  }, []);

  return {
    status,
    connectionState: status,
    isConnected,
    subscribe,
    unsubscribe,
    reconnect,
  };
}

export { WSConnectionStatus, type WSEventEnvelope, type SubscriptionFilters };
