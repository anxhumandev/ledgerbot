import { useMutation } from "@tanstack/react-query";
import { FlaskConical } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { post } from "../lib/api";
import { useApi } from "../lib/hooks";
import { Badge, Button, cx, Field, Input, Notice, Skeleton, SupplierChip } from "../ui/core";
import { EvidenceBars } from "../ui/evidence";

const FIELDS: [string, string, string][] = [
  ["name", "Property name", "e.g. Atlantiss The Plam"], ["address", "Address", "optional"], ["phone", "Phone", "optional"],
  ["lat", "Latitude", "optional"], ["lng", "Longitude", "optional"], ["room_name", "Room name", "e.g. DLX DBL SV BB NRF"],
];
const ROUTE: Record<string, [string, string]> = {
  auto_merge: ["ok", "Auto-merge"], review: ["warn", "Human review"], llm: ["sim", "LLM adjudicated"], new_property: ["brand", "New property"],
};

/** Runs one supplier record through the live matching pipeline without changing the catalog. */
export default function MatchTester() {
  const { data: presets } = useApi<any[]>("/pipeline/presets");
  const [rec, setRec] = useState<Record<string, string>>({ name: "", address: "", phone: "", lat: "", lng: "", room_name: "" });
  const [err, setErr] = useState("");
  const run = useMutation({ mutationFn: (r: Record<string, string>) => post("/pipeline/single", { ...r, lat: r.lat === "" ? null : r.lat, lng: r.lng === "" ? null : r.lng }) });
  const submit = (r = rec) => {
    const hasLat = r.lat.trim() !== "", hasLng = r.lng.trim() !== "";
    if (!r.name.trim()) return setErr("Enter a property name.");
    if (hasLat !== hasLng) return setErr("Enter both latitude and longitude, or neither.");
    setErr("");
    run.mutate(r);
  };
  const t: any = run.data;
  return (
    <div className="space-y-4">
      <Notice tone="neutral">Test how the engine would treat a listing before a supplier sends it. Nothing is written to the catalog.</Notice>
      <div className="flex flex-wrap gap-1.5">
        {presets?.map((p) => (
          <button key={p.id} onClick={() => { const r = Object.fromEntries(Object.entries(p.record).map(([k, v]) => [k, v == null ? "" : String(v)])) as any; setRec(r); submit(r); }}
            className="rounded-full border border-edge-strong px-2.5 py-1 text-[12px] font-semibold text-fg-2 hover:border-brand hover:text-brand-ink">{p.label}</button>
        ))}
      </div>
      <form onSubmit={(e) => { e.preventDefault(); submit(); }} className="grid grid-cols-2 gap-3">
        {FIELDS.map(([k, label, ph]) => (
          <div key={k} className={k === "name" || k === "address" || k === "room_name" ? "col-span-2" : ""}>
            <Field label={label} htmlFor={`mt-${k}`}><Input id={`mt-${k}`} value={rec[k]} placeholder={ph} onChange={(e) => setRec({ ...rec, [k]: e.target.value })} /></Field>
          </div>
        ))}
        {err && <p role="alert" className="col-span-2 text-[12px] text-bad">{err}</p>}
        <div className="col-span-2"><Button variant="primary" type="submit" icon={<FlaskConical size={14} />} loading={run.isPending}>Run through pipeline</Button></div>
      </form>
      {run.isPending && <Skeleton className="h-48" />}
      {run.error && <Notice tone="bad">{(run.error as Error).message}</Notice>}
      {t && !run.isPending && (
        <div className="space-y-3">
          <div className={cx("rounded-card border-2 p-4", t.decision.route === "auto_merge" ? "border-ok bg-ok-soft" : t.decision.route === "review" ? "border-warn bg-warn-soft" : t.decision.route === "llm" ? "border-sim bg-sim-soft" : "border-brand bg-brand-soft")}>
            <div className="flex items-center gap-2"><Badge tone={ROUTE[t.decision.route][0] as any}>{ROUTE[t.decision.route][1]}</Badge>
              {t.decision.tessera_id && <Link to={`/inventory/hotel/${t.decision.tessera_id}`} className="text-[13px] font-semibold text-fg underline">{t.decision.name}</Link>}</div>
            <p className="mt-2 text-[13px] text-fg">{t.decision.reason}</p>
            {t.decision.route === "review" && t.decision.llm_offline && <p className="mt-1 text-[12px] text-fg-3">LLM adjudicator is off, so ambiguous records go straight to human review.</p>}
            {t.room_match && <p className="mt-1 text-[12px] text-fg-2">Room matched to <b>{t.room_match.name}</b> ({t.room_match.tier}).</p>}
          </div>
          <div className="text-[12px] text-fg-3">Parsed in {t.timings.parse_ms} ms · {t.n_candidates_raw} candidate records in {t.timings.candidates_ms} ms · scored in {t.timings.score_ms} ms · α {(t.alpha * 100).toFixed(1)}%</div>
          <ul className="divide-y divide-edge rounded-card border border-edge">
            {t.candidates.slice(0, 5).map((c: any) => (
              <li key={c.tessera_id} className="flex items-center gap-3 px-3 py-2 text-[13px]">
                <SupplierChip code={c.supplier} compact />
                <span className="min-w-0 flex-1 truncate text-fg">{c.name}{c.dist_m !== null && <span className="text-fg-3"> · {c.dist_m} m</span>}</span>
                <span className="hidden gap-1 sm:flex">{c.sources.map((s: string) => <span key={s} className="rounded bg-panel-3 px-1.5 font-mono text-[11px] text-fg-3">{s}</span>)}</span>
                <span className="num font-semibold text-fg">{c.p.toFixed(3)}</span>
              </li>
            ))}
          </ul>
          {t.candidates[0] && <div><div className="mb-2 text-[12px] font-semibold text-fg-3">Evidence for the best candidate</div><EvidenceBars explain={t.candidates[0].explain} limit={7} /></div>}
        </div>
      )}
    </div>
  );
}
