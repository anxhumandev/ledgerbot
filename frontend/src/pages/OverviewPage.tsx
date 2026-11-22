import { useQueryClient } from "@tanstack/react-query";
import { Download, RefreshCw } from "lucide-react";
import { useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useApi } from "../lib/hooks";
import { ago, date, dateTime, num, pct } from "../lib/fmt";
import { ActivityTimeline } from "../ui/activity";
import { Bar, Button, Card, ErrorState, Metric, PageHeader, Select, Skeleton, SourceTag, StatusBadge, SupplierChip } from "../ui/core";
import { DataTable } from "../ui/table";

const RANGES: Record<string, number> = { "24h": 86400, "7d": 7 * 86400, "30d": 30 * 86400, all: Infinity };
const KPI_LINK: Record<string, string> = {
  suppliers: "/suppliers/directory", listings: "/inventory/hotels", canonical: "/inventory/hotels", dedup: "/matching/clusters",
  reviews: "/matching/review", reliability: "/suppliers/directory", competitiveness: "/offers/optimization", quality: "/inventory/hotels?sort=quality&order=asc",
};

function fmtKpi(k: any) {
  if (k.value === null || k.value === undefined) return "Not available";
  if (k.unit === "pct") return pct(k.value, 1);
  if (k.unit === "score") return `${num(k.value, 0)}/100`;
  return num(k.value);
}

function exportCsv(rows: any[]) {
  const head = ["Issue ID", "Type", "Entity", "Supplier", "Severity", "Status", "Detected", "Owner"];
  const esc = (v: any) => `"${String(v ?? "").replace(/"/g, '""')}"`;
  const body = rows.map((r) => [r.id, r.type, r.entity, r.supplier, r.severity, r.status, dateTime(r.detected_at), r.owner ?? "Unassigned"].map(esc).join(","));
  const blob = new Blob([[head.join(","), ...body].join("\n")], { type: "text/csv" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = `ledgerbot-issues-${new Date().toISOString().slice(0, 10)}.csv`;
  a.click();
  URL.revokeObjectURL(a.href);
}

export default function OverviewPage() {
  const { data, error, isLoading, refetch, isFetching } = useApi<any>("/overview", { staleTime: 30_000 });
  const qc = useQueryClient();
  const nav = useNavigate();
  const [range, setRange] = useState("all");
  const cutoff = Date.now() / 1000 - RANGES[range];
  const issues = useMemo(() => (data?.issues ?? []).filter((i: any) => !i.detected_at || i.detected_at >= cutoff), [data, range]);
  const activity = useMemo(() => (data?.activity ?? []).filter((e: any) => e.ts >= cutoff), [data, range]);

  if (error) return <ErrorState error={error} onRetry={() => refetch()} />;
  const h = data?.inventory_health;
  return (
    <>
      <PageHeader title="Operations Overview"
        description="Monitor supplier inventory, catalog quality, matching operations and optimization performance."
        meta={data && <>
          <span>Catalog built {date(data.built_at)}</span><span aria-hidden>·</span>
          <span>{data.world === "large" ? "5 cities" : "Dubai"} · synthetic supplier feeds</span><span aria-hidden>·</span>
          <span>Data as of {ago(data.generated_at)}</span>
        </>}
        actions={<>
          <label className="flex items-center gap-2 text-[12px] text-fg-3">Range
            <Select value={range} onChange={(e) => setRange(e.target.value)} aria-label="Date range for issues and activity">
              <option value="24h">Last 24 hours</option><option value="7d">Last 7 days</option><option value="30d">Last 30 days</option><option value="all">All time</option>
            </Select>
          </label>
          <Button icon={<RefreshCw size={14} className={isFetching ? "animate-spin" : ""} />} onClick={() => qc.invalidateQueries()}>Refresh</Button>
          <Button icon={<Download size={14} />} onClick={() => exportCsv(issues)} disabled={!issues.length}>Export issues</Button>
        </>} />

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {isLoading ? Array.from({ length: 8 }).map((_, i) => <Skeleton key={i} className="h-[108px]" />) :
          data.kpis.map((k: any) => (
            <Metric key={k.key} label={k.label} value={<>{fmtKpi(k)}{k.of ? <span className="ml-1 text-[14px] font-semibold text-fg-3">/ {k.of}</span> : null}</>}
              hint={k.hint} source={k.source} tone={k.key === "reviews" && k.value > 0 ? "accent" : undefined} onClick={() => nav(KPI_LINK[k.key])} />
          ))}
      </div>

      <div className="mt-4 grid grid-cols-1 gap-4 2xl:grid-cols-[minmax(0,5fr)_minmax(0,7fr)]">
        <Card title="Inventory health" subtitle="Supplier listings and how they consolidate into canonical records" actions={<SourceTag source="measured" />}>
          {!h ? <Skeleton className="h-48" /> : (
            <div className="space-y-5">
              <div>
                <div className="flex items-baseline justify-between"><span className="text-[12px] text-fg-3">Raw supplier listings</span><span className="num text-[20px] font-bold text-fg">{num(h.raw_records)}</span></div>
                <div className="mt-2 flex h-2.5 overflow-hidden rounded-full bg-panel-3" aria-hidden>
                  <div className="bg-ok" style={{ width: `${(h.matched / h.raw_records) * 100}%` }} />
                  <div className="bg-edge-strong" style={{ width: `${(h.unmatched / h.raw_records) * 100}%` }} />
                </div>
                <div className="mt-2 grid grid-cols-3 gap-2 text-[12px]">
                  <div><span className="mr-1.5 inline-block h-2 w-2 rounded-full bg-ok" />Matched <b className="num block text-[14px] text-fg">{num(h.matched)}</b></div>
                  <div><span className="mr-1.5 inline-block h-2 w-2 rounded-full bg-edge-strong" />Single source <b className="num block text-[14px] text-fg">{num(h.unmatched)}</b></div>
                  <Link to="/matching/review" className="hover:text-brand-ink"><span className="mr-1.5 inline-block h-2 w-2 rounded-full bg-warn" />Manual review <b className="num block text-[14px] text-fg">{num(h.review)}</b></Link>
                </div>
              </div>
              <div className="grid grid-cols-2 gap-3">
                {([["Hotels", h.hotel, "/inventory/hotels"], ["Sightseeing", h.sightseeing, "/inventory/sightseeing"]] as const).map(([label, v, to]) => (
                  <Link key={label} to={to} className="rounded-lg border border-edge p-3 hover:border-brand/50">
                    <div className="text-[12px] font-semibold text-fg-3">{label}</div>
                    <div className="num mt-1 text-[18px] font-bold text-fg">{num(v.canonical)}</div>
                    <div className="text-[12px] text-fg-3">canonical from <span className="num">{num(v.listings)}</span> listings</div>
                  </Link>
                ))}
              </div>
              <div>
                <div className="mb-1.5 text-[12px] font-semibold text-fg-3">Hotels by city</div>
                <div className="space-y-1.5">
                  {h.by_city.map((c: any) => (
                    <div key={c.city} className="grid grid-cols-[96px_1fr_120px] items-center gap-3 text-[12px]">
                      <span className="truncate text-fg-2">{c.city}</span>
                      <Bar value={c.listings / h.by_city[0].listings} />
                      <span className="num text-right text-fg-3">{num(c.listings)} → <b className="text-fg">{num(c.canonical)}</b></span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}
        </Card>

        <Card title="Supplier health" subtitle="Feed status, freshness, data quality and fulfilment reliability" pad={false}
          actions={<Link to="/suppliers/directory" className="text-[12px] font-semibold text-brand-ink hover:underline">All suppliers</Link>}>
          <DataTable rows={data?.suppliers} loading={isLoading} rowKey={(r: any) => r.code} onRowClick={(r: any) => nav(`/suppliers/${r.code}`)} dense
            columns={[
              { key: "s", header: "Supplier", cell: (r: any) => <SupplierChip code={r.code} name={r.name} /> },
              { key: "st", header: "Feed", cell: (r: any) => <StatusBadge status={r.feed_health} label={r.feed_health === "degraded" && r.simulated_fault ? "Degraded (sim.)" : undefined} /> },
              { key: "sync", header: "Last successful sync", cell: (r: any) => r.last_sync ? <span title={`${dateTime(r.last_sync)} · ${r.last_sync_source}`}>{ago(r.last_sync)}</span> : <span className="text-fg-3">Never</span> },
              { key: "l", header: "Listings", align: "right", cell: (r: any) => <span className="num">{num(r.listings)}</span> },
              { key: "e", header: "Data issues", align: "right", cell: (r: any) => <span className={r.validation_errors ? "num text-warn" : "num"}>{num(r.validation_errors)}</span> },
              { key: "r", header: "Reliability", align: "right", cell: (r: any) => r.has_history ? <span className="num">{pct(r.reliability, 1)}</span> : <span className="text-fg-3">No history</span> },
            ]} />
        </Card>
      </div>

      <div className="mt-4 grid grid-cols-1 gap-4 2xl:grid-cols-[minmax(0,8fr)_minmax(0,4fr)]">
        <Card title="Needs attention" subtitle={`${issues.length} open item${issues.length === 1 ? "" : "s"} · highest severity first`} pad={false}>
          <DataTable rows={issues} loading={isLoading} rowKey={(r: any) => r.id} onRowClick={(r: any) => nav(r.link)} dense
            empty={<div className="p-8 text-center text-[13px] text-fg-3">Nothing needs attention in this range.</div>}
            columns={[
              { key: "id", header: "Issue", cell: (r: any) => <span className="whitespace-nowrap font-mono text-[12px] text-fg-3">{r.id}</span> },
              { key: "type", header: "Type", cell: (r: any) => <span className="whitespace-nowrap font-semibold text-fg">{r.type}</span> },
              { key: "entity", header: "Affected entity", cell: (r: any) => <span className="block max-w-[420px] truncate" title={r.entity}>{r.entity}</span> },
              { key: "sup", header: "Supplier", cell: (r: any) => r.supplier ? <SupplierChip code={r.supplier} compact /> : "—" },
              { key: "sev", header: "Severity", cell: (r: any) => <StatusBadge status={r.severity} /> },
              { key: "st", header: "Status", cell: (r: any) => <span className="whitespace-nowrap">{r.status}</span> },
              { key: "at", header: "Detected", cell: (r: any) => <span className="whitespace-nowrap" title={dateTime(r.detected_at)}>{ago(r.detected_at)}</span> },
              { key: "own", header: "Owner", cell: (r: any) => <span className="whitespace-nowrap">{r.owner ?? <span className="text-fg-3">Unassigned</span>}</span> },
              { key: "a", header: "", align: "right", cell: (r: any) => <span className="whitespace-nowrap text-[12px] font-semibold text-brand-ink">{r.action} →</span> },
            ]} />
        </Card>
        <Card title="Recent activity" subtitle="From the audit trail" actions={<Link to="/audit" className="text-[12px] font-semibold text-brand-ink hover:underline">Audit trail</Link>}>
          {isLoading ? <Skeleton className="h-48" /> : <ActivityTimeline events={activity} compact />}
        </Card>
      </div>
    </>
  );
}
