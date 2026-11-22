import { create } from "zustand";

export const DEFAULT_USER = "u-admin";

/** Client-side UI state only. Server data lives in TanStack Query. */
type Toast = { id: number; title: string; body?: string; tone: "success" | "error" | "info" };

interface SessionState {
  userId: string;
  setUser: (id: string) => void;
  sidebarCollapsed: boolean;
  toggleSidebar: () => void;
  mobileNav: boolean;
  setMobileNav: (open: boolean) => void;
  paletteOpen: boolean;
  setPalette: (open: boolean) => void;
  toasts: Toast[];
  toast: (t: Omit<Toast, "id">) => void;
  dismiss: (id: number) => void;
}

const read = (k: string, fallback: string) => {
  try {
    return localStorage.getItem(k) ?? fallback;
  } catch {
    return fallback;
  }
};
const write = (k: string, v: string) => {
  try {
    localStorage.setItem(k, v);
  } catch {
    /* storage unavailable: keep in memory */
  }
};

export const useSession = create<SessionState>((set, get) => ({
  userId: read("lb.user", DEFAULT_USER),
  setUser: (id) => {
    write("lb.user", id);
    set({ userId: id });
  },
  sidebarCollapsed: read("lb.sidebar", "0") === "1",
  toggleSidebar: () => {
    const v = !get().sidebarCollapsed;
    write("lb.sidebar", v ? "1" : "0");
    set({ sidebarCollapsed: v });
  },
  mobileNav: false,
  setMobileNav: (open) => set({ mobileNav: open }),
  paletteOpen: false,
  setPalette: (open) => set({ paletteOpen: open }),
  toasts: [],
  toast: (t) => {
    const id = Date.now() + Math.random();
    set({ toasts: [...get().toasts, { ...t, id }] });
    setTimeout(() => get().dismiss(id), t.tone === "error" ? 7000 : 4500);
  },
  dismiss: (id) => set({ toasts: get().toasts.filter((x) => x.id !== id) }),
}));

export const toast = (t: Omit<Toast, "id">) => useSession.getState().toast(t);
