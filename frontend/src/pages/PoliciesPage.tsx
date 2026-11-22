import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { CartesianGrid, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { put } from "../lib/api";
import { tok } from "../lib/tokens";
import { useApi, useDebounced } from "../lib/hooks";
import { dateTime, inr, num, pct } from "../lib/fmt";
import { toast } from "../lib/session";
import { Badge, Button, Card, ErrorState, KeyValue, Metric, Notice, PageHeader, Skeleton, SourceTag } from "../ui/core";
import { ConfirmDialog } from "../ui/overlay";

const AXIS = { fontSize: 11, fill: tok("fg-3") };

export default function PoliciesPage() {
  const { data, error, isLoading, refetch } = useApi<any>("/matching/policy");
  const { data: me } = useApi<any>("/me");
  const qc = useQueryClient();
  const [alpha, setAlpha] = useState<number | null>(null);
  const [confirm, setConfirm] = useState(false);
  useEffect(() => { if (data && alpha === null) setAlpha(data.alpha); }, [data]);
  const da = useDebounced(alpha, 200);
  const preview = useApi<any>(da !== null && data && Math.abs(da - data.alpha) > 1e-9 ? `/matching/policy/preview?alpha=${da}` : null);
  const save = useMutation({
    mutationFn: (reason: string) => put("/settings/alpha", { value: alpha, reason }),
    onSuccess: () => { setConfirm(false); toast({ tone: "success", title: "Risk budget updated", body: "Thresholds re-certified; the review queue now reflects the new band." }); qc.invalidateQueries(); },
    onError: (e: any) => { setConfirm(false); toast({ tone: "error", title: "Could not update", body: e.message }); },
  });
  if (error) return <ErrorState error={error} onRetry={() => refetch()} />;
  if (isLoading || !data || alpha === null) return <Skeleton className="h-96" />;
  const row = preview.data ?? data.current;
  const canEdit = me?.user?.permissions?.includes("matching.configure");
  const curve = data.curve.map((r: any) => ({ alpha: r.alpha * 100, automation: r.automation * 100, review: r.review_rate * 100,
    empirical: r.test_merges ? r.empirical_fmr * 100 : null, certifiable: r.certifiable }));
  return (
    <>
      <PageHeader title="Matching Policies"
        description="Choose the maximum share of automatic merges that may be wrong. LedgerBot re-certifies its thresholds with Learn-then-Test (Clopper–Pearson bounds, 95% confidence) and checks the result on hotels the model never saw."
        meta={<><span>Last changed {data.updated.updated_at ? dateTime(data.updated.updated_at) : "never (default)"}</span><SourceTag source="measured" /></>} />
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-[minmax(0,5fr)_minmax(0,7fr)]">
        <Card title="Risk budget (α)" subtitle="Guaranteed maximum false-merge rate among automatic merges">
          <div className="flex items-baseline gap-3"><span className="num text-[34px] font-bold text-fg">{pct(alpha, 2)}</span>
            {Math.abs(alpha - data.alpha) > 1e-9 && <Badge tone="warn">Preview · current {pct(data.alpha, 2)}</Badge>}</div>
          <input type="range" min={Math.log(0.001)} max={Math.log(0.05)} step={0.01} value={Math.log(alpha)} disabled={!canEdit}
            onChange={(e) => setAlpha(Number(Math.exp(Number(e.target.value)).toFixed(5)))} aria-label="Risk budget alpha" className="mt-3 w-full accent-[var(--brand)]" />
          <div className="flex justify-between text-[11px] text-fg-3"><span>0.1% · more review</span><span>5% · more automation</span></div>
          {!row.certifiable && <Notice tone="warn" className="mt-3">Not certifiable at this budget with the current calibration audit: LedgerBot will not auto-merge and sends every candidate merge to review.</Notice>}
          <div className="mt-4 grid grid-cols-2 gap-3">
            <Metric label="Decided automatically" value={pct(row.automation, 1)} />
            <Metric label="Human reviews / 10k pairs" value={num(row.reviews_per_10k)} />
            <Metric label="Held-out false merges" value={row.test_merges ? pct(row.empirical_fmr, 2) : "—"}
              hint={row.test_merges ? (row.held ? <span className="text-ok">Within budget ✓</span> : <span className="text-bad">Exceeds budget</span>) : "No held-out merges"} />
            <Metric label="Review cost / month" value={inr(row.ops_cost_month_inr, true)} hint="Illustrative: 1.2M pairs, 1.5 min, ₹450/h" source="assumption" />
          </div>
          <div className="mt-4 flex items-center gap-2">
            <Button variant="primary" disabled={!canEdit || Math.abs(alpha - data.alpha) < 1e-9} onClick={() => setConfirm(true)}>Apply policy</Button>
            <Button variant="ghost" disabled={Math.abs(alpha - data.alpha) < 1e-9} onClick={() => setAlpha(data.alpha)}>Discard</Button>
            {!canEdit && <span className="text-[12px] text-fg-3">Only administrators can change the matching policy.</span>}
          </div>
        </Card>
        <Card title="Automation vs guaranteed risk" subtitle="Each point is re-certified on calibration data and checked on held-out hotels">
          <div className="h-[300px]">
            <ResponsiveContainer>
              <LineChart data={curve} margin={{ top: 8, right: 16, bottom: 8, left: 0 }}>
                <CartesianGrid stroke={tok("edge")} vertical={false} />
                <XAxis dataKey="alpha" type="number" scale="log" domain={[0.1, 5]} ticks={[0.1, 0.25, 0.5, 1, 2, 5]} tickFormatter={(v) => `${v}%`} tick={AXIS} stroke={tok("edge-strong")} />
                <YAxis yAxisId="a" domain={[0, 100]} tickFormatter={(v) => `${v}%`} tick={AXIS} stroke={tok("edge-strong")} width={44} />
                <YAxis yAxisId="e" orientation="right" domain={[0, 5]} tickFormatter={(v) => `${v}%`} tick={AXIS} stroke={tok("edge-strong")} width={40} />
                <Tooltip formatter={(v: any, n: any) => [`${Number(v).toFixed(2)}%`, n]} labelFormatter={(l) => `α = ${Number(l).toFixed(2)}%`} />
                <Line yAxisId="a" dataKey="automation" name="Automated" stroke={tok("brand")} strokeWidth={2} dot={false} />
                <Line yAxisId="e" dataKey="empirical" name="Held-out false merges" stroke={tok("accent")} strokeWidth={2} dot={false} connectNulls />
                <Line yAxisId="e" dataKey="alpha" name="Budget (α)" stroke={tok("fg-3")} strokeDasharray="4 4" dot={false} />
                <ReferenceLine yAxisId="a" x={alpha * 100} stroke={tok("fg")} strokeDasharray="2 2" />
              </LineChart>
            </ResponsiveContainer>
          </div>
          <div className="mt-2 flex flex-wrap gap-4 text-[12px] text-fg-3">
            <span><span className="mr-1 inline-block h-0.5 w-4 align-middle bg-brand" />Automated (left)</span>
            <span><span className="mr-1 inline-block h-0.5 w-4 align-middle bg-accent" />Held-out false merges (right)</span>
            <span><span className="mr-1 inline-block h-0.5 w-4 border-t border-dashed border-fg-3 align-middle" />Budget α (right)</span>
          </div>
        </Card>
      </div>
      <div className="mt-4 grid grid-cols-1 gap-4 xl:grid-cols-2">
        <Card title="Decision routing">
          <KeyValue cols={2} items={[
            ["Auto-merge when", `p ≥ ${row.tau_accept?.toFixed(3) ?? "disabled"}`], ["Auto-reject when", `p ≤ ${row.tau_reject?.toFixed(3) ?? "disabled"}`],
            ["Lost-match budget (β)", pct(data.beta, 1)], ["Confidence (1 − δ)", pct(1 - data.delta, 0)],
            ["Calibration audit", `${num(data.calibration.pairs)} pairs, ${num(data.calibration.units)} properties`],
            ["Uncertain pairs", data.llm_enabled ? `LLM adjudicator (${data.adjudicator_model}), then human` : "Human review (LLM adjudicator off)"],
          ]} />
        </Card>
        <Card title="Pipeline build routing" subtitle="How the candidate pairs of the build were decided" actions={<SourceTag source="measured" />}>
          <KeyValue cols={3} items={Object.entries(data.routes).map(([k, v]) => [{ auto_merge: "Auto-merged", auto_reject: "Auto-rejected", review: "Human review", llm: "LLM" }[k] ?? k, num(v as number)])} />
        </Card>
      </div>
      <ConfirmDialog open={confirm} onClose={() => setConfirm(false)} busy={save.isPending} confirmLabel="Apply policy" title={`Set α to ${pct(alpha, 2)}?`}
        body={<>Automation becomes about {pct(row.automation, 1)} of candidate pairs. New pairs inside the review band are added to the Match Review queue. The change is audited.</>}
        reason="Reason for the change" reasonRequired onConfirm={(r) => save.mutate(r)} />
    </>
  );
}
