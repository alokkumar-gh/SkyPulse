/**
 * notificationsStore — Zustand store for in-app notifications
 * ============================================================
 * Managed by:
 *   - REST API (initial load, history, unread count)
 *   - WebSocket (real-time delivery via useWebSocket hook)
 */

import { create } from "zustand";

export interface AppNotification {
  id: string;
  title: string;
  body: string;
  type: string;
  priority: string;
  createdAt: string;
  isRead: boolean;
}

interface NotificationsState {
  notifications: AppNotification[];
  unreadCount: number;

  // Actions
  addNotification: (n: AppNotification) => void;
  setNotifications: (notifications: AppNotification[]) => void;
  markRead: (id: string) => void;
  markAllRead: () => void;
  setUnreadCount: (count: number) => void;
}

export const useNotificationsStore = create<NotificationsState>((set) => ({
  notifications: [],
  unreadCount: 0,

  addNotification: (n: AppNotification) =>
    set((state) => {
      // Deduplicate by ID
      if (state.notifications.some((existing) => existing.id === n.id)) {
        return state;
      }
      const updated = [n, ...state.notifications].slice(0, 200);
      const unreadCount = updated.filter((x) => !x.isRead).length;
      return { notifications: updated, unreadCount };
    }),

  setNotifications: (notifications: AppNotification[]) =>
    set({
      notifications,
      unreadCount: notifications.filter((n) => !n.isRead).length,
    }),

  markRead: (id: string) =>
    set((state) => {
      const updated = state.notifications.map((n) =>
        n.id === id ? { ...n, isRead: true } : n
      );
      return {
        notifications: updated,
        unreadCount: updated.filter((n) => !n.isRead).length,
      };
    }),

  markAllRead: () =>
    set((state) => ({
      notifications: state.notifications.map((n) => ({ ...n, isRead: true })),
      unreadCount: 0,
    })),

  setUnreadCount: (count: number) => set({ unreadCount: count }),
}));
