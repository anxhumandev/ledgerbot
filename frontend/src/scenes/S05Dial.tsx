import { useCallback, useEffect, useRef, useState } from "react";
import { Area, CartesianGrid, ComposedChart, Line, ReferenceLine, ResponsiveContainer, XAxis, YAxis } from "recharts";
import { Caption, Card, Chip, Cite, SceneHeader, Skeleton, Stat } from "../design/primitives";
import { Dial } from "../design/Dial";
import { useApp } from "../app/store";
import { api } from "../lib/api";
import { formatINR, groupIN, pct } from "../lib/format";
import { useFetch } from "../lib/hooks";

export default function DialScene() {
  const { data: curve } = useFetch<any>("/risk/curve");
  const [alpha, setAlpha] = useState<number | null>(null);
  const [row, setRow] = useState<any>(null);
  const pending = useRef<{ alpha: number; apply: boolean }[]>([]);
  const showToast = useApp((s) => s.showToast);
  const inflight = useRef(false);
  useEffect(() => {
    if (curve && alpha === null) { setAlpha(curve.alpha); setRow(curve.current); }
  }, [curve]);

  const fetchRow = useCallback(async (a: number, apply = false) => {
    const queue = pending.current;
    if (queue.length && !queue[queue.length - 1].apply) queue.pop();
    queue.push({ alpha: a, apply });
    if (inflight.current) return;
    inflight.current = true;
    try {
      while (queue.length) {
        const next = queue.shift()!;
        try {
          const result = await api(`/risk/at?alpha=${next.alpha.toFixed(5)}${next.apply ? "&apply=true" : ""}`);
          if (!queue.length) setRow(result);
        } catch {
          if (next.apply) showToast("Could not save the risk setting. Adjust the dial to retry.", "clay");
        }
      }
    } finally { inflight.current = false; }
  }, [showToast]);

  const onChange = (a: number) => { setAlpha(a); fetchRow(a); };
  const onCommit = (a: number) => fetchRow(a, true);

  if (!curve || alpha === null || !row) return <Skeleton className="w-full h-full" />;
  const data = curve.dense.map((r: any) => ({ x: Math.log10(r.alpha * 100), alpha: r.alpha, automation: r.automation * 100, review: r.review_rate * 100,
    merges: r.auto_accept_rate * 100 }));
  const held = row.held;
  return (
    <div className="h-full flex flex-col">
      <SceneHeader headline="You choose the risk. We guarantee it." subline="Turn the dial to set the maximum false-merge rate. Thresholds are re-certified on calibration data and checked on held-out hotels." />
      <div className="grid grid-cols-[minmax(0,1fr)_400px_520px] gap-8 flex-1 min-h-0 items-center">
        <Card className="p-6 h-[600px] flex flex-col">
          <Caption>Automation vs guaranteed risk · held-out test</Caption>
          <div className="flex gap-5 mt-2 text-[13px]">
            <span className="flex items-center gap-2"><span className="w-4 h-0.5 bg-lagoon" />auto-decided</span>
            <span className="flex items-center gap-2"><span className="w-4 h-2.5 bg-amber-soft border border-amber" />review volume (right axis)</span>
          </div>
          <div className="flex-1 mt-2">
            <ResponsiveContainer width="100%" height="100%">
              <ComposedChart data={data} margin={{ top: 10, right: 10, left: 0, bottom: 10 }}>
                <CartesianGrid stroke="var(--line)" vertical={false} />
                <XAxis dataKey="x" type="number" domain={["dataMin", "dataMax"]} ticks={[-1, Math.log10(0.25), Math.log10(0.5), 0, Math.log10(2), Math.log10(5)]}
                  tickFormatter={(v) => `${(10 ** v).toFixed(10 ** v < 1 ? 2 : 0)}%`} tick={{ fill: "var(--ink-3)", fontSize: 12 }} stroke="var(--line)" />
                <YAxis yAxisId="a" domain={[80, 100]} tickFormatter={(v) => `${v}%`} tick={{ fill: "var(--ink-3)", fontSize: 12 }} stroke="var(--line)" width={48} />
                <YAxis yAxisId="r" orientation="right" domain={[0, "auto"]} tickFormatter={(v) => `${v.toFixed(1)}%`} tick={{ fill: "var(--ink-3)", fontSize: 12 }} stroke="var(--line)" width={48} />
                <Area yAxisId="r" type="stepAfter" dataKey="review" stroke="var(--amber)" fill="var(--amber-soft)" strokeWidth={1.5} isAnimationActive={false} />
                <Line yAxisId="a" type="stepAfter" dataKey="automation" stroke="var(--lagoon)" strokeWidth={3} dot={false} isAnimationActive={false} />
                <ReferenceLine yAxisId="a" x={Math.log10(alpha * 100)} stroke="var(--ink)" strokeDasharray="4 4" />
              </ComposedChart>
            </ResponsiveContainer>
          </div>
          <div className="text-[12px] text-ink-3">x: guaranteed max false-merge rate α (log scale)</div>
        </Card>
        <div className="flex flex-col items-center">
          <Dial value={alpha} min={0.001} max={0.05} onChange={onChange} onCommit={onCommit} size={260}
            format={(v) => `${(v * 100).toFixed(v < 0.01 ? 2 : 1)}%`} />
          {!row.certifiable && (
            <div className="mt-4 text-center text-[14px] text-[color:var(--amber-ink)] max-w-[340px]">
              Not certifiable with {groupIN(row.cal_units_total)} audited property pairs: needs ≥ {groupIN(row.n_min)} clean auto-merges. Tessera refuses to auto-merge rather than pretend.
            </div>
          )}
        </div>
        <div className="grid grid-cols-1 gap-5">
          <Card className="p-5"><Stat caption="Auto-decided" value={row.automation * 100} format={(v) => `${v.toFixed(2)}%`} tone="lagoon" size={52}
            sub={`${pct(row.auto_accept_rate, 1)} auto-merged · rest auto-rejected`} /></Card>
          <Card className="p-5"><Stat caption="Human reviews / 10k pairs" value={row.reviews_per_10k} format={(v) => v.toFixed(0)} tone="amber" size={52} /></Card>
          <Card className="p-5">
            <Stat caption="Empirical false merges on held-out test" value={row.test_merges ? row.empirical_fmr * 100 : "—"} format={(v) => `${v.toFixed(2)}%`} size={52}
              sub={`${row.test_false_merges} of ${groupIN(row.test_merges)} property merges`} />
            <div className="mt-3">
              <Chip variant={!row.certifiable || !row.test_merges ? "amber" : held ? "sage" : "clay"}>{!row.certifiable ? "No certified auto-merge threshold" : !row.test_merges ? "No held-out merges" : held ? `≤ α ✓ Guarantee held` : `> α ✗ Guarantee violated on this split`}</Chip>
            </div>
          </Card>
          <Card className="p-5"><Stat caption="Ops cost / month (illustrative)" value={row.ops_cost_month_inr} format={(v) => formatINR(v, { compact: true })} size={40}
            sub="Monthly candidate pairs × review rate × labour cost per review" /></Card>
        </div>
      </div>
      <div className="mt-2">
        <Cite>Learn-then-Test risk control (Angelopoulos et al., 2021) · fixed-sequence testing with Clopper–Pearson bounds · δ = {row.delta} · calibration n = {groupIN(row.cal_n)} record pairs / {groupIN(row.cal_units_total)} property pairs · risk counted per property pair</Cite>
      </div>
    </div>
  );
}
