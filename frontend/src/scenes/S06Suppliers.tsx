import { AnimatePresence, LayoutGroup, motion } from "framer-motion";
import { useEffect, useState } from "react";
import { useApp } from "../app/store";
import { Button, Caption, Card, Chip, Photo, SceneHeader, Skeleton, Sparkline, SupplierChip, T } from "../design/primitives";
import { api, post } from "../lib/api";
import { formatINR, SUPPLIERS } from "../lib/format";
import { useHotkeys } from "../lib/hooks";
import { useTopic } from "../lib/ws";

const CODES = ["S1", "S2", "S3", "S4", "S5"];
let simUsers = 0; // debounced so StrictMode remounts do not stop the stream

export default function Suppliers() {
  const [sups, setSups] = useState<any[] | null>(null);
  const [events, setEvents] = useState<any[]>([]);
  const [cards, setCards] = useState<any[] | null>(null);
  const [sabotage, setSabotage] = useState<Record<string, any>>({});
  const showToast = useApp((s) => s.showToast);

  useEffect(() => {
    api("/suppliers").then((d) => { setSups(d.suppliers); setSabotage(d.sabotage); });
    api("/sim/showcase").then((d) => setCards(d.cards));
    simUsers++;
    post("/sim/start");
    return () => {
      simUsers--;
      setTimeout(() => { if (simUsers === 0) post("/sim/stop"); }, 800);
    };
  }, []);
  useTopic("suppliers", (m) => setSups(m.payload));
  useTopic("bookings", (m) => setEvents((e) => [{ ...m.payload, id: m.ts + Math.random() }, ...e].slice(0, 9)));
  useTopic("offers", (m) => {
    if (m.type === "showcase") setCards(m.payload);
    if (m.type === "switch" && m.payload.switched) {
      showToast(`Switched ${m.payload.switched} offer slots away from ${m.payload.from_name} · expected failures avoided: ${m.payload.failures_avoided_per_day}/day (simulated)`, "sage");
    }
  });

  const doSabotage = async (code: string) => {
    const d = await post("/sim/sabotage", { supplier: code, mode: "price_jump", severity: 0.35 });
    setSabotage(d.sabotage);
  };
  const heal = async () => { const d = await post("/sim/heal"); setSabotage(d.sabotage); };
  useHotkeys(Object.fromEntries([...CODES.map((c, i) => [`Shift+${i + 1}`, () => doSabotage(c)]), ["Shift+0", heal]]));

  if (!sups || !cards) return <Skeleton className="w-full h-full" />;
  return (
    <div className="h-full flex flex-col">
      <SceneHeader headline="When a supplier goes bad, the shelf heals itself." subline="Reliability is learned from booking outcomes (simulated stream). Sabotage changes a supplier's hidden behaviour; the scores move only because the events do." />
      <div className="grid grid-cols-5 gap-4">
        {CODES.map((code) => {
          const s = sups.find((x) => x.code === code);
          if (!s) return null;
          const bad = !!sabotage[code];
          return (
            <Card key={code} className="p-4 group" style={{ borderColor: bad ? "var(--clay)" : undefined }}>
              <div className="flex items-center justify-between">
                <SupplierChip code={code} />
                {bad ? <Chip variant="clay">sabotaged</Chip> : <span className="text-[13px] text-ink-3">{s.n_obs} obs.</span>}
              </div>
              <div className="mt-3 flex items-end justify-between">
                <div>
                  <Caption>Reliability</Caption>
                  <div className="font-sans font-semibold tabular text-[44px] leading-none" style={{ color: bad ? "var(--clay-ink)" : "var(--ink)" }}>{(s.score * 100).toFixed(1)}</div>
                </div>
                <Sparkline data={s.spark} color={SUPPLIERS[code].color} width={120} height={40} />
              </div>
              {/* 90% credible interval band */}
              <div className="relative mt-3 h-2 rounded-full bg-surface-2">
                <motion.div className="absolute inset-y-0 rounded-full" animate={{ left: `${Math.max(0, (s.ci[0] - 0.5) / 0.5) * 100}%`, width: `${Math.max(1, ((s.ci[1] - s.ci[0]) / 0.5) * 100)}%` }}
                  transition={T} style={{ background: `${SUPPLIERS[code].color}55` }} />
                <motion.div className="absolute -top-1 w-1 h-4 rounded" animate={{ left: `${Math.max(0, (s.score - 0.5) / 0.5) * 100}%` }} transition={T} style={{ background: SUPPLIERS[code].color }} />
              </div>
              <div className="text-[13px] text-ink-3 mt-1 font-mono">90% CI {(s.ci[0] * 100).toFixed(1)}–{(s.ci[1] * 100).toFixed(1)}</div>
              <div className="mt-2 grid grid-cols-3 text-[13px]">
                <div><div className="text-ink-3">confirm</div><div className="font-mono">{(s.confirm * 100).toFixed(1)}%</div></div>
                <div><div className="text-ink-3">price jump</div><div className="font-mono">{(s.price_jump * 100).toFixed(1)}%</div></div>
                <div><div className="text-ink-3">p50</div><div className="font-mono">{s.p50_latency.toFixed(1)} s</div></div>
              </div>
              <Button variant="danger" className="mt-3 w-full justify-center" onClick={() => doSabotage(code)} kbd={`⇧${CODES.indexOf(code) + 1}`}>Sabotage</Button>
            </Card>
          );
        })}
      </div>
      <div className="grid grid-cols-[560px_minmax(0,1fr)] gap-6 mt-5 flex-1 min-h-0">
        <Card className="p-4 overflow-hidden">
          <div className="flex items-center justify-between"><Caption>Live bookings · simulated</Caption>{Object.keys(sabotage).length > 0 && <Button variant="ghost" onClick={heal} kbd="⇧0">Heal all</Button>}</div>
          <div className="mt-2">
            <AnimatePresence initial={false}>
              {events.map((e) => (
                <motion.div key={e.id} layout initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} transition={T}
                  className="flex items-center gap-3 py-1.5 border-b border-line/60 text-[14px]">
                  <span className="w-[180px] truncate">{e.hotel}</span>
                  <SupplierChip code={e.supplier} short />
                  {e.status === "confirmed" ? <span className="text-[color:var(--sage-ink)]">✓ confirmed {e.latency.toFixed(1)} s</span>
                    : e.status === "price_jump" ? <span className="text-[color:var(--clay-ink)]">✗ price jump +{formatINR(e.jump_inr)}</span>
                      : e.status === "timeout" ? <span className="text-[color:var(--clay-ink)]">⏱ timeout</span>
                        : <span className="text-[color:var(--clay-ink)]">✗ not confirmed</span>}
                </motion.div>
              ))}
            </AnimatePresence>
          </div>
        </Card>
        <div className="grid grid-cols-2 gap-4 content-start">
          <LayoutGroup>
            {cards.map((c) => (
              <Card key={c.tessera_id} className="p-4 flex gap-4">
                <Photo src={c.hero} name={c.hotel} className="w-[96px] h-[96px] rounded-xl flex-none" />
                <div className="min-w-0 flex-1">
                  <div className="text-[17px] font-medium truncate">{c.hotel}</div>
                  <div className="text-[14px] text-ink-3 truncate">{c.room} · {c.board === "BB" ? "Breakfast" : c.board} · {c.refundable ? "free cancel" : "NRF"}</div>
                  <div className="mt-2 flex items-center gap-2">
                    <Caption>selected</Caption>
                    <AnimatePresence mode="popLayout">
                      <motion.span key={c.supplier} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -10 }} transition={T}>
                        <SupplierChip code={c.supplier} />
                      </motion.span>
                    </AnimatePresence>
                    <span className="font-mono text-[15px] ml-auto">{formatINR(c.price)}</span>
                  </div>
                  <div className="text-[13px] text-ink-2 mt-1 truncate">{c.why}</div>
                </div>
              </Card>
            ))}
          </LayoutGroup>
        </div>
      </div>
    </div>
  );
}
