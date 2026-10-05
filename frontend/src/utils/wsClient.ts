/**
 * SkyPulse WebSocket Client — Phase 6 Frontend Integration
 * ==========================================================
 * Manages WebSocket connection lifecycle:
 *   1. Connect with optional JWT token
 *   2. Authenticate (role extracted on server)
 *   3. Subscribe with filters
 *   4. Receive and parse typed events
 *   5. Reconnect with exponential backoff after disconnect
 *   6. Resubscribe automatically after reconnect
 *
 * This is a plain TypeScript class (no React dependencies).
 * React hooks and Zustand stores build on top of this.
 */

export interface SubscriptionFilters {
  categories?: string[];
  states?: string[];
  districts?: string[];
  cities?: string[];
  min_severity?: number;
  max_severity?: number;
  min_confidence?: number;
  verification_statuses?: string[];
  source_types?: string[];
  bbox?: [number, number, number, number]; // [west, south, east, north]
}

export interface WSEventEnvelope {
  version: string;
  type: string;
  event_id: string;
  timestamp: string;
  data: Record<string, unknown>;
}

export type WSEventHandler = (event: WSEventEnvelope) => void;
export type WSStatusHandler = (status: WSConnectionStatus) => void;

export const WSConnectionStatus = {
  DISCONNECTED: "DISCONNECTED",
  CONNECTING: "CONNECTING",
  CONNECTED: "CONNECTED",
  AUTHENTICATED: "AUTHENTICATED",
  RECONNECTING: "RECONNECTING",
  FAILED: "FAILED",
} as const;
export type WSConnectionStatus = (typeof WSConnectionStatus)[keyof typeof WSConnectionStatus];

export function getWSBaseUrl(): string {
  const envUrl = import.meta.env.VITE_WS_URL;
  if (envUrl) {
    if (envUrl.startsWith('http://')) return envUrl.replace(/^http:\/\//, 'ws://');
    if (envUrl.startsWith('https://')) return envUrl.replace(/^https:\/\//, 'wss://');
    return envUrl;
  }
  return 'wss://skypulse-backend-62479304097.asia-south1.run.app/ws/events';
}

const MAX_RECONNECT_ATTEMPTS = 10;
const BASE_RECONNECT_DELAY_MS = 1000;
const MAX_RECONNECT_DELAY_MS = 30_000;
const HEARTBEAT_TIMEOUT_MS = 60_000; // If no pong in 60s, reconnect


export class SkyPulseWSClient {
  private ws: WebSocket | null = null;
  private token: string | null = null;
  private filters: SubscriptionFilters = {};
  private status: WSConnectionStatus = WSConnectionStatus.DISCONNECTED;
  private reconnectAttempts = 0;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private heartbeatTimer: ReturnType<typeof setTimeout> | null = null;
  private eventHandlers: Set<WSEventHandler> = new Set();
  private statusHandlers: Set<WSStatusHandler> = new Set();
  private shouldReconnect = true;

  // -------------------------------------------------------------------------
  // Public API
  // -------------------------------------------------------------------------

  setToken(token: string | null): void {
    this.token = token;
  }

  onEvent(handler: WSEventHandler): () => void {
    this.eventHandlers.add(handler);
    return () => this.eventHandlers.delete(handler);
  }

  onStatusChange(handler: WSStatusHandler): () => void {
    this.statusHandlers.add(handler);
    return () => this.statusHandlers.delete(handler);
  }

  connect(): void {
    if (
      this.ws?.readyState === WebSocket.OPEN ||
      this.ws?.readyState === WebSocket.CONNECTING
    ) {
      return;
    }
    this.shouldReconnect = true;
    this._connect();
  }

  disconnect(): void {
    this.shouldReconnect = false;
    this._clearTimers();
    if (this.ws) {
      this.ws.close(1000, "client_disconnect");
      this.ws = null;
    }
    this._setStatus(WSConnectionStatus.DISCONNECTED);
  }

  subscribe(filters: SubscriptionFilters): void {
    this.filters = filters;
    this._send({ type: "subscribe", filters });
  }

  unsubscribe(): void {
    this.filters = {};
    this._send({ type: "unsubscribe" });
  }

  getStatus(): WSConnectionStatus {
    return this.status;
  }

  /** Dispatch inbound event envelope directly (used for testing or simulated WS messages) */
  emit(event: WSEventEnvelope): void {
    this._handleInbound(event as unknown as Record<string, unknown>);
  }

  // -------------------------------------------------------------------------
  // Internal
  // -------------------------------------------------------------------------

  private _connect(): void {
    this._setStatus(WSConnectionStatus.CONNECTING);
    const base = getWSBaseUrl().replace(/\/+$/, '');
    let endpoint: string;
    if (base.endsWith('/ws/events')) {
      endpoint = base;
    } else if (base.endsWith('/ws')) {
      endpoint = `${base}/events`;
    } else {
      endpoint = `${base}/ws/events`;
    }
    const url = this.token
      ? `${endpoint}?token=${encodeURIComponent(this.token)}`
      : endpoint;

    try {
      this.ws = new WebSocket(url);
    } catch {
      this._scheduleReconnect();
      return;
    }


    this.ws.onopen = () => {
      this.reconnectAttempts = 0;
      this._setStatus(
        this.token
          ? WSConnectionStatus.AUTHENTICATED
          : WSConnectionStatus.CONNECTED
      );
      this._resetHeartbeatTimer();

      // Resubscribe if we have existing filters
      if (Object.keys(this.filters).length > 0) {
        this._send({ type: "subscribe", filters: this.filters });
      }
    };

    this.ws.onmessage = (event) => {
      this._resetHeartbeatTimer();
      try {
        const msg = JSON.parse(event.data as string);
        this._handleInbound(msg);
      } catch {
        // Ignore malformed messages
      }
    };

    this.ws.onclose = (event) => {
      this._clearTimers();
      if (event.code === 4001) {
        // Auth failure — do not reconnect
        this._setStatus(WSConnectionStatus.FAILED);
        return;
      }
      if (this.shouldReconnect) {
        this._setStatus(WSConnectionStatus.RECONNECTING);
        this._scheduleReconnect();
      } else {
        this._setStatus(WSConnectionStatus.DISCONNECTED);
      }
    };

    this.ws.onerror = () => {
      // onerror is always followed by onclose
    };
  }

  private _handleInbound(msg: Record<string, unknown>): void {
    const type = msg.type as string;

    if (type === "ping") {
      // Server heartbeat — respond
      this._send({ type: "ping" });
      return;
    }

    if (type === "pong" || type === "ack") {
      return; // No action needed
    }

    if (type === "error") {
      console.warn("[SkyPulseWS] Server error:", msg.code, msg.message);
      return;
    }

    // All other messages are event envelopes
    if (msg.version && msg.type && msg.event_id) {
      const envelope = msg as unknown as WSEventEnvelope;
      this.eventHandlers.forEach((handler) => {
        try {
          handler(envelope);
        } catch {
          // Ignore handler errors
        }
      });
    }
  }

  private _send(msg: Record<string, unknown>): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(msg));
    }
  }

  private _scheduleReconnect(): void {
    if (!this.shouldReconnect) return;
    if (this.reconnectAttempts >= MAX_RECONNECT_ATTEMPTS) {
      this._setStatus(WSConnectionStatus.FAILED);
      return;
    }
    const delay = Math.min(
      BASE_RECONNECT_DELAY_MS * 2 ** this.reconnectAttempts,
      MAX_RECONNECT_DELAY_MS
    );
    this.reconnectAttempts++;
    this.reconnectTimer = setTimeout(() => this._connect(), delay);
  }

  private _resetHeartbeatTimer(): void {
    if (this.heartbeatTimer) clearTimeout(this.heartbeatTimer);
    this.heartbeatTimer = setTimeout(() => {
      // No message from server in timeout window — reconnect
      this.ws?.close();
    }, HEARTBEAT_TIMEOUT_MS);
  }

  private _clearTimers(): void {
    if (this.reconnectTimer) clearTimeout(this.reconnectTimer);
    if (this.heartbeatTimer) clearTimeout(this.heartbeatTimer);
    this.reconnectTimer = null;
    this.heartbeatTimer = null;
  }

  private _setStatus(status: WSConnectionStatus): void {
    this.status = status;
    this.statusHandlers.forEach((h) => {
      try {
        h(status);
      } catch {
        // ignore
      }
    });
  }
}

// Singleton instance shared across the application
export const skyPulseWSClient = new SkyPulseWSClient();
