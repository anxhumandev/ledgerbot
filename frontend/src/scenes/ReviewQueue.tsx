import { AnimatePresence, motion } from "framer-motion";
import { Check, CornerUpLeft, SkipForward, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Caption, Card, Chip, Cite, Explain, Kbd, ProbBar, Skeleton, SupplierChip, T, cx } from "../design/primitives";
import { api, post } from "../lib/api";
import { useHotkeys } from "../lib/hooks";

const STATE_STYLE: Record<string, string> = {
  same: "bg-sage-soft text-[color:var(--sage-ink)]",
  similar: "bg-sage-soft/60 text-[color:var(--sage-ink)]",
  different: "bg-clay-soft text-[color:var(--clay-ink)]",
  missing: "bg-surface-2 text-ink-3",
};
const STATE_LABEL: Record<string, string> = { same: "match", similar: "close", different: "differs", missing: "missing" };

/** The human-in-the-loop console: the pairs LedgerBot would not decide on its own, most uncertain first. */
export default function ReviewQueue() {
  const [data, setData] = useState<any>(null);
  const [i, setI] = useState(0);
  const [history, setHistory] = useState<string[]>([]);
  const [flash, setFlash] = useState<string | null>(null);
  const shownAt = useRef(Date.now());

  const load = () => api("/review/queue?limit=40").then((d) => { setData(d); setI(0); shownAt.current = Date.now(); });
  useEffect(() => { load(); }, []);

  const item = data?.items?.[i];
  const decide = async (verdict: "same" | "different" | "skip") => {
    if (!item) return;
    const seconds = (Date.now() - shownAt.current) / 1000;
    setFlash(verdict);
    setTimeout(() => setFlash(null), 350);
    const stats = await post("/review/decide", { pair_id: item.pair_id, verdict, seconds });
    setHistory((h) => [...h, item.pair_id]);
    setData((d: any) => ({ ...d, stats }));
    if (i + 1 < data.items.length) { setI(i + 1); shownAt.current = Date.now(); } else load();
  };
  const undo = async () => {
    const last = history[history.length - 1];
    if (!last) return;
    const stats = await post("/review/undo", { pair_id: last, verdict: "skip" });
    setHistory((h) => h.slice(0, -1));
    setData((d: any) => ({ ...d, stats }));
    if (i > 0) setI(i - 1);
    shownAt.current = Date.now();
  };
  useHotkeys({ s: () => decide("same"), d: () => decide("different"), k: () => decide("skip"), u: undo });

  if (!data) return <Skeleton className="w-full h-full" />;
  const st = data.stats;
  const done = st.total - st.remaining;
  return (
    <div className="h-full flex flex-col gap-4">
      {/* progress strip */}
      <Card className="px-5 py-3 flex items-center gap-6">
        <div>
          <Caption>Human review queue</Caption>
          <div className="text-[15px] text-ink-2 mt-0.5">Pairs LedgerBot refused to decide alone, <b className="text-ink">most uncertain first</b>. Each decision becomes a gold label for the next retrain.</div>
        </div>
        <div className="ml-auto flex items-center gap-6 text-[15px]">
          <div className="w-[260px]">
            <div className="flex justify-between text-[13px] text-ink-3 mb-1"><span>{done} of {st.total} handled</span><span>{st.remaining} left</span></div>
            <div className="h-2.5 rounded-full bg-surface-2 overflow-hidden"><div className="h-full bg-lagoon rounded-full transition-all duration-300" style={{ width: `${st.total ? (done / st.total) * 100 : 0}%` }} /></div>
          </div>
          <Stat2 label="Same" value={st.same} tone="text-[color:var(--sage-ink)]" />
          <Stat2 label="Different" value={st.different} tone="text-[color:var(--clay-ink)]" />
          <Stat2 label="Median time" value={st.median_seconds != null ? `${st.median_seconds}s` : "—"} tone="text-ink" />
        </div>
      </Card>

      {!item ? (
        <div className="flex-1 rounded-card border border-dashed border-line flex items-center justify-center text-[20px] text-ink-3">The queue is empty. Every uncertain pair has a human decision.</div>
      ) : (
        <div className="grid grid-cols-[minmax(0,1fr)_520px] gap-5 flex-1 min-h-0">
          <AnimatePresence mode="wait">
            <motion.div key={item.pair_id} initial={{ opacity: 0, x: 16 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -16 }} transition={T}
              className={cx("flex flex-col gap-4 min-h-0 rounded-card", flash === "same" && "ring-4 ring-sage", flash === "different" && "ring-4 ring-clay")}>
              {/* side-by-side records with field-level agreement */}
              <Card className="overflow-hidden">
                <div className="grid grid-cols-[150px_minmax(0,1fr)_minmax(0,1fr)_110px] bg-surface-2 px-5 py-3 items-center text-[14px] font-semibold text-ink-2">
                  <span>Field</span>
                  <span className="flex items-center gap-2"><SupplierChip code={item.a.supplier} /><span className="text-ink-3 font-normal truncate">{item.hotel_a}</span></span>
                  <span className="flex items-center gap-2"><SupplierChip code={item.b.supplier} /><span className="text-ink-3 font-normal truncate">{item.hotel_b}</span></span>
                  <span>Agreement</span>
                </div>
                {item.diffs.map((d: any) => (
                  <div key={d.field} className="grid grid-cols-[150px_minmax(0,1fr)_minmax(0,1fr)_110px] px-5 py-3 items-center border-t border-line text-[16px]">
                    <span className="text-ink-3 font-medium">{d.field}</span>
                    <span className="truncate pr-3" title={String(d.a ?? "")}>{d.a ?? <i className="text-ink-3">missing</i>}</span>
                    <span className="truncate pr-3" title={String(d.b ?? "")}>{d.b ?? <i className="text-ink-3">missing</i>}</span>
                    <span><span className={cx("rounded-full px-2.5 py-0.5 text-[13px] font-semibold", STATE_STYLE[d.state])}>{d.note ?? STATE_LABEL[d.state]}</span></span>
                  </div>
                ))}
              </Card>
              {/* decision bar */}
              <Card className="p-5 flex items-center gap-4">
                <div className="flex-1">
                  <Caption>LedgerBot's lean</Caption>
                  <div className="text-[17px] mt-0.5">Leans <b>{item.lean === "same" ? "same hotel" : "different hotels"}</b> at p = <b className="tabular">{item.p.toFixed(3)}</b>, inside the review band, so a person decides.</div>
                  <div className="mt-2"><ProbBar p={item.p} tauAccept={data.tau_accept} tauReject={data.tau_reject} width={460} /></div>
                </div>
                <div className="flex flex-col gap-2">
                  <div className="flex gap-2">
                    <button onClick={() => decide("same")} className="inline-flex items-center gap-2 rounded-full bg-sage text-white px-5 py-2.5 text-[16px] font-semibold hover:brightness-110"><Check size={18} />Same hotel <Kbd>S</Kbd></button>
                    <button onClick={() => decide("different")} className="inline-flex items-center gap-2 rounded-full bg-clay text-white px-5 py-2.5 text-[16px] font-semibold hover:brightness-110"><X size={18} />Different <Kbd>D</Kbd></button>
                  </div>
                  <div className="flex gap-2 justify-end">
                    <button onClick={() => decide("skip")} className="inline-flex items-center gap-1.5 rounded-full border border-line bg-surface px-3.5 py-1.5 text-[14px] text-ink-2 hover:bg-surface-2"><SkipForward size={15} />Skip <Kbd>K</Kbd></button>
                    <button onClick={undo} disabled={!history.length} className="inline-flex items-center gap-1.5 rounded-full border border-line bg-surface px-3.5 py-1.5 text-[14px] text-ink-2 hover:bg-surface-2 disabled:opacity-40"><CornerUpLeft size={15} />Undo <Kbd>U</Kbd></button>
                  </div>
                </div>
              </Card>
            </motion.div>
          </AnimatePresence>
          <Card className="p-5 overflow-hidden">
            <Caption>Why it is unsure: evidence for and against</Caption>
            <div className="mt-3"><Explain explain={item.explain} width={480} /></div>
            <div className="mt-4 text-[14px] text-ink-2 leading-relaxed">
              Green bars push toward "same hotel", red bars toward "different". The analyst sees the same evidence the model used, so a decision takes seconds, not a search across supplier extranets.
            </div>
            <div className="mt-3"><Cite>Uncertainty sampling (active learning): reviewing the pairs closest to 50/50 first gives the model the most information per human minute.</Cite></div>
          </Card>
        </div>
      )}
      <div className="flex gap-2 text-[13px] text-ink-3">
        <Chip variant="amber">review band</Chip><span className="self-center">between the certified auto-reject and auto-merge thresholds at α = {(data.alpha * 100).toFixed(1)}%</span>
      </div>
    </div>
  );
}

function Stat2({ label, value, tone }: { label: string; value: any; tone: string }) {
  return (
    <div className="text-center">
      <div className={cx("font-semibold tabular text-[24px] leading-none", tone)}>{value}</div>
      <div className="text-[12px] uppercase tracking-[0.06em] text-ink-3 font-semibold mt-1">{label}</div>
    </div>
  );
}
