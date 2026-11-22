import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Play } from "lucide-react";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { post, put } from "../lib/api";
import { useApi } from "../lib/hooks";
import { dateTime, inr, num, pct } from "../lib/fmt";
import { toast } from "../lib/session";
import { Badge, Bar, Button, Card, ErrorState, Field, Input, KeyValue, Metric, Notice, PageHeader, Skeleton, SourceTag, SupplierChip } from "../ui/core";
import { ConfirmDialog } from "../ui/overlay";
import { DataTable } from "../ui/table";

export default function OfferOptimizationPage() {
  const { data: an, error, isLoading, refetch } = useApi<any>("/analytics");
  const { data: settings } = useApi<any>("/settings");
  const { data: me } = useApi<any>("/me");
  const qc = useQueryClient();
  const cap = settings?.settings?.price_cap_pct;
  const [value, setValue] = useState("");
  const [ask, setAsk] = useState(false);
  useEffect(() => { if (cap) setValue(String(cap.value)); }, [cap?.value]);
  const can = me?.user?.permissions?.includes("offers.configure");
  const save = useMutation({ mutationFn: (reason: string) => put("/settings/price_cap_pct", { value: Number(value), reason }),
    onSuccess: () => { setAsk(false); toast({ tone: "success", title: "Competitiveness cap updated", body: "Recommendations everywhere now use the new cap." }); qc.invalidateQueries(); },
    onError: (e: any) => { setAsk(false); toast({ tone: "error", title: "Could not update", body: e.message }); } });
  const invalid = value === "" || Number.isNaN(Number(value)) || Number(value) < 0 || Number(value) > 50;
  if (error) return <ErrorState error={error} onRetry={() => refetch()} />;
  const comp = an?.competitiveness;
  return (
    <>
      <PageHeader title="Offer Optimization" description="How LedgerBot chooses which supplier offer to show, the guardrails it must respect, and what that is worth in simulation." />
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-[minmax(0,5fr)_minmax(0,7fr)]">
        <Card title="Selection policy">
          <ol className="list-decimal space-y-1.5 pl-5 text-[13px] text-fg-2">
            <li>Only offers for the same physical room with the same meal plan and refundability compete.</li>
            <li>Paused suppliers are not eligible (<Link to="/suppliers/directory" className="text-brand-ink hover:underline">supplier configuration</Link>).</li>
            <li>An offer priced more than the <b>competitiveness cap</b> above the cheapest comparable offer is not eligible, whatever its margin.</li>
            <li>Among eligible offers, the highest expected value wins: P(book) × P(confirm at quoted price) × margin − (1 − P(confirm)) × ₹{num(settings?.failure_cost_inr ?? 2500)} failure cost.</li>
            <li>The shown price, cancellation deadline and payment terms always come from that one offer.</li>
          </ol>
          <div className="mt-5 max-w-[340px] space-y-2">
            <Field label="Competitiveness cap (%)" error={invalid ? "Enter a value between 0 and 50." : null}
              hint={cap?.updated_at ? `Last changed ${dateTime(cap.updated_at)} by ${cap.updated_by}` : "Default from configuration"}>
              <Input type="number" min={0} max={50} step={0.5} value={value} onChange={(e) => setValue(e.target.value)} disabled={!can} invalid={invalid} />
            </Field>
            <div className="flex items-center gap-2">
              <Button variant="primary" disabled={!can || invalid || Number(value) === cap?.value} onClick={() => setAsk(true)}>Apply</Button>
              {!can && <span className="text-[12px] text-fg-3">Revenue analysts and administrators can change this.</span>}
            </div>
          </div>
        </Card>
        <Card title="Competitiveness of recommendations" subtitle="All comparable offer groups with 2+ suppliers (Dubai rates)" actions={<SourceTag source="measured" />}>
          {isLoading || !comp ? <Skeleton className="h-40" /> : (
            <>
              <div className="grid grid-cols-3 gap-3">
                <Metric label="Groups" value={num(comp.summary.groups)} />
                <Metric label="Cheapest wins" value={pct(comp.summary.cheapest_share, 1)} hint="Recommended offer is also the cheapest" />
                <Metric label="Avg premium" value={`${comp.summary.avg_premium_pct?.toFixed(2)}%`} hint={`Max ${comp.summary.max_premium_pct?.toFixed(2)}%`} />
              </div>
              <div className="mt-4"><DataTable rows={comp.by_supplier} rowKey={(r: any) => r.code} dense
                columns={[
                  { key: "s", header: "Supplier", cell: (r: any) => <SupplierChip code={r.code} name={r.name} /> },
                  { key: "g", header: "Groups", align: "right", cell: (r: any) => <span className="num">{num(r.groups)}</span> },
                  { key: "w", header: "Recommended", cell: (r: any) => <span className="inline-flex items-center gap-2"><span className="num w-12 text-right">{pct(r.recommended / r.groups, 1)}</span><Bar value={r.recommended / r.groups} tone="accent" className="w-20" /></span> },
                  { key: "c", header: "Cheapest", cell: (r: any) => <span className="inline-flex items-center gap-2"><span className="num w-12 text-right">{pct(r.cheapest / r.groups, 1)}</span><Bar value={r.cheapest / r.groups} className="w-20" /></span> },
                ]} /></div>
            </>
          )}
        </Card>
      </div>
      <Replay />
      <ConfirmDialog open={ask} onClose={() => setAsk(false)} busy={save.isPending} title={`Set the competitiveness cap to ${value}%?`}
        body="Offer recommendations in the catalog, comparison, ranking preview and Clean Feed API change immediately." reason="Reason" reasonRequired onConfirm={(r) => save.mutate(r)} />
    </>
  );
}

function Replay() {
  const { data, refetch } = useApi<any>("/ops/simulation/replay", { refetchInterval: (q: any) => (q.state.data?.running ? 700 : false) });
  const { data: me } = useApi<any>("/me");
  const qc = useQueryClient();
  const can = me?.user?.permissions?.includes("simulation.run");
  const run = useMutation({ mutationFn: () => post("/ops/simulation/replay", { n: 50000 }), onSuccess: () => { setTimeout(() => refetch(), 300); qc.invalidateQueries({ queryKey: ["/analytics"] }); },
    onError: (e: any) => toast({ tone: "error", title: "Could not run", body: e.message }) });
  const r = data?.last;
  const rows = r ? [
    ["Searches", r.arms.raw.searches, r.arms.tessera.searches, (v: number) => num(v)],
    ["Bookings", r.arms.raw.bookings, r.arms.tessera.bookings, (v: number) => num(v)],
    ["Look-to-book", r.arms.raw.look_to_book, r.arms.tessera.look_to_book, (v: number) => pct(v, 2)],
    ["Gross profit", r.arms.raw.gross_profit, r.arms.tessera.gross_profit, (v: number) => inr(v, true)],
    ["Failed bookings", r.arms.raw.failed, r.arms.tessera.failed, (v: number) => num(v)],
    ["Wrong-room incidents", r.arms.raw.wrong_room, r.arms.tessera.wrong_room, (v: number) => num(v)],
  ] as const : [];
  return (
    <Card className="mt-4" title="Commercial simulation" subtitle="Replay simulated agent searches through today's raw shelf (every supplier copy, cheapest first) and LedgerBot's shelf (deduplicated, expected-value offer)"
      actions={<><Badge tone="sim">Simulated</Badge><Button variant="accent" icon={<Play size={14} />} loading={run.isPending || data?.running} disabled={!can} onClick={() => run.mutate()}>Run 50,000 searches</Button></>}>
      {!r ? <p className="text-[13px] text-fg-3">{data?.running ? "Running…" : "Not run yet in this session."}</p> : (
        <div className="space-y-3">
          <div className="overflow-x-auto"><table className="w-full min-w-[520px] text-[13px]">
            <thead><tr className="border-b border-edge text-left text-[12px] text-fg-3"><th className="py-2 font-semibold">Metric</th><th className="py-2 text-right font-semibold">Raw shelf</th><th className="py-2 text-right font-semibold">LedgerBot</th></tr></thead>
            <tbody>{rows.map(([k, a, b, f]) => <tr key={k} className="border-b border-edge last:border-0"><td className="py-2">{k}</td><td className="num py-2 text-right">{f(a as number)}</td><td className="num py-2 text-right font-semibold text-fg">{f(b as number)}</td></tr>)}</tbody>
          </table></div>
          <KeyValue cols={2} items={[["Gross profit per search", <b className="num text-accent-ink">{r.lift_gp_per_search >= 0 ? "+" : ""}{pct(r.lift_gp_per_search, 1)}</b>],
            ["Annualised at TBO scale (illustrative)", <span><b className="num">{inr(r.annualized_inr_illustrative, true)}</b> <span className="text-[12px] text-fg-3">{r.formula}</span></span>]]} />
          <Notice tone="sim">Simulated with a two-stage choice model calibrated to about 3% look-to-book and the suppliers' hidden reliability profiles. These are not measured booking outcomes. Any supplier fault simulation that is still active changes the result.</Notice>
        </div>
      )}
    </Card>
  );
}
