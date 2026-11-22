import { useMutation, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, Download, FileUp, Play, RotateCcw, Upload } from "lucide-react";
import { useRef, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { api, ApiError } from "../lib/api";
import { useApi } from "../lib/hooks";
import { ago, dateTime, num, SUPPLIER_NAME } from "../lib/fmt";
import { toast, useSession } from "../lib/session";
import { Badge, Bar, Button, Card, cx, Empty, ErrorState, Field, Notice, PageHeader, Select, Skeleton, StatusBadge, SupplierChip } from "../ui/core";
import { ConfirmDialog } from "../ui/overlay";
import { DataTable } from "../ui/table";

export default function IngestionPage() {
  const [params, setParams] = useSearchParams();
  const job = params.get("job");
  const { data: jobs, isLoading } = useApi<any>("/ingestion/jobs?page_size=50", { refetchInterval: (q: any) => (q.state.data?.items?.some((j: any) => ["queued", "running"].includes(j.status)) ? 1500 : false) });
  const nav = useNavigate();
  return (
    <>
      <PageHeader title="Data Ingestion" description="Import a supplier feed. Files are validated first; on confirmation every valid record runs through the same matching pipeline as the catalog build, and each outcome is recorded."
        actions={job && <Button icon={<Upload size={14} />} onClick={() => setParams({}, { replace: true })}>New import</Button>} />
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-[minmax(0,1fr)_420px]">
        {job ? <JobView id={job} /> : <NewImport defaultSupplier={params.get("supplier") ?? ""} onCreated={(id) => setParams({ job: id }, { replace: true })} />}
        <Card title="Recent imports" pad={false}>
          <DataTable rows={jobs?.items} loading={isLoading} rowKey={(r: any) => r.id} onRowClick={(r: any) => setParams({ job: r.id }, { replace: true })} activeKey={job} dense
            empty={<Empty title="No imports yet" body="Validated and completed imports appear here." />}
            columns={[
              { key: "id", header: "Job", cell: (r: any) => <div><div className="font-mono text-[12px] text-fg">{r.id}</div><div className="max-w-[150px] truncate text-[11px] text-fg-3">{r.filename}</div></div> },
              { key: "s", header: "Supplier", cell: (r: any) => <SupplierChip code={r.supplier} compact /> },
              { key: "st", header: "Status", cell: (r: any) => <StatusBadge status={r.status} /> },
              { key: "t", header: "When", cell: (r: any) => <span title={dateTime(r.created_at)}>{ago(r.created_at)}</span> },
            ]} />
        </Card>
      </div>
    </>
  );
}

function NewImport({ defaultSupplier, onCreated }: { defaultSupplier: string; onCreated: (id: string) => void }) {
  const { data: sup } = useApi<any>("/ops/suppliers");
  const { data: me } = useApi<any>("/me");
  const [supplier, setSupplier] = useState(defaultSupplier || "S6");
  const [file, setFile] = useState<File | null>(null);
  const [drag, setDrag] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const input = useRef<HTMLInputElement>(null);
  const qc = useQueryClient();
  const can = me?.user?.permissions?.includes("ingestion.run");
  const status = sup?.items?.find((s: any) => s.code === supplier)?.status;
  const validate = useMutation({
    mutationFn: async () => {
      const fd = new FormData();
      fd.append("supplier", supplier);
      fd.append("file", file!);
      return api("/ingestion/jobs", { method: "POST", body: fd });
    },
    onSuccess: (j: any) => { qc.invalidateQueries(); onCreated(j.id); },
    onError: (e: any) => setErr(e instanceof ApiError ? e.message : String(e)),
  });
  const pick = (f: File | undefined | null) => {
    setErr(null);
    if (!f) return;
    if (!/\.(json|csv)$/i.test(f.name)) return setErr("Choose a .json or .csv file.");
    if (f.size > 5 * 1024 * 1024) return setErr("Files are limited to 5 MB.");
    setFile(f);
  };
  const download = async (fmt: "json" | "csv") => {
    const r = await fetch(`/api/ingestion/sample?format=${fmt}`);
    const a = document.createElement("a");
    a.href = URL.createObjectURL(await r.blob());
    a.download = `novabeds_sample.${fmt}`;
    a.click();
  };
  return (
    <Card title="New import" subtitle="Step 1 of 3 · choose the supplier and file. You will see a preview and every detected issue before anything is imported.">
      <ol className="mb-5 flex flex-wrap gap-2 text-[12px]">
        {["Select file", "Validate & preview", "Import & review results"].map((s, i) => (
          <li key={s} className={cx("flex items-center gap-1.5 rounded-full px-2.5 py-1 font-semibold", i === 0 ? "bg-brand text-white" : "bg-panel-3 text-fg-3")}>
            <span className="num">{i + 1}</span>{s}</li>
        ))}
      </ol>
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <Field label="Supplier" hint={status === "paused" ? "This supplier is paused; resume it before importing." : "Records are imported as this supplier's listings."}>
          <Select value={supplier} onChange={(e) => setSupplier(e.target.value)} className="w-full">
            {sup?.items?.map((s: any) => <option key={s.code} value={s.code}>{s.code} · {s.name} ({s.status})</option>)}
          </Select>
        </Field>
        <Field label="Need a file?" hint="A 40-hotel slice of the synthetic NovaBeds feed, never loaded at startup.">
          <div className="flex gap-2"><Button size="sm" icon={<Download size={13} />} onClick={() => download("json")}>Sample JSON</Button><Button size="sm" icon={<Download size={13} />} onClick={() => download("csv")}>Sample CSV</Button></div>
        </Field>
      </div>
      <div onDragOver={(e) => { e.preventDefault(); setDrag(true); }} onDragLeave={() => setDrag(false)}
        onDrop={(e) => { e.preventDefault(); setDrag(false); pick(e.dataTransfer.files?.[0]); }}
        className={cx("mt-4 flex flex-col items-center justify-center gap-2 rounded-card border-2 border-dashed px-6 py-10 text-center transition-colors",
          drag ? "border-brand bg-brand-soft" : "border-edge-strong bg-panel-2")}>
        <FileUp size={26} className="text-brand" />
        {file ? <div className="text-[13px]"><b className="text-fg">{file.name}</b> <span className="text-fg-3">· {num(file.size / 1024)} KB</span></div>
          : <div className="text-[13px] text-fg-2">Drop a .json or .csv supplier file here</div>}
        <Button size="sm" onClick={() => input.current?.click()}>{file ? "Choose another file" : "Browse files"}</Button>
        <input ref={input} type="file" accept=".json,.csv,application/json,text/csv" className="hidden" onChange={(e) => pick(e.target.files?.[0])} />
        <p className="mt-1 max-w-[520px] text-[12px] text-fg-3">JSON: {"{ hotels: [...], rooms: [...], offers: [...] }"} (the NovaBeds feed format). CSV: one hotel per row with record_id, name, address, phone, lat, lng, stars, city. Max 5 MB.</p>
      </div>
      {err && <Notice tone="bad" className="mt-3">{err}</Notice>}
      <div className="mt-4 flex items-center gap-3">
        <Button variant="primary" disabled={!file || !can || status === "paused"} loading={validate.isPending} onClick={() => validate.mutate()}>Validate file</Button>
        {!can && <span className="text-[12px] text-fg-3">Supplier operations managers and administrators can import data.</span>}
      </div>
    </Card>
  );
}

const OUTCOME: Record<string, [any, string]> = { attach: ["ok", "Merged into existing property"], new: ["brand", "New property"], update: ["brand", "Existing listing updated"],
  review: ["warn", "Sent to review"], rejected: ["bad", "Rejected"] };

function JobView({ id }: { id: string }) {
  const { data: j, error, isLoading, refetch } = useApi<any>(`/ingestion/jobs/${id}`, {
    placeholderData: undefined, refetchInterval: (q: any) => (["queued", "running"].includes(q.state.data?.status) ? 800 : false) });
  const { data: me } = useApi<any>("/me");
  const qc = useQueryClient();
  const nav = useNavigate();
  const [ask, setAsk] = useState(false);
  const can = me?.user?.permissions?.includes("ingestion.run");
  const start = useMutation({ mutationFn: (retry: boolean) => api(`/ingestion/jobs/${id}/${retry ? "retry" : "start"}`, { method: "POST" }),
    onSuccess: () => { setAsk(false); qc.invalidateQueries(); }, onError: (e: any) => { setAsk(false); toast({ tone: "error", title: "Could not start", body: e.message }); } });
  if (error) return <Card><ErrorState error={error} onRetry={() => refetch()} /></Card>;
  if (isLoading || !j) return <Card><Skeleton className="h-80" /></Card>;
  const step = j.status === "validated" ? 2 : 3;
  const errors = j.issues.filter((i: any) => i.severity === "error");
  const warnings = j.issues.filter((i: any) => i.severity === "warning");
  const progress = j.valid ? j.processed / j.valid : 0;
  return (
    <div className="space-y-4">
      <Card title={<span className="flex items-center gap-2">Import {j.id}<StatusBadge status={j.status} /></span>}
        subtitle={`${j.filename} · ${SUPPLIER_NAME[j.supplier]} · ${j.format.toUpperCase()} · by ${j.created_by_name} ${ago(j.created_at)}`}>
        <ol className="mb-4 flex flex-wrap gap-2 text-[12px]">
          {["Select file", "Validate & preview", "Import & review results"].map((s, i) => (
            <li key={s} className={cx("flex items-center gap-1.5 rounded-full px-2.5 py-1 font-semibold", i + 1 < step ? "bg-ok-soft text-ok" : i + 1 === step ? "bg-brand text-white" : "bg-panel-3 text-fg-3")}>
              {i + 1 < step ? <CheckCircle2 size={12} /> : <span className="num">{i + 1}</span>}{s}</li>
          ))}
        </ol>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          {[["Records in file", j.total], ["Valid", j.valid], ["Invalid (skipped)", j.invalid], ["Rooms · rates", `${j.n_rooms} · ${j.n_rates}`]].map(([k, v]) => (
            <div key={k as string} className="rounded-lg border border-edge p-3"><div className="text-[12px] text-fg-3">{k}</div><div className="num text-[18px] font-bold text-fg">{typeof v === "number" ? num(v) : v}</div></div>
          ))}
        </div>
        {j.status === "validated" && (
          <div className="mt-4 flex flex-wrap items-center gap-3">
            <Button variant="accent" icon={<Play size={14} />} disabled={!can || !j.valid} onClick={() => setAsk(true)}>Import {num(j.valid)} valid record{j.valid === 1 ? "" : "s"}</Button>
            <span className="text-[12px] text-fg-3">{j.invalid ? `${j.invalid} invalid record${j.invalid > 1 ? "s" : ""} will be skipped.` : "No blocking errors."}</span>
          </div>
        )}
        {["queued", "running"].includes(j.status) && (
          <div className="mt-4"><div className="mb-1 flex justify-between text-[12px] text-fg-3"><span>Matching records against the catalog…</span><span className="num">{j.processed} / {j.valid}</span></div><Bar value={progress} /></div>
        )}
        {j.status === "failed" && (
          <div className="mt-4 space-y-2"><Notice tone="bad">{j.error ?? "The job failed."} Records already processed are kept; retrying continues with the rest.</Notice>
            <Button icon={<RotateCcw size={14} />} onClick={() => start.mutate(true)} loading={start.isPending} disabled={!can}>Retry import</Button></div>
        )}
        {j.status === "completed" && (
          <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-5">
            {[["Merged", j.merged, "ok"], ["New properties", j.created, "brand"], ["Updated", j.updated, "brand"], ["Sent to review", j.review, "warn"], ["Rejected", j.invalid + j.rejected, "bad"]].map(([k, v, t]) => (
              <div key={k as string} className="rounded-lg border border-edge p-3"><Badge tone={t as any}>{k}</Badge><div className="num mt-1 text-[20px] font-bold text-fg">{num(v as number)}</div></div>
            ))}
          </div>
        )}
      </Card>

      {j.results.length > 0 && (
        <Card title="Record outcomes" subtitle="Decided by the calibrated matcher and the certified thresholds" pad={false}>
          <DataTable rows={j.results} rowKey={(r: any) => r.record_id} dense onRowClick={(r: any) => r.tessera_id && nav(`/inventory/hotel/${r.tessera_id}`)}
            columns={[
              { key: "id", header: "Record", cell: (r: any) => <span className="font-mono text-[12px]">{r.record_id}</span> },
              { key: "o", header: "Outcome", cell: (r: any) => <Badge tone={OUTCOME[r.outcome]?.[0]}>{OUTCOME[r.outcome]?.[1] ?? r.outcome}</Badge> },
              { key: "t", header: "Canonical record", cell: (r: any) => r.tessera_id ? <span className="font-mono text-[12px] text-brand-ink">{r.tessera_id}</span> : "—" },
              { key: "p", header: "p", align: "right", cell: (r: any) => r.p != null ? <span className="num">{r.p.toFixed(3)}</span> : "—" },
              { key: "d", header: "Detail", cell: (r: any) => {
                const m = /review case (RC-[0-9A-F]+)/.exec(r.detail ?? "");
                return <span className="text-[12px]">{r.detail}{m && <> · <Link onClick={(e) => e.stopPropagation()} to={`/matching/review?case=${m[1]}`} className="font-semibold text-brand-ink hover:underline">Open case</Link></>}</span>;
              } },
            ]} />
        </Card>
      )}

      {(errors.length > 0 || warnings.length > 0) && (
        <Card title="Detected issues" subtitle={`${errors.length} error${errors.length === 1 ? "" : "s"} (record skipped) · ${warnings.length} warning${warnings.length === 1 ? "" : "s"}`} pad={false}>
          <DataTable rows={[...errors, ...warnings].slice(0, 200)} rowKey={(r: any) => `${r.row}-${r.field}-${r.message}`} dense
            columns={[
              { key: "sev", header: "Severity", cell: (r: any) => <Badge tone={r.severity === "error" ? "bad" : "warn"}>{r.severity}</Badge> },
              { key: "row", header: "Row", align: "right", cell: (r: any) => <span className="num">{r.row}</span> },
              { key: "rid", header: "Record", cell: (r: any) => <span className="font-mono text-[12px]">{r.record_id ?? "—"}</span> },
              { key: "f", header: "Field", cell: (r: any) => r.field ?? "—" },
              { key: "m", header: "Issue", cell: (r: any) => r.message },
            ]} />
        </Card>
      )}

      {j.status === "validated" && (
        <Card title="Preview" subtitle="First rows as LedgerBot will read them" pad={false}>
          <DataTable rows={j.preview} rowKey={(r: any) => `${r.row}`} dense
            columns={[
              { key: "row", header: "Row", align: "right", cell: (r: any) => <span className="num">{r.row}</span> },
              { key: "rid", header: "Record ID", cell: (r: any) => <span className="font-mono text-[12px]">{r.record_id || "—"}</span> },
              { key: "n", header: "Name", cell: (r: any) => r.name || <i className="text-fg-3">missing</i> },
              { key: "c", header: "City", cell: (r: any) => r.city ?? "—" },
              { key: "g", header: "Coordinates", cell: (r: any) => r.lat != null ? <span className="num">{r.lat.toFixed(4)}, {r.lng.toFixed(4)}</span> : "—" },
              { key: "s", header: "Stars", cell: (r: any) => r.stars ?? "—" },
              { key: "v", header: "Validation", cell: (r: any) => r.valid ? <Badge tone={r.update ? "brand" : "ok"}>{r.update ? "Valid · updates listing" : "Valid"}</Badge> : <Badge tone="bad">Invalid</Badge> },
            ]} />
        </Card>
      )}
      <ConfirmDialog open={ask} onClose={() => setAsk(false)} busy={start.isPending} tone="accent" confirmLabel="Start import" title={`Import ${num(j.valid)} records from ${SUPPLIER_NAME[j.supplier]}?`}
        body="Each record is matched against the catalog. Confident matches merge into existing properties, clear non-matches become new properties, and ambiguous ones create review cases. Changes are recorded and can be traced in the audit trail."
        onConfirm={() => start.mutate(false)} />
    </div>
  );
}
