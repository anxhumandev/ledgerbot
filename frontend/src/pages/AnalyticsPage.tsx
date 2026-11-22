import { useQueries } from "@tanstack/react-query";
import { Bar as RBar, BarChart, CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api } from "../lib/api";
import { tok } from "../lib/tokens";
import { useApi } from "../lib/hooks";
import { dateTime, inr, num, pct, SUPPLIER_COLOR, SUPPLIER_NAME } from "../lib/fmt";
import { Badge, Card, ErrorState, KeyValue, Metric, Notice, PageHeader, Skeleton, SourceTag } from "../ui/core";

const AXIS = { fontSize: 11, fill: tok("fg-3") };
const CODES = ["S1", "S2", "S3", "S4", "S5"];

export default function AnalyticsPage() {
  const { data: a, error, isLoading, refetch } = useApi<any>("/analytics");
  const bench = useApi<any>("/arena/benchmark", { staleTime: 5 * 60_000 });
  const cost = useApi<any>("/cost");
  const rel = useQueries({ queries: CODES.map((c) => ({ queryKey: [`/ops/suppliers/${c}/reliability`], queryFn: () => api(`/ops/suppliers/${c}/reliability`), staleTime: 5 * 60_000 })) });
  if (error) return <ErrorState error={error} onRetry={() => refetch()} />;
  if (isLoading || !a) return <div className="space-y-4"><Skeleton className="h-8 w-64" /><Skeleton className="h-64" /><Skeleton className="h-64" /></div>;
  const m = a.matching;
  const days = rel.every((q) => q.data) ? (rel[0].data as any).daily.map((d: any, i: number) => ({ day: `D${d.day + 1}`,
    ...Object.fromEntries(CODES.map((c, k) => [c, (rel[k].data as any).daily[i]?.confirm_rate * 100])) })) : [];
  const b = bench.data;
  return (
    <>
      <PageHeader title="Analytics" description="Matching quality, review workload, supplier reliability, consolidation, competitiveness and ranking quality. Every panel states whether its numbers are measured, synthetic, simulated or live."
        meta={<><SourceTag source="measured" /><span>held-out evaluation and catalog counts</span><SourceTag source="synthetic" /><span>booking history</span><SourceTag source="simulated" /><span>simulator and replay</span><SourceTag source="live" /><span>workspace records</span></>} />

      <h2 className="mb-2 mt-1 text-[15px] font-semibold text-fg">Matching quality</h2>
      <div className="grid grid-cols-2 gap-3 xl:grid-cols-6">
        <Metric label="Pair precision" value={pct(m.pairwise.precision, 2)} source="measured" />
        <Metric label="Pair recall" value={pct(m.pairwise.recall, 2)} source="measured" />
        <Metric label="Pair F1" value={m.pairwise.f1.toFixed(3)} source="measured" />
        <Metric label="B-cubed F1" value={m.bcubed.f1.toFixed(3)} source="measured" />
        <Metric label="Matcher AUC" value={m.auc.toFixed(4)} source="measured" />
        <Metric label="Consistency violations" value={num(m.consistency.total_violations)} hint={`Largest cluster ${m.consistency.largest_cluster}`} source="measured" />
      </div>
      <p className="mt-1.5 text-[12px] text-fg-3">{m.basis}. Auto-decisions alone: precision {pct(m.auto_only.precision, 2)}, recall {pct(m.auto_only.recall, 2)}.</p>

      <div className="mt-4 grid grid-cols-1 gap-4 xl:grid-cols-2">
        <Card title="Hotels vs sightseeing" actions={<SourceTag source="measured" />}>
          <div className="grid grid-cols-2 gap-4">
            <div><Badge tone="brand">Hotels</Badge><KeyValue cols={1} items={[["Property pair F1", a.by_category.hotel.pair_f1?.toFixed(3)], ["Room-pair F1", a.by_category.hotel.room_f1?.toFixed(3)],
              ["Wrong-room rate", `${pct(a.by_category.hotel.raw_wrong_room_rate, 2)} raw → ${pct(a.by_category.hotel.offer_wrong_room_rate, 2)} after LedgerBot`]]} /></div>
            <div><Badge tone="accent">Sightseeing</Badge><KeyValue cols={1} items={[["Product F1", a.by_category.sightseeing.product_f1?.toFixed(3)], ["Option F1", a.by_category.sightseeing.option_f1?.toFixed(3)],
              ["Method", "Exact attraction + tier rule, option keys"]]} /></div>
          </div>
        </Card>
        <Card title="False-merge monitoring" subtitle={`Current budget α = ${pct(a.risk.alpha, 2)}`} actions={<SourceTag source="measured" />}>
          <table className="w-full text-[13px]"><thead><tr className="border-b border-edge text-left text-[12px] text-fg-3"><th className="py-1.5 font-semibold">Budget α</th><th className="py-1.5 text-right font-semibold">Automated</th><th className="py-1.5 text-right font-semibold">Held-out false merges</th><th className="py-1.5 text-right font-semibold">Status</th></tr></thead>
            <tbody>{a.risk.curve.filter((_: any, i: number) => i % 5 === 0).map((r: any) => (
              <tr key={r.alpha} className="border-b border-edge last:border-0"><td className="num py-1.5">{pct(r.alpha, 2)}</td><td className="num py-1.5 text-right">{pct(r.automation, 1)}</td>
                <td className="num py-1.5 text-right">{r.test_merges ? pct(r.empirical_fmr, 2) : "—"}</td>
                <td className="py-1.5 text-right">{!r.certifiable ? <Badge>Not certifiable</Badge> : r.held ? <Badge tone="ok">Held</Badge> : <Badge tone="bad">Exceeded</Badge>}</td></tr>))}</tbody></table>
        </Card>
      </div>

      <div className="mt-4 grid grid-cols-1 gap-4 xl:grid-cols-2">
        <Card title="Review workload" actions={<SourceTag source="live" />}>
          <div className="grid grid-cols-4 gap-3">
            {[["Open", a.workload.cases.open], ["Escalated", a.workload.cases.escalated], ["Confirmed", a.workload.cases.confirmed], ["Rejected", a.workload.cases.rejected]].map(([k, v]) => (
              <div key={k as string} className="rounded-lg border border-edge p-2.5"><div className="text-[12px] text-fg-3">{k}</div><div className="num text-[18px] font-bold text-fg">{num(v as number)}</div></div>))}
          </div>
          {a.workload.per_day.length ? (
            <div className="mt-3 h-[180px]"><ResponsiveContainer><BarChart data={a.workload.per_day} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
              <CartesianGrid stroke={tok("edge")} vertical={false} /><XAxis dataKey="day" tick={AXIS} stroke={tok("edge-strong")} /><YAxis tick={AXIS} allowDecimals={false} width={30} stroke={tok("edge-strong")} /><Tooltip />
              <RBar dataKey="review.confirmed" name="Confirmed" stackId="a" fill={tok("ok")} /><RBar dataKey="review.rejected" name="Rejected" stackId="a" fill={tok("fg-3")} /><RBar dataKey="review.escalated" name="Escalated" stackId="a" fill={tok("bad")} />
            </BarChart></ResponsiveContainer></div>
          ) : <p className="mt-3 text-[13px] text-fg-3">No decisions recorded yet.</p>}
          {a.workload.by_user.length > 0 && <p className="mt-2 text-[12px] text-fg-3">By reviewer: {a.workload.by_user.map((u: any) => `${u.user} (${u.decisions})`).join(", ")}</p>}
        </Card>
        <Card title="Supplier confirm rate · 30 days" subtitle="Daily share of bookings confirmed" actions={<SourceTag source="synthetic" />}>
          {!days.length ? <Skeleton className="h-[220px]" /> : (
            <div className="h-[240px]"><ResponsiveContainer><LineChart data={days} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
              <CartesianGrid stroke={tok("edge")} vertical={false} /><XAxis dataKey="day" tick={AXIS} interval={4} stroke={tok("edge-strong")} />
              <YAxis domain={[90, 100]} tickFormatter={(v) => `${v}%`} tick={AXIS} width={40} stroke={tok("edge-strong")} /><Tooltip formatter={(v: any, n: any) => [`${Number(v).toFixed(1)}%`, SUPPLIER_NAME[n] ?? n]} />
              <Legend formatter={(v) => SUPPLIER_NAME[v] ?? v} wrapperStyle={{ fontSize: 12 }} />
              {CODES.map((c) => <Line key={c} dataKey={c} stroke={SUPPLIER_COLOR[c]} strokeWidth={1.8} dot={false} />)}
            </LineChart></ResponsiveContainer></div>
          )}
        </Card>
      </div>

      <div className="mt-4 grid grid-cols-1 gap-4 xl:grid-cols-3">
        <Card title="Catalog consolidation" subtitle="Hotel listings → canonical properties" actions={<SourceTag source="measured" />}>
          <div className="h-[220px]"><ResponsiveContainer><BarChart data={a.consolidation} layout="vertical" margin={{ left: 10, right: 10 }}>
            <XAxis type="number" tick={AXIS} stroke={tok("edge-strong")} /><YAxis type="category" dataKey="city" tick={AXIS} width={72} stroke={tok("edge-strong")} /><Tooltip />
            <RBar dataKey="listings" name="Listings" fill={tok("edge-strong")} /><RBar dataKey="canonical" name="Canonical" fill={tok("brand")} />
          </BarChart></ResponsiveContainer></div>
        </Card>
        <Card title="Offer competitiveness" actions={<SourceTag source="measured" />}>
          <KeyValue cols={1} items={[["Comparable groups", num(a.competitiveness.summary.groups)], ["Recommended = cheapest", pct(a.competitiveness.summary.cheapest_share, 1)],
            ["Average premium of recommendation", `${a.competitiveness.summary.avg_premium_pct?.toFixed(2)}%`], ["Largest premium", `${a.competitiveness.summary.max_premium_pct?.toFixed(2)}%`]]} />
        </Card>
        <Card title="Ranking quality" subtitle={a.ranking.source} actions={<SourceTag source="measured" />}>
          <KeyValue cols={1} items={[["NDCG@10, naive ranker", a.ranking.ndcg.naive.toFixed(3)], ["NDCG@10, position-bias corrected", <b>{a.ranking.ndcg.ipw.toFixed(3)}</b>],
            ["Search sessions", num(a.ranking.sessions ?? 0)], ["Randomised sessions (propensity)", num(a.ranking.randomized ?? 0)]]} />
        </Card>
      </div>

      <div className="mt-4 grid grid-cols-1 gap-4 xl:grid-cols-2">
        <Card title="LedgerBot vs an LLM-only pipeline" subtitle={b ? `${num(b.n_hotel)} hotel pairs and ${num(b.n_room)} room pairs from the held-out set` : undefined}
          actions={b?.baseline?.simulated ? <SourceTag source="simulated" /> : b?.baseline ? <SourceTag source="measured" /> : null}>
          {!b ? <Skeleton className="h-40" /> : (
            <>
              <table className="w-full text-[13px]"><thead><tr className="border-b border-edge text-left text-[12px] text-fg-3"><th className="py-1.5 font-semibold">Metric</th><th className="py-1.5 text-right font-semibold">LLM-only ({b.baseline_model})</th><th className="py-1.5 text-right font-semibold">LedgerBot</th></tr></thead>
                <tbody>{[["Hotel pair F1", b.baseline?.hotel_f1?.toFixed(3), b.tessera.hotel_f1?.toFixed(3)], ["Room-and-offer F1", b.baseline?.room_f1?.toFixed(3), b.tessera.room_f1?.toFixed(3)],
                  ["Consistency violations", b.baseline?.consistency_violations, b.tessera.consistency_violations], ["Largest wrong cluster", b.baseline?.largest_wrong_cluster, b.tessera.largest_wrong_cluster],
                  ["Cost per 1,000 pairs", b.baseline ? inr(b.baseline.cost_per_1000_inr) : null, inr(b.tessera.cost_per_1000_inr)]].map(([k, x, y]) => (
                  <tr key={k as string} className="border-b border-edge last:border-0"><td className="py-1.5">{k}</td><td className="num py-1.5 text-right">{x ?? "Not run"}</td><td className="num py-1.5 text-right font-semibold text-fg">{y ?? "—"}</td></tr>))}</tbody></table>
              <Notice tone={b.baseline?.simulated ? "sim" : "neutral"} className="mt-3">{!b.baseline ? "No LLM-only baseline run yet (make baseline, needs an API key)." : b.baseline.simulated
                ? "The LLM-only column is a simulated profile: stated error-rate assumptions applied to the hardest pairs. LedgerBot's column is measured."
                : `Measured run ${b.baseline.run_at}.`}</Notice>
            </>
          )}
        </Card>
        <Card title="LLM usage this session" actions={<SourceTag source="live" />}>
          {cost.data ? <KeyValue cols={2} items={[["LLM spend", inr(cost.data.tessera_llm_spend_inr)], [`LLM-only counterfactual${cost.data.counterfactual_estimated ? " (est.)" : ""}`, inr(cost.data.llm_only_counterfactual_inr)],
            ["Pairs scored", num(cost.data.pairs_processed)], ["LLM calls", num(cost.data.calls)], ["Cache hits", num(cost.data.cache_hits)], ["Adjudicator", cost.data.llm_enabled ? "On" : "Off (no API key)"]]} /> : <Skeleton className="h-32" />}
          {a.replay.last && <p className="mt-3 text-[12px] text-fg-3">Last commercial simulation: {pct(a.replay.last.lift_gp_per_search, 1)} gross profit per search (simulated).</p>}
        </Card>
      </div>
    </>
  );
}
