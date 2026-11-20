import { AnimatePresence, motion } from "framer-motion";
import { useEffect, useState } from "react";
import { Caption, Chip, Photo, Skeleton, SupplierChip, T, Ticker } from "../design/primitives";
import { formatINR, groupIN, REDUCE_MOTION } from "../lib/format";
import { useFetch, useHotkeys } from "../lib/hooks";

function RawRow({ r }: { r: any }) {
  return (
    <div className="grid grid-cols-[150px_300px_330px_190px_1fr_120px] items-center gap-4 px-6 h-[54px] text-[15px]">
      <SupplierChip code={r.supplier} />
      <span className="truncate text-ink">{r.hotel_name}</span>
      <span className="truncate font-mono text-[14px] text-ink-2">{r.room_name}</span>
      <span className="truncate font-mono text-[14px] text-ink-2">{r.board_raw}</span>
      <span className="truncate text-[14px] text-ink-3">{r.cancellation_raw}</span>
      <span className="text-right font-mono text-ink">{formatINR(r.price)}</span>
    </div>
  );
}

export default function ColdOpen() {
  const { data } = useFetch<any>("/world/cold-open");
  const [folded, setFolded] = useState(false);
  useEffect(() => {
    if (!data) return;
    const t = setTimeout(() => setFolded(true), 1500);
    return () => clearTimeout(t);
  }, [data]);
  useHotkeys({ " ": () => setFolded((f) => !f) });
  if (!data) return <Skeleton className="w-full h-[700px]" />;
  const s = data.stats;
  const best = data.best.winner;
  return (
    <div className="h-full flex flex-col items-center">
      <motion.h1 initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={T}
        className="font-serif text-[64px] leading-[1.05] tracking-[-0.01em] text-ink text-center mt-2">
        {folded ? "Nine listings. One room." : "Nine listings."}
      </motion.h1>
      <div className="h-[34px] mt-3">
        <AnimatePresence>
          {folded && (
            <motion.p initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ ...T, delay: 0.7 }} className="text-[18px] text-ink-2 text-center">
              Tessera turns supplier chaos into one trustworthy shelf.
            </motion.p>
          )}
        </AnimatePresence>
      </div>
      <div className="relative w-[1440px] mt-6 h-[600px]">
        
          <AnimatePresence>
            {!folded && (
              <motion.div key="rows" exit={{ height: 94, opacity: 0, transition: { height: { ...T, duration: REDUCE_MOTION ? 0 : 0.5 }, opacity: { duration: 0.2, delay: REDUCE_MOTION ? 0 : 0.5 } } }} className="absolute inset-x-0 top-0 bg-surface border border-line rounded-card shadow-card overflow-hidden">
                <div className="px-6 h-10 flex items-center text-[12px] uppercase tracking-[0.08em] text-ink-3 border-b border-line bg-surface-2">
                  Raw supplier feed · {data.hotel.name} · same physical room
                </div>
                {data.rows.map((r: any, i: number) => (
                  <motion.div key={r.offer_id}
                    initial={{ opacity: 0, y: REDUCE_MOTION ? 0 : 8 }} animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: i === 0 ? 1 : 0, y: REDUCE_MOTION ? 0 : -(i * 54), transition: { ...T, duration: 0.45, delay: (8 - i) * 0.025 } }}
                    transition={{ ...T, delay: i * 0.04 }}
                    className={i % 2 ? "bg-surface-2/60" : ""}>
                    <RawRow r={r} />
                  </motion.div>
                ))}
              </motion.div>
            )}
            {folded && (
              <motion.div key="card" initial={{ opacity: 0, scaleY: 0.2, y: -10 }} animate={{ opacity: 1, scaleY: 1, y: 0 }} exit={{ opacity: 0, scale: 0.98 }}
                transition={{ ...T, duration: REDUCE_MOTION ? 0 : 0.55, delay: REDUCE_MOTION ? 0 : 0.55 }}
                style={{ left: "calc(50% - 430px)", transformOrigin: "top center" }} className="absolute top-6 w-[860px] bg-surface border border-line rounded-card shadow-card overflow-hidden">
                <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ ...T, delay: REDUCE_MOTION ? 0 : 0.85 }} className="flex">
                  <Photo src={data.hotel.hero} name={data.hotel.name} className="w-[300px] min-h-[300px] self-stretch flex-none" />
                  <div className="flex-1 p-8">
                    <Caption>{data.hotel.neighbourhood} · {"★".repeat(data.hotel.stars || 0)}</Caption>
                    <div className="font-serif text-[40px] leading-tight mt-1">{data.hotel.name}</div>
                    <div className="mt-2 flex items-center gap-2">
                      <span className="text-[20px] text-ink">{data.room.name}</span>
                      <Chip variant="lagoon">{data.room.tier} match</Chip>
                    </div>
                    <div className="mt-2 flex gap-1.5 flex-wrap">{data.room.suppliers.map((c: string) => <SupplierChip key={c} code={c} short />)}</div>
                    <div className="mt-6 rounded-2xl bg-saffron-soft p-4">
                      <div className="flex items-baseline justify-between">
                        <div>
                          <div className="text-[12px] uppercase tracking-[0.08em] text-[color:var(--saffron-ink)] font-medium">Best offer · {data.best.label}</div>
                          <div className="font-mono text-[34px] text-ink mt-1">{formatINR(best.price)}<span className="text-[15px] text-ink-3"> /night</span></div>
                        </div>
                        <SupplierChip code={best.supplier} />
                      </div>
                      <div className="text-[14px] text-ink-2 mt-1">{data.best.why}</div>
                    </div>
                    <div className="mt-4 text-[15px] text-lagoon font-medium">+{data.alternatives} alternatives across {data.n_slots} offer slots</div>
                  </div>
                </motion.div>
              </motion.div>
            )}
          </AnimatePresence>
        
      </div>
      <AnimatePresence>
        {folded && (
          <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ ...T, delay: 1.0 }}
            className="absolute bottom-10 left-0 right-0 flex justify-center gap-24">
            <SoftStat a={s.dubai_raw_records} b={s.dubai_hotels} la="raw supplier records" lb="unique hotels" />
            <SoftStat a={s.dubai_room_names} b={s.dubai_room_groups} la="supplier room names" lb="real rooms" />
            <div className="text-center">
              <div className="font-mono text-[44px] text-[color:var(--sage-ink)] leading-none"><Ticker value={s.violations} /></div>
              <Caption className="mt-2">consistency violations</Caption>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

function SoftStat({ a, b, la, lb }: { a: number; b: number; la: string; lb: string }) {
  return (
    <div className="text-center">
      <div className="font-mono text-[44px] leading-none text-ink">
        <Ticker value={a} format={(v) => groupIN(v)} /> <span className="text-ink-3">→</span> <span className="text-lagoon"><Ticker value={b} format={(v) => groupIN(v)} /></span>
      </div>
      <Caption className="mt-2">{la} → {lb} · Dubai</Caption>
    </div>
  );
}
