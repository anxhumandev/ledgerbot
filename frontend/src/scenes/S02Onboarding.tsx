import { AnimatePresence, motion } from "framer-motion";
import { useEffect, useMemo, useRef, useState } from "react";
import ForceGraph2D from "react-force-graph-2d";
import { Caption, Card, Chip, Kbd, SceneHeader, Skeleton, SupplierChip, T, Ticker } from "../design/primitives";
import { api, post } from "../lib/api";
import { useApp } from "../app/store";
import { groupIN, pct, SUPPLIERS } from "../lib/format";
import { useFetch, useHotkeys } from "../lib/hooks";
import { useTopic } from "../lib/ws";

type Node = { id: string; supplier: string; cluster: string; x?: number; y?: number; status?: string; until?: number; born?: number };
const W = 1060, H = 640;

export default function Onboarding() {
  const connected = useApp((s) => s.wsConnected);
  const showToast = useApp((s) => s.showToast);
  const [refresh, setRefresh] = useState(0);
  const { data: feedState } = useFetch<any>("/pipeline/onboard", [connected, refresh]);
  const { data: g } = useFetch<any>("/graph?city=dubai", [connected]);
  const fgRef = useRef<any>();
  const fitted = useRef(false);
  const graph = useRef<{ nodes: Node[]; links: any[] }>({ nodes: [], links: [] });
  const [graphData, setGraphData] = useState<{ nodes: Node[]; links: any[] }>({ nodes: [], links: [] });
  const [c, setC] = useState<any>(null);
  const [status, setStatus] = useState<"idle" | "running" | "done">("idle");
  const [startAt, setStartAt] = useState<number | null>(null);
  const [now, setNow] = useState(Date.now());
  const [doneInfo, setDoneInfo] = useState<any>(null);
  const [last, setLast] = useState<any[]>([]);
  const [drag, setDrag] = useState(false);

  useEffect(() => {
    if (!g) return;
    const nodes = g.nodes.map((n: Node) => ({ ...n }));
    graph.current = { nodes, links: g.links.map((l: any) => ({ ...l })) };
    setGraphData(graph.current);
  }, [g]);
  useEffect(() => {
    const st = feedState?.state;
    if (st?.status === "done") {
      setStatus("done");
      setC(st.counters);
      setDoneInfo(st);
    } else if (st?.status === "running") {
      setStatus("running"); setStartAt(st.started * 1000); if (st.counters) setC(st.counters);
    }
  }, [feedState]);
  useEffect(() => {
    if (status !== "running") return;
    const id = setInterval(() => setNow(Date.now()), 100);
    return () => clearInterval(id);
  }, [status]);
  useEffect(() => {
    const fg = fgRef.current;
    if (!fg) return;
    fg.d3Force("charge")?.strength(-6);
    fg.d3Force("link")?.distance(10).strength(0.9);
  }, [graphData.nodes.length > 0]);

  useTopic("pipeline", (m) => {
    if (m.type === "start") { setStatus("running"); setStartAt(Date.now()); setC(m.payload.counters); }
    if (m.type === "progress") setC(m.payload.counters);
    if (m.type === "decision") {
      const d = m.payload;
      setLast((l) => [d, ...l].slice(0, 5));
      if (d.city !== "dubai") return;
      const nodes = graph.current.nodes;
      if (nodes.some((n) => n.id === d.record_id)) return;
      const offset = [...String(d.record_id)].reduce((hash, char) => (hash * 31 + char.charCodeAt(0)) >>> 0, 1);
      const xs = nodes.map((n) => n.x ?? 0);
      const minX = xs.length ? Math.min(...xs) : -300;
      const node: Node = { id: d.record_id, supplier: "S6", cluster: d.tessera_id ?? d.record_id, status: d.decision,
        until: Date.now() + 1800, born: Date.now(), x: minX - 60, y: offset % 201 - 100 };
      const links = [...graph.current.links];
      if ((d.decision === "auto_merge" || d.decision === "llm") && nodes.some((n) => n.id === d.link_to)) links.push({ source: d.record_id, target: d.link_to });
      if (d.decision === "new_cluster") { node.x = offset % 501 - 250; node.y = (offset >>> 4) % 401 - 200; }
      if (d.decision === "review" && d.tessera_id) {
        const anchor = nodes.find((n) => n.cluster === d.tessera_id);
        if (anchor) { node.x = (anchor.x ?? 0) + 18; node.y = (anchor.y ?? 0) + 18; }
      }
      graph.current = { nodes: [...nodes, node], links };
      setGraphData(graph.current);
      fgRef.current?.d3ReheatSimulation();
    }
    if (m.type === "done") { setStatus("done"); setC(m.payload.counters); setDoneInfo(m.payload); }
  });

  const start = async () => {
    if (status !== "idle") return;
    try {
      await post("/pipeline/onboard");
      setRefresh((n) => n + 1);
    } catch { showToast("Could not start onboarding. Try again.", "clay"); }
  };
  useHotkeys({ o: start });

  const decided = c ? c.clustered + c.review : 0;
  const elapsed = status === "done" ? c?.elapsed ?? 0 : startAt ? (now - startAt) / 1000 : 0;
  const clock = `${String(Math.floor(elapsed / 60)).padStart(2, "0")}:${String(Math.floor(elapsed % 60)).padStart(2, "0")}`;
  const feed = feedState?.feed;
  const risk = doneInfo?.risk;

  const drawNode = useMemo(() => (node: any, ctx: CanvasRenderingContext2D) => {
    const s6 = node.supplier === "S6";
    const r = s6 ? 5 : 3.6;
    ctx.beginPath();
    ctx.arc(node.x, node.y, r, 0, 2 * Math.PI);
    ctx.fillStyle = SUPPLIERS[node.supplier]?.color ?? "#999";
    ctx.globalAlpha = s6 ? 1 : 0.8;
    ctx.fill();
    ctx.globalAlpha = 1;
    const t = Date.now();
    if (node.status === "review") {
      const k = (t % 1400) / 1400;
      ctx.beginPath();
      ctx.arc(node.x, node.y, r + 2 + 6 * k, 0, 2 * Math.PI);
      ctx.strokeStyle = `rgba(201,154,26,${0.8 * (1 - k)})`;
      ctx.lineWidth = 1.6;
      ctx.stroke();
    } else if (node.status === "llm" && node.until > t) {
      ctx.beginPath();
      ctx.arc(node.x, node.y, r + 3, 0, 2 * Math.PI);
      ctx.strokeStyle = "rgba(91,79,201,.9)";
      ctx.lineWidth = 1.6;
      ctx.stroke();
    } else if (s6 && node.until > t) {
      ctx.beginPath();
      ctx.arc(node.x, node.y, r + 3 * ((node.until - t) / 1800), 0, 2 * Math.PI);
      ctx.strokeStyle = "rgba(180,104,58,.6)";
      ctx.lineWidth = 1.2;
      ctx.stroke();
    }
  }, []);

  const drawHulls = (ctx: CanvasRenderingContext2D) => {
    const by: Record<string, Node[]> = {};
    for (const n of graph.current.nodes) (by[n.cluster] ??= []).push(n);
    ctx.save();
    for (const k in by) {
      const ns = by[k];
      if (ns.length < 2) continue;
      if (ns.some((n) => n.supplier === "S6" && (n.until ?? 0) > Date.now())) continue;
      let cx = 0, cy = 0;
      for (const n of ns) { cx += n.x ?? 0; cy += n.y ?? 0; }
      cx /= ns.length; cy /= ns.length;
      let r = 0;
      for (const n of ns) r = Math.max(r, Math.hypot((n.x ?? 0) - cx, (n.y ?? 0) - cy));
      if (r > 40) continue;
      ctx.beginPath();
      ctx.arc(cx, cy, r + 7, 0, 2 * Math.PI);
      ctx.fillStyle = "rgba(14,94,111,0.055)";
      ctx.fill();
    }
    ctx.restore();
  };

  if (!feed || !g) return <Skeleton className="w-full h-full" />;
  const stages = [
    { label: "Parsed", value: c?.parsed ?? 0, sub: `of ${groupIN(feed.hotels)} records` },
    { label: "Candidates", value: c?.candidates ?? 0, sub: c ? `recall ${pct(c.recall ?? 0, 1)} · reduction ${pct(c.reduction ?? 0, 2)}` : "H3 · BM25 · ANN · pHash" },
    { label: "Scored", value: c?.scored ?? 0, sub: "LightGBM + isotonic" },
    { label: "Decided", value: decided, sub: c ? `${c.auto_merge} auto · ${c.llm} LLM · ${c.review} review · ${c.new_cluster} new` : "risk-controlled" },
    { label: "Clustered", value: c?.clustered ?? 0, sub: "supplier-exclusive" },
  ];
  return (
    <div className="h-full flex flex-col">
      <SceneHeader headline="A new supplier, mapped in under a minute." subline="NovaBeds has never been seen before. Every decision below is computed live: blocking, scoring, risk-controlled routing, clustering." />
      <div className="grid grid-cols-5 gap-3">
        {stages.map((s, i) => (
          <Card key={s.label} {...{ initial: { opacity: 0, y: 8 }, animate: { opacity: 1, y: 0 }, transition: { ...T, delay: i * 0.04 } }} className="px-5 py-3 relative">
            <Caption>{String(i + 1).padStart(2, "0")} · {s.label}</Caption>
            <div className="font-mono text-[32px] leading-tight text-ink"><Ticker value={s.value} format={(v) => groupIN(v)} /></div>
            <div className="text-[12px] text-ink-3 truncate">{s.sub}</div>
            {i < 4 && <div className="absolute -right-3 top-1/2 -translate-y-1/2 text-ink-3 z-10">›</div>}
          </Card>
        ))}
      </div>
      <div className="mt-4 flex gap-6 flex-1 min-h-0">
        <div className="w-[300px] flex flex-col gap-4">
          <motion.div onDragOver={(e) => { e.preventDefault(); setDrag(true); }} onDragLeave={() => setDrag(false)}
            onDrop={(e) => { e.preventDefault(); setDrag(false); start(); }} onClick={start}
            animate={{ scale: drag ? 1.02 : 1 }} transition={T}
            className="rounded-card border-2 border-dashed p-5 cursor-pointer bg-surface"
            style={{ borderColor: status === "idle" ? SUPPLIERS.S6.color : "var(--line)" }}>
            <SupplierChip code="S6" />
            <div className="font-serif text-[30px] mt-3 leading-tight">NovaBeds</div>
            <div className="text-[15px] text-ink-2 mt-1 font-mono">{groupIN(feed.hotels)} hotels · {groupIN(feed.rooms)} rooms</div>
            <div className="text-[13px] text-ink-3 mt-1">{feed.cities.length} cities · never seen before</div>
            <div className="mt-4 text-[13px] text-ink-3">{status === "idle" ? <>Drop the feed or press <Kbd>O</Kbd></> : status === "running" ? "Onboarding…" : "Live"}</div>
          </motion.div>
          <Card className="p-4 flex-1 min-h-0 overflow-hidden">
            <Caption>Latest decisions</Caption>
            <div className="mt-2 space-y-2">
              <AnimatePresence initial={false} mode="popLayout">
                {last.map((d) => (
                  <motion.div key={d.record_id} layout initial={{ opacity: 0, y: -6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} transition={T} className="text-[13px]">
                    <div className="truncate text-ink">{d.name}</div>
                    <div className="flex items-center gap-1.5 mt-0.5">
                      <Chip variant={d.decision === "auto_merge" ? "sage" : d.decision === "llm" ? "iris" : d.decision === "review" ? "amber" : "lagoon"}>
                        {d.decision === "auto_merge" ? "auto-merged" : d.decision === "llm" ? "LLM" : d.decision === "review" ? "review" : "new hotel"}
                      </Chip>
                      <span className="text-ink-3 truncate">{d.cluster_name ?? d.city}</span>
                    </div>
                  </motion.div>
                ))}
              </AnimatePresence>
            </div>
          </Card>
        </div>
        <Card className="flex-1 relative overflow-hidden dotgrid">
          <ForceGraph2D ref={fgRef} graphData={graphData} width={W} height={H} backgroundColor="rgba(0,0,0,0)"
            nodeCanvasObject={drawNode} nodeCanvasObjectMode={() => "replace"} onRenderFramePre={drawHulls}
            linkColor={() => "rgba(14,94,111,0.18)"} linkWidth={0.6} enableNodeDrag={false} enableZoomInteraction={false}
            enablePanInteraction={false} cooldownTime={4000} d3VelocityDecay={0.35} warmupTicks={60}
            onEngineStop={() => { if (!fitted.current) { fitted.current = true; fgRef.current?.zoomToFit(600, 40); } }} />
          <div className="absolute left-4 bottom-3 flex gap-2 flex-wrap">
            {["S1", "S2", "S3", "S4", "S5", "S6"].map((s) => <SupplierChip key={s} code={s} short />)}
            <span className="text-[12px] text-ink-3 self-center ml-2">Dubai shown · counters cover all {feed.cities.length} cities</span>
          </div>
        </Card>
        <div className="w-[300px] flex flex-col gap-4">
          <Card className="p-5">
            <Caption>Elapsed</Caption>
            <div className="font-mono text-[52px] leading-none mt-1">{clock}</div>
          </Card>
          {[
            { label: "Auto-merged", v: decided ? c.auto_merge / decided : 0, tone: "text-[color:var(--sage-ink)]", hint: "matched to an existing hotel" },
            { label: "Sent to LLM", v: decided ? c.llm / decided : 0, tone: "text-iris", hint: "uncertain band only" },
            { label: "Human review", v: decided ? c.review / decided : 0, tone: "text-[color:var(--amber-ink)]", hint: "abstained, with a reason" },
          ].map((s) => (
            <Card key={s.label} className="p-5">
              <Caption>{s.label}</Caption>
              <div className={`font-mono text-[44px] leading-none mt-1 ${s.tone}`}><Ticker value={s.v * 100} format={(v) => `${v.toFixed(1)}%`} /></div>
              <div className="text-[12px] text-ink-3 mt-1">{s.hint}</div>
            </Card>
          ))}
        </div>
      </div>
      <AnimatePresence>
        {status === "done" && doneInfo && (
          <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={T}
            className="absolute left-1/2 -translate-x-1/2 bottom-12 bg-surface border border-line text-ink rounded-full px-7 py-3 text-[18px] font-medium shadow-card z-30">
            NovaBeds live in {Math.round(doneInfo.counters.elapsed)} s. {doneInfo.counters.violations} consistency violations. {risk?.certifiable && risk?.held && risk.test_merges > 0 ? `Certified false-merge limit ${(doneInfo.alpha * 100).toFixed(1)}% (${Math.round((1 - risk.delta) * 100)}% confidence).` : risk?.certifiable && !risk?.held ? "Held-out false merges exceeded the target." : "No verified held-out guarantee for this setting."}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
