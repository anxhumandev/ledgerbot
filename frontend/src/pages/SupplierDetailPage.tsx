import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Pause, Play, ShieldAlert, Upload } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { patch, post, qs } from "../lib/api";
import { tok } from "../lib/tokens";
import { useApi, useDebounced } from "../lib/hooks";
import { ago, dateTime, num, pct, SUPPLIER_NAME } from "../lib/fmt";
import { toast } from "../lib/session";
import { ActivityTimeline } from "../ui/activity";
import { Badge, Bar, Button, Card, CopyId, Empty, ErrorState, Field, KeyValue, Metric, Notice, PageHeader, SearchInput, Select, Skeleton, SourceTag, StatusBadge, SupplierChip, Tabs } from "../ui/core";
import { ConfirmDialog } from "../ui/overlay";
import { DataTable, Pagination } from "../ui/table";

const TABS = ["overview", "inventory", "runs", "reliability", "errors", "config", "history"] as const;
const LABEL: Record<string, string> = { overview: "Overview", inventory: "Inventory", runs: "Ingestion runs", reliability: "Reliability", errors: "Errors", config: "Configuration", history: "Activity history" };
const ISSUE: Record<string, string> = { missing_phone: "Phone missing", missing_address: "Address missing", missing_coordinates: "Coordinates missing",
  coordinates_off: "Pin > 1 km from consensus", star_mismatch: "Star rating differs", duplicate_listing: "Duplicate listing" };
const AXIS = { fontSize: 11, fill: tok("fg-3") };

export default function SupplierDetailPage() {
  const { id = "" } = useParams();
  const [params, setParams] = useSearchParams();
  const tab = (TABS as readonly string[]).includes(params.get("tab") ?? "") ? params.get("tab")! : "overview";
  const { data: d, error, isLoading, refetch } = useApi<any>(`/ops/suppliers/${id}`);
  const nav = useNavigate();
  if (error) return <ErrorState error={error} onRetry={() => refetch()} />;
  if (isLoading || !d) return <Skeleton className="h-96" />;
  return (
    <>
      <Link to="/suppliers/directory" className="mb-3 inline-flex items-center gap-1.5 text-[13px] text-fg-3 hover:text-brand-ink"><ArrowLeft size={14} />Suppliers</Link>
      <PageHeader title={<span className="flex items-center gap-3">{d.name}<StatusBadge status={d.feed_health} label={d.feed_health === "degraded" && d.simulated_fault ? "Degraded (simulated)" : undefined} /></span>}
        meta={<><span className="font-mono">{d.code}</span><span>·</span><span>{d.persona}</span><span>·</span><span>Configured status: {d.status}</span><span>·</span><span>Take rate {pct(d.take_rate, 1)}</span></>}
        actions={<Button variant="primary" icon={<Upload size={14} />} onClick={() => nav(`/suppliers/ingestion?supplier=${d.code}`)}>Import data</Button>} />
      <Tabs value={tab} onChange={(t) => setParams(t === "overview" ? {} : { tab: t }, { replace: true })} tabs={TABS.map((t) => ({ value: t, label: LABEL[t] }))} />
      <div className="mt-4">
        {tab === "overview" && <Overview d={d} />}
        {tab === "inventory" && <Inventory code={d.code} issuesOnly={false} />}
        {tab === "runs" && <Runs d={d} />}
        {tab === "reliability" && <Reliability d={d} />}
        {tab === "errors" && <Errors d={d} />}
        {tab === "config" && <Config d={d} />}
        {tab === "history" && <Card title="Activity history"><ActivityTimeline events={d.history} /></Card>}
      </div>
    </>
  );
}

function Overview({ d }: { d: any }) {
  const c = d.competitiveness ?? {};
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-3 xl:grid-cols-4">
        <Metric label="Hotel listings" value={num(d.listings)} hint={`${num(d.properties)} canonical properties · ${pct(d.coverage, 1)} of catalog`} source="measured" />
        <Metric label="Reliability" value={d.has_history ? pct(d.reliability, 1) : "—"} hint={d.reliability_ci ? `90% interval ${pct(d.reliability_ci[0], 1)}–${pct(d.reliability_ci[1], 1)}` : undefined} source="simulated" />
        <Metric label="Last successful sync" value={d.last_sync ? ago(d.last_sync) : "Never"} hint={d.last_sync_source ? `From ${d.last_sync_source}` : undefined} source="live" />
        <Metric label="Data issues" value={num(d.validation_errors)} hint="Records needing correction" source="measured" />
      </div>
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
        <Card title="Catalog distribution" subtitle="Listings by city">
          {d.cities.length ? <div className="space-y-2">{d.cities.map((c2: any) => (
            <div key={c2.city} className="grid grid-cols-[110px_1fr_60px] items-center gap-3 text-[13px]"><span>{c2.city}</span><Bar value={c2.listings / d.cities[0].listings} /><span className="num text-right">{num(c2.listings)}</span></div>
          ))}</div> : <Empty title="No listings yet" body="Import a feed to onboard this supplier." />}
        </Card>
        <Card title="Offer competitiveness" subtitle="Comparable offer groups (Dubai rates) this supplier competes in" actions={<SourceTag source="measured" />}>
          {c.groups ? (
            <KeyValue cols={3} items={[["Groups competed", num(c.groups)], ["Recommended", `${num(c.recommended)} (${pct(c.recommended / c.groups, 1)})`], ["Cheapest", `${num(c.cheapest)} (${pct(c.cheapest / c.groups, 1)})`]]} />
          ) : <p className="text-[13px] text-fg-3">No comparable rates for this supplier.</p>}
          <p className="mt-3 text-[12px] text-fg-3">Recommended share falls when reliability drops or a price exceeds the competitiveness cap, even if the supplier is cheapest.</p>
        </Card>
      </div>
    </div>
  );
}

function Inventory({ code, issuesOnly }: { code: string; issuesOnly: boolean }) {
  const [q, setQ] = useState("");
  const [page, setPage] = useState(1);
  const [only, setOnly] = useState(issuesOnly);
  const dq = useDebounced(q, 250);
  useEffect(() => setPage(1), [dq, only]);
  const { data, isFetching, error } = useApi<any>(`/ops/suppliers/${code}/listings${qs({ q: dq, issues_only: only || undefined, page, page_size: 25 })}`);
  const nav = useNavigate();
  return (
    <Card pad={false}>
      <div className="flex flex-wrap items-center gap-3 border-b border-edge p-3">
        <SearchInput value={q} onChange={setQ} className="w-[280px]" placeholder="Listing name or record ID" label="Search listings" />
        <label className="flex items-center gap-2 text-[13px] text-fg-2"><input type="checkbox" checked={only} onChange={(e) => setOnly(e.target.checked)} className="h-4 w-4 accent-[var(--brand)]" />Only listings with issues</label>
      </div>
      {error ? <ErrorState error={error} /> : (
        <DataTable rows={data?.items} loading={isFetching} rowKey={(r: any) => r.record_id} onRowClick={(r: any) => r.tessera_id && nav(`/inventory/hotel/${r.tessera_id}?tab=records`)}
          columns={[
            { key: "id", header: "Record ID", cell: (r: any) => <CopyId value={r.record_id} /> },
            { key: "n", header: "Supplier listing", cell: (r: any) => <span className="font-semibold text-fg">{r.name}</span> },
            { key: "c", header: "City", cell: (r: any) => r.city },
            { key: "t", header: "Mapped to", cell: (r: any) => r.tessera_id ? <span><span className="text-fg">{r.canonical_name}</span><span className="ml-1.5 font-mono text-[11px] text-fg-3">{r.tessera_id}</span></span> : "—" },
            { key: "s", header: "Suppliers on record", align: "right", cell: (r: any) => <span className="num">{r.n_suppliers}</span> },
            { key: "i", header: "Issues", cell: (r: any) => r.issues.length ? <span className="flex flex-wrap gap-1">{r.issues.map((i: any) => <Badge key={i.code} tone={i.severity === "high" ? "bad" : i.severity === "medium" ? "warn" : "neutral"}>{i.message}</Badge>)}</span> : <span className="text-fg-3">None</span> },
          ]} />
      )}
      {data && <Pagination page={page} pageSize={25} total={data.total} onPage={setPage} />}
    </Card>
  );
}

function Runs({ d }: { d: any }) {
  const nav = useNavigate();
  return (
    <Card pad={false} title="Ingestion runs" subtitle="Imports for this supplier, newest first">
      <DataTable rows={d.jobs} rowKey={(r: any) => r.id} onRowClick={(r: any) => nav(`/suppliers/ingestion?job=${r.id}`)}
        empty={<Empty title="No imports yet" body="The supplier's current listings come from the catalog build." action={<Button size="sm" onClick={() => nav(`/suppliers/ingestion?supplier=${d.code}`)}>Start an import</Button>} />}
        columns={[
          { key: "id", header: "Job", cell: (r: any) => <span className="font-mono text-[12px]">{r.id}</span> },
          { key: "f", header: "File", cell: (r: any) => r.filename },
          { key: "s", header: "Status", cell: (r: any) => <StatusBadge status={r.status} /> },
          { key: "c", header: "Created", cell: (r: any) => <span title={dateTime(r.created_at)}>{ago(r.created_at)}</span> },
          { key: "t", header: "Records", align: "right", cell: (r: any) => <span className="num">{r.total}</span> },
          { key: "m", header: "Merged", align: "right", cell: (r: any) => <span className="num">{r.merged}</span> },
          { key: "n", header: "New", align: "right", cell: (r: any) => <span className="num">{r.created}</span> },
          { key: "r", header: "Review", align: "right", cell: (r: any) => <span className="num">{r.review}</span> },
          { key: "x", header: "Rejected", align: "right", cell: (r: any) => <span className="num">{r.invalid + r.rejected}</span> },
        ]} />
    </Card>
  );
}

function Reliability({ d }: { d: any }) {
  const { data: h } = useApi<any>(`/ops/suppliers/${d.code}/reliability`);
  const { data: sim } = useApi<any>("/ops/simulation", { refetchInterval: (q: any) => (q.state.data?.running ? 1500 : false) });
  const { data: me } = useApi<any>("/me");
  const qc = useQueryClient();
  const [mode, setMode] = useState("price_jump");
  const [sev, setSev] = useState("0.35");
  const [ask, setAsk] = useState(false);
  const can = me?.user?.permissions?.includes("simulation.run");
  const faulted = !!sim?.faults?.[d.code];
  const start = useMutation({ mutationFn: () => post(`/ops/suppliers/${d.code}/simulate`, { mode, severity: Number(sev) }),
    onSuccess: () => { setAsk(false); toast({ tone: "info", title: "Fault simulation started", body: "Reliability now moves only through simulated booking outcomes." }); qc.invalidateQueries(); },
    onError: (e: any) => { setAsk(false); toast({ tone: "error", title: "Could not start", body: e.message }); } });
  const heal = useMutation({ mutationFn: () => post("/ops/simulation/heal"), onSuccess: () => { toast({ tone: "success", title: "Simulated faults cleared" }); qc.invalidateQueries(); } });
  const stopStream = useMutation({ mutationFn: () => post("/ops/simulation/stream/stop"), onSuccess: () => qc.invalidateQueries() });
  const live = sim?.suppliers?.find((s: any) => s.code === d.code);
  const daily = (h?.daily ?? []).map((x: any) => ({ day: `D${x.day + 1}`, confirm: x.confirm_rate * 100, change: x.price_change_rate * 100 }));
  const report = sim?.switch_report;
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
        <Card title="Booking outcomes · last 30 days" subtitle={h?.source} actions={<SourceTag source="synthetic" />}>
          <div className="h-[240px]">
            <ResponsiveContainer>
              <LineChart data={daily} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
                <CartesianGrid stroke={tok("edge")} vertical={false} />
                <XAxis dataKey="day" tick={AXIS} interval={4} stroke={tok("edge-strong")} />
                <YAxis yAxisId="c" domain={[90, 100]} tickFormatter={(v) => `${v}%`} tick={AXIS} width={40} stroke={tok("edge-strong")} />
                <YAxis yAxisId="p" orientation="right" domain={[0, 10]} tickFormatter={(v) => `${v}%`} tick={AXIS} width={36} stroke={tok("edge-strong")} />
                <Tooltip formatter={(v: any, n: any) => [`${Number(v).toFixed(1)}%`, n]} />
                <Line yAxisId="c" dataKey="confirm" name="Confirm rate" stroke={tok("brand")} strokeWidth={2} dot={false} />
                <Line yAxisId="p" dataKey="change" name="Price change rate" stroke={tok("accent")} strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </Card>
        <Card title="Current reliability posterior" subtitle="Beta posterior updated by every observed booking" actions={<SourceTag source="simulated" />}>
          {live ? (
            <>
              <KeyValue cols={2} items={[["Reliability score", <b className="num text-[18px]">{pct(live.score, 2)}</b>], ["90% credible interval", `${pct(live.ci[0], 1)} – ${pct(live.ci[1], 1)}`],
                ["Confirm rate", pct(live.confirm, 2)], ["Price change at booking", pct(live.price_jump, 2)], ["Median confirmation", `${live.p50_latency.toFixed(1)} s`], ["Live observations", num(live.n_obs)]]} />
              {live.spark?.length > 1 && <div className="mt-3 h-[70px]"><ResponsiveContainer><LineChart data={live.spark.map((v: number, i: number) => ({ i, v: v * 100 }))}>
                <YAxis hide domain={["dataMin - 1", "dataMax + 1"]} /><Line dataKey="v" stroke={tok("brand")} strokeWidth={2} dot={false} isAnimationActive={false} /></LineChart></ResponsiveContainer></div>}
            </>
          ) : <Skeleton className="h-32" />}
        </Card>
      </div>
      <Card title="What-if: supplier degradation" subtitle="Change this supplier's hidden behaviour in the booking simulator and watch reliability and offer selection respond"
        actions={<Badge tone="sim">Simulation</Badge>}>
        {d.code === "S6" ? <p className="text-[13px] text-fg-3">Simulations run on suppliers with booking history (S1–S5).</p> : (
          <div className="space-y-3">
            <div className="flex flex-wrap items-end gap-3">
              <Field label="Fault"><Select value={mode} onChange={(e) => setMode(e.target.value)} disabled={faulted}>
                <option value="price_jump">Price changes at booking</option><option value="timeouts">Slow confirmations / timeouts</option><option value="failures">Confirmation failures</option></Select></Field>
              <Field label="Severity"><Select value={sev} onChange={(e) => setSev(e.target.value)} disabled={faulted}>
                {["0.15", "0.35", "0.6"].map((s) => <option key={s} value={s}>{Math.round(Number(s) * 100)}%</option>)}</Select></Field>
              {faulted ? <Button icon={<Pause size={14} />} onClick={() => heal.mutate()} loading={heal.isPending} disabled={!can}>Clear simulated faults</Button>
                : <Button variant="accent" icon={<ShieldAlert size={14} />} onClick={() => setAsk(true)} disabled={!can}>Start simulation</Button>}
              {sim?.running && <Button variant="ghost" icon={<Pause size={14} />} onClick={() => stopStream.mutate()} disabled={!can}>Stop booking stream</Button>}
              {!can && <span className="text-[12px] text-fg-3">Your role cannot run simulations.</span>}
            </div>
            {sim?.running && <Notice tone="sim">Simulated booking stream running (~15 bookings/s across Dubai offer groups). Scores update every few seconds.</Notice>}
            {report?.switched > 0 && (
              <Notice tone="accent">LedgerBot moved <b>{num(report.switched)}</b> offer groups away from {report.from_name}; about <b>{num(report.failures_avoided_per_day)}</b> failed bookings per day avoided at the simulated demand. Simulated.</Notice>
            )}
          </div>
        )}
      </Card>
      <ConfirmDialog open={ask} onClose={() => setAsk(false)} busy={start.isPending} confirmLabel="Start simulation" tone="accent"
        title={`Simulate ${SUPPLIER_NAME[d.code]} degradation?`}
        body="This changes the supplier's hidden profile in the booking simulator only. No real supplier is affected; reliability scores move as simulated bookings fail. Clear it afterwards to restore normal behaviour."
        onConfirm={() => start.mutate()} />
    </div>
  );
}

function Errors({ d }: { d: any }) {
  const entries = Object.entries(d.issue_counts as Record<string, number>).sort((a, b) => b[1] - a[1]);
  return (
    <div className="space-y-4">
      <Card title="Data-quality findings" subtitle="Computed by comparing each listing with its golden record">
        {entries.length ? <div className="grid grid-cols-2 gap-3 lg:grid-cols-3">{entries.map(([k, n]) => (
          <div key={k} className="rounded-lg border border-edge p-3"><div className="text-[12px] text-fg-3">{ISSUE[k] ?? k}</div><div className="num text-[20px] font-bold text-fg">{num(n)}</div></div>
        ))}</div> : <Empty title="No findings" />}
      </Card>
      <Inventory code={d.code} issuesOnly />
    </div>
  );
}

function Config({ d }: { d: any }) {
  const { data: me } = useApi<any>("/me");
  const qc = useQueryClient();
  const [status, setStatus] = useState(d.config.status);
  const [notes, setNotes] = useState(d.config.notes);
  const [ask, setAsk] = useState(false);
  const can = me?.user?.permissions?.includes("supplier.configure");
  const dirty = status !== d.config.status || notes !== d.config.notes;
  const save = useMutation({ mutationFn: (reason: string) => patch(`/ops/suppliers/${d.code}/config`, { status, notes, reason }),
    onSuccess: () => { setAsk(false); toast({ tone: "success", title: "Supplier configuration saved" }); qc.invalidateQueries(); },
    onError: (e: any) => { setAsk(false); toast({ tone: "error", title: "Could not save", body: e.message }); } });
  useEffect(() => {
    const warn = (e: BeforeUnloadEvent) => { if (dirty) { e.preventDefault(); e.returnValue = ""; } };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [dirty]);
  return (
    <Card title="Configuration" subtitle={d.config.updated_at ? `Last changed ${dateTime(d.config.updated_at)} by ${d.config.updated_by}` : "Default configuration"}>
      <div className="max-w-[560px] space-y-4">
        <Field label="Feed status" hint="Paused suppliers are excluded from offer recommendations and cannot be imported.">
          <Select value={status} onChange={(e) => setStatus(e.target.value)} disabled={!can}>
            <option value="active">Active</option><option value="paused">Paused</option><option value="onboarding">Onboarding</option></Select>
        </Field>
        <Field label="Operations notes" htmlFor="sup-notes">
          <textarea id="sup-notes" value={notes} onChange={(e) => setNotes(e.target.value)} rows={4} disabled={!can} maxLength={2000}
            className="w-full rounded-lg border border-edge-strong bg-panel px-3 py-2 text-[13px] outline-none focus:border-brand focus:shadow-[var(--focus)] disabled:bg-panel-2" />
        </Field>
        <KeyValue items={[["Take rate", `${pct(d.config.take_rate, 1)} (contract, read-only)`], ["Integration", "Synthetic feed (demo); no live connection"]]} />
        <div className="flex items-center gap-2">
          <Button variant="primary" icon={status === "paused" ? <Pause size={14} /> : <Play size={14} />} disabled={!can || !dirty} onClick={() => setAsk(true)}>Save changes</Button>
          <Button variant="ghost" disabled={!dirty} onClick={() => { setStatus(d.config.status); setNotes(d.config.notes); }}>Discard</Button>
          {!can && <span className="text-[12px] text-fg-3">Supplier operations managers and administrators can edit this.</span>}
          {dirty && can && <span className="text-[12px] text-warn">Unsaved changes</span>}
        </div>
      </div>
      <ConfirmDialog open={ask} onClose={() => setAsk(false)} busy={save.isPending} confirmLabel="Save" title="Save supplier configuration?"
        body={status === "paused" && d.config.status !== "paused" ? "Pausing removes this supplier's offers from every recommendation immediately." : undefined}
        reason="Reason" reasonRequired onConfirm={(r) => save.mutate(r)} />
    </Card>
  );
}
