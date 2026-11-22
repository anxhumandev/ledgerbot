import { AnimatePresence, motion } from "framer-motion";
import { useEffect, useState } from "react";
import { Button, Caption, Card, Chip, Kbd, SceneHeader, T, Ticker, Toggle } from "../design/primitives";
import { api, post } from "../lib/api";
import { formatINR, groupIN, RECORD_MODE } from "../lib/format";
import { useHotkeys } from "../lib/hooks";
import { useTopic } from "../lib/ws";

export default function Impact() {
  const [view, setView] = useState<"A" | "B">("A");
  const [step, setStep] = useState(0);
  const [replay, setReplay] = useState<any>(null);
  const [running, setRunning] = useState(false);
  useEffect(() => { api("/sim/replay").then((r) => { if (r.last) setReplay(r.last); setRunning(r.running); }); }, []);
  useTopic("replay", (m) => {
    if (m.type === "start") setRunning(true);
    if (m.type === "tick") setReplay(m.payload);
    if (m.type === "done") { setReplay(m.payload); setRunning(false); }
  });
  const runReplay = () => { if (!running) post("/sim/replay", { n: 50000 }); };
  const nextStep = () => setStep((s) => Math.min(STEPS.length, s + 1));
  const space = () => (view === "A" ? runReplay() : nextStep());
  useHotkeys({ a: () => setView("A"), b: () => setView("B"), " ": space });
  return (
    <div className="h-full flex flex-col">
      <SceneHeader headline="From prototype to production at TBO scale."
        subline={view === "A" ? "Replay simulated agent searches through two shelves. Same agents, same suppliers, same hidden reliability." : "Where each piece runs, and why the LLM never sits on the search path."}
        right={<Toggle value={view} onChange={(v) => setView(v)} options={[{ value: "A", label: "Impact replay" }, { value: "B", label: "Architecture" }]} />} />
      <div className="flex-1 min-h-0">{view === "A" ? <Replay r={replay} running={running} onRun={runReplay} /> : <Architecture step={step} onNext={nextStep} onAll={() => setStep(STEPS.length)} onRestart={() => setStep(0)} />}</div>
    </div>
  );
}

const LANES = [
  { key: "searches", label: "Searches", fmt: (v: number) => groupIN(v) },
  { key: "bookings", label: "Bookings", fmt: (v: number) => groupIN(v) },
  { key: "look_to_book", label: "Look-to-book", fmt: (v: number) => `${(v * 100).toFixed(2)}%` },
  { key: "gross_profit", label: "Gross profit", fmt: (v: number) => formatINR(v, { compact: true, decimals: 2 }) },
  { key: "failed", label: "Failed bookings", fmt: (v: number) => groupIN(v) },
  { key: "wrong_room", label: "Wrong-room incidents", fmt: (v: number) => groupIN(v) },
];

function Replay({ r, running, onRun }: { r: any; running: boolean; onRun: () => void }) {
  const arms = r?.arms;
  return (
    <div className="h-full flex flex-col gap-5">
      {[["raw", "Cheapest-wins + raw shelf", "text-ink-2"], ["tessera", "LedgerBot: expected value + deduplicated shelf", "text-lagoon"]].map(([k, label, tone]) => (
        <Card key={k} className="p-6">
          <div className={`text-[20px] font-medium ${tone}`}>{label}</div>
          <div className="grid grid-cols-6 gap-6 mt-3">
            {LANES.map((l) => (
              <div key={l.key}>
                <Caption>{l.label}</Caption>
                <div className={`font-sans font-semibold tabular text-[38px] leading-tight ${k === "tessera" ? "text-ink" : "text-ink-2"}`}>
                  <Ticker value={arms ? arms[k][l.key] : 0} format={l.fmt} />
                </div>
              </div>
            ))}
          </div>
        </Card>
      ))}
      <div className="flex-1 flex items-center justify-center">
        <AnimatePresence mode="wait">
          {!r && !running && <motion.div key="hint" exit={{ opacity: 0 }} className="flex flex-col items-center gap-3"><Button onClick={onRun} kbd="Space" className="!text-[18px] !px-6 !py-3">Replay 50,000 searches</Button><span className="text-[15px] text-ink-3">simulated, at about 1000× speed</span></motion.div>}
          {r && (
            <motion.div key="fin" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={T} className="text-center">
              <div className="font-sans font-semibold tabular text-[72px] leading-none text-[color:var(--saffron-ink)]">
                <Ticker value={r.lift_gp_per_search * 100} format={(v) => `${v >= 0 ? "+" : ""}${v.toFixed(1)}%`} />
              </div>
              <div className="text-[18px] text-ink-2 mt-2">gross profit per search (simulated) · {groupIN(r.done)} of {groupIN(r.n)} searches replayed</div>
              {!running && (
                <div className="mt-4 inline-flex items-center gap-3 rounded-full bg-saffron-soft px-5 py-2">
                  <span className="text-[14px] uppercase tracking-[0.08em] text-[color:var(--saffron-ink)] font-medium">Annualized at TBO hotel scale (illustrative)</span>
                  <span className="font-sans font-semibold tabular text-[22px] text-ink">{formatINR(r.annualized_inr_illustrative, { compact: true })}</span>
                  <span className="text-[13px] text-ink-3">= {r.formula}</span>
                </div>
              )}
              {!running && !RECORD_MODE && <div className="mt-4"><Button variant="ghost" onClick={onRun} kbd="Space">Run the replay again</Button></div>}
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ architecture */
const STEPS = [
  { id: 1, x: 40, y: 70, w: 230, h: 120, title: "Ingest", lines: ["Supplier pull/push", "XML · JSON · OCTO", "Kafka topic per supplier", "Schema registry"] },
  { id: 2, x: 320, y: 70, w: 230, h: 120, title: "Normalize", lines: ["Dictionaries + distilled tagger", "Offline LLM teacher", "EN · ES · abbreviations"] },
  { id: 3, x: 600, y: 70, w: 250, h: 120, title: "Candidates", lines: ["OpenSearch BM25", "Vector index (HNSW)", "H3 keys · pHash index"] },
  { id: 4, x: 900, y: 70, w: 230, h: 120, title: "Matcher", lines: ["LightGBM / ONNX on CPU", "< 2 ms per pair"] },
  { id: 5, x: 1180, y: 70, w: 280, h: 120, title: "Risk-controlled decisions", lines: ["Per-supplier calibration", "Learn-then-Test thresholds", "Recalibrated weekly"] },
  { id: 6, x: 1180, y: 250, w: 280, h: 110, title: "LLM adjudicator", lines: ["Async, batched", "Uncertain band only", "Never on the search path"], tone: "iris" },
  { id: 7, x: 1180, y: 410, w: 280, h: 110, title: "Ops review console", lines: ["Active learning picks", "what humans label"], tone: "amber" },
  { id: 8, x: 760, y: 300, w: 330, h: 120, title: "Golden records + cluster graph", lines: ["Postgres + graph tables", "Versioned mappings", "One-click rollback"] },
  { id: 9, x: 40, y: 300, w: 640, h: 120, title: "Search path", lines: ["Redis mapping cache → offer selector (EV, < 3 ms) → ranker", "→ B2B portal and API buyers (a clean deduplicated feed is a product too)"], tone: "saffron" },
  { id: 10, x: 40, y: 560, w: 1420, h: 80, title: "Feedback loop", lines: ["Booking outcomes · 409 / price mismatch · timeouts · wrong-room complaints → feature store → reliability posteriors + retraining + drift monitors"], tone: "sage" },
];
const EDGES: [number, number][] = [[1, 2], [2, 3], [3, 4], [4, 5], [5, 6], [6, 7], [5, 8], [7, 8], [8, 9]];
const TONE: Record<string, [string, string]> = { iris: ["var(--iris-soft)", "var(--iris)"], amber: ["var(--amber-soft)", "var(--amber)"], saffron: ["var(--saffron-soft)", "var(--saffron)"], sage: ["var(--sage-soft)", "var(--sage)"] };

function Architecture({ step, onNext, onAll, onRestart }: { step: number; onNext: () => void; onAll: () => void; onRestart: () => void }) {
  const box = (id: number) => STEPS.find((s) => s.id === id)!;
  const c = (s: any, side: "r" | "l" | "b" | "t") => side === "r" ? [s.x + s.w, s.y + s.h / 2] : side === "l" ? [s.x, s.y + s.h / 2] : side === "b" ? [s.x + s.w / 2, s.y + s.h] : [s.x + s.w / 2, s.y];
  const path = (a: any, b: any) => {
    if (Math.abs(a.y - b.y) < 5) { const [x1, y1] = c(a, "r"); const [x2, y2] = c(b, "l"); return `M${x1},${y1} L${x2},${y2}`; }
    if (a.x === b.x) { const [x1, y1] = c(a, "b"); const [x2, y2] = c(b, "t"); return `M${x1},${y1} L${x2},${y2}`; }
    if (b.x < a.x) { const [x1, y1] = c(a, a.y < b.y ? "b" : "l"); const [x2, y2] = c(b, "r"); return `M${x1},${y1} C${x1},${y2} ${x1},${y2} ${x2},${y2}`; }
    const [x1, y1] = c(a, "b"); const [x2, y2] = c(b, "t"); return `M${x1},${y1} C${x1},${(y1 + y2) / 2} ${x2},${(y1 + y2) / 2} ${x2},${y2}`;
  };
  return (
    <div className="relative h-full">
      <svg viewBox="0 0 1500 660" className="w-full h-[640px]">
        <defs><marker id="arr" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M0,0 L10,5 L0,10 z" fill="var(--ink-3)" /></marker></defs>
        {EDGES.map(([a, b]) => step >= Math.max(a, b) && (
          <motion.path key={`${a}-${b}`} d={path(box(a), box(b))} fill="none" stroke="var(--ink-3)" strokeWidth={1.5} markerEnd="url(#arr)"
            initial={{ pathLength: 0 } as any} animate={{ pathLength: 1 } as any} transition={{ duration: 0.6, ease: [0.22, 1, 0.36, 1] }} />
        ))}
        {step >= 10 && (
          <motion.path d="M 750 560 C 750 520, 155 520, 155 190" fill="none" stroke="var(--sage)" strokeWidth={2} strokeDasharray="7 7"
            initial={{ pathLength: 0 } as any} animate={{ pathLength: 1, strokeDashoffset: [0, -28] } as any} transition={{ pathLength: { duration: 1.2 }, strokeDashoffset: { duration: 1.2, repeat: Infinity, ease: "linear" } }} />
        )}
        {STEPS.map((s) => step >= s.id && (
          <motion.g key={s.id} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={T}>
            <rect x={s.x} y={s.y} width={s.w} height={s.h} rx={16} fill={s.tone ? TONE[s.tone][0] : "var(--surface)"} stroke={s.tone ? TONE[s.tone][1] : "var(--line)"} />
            <text x={s.x + 18} y={s.y + 30} fontFamily="Geist" fontWeight={600} fontSize={17} fill="var(--ink)">{s.id}. {s.title}</text>
            {s.lines.map((l, i) => <text key={i} x={s.x + 18} y={s.y + 56 + i * 20} fontFamily="Geist" fontSize={14} fill="var(--ink-2)">{l}</text>)}
          </motion.g>
        ))}
      </svg>
      <div className="absolute left-0 bottom-0 flex gap-3 items-center">
        {step >= 9 && <Chip variant="saffron">Added to search path: &lt; 5 ms p95</Chip>}
        {step >= 10 && <Chip variant="lagoon">Shadow mode → triggered A/B (only searches where rankings differ) → ramp</Chip>}
        {!RECORD_MODE && step < STEPS.length && <Button onClick={onNext} kbd="Space">{step === 0 ? "Start drawing" : "Next step"} ({step}/{STEPS.length})</Button>}
        {!RECORD_MODE && step < STEPS.length && <Button variant="ghost" onClick={onAll}>Draw all</Button>}
        {!RECORD_MODE && step > 0 && <Button variant="ghost" onClick={onRestart}>Restart</Button>}
      </div>
    </div>
  );
}
