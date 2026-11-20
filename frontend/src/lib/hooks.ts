import { useEffect, useRef } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "./api";
import { useApp } from "../app/store";

const typing = () => {
  const el = document.activeElement as HTMLElement | null;
  return !!el && (el.tagName === "INPUT" || el.tagName === "SELECT" || el.tagName === "TEXTAREA" || el.isContentEditable);
};

/** Scene-level hotkeys. Keys are KeyboardEvent.key values; "Shift+1" style combos supported. */
export function useHotkeys(map: Record<string, (e: KeyboardEvent) => void>) {
  const ref = useRef(map);
  ref.current = map;
  useEffect(() => {
    const on = (e: KeyboardEvent) => {
      if (typing() || e.metaKey || e.ctrlKey || e.altKey) return;
      const key = e.shiftKey && /^Digit\d$/.test(e.code) ? `Shift+${e.code.slice(5)}` : e.key;
      const fn = ref.current[key] ?? ref.current[key.toLowerCase()];
      if (fn) {
        e.preventDefault();
        fn(e);
      }
    };
    window.addEventListener("keydown", on);
    return () => window.removeEventListener("keydown", on);
  }, []);
}

/** Fetch JSON once per demo epoch (re-fetches after a reset). */
export function useFetch<T = any>(path: string | null, deps: unknown[] = []) {
  const epoch = useApp((s) => s.epoch);
  const query = useQuery<T>({
    queryKey: ["scene", epoch, path, ...deps],
    enabled: Boolean(path),
    queryFn: ({ signal }) => api<T>(path!, { signal }),
    throwOnError: true,
  });
  return { data: query.data ?? null, error: query.error };
}

export { typing };
