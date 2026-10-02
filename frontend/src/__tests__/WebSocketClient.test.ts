import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { SkyPulseWSClient, WSConnectionStatus } from '../utils/wsClient';
import type { WSEventEnvelope } from '../utils/wsClient';

class MockWebSocket {
  static OPEN = 1;
  static CLOSED = 3;
  static CONNECTING = 0;

  url: string;
  readyState = MockWebSocket.CONNECTING;
  onopen: (() => void) | null = null;
  onclose: ((ev: { code: number }) => void) | null = null;
  onmessage: ((ev: { data: string }) => void) | null = null;
  onerror: (() => void) | null = null;

  send = vi.fn();
  close = vi.fn((code = 1000) => {
    this.readyState = MockWebSocket.CLOSED;
    if (this.onclose) this.onclose({ code });
  });

  constructor(url: string) {
    this.url = url;
    setTimeout(() => {
      this.readyState = MockWebSocket.OPEN;
      if (this.onopen) this.onopen();
    }, 10);
  }
}

describe('SkyPulseWSClient', () => {
  let client: SkyPulseWSClient;
  const originalWebSocket = global.WebSocket;

  beforeEach(() => {
    vi.useFakeTimers();
    (global as any).WebSocket = MockWebSocket;
    client = new SkyPulseWSClient();
  });

  afterEach(() => {
    client.disconnect();
    vi.clearAllTimers();
    vi.useRealTimers();
    global.WebSocket = originalWebSocket;
  });

  it('starts in DISCONNECTED state', () => {
    expect(client.getStatus()).toBe(WSConnectionStatus.DISCONNECTED);
  });

  it('transitions to CONNECTING then CONNECTED on open without token', async () => {
    const statusChanges: string[] = [];
    client.onStatusChange((s) => statusChanges.push(s));

    client.connect();
    expect(client.getStatus()).toBe(WSConnectionStatus.CONNECTING);

    vi.advanceTimersByTime(20);
    expect(client.getStatus()).toBe(WSConnectionStatus.CONNECTED);
    expect(statusChanges).toContain(WSConnectionStatus.CONNECTED);
  });

  it('transitions to AUTHENTICATED on open when token is provided', () => {
    client.setToken('valid-analyst-jwt');
    client.connect();

    vi.advanceTimersByTime(20);
    expect(client.getStatus()).toBe(WSConnectionStatus.AUTHENTICATED);
  });

  it('sends subscription filters when subscribed', () => {
    client.connect();
    vi.advanceTimersByTime(20);

    const wsInstance = (client as any).ws as MockWebSocket;
    client.subscribe({
      categories: ['FLOODING'],
      states: ['Odisha'],
      min_severity: 3,
    });

    expect(wsInstance.send).toHaveBeenCalledWith(
      JSON.stringify({
        type: 'subscribe',
        filters: {
          categories: ['FLOODING'],
          states: ['Odisha'],
          min_severity: 3,
        },
      })
    );
  });

  it('delivers typed event envelopes to registered event handlers', () => {
    const receivedEvents: WSEventEnvelope[] = [];
    client.onEvent((ev) => receivedEvents.push(ev));

    client.connect();
    vi.advanceTimersByTime(20);

    const wsInstance = (client as any).ws as MockWebSocket;
    const testEnvelope: WSEventEnvelope = {
      version: '1.0',
      type: 'weather_event.created',
      event_id: 'ev-ws-999',
      timestamp: '2026-04-10T14:30:00Z',
      data: {
        id: 'ev-ws-999',
        category: 'CYCLONE',
        severity: 4,
        state: 'Tamil Nadu',
      },
    };

    wsInstance.onmessage?.({ data: JSON.stringify(testEnvelope) });

    expect(receivedEvents).toHaveLength(1);
    expect(receivedEvents[0].type).toBe('weather_event.created');
    expect(receivedEvents[0].event_id).toBe('ev-ws-999');
    expect(receivedEvents[0].data.category).toBe('CYCLONE');
  });

  it('transitions to FAILED on authentication error code 4001 without reconnecting', () => {
    client.connect();
    vi.advanceTimersByTime(20);

    const wsInstance = (client as any).ws as MockWebSocket;
    wsInstance.onclose?.({ code: 4001 });

    expect(client.getStatus()).toBe(WSConnectionStatus.FAILED);
  });

  it('schedules reconnection on unexpected close', () => {
    client.connect();
    vi.advanceTimersByTime(20);
    expect(client.getStatus()).toBe(WSConnectionStatus.CONNECTED);

    const wsInstance = (client as any).ws as MockWebSocket;
    wsInstance.onclose?.({ code: 1006 }); // abnormal closure

    expect(client.getStatus()).toBe(WSConnectionStatus.RECONNECTING);
  });
});
