import { AnimatePresence, motion } from "framer-motion";
import { useEffect, useRef, useState } from "react";
import { Button, Caption, Card, Chip, ProbBar, SceneHeader, Skeleton, SupplierChip, T, cx } from "../design/primitives";
import { post } from "../lib/api";
import { ms } from "../lib/format";
import { useFetch, useHotkeys } from "../lib/hooks";

const FIELDS: [string, string, string][] = [
  ["name", "Hotel name", "e.g. Atlantiss The Plam"], ["address", "Address", "optional"], ["phone", "Phone", "optional"],
  ["lat", "Latitude", "optional"], ["lng", "Longitude", "optional"], ["room_name", "Room name", "e.g. DLX DBL SV BB NRF"],
];

/** Single-record pipeline trace. Rendered as the Inspector's "Try to fool it" tab (embedded) or on its own. */
export default function BreakIt({ embedded = false }: { embedded?: boolean }) {
  const { data: presets } = useFetch<any[]>("/pipeline/presets");
  const [rec, setRec] = useState<any>({ name: "", address: "", phone: "", lat: "", lng: "", room_name: "" });
  const [trace, setTrace] = useState<any>(null);
  const [step, setStep] = useState(0);
  const [busy, setBusy] = useState(false);
  const [active, setActive] = useState<string | null>(null);

  const [error, setError] = useState("");
  const latest = useRef(0);
  const run = async (r = rec) => {
    const request = ++latest.current;
    const hasLat = String(r.lat ?? "").trim() !== "";
    const hasLng = String(r.lng ?? "").trim() !== "";
    let validation = "";
    if (!r.name?.trim()) validation = "Enter a hotel name.";
    else if (hasLat !== hasLng) validation = "Enter both latitude and longitude, or leave both empty.";
    else if (hasLat && (!Number.isFinite(Number(r.lat)) || Math.abs(Number(r.lat)) > 90 ||
      !Number.isFinite(Number(r.lng)) || Math.abs(Number(r.lng)) > 180)) {
      validation = "Latitude must be between −90 and 90 and longitude between −180 and 180.";
    }
    setError(validation);
    if (validation) { setTrace(null); setBusy(false); return; }
    setBusy(true);
    setTrace(null);
    setStep(0);
    try {
      const t = await post("/pipeline/single", { ...r, lat: r.lat === "" ? null : r.lat, lng: r.lng === "" ? null : r.lng });
      if (request === latest.current) setTrace(t);
    } catch {
      if (request === latest.current) setError("Could not score this listing. Check the input and try again.");
    } finally {
      if (request === latest.current) setBusy(false);
    }
  };
  useEffect(() => {
    if (!trace) return;
    const ids = [1, 2, 3, 4].map((s, i) => setTimeout(() => setStep(s), 120 + i * 300));
    return () => ids.forEach(clearTimeout);
  }, [trace]);
  const choose = (p: any) => {
    const r = Object.fromEntries(Object.entries(p.record).map(([k, v]) => [k, v ?? ""]));
    setRec(r);
    setActive(p.id);
    run(r);
  };
  useHotkeys(Object.fromEntries([
    ...(presets ?? []).map((p, i) => [String(i + 1), () => choose(p)]),
    ["Enter", () => run()],
  ]));

  return (
    <div className="h-full flex flex-col">
      {!embedded && <SceneHeader headline="Try to fool it." subline="Paste any supplier listing. The real pipeline runs on one record: parse, block, score, decide. Abstaining is a feature." />}
      <div className="grid grid-cols-[520px_minmax(0,1fr)] gap-6 flex-1 min-h-0">
        <Card className="p-6 flex flex-col">
          <Caption>Paste or type any supplier listing</Caption>
          <div className="mt-3 flex flex-wrap gap-2">
            {presets ? presets.map((p, i) => (
              <button key={p.id} onClick={() => choose(p)} className={cx("rounded-full px-3 py-1 text-[14px] border transition",
                active === p.id ? "bg-ink text-paper border-ink" : "border-line text-ink-2 hover:bg-surface-2")}>
                <span className="font-mono text-[13px] opacity-60 mr-1">{i + 1}</span>{p.label}
              </button>
            )) : <Skeleton className="h-7 w-full" />}
          </div>
          <div className="mt-5 space-y-3">
            {FIELDS.map(([k, label, ph]) => (
              <label key={k} className="block">
                <span className="text-[13px] text-ink-3">{label}</span>
                <input value={rec[k] ?? ""} placeholder={ph} onChange={(e) => { setRec({ ...rec, [k]: e.target.value }); setActive(null); }}
                  onKeyDown={(e) => e.key === "Enter" && run()}
                  className="mt-1 w-full rounded-xl border border-line bg-paper px-3 py-2 text-[16px] font-mono outline-none focus:border-lagoon focus:ring-2 focus:ring-lagoon-soft" />
              </label>
            ))}
          </div>
          {error && <p role="alert" className="mt-3 text-[15px] text-[color:var(--clay-ink)]">{error}</p>}
          <div className="mt-auto pt-5 flex items-center justify-between">
            <Button onClick={() => run()} disabled={busy || !rec.name} kbd="Enter">Run the pipeline</Button>
            {trace && <span className="text-[14px] text-ink-3 font-mono">total {ms(trace.timings.total_ms)}</span>}
          </div>
        </Card>
        <div className="flex flex-col gap-3 min-h-0">
          {!trace && !busy && <div className="h-full rounded-card border border-dashed border-line flex items-center justify-center text-ink-3 text-[18px]">Pick a preset (1–5) or type a listing.</div>}
          {busy && <Skeleton className="h-full" />}
          {trace && (
            <>
              <TraceStep n={1} show={step >= 1} title="Parsed" time={trace.timings.parse_ms}>
                <div className="flex flex-wrap gap-1.5">
                  {trace.parsed.brand && <Chip variant="lagoon">brand · {trace.parsed.brand}</Chip>}
                  <Chip>core · {trace.parsed.core_name || "—"}</Chip>
                  <Chip>phone · {trace.parsed.phone ?? "missing"}</Chip>
                  <Chip>city · {trace.parsed.city}</Chip>
                  {trace.parsed.room_identity && Object.entries(trace.parsed.room_identity).filter(([, v]) => v !== null && v !== false).map(([k, v]) => <Chip key={k} variant="iris">{k} · {String(v)}</Chip>)}
                  {trace.parsed.room?.board && <Chip variant="saffron">board · {trace.parsed.room.board} (offer, not identity)</Chip>}
                  {trace.parsed.room?.refundable === false && <Chip variant="saffron">non-refundable (offer)</Chip>}
                </div>
              </TraceStep>
              <TraceStep n={2} show={step >= 2} title={`Candidates · ${trace.candidates.length} hotels (from ${trace.n_candidates_raw} records)`} time={trace.timings.candidates_ms}>
                <div className="grid grid-cols-2 gap-x-6 gap-y-1">
                  {trace.candidates.slice(0, 8).map((c: any) => (
                    <div key={c.tessera_id} className="flex items-center gap-2 text-[14px] min-w-0">
                      <span className="truncate flex-1">{c.name}</span>
                      {c.sources.map((s: string) => <span key={s} className="font-mono text-[12px] px-1.5 rounded bg-surface-2 text-ink-3">{s}</span>)}
                    </div>
                  ))}
                </div>
              </TraceStep>
              <TraceStep n={3} show={step >= 3} title="Scored · calibrated p against the current thresholds" time={trace.timings.score_ms}>
                <div className="space-y-2">
                  {trace.candidates.slice(0, 4).map((c: any) => (
                    <div key={c.tessera_id} className="flex items-center gap-4">
                      <span className="w-[260px] truncate text-[14px]">{c.name}{c.dist_m !== null && <span className="text-ink-3"> · {c.dist_m} m</span>}</span>
                      <ProbBar p={c.p} tauAccept={trace.tau_accept} tauReject={trace.tau_reject} width={420} label={false} />
                      <span className="font-mono text-[14px] w-16">{c.p.toFixed(3)}</span>
                    </div>
                  ))}
                  <div className="text-[13px] text-ink-3 font-mono">{trace.tau_reject == null ? "auto-reject disabled" : `grey ≤ ${trace.tau_reject.toFixed(2)} auto-reject`} · amber review · {trace.tau_accept == null ? "auto-merge disabled" : `green ≥ ${trace.tau_accept.toFixed(2)} auto-merge`} (α = {(trace.alpha * 100).toFixed(1)}%)</div>
                </div>
              </TraceStep>
              <AnimatePresence>
                {step >= 4 && <Decision t={trace} />}
              </AnimatePresence>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

function TraceStep({ n, show, title, time, children }: any) {
  return (
    <AnimatePresence>
      {show && (
        <Card initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={T} className="p-4">
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-2"><span className="w-6 h-6 rounded-full bg-lagoon-soft text-lagoon text-[13px] font-mono flex items-center justify-center">{n}</span><span className="text-[16px] font-medium">{title}</span></div>
            <span className="font-mono text-[13px] text-ink-3">{ms(time)}</span>
          </div>
          {children}
        </Card>
      )}
    </AnimatePresence>
  );
}

function Decision({ t }: { t: any }) {
  const d = t.decision;
  const tone = { auto_merge: ["bg-sage-soft border-sage", "text-[color:var(--sage-ink)]", "AUTO-MERGE"], llm: ["bg-iris-soft border-iris", "text-iris", "LLM ADJUDICATED"],
    review: ["bg-amber-soft border-amber", "text-[color:var(--amber-ink)]", "HUMAN REVIEW"], new_property: ["bg-lagoon-soft border-lagoon", "text-lagoon", "NEW PROPERTY"] }[d.route as string]!;
  return (
    <motion.div initial={{ opacity: 0, scale: 0.98 }} animate={{ opacity: 1, scale: 1 }} transition={T} className={cx("rounded-card border-2 p-5", tone[0])}>
      <div className="flex items-center gap-3">
        <span className="w-6 h-6 rounded-full bg-white/70 text-[13px] font-mono flex items-center justify-center">4</span>
        <span className={cx("text-[22px] font-semibold tracking-wide", tone[1])}>{tone[2]}</span>
        {d.name && <span className="text-[18px] text-ink">→ {d.name}</span>}
      </div>
      <div className="mt-2 text-[17px] text-ink">{d.reason}</div>
      {d.route === "llm" && d.llm_json && <pre className="mt-2 font-mono text-[13px] text-iris bg-white/60 rounded-lg p-2">{JSON.stringify(d.llm_json)}</pre>}
      {d.route === "review" && d.llm_offline && <div className="mt-1 text-[14px] text-ink-3">LLM offline: routing to review.</div>}
      {t.room_match && (
        <div className="mt-3 flex items-center gap-2 text-[15px]">
          <Caption>Room</Caption><span>{t.room_match.name}</span><Chip variant={t.room_match.tier === "Primary" ? "lagoon" : "amber"}>{t.room_match.tier} match</Chip>
          {t.room_match.suppliers.map((s: string) => <SupplierChip key={s} code={s} short />)}
        </div>
      )}
    </motion.div>
  );
}
