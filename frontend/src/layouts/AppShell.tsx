import { useIsFetching, useQueryClient } from "@tanstack/react-query";
import {
  Activity, BarChart3, Bell, Boxes, ChevronDown, ChevronsLeft, ChevronsRight, CircleDot, FileClock, GitMerge, LayoutDashboard,
  Menu as MenuIcon, PackageSearch, RefreshCw, Search, Settings, ShieldCheck, Truck, Upload, X,
} from "lucide-react";
import { type ReactNode, Suspense, useEffect, useMemo, useState } from "react";
import { Link, NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { useApi, useDebounced } from "../lib/hooks";
import { ago } from "../lib/fmt";
import { DEFAULT_USER, useSession } from "../lib/session";
import { Badge, cx, Skeleton, StatusBadge } from "../ui/core";
import { Menu, MenuItem, Toaster } from "../ui/overlay";

type NavItem = { to: string; label: string; icon: ReactNode; children?: { to: string; label: string }[] };
const NAV: { group: string; items: NavItem[] }[] = [
  { group: "Workspace", items: [
    { to: "/overview", label: "Overview", icon: <LayoutDashboard size={17} /> },
    { to: "/inventory", label: "Inventory Catalog", icon: <Boxes size={17} />, children: [
      { to: "/inventory/hotels", label: "Hotels" }, { to: "/inventory/sightseeing", label: "Sightseeing" }] },
    { to: "/matching", label: "Match Review", icon: <GitMerge size={17} />, children: [
      { to: "/matching/review", label: "Review queue" }, { to: "/matching/clusters", label: "Clusters" }, { to: "/matching/policies", label: "Policies" }] },
  ] },
  { group: "Operations", items: [
    { to: "/suppliers/directory", label: "Suppliers", icon: <Truck size={17} /> },
    { to: "/suppliers/ingestion", label: "Data Ingestion", icon: <Upload size={17} /> },
    { to: "/offers", label: "Offer Intelligence", icon: <PackageSearch size={17} />, children: [
      { to: "/offers/comparison", label: "Comparison" }, { to: "/offers/optimization", label: "Optimization" }] },
  ] },
  { group: "Intelligence", items: [
    { to: "/ranking", label: "Search Ranking", icon: <Activity size={17} />, children: [
      { to: "/ranking/preview", label: "Preview" }, { to: "/ranking/experiments", label: "Experiments" }] },
    { to: "/analytics", label: "Analytics", icon: <BarChart3 size={17} /> },
    { to: "/audit", label: "Quality & Audit", icon: <FileClock size={17} /> },
  ] },
  { group: "Administration", items: [{ to: "/settings", label: "Settings", icon: <Settings size={17} /> }] },
];

const CRUMB: Record<string, string> = {
  overview: "Overview", inventory: "Inventory", hotels: "Hotels", sightseeing: "Sightseeing", hotel: "Hotels", activity: "Sightseeing",
  matching: "Match Review", review: "Review queue", clusters: "Clusters", policies: "Policies", suppliers: "Suppliers",
  directory: "Directory", ingestion: "Data Ingestion", offers: "Offer Intelligence", comparison: "Comparison", optimization: "Optimization",
  ranking: "Search Ranking", preview: "Preview", experiments: "Experiments", analytics: "Analytics", audit: "Quality & Audit", settings: "Settings",
};
const CRUMB_LINK: Record<string, string> = { hotel: "/inventory/hotels", activity: "/inventory/sightseeing", inventory: "/inventory/hotels",
  matching: "/matching/review", suppliers: "/suppliers/directory", offers: "/offers/comparison", ranking: "/ranking/preview" };

function Logo({ collapsed }: { collapsed: boolean }) {
  return (
    <Link to="/overview" className="flex items-center gap-2.5 px-1" aria-label="LedgerBot home">
      <svg width="28" height="28" viewBox="0 0 32 32" aria-hidden><rect width="32" height="32" rx="8" fill="var(--brand)" />
        <g fill="#fff"><rect x="7" y="7" width="8" height="8" rx="1.5" /><rect x="17" y="7" width="8" height="8" rx="1.5" opacity=".6" />
          <rect x="7" y="17" width="8" height="8" rx="1.5" opacity=".6" /></g><rect x="17" y="17" width="8" height="8" rx="1.5" fill="var(--accent)" /></svg>
      {!collapsed && (
        <div className="leading-tight">
          <div className="text-[15px] font-bold text-fg">Ledger<span className="text-accent">Bot</span></div>
          <div className="text-[11px] font-medium text-fg-3">Inventory Intelligence</div>
        </div>
      )}
    </Link>
  );
}

function Sidebar({ mobile = false }: { mobile?: boolean }) {
  const collapsed = useSession((s) => s.sidebarCollapsed) && !mobile;
  const toggle = useSession((s) => s.toggleSidebar);
  const setMobile = useSession((s) => s.setMobileNav);
  const { pathname } = useLocation();
  const { data: me } = useApi<any>("/me");
  const ws = me?.workspace;
  return (
    <nav aria-label="Main" className={cx("flex h-full flex-col border-r border-edge bg-panel", collapsed ? "w-[68px]" : "w-[240px]")}>
      <div className="flex h-[60px] items-center justify-between border-b border-edge px-3">
        <Logo collapsed={collapsed} />
        {mobile && <button aria-label="Close navigation" onClick={() => setMobile(false)} className="rounded-full p-1.5 text-fg-3 hover:bg-panel-3"><X size={18} /></button>}
      </div>
      {!collapsed && (
        <div className="mx-3 mt-3 rounded-lg border border-edge bg-panel-2 px-3 py-2">
          <div className="text-[11px] font-semibold uppercase tracking-[0.05em] text-fg-3">Workspace</div>
          <div className="truncate text-[13px] font-semibold text-fg">{ws?.name ?? "Demo Workspace"}</div>
          <div className="text-[11px] text-sim">Synthetic data · demo identities</div>
        </div>
      )}
      <div className="flex-1 overflow-y-auto px-2 py-3 scroll-thin">
        {NAV.map((g) => (
          <div key={g.group} className="mb-3">
            {!collapsed && <div className="px-2.5 pb-1 text-[11px] font-semibold uppercase tracking-[0.06em] text-fg-3">{g.group}</div>}
            {g.items.map((it) => {
              const activeGroup = pathname.startsWith(it.to) || (it.to === "/suppliers/directory" && /^\/suppliers\/(?!ingestion)/.test(pathname));
              return (
                <div key={it.to}>
                  <NavLink to={it.children ? it.children[0].to : it.to} title={collapsed ? it.label : undefined}
                    onClick={() => mobile && setMobile(false)}
                    className={cx("relative flex h-9 items-center gap-2.5 rounded-lg px-2.5 text-[13px] font-semibold transition-colors",
                      activeGroup ? "bg-brand-soft text-brand-ink" : "text-fg-2 hover:bg-panel-2 hover:text-fg", collapsed && "justify-center")}>
                    {activeGroup && <span className="absolute left-0 top-1.5 bottom-1.5 w-[3px] rounded-r bg-brand" aria-hidden />}
                    <span className={activeGroup ? "text-brand" : "text-fg-3"}>{it.icon}</span>
                    {!collapsed && <span className="truncate">{it.label}</span>}
                  </NavLink>
                  {!collapsed && it.children && activeGroup && (
                    <div className="mb-1 ml-[30px] mt-0.5 space-y-0.5 border-l border-edge pl-2">
                      {it.children.map((c) => (
                        <NavLink key={c.to} to={c.to} onClick={() => mobile && setMobile(false)}
                          className={({ isActive }) => cx("block rounded-md px-2 py-1.5 text-[13px]", isActive ? "font-semibold text-brand-ink" : "text-fg-3 hover:text-fg")}>
                          {c.label}
                        </NavLink>
                      ))}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        ))}
      </div>
      <div className="border-t border-edge p-2">
        {!mobile && (
          <button onClick={toggle} aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
            className={cx("flex h-8 w-full items-center gap-2 rounded-lg px-2.5 text-[12px] text-fg-3 hover:bg-panel-2 hover:text-fg", collapsed && "justify-center")}>
            {collapsed ? <ChevronsRight size={16} /> : <><ChevronsLeft size={16} />Collapse</>}
          </button>
        )}
        <IdentityMenu collapsed={collapsed} />
      </div>
    </nav>
  );
}

function initials(name?: string) {
  return (name ?? "?").split(" ").map((p) => p[0]).slice(0, 2).join("");
}

function IdentityMenu({ collapsed }: { collapsed: boolean }) {
  const { data: me } = useApi<any>("/me");
  const setUser = useSession((s) => s.setUser);
  const qc = useQueryClient();
  const u = me?.user;
  return (
    <Menu align="left" width={290} trigger={({ toggle, open }) => (
      <button onClick={toggle} aria-expanded={open} aria-label="Workspace identity"
        className={cx("mt-1 flex w-full items-center gap-2.5 rounded-lg p-2 text-left hover:bg-panel-2", collapsed && "justify-center")}>
        <span className="flex h-8 w-8 flex-none items-center justify-center rounded-full bg-brand text-[12px] font-bold text-white">{initials(u?.name)}</span>
        {!collapsed && (
          <span className="min-w-0 flex-1">
            <span className="block truncate text-[13px] font-semibold text-fg">{u?.name ?? "Choose identity"}</span>
            <span className="block truncate text-[11px] text-fg-3">{u?.role_label ?? ""}</span>
          </span>
        )}
        {!collapsed && <ChevronDown size={14} className="text-fg-3" />}
      </button>
    )}>
      {(close) => (
        <div>
          <div className="px-2.5 pb-1.5 pt-1 text-[11px] text-fg-3">
            Demo identities. The API attributes and authorises actions by role, but there is no sign-in: this is not authentication.
          </div>
          {me?.users?.map((x: any) => (
            <MenuItem key={x.id} active={x.id === u?.id} onClick={() => { setUser(x.id); qc.invalidateQueries(); close(); }}
              icon={<span className="flex h-6 w-6 flex-none items-center justify-center rounded-full bg-panel-3 text-[10px] font-bold">{initials(x.name)}</span>}>
              <span className="min-w-0"><span className="block truncate font-semibold">{x.name}</span><span className="block truncate text-[11px] text-fg-3">{x.role_label}</span></span>
            </MenuItem>
          ))}
        </div>
      )}
    </Menu>
  );
}

function Breadcrumbs() {
  const { pathname } = useLocation();
  const parts = pathname.split("/").filter(Boolean);
  return (
    <ol className="flex min-w-0 items-center gap-1.5 text-[13px]" aria-label="Breadcrumb">
      {parts.map((p, i) => {
        const last = i === parts.length - 1;
        const label = CRUMB[p] ?? decodeURIComponent(p);
        const to = CRUMB_LINK[p] ?? "/" + parts.slice(0, i + 1).join("/");
        return (
          <li key={i} className="flex min-w-0 items-center gap-1.5">
            {i > 0 && <span className="text-fg-3">/</span>}
            {last ? <span className="truncate font-semibold text-fg" aria-current="page">{label}</span>
              : <Link to={to} className="truncate text-fg-3 hover:text-brand-ink">{label}</Link>}
          </li>
        );
      })}
    </ol>
  );
}

function Notifications() {
  const { data } = useApi<any>("/overview", { staleTime: 30_000 });
  const nav = useNavigate();
  const items = (data?.issues ?? []).filter((i: any) => i.severity === "high").slice(0, 8);
  return (
    <Menu width={380} trigger={({ toggle, open }) => (
      <button onClick={toggle} aria-expanded={open} aria-label={`Notifications${items.length ? `, ${items.length} high severity` : ""}`}
        className="relative inline-flex h-9 w-9 items-center justify-center rounded-full text-fg-3 hover:bg-panel-3 hover:text-fg">
        <Bell size={18} />
        {items.length > 0 && <span className="absolute right-1.5 top-1.5 h-2 w-2 rounded-full bg-accent ring-2 ring-panel" />}
      </button>
    )}>
      {(close) => (
        <div>
          <div className="flex items-center justify-between px-2.5 py-1.5"><span className="text-[13px] font-semibold text-fg">High-severity items</span>
            <Link to="/overview" onClick={close} className="text-[12px] text-brand-ink hover:underline">All issues</Link></div>
          {!items.length && <div className="px-2.5 py-4 text-[13px] text-fg-3">Nothing urgent right now.</div>}
          {items.map((i: any) => (
            <button key={i.id} onClick={() => { nav(i.link); close(); }} className="flex w-full flex-col gap-0.5 rounded-lg px-2.5 py-2 text-left hover:bg-panel-2">
              <span className="text-[12px] font-semibold text-fg">{i.type}</span>
              <span className="truncate text-[12px] text-fg-3">{i.entity}</span>
            </button>
          ))}
        </div>
      )}
    </Menu>
  );
}

function RefreshStatus() {
  const qc = useQueryClient();
  const fetching = useIsFetching();
  const [at, setAt] = useState(Date.now() / 1000);
  const [, tick] = useState(0);
  useEffect(() => { if (!fetching) setAt(Date.now() / 1000); }, [fetching]);
  useEffect(() => { const t = setInterval(() => tick((x) => x + 1), 30_000); return () => clearInterval(t); }, []);
  return (
    <button onClick={() => qc.invalidateQueries()} title="Refresh all data"
      className="hidden items-center gap-2 rounded-full px-2.5 py-1.5 text-[12px] text-fg-3 hover:bg-panel-3 hover:text-fg md:inline-flex">
      <RefreshCw size={14} className={fetching ? "animate-spin" : ""} />
      {fetching ? "Refreshing…" : `Updated ${ago(at)}`}
    </button>
  );
}

function Topbar() {
  const setPalette = useSession((s) => s.setPalette);
  const setMobile = useSession((s) => s.setMobileNav);
  const { data: health } = useApi<any>("/health", { refetchInterval: 30_000 });
  return (
    <header className="flex h-[60px] flex-none items-center gap-3 border-b border-edge bg-panel px-4 lg:px-6">
      <button aria-label="Open navigation" onClick={() => setMobile(true)} className="rounded-full p-1.5 text-fg-3 hover:bg-panel-3 lg:hidden"><MenuIcon size={20} /></button>
      <div className="min-w-0 flex-1"><Breadcrumbs /></div>
      <button onClick={() => setPalette(true)}
        className="hidden h-9 w-[280px] items-center gap-2 whitespace-nowrap rounded-full border border-edge-strong bg-panel-2 px-3 text-[13px] text-fg-3 hover:border-brand/50 md:flex">
        <Search size={15} /><span className="truncate">Search inventory and pages</span><kbd className="ml-auto whitespace-nowrap rounded border border-edge bg-panel px-1.5 text-[11px]">Ctrl K</kbd>
      </button>
      <button onClick={() => setPalette(true)} aria-label="Search" className="rounded-full p-2 text-fg-3 hover:bg-panel-3 md:hidden"><Search size={18} /></button>
      <span className="hidden items-center gap-1.5 xl:inline-flex" title="Synthetic demo data; prices and policies are fictional">
        <Badge tone="sim"><CircleDot size={11} />Demo workspace</Badge>
      </span>
      <span className="hidden lg:inline-flex" title={health?.llm?.enabled ? `LLM adjudicator ${health.llm.model}` : `LLM offline: ${health?.llm?.reason ?? ""}. Uncertain matches go to human review.`}>
        <Badge tone={health?.llm?.enabled ? "ok" : "neutral"}><ShieldCheck size={12} />{health?.llm?.enabled ? "LLM on" : "LLM off"}</Badge>
      </span>
      <RefreshStatus />
      <Notifications />
    </header>
  );
}

function CommandPalette() {
  const open = useSession((s) => s.paletteOpen);
  const setOpen = useSession((s) => s.setPalette);
  const nav = useNavigate();
  const [q, setQ] = useState("");
  const [i, setI] = useState(0);
  const dq = useDebounced(q, 200);
  const hotels = useApi<any>(open && dq.length >= 2 ? `/inventory?type=hotel&q=${encodeURIComponent(dq)}&page_size=6` : null);
  const acts = useApi<any>(open && dq.length >= 2 ? `/inventory?type=activity&q=${encodeURIComponent(dq)}&page_size=4` : null);
  const pages = NAV.flatMap((g) => g.items.flatMap((it) => it.children ? it.children.map((c) => ({ label: `${it.label} · ${c.label}`, to: c.to })) : [{ label: it.label, to: it.to }]));
  const results = useMemo(() => {
    const ql = q.toLowerCase();
    const p = pages.filter((x) => !ql || x.label.toLowerCase().includes(ql)).slice(0, ql ? 5 : 8).map((x) => ({ ...x, kind: "Page" }));
    const h = (hotels.data?.items ?? []).map((x: any) => ({ label: x.name, sub: `${x.id} · ${x.city_name}`, to: `/inventory/hotel/${x.id}`, kind: "Hotel" }));
    const a = (acts.data?.items ?? []).map((x: any) => ({ label: x.name, sub: `${x.id} · ${x.city_name}`, to: `/inventory/activity/${x.id}`, kind: "Sightseeing" }));
    return [...h, ...a, ...p];
  }, [q, hotels.data, acts.data]);
  useEffect(() => {
    const on = (e: KeyboardEvent) => { if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") { e.preventDefault(); setOpen(!useSession.getState().paletteOpen); } };
    window.addEventListener("keydown", on);
    return () => window.removeEventListener("keydown", on);
  }, []);
  useEffect(() => { if (open) { setQ(""); setI(0); } }, [open]);
  useEffect(() => setI(0), [results.length]);
  if (!open) return null;
  const go = (to: string) => { nav(to); setOpen(false); };
  return (
    <div className="fixed inset-0 z-[85] flex items-start justify-center bg-[rgba(16,24,40,0.45)] p-4 pt-[12vh]" onMouseDown={(e) => { if (e.target === e.currentTarget) setOpen(false); }}>
      <div role="dialog" aria-modal="true" aria-label="Search" className="w-full max-w-[600px] overflow-hidden rounded-xl border border-edge bg-panel shadow-pop">
        <div className="flex items-center gap-2 border-b border-edge px-4">
          <Search size={16} className="text-fg-3" />
          <input autoFocus value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search properties, experiences, supplier spellings or pages"
            aria-label="Search" className="h-12 flex-1 bg-transparent text-[14px] text-fg outline-none placeholder:text-fg-3"
            onKeyDown={(e) => {
              if (e.key === "ArrowDown") { e.preventDefault(); setI((x) => Math.min(results.length - 1, x + 1)); }
              if (e.key === "ArrowUp") { e.preventDefault(); setI((x) => Math.max(0, x - 1)); }
              if (e.key === "Enter" && results[i]) go(results[i].to);
              if (e.key === "Escape") setOpen(false);
            }} />
          <kbd className="rounded border border-edge px-1.5 text-[11px] text-fg-3">Esc</kbd>
        </div>
        <ul className="max-h-[50vh] overflow-y-auto p-1.5 scroll-thin" role="listbox">
          {(hotels.isFetching || acts.isFetching) && !results.length && <li className="p-3"><Skeleton className="h-4 w-1/2" /></li>}
          {results.map((r: any, k: number) => (
            <li key={r.to + k} role="option" aria-selected={k === i}>
              <button onMouseEnter={() => setI(k)} onClick={() => go(r.to)}
                className={cx("flex w-full items-center gap-3 rounded-lg px-3 py-2 text-left", k === i ? "bg-brand-soft" : "")}>
                <span className="w-[78px] flex-none text-[11px] font-semibold uppercase tracking-[0.04em] text-fg-3">{r.kind}</span>
                <span className="min-w-0 flex-1"><span className="block truncate text-[13px] font-semibold text-fg">{r.label}</span>
                  {r.sub && <span className="block truncate text-[12px] text-fg-3">{r.sub}</span>}</span>
              </button>
            </li>
          ))}
          {!results.length && dq.length >= 2 && !hotels.isFetching && <li className="px-3 py-6 text-center text-[13px] text-fg-3">No matches.</li>}
        </ul>
      </div>
    </div>
  );
}

export function PageFallback() {
  return <div className="space-y-4"><Skeleton className="h-7 w-64" /><Skeleton className="h-4 w-96" /><Skeleton className="h-64 w-full" /></div>;
}

function useValidIdentity() {
  const { data: me } = useApi<any>("/me");
  const userId = useSession((s) => s.userId);
  const setUser = useSession((s) => s.setUser);
  const qc = useQueryClient();
  useEffect(() => {
    if (me && !me.user && me.users?.length && userId !== DEFAULT_USER) {
      setUser(me.users.some((u: any) => u.id === DEFAULT_USER) ? DEFAULT_USER : me.users[0].id);
      qc.invalidateQueries();
    }
  }, [me, userId]);
}

export default function AppShell() {
  useValidIdentity();
  const mobile = useSession((s) => s.mobileNav);
  const setMobile = useSession((s) => s.setMobileNav);
  const { pathname } = useLocation();
  useEffect(() => setMobile(false), [pathname]);
  return (
    <div className="flex h-screen bg-canvas text-fg-2">
      <a href="#main" className="sr-only focus:not-sr-only focus:fixed focus:left-2 focus:top-2 focus:z-[100] focus:rounded focus:bg-panel focus:px-3 focus:py-2">Skip to content</a>
      <div className="hidden flex-none lg:block"><Sidebar /></div>
      {mobile && (
        <div className="fixed inset-0 z-[75] bg-[rgba(16,24,40,0.4)] lg:hidden" onMouseDown={(e) => { if (e.target === e.currentTarget) setMobile(false); }}>
          <div className="h-full w-[260px]"><Sidebar mobile /></div>
        </div>
      )}
      <div className="flex min-w-0 flex-1 flex-col">
        <Topbar />
        <main id="main" className="min-h-0 flex-1 overflow-y-auto scroll-thin">
          <div className="mx-auto w-full max-w-[1600px] px-4 py-5 lg:px-7 lg:py-6">
            <Suspense fallback={<PageFallback />}><Outlet /></Suspense>
          </div>
        </main>
      </div>
      <CommandPalette />
      <Toaster />
    </div>
  );
}

export { StatusBadge };
