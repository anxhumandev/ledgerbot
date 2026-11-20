import { create } from "zustand";

export const SCENES = [
  { id: "00", title: "Cold Open" },
  { id: "01", title: "The Mess" },
  { id: "02", title: "Live Onboarding" },
  { id: "03", title: "The Inspector" },
  { id: "04", title: "Break It" },
  { id: "05", title: "Error Budget" },
  { id: "06", title: "Supplier Health" },
  { id: "07", title: "Ranking for Agents" },
  { id: "08", title: "The Arena" },
  { id: "09", title: "Impact & Architecture" },
] as const;

export type WSMsg = { topic: string; type: string; payload: any; ts: number };
type Listener = (m: WSMsg) => void;

interface AppState {
  scene: number;
  presenter: boolean;
  epoch: number; // bumps on demo reset -> scenes remount
  toast: { id: number; text: string; tone?: string } | null;
  cost: any;
  llm: any;
  wsConnected: boolean;
  listeners: Map<string, Set<Listener>>;
  setScene: (i: number) => void;
  next: () => void;
  prev: () => void;
  togglePresenter: () => void;
  bumpEpoch: () => void;
  showToast: (text: string, tone?: string) => void;
  subscribe: (topic: string, fn: Listener) => () => void;
  dispatch: (m: WSMsg) => void;
}

const initialScene = () => {
  const m = window.location.hash.match(/#(\d+)/);
  return m ? Math.min(SCENES.length - 1, parseInt(m[1], 10)) : 0;
};

export const useApp = create<AppState>((set, get) => ({
  scene: initialScene(),
  presenter: false,
  epoch: 0,
  toast: null,
  cost: null,
  llm: null,
  wsConnected: false,
  listeners: new Map(),
  setScene: (i) => {
    const s = Math.max(0, Math.min(SCENES.length - 1, i));
    window.location.hash = `#${String(s).padStart(2, "0")}`;
    set({ scene: s });
  },
  next: () => get().setScene(get().scene + 1),
  prev: () => get().setScene(get().scene - 1),
  togglePresenter: () => set({ presenter: !get().presenter }),
  bumpEpoch: () => set({ epoch: get().epoch + 1 }),
  showToast: (text, tone) => set({ toast: { id: Date.now(), text, tone } }),
  subscribe: (topic, fn) => {
    const m = get().listeners;
    if (!m.has(topic)) m.set(topic, new Set());
    m.get(topic)!.add(fn);
    return () => m.get(topic)?.delete(fn);
  },
  dispatch: (msg) => {
    if (msg.topic === "cost") set({ cost: msg.payload });
    get().listeners.get(msg.topic)?.forEach((fn) => fn(msg));
    get().listeners.get("*")?.forEach((fn) => fn(msg));
  },
}));
