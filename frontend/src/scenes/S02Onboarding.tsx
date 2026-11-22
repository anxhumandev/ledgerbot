import { AnimatePresence, motion } from "framer-motion";
import { Maximize2, Minus, MousePointerClick, Plus, Search } from "lucide-react";
import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import ForceGraph2D from "react-force-graph-2d";
import { Caption, Card, Chip, Kbd, SceneHeader, Skeleton, SupplierChip, T, Ticker } from "../design/primitives";
import { post } from "../lib/api";
import { useApp } from "../app/store";
import { groupIN, pct, RECORD_MODE, SUPPLIERS } from "../lib/format";
import { useFetch, useHotkeys } from "../lib/hooks";
import { useTopic } from "../lib/ws";

type Node = {
  id: string; supplier: string; cluster: string; name?: string; hotel?: string; neighbourhood?: string; stars?: number;
  size?: number; x?: number; y?: number; fx?: number; fy?: number; status?: string; until?: number; born?: number;
};

/** Size of an element, kept in sync with layout (the graph canvas needs explicit pixels). */
function useBox<T extends HTMLElement>() {
  const ref = useRef<T>(null);
  const [box, setBox] = useState({ w: 1200, h: 640 });
  useLayoutEffect(() => {
    if (!ref.current) return;
    const ro = new ResizeObserver(([e]) => {
      const { width, height } = e.contentRect;
      if (width > 0 && height > 0) setBox({ w: Math.round(width), h: Math.round(height) });
    });
    ro.observe(ref.current);
    return () => ro.disconnect();
  }, []);
  return [ref, box] as const;
}

const esc = (s: unknown) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]!));

export default function Onboarding() {
  const connected = useApp((s) => s.wsConnected);
  const showToast = useApp((s) => s.showToast);
  const [refresh, setRefresh] = useState(0);
  const { data: feedState } = useFetch<any>("/pipeline/onboard", [connected, refresh]);
  const { data: g } = useFetch<any>("/graph?city=dubai", [connected]);
  const fgRef = useRef<any>();
  const fitted = useRef(false);
  const hover = useRef<string | null>(null); // hovered cluster
  const focus = useRef<string | null>(null); // cluster found by the map search
  const graph = useRef<{ nodes: Node[]; links: any[] }>({ nodes: [], links: [] });
  const [graphData, setGraphData] = useState<{ nodes: Node[]; links: any[] }>({ nodes: [], links: [] });
  const [c, setC] = useState<any>(null);
  const [status, setStatus] = useState<"idle" | "running" | "done">("idle");
  const [startAt, setStartAt] = useState<number | null>(null);
  const [now, setNow] = useState(Date.now());
  const [doneInfo, setDoneInfo] = useState<any>(null);
  const [last, setLast] = useState<any[]>([]);
  const [drag, setDrag] = useState(false);
  const [query, setQuery] = useState("");
  const [boxRef, box] = useBox<HTMLDivElement>();

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
    // when onboarding finishes, glide out to frame every cluster, new NovaBeds hotels included
    if (status !== "done") return;
    const t = setTimeout(() => fgRef.current?.zoomToFit(900, 50), 600);
    return () => clearTimeout(t);
  }, [status]);
  useEffect(() => {
    const fg = fgRef.current;
    if (!fg) return;
    fg.d3Force("charge")?.strength(-9);
    fg.d3Force("link")?.distance(12).strength(0.9);
  }, [graphData.nodes.length > 0]);

  useTopic("pipeline", (m) => {
    if (m.type === "start") { setStatus("running"); setStartAt(Date.now()); setC(m.payload.counters); }
    if (m.type === "progress") setC(m.payload.counters);
    if (m.type === "decision") {
      const d = m.payload;
      setLast((l) => [d, ...l].slice(0, 4));
      if (d.city !== "dubai") return;
      const nodes = graph.current.nodes;
      if (nodes.some((n) => n.id === d.record_id)) return;
      const offset = [...String(d.record_id)].reduce((hash, char) => (hash * 31 + char.charCodeAt(0)) >>> 0, 1);
      const xs = nodes.map((n) => n.x ?? 0);
      const minX = xs.length ? Math.min(...xs) : -300;
      const anchorNode = nodes.find((n) => n.cluster === d.tessera_id);
      const node: Node = {
        id: d.record_id, supplier: "S6", cluster: d.tessera_id ?? d.record_id, status: d.decision, name: d.name,
        hotel: d.cluster_name ?? anchorNode?.hotel ?? d.name, neighbourhood: anchorNode?.neighbourhood, stars: anchorNode?.stars,
        until: Date.now() + 1800, born: Date.now(), x: minX - 60, y: offset % 201 - 100,
      };
      const links = [...graph.current.links];
      if ((d.decision === "auto_merge" || d.decision === "llm") && nodes.some((n) => n.id === d.link_to)) links.push({ source: d.record_id, target: d.link_to });
      if (d.decision === "new_cluster") {
        // a brand-new hotel gets its own fixed spot inside the current constellation
        const ys = nodes.map((n) => n.y ?? 0);
        const [x0, x1, y0, y1] = [Math.min(...xs), Math.max(...xs), Math.min(...ys), Math.max(...ys)];
        node.x = node.fx = x0 + ((offset % 1000) / 1000) * (x1 - x0);
        node.y = node.fy = y0 + (((offset >>> 10) % 1000) / 1000) * (y1 - y0);
      }
      if (d.decision === "review" && anchorNode) {
        node.x = node.fx = (anchorNode.x ?? 0) + 14; node.y = node.fy = (anchorNode.y ?? 0) + 14;
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

  /* ---------------------------------------------------------------- graph drawing */
  const drawNode = useMemo(() => (node: any, ctx: CanvasRenderingContext2D, scale: number) => {
    const s6 = node.supplier === "S6";
    const lit = node.cluster === hover.current || node.cluster === focus.current;
    const dim = (hover.current || focus.current) && !lit;
    const r = (s6 ? 6 : 4.6) * (lit ? 1.35 : 1) / Math.max(1, scale / 3);
    ctx.beginPath();
    ctx.arc(node.x, node.y, r, 0, 2 * Math.PI);
    ctx.fillStyle = SUPPLIERS[node.supplier]?.color ?? "#999";
    ctx.globalAlpha = dim ? 0.25 : s6 ? 1 : 0.9;
    ctx.fill();
    ctx.lineWidth = 1 / Math.max(1, scale / 3);
    ctx.strokeStyle = "#FFFFFF";
    ctx.stroke();
    ctx.globalAlpha = 1;
    const t = Date.now();
    const ring = (rad: number, color: string, w = 1.8) => {
      ctx.beginPath(); ctx.arc(node.x, node.y, rad, 0, 2 * Math.PI); ctx.strokeStyle = color; ctx.lineWidth = w; ctx.stroke();
    };
    if (node.status === "review") {
      const k = (t % 1400) / 1400;
      ring(r + 2 + 7 * k, `rgba(201,151,0,${0.9 * (1 - k)})`, 2);
    } else if (node.status === "llm" && node.until > t) {
      ring(r + 3, "rgba(107,63,212,.95)");
    } else if (s6 && node.until > t) {
      ring(r + 4 * ((node.until - t) / 1800), "rgba(232,89,12,.7)", 1.6);
    }
  }, []);

  const drawHulls = (ctx: CanvasRenderingContext2D, scale: number) => {
    const by: Record<string, Node[]> = {};
    for (const n of graph.current.nodes) (by[n.cluster] ??= []).push(n);
    ctx.save();
    for (const k in by) {
      const ns = by[k];
      if (ns.some((n) => n.supplier === "S6" && (n.until ?? 0) > Date.now())) continue;
      let cx = 0, cy = 0;
      for (const n of ns) { cx += n.x ?? 0; cy += n.y ?? 0; }
      cx /= ns.length; cy /= ns.length;
      let r = 0;
      for (const n of ns) r = Math.max(r, Math.hypot((n.x ?? 0) - cx, (n.y ?? 0) - cy));
      if (r > 45) continue;
      const lit = k === hover.current || k === focus.current;
      if (ns.length > 1 || lit) {
        ctx.beginPath();
        ctx.arc(cx, cy, r + 8, 0, 2 * Math.PI);
        ctx.fillStyle = lit ? "rgba(242,166,2,0.20)" : "rgba(1,76,142,0.07)";
        ctx.fill();
        if (lit) { ctx.lineWidth = 1.5 / scale * 2; ctx.strokeStyle = "rgba(242,166,2,0.9)"; ctx.stroke(); }
      }
      // hotel names appear once zoomed in far enough to read them (or always for the highlighted hotel)
      if ((scale > 2.4 && ns.length > 1) || lit) {
        const fs = (lit ? 17 : 14) / scale; // constant on-screen size whatever the zoom
        ctx.font = `${lit ? 700 : 600} ${fs}px "Inter Variable", system-ui, sans-serif`;
        ctx.textAlign = "center";
        ctx.textBaseline = "top";
        const label = ns[0].hotel ?? "";
        const y = cy + r + 10;
        ctx.lineWidth = 3 / scale;
        ctx.strokeStyle = "rgba(255,255,255,0.95)";
        ctx.strokeText(label, cx, y);
        ctx.fillStyle = lit ? "#013A6D" : "#3F4B5E";
        ctx.fillText(label, cx, y);
      }
    }
    ctx.restore();
  };

  const label = (n: Node) => {
    const sup = SUPPLIERS[n.supplier]?.name ?? n.supplier;
    const members = graph.current.nodes.filter((x) => x.cluster === n.cluster);
    const sups = [...new Set(members.map((x) => SUPPLIERS[x.supplier]?.name ?? x.supplier))];
    return `<div style="font-family:Inter Variable,system-ui;padding:8px 10px;max-width:320px">
      <div style="font-weight:700;font-size:15px;color:#fff">${esc(n.hotel)}</div>
      <div style="font-size:13px;opacity:.85">${esc(n.neighbourhood ?? "Dubai")}${n.stars ? " · " + "★".repeat(n.stars) : ""}</div>
      <div style="margin-top:6px;font-size:13px"><b>${esc(sup)}</b> listing: “${esc(n.name)}”</div>
      <div style="margin-top:4px;font-size:13px;opacity:.85">One hotel from ${members.length} supplier listing${members.length > 1 ? "s" : ""}: ${esc(sups.join(", "))}</div>
      ${n.cluster.startsWith("TS-") ? '<div style="margin-top:6px;font-size:12px;color:#F2A602;font-weight:600">Click to open in the Inspector</div>' : ""}
    </div>`;
  };

  const zoomBy = (f: number) => { const fg = fgRef.current; if (fg) fg.zoom(fg.zoom() * f, 300); };
  const findOnMap = () => {
    const q = query.trim().toLowerCase();
    if (!q) { focus.current = null; return; }
    const hit = graph.current.nodes.find((n) => (n.hotel ?? "").toLowerCase().includes(q)) ??
      graph.current.nodes.find((n) => (n.name ?? "").toLowerCase().includes(q));
    if (!hit) { showToast(`No hotel on the map matches “${query}”`); return; }
    focus.current = hit.cluster;
    fgRef.current?.centerAt(hit.x, hit.y, 700);
    fgRef.current?.zoom(5, 700);
  };

  const decided = c ? c.clustered + c.review : 0;
  const elapsed = status === "done" ? c?.elapsed ?? 0 : startAt ? (now - startAt) / 1000 : 0;
  const clock = `${String(Math.floor(elapsed / 60)).padStart(2, "0")}:${String(Math.floor(elapsed % 60)).padStart(2, "0")}`;
  const feed = feedState?.feed;
  const risk = doneInfo?.risk;

  if (!feed || !g) return <Skeleton className="w-full h-full" />;
  const stages = [
    { label: "Parsed", value: c?.parsed ?? 0, sub: `of ${groupIN(feed.hotels)} records` },
    { label: "Candidates", value: c?.candidates ?? 0, sub: c ? `recall ${pct(c.recall ?? 0, 1)} · reduction ${pct(c.reduction ?? 0, 1)}` : "location · name · meaning · photos" },
    { label: "Scored", value: c?.scored ?? 0, sub: "learned matcher, calibrated" },
    { label: "Decided", value: decided, sub: c ? `${c.auto_merge} auto · ${c.llm} LLM · ${c.review} review · ${c.new_cluster} new` : "within the guaranteed error budget" },
    { label: "Clustered", value: c?.clustered ?? 0, sub: "one supplier per hotel, no contradictions" },
  ];
  const stats = [
    { label: "Auto-merged", v: decided ? c.auto_merge / decided : 0, tone: "text-[color:var(--sage-ink)]", hint: "matched to an existing hotel" },
    { label: "Sent to LLM", v: decided ? c.llm / decided : 0, tone: "text-iris", hint: "hard cases only" },
    { label: "Human review", v: decided ? c.review / decided : 0, tone: "text-[color:var(--amber-ink)]", hint: "abstained, with a reason" },
  ];
  return (
    <div className="h-full flex flex-col">
      <SceneHeader headline="A new supplier, mapped in under a minute." subline="NovaBeds has never been seen before. Every decision below is computed live: find candidates, score, route within the error budget, cluster." />
      <div className="grid grid-cols-5 gap-3">
        {stages.map((s, i) => (
          <Card key={s.label} {...{ initial: { opacity: 0, y: 8 }, animate: { opacity: 1, y: 0 }, transition: { ...T, delay: i * 0.04 } }} className="px-5 py-3 relative">
            <Caption>{String(i + 1).padStart(2, "0")} · {s.label}</Caption>
            <div className="font-semibold tabular text-[32px] leading-tight text-ink"><Ticker value={s.value} format={(v) => groupIN(v)} /></div>
            <div className="text-[14px] text-ink-3 truncate">{s.sub}</div>
            {i < 4 && <div className="absolute -right-3 top-1/2 -translate-y-1/2 text-lagoon z-10 text-[20px] font-bold">›</div>}
          </Card>
        ))}
      </div>
      <div className="mt-4 flex gap-5 flex-1 min-h-0">
        {/* left: the feed, live stats, latest decisions */}
        <div className="w-[330px] flex flex-col gap-3 min-h-0">
          <motion.div onDragOver={(e) => { e.preventDefault(); setDrag(true); }} onDragLeave={() => setDrag(false)}
            onDrop={(e) => { e.preventDefault(); setDrag(false); start(); }} onClick={start}
            animate={{ scale: drag ? 1.02 : 1 }} transition={T}
            className="rounded-card border-2 border-dashed p-4 cursor-pointer bg-surface"
            style={{ borderColor: status === "idle" ? SUPPLIERS.S6.color : "var(--line)" }}>
            <div className="flex items-center justify-between"><SupplierChip code="S6" /><span className="text-[14px] text-ink-3">{feed.cities.length} cities · never seen before</span></div>
            <div className="text-[17px] text-ink mt-2 font-semibold tabular">{groupIN(feed.hotels)} hotels · {groupIN(feed.rooms)} rooms</div>
            <div className="mt-3">{status === "idle"
              ? <span className="inline-flex items-center gap-2 rounded-full bg-saffron text-ink px-3.5 py-1.5 text-[15px] font-semibold">Click to onboard NovaBeds <Kbd>O</Kbd></span>
              : <span className="text-[15px] font-medium text-lagoon">{status === "running" ? "Onboarding live…" : "NovaBeds is live"}</span>}</div>
          </motion.div>
          <div className="grid grid-cols-2 gap-3">
            <Card className="p-4">
              <Caption>Elapsed</Caption>
              <div className="font-semibold tabular text-[34px] leading-none mt-1">{clock}</div>
              <div className="text-[13px] text-ink-3 mt-1">real computation</div>
            </Card>
            {stats.map((s) => (
              <Card key={s.label} className="p-4">
                <Caption>{s.label}</Caption>
                <div className={`font-semibold tabular text-[34px] leading-none mt-1 ${s.tone}`}><Ticker value={s.v * 100} format={(v) => `${v.toFixed(1)}%`} /></div>
                <div className="text-[13px] text-ink-3 mt-1">{s.hint}</div>
              </Card>
            ))}
          </div>
          <Card className="p-4 flex-1 min-h-0 overflow-hidden">
            <Caption>Latest decisions</Caption>
            <div className="mt-2 space-y-2.5">
              {/* plain list: decisions arrive every ~40 ms, faster than exit animations can finish */}
              {last.map((d) => (
                <motion.div key={d.record_id} initial={{ opacity: 0, y: -6 }} animate={{ opacity: 1, y: 0 }} transition={T} className="text-[15px]">
                  <div className="truncate text-ink font-medium">{d.name}</div>
                  <div className="flex items-center gap-1.5 mt-0.5">
                    <Chip variant={d.decision === "auto_merge" ? "sage" : d.decision === "llm" ? "iris" : d.decision === "review" ? "amber" : "lagoon"}>
                      {d.decision === "auto_merge" ? "auto-merged" : d.decision === "llm" ? "LLM" : d.decision === "review" ? "review" : "new hotel"}
                    </Chip>
                    <span className="text-ink-3 truncate text-[14px]">{d.cluster_name ?? d.city}</span>
                  </div>
                </motion.div>
              ))}
              {!last.length && <div className="text-[14px] text-ink-3">Decisions stream here as NovaBeds is mapped.</div>}
            </div>
          </Card>
        </div>

        {/* the supply graph: large and explorable */}
        <Card className="flex-1 relative overflow-hidden dotgrid">
          <div ref={boxRef} className="absolute inset-0">
            <ForceGraph2D ref={fgRef} graphData={graphData} width={box.w} height={box.h} backgroundColor="rgba(0,0,0,0)"
              nodeCanvasObject={drawNode} nodeCanvasObjectMode={() => "replace"} onRenderFramePre={drawHulls}
              nodeLabel={(n: any) => label(n)} nodeRelSize={6}
              onNodeHover={(n: any) => { hover.current = n?.cluster ?? null; if (boxRef.current) boxRef.current.style.cursor = n ? "pointer" : "grab"; }}
              onNodeClick={(n: any) => { if (n?.cluster?.startsWith("TS-")) useApp.getState().openInspector(n.cluster); }}
              onNodeDragEnd={(n: any) => { n.fx = n.x; n.fy = n.y; }}
              linkColor={() => "rgba(1,76,142,0.22)"} linkWidth={0.8}
              enableNodeDrag enableZoomInteraction enablePanInteraction minZoom={0.4} maxZoom={14}
              cooldownTime={4000} d3VelocityDecay={0.35} warmupTicks={60}
              onEngineStop={() => {
                // fit once real data is on the canvas (not the empty first render), then hold the camera still
                if (!fitted.current && graph.current.nodes.length) {
                  fitted.current = true;
                  // pin the settled constellation: streamed decisions reheat the simulation ~25x/s, and without
                  // pins the clusters keep repelling each other out of frame. Only NovaBeds nodes move from here on.
                  for (const n of graph.current.nodes) { n.fx = n.x; n.fy = n.y; }
                  fgRef.current?.zoomToFit(600, 50);
                }
              }} />
          </div>
          {/* map controls */}
          {!RECORD_MODE && (
            <div className="absolute right-3 top-3 flex items-center gap-2">
              <form onSubmit={(e) => { e.preventDefault(); findOnMap(); }} className="flex items-center gap-2 rounded-full bg-surface border border-line shadow-card pl-3 pr-1 py-1">
                <Search size={15} className="text-ink-3" />
                <input value={query} onChange={(e) => { setQuery(e.target.value); if (!e.target.value) focus.current = null; }}
                  placeholder="Find a hotel on the map" className="w-[220px] bg-transparent outline-none text-[15px] text-ink placeholder:text-ink-3" />
                <button type="submit" className="rounded-full bg-lagoon text-white text-[13px] font-semibold px-3 py-1">Find</button>
              </form>
              <div className="flex rounded-full bg-surface border border-line shadow-card overflow-hidden">
                <button onClick={() => zoomBy(1.5)} className="px-2.5 py-2 hover:bg-surface-2" title="Zoom in"><Plus size={16} /></button>
                <button onClick={() => zoomBy(1 / 1.5)} className="px-2.5 py-2 hover:bg-surface-2 border-l border-line" title="Zoom out"><Minus size={16} /></button>
                <button onClick={() => { focus.current = null; setQuery(""); fgRef.current?.zoomToFit(600, 50); }} className="px-2.5 py-2 hover:bg-surface-2 border-l border-line" title="Fit everything"><Maximize2 size={16} /></button>
              </div>
            </div>
          )}
          {/* legend */}
          <div className="absolute left-3 bottom-3 right-3 flex items-end justify-between gap-4 pointer-events-none">
            <div className="rounded-2xl bg-surface/95 border border-line shadow-card px-4 py-3">
              <div className="text-[13px] font-semibold text-ink mb-1.5">Each dot is one supplier listing · each tinted circle is one real hotel</div>
              <div className="flex gap-x-3 gap-y-1.5 flex-wrap max-w-[760px]">
                {["S1", "S2", "S3", "S4", "S5", "S6"].map((s) => <SupplierChip key={s} code={s} />)}
              </div>
              <div className="flex gap-4 mt-2 text-[13px] text-ink-2">
                <span className="flex items-center gap-1.5"><span className="w-3 h-3 rounded-full border-2" style={{ borderColor: "#E8590C" }} />arriving NovaBeds listing</span>
                <span className="flex items-center gap-1.5"><span className="w-3 h-3 rounded-full border-2" style={{ borderColor: "#C99700" }} />sent to human review</span>
                <span className="flex items-center gap-1.5"><span className="w-3 h-3 rounded-full border-2" style={{ borderColor: "#6B3FD4" }} />LLM consulted</span>
              </div>
            </div>
            {!RECORD_MODE && (
              <div className="rounded-full bg-surface/95 border border-line shadow-card px-3 py-1.5 text-[13px] text-ink-2 flex items-center gap-2">
                <MousePointerClick size={14} className="text-lagoon" />Hover for details · scroll to zoom · drag to pan · click a hotel to inspect it
              </div>
            )}
          </div>
          <div className="absolute left-4 top-3 text-[13px] text-ink-3 pointer-events-none">Dubai shown ({groupIN(graphData.nodes.length)} listings) · counters cover all {feed.cities.length} cities</div>
        </Card>
      </div>
      <AnimatePresence>
        {status === "done" && doneInfo && (
          <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={T}
            className="absolute left-1/2 -translate-x-1/2 bottom-12 bg-sage-soft border border-sage text-[color:var(--sage-ink)] rounded-full px-7 py-3 text-[18px] font-semibold shadow-card z-30">
            NovaBeds live in {Math.round(doneInfo.counters.elapsed)} s. {doneInfo.counters.violations} consistency violations. {risk?.certifiable && risk?.held && risk.test_merges > 0 ? `Certified false-merge limit ${(doneInfo.alpha * 100).toFixed(1)}% (${Math.round((1 - risk.delta) * 100)}% confidence).` : risk?.certifiable && !risk?.held ? "Held-out false merges exceeded the target." : "No verified held-out guarantee for this setting."}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
