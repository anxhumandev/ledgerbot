import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ArrowDown, ArrowUp, Minus } from "lucide-react";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { put, qs } from "../lib/api";
import { useApi, useUrlState } from "../lib/hooks";
import { dateTime, inr, num } from "../lib/fmt";
import { toast } from "../lib/session";
import { Badge, Button, Card, ErrorState, Field, Input, Metric, Notice, PageHeader, Select, Skeleton, SourceTag } from "../ui/core";
import { ConfirmDialog } from "../ui/overlay";

const DEF = { persona: "mark", a: "relevance", b: "commercial", area: "", offer_a: "cheapest", offer_b: "expected_value" };

export default function RankingExperimentsPage() {
  const [s, set] = useUrlState(DEF);
  const { data: opt } = useApi<any>("/ranking/options");
  const { data, error, isFetching, refetch } = useApi<any>(`/ranking/compare${qs({ persona: s.persona, a: s.a, b: s.b, area: s.area, offer_a: s.offer_a, offer_b: s.offer_b })}`);
  const strat = opt?.hotel_strategies ?? {};
  const ndcg = data?.offline_quality?.ndcg;
  const moved = data?.rows?.filter((r: any) => r.delta !== null && r.delta !== 0).length ?? 0;
  const offerChanged = data?.rows?.filter((r: any) => r.offer_changed).length ?? 0;
  return (
    <>
      <PageHeader title="Search Ranking · Experiments" description="Compare two ranking strategies or offer-selection policies on the same search before running them on live traffic." />
      <Card className="mb-4">
        <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
          <Field label="Agent profile"><Select value={s.persona} onChange={(e) => set({ persona: e.target.value })} className="w-full">{opt?.personas?.map((p: any) => <option key={p.id} value={p.id}>{p.name}</option>)}</Select></Field>
          <Field label="Area"><Select value={s.area} onChange={(e) => set({ area: e.target.value })} className="w-full"><option value="">All Dubai</option>{opt?.areas?.map((a: string) => <option key={a}>{a}</option>)}</Select></Field>
          <Field label="Control (A)"><Select value={s.a} onChange={(e) => set({ a: e.target.value })} className="w-full">{Object.entries(strat).map(([k, v]: any) => <option key={k} value={k}>{v.label}</option>)}</Select></Field>
          <Field label="A · offers"><Select value={s.offer_a} onChange={(e) => set({ offer_a: e.target.value })} className="w-full"><option value="expected_value">Recommended</option><option value="cheapest">Cheapest copy</option></Select></Field>
          <Field label="Variant (B)"><Select value={s.b} onChange={(e) => set({ b: e.target.value })} className="w-full">{Object.entries(strat).map(([k, v]: any) => <option key={k} value={k}>{v.label}</option>)}</Select></Field>
          <Field label="B · offers"><Select value={s.offer_b} onChange={(e) => set({ offer_b: e.target.value })} className="w-full"><option value="expected_value">Recommended</option><option value="cheapest">Cheapest copy</option></Select></Field>
        </div>
      </Card>
      <div className="mb-4 grid grid-cols-2 gap-3 xl:grid-cols-4">
        <Metric label="Results that moved" value={data ? `${moved} / ${data.rows.length}` : "—"} hint="Top 10 positions" />
        <Metric label="Selected offer changed" value={data ? num(offerChanged) : "—"} hint="Different supplier, price or terms" />
        <Metric label="Rank agreement (Kendall τ)" value={data?.kendall_tau != null ? data.kendall_tau.toFixed(2) : "—"} hint="Over results present in both lists" />
        <Metric label="Offline NDCG@10" value={ndcg ? `${ndcg.naive.toFixed(3)} → ${ndcg.ipw.toFixed(3)}` : "—"} hint="Naive vs position-bias-corrected ranker" source="measured" />
      </div>
      <Card title="Before / after" subtitle={data ? `${strat[s.a]?.label} → ${strat[s.b]?.label}` : undefined} pad={false}>
        {error ? <ErrorState error={error} onRetry={() => refetch()} /> : !data ? <Skeleton className="m-4 h-80" /> : (
          <div className={`overflow-x-auto ${isFetching ? "opacity-60" : ""}`}>
            <table className="w-full min-w-[920px] text-[13px]">
              <thead><tr className="border-b border-edge bg-panel-2 text-left text-[12px] text-fg-3">
                <th className="px-3 py-2.5 font-semibold">B pos.</th><th className="px-3 py-2.5 font-semibold">Change</th><th className="px-3 py-2.5 font-semibold">Property</th>
                <th className="px-3 py-2.5 font-semibold">Offer in A</th><th className="px-3 py-2.5 font-semibold">Offer in B</th><th className="px-3 py-2.5 font-semibold">Why (B)</th></tr></thead>
              <tbody>
                {data.rows.map((r: any) => (
                  <tr key={r.tessera_id} className="border-b border-edge last:border-0">
                    <td className="num px-3 py-2.5 font-bold text-fg">{r.position_b}</td>
                    <td className="px-3 py-2.5">{r.delta === null ? <Badge tone="brand">New in top 10</Badge> : r.delta > 0 ? <span className="inline-flex items-center gap-1 text-ok"><ArrowUp size={14} />{r.delta}</span>
                      : r.delta < 0 ? <span className="inline-flex items-center gap-1 text-bad"><ArrowDown size={14} />{-r.delta}</span> : <span className="inline-flex items-center gap-1 text-fg-3"><Minus size={14} />0</span>}</td>
                    <td className="px-3 py-2.5"><Link to={`/inventory/hotel/${r.tessera_id}`} className="font-semibold text-fg hover:text-brand-ink">{r.name}</Link>{r.position_a && <div className="text-[11px] text-fg-3">was #{r.position_a}</div>}</td>
                    <td className="px-3 py-2.5 text-[12px]">{r.offer_a ? <><b className="num text-fg">{inr(r.offer_a.total)}</b> · {r.offer_a.supplier} · {r.offer_a.refundable ? "refundable" : "non-ref."}</> : "—"}</td>
                    <td className={`px-3 py-2.5 text-[12px] ${r.offer_changed ? "bg-accent-soft/50" : ""}`}>{r.offer_b ? <><b className="num text-fg">{inr(r.offer_b.total)}</b> · {r.offer_b.supplier} · {r.offer_b.refundable ? "refundable" : "non-ref."}</> : "—"}</td>
                    <td className="px-3 py-2.5"><div className="flex flex-wrap gap-1">{r.chips.slice(0, 3).map((c: string) => <span key={c} className="rounded-full bg-panel-3 px-2 py-0.5 text-[11px]">{c}</span>)}</div></td>
                  </tr>
                ))}
              </tbody>
            </table>
            {data.dropped.length > 0 && <div className="border-t border-edge px-3 py-2.5 text-[12px] text-fg-3">Left the top 10 in B: {data.dropped.map((d: any) => `${d.name} (#${d.position_a})`).join(", ")}</div>}
          </div>
        )}
      </Card>
      <div className="mt-4 grid grid-cols-1 gap-4 xl:grid-cols-2">
        <Weights opt={opt} />
        <Card title="Commercial impact" actions={<SourceTag source="simulated" />}>
          <p className="text-[13px] text-fg-2">Offline ranking quality above is measured against known true relevance on {num(data?.offline_quality?.sessions ?? opt?.sessions ?? 0)} simulated search sessions. Booking and profit effects are estimated by the commercial replay simulation, not measured on real traffic.</p>
          <Link to="/offers/optimization" className="mt-3 inline-block text-[13px] font-semibold text-brand-ink hover:underline">Open the commercial simulation →</Link>
          <Notice tone="neutral" className="mt-3">Recommended rollout: shadow mode, then a triggered A/B test on searches where the two rankings differ, then ramp.</Notice>
        </Card>
      </div>
    </>
  );
}

function Weights({ opt }: { opt: any }) {
  const { data: settings } = useApi<any>("/settings");
  const { data: me } = useApi<any>("/me");
  const qc = useQueryClient();
  const cur = settings?.settings?.rank_weights;
  const [w, setW] = useState<Record<string, string>>({});
  const [ask, setAsk] = useState(false);
  useEffect(() => { if (cur?.value) setW(Object.fromEntries(Object.entries(cur.value).map(([k, v]) => [k, String(v)]))); }, [cur?.value?.margin, cur?.value?.platinum, cur?.value?.risk]);
  const can = me?.user?.permissions?.includes("ranking.configure");
  const bad = Object.values(w).some((v) => v === "" || Number.isNaN(Number(v)) || Number(v) < 0 || Number(v) > 2);
  const dirty = cur && Object.entries(cur.value).some(([k, v]) => Number(w[k]) !== v);
  const save = useMutation({ mutationFn: (reason: string) => put("/settings/rank_weights", { value: Object.fromEntries(Object.entries(w).map(([k, v]) => [k, Number(v)])), reason }),
    onSuccess: () => { setAsk(false); toast({ tone: "success", title: "Ranking weights updated" }); qc.invalidateQueries(); },
    onError: (e: any) => { setAsk(false); toast({ tone: "error", title: "Could not update", body: e.message }); } });
  return (
    <Card title="Business weights" subtitle={cur?.updated_at ? `Last changed ${dateTime(cur.updated_at)}` : "Configuration defaults"}>
      <p className="mb-3 text-[13px] text-fg-2">Commercial and balanced strategies add these weights to learned relevance. If the result drifts too far from relevance (Kendall τ below {opt?.guardrail ?? 0.8}), the weights are scaled down automatically.</p>
      <div className="grid grid-cols-3 gap-3">
        {[["margin", "Margin"], ["platinum", "Platinum partner"], ["risk", "Reliability risk"]].map(([k, label]) => (
          <Field key={k} label={label}><Input type="number" step={0.05} min={0} max={2} value={w[k] ?? ""} disabled={!can} invalid={w[k] !== undefined && (Number(w[k]) < 0 || Number(w[k]) > 2)} onChange={(e) => setW({ ...w, [k]: e.target.value })} /></Field>
        ))}
      </div>
      {bad && <p className="mt-2 text-[12px] text-bad">Each weight must be between 0 and 2.</p>}
      <div className="mt-3 flex items-center gap-2"><Button variant="primary" disabled={!can || bad || !dirty} onClick={() => setAsk(true)}>Save weights</Button>
        {!can && <span className="text-[12px] text-fg-3">Revenue analysts and administrators can change ranking weights.</span>}</div>
      <ConfirmDialog open={ask} onClose={() => setAsk(false)} busy={save.isPending} title="Save ranking weights?" body="Commercial and balanced rankings use the new weights immediately." reason="Reason" reasonRequired onConfirm={(r) => save.mutate(r)} />
    </Card>
  );
}
