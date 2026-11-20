import { motion, useAnimationControls } from "framer-motion";
import { useState } from "react";
import { Button, Caption, Card, Chip, Kbd, Photo, Skeleton, SupplierChip, T, Timer, cx } from "../design/primitives";
import { formatINR } from "../lib/format";
import { useFetch, useHotkeys } from "../lib/hooks";

type Side = "left" | "right";
type Run = { startedAt: number | null; stoppedAt: number | null; result: "ok" | "timeout" | null };
const LIMIT = 20;

export default function Mess() {
  const { data } = useFetch<any>("/listings?area=marina&strategy=cheapest&nights=3");
  const [runs, setRuns] = useState<Record<Side, Run>>({ left: { startedAt: null, stoppedAt: null, result: null }, right: { startedAt: null, stoppedAt: null, result: null } });
  const [flash, setFlash] = useState<{ side: Side; ok: boolean; id: string } | null>(null);
  const left = useAnimationControls();
  const right = useAnimationControls();

  const start = (side: Side) => {
    setRuns((r) => ({ ...r, [side]: { startedAt: Date.now(), stoppedAt: null, result: null } }));
    setTimeout(() => setRuns((r) => (r[side].startedAt && !r[side].stoppedAt && Date.now() - r[side].startedAt! >= LIMIT * 1000 - 50
      ? { ...r, [side]: { ...r[side], stoppedAt: r[side].startedAt! + LIMIT * 1000, result: "timeout" } } : r)), LIMIT * 1000);
  };
  const clear = () => setRuns({ left: { startedAt: null, stoppedAt: null, result: null }, right: { startedAt: null, stoppedAt: null, result: null } });
  useHotkeys({ "1": () => start("left"), "2": () => start("right"), "0": clear });

  const attempt = (side: Side, ok: boolean, id: string) => {
    const r = runs[side];
    if (!r.startedAt || r.stoppedAt) return;
    setFlash({ side, ok, id });
    setTimeout(() => setFlash(null), 700);
    if (ok) setRuns((s) => ({ ...s, [side]: { ...s[side], stoppedAt: Date.now(), result: "ok" } }));
    else (side === "left" ? left : right).start({ x: [0, -10, 10, -6, 6, 0], transition: { duration: 0.4 } });
  };

  if (!data) return <Skeleton className="w-full h-full" />;
  const tgt = data.target;
  const st = data.stats;
  const res = (r: Run) => r.result === "ok" ? `✓ ${(((r.stoppedAt ?? 0) - (r.startedAt ?? 0)) / 1000).toFixed(1)} s`
    : r.result === "timeout" ? "✗ timed out" : r.startedAt ? "searching…" : "not started";
  return (
    <div className="h-full flex flex-col">
      <div className="flex items-end justify-between">
        <div>
          <h1 className="font-serif text-[56px] leading-[1.05] tracking-[-0.01em]">Find the cheapest refundable breakfast room. You have 20 seconds.</h1>
          <p className="mt-2 text-[18px] text-ink-2">Same search on both sides: {data.search.area}, {data.search.adults} adults, {data.search.nights} nights.</p>
        </div>
      </div>
      <div className="mt-5 flex items-center gap-6">
        <Card className="px-6 py-4 flex items-center gap-6 flex-1">
          <div>
            <Caption>Target</Caption>
            <div className="text-[20px] font-medium mt-0.5">{tgt?.label}</div>
          </div>
          <div className="ml-auto flex items-center gap-10">
            <div className="flex items-center gap-3"><Button variant="soft" onClick={() => start("left")} kbd="1">Start left</Button><Timer {...runs.left} limit={LIMIT} tone={runs.left.result === "ok" ? "var(--sage)" : runs.left.result === "timeout" ? "var(--clay)" : undefined} /></div>
            <div className="flex items-center gap-3"><Button variant="soft" onClick={() => start("right")} kbd="2">Start right</Button><Timer {...runs.right} limit={LIMIT} tone={runs.right.result === "ok" ? "var(--sage)" : undefined} /></div>
          </div>
        </Card>
        <Card className="px-6 py-4 w-[420px]">
          <div className="flex items-center justify-between"><Caption>Result</Caption><Button variant="ghost" onClick={clear} kbd="0" className="!py-1 !px-3 !text-[12px]">Clear</Button></div>
          <div className="mt-1 text-[18px] font-mono">
            <span className={runs.left.result === "timeout" ? "text-[color:var(--clay-ink)]" : "text-ink"}>Left: {res(runs.left)}</span>
            <span className="text-ink-3"> / </span>
            <span className={runs.right.result === "ok" ? "text-[color:var(--sage-ink)]" : "text-ink"}>Right: {res(runs.right)}</span>
          </div>
        </Card>
      </div>

      <div className="mt-5 grid grid-cols-2 gap-8 flex-1 min-h-0">
        {/* LEFT: raw feed */}
        <motion.div animate={left} className="min-h-0 flex flex-col">
          <div className="flex items-baseline justify-between mb-2"><div className="text-[20px] font-medium">Today: raw supplier feed</div><div className="text-[13px] text-ink-3">sorted by price</div></div>
          <Card className={cx("flex-1 min-h-0 overflow-y-auto scroll-quiet", flash?.side === "left" && (flash.ok ? "ring-2 ring-sage" : "ring-2 ring-clay"))}>
            <div className="sticky top-0 bg-surface-2 grid grid-cols-[92px_1fr_1fr_120px_96px] gap-3 px-4 h-8 items-center text-[11px] uppercase tracking-[0.08em] text-ink-3 border-b border-line">
              <span>Supplier</span><span>Hotel · Room</span><span>Board · Cancellation</span><span>Ref</span><span className="text-right">3 nights</span>
            </div>
            {data.raw.map((r: any, i: number) => (
              <button key={r.offer_id} onClick={() => attempt("left", r.offer_id === tgt?.offer_id, r.offer_id)}
                className={cx("w-full text-left grid grid-cols-[92px_1fr_1fr_120px_96px] gap-3 px-4 py-1.5 items-center text-[13px] border-b border-line/60 hover:bg-lagoon-soft/50",
                  i % 2 === 1 && "bg-surface-2/40", flash && flash.id === r.offer_id && (flash.ok ? "bg-sage-soft" : "bg-clay-soft"))}>
                <SupplierChip code={r.supplier} short />
                <span className="truncate"><span className="text-ink">{r.hotel_name}</span><br /><span className="font-mono text-[12px] text-ink-2">{r.room_name}</span></span>
                <span className="truncate"><span className="font-mono text-[12px]">{r.board_raw}</span><br /><span className="text-[12px] text-ink-3">{r.cancellation_raw}</span></span>
                <span className="font-mono text-[11px] text-ink-3 truncate">{r.offer_id}</span>
                <span className="text-right font-mono">{formatINR(r.price)}</span>
              </button>
            ))}
          </Card>
        </motion.div>
        {/* RIGHT: LedgerBot */}
        <motion.div animate={right} className="min-h-0 flex flex-col">
          <div className="flex items-baseline justify-between mb-2"><div className="text-[20px] font-medium text-lagoon">LedgerBot</div><div className="text-[13px] text-ink-3">one card per hotel · one row per real room</div></div>
          <div className={cx("flex-1 min-h-0 overflow-y-auto scroll-quiet grid grid-cols-2 gap-3 content-start pr-1", flash?.side === "right" && (flash.ok ? "ring-2 ring-sage rounded-card" : "ring-2 ring-clay rounded-card"))}>
            {data.cards.map((c: any, i: number) => (
              <Card key={c.tessera_id} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ ...T, delay: i * 0.04 }} className="p-3">
                <div className="flex gap-3">
                  <Photo src={c.hero} name={c.name} className="w-14 h-14 rounded-xl flex-none" />
                  <div className="min-w-0">
                    <div className="text-[15px] font-medium truncate">{c.name}</div>
                    <div className="text-[12px] text-ink-3">{"★".repeat(c.stars || 0)} · {c.suppliers.length} suppliers · {c.n_rooms} rooms</div>
                  </div>
                </div>
                <div className="mt-2 space-y-1.5">
                  {c.rooms.map((g: any) => (
                    <div key={g.group}>
                      <div className="text-[12px] text-ink-2 font-medium">{g.name}</div>
                      <div className="flex flex-wrap gap-1 mt-0.5">
                        {g.slots.map((s: any) => (
                          <button key={s.slot_ref} onClick={() => attempt("right", s.slot_ref === tgt?.slot_ref, s.slot_ref)}
                            className={cx("rounded-full px-2 py-0.5 text-[11px] border border-line hover:border-lagoon hover:bg-lagoon-soft",
                              flash && flash.id === s.slot_ref && (flash.ok ? "bg-sage-soft border-sage" : "bg-clay-soft border-clay"))}>
                            {s.board} {s.refundable ? "· free cancel" : "· NRF"} <span className="font-mono">{formatINR(s.winner.price)}</span>
                          </button>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              </Card>
            ))}
          </div>
        </motion.div>
      </div>
      <div className="mt-3 flex gap-6 text-[15px] text-ink-2 font-mono">
        <span>Rows: <b className="text-ink">{st.rows}</b> vs Cards: <b className="text-lagoon">{st.cards}</b></span>
        <span>· Duplicate rows hidden: <b className="text-ink">{st.duplicate_rows_hidden}</b></span>
        <span>· Board codes normalized: <b className="text-ink">{st.board_codes_raw} → {st.board_codes_normalized}</b></span>
        <Chip variant="neutral" className="ml-auto">computed from this search</Chip>
      </div>
    </div>
  );
}
