import { Code2, Table2 } from "lucide-react";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ActivityOffers, HotelOffers } from "../features/offers";
import { qs } from "../lib/api";
import { useApi, useDebounced, useUrlState } from "../lib/hooks";
import { num } from "../lib/fmt";
import { Badge, Button, Card, cx, Empty, ErrorState, Field, PageHeader, SearchInput, Segmented, Select, Skeleton, SupplierChip } from "../ui/core";

const DEF = { type: "hotel", id: "", nights: "3", board: "", refundable: "", payment: "", supplier: "", view: "table", compare: "group" };

export default function OfferComparisonPage() {
  const [s, set] = useUrlState(DEF);
  const [search, setSearch] = useState("");
  const dq = useDebounced(search, 250);
  const results = useApi<any[]>(`/offers/search${qs({ type: s.type, q: dq, limit: 12 })}`);
  useEffect(() => { if (!s.id && results.data?.length) set({ id: results.data[0].id }, false); }, [results.data, s.id]);
  const path = s.id ? (s.type === "hotel"
    ? `/offers/hotel/${s.id}${qs({ nights: s.nights, board: s.board, refundable: s.refundable, payment: s.payment, supplier: s.supplier, compare: s.compare })}`
    : `/offers/activity/${s.id}${qs({ supplier: s.supplier })}`) : null;
  const { data, error, isFetching, refetch } = useApi<any>(path);
  const api = useApi<any>(s.view === "api" && s.type === "hotel" && s.id ? `/v1/hotels/${s.id}/offers?nights=${s.nights}` : null);
  const boards = s.board ? s.board.split(",") : [];
  const toggleBoard = (b: string) => set({ board: (boards.includes(b) ? boards.filter((x) => x !== b) : [...boards, b]).join(",") }, false);
  return (
    <>
      <PageHeader title="Offer Comparison" description="Compare every supplier offer for a property or experience. Only offers with the same room and terms compete, and the recommendation is explained."
        actions={<Segmented label="Category" value={s.type as "hotel" | "activity"} onChange={(v) => set({ type: v, id: "", board: "", refundable: "", payment: "", supplier: "", view: "table" })}
          options={[{ value: "hotel", label: "Hotels" }, { value: "activity", label: "Sightseeing" }]} />} />
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-[300px_minmax(0,1fr)]">
        <div className="space-y-4">
          <Card pad={false}>
            <div className="border-b border-edge p-3"><SearchInput value={search} onChange={setSearch} placeholder={s.type === "hotel" ? "Find a property" : "Find an experience"} label="Find product" /></div>
            <ul className="max-h-[360px] overflow-y-auto scroll-thin">
              {results.isLoading && <li className="p-3"><Skeleton className="h-24" /></li>}
              {results.data?.map((r) => (
                <li key={r.id}>
                  <button onClick={() => set({ id: r.id }, false)} className={cx("w-full border-l-[3px] px-3 py-2 text-left", r.id === s.id ? "border-brand bg-brand-soft/60" : "border-transparent hover:bg-panel-2")}>
                    <div className="truncate text-[13px] font-semibold text-fg">{r.name}</div>
                    <div className="text-[11px] text-fg-3">{r.id} · {r.city_name} · {r.n_suppliers} suppliers · {num(r.n_offers)} offers</div>
                  </button>
                </li>
              ))}
              {results.data?.length === 0 && <li><Empty title="No matches" body={s.type === "hotel" ? "Rates exist for Dubai properties only." : undefined} /></li>}
            </ul>
          </Card>
          {s.type === "hotel" && (
            <Card title="Requirements">
              <div className="space-y-3">
                <Field label="Nights (2 adults)"><Select value={s.nights} onChange={(e) => set({ nights: e.target.value }, false)} className="w-full">{[1, 2, 3, 4, 5, 7, 10].map((n) => <option key={n}>{n}</option>)}</Select></Field>
                <fieldset><legend className="mb-1 text-[12px] font-semibold text-fg-2">Meal plan</legend>
                  <div className="flex flex-wrap gap-1.5">{["RO", "BB", "HB", "FB", "AI"].map((b) => (
                    <button key={b} onClick={() => toggleBoard(b)} aria-pressed={boards.includes(b)} className={cx("rounded-full border px-2.5 py-1 text-[12px] font-semibold", boards.includes(b) ? "border-brand bg-brand text-white" : "border-edge-strong text-fg-2 hover:border-brand")}>{b}</button>
                  ))}</div></fieldset>
                <Field label="Cancellation"><Select value={s.refundable} onChange={(e) => set({ refundable: e.target.value }, false)} className="w-full">
                  <option value="">Any</option><option value="yes">Free cancellation only</option><option value="no">Non-refundable only</option></Select></Field>
                <Field label="Payment"><Select value={s.payment} onChange={(e) => set({ payment: e.target.value }, false)} className="w-full">
                  <option value="">Any</option><option value="prepay">Prepay</option><option value="pay_later">Pay later</option></Select></Field>
                <Field label="Compare offers by" hint={s.compare === "plan" ? "Only identical rate plans compete: same meal plan, refundability, cancellation deadline and payment." : "Suppliers compete within the same room, meal plan and refundability; each row keeps its own deadline and payment terms."}>
                  <Select value={s.compare} onChange={(e) => set({ compare: e.target.value }, false)} className="w-full">
                    <option value="group">Comparable group</option><option value="plan">Identical rate plan</option></Select></Field>
                <Field label="Supplier"><Select value={s.supplier} onChange={(e) => set({ supplier: e.target.value }, false)} className="w-full">
                  <option value="">All suppliers</option>{["S1", "S2", "S3", "S4", "S5", "S6"].map((c) => <option key={c} value={c}>{c}</option>)}</Select></Field>
                <Button variant="ghost" size="sm" onClick={() => set({ board: "", refundable: "", payment: "", supplier: "", nights: "3", compare: "group" }, false)}>Reset requirements</Button>
              </div>
            </Card>
          )}
        </div>
        <Card title={data ? <span className="flex flex-wrap items-center gap-2"><Link to={`/inventory/${s.type}/${s.id}`} className="hover:text-brand-ink">{data.name}</Link><Badge>{s.id}</Badge>{data.city_name && <span className="text-[12px] font-normal text-fg-3">{data.city_name}</span>}</span> : "Offers"}
          actions={s.type === "hotel" && s.id && <Segmented label="View" value={s.view as "table" | "api"} onChange={(v) => set({ view: v }, false)}
            options={[{ value: "table", label: <span className="inline-flex items-center gap-1"><Table2 size={13} />Comparison</span> }, { value: "api", label: <span className="inline-flex items-center gap-1"><Code2 size={13} />Clean Feed API</span> }]} />}>
          {!s.id ? <Empty title="Choose a product" body="Search on the left to compare its supplier offers." />
            : error ? <ErrorState error={error} onRetry={() => refetch()} />
            : s.view === "api" ? <ApiView q={api} id={s.id} nights={s.nights} />
            : !data || (isFetching && !data) ? <Skeleton className="h-80" />
            : <div className={isFetching ? "opacity-60 transition-opacity" : ""}>{s.type === "hotel" ? <HotelOffers data={data} /> : <ActivityOffers data={data} />}</div>}
        </Card>
      </div>
    </>
  );
}

function ApiView({ q, id, nights }: { q: any; id: string; nights: string }) {
  const [rtt, setRtt] = useState<number | null>(null);
  const call = async () => { const t = performance.now(); await q.refetch(); setRtt(performance.now() - t); };
  if (q.error) return <ErrorState error={q.error} />;
  if (!q.data) return <Skeleton className="h-80" />;
  const d = q.data;
  return (
    <div className="space-y-3">
      <p className="text-[13px] text-fg-2">API customers receive the same canonical record the portal shows: physical rooms, one offer per meal plan and cancellation term, a confirm probability and ranked fallback booking tokens. No matching or LLM work happens at request time.</p>
      <div className="flex flex-wrap items-center gap-3 rounded-lg bg-[#1F2330] px-3 py-2 font-mono text-[12px] text-white">
        <span className="font-bold text-accent">GET</span><span className="truncate">/api/v1/hotels/{id}/offers?nights={nights}</span>
        <span className="ml-auto text-white/70">server {d.meta.server_ms} ms{rtt !== null ? ` · round trip ${rtt.toFixed(0)} ms` : ""}</span>
        <Button size="sm" onClick={call}>Call again</Button>
      </div>
      <div className="flex flex-wrap gap-4 text-[12px] text-fg-3">
        <span>{d.meta.source_supplier_records} supplier records</span><span>{d.meta.source_supplier_rates} supplier rates</span><span>→ {d.rooms.length} rooms, {d.rooms.reduce((n: number, r: any) => n + r.offers.length, 0)} offers</span>
      </div>
      <pre className="max-h-[560px] overflow-auto rounded-lg border border-edge bg-panel-2 p-3 font-mono text-[12px] leading-relaxed text-fg-2 scroll-thin">{JSON.stringify(d, null, 2)}</pre>
    </div>
  );
}
