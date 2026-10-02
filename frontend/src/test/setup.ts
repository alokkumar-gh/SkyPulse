import '@testing-library/jest-dom';

// Mock WebSocket in test environment
if (typeof window !== 'undefined' && !(window as any)._wsMocked) {
  (window as any)._wsMocked = true;
  class MockWebSocket {
    static OPEN = 1;
    static CLOSED = 3;
    static CONNECTING = 0;
    url: string;
    readyState = 1;
    onopen: (() => void) | null = null;
    onclose: ((ev: any) => void) | null = null;
    onmessage: ((ev: any) => void) | null = null;
    onerror: ((ev: any) => void) | null = null;
    send() {}
    close() {
      this.readyState = 3;
      if (this.onclose) this.onclose({ code: 1000 });
    }
    constructor(url: string) {
      this.url = url;
      setTimeout(() => {
        this.readyState = 1;
        if (this.onopen) this.onopen();
      }, 0);
    }
  }
  (globalThis as any).WebSocket = MockWebSocket;
}
