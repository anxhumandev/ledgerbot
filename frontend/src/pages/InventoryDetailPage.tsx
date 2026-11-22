import { ArrowLeft, ExternalLink, GitMerge, MapPin } from "lucide-react";
import { useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { ActivityOffers, HotelOffers } from "../features/offers";
import { useApi } from "../lib/hooks";
import { ago, BOARD, dateTime, duration, inr, num, pct, SUPPLIER_NAME } from "../lib/fmt";
import { ActivityTimeline } from "../ui/activity";
import { Badge, Bar, Button, Card, Confidence, CopyId, Empty, ErrorState, KeyValue, Notice, PageHeader, Select, Skeleton, StatusBadge, SupplierChip, Tabs } from "../ui/core";
import { EvidenceBars, FieldCompare } from "../ui/evidence";
import { Drawer } from "../ui/overlay";

const HOTEL_TABS = ["overview", "records", "rooms", "offers", "evidence", "content", "history"] as const;
const ACT_TABS = ["overview", "records", "rooms", "offers", "evidence", "history"] as const;
const CHECK_LABEL: Record<string, string> = { phone: "Phone", address: "Address", coordinates: "Coordinates", stars: "Star rating", photos: "Hero photo",
  rooms: "Room mapping", corroborated: "2+ suppliers", no_open_review: "No open review" };

export default function InventoryDetailPage() {
  const { type, id } = useParams();
  const [params, setParams] = useSearchParams();
  const kind = type === "activity" ? "activity" : "hotel";
  const tabs = kind === "hotel" ? HOTEL_TABS : ACT_TABS;
  const tab = (tabs as readonly string[]).includes(params.get("tab") ?? "") ? params.get("tab")! : "overview";
  const setTab = (t: string) => setParams((p) => { const n = new URLSearchParams(p); t === "overview" ? n.delete("tab") : n.set("tab", t); return n; }, { replace: true });
  const { data: d, error, isLoading, refetch } = useApi<any>(type === "hotel" || type === "activity" ? `/inventory/${type}/${id}` : null);
  const nav = useNavigate();

  if (type !== "hotel" && type !== "activity") return <ErrorState error={{ code: "not_found", message: "Unknown inventory type." }} />;
  if (error) {
    const merged = (error as any)?.details?.merged_into;
    return (
      <div className="space-y-3">
        <ErrorState error={error} onRetry={() => refetch()} />
        {merged && <div className="text-center"><Button variant="primary" onClick={() => nav(`/inventory/hotel/${merged}`)}>Open {merged}</Button></div>}
      </div>
    );
  }
  if (isLoading || !d) return <div className="space-y-4"><Skeleton className="h-8 w-80" /><Skeleton className="h-10 w-full" /><Skeleton className="h-72 w-full" /></div>;

  const tabLabels: Record<string, string> = kind === "hotel"
    ? { overview: "Overview", records: "Supplier records", rooms: "Rooms", offers: "Offers", evidence: "Matching evidence", content: "Images & content", history: "Activity history" }
    : { overview: "Overview", records: "Supplier listings", rooms: "Options", offers: "Offers", evidence: "Matching evidence", history: "Activity history" };
  return (
    <>
      <Link to={`/inventory/${kind === "hotel" ? "hotels" : "sightseeing"}`} className="mb-3 inline-flex items-center gap-1.5 text-[13px] text-fg-3 hover:text-brand-ink"><ArrowLeft size={14} />Inventory</Link>
      <PageHeader title={d.name}
        meta={<>
          <CopyId value={d.id} />
          <Badge tone={kind === "hotel" ? "brand" : "accent"}>{kind === "hotel" ? "Hotel" : "Sightseeing"}</Badge>
          <span className="inline-flex items-center gap-1"><MapPin size={13} />{d.area ? `${d.area}, ` : ""}{d.city_name}{d.country ? `, ${d.country}` : ""}</span>
          <StatusBadge status={d.status} />
          {kind === "hotel" && d.confidence !== null && <span className="inline-flex items-center gap-1.5">Confidence <Confidence p={d.confidence} /></span>}
          <span title={dateTime(d.updated_at)}>Updated {ago(d.updated_at)}</span>
        </>}
        actions={<>
          <Button icon={<ExternalLink size={14} />} onClick={() => nav(`/offers/comparison?type=${kind}&id=${d.id}`)}>Compare offers</Button>
          {d.review_cases?.some((c: any) => c.status === "open" || c.status === "escalated") && (
            <Button variant="primary" icon={<GitMerge size={14} />} onClick={() => nav(`/matching/review?case=${d.review_cases.find((c: any) => c.status === "open" || c.status === "escalated").id}`)}>Open review case</Button>
          )}
        </>} />
      <Tabs value={tab} onChange={setTab} tabs={tabs.map((t) => ({ value: t, label: tabLabels[t],
        count: t === "records" ? d.n_listings : t === "rooms" ? (kind === "hotel" ? d.rooms?.length : d.options?.length) : undefined }))} />
      <div className="mt-4">
        {kind === "hotel" ? <HotelTab tab={tab} d={d} /> : <ActivityTab tab={tab} d={d} />}
      </div>
    </>
  );
}

/* ------------------------------------------------------------------ hotel */
function HotelTab({ tab, d }: { tab: string; d: any }) {
  if (tab === "overview") return <HotelOverview d={d} />;
  if (tab === "records") return <HotelRecords d={d} />;
  if (tab === "rooms") return <HotelRooms d={d} />;
  if (tab === "offers") return <OffersTab id={d.id} kind="hotel" />;
  if (tab === "evidence") return <HotelEvidence d={d} />;
  if (tab === "content") return <HotelContent d={d} />;
  return <Card title="Activity history" subtitle="Decisions and changes recorded for this property"><ActivityTimeline events={d.history} /></Card>;
}

function HotelOverview({ d }: { d: any }) {
  const g = d.golden;
  const h = d.headline_offer;
  return (
    <div className="grid grid-cols-1 gap-4 xl:grid-cols-3">
      <Card title="Golden record" subtitle="Canonical attributes chosen by trust-weighted agreement across suppliers" className="xl:col-span-2">
        <KeyValue cols={3} items={[
          ["Name", g.name], ["Brand", g.brand ?? "—"], ["Star rating", g.stars ? `${g.stars}★` : "—"],
          ["Address", g.address ?? "—"], ["Phone", g.phone ?? "—"], ["Coordinates", <span className="num">{g.lat?.toFixed(5)}, {g.lng?.toFixed(5)}</span>],
          ["Area", g.neighbourhood ?? "—"], ["City", g.city_name], ["Country", g.country],
          ["Supplier listings", num(d.n_listings)], ["Suppliers", <span className="flex flex-wrap gap-2">{d.suppliers.map((s: string) => <SupplierChip key={s} code={s} />)}</span>],
          ["Rate plans", d.rates_loaded ? `${num(d.n_offers)} supplier offers` : "Not modelled for this city"],
        ]} />
        {d.split_from && <Notice tone="warn" className="mt-4">Split from {d.split_from} by a review decision.</Notice>}
        {d.ingested && <Notice tone="brand" className="mt-4">Created by a supplier import.</Notice>}
      </Card>
      <div className="space-y-4">
        <Card title="Catalog quality" actions={<span className="num text-[20px] font-bold text-fg">{d.quality ?? "—"}<span className="text-[12px] font-normal text-fg-3">/100</span></span>}>
          <ul className="space-y-1.5">
            {Object.entries(d.quality_checks).map(([k, v]) => (
              <li key={k} className="flex items-center justify-between text-[13px]">
                <span className="text-fg-2">{CHECK_LABEL[k] ?? k} <span className="text-[11px] text-fg-3">({d.quality_weights[k]} pts)</span></span>
                {v === null ? <span className="text-[12px] text-fg-3">n/a</span> : v ? <Badge tone="ok">Pass</Badge> : <Badge tone="bad">Missing</Badge>}
              </li>
            ))}
          </ul>
        </Card>
        <Card title="Best bookable offer" subtitle="Cheapest comparable group, recommended supplier">
          {h ? (
            <div className="space-y-1 text-[13px]">
              <div className="num text-[20px] font-bold text-fg">{inr(h.total)} <span className="text-[12px] font-normal text-fg-3">for {h.nights} nights</span></div>
              <div className="text-fg">{h.room}</div>
              <div className="text-fg-3">{h.rate_plan}</div>
              <div className="flex items-center gap-2 pt-1"><SupplierChip code={h.supplier} name={h.supplier_name} /><span className="text-fg-3">· {pct(h.reliability, 1)} reliable</span></div>
            </div>
          ) : <p className="text-[13px] text-fg-3">No rates in the synthetic world for this city.</p>}
        </Card>
      </div>
    </div>
  );
}

function HotelRecords({ d }: { d: any }) {
  const cols = ["name", "address", "phone", "coords", "stars"] as const;
  return (
    <Card title="Supplier records" subtitle="Each supplier's listing compared with the golden record (✓ agrees · ≠ differs)" pad={false}>
      <div className="overflow-x-auto scroll-thin">
        <table className="w-full min-w-[980px] text-[13px]">
          <thead><tr className="border-b border-edge bg-panel-2 text-left text-[12px] text-fg-3">
            <th className="px-3 py-2.5 font-semibold">Supplier</th><th className="px-3 py-2.5 font-semibold">Record ID</th>
            {cols.map((c) => <th key={c} className="px-3 py-2.5 font-semibold capitalize">{c === "coords" ? "Coordinates" : c}</th>)}
          </tr></thead>
          <tbody>
            {d.records.map((r: any) => (
              <tr key={r.record_id} className="border-b border-edge last:border-0">
                <td className="px-3 py-2.5"><SupplierChip code={r.supplier} name={r.supplier_name} />{r.dup_of && <Badge tone="warn" className="ml-1">duplicate listing</Badge>}</td>
                <td className="px-3 py-2.5"><CopyId value={r.record_id} /></td>
                {cols.map((c) => {
                  const cell = r.cells[c];
                  return (
                    <td key={c} className="max-w-[240px] px-3 py-2.5">
                      <span className="flex items-start gap-1.5">
                        <span className={cell.match ? "text-ok" : "text-bad"} aria-label={cell.match ? "agrees" : "differs"}>{cell.match ? "✓" : "≠"}</span>
                        <span className="break-words text-fg-2">{cell.value ?? "—"}{c === "coords" && cell.dist_m !== undefined && <span className="text-fg-3"> · {cell.dist_m} m</span>}</span>
                      </span>
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="border-t border-edge px-4 py-3">
        <div className="mb-2 text-[12px] font-semibold text-fg-3">Learned source trust (truth discovery)</div>
        <div className="grid grid-cols-1 gap-x-8 gap-y-1.5 sm:grid-cols-2 lg:grid-cols-3">
          {d.trust.map((t: any) => (
            <div key={t.supplier} className="grid grid-cols-[120px_1fr_44px] items-center gap-2 text-[12px]">
              <SupplierChip code={t.supplier} name={t.name} /><Bar value={t.trust} /><span className="num text-right">{t.trust.toFixed(2)}</span>
            </div>
          ))}
        </div>
      </div>
    </Card>
  );
}

function HotelRooms({ d }: { d: any }) {
  if (!d.rooms?.length) return <Card><Empty title="No room data" body="Rooms and rates are generated only for Dubai properties in the synthetic world." /></Card>;
  return (
    <div className="space-y-3">
      <Notice tone="neutral">Physical rooms are matched on class, bed, view, occupancy and accessibility only. Meal plan, cancellation and payment are rate-plan terms and never decide room identity.</Notice>
      <div className="grid grid-cols-1 gap-3 xl:grid-cols-2">
        {d.rooms.filter((g: any) => g.slots.length).map((g: any) => (
          <Card key={g.group} title={<span className="flex items-center gap-2">{g.name}<Badge tone={g.tier === "Primary" ? "brand" : "warn"}>{g.tier}</Badge>{g.ambiguous && <Badge tone="warn">ambiguous</Badge>}</span>}
            subtitle={`${g.suppliers.length} supplier${g.suppliers.length > 1 ? "s" : ""} · ${g.slots.length} rate plan group${g.slots.length > 1 ? "s" : ""}`}>
            <div className="mb-3 space-y-0.5">
              {g.raw_names.map((r: any) => <div key={r.supplier + r.room_name} className="flex gap-2 text-[12px]"><span className="w-7 font-semibold text-fg-3">{r.supplier}</span><span className="font-mono text-fg-3">{r.room_name}</span></div>)}
            </div>
            <ul className="space-y-1.5">
              {g.slots.map((s: any) => (
                <li key={s.label} className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-edge px-3 py-2 text-[13px]">
                  <span className="font-semibold text-fg">{BOARD[s.board]} · {s.refundable ? "Refundable" : "Non-refundable"}</span>
                  <span className="flex items-center gap-2"><SupplierChip code={s.winner.supplier} compact /><span className="num font-semibold">{inr(s.winner.price)}</span>
                    <span className="text-[12px] text-fg-3">/night · {s.n_offers} offer{s.n_offers > 1 ? "s" : ""}</span></span>
                </li>
              ))}
            </ul>
          </Card>
        ))}
      </div>
    </div>
  );
}

function OffersTab({ id, kind }: { id: string; kind: "hotel" | "activity" }) {
  const [nights, setNights] = useState("3");
  const { data, error, isLoading, refetch } = useApi<any>(kind === "hotel" ? `/offers/hotel/${id}?nights=${nights}` : `/offers/activity/${id}`);
  return (
    <Card title="Supplier offers" subtitle="Grouped so only comparable offers compete; the recommendation keeps its own price and terms"
      actions={kind === "hotel" && <label className="flex items-center gap-2 text-[12px] text-fg-3">Nights
        <Select value={nights} onChange={(e) => setNights(e.target.value)}>{[1, 2, 3, 5, 7].map((n) => <option key={n}>{n}</option>)}</Select></label>}>
      {error ? <ErrorState error={error} onRetry={() => refetch()} /> : isLoading || !data ? <Skeleton className="h-64" />
        : kind === "hotel" ? <HotelOffers data={data} compact /> : <ActivityOffers data={data} />}
    </Card>
  );
}

function PairExplain({ a, b, onClose }: { a: string | null; b: string | null; onClose: () => void }) {
  const { data, isLoading, error } = useApi<any>(a && b ? `/matching/explain?a=${a}&b=${b}` : null);
  return (
    <Drawer open={!!a} onClose={onClose} title="Pair evidence" width={640}>
      {error ? <ErrorState error={error} /> : isLoading || !data ? <Skeleton className="h-64" /> : (
        <div className="space-y-5">
          <FieldCompare diffs={data.diffs} headA={<SupplierChip code={data.explain.a.supplier} />} headB={<SupplierChip code={data.explain.b.supplier} />} />
          <EvidenceBars explain={data.explain} />
          <Notice tone={data.same_property ? "ok" : "neutral"}>{data.same_property ? "These records are currently mapped to the same property." : "These records are currently mapped to different properties."}</Notice>
        </div>
      )}
    </Drawer>
  );
}

function HotelEvidence({ d }: { d: any }) {
  const [pair, setPair] = useState<[string, string] | null>(null);
  return (
    <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
      <Card title="Why these listings were merged" subtitle="Every scored link inside the record, strongest first" pad={false}>
        {!d.links.length ? <Empty title="Single-source record" body="Only one supplier lists this property, so there is nothing to merge." /> : (
          <ul className="divide-y divide-edge">
            {d.links.map((l: any) => (
              <li key={l.record_a + l.record_b}>
                <button onClick={() => setPair([l.record_a, l.record_b])} className="flex w-full items-center gap-3 px-4 py-2.5 text-left hover:bg-panel-2">
                  <span className="min-w-0 flex-1 text-[13px]">
                    <span className="flex items-center gap-1.5"><SupplierChip code={l.supplier_a} compact /><span className="truncate text-fg">{l.name_a}</span></span>
                    <span className="flex items-center gap-1.5"><SupplierChip code={l.supplier_b} compact /><span className="truncate text-fg">{l.name_b}</span></span>
                  </span>
                  <Confidence p={l.p} />
                  {l.band && <StatusBadge status={l.band === "auto_merge" ? "verified" : l.band === "uncertain" ? "needs_review" : "rejected"} label={l.band === "auto_merge" ? "Auto-merge" : l.band === "uncertain" ? "Review band" : "Below reject"} />}
                </button>
              </li>
            ))}
          </ul>
        )}
      </Card>
      <Card title="Why nearby properties were kept separate" subtitle="Closest candidates the matcher scored and did not merge" pad={false}>
        {!d.kept_separate.length ? <Empty title="No close candidates" /> : (
          <ul className="divide-y divide-edge">
            {d.kept_separate.map((k: any) => (
              <li key={k.tessera_id} className="flex items-center gap-3 px-4 py-2.5">
                <div className="min-w-0 flex-1">
                  <Link to={`/inventory/hotel/${k.tessera_id}`} className="block truncate text-[13px] font-semibold text-fg hover:text-brand-ink">{k.name}</Link>
                  <div className="text-[12px] text-fg-3">{k.tessera_id}{k.distance_m !== null ? ` · ${num(k.distance_m)} m away` : ""}</div>
                </div>
                <Confidence p={k.p} />
                <Button size="sm" variant="ghost" onClick={() => setPair([k.record_a, k.record_b])}>Evidence</Button>
              </li>
            ))}
          </ul>
        )}
      </Card>
      {d.weakest_explain && (
        <Card title="Weakest link in this record" subtitle={`${d.weakest_explain.a.name} ↔ ${d.weakest_explain.b.name}`} className="xl:col-span-2">
          <div className="max-w-[720px]"><EvidenceBars explain={d.weakest_explain} /></div>
        </Card>
      )}
      <PairExplain a={pair?.[0] ?? null} b={pair?.[1] ?? null} onClose={() => setPair(null)} />
    </div>
  );
}

function HotelContent({ d }: { d: any }) {
  const [showAll, setShowAll] = useState(false);
  if (!d.photos) return <Card><Empty title="No photos" body="Photos are generated for showcase Dubai properties only." /></Card>;
  const all = d.photos.unique.flatMap((u: any) => u.members.map((m: string) => ({ ...u, url: m })));
  const shown = showAll ? all : d.photos.unique;
  return (
    <Card title="Images & content" subtitle={`${d.photos.total} supplier photos from ${d.photos.suppliers} suppliers → ${d.photos.n_unique} unique after perceptual-hash de-duplication`}
      actions={<Button size="sm" onClick={() => setShowAll(!showAll)}>{showAll ? "Show unique only" : "Show all supplier copies"}</Button>}>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-6">
        {shown.map((p: any, i: number) => (
          <figure key={p.url + i} className="overflow-hidden rounded-lg border border-edge">
            <img src={p.url} alt={`${d.name} photo ${i + 1}`} loading="lazy" className="aspect-[4/3] w-full object-cover" />
            {!showAll && <figcaption className="flex items-center justify-between px-2 py-1 text-[11px] text-fg-3">{i === 0 ? <Badge tone="accent">Hero</Badge> : <span>{p.members.length} copies</span>}<span>{p.w}×{p.h}</span></figcaption>}
          </figure>
        ))}
      </div>
    </Card>
  );
}

/* ------------------------------------------------------------------ sightseeing */
function ActivityTab({ tab, d }: { tab: string; d: any }) {
  if (tab === "overview") return (
    <div className="grid grid-cols-1 gap-4 xl:grid-cols-3">
      <Card title="Canonical experience" className="xl:col-span-2">
        <KeyValue cols={3} items={[
          ["Name", d.name], ["Attraction", d.attraction.replace(/_/g, " ")], ["Access tier", d.access_tier ? `Level ${d.access_tier}` : "Standard"],
          ["City", d.city_name], ["Options", num(d.options.length)], ["Supplier listings", num(d.n_listings)],
          ["Suppliers", <span className="flex flex-wrap gap-2">{d.suppliers.map((s: string) => <SupplierChip key={s} code={s} />)}</span>],
          ["Option differences", d.option_axes.length ? d.option_axes.join(", ").replace("time_slot", "time slot") : "—"], ["Quality", d.quality !== null ? `${d.quality}/100` : "—"],
        ]} />
      </Card>
      <Card title="Matching rule"><p className="text-[13px] text-fg-2">{d.merge_rule}</p>
        <p className="mt-3 text-[12px] text-fg-3">Evaluation on the synthetic ground truth: product F1 {d.evaluation.product.f1.toFixed(3)}, option F1 {d.evaluation.option.f1.toFixed(3)}.</p></Card>
    </div>
  );
  if (tab === "records" || tab === "rooms") return (
    <div className="space-y-3">
      {d.options.map((o: any) => (
        <Card key={o.label} title={`Option · ${o.label}`} subtitle={`${o.units.length} listing${o.units.length > 1 ? "s" : ""} · from ${inr(o.best_adult)} per adult${o.duration_range ? ` · ${duration(o.duration_range[0])}` : ""}`} pad={false}>
          <div className="overflow-x-auto scroll-thin">
            <table className="w-full min-w-[820px] text-[13px]">
              <thead><tr className="border-b border-edge bg-panel-2 text-left text-[12px] text-fg-3">
                <th className="px-4 py-2 font-semibold">Supplier</th><th className="px-3 py-2 font-semibold">Listing</th><th className="px-3 py-2 font-semibold">Duration</th>
                <th className="px-3 py-2 font-semibold">Language</th><th className="px-3 py-2 font-semibold">Pickup / meeting point</th><th className="px-3 py-2 font-semibold">Inclusions</th>
                <th className="px-3 py-2 text-right font-semibold">Adult</th></tr></thead>
              <tbody>{o.units.map((u: any) => (
                <tr key={u.listing_id} className="border-b border-edge last:border-0">
                  <td className="px-4 py-2"><SupplierChip code={u.supplier} name={u.supplier_name} /></td>
                  <td className="max-w-[280px] px-3 py-2"><div className="truncate text-fg" title={u.title}>{u.title}</div><CopyId value={u.listing_id} /></td>
                  <td className="px-3 py-2"><span className="num">{u.duration}</span>{u.duration_min ? <span className="text-[11px] text-fg-3"> ({duration(u.duration_min)})</span> : null}</td>
                  <td className="px-3 py-2">{u.language ?? "—"}</td><td className="max-w-[200px] truncate px-3 py-2" title={u.meeting_point}>{u.meeting_point ?? "—"}</td>
                  <td className="max-w-[200px] truncate px-3 py-2" title={u.inclusions}>{u.inclusions ?? "—"}</td>
                  <td className="num px-3 py-2 text-right font-semibold text-fg">{inr(u.prices.adult)}</td>
                </tr>))}</tbody>
            </table>
          </div>
        </Card>
      ))}
    </div>
  );
  if (tab === "offers") return <OffersTab id={d.id} kind="activity" />;
  if (tab === "evidence") return (
    <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
      <Card title="Why these listings were merged"><p className="text-[13px] text-fg-2">{d.merge_rule}</p>
        <ul className="mt-3 space-y-1.5 text-[13px]">{d.options.map((o: any) => <li key={o.label} className="flex justify-between gap-3"><span className="text-fg">{o.label}</span><span className="text-fg-3">{o.suppliers.map((s: string) => SUPPLIER_NAME[s] ?? s).join(", ")}</span></li>)}</ul>
      </Card>
      <Card title="Kept separate on purpose" subtitle="Same attraction, different access tier: a different product">
        {d.kept_separate_products.length ? (
          <ul className="space-y-2">{d.kept_separate_products.map((p: any) => (
            <li key={p.product_id} className="flex items-center justify-between gap-3 text-[13px]">
              <Link to={`/inventory/activity/${p.product_id}`} className="font-semibold text-fg hover:text-brand-ink">{p.label}</Link>
              <span className="text-fg-3">{p.tier ? `Level ${p.tier}` : "Standard"} · {p.n_listings} listings</span>
            </li>))}</ul>
        ) : <p className="text-[13px] text-fg-3">No other product shares this attraction.</p>}
        {d.option_axes.length > 0 && <p className="mt-3 text-[12px] text-fg-3">Options inside this product differ by {d.option_axes.join(", ").replace("time_slot", "time slot")}: those listings were deliberately not merged into one option.</p>}
      </Card>
    </div>
  );
  return <Card title="Activity history"><ActivityTimeline events={d.history} /></Card>;
}
