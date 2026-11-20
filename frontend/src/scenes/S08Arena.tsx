import { AnimatePresence, motion } from "framer-motion";
import { QRCodeSVG } from "qrcode.react";
import { useEffect, useRef, useState } from "react";
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Scatter, XAxis, YAxis, ZAxis, ComposedChart } from "recharts";
import { Button, Caption, Card, Chip, Cite, Kbd, SceneHeader, Skeleton, SupplierChip, T, Toggle, cx, rise } from "../design/primitives";
import { useApp } from "../app/store";
import { api, post } from "../lib/api";
import { formatINR, ms, pct } from "../lib/format";
import { useFetch, useHotkeys } from "../lib/hooks";
import { useTopic } from "../lib/ws";

export default function Arena() {
  const [view, setView] = useState<"A" | "B">("A");
  useHotkeys({ a: () => setView("A"), b: () => setView("B") });
  const { data: bench } = useFetch<any>("/arena/benchmark");
  const simulated = !!bench?.baseline?.simulated;
  const sublineA = simulated
    ? "Same candidate pairs, same held-out hotels. LedgerBot is measured; the LLM-only column is a simulated profile."
    : "Same candidate pairs, same held-out hotels. Every number below is measured.";
  return (
    <div className="h-full flex flex-col">
      <SceneHeader headline="LedgerBot vs an LLM-only pipeline." subline={view === "A" ? sublineA : "Judges vs Machine: vote on your phone."}
        right={<Toggle value={view} onChange={setView} options={[{ value: "A", label: "Benchmark" }, { value: "B", label: "Judges vs Machine" }]} />} />
      <div className="flex-1 min-h-0">{view === "A" ? <Board /> : <Voting />}</div>
    </div>
  );
}

function Board() {
  const { data } = useFetch<any>("/arena/benchmark");
  const { data: corners } = useFetch<any[]>("/arena/corner-cases");
  const [ci, setCi] = useState(0);
  useEffect(() => {
    if (!corners?.length) return;
    const id = setInterval(() => setCi((i) => (i + 1) % corners.length), 4000);
    return () => clearInterval(id);
  }, [corners]);
  if (!data) return <Skeleton className="w-full h-full" />;
  const t = data.tessera, b = data.baseline;
  const sim = !!b?.simulated;
  const rows: [string, string, string, string?][] = [
    ["Hotel pair F1", b ? (b.hotel_f1 ?? 0).toFixed(3) : "—", `${t.hotel_f1.toFixed(3)}`, `${pct(t.hotel_coverage, 1)} decided automatically · ${t.abstained} abstained`],
    ["Room-variant F1 (offer corner cases)", b?.room_f1 != null ? b.room_f1.toFixed(3) : "—", t.room_f1.toFixed(3)],
    ["Consistency violations", b ? String(b.consistency_violations) : "—", String(t.consistency_violations), "whole world"],
    ["Largest wrong cluster size", b ? String(b.largest_wrong_cluster) : "—", String(t.largest_wrong_cluster), "whole world"],
    ["Cost per 1,000 pairs", b ? `${formatINR(b.cost_per_1000_inr, { decimals: 2 })}${sim ? " est." : ""}` : "—", `${formatINR(t.cost_per_1000_inr, { decimals: 2 })}${t.cost_estimated ? " est." : ""}`, "LLM only on the uncertain band"],
    ["p95 latency per pair", b?.latency_s ? `${b.latency_s.p95.toFixed(1)} s${sim ? " est." : ""}` : "—", ms(t.latency_ms.p95), "features + LightGBM on CPU"],
    ["Calibrated? Guarantee?", b ? "stated confidence ≠ accuracy" : "—", !t.guarantee.certifiable ? "No certified auto-merge threshold" : !t.guarantee.test_merges ? "No held-out merges" : `${t.guarantee.held ? "✓ held" : "✗ violated"} at α = ${(t.guarantee.alpha * 100).toFixed(1)}%`],
  ];
  const rel = [
    ...t.reliability.map((r: any) => ({ conf: r.confidence * 100, tessera: r.accuracy * 100 })),
  ];
  const llmRel = (b?.reliability ?? []).map((r: any) => ({ conf: r.confidence * 100, llm: r.accuracy * 100 }));
  const corner = corners?.[ci];
  return (
    <div className="grid grid-cols-[minmax(0,1fr)_520px] gap-6 h-full">
      <div className="flex flex-col gap-4 min-h-0">
        <Card {...rise(0)} className="overflow-hidden shrink-0">
          <div className="grid grid-cols-[1.3fr_1fr_1fr] px-6 h-12 items-center bg-surface-2 text-[13px] font-medium">
            <span className="text-ink-3 uppercase tracking-[0.08em] text-[12px]">Metric · {data.n_hotel} hotel pairs · {data.n_room} room pairs</span>
            <span className="text-iris flex items-center gap-2">
              {sim ? <>LLM-only (pairwise) <Chip variant="iris">SIMULATED</Chip></> : <>LLM-only ({data.baseline_model}, pairwise)</>}
            </span>
            <span className="text-lagoon">LedgerBot</span>
          </div>
          {rows.map(([m, l, r, note], i) => (
            <motion.div key={m} {...rise(i + 1)} className="grid grid-cols-[1.3fr_1fr_1fr] px-6 py-3 items-center border-t border-line">
              <span className="text-[16px]">{m}</span>
              <span className="font-mono text-[20px] text-iris">{l}</span>
              <span><span className="font-mono text-[20px] text-lagoon">{r}</span>{note && <div className="text-[12px] text-ink-3">{note}</div>}</span>
            </motion.div>
          ))}
        </Card>
        {!b && (
          <Card className="p-4 border-iris bg-iris-soft/60">
            <div className="text-[16px] text-iris font-medium">Baseline not yet run: <code className="font-mono">make baseline</code></div>
            <div className="text-[13px] text-ink-2 mt-1">The LLM-only column is never estimated or faked. Add ANTHROPIC_API_KEY to .env and run it once ({data.n_hotel} + {data.n_room} calls to {data.baseline_model}); results are cached with a timestamp.</div>
          </Card>
        )}
        {b && sim && (
          <div className="text-[13px] text-ink-2 shrink-0 leading-snug">
            <span className="text-iris font-medium">LLM-only column is a simulated profile, not a live run:</span> stated error rates for a zero-shot pairwise LLM
            ({pct(b.profile?.hotel_hard_negative_false_merge ?? 0, 0)} of sister hotels merged, {pct(b.profile?.room_diff_terms_false_merge ?? 0, 0)} of breakfast-vs-room-only
            offers merged) on the hardest-looking pairs; F1, violations and calibration computed from those answers; cost and latency estimated.
          </div>
        )}
        {b && !sim && <div className="text-[13px] text-ink-3">Baseline run on {b.run_at}, model {b.model}. <Cite>Entity matching with LLMs (Peeters, Steiner &amp; Bizer, EDBT 2025)</Cite></div>}
        {corner && (
          <Card className="p-5">
            <Caption>Corner case · where the {sim ? "simulated " : ""}LLM-only pipeline was wrong</Caption>
            <AnimatePresence mode="wait">
              <motion.div key={ci} initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -20 }} transition={T} className="mt-2">
                <div className="grid grid-cols-2 gap-4 text-[14px]">
                  {[corner.a, corner.b].map((x: any, k: number) => (
                    <div key={k} className="rounded-xl bg-surface-2 p-3">
                      <SupplierChip code={x.supplier} short /> <span className="ml-1">{x.name ?? x.room_name}</span>
                      {x.board_raw && <div className="font-mono text-[12px] text-ink-3 mt-1">{x.board_raw} · {x.cancellation_raw}</div>}
                    </div>
                  ))}
                </div>
                <div className="mt-3 flex gap-3 text-[14px]">
                  <Chip variant="neutral">truth: {corner.truth.replaceAll("_", " ")}</Chip>
                  <Chip variant="iris">LLM: {corner.llm.same ? "same" : "different"} ({corner.llm.confidence}% sure)</Chip>
                  <Chip variant="lagoon">LedgerBot: {corner.tessera.answer}{corner.tessera.p != null ? ` (p = ${corner.tessera.p.toFixed(2)})` : ""}</Chip>
                </div>
              </motion.div>
            </AnimatePresence>
          </Card>
        )}
      </div>
      <Card {...rise(2)} className="p-5 flex flex-col">
        <Caption>Reliability diagram · stated confidence vs actual accuracy</Caption>
        <div className="flex gap-4 mt-2 text-[13px]">
          <span className="flex items-center gap-2"><span className="w-4 h-0.5 bg-lagoon" />LedgerBot (held-out)</span>
          <span className="flex items-center gap-2"><span className="w-4 h-0.5 bg-iris" />LLM-only {b ? (sim ? "(simulated)" : "") : "(not run)"}</span>
          <span className="flex items-center gap-2"><span className="w-4 h-0.5 border-t border-dashed border-ink-3" />perfect</span>
        </div>
        <div className="flex-1 mt-3">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart margin={{ top: 10, right: 16, left: 0, bottom: 10 }}>
              <CartesianGrid stroke="var(--line)" />
              <XAxis dataKey="conf" type="number" domain={[50, 100]} tickFormatter={(v) => `${v}%`} tick={{ fill: "var(--ink-3)", fontSize: 12 }} stroke="var(--line)" />
              <YAxis type="number" domain={[50, 100]} tickFormatter={(v) => `${v}%`} tick={{ fill: "var(--ink-3)", fontSize: 12 }} stroke="var(--line)" width={44} />
              <Line data={[{ conf: 50, d: 50 }, { conf: 100, d: 100 }]} dataKey="d" stroke="var(--ink-3)" strokeDasharray="4 4" dot={false} isAnimationActive={false} />
              <Line data={rel} dataKey="tessera" stroke="var(--lagoon)" strokeWidth={3} dot={{ r: 4, fill: "var(--lagoon)" }} isAnimationActive={false} />
              {llmRel.length > 0 && <Line data={llmRel} dataKey="llm" stroke="var(--iris)" strokeWidth={3} dot={{ r: 4, fill: "var(--iris)" }} isAnimationActive={false} />}
            </LineChart>
          </ResponsiveContainer>
        </div>
        <div className="text-[12px] text-ink-3 mt-2">x: confidence in the predicted answer · y: share correct. On the diagonal = says what it knows.</div>
        {t.reliability.length > 0 && (
          <div className="text-[12px] text-ink-2 mt-1">
            Pairs per point · <span className="text-lagoon">LedgerBot</span> {t.reliability.map((r: any) => r.n.toLocaleString("en-IN")).join(" · ")}
            {b?.reliability?.length ? <> · <span className="text-iris">LLM-only</span> {b.reliability.map((r: any) => r.n.toLocaleString("en-IN")).join(" · ")}</> : null}
          </div>
        )}
      </Card>
    </div>
  );
}

const ANSWER_LABEL: Record<string, string> = { same: "Same", different: "Different", same_room_diff_offer: "Same room, different offer", abstain: "Abstain → review" };

function Voting() {
  const [sess, setSess] = useState<any>(null);
  const [pair, setPair] = useState<any>(null);
  const [tally, setTally] = useState<any>(null);
  const [reveal, setReveal] = useState<any>(null);
  const [learned, setLearned] = useState<any>(null);
  const [learning, setLearning] = useState(false);
  const [now, setNow] = useState(Date.now());
  const connected = useApp((s) => s.wsConnected);
  const showToast = useApp((s) => s.showToast);
  const advancing = useRef(false);
  const revision = useRef(0);
  useEffect(() => {
    let active = true;
    const version = revision.current;
    post("/vote/session").then((s) => {
      if (!active) return;
      setSess((old: any) => version === revision.current ? s : { ...s, ...old, url: s.url });
      if (version !== revision.current) return;
      setPair(s.pair); setTally(s.tally); setLearned(s.learned); setReveal(s.reveal ?? null);
    }).catch(() => { if (active) showToast("Could not load the voting session.", "clay"); });
    return () => { active = false; };
  }, [connected, showToast]);
  useEffect(() => { const id = setInterval(() => setNow(Date.now()), 200); return () => clearInterval(id); }, []);
  useTopic("vote", (m) => {
    revision.current++;
    if (m.type === "pair") { setPair(m.payload); setSess((s: any) => ({ ...s, current: m.payload.idx })); setReveal(null); setTally({ counts: {}, n: 0 }); }
    if (m.type === "tally") setTally(m.payload);
    if (m.type === "reveal") { setReveal(m.payload); api("/vote/state").then((s) => setSess((old: any) => ({ ...old, ...s }))).catch(() => showToast("Could not refresh the leaderboard.", "clay")); }
  });
  const advance = async () => {
    if (advancing.current || !sess || (pair && reveal && pair.idx + 1 >= pair.total)) return;
    advancing.current = true;
    try {
      if (pair && !reveal) setReveal(await post("/vote/reveal"));
      else {
        const next = await post("/vote/next");
        if (next.idx != null) { setPair(next); setReveal(null); }
      }
    } catch { showToast("Could not advance the voting round.", "clay"); }
    finally { advancing.current = false; }
  };
  const learn = async () => {
    if (learning || !reveal) return;
    setLearning(true);
    try { setLearned(await post("/vote/learn")); }
    catch { showToast("Retraining failed. Try again.", "clay"); }
    finally { setLearning(false); }
  };
  useHotkeys({ " ": advance, l: learn });
  const left = pair ? Math.max(0, Math.min(pair.countdown, pair.opened_at + pair.countdown - now / 1000)) : 0;
  const counts = tally?.counts ?? {};
  const n = tally?.n ?? 0;
  const opts = ["same", "different", "same_room_diff_offer"];
  const lb = reveal?.leaderboard ?? sess?.leaderboard ?? [];
  const twist = sess?.twist;
  return (
    <div className="grid grid-cols-[360px_minmax(0,1fr)_400px] gap-6 h-full">
      <Card className="p-6 flex flex-col items-center">
        <Caption>Scan to vote</Caption>
        {sess ? <div className="mt-4 p-3 bg-white rounded-2xl border border-line"><QRCodeSVG value={sess.url} size={260} fgColor="#15171C" /></div> : <Skeleton className="w-[280px] h-[280px] mt-4" />}
        <div className="mt-3 font-mono text-[13px] text-ink-2 break-all text-center">{sess?.url}</div>
        <Button className="mt-auto" onClick={advance} disabled={!sess || !!(reveal && pair?.idx + 1 >= pair?.total)} kbd="Space">
          {!pair ? "Start voting" : !reveal ? "Reveal answer" : pair.idx + 1 < pair.total ? "Next pair" : "Voting complete"}
        </Button>
      </Card>
      <div className="flex flex-col gap-4 min-h-0">
        {!pair ? (
          <div className="flex-1 rounded-card border border-dashed border-line flex items-center justify-center text-[20px] text-ink-3">Press Space to push the first pair to every phone.</div>
        ) : (
          <>
            <div className="flex items-center justify-between">
              <Caption>Pair {pair.idx + 1} of {pair.total} · {pair.kind === "room" ? "two rate offers, same hotel" : "two hotel listings"}</Caption>
              {!reveal && <span className="font-mono text-[28px]" style={{ color: left < 3 ? "var(--clay)" : "var(--ink)" }}>{left.toFixed(0)}s</span>}
            </div>
            <div className="grid grid-cols-2 gap-4">
              {[pair.a, pair.b].map((x: any, k: number) => (
                <Card key={k} className="p-4">
                  <SupplierChip code={x.supplier} />
                  <div className="text-[18px] font-medium mt-2">{x.name}</div>
                  <div className="text-[13px] text-ink-2 mt-1 font-mono">{x.address ?? "—"}</div>
                  <div className="text-[13px] text-ink-2 font-mono">{x.phone ?? "—"}</div>
                  <div className="text-[13px] text-ink-3 font-mono">{x.coords}{x.stars ? ` · ${x.stars}★` : ""}</div>
                </Card>
              ))}
            </div>
            <Card className="p-5">
              <Caption>Live votes · {n} phones</Caption>
              <div className="mt-3 space-y-3">
                {opts.map((o) => {
                  const v = counts[o] ?? 0;
                  const isTruth = reveal?.truth === o;
                  return (
                    <div key={o} className="flex items-center gap-3">
                      <span className={cx("w-[230px] text-[15px]", isTruth && "font-semibold text-[color:var(--sage-ink)]")}>{ANSWER_LABEL[o]}{isTruth && " ✓"}</span>
                      <div className="flex-1 h-6 rounded-full bg-surface-2 overflow-hidden">
                        <div className="h-full rounded-full transition-all duration-300" style={{ width: `${n ? (v / n) * 100 : 0}%`, background: isTruth ? "var(--sage)" : "var(--lagoon)" }} />
                      </div>
                      <span className="w-10 text-right font-mono">{v}</span>
                    </div>
                  );
                })}
              </div>
            </Card>
            <AnimatePresence>
              {reveal && (
                <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={T} className="grid grid-cols-3 gap-3">
                  <Card className="p-4"><Caption>Truth</Caption><div className="text-[18px] mt-1 font-medium">{ANSWER_LABEL[reveal.truth]}</div><div className="text-[12px] text-ink-3 mt-1">humans avg {reveal.human_avg_ms ? ms(reveal.human_avg_ms) : "—"}</div></Card>
                  <Card className="p-4 border-lagoon"><Caption>LedgerBot</Caption><div className="text-[18px] mt-1 font-medium text-lagoon">{ANSWER_LABEL[reveal.tessera.answer]}</div>
                    <div className="text-[12px] text-ink-3 mt-1">{reveal.tessera.p != null ? `p = ${reveal.tessera.p.toFixed(3)} · ` : ""}{ms(reveal.tessera.ms)}</div></Card>
                  <Card className="p-4"><Caption>LLM-only ({reveal.baseline?.simulated ? "simulated" : "cached"})</Caption><div className="text-[18px] mt-1 font-medium text-iris">{reveal.baseline ? `${ANSWER_LABEL[reveal.baseline.answer]} (${reveal.baseline.confidence}%)` : "not run"}</div></Card>
                </motion.div>
              )}
            </AnimatePresence>
          </>
        )}
      </div>
      <div className="flex flex-col gap-4">
        <Card className="p-5">
          <Caption>Leaderboard</Caption>
          <div className="mt-2">
            {lb.slice(0, 8).map((r: any, i: number) => (
              <motion.div layout key={r.name} transition={T} className="flex items-center justify-between py-1.5 border-b border-line/60 text-[15px]">
                <span className={cx(r.kind === "tessera" && "text-lagoon font-medium", r.kind === "llm" && "text-iris font-medium")}>{i + 1}. {r.name}</span>
                <span className="font-mono">{r.score}</span>
              </motion.div>
            ))}
          </div>
        </Card>
        <Card className="p-5">
          <Caption>Twist</Caption>
          <div className="text-[16px] mt-2">Pairs where you disagreed with each other → LedgerBot abstained on <span className="font-mono text-[color:var(--amber-ink)]">{twist?.tessera_abstained ?? 0}/{twist?.disagreed ?? 0}</span> of them.</div>
          <Button className="mt-4" onClick={learn} disabled={learning || !reveal} kbd="L">{learning ? "Retraining…" : "Learn from your votes"}</Button>
          {learned?.reason && <p className="mt-3 text-sm text-ink-2">{learned.reason}</p>}
          {learned && learned.labels_added > 0 && (
            <div className="mt-3 text-[15px]">
              <span className="text-ink-2">+{learned.labels_added} labels · retrained in {learned.seconds}s</span>
              <div className="font-mono text-[20px] mt-1">Review band: {learned.review_before} → <span className="text-lagoon">{learned.review_after}</span> pairs</div>
              <div className="text-[12px] text-ink-3">{pct(learned.review_before_pct, 3)} → {pct(learned.review_after_pct, 3)} of candidate pairs · thresholds re-certified</div>
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}
