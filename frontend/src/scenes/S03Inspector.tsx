import { AnimatePresence, motion } from "framer-motion";
import { useEffect, useState } from "react";
import { useApp } from "../app/store";
import ReviewQueue from "./ReviewQueue";
import { Button, Caption, Card, Chip, Cite, Explain, Photo, SceneHeader, Skeleton, SupplierChip, T, Toggle, cx, rise } from "../design/primitives";
import { formatINR, SUPPLIERS } from "../lib/format";
import { useFetch, useHotkeys } from "../lib/hooks";

type Tab = "hotel" | "rooms" | "activities" | "review";

export default function Inspector() {
  const [tab, setTab] = useState<Tab>("hotel");
  const { data: featured } = useFetch<any[]>("/clusters/featured");
  const inspect = useApp((s) => s.inspect);
  const [tid, setTid] = useState<string | null>(inspect);
  useEffect(() => { if (inspect) { setTid(inspect); setTab("hotel"); } }, [inspect]);
  const id = tid ?? featured?.[0]?.tessera_id ?? null;
  const { data } = useFetch<any>(id ? `/clusters/${id}` : null, [id]);
  const [nearMiss, setNearMiss] = useState(false);
  const { data: nm } = useFetch<any>(nearMiss ? "/clusters/near-miss" : null, [nearMiss]);
  useHotkeys({ h: () => setTab("hotel"), m: () => setTab("rooms"), a: () => setTab("activities"), q: () => setTab("review"), n: () => { setTab("hotel"); setNearMiss((v) => !v); } });

  return (
    <div className="h-full flex flex-col">
      <SceneHeader headline="Every merge comes with a reason." subline="A golden record per property, built from every supplier, with the evidence on display."
        right={<Toggle value={tab} onChange={setTab} options={[{ value: "hotel", label: "Hotel" }, { value: "rooms", label: "Rooms" }, { value: "activities", label: "Activities" }, { value: "review", label: "Review queue" }]} />} />
      {featured && (tab === "hotel" || tab === "rooms") && (
        <div className="flex gap-2 mb-4 flex-wrap">
          {id && !featured.slice(0, 9).some((f) => f.tessera_id === id) && data?.golden && (
            <span className="rounded-full px-3 py-1 text-[14px] border bg-ink text-paper border-ink">{data.golden.name}</span>
          )}
          {featured.slice(0, 9).map((f) => (
            <button key={f.tessera_id} onClick={() => { setTid(f.tessera_id); setNearMiss(false); }}
              className={cx("rounded-full px-3 py-1 text-[14px] border", f.tessera_id === id ? "bg-ink text-paper border-ink" : "border-line text-ink-2 hover:bg-surface-2")}>
              {f.name}
            </button>
          ))}
        </div>
      )}
      <div className="flex-1 min-h-0">
        {tab === "hotel" && (data ? <HotelTab d={data} nearMiss={nearMiss} nm={nm} toggleNM={() => setNearMiss((v) => !v)} /> : <Skeleton className="w-full h-full" />)}
        {tab === "rooms" && (data ? <RoomsTab d={data} /> : <Skeleton className="w-full h-full" />)}
        {tab === "activities" && <ActivitiesTab />}
        {tab === "review" && <ReviewQueue />}
      </div>
    </div>
  );
}

function HotelTab({ d, nearMiss, nm, toggleNM }: { d: any; nearMiss: boolean; nm: any; toggleNM: () => void }) {
  const g = d.golden;
  const cols = ["name", "address", "phone", "coords", "stars"];
  const [collapsed, setCollapsed] = useState(false);
  const ex = nearMiss && nm ? nm.pair : d.explain;
  return (
    <div className="grid grid-cols-[minmax(0,1fr)_560px] gap-6 h-full">
      <div className="flex flex-col gap-4 min-h-0">
        <Card {...rise(0)} className="flex overflow-hidden">
          <Photo src={g.hero} name={g.name} className="w-[220px] h-[170px] flex-none" />
          <div className="p-5 flex-1">
            <div className="flex items-center gap-2"><Chip variant="lagoon">{g.tessera_id}</Chip><Caption>golden record</Caption></div>
            <div className="font-serif text-[38px] leading-tight mt-1">{g.name}</div>
            <div className="text-[16px] text-ink-2">{"★".repeat(g.stars || 0)} · {g.neighbourhood} · {g.phone ?? "—"}</div>
            <div className="mt-2 flex gap-1.5">{g.suppliers.map((s: string) => <SupplierChip key={s} code={s} />)}</div>
          </div>
        </Card>
        <Card {...rise(1)} className="overflow-hidden">
          <div className="grid grid-cols-[120px_1.4fr_1.4fr_1fr_0.9fr_60px] px-4 h-9 items-center bg-surface-2 text-[13px] uppercase tracking-[0.08em] text-ink-3">
            <span>Supplier</span>{cols.map((c) => <span key={c}>{c}</span>)}
          </div>
          {d.diffs.map((r: any, i: number) => (
            <motion.div key={r.record_id} {...rise(i + 2)} className="grid grid-cols-[120px_1.4fr_1.4fr_1fr_0.9fr_60px] px-4 py-2 items-center border-t border-line text-[14px]">
              <span><SupplierChip code={r.supplier} short />{r.dup_of && <Chip variant="amber" className="ml-1">dup</Chip>}</span>
              {cols.map((c) => {
                const cell = r.cells[c];
                return (
                  <span key={c} className="flex items-center gap-1.5 min-w-0 pr-2">
                    <span className={cx("w-4 flex-none text-center font-medium", cell.match ? "text-[color:var(--sage-ink)]" : "text-[color:var(--clay-ink)]")}>{cell.match ? "✓" : "≠"}</span>
                    <span className="truncate text-ink-2" title={String(cell.value ?? "—")}>{cell.value ?? "—"}{c === "coords" && cell.dist_m !== undefined ? <span className="text-ink-3"> · {cell.dist_m} m</span> : null}</span>
                  </span>
                );
              })}
            </motion.div>
          ))}
        </Card>
        {d.photos && (
          <Card {...rise(3)} className="p-4 cursor-pointer" onClick={() => setCollapsed((c) => !c)}>
            <div className="flex items-baseline justify-between">
              <Caption>Photos · pHash dedup (Hamming ≤ 8) · hero pick</Caption>
              <div className="text-[16px]"><span className="font-mono">{d.photos.total}</span> photos from {d.photos.suppliers} suppliers → <span className="font-mono text-lagoon">{d.photos.n_unique}</span> unique</div>
            </div>
            <div className="mt-3 flex gap-2 overflow-hidden h-[74px]">
              <AnimatePresence initial={false}>
                {(collapsed ? d.photos.unique : d.photos.unique.flatMap((u: any) => u.members.map((m: string) => ({ ...u, url: m, key: m })))).slice(0, 26).map((p: any, i: number) => (
                  <motion.img layout key={p.key ?? p.url} src={p.url} initial={{ opacity: 0, scale: 0.8 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0, scale: 0.6 }}
                    transition={{ ...T, delay: i * 0.01 }} className={cx("h-[74px] w-[96px] object-cover rounded-lg flex-none", i === 0 && collapsed && "ring-2 ring-saffron")} />
                ))}
              </AnimatePresence>
            </div>
            <div className="mt-2 text-[13px] text-ink-3">{collapsed ? "Unique set, best copy kept (highest resolution). Saffron = hero (sharpness × resolution × category prior)." : "All supplier copies. Click to collapse duplicates."}</div>
          </Card>
        )}
      </div>
      <div className="flex flex-col gap-4 min-h-0">
        <Card {...rise(1)} className="p-5">
          <div className="flex items-center justify-between">
            <Caption>{nearMiss ? "Near-miss: sister properties" : "Weakest edge in this cluster"}</Caption>
            <Button variant="ghost" onClick={toggleNM} kbd="N">{nearMiss ? "Back" : "Show a near-miss"}</Button>
          </div>
          {ex && (
            <div className="mt-2 text-[15px] text-ink-2">
              <SupplierChip code={ex.a.supplier} short /> <span className="text-ink">{ex.a.name}</span>
              <span className="text-ink-3"> vs </span>
              <SupplierChip code={ex.b.supplier} short /> <span className="text-ink">{ex.b.name}</span>
            </div>
          )}
          <div className="mt-3">{ex ? <Explain explain={ex} width={510} /> : <Skeleton className="h-40" />}</div>
          {ex && (
            <div className="mt-3">
              <Chip variant={ex.band === "auto_merge" ? "sage" : ex.band === "auto_reject" ? "neutral" : "amber"}>
                {ex.band === "auto_merge" ? "auto-merged" : ex.band === "auto_reject" ? "kept separate" : "sent to review"}
              </Chip>
            </div>
          )}
        </Card>
        <Card {...rise(2)} className="p-5">
          <Caption>Learned source trust · truth discovery</Caption>
          <div className="mt-3 space-y-2">
            {d.trust.map((t: any) => (
              <div key={t.supplier} className="flex items-center gap-3">
                <span className="w-[120px] text-[14px] text-ink-2">{t.name}</span>
                <div className="flex-1 h-2.5 rounded-full bg-surface-2 overflow-hidden">
                  <motion.div initial={{ width: 0 }} animate={{ width: `${t.trust * 100}%` }} transition={{ ...T, duration: 0.7 }} className="h-full rounded-full" style={{ background: SUPPLIERS[t.supplier]?.color }} />
                </div>
                <span className="w-12 text-right font-mono text-[14px]">{t.trust.toFixed(2)}</span>
              </div>
            ))}
          </div>
          <div className="mt-3"><Cite>Trust = agreement with the trust-weighted consensus on stars, phone, address and coordinates (TruthFinder-lite).</Cite></div>
        </Card>
      </div>
    </div>
  );
}

function RoomsTab({ d }: { d: any }) {
  return (
    <div className="h-full flex flex-col">
      <div className="flex-1 min-h-0 overflow-y-auto scroll-quiet grid grid-cols-2 gap-4 content-start">
        {d.rooms.filter((g: any) => g.slots.length).map((g: any, i: number) => (
          <Card key={g.group} {...rise(i)} className="p-5">
            <div className="flex items-center gap-2">
              <span className="text-[20px] font-medium">{g.name}</span>
              <Chip variant={g.tier === "Primary" ? "lagoon" : "amber"}>{g.tier} match · {g.suppliers.length} supplier{g.suppliers.length > 1 ? "s" : ""}</Chip>
            </div>
            <div className="mt-1 flex flex-wrap gap-x-3 gap-y-0.5">
              {g.raw_names.map((r: any) => <span key={r.supplier + r.room_name} className="font-mono text-[13px] text-ink-3">{r.supplier}: {r.room_name}</span>)}
            </div>
            <div className="mt-3 space-y-2">
              {g.slots.map((s: any) => (
                <div key={s.label} className="rounded-xl border border-line p-3">
                  <div className="flex items-center justify-between">
                    <span className="text-[15px] font-medium">{s.label}</span>
                    <span className="text-[13px] text-ink-3">{s.n_offers} supplier offer{s.n_offers > 1 ? "s" : ""} compete</span>
                  </div>
                  <div className="mt-2 flex flex-wrap gap-2 items-center">
                    <span className="inline-flex items-center gap-2 rounded-full bg-saffron-soft px-3 py-1">
                      <SupplierChip code={s.winner.supplier} short /><span className="font-mono text-[14px]">{formatINR(s.winner.price)}</span>
                      <span className="text-[13px] text-[color:var(--saffron-ink)] font-medium">winner</span>
                    </span>
                    {s.alternatives.map((a: any) => (
                      <span key={a.offer_id} className="inline-flex items-center gap-1.5 text-[14px] text-ink-3"><SupplierChip code={a.supplier} short /><span className="font-mono">{formatINR(a.price)}</span></span>
                    ))}
                  </div>
                  <div className="mt-1.5 text-[13px] text-ink-2">{s.why}</div>
                </div>
              ))}
            </div>
          </Card>
        ))}
      </div>
      <div className="mt-3 text-[17px] text-ink-2">Board and cancellation never decide room identity. <Cite>Room identity = class · bed · view · occupancy · accessibility. Offers merge into a slot only when board, refundability, occupancy and nights all match.</Cite></div>
    </div>
  );
}

function ActivitiesTab() {
  const { data } = useFetch<any>("/activities");
  if (!data) return <Skeleton className="w-full h-full" />;
  return (
    <div className="h-full flex flex-col">
      <div className="grid grid-cols-2 gap-6 flex-1 min-h-0">
        {data.burj.map((p: any, i: number) => (
          <Card key={p.product_id} {...rise(i)} className="p-6 overflow-hidden">
            <Caption>Product · {p.product_id}</Caption>
            <div className="font-serif text-[32px] leading-tight mt-1">{p.label}</div>
            <div className="text-[14px] text-ink-3">{p.n_listings} supplier listings · {p.options.length} options</div>
            <div className="mt-4 space-y-3">
              {p.options.map((o: any) => (
                <div key={o.label} className="rounded-xl border border-line p-3">
                  <div className="flex items-center justify-between"><span className="text-[16px] font-medium">Option · {o.label}</span><span className="font-mono text-[14px]">from {formatINR(o.best_adult)} / adult</span></div>
                  <div className="mt-2 space-y-1">
                    {o.units.map((u: any) => (
                      <div key={u.listing_id} className="flex items-center gap-2 text-[13px]">
                        <SupplierChip code={u.supplier} short />
                        <span className="truncate text-ink-2 flex-1" title={u.title}>{u.title}</span>
                        <span className="text-ink-3 font-mono">{u.duration}</span>
                        <span className="font-mono">{formatINR(u.prices.adult)}</span>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </Card>
        ))}
      </div>
      <div className="mt-3 text-[17px] text-ink-2">
        Levels 124/125 and SKY 148 are different products; prime vs non-prime are options of one product.{" "}
        <Cite>Product F1 {data.eval.product.f1.toFixed(3)} · option F1 {data.eval.option.f1.toFixed(3)} on {data.n_listings} listings · OCTO activity model</Cite>
      </div>
    </div>
  );
}
