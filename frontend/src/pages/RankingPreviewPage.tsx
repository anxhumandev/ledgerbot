import { Link } from "react-router-dom";
import { qs } from "../lib/api";
import { useApi, useDebounced, useUrlState } from "../lib/hooks";
import { duration, inr, pct } from "../lib/fmt";
import { Badge, Card, Empty, ErrorState, Field, Input, Notice, PageHeader, Segmented, Select, Skeleton, SupplierChip } from "../ui/core";

const DEF = { cat: "hotel", persona: "riya", strategy: "relevance", area: "", q: "", stars: "0", offer: "expected_value", city: "" };

export default function RankingPreviewPage() {
  const [s, set] = useUrlState(DEF);
  const { data: opt } = useApi<any>("/ranking/options");
  const dq = useDebounced(s.q, 300);
  const hotelPath = s.cat === "hotel" ? `/ranking/hotels${qs({ persona: s.persona, strategy: s.strategy, area: s.area, q: dq, min_stars: s.stars, offer_policy: s.offer })}` : null;
  const actStrategy = ["relevance", "price", "reliability"].includes(s.strategy) ? s.strategy : "relevance";
  const actPath = s.cat === "activity" ? `/ranking/activities${qs({ q: dq, city: s.city, strategy: actStrategy })}` : null;
  const { data, error, isFetching, refetch } = useApi<any>(hotelPath ?? actPath);
  const strategies = s.cat === "hotel" ? opt?.hotel_strategies : opt?.activity_strategies;
  const persona = opt?.personas?.find((p: any) => p.id === s.persona);
  return (
    <>
      <PageHeader title="Search Ranking · Preview" description="See how a search result page would look for an agent profile and ranking strategy, with the selected eligible offer and why each result is placed where it is."
        actions={<Segmented label="Category" value={s.cat as "hotel" | "activity"} onChange={(v) => set({ cat: v, strategy: "relevance" })} options={[{ value: "hotel", label: "Hotels" }, { value: "activity", label: "Sightseeing" }]} />} />
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-[300px_minmax(0,1fr)]">
        <Card title="Search">
          <div className="space-y-3">
            <Field label="Query"><Input value={s.q} onChange={(e) => set({ q: e.target.value })} placeholder={s.cat === "hotel" ? "Property name (optional)" : "e.g. safari, burj, cruise"} /></Field>
            {s.cat === "hotel" ? (
              <>
                <Field label="Agent profile" hint={persona?.label ?? persona?.blurb ?? persona?.desc}>
                  <Select value={s.persona} onChange={(e) => set({ persona: e.target.value })} className="w-full">{opt?.personas?.map((p: any) => <option key={p.id} value={p.id}>{p.name}</option>)}</Select>
                </Field>
                <Field label="Area"><Select value={s.area} onChange={(e) => set({ area: e.target.value })} className="w-full"><option value="">All Dubai</option>{opt?.areas?.map((a: string) => <option key={a}>{a}</option>)}</Select></Field>
                <Field label="Minimum stars"><Select value={s.stars} onChange={(e) => set({ stars: e.target.value })} className="w-full">{["0", "3", "4", "5"].map((x) => <option key={x} value={x}>{x === "0" ? "Any" : `${x}★ and above`}</option>)}</Select></Field>
                <Field label="Offer selection"><Select value={s.offer} onChange={(e) => set({ offer: e.target.value })} className="w-full">
                  <option value="expected_value">Recommended (expected value, within cap)</option><option value="cheapest">Cheapest supplier copy</option></Select></Field>
              </>
            ) : (
              <Field label="City"><Select value={s.city} onChange={(e) => set({ city: e.target.value })} className="w-full"><option value="">All</option><option value="dubai">Dubai</option><option value="abu_dhabi">Abu Dhabi</option></Select></Field>
            )}
            <Field label="Ranking strategy">
              <div className="space-y-1.5">
                {strategies && Object.entries(strategies).map(([k, v]: any) => (
                  <label key={k} className={`flex cursor-pointer gap-2 rounded-lg border p-2 text-[13px] ${s.strategy === k || (s.cat === "activity" && actStrategy === k) ? "border-brand bg-brand-soft/50" : "border-edge hover:border-brand/40"}`}>
                    <input type="radio" name="strategy" checked={s.cat === "hotel" ? s.strategy === k : actStrategy === k} onChange={() => set({ strategy: k })} className="mt-0.5 accent-[var(--brand)]" />
                    <span><span className="font-semibold text-fg">{v.label}</span><span className="block text-[12px] text-fg-3">{v.desc}</span></span>
                  </label>
                ))}
              </div>
            </Field>
          </div>
        </Card>
        <Card title={data ? `${data.results.length} results · ${data.strategy_label ?? ""}` : "Results"}
          subtitle={s.cat === "hotel" ? (data?.kendall_tau != null && s.strategy !== "relevance" && s.strategy !== "price" ? `Kendall τ vs relevance-only ${data.kendall_tau} (guardrail ${opt?.guardrail}) · business weights scaled ×${data.business_scale}` : "Learned ranker (LambdaRank + position-bias correction)") : data?.model}>
          {error ? <ErrorState error={error} onRetry={() => refetch()} /> : !data ? <Skeleton className="h-96" /> : !data.results.length ? <Empty title="No results" body="Broaden the search." /> : (
            <ol className={`space-y-2 ${isFetching ? "opacity-60" : ""}`}>
              {s.cat === "hotel" ? data.results.map((r: any) => (
                <li key={r.tessera_id} className="flex gap-3 rounded-card border border-edge p-3">
                  <span className="num flex h-8 w-8 flex-none items-center justify-center rounded-full bg-panel-3 text-[13px] font-bold text-fg">{r.position}</span>
                  {r.hero ? <img src={r.hero} alt="" className="hidden h-[72px] w-[96px] flex-none rounded-lg object-cover sm:block" />
                    : <div aria-hidden className="hidden h-[72px] w-[96px] flex-none items-center justify-center rounded-lg bg-brand-soft text-[22px] font-bold text-brand sm:flex">{r.name[0]}</div>}
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2"><Link to={`/inventory/hotel/${r.tessera_id}`} className="text-[14px] font-semibold text-fg hover:text-brand-ink">{r.name}</Link>
                      <span className="text-[12px] text-fg-3">{"★".repeat(r.stars || 0)} · {r.location} · guests {r.review}</span>{r.platinum && <Badge tone="accent">Platinum</Badge>}</div>
                    <div className="mt-1 flex flex-wrap gap-1.5">{r.chips.map((c: string) => <span key={c} className="rounded-full bg-brand-soft px-2 py-0.5 text-[12px] text-brand-ink">{c}</span>)}</div>
                  </div>
                  {r.offer ? (
                    <div className="w-[230px] flex-none text-right text-[12px]">
                      <div className="num text-[16px] font-bold text-fg">{inr(r.offer.total)}<span className="text-[11px] font-normal text-fg-3"> / {r.offer.nights} nights</span></div>
                      <div className="truncate text-fg-2" title={r.offer.room}>{r.offer.room}</div>
                      <div className="truncate text-fg-3" title={r.offer.rate_plan}>{r.offer.rate_plan}</div>
                      <div className="mt-0.5 flex justify-end"><SupplierChip code={r.offer.supplier} name={r.offer.supplier_name} /></div>
                    </div>
                  ) : <div className="w-[230px] text-right text-[12px] text-fg-3">No eligible offer</div>}
                </li>
              )) : data.results.map((r: any) => (
                <li key={r.product_id} className="flex gap-3 rounded-card border border-edge p-3">
                  <span className="num flex h-8 w-8 flex-none items-center justify-center rounded-full bg-panel-3 text-[13px] font-bold text-fg">{r.position}</span>
                  <div className="min-w-0 flex-1">
                    <Link to={`/inventory/activity/${r.product_id}`} className="text-[14px] font-semibold text-fg hover:text-brand-ink">{r.name}</Link>
                    <div className="text-[12px] text-fg-3">{r.city} · {r.options} option{r.options > 1 ? "s" : ""}{r.duration_range ? ` · ${duration(r.duration_range[0])}${r.duration_range[1] !== r.duration_range[0] ? `–${duration(r.duration_range[1])}` : ""}` : ""}{r.inclusions.length ? ` · ${r.inclusions.join(", ")} options` : ""}</div>
                    <div className="mt-1 flex flex-wrap gap-1.5">{r.why.map((c: string) => <span key={c} className="rounded-full bg-brand-soft px-2 py-0.5 text-[12px] text-brand-ink">{c}</span>)}</div>
                  </div>
                  {r.offer && <div className="w-[180px] flex-none text-right text-[12px]"><div className="num text-[16px] font-bold text-fg">{inr(r.offer.adult)}<span className="text-[11px] font-normal text-fg-3"> / adult</span></div>
                    <div className="mt-0.5 flex justify-end"><SupplierChip code={r.offer.supplier} name={r.offer.supplier_name} /></div><div className="text-fg-3">{pct(r.offer.reliability, 1)} reliable</div></div>}
                </li>
              ))}
            </ol>
          )}
          {s.cat === "activity" && <Notice tone="neutral" className="mt-3">Sightseeing uses transparent rule-based scoring in this build; there is no learned sightseeing ranker yet.</Notice>}
        </Card>
      </div>
    </>
  );
}
