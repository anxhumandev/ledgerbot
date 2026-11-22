import { useEffect, useState } from "react";
import { useQuery, type UseQueryOptions } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";
import { api } from "./api";

const typing = () => {
  const el = document.activeElement as HTMLElement | null;
  return !!el && (el.tagName === "INPUT" || el.tagName === "SELECT" || el.tagName === "TEXTAREA" || el.isContentEditable);
};

/** Enterprise data hook: GET `path` (null disables). Keyed by path so URL state drives refetches. */
export function useApi<T = any>(path: string | null, opts: Partial<UseQueryOptions<T>> = {}) {
  return useQuery<T>({
    queryKey: [path],
    enabled: Boolean(path),
    queryFn: ({ signal }) => api<T>(path!, { signal }),
    placeholderData: (prev) => prev,
    ...opts,
  });
}

export function useDebounced<T>(value: T, ms = 250): T {
  const [v, setV] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setV(value), ms);
    return () => clearTimeout(t);
  }, [value, ms]);
  return v;
}

/** URL-backed state for filters, sort and paging, so views are shareable and survive refresh. */
export function useUrlState<T extends Record<string, string>>(defaults: T) {
  const [params, setParams] = useSearchParams();
  const state = Object.fromEntries(Object.entries(defaults).map(([k, d]) => [k, params.get(k) ?? d])) as T;
  const set = (patch: Partial<T>, resetPage = true) => {
    const next = new URLSearchParams(params);
    for (const [k, v] of Object.entries(patch)) {
      if (v === undefined || v === "" || v === defaults[k]) next.delete(k);
      else next.set(k, String(v));
    }
    if (resetPage && !("page" in patch)) next.delete("page");
    setParams(next, { replace: true });
  };
  const reset = () => setParams(new URLSearchParams(), { replace: true });
  return [state, set, reset] as const;
}

export { typing };
