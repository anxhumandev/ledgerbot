import { create } from "zustand";
import { qs } from "../lib/format";

/** Scene order. `key` is stable (hotkey lists, research notes); `id` is the on-screen number.
 *  `optional` scenes are skipped by next/previous in the short cut (?short=1) and marked in the scene menu. */
const ORDER = [
  { key: "cold", title: "Cold Open" },
  { key: "mess", title: "The Mess" },
  { key: "onboard", title: "Live Onboarding" },
  { key: "inspect", title: "The Inspector" },
  { key: "review", title: "Human Review" },
  { key: "dial", title: "Error Budget" },
  { key: "health", title: "Supplier Health" },
  { key: "shelf", title: "Portal & API" },
  { key: "rank", title: "Ranking for Agents", optional: true },
  { key: "arena", title: "The Arena" },
  { key: "impact", title: "Impact & Architecture" },
] as const;

export type SceneKey = (typeof ORDER)[number]["key"];
export const SCENES: { key: SceneKey; id: string; title: string; optional: boolean }[] =
  ORDER.map((s, i) => ({ key: s.key, title: s.title, optional: "optional" in s && s.optional, id: String(i).padStart(2, "0") }));
export const SHORT_CUT = qs.get("short") === "1";
export const sceneIndex = (key: SceneKey) => SCENES.findIndex((s) => s.key === key);
/** Next scene index in direction `dir`, skipping optional scenes in the short cut. */
export const stepScene = (from: number, dir: 1 | -1) => {
  let i = from + dir;
  while (SHORT_CUT && i > 0 && i < SCENES.length - 1 && SCENES[i].optional) i += dir;
  return Math.max(0, Math.min(SCENES.length - 1, i));
};

export type WSMsg = { topic: string; type: string; payload: any; ts: number };
type Listener = (m: WSMsg) => void;

interface AppState {
  scene: number;
  presenter: boolean;
  searchOpen: boolean;
  setSearch: (open: boolean) => void;
  inspect: string | null; // tessera id the Inspector should open (set by hotel search or a graph click)
  openInspector: (tid: string) => void;
  research: boolean;
  toggleResearch: () => void;
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
  searchOpen: false,
  setSearch: (open) => set({ searchOpen: open }),
  inspect: null,
  openInspector: (tid) => { set({ inspect: tid, searchOpen: false }); get().setScene(sceneIndex("inspect")); },
  research: false,
  toggleResearch: () => set({ research: !get().research }),
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
  next: () => get().setScene(stepScene(get().scene, 1)),
  prev: () => get().setScene(stepScene(get().scene, -1)),
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
