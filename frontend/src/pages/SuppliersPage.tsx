import { Upload } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { useApi } from "../lib/hooks";
import { ago, dateTime, num, pct } from "../lib/fmt";
import { Bar, Button, Card, ErrorState, PageHeader, SourceTag, StatusBadge, SupplierChip } from "../ui/core";
import { DataTable } from "../ui/table";

export default function SuppliersPage() {
  const nav = useNavigate();
  const { data, error, isLoading, refetch } = useApi<any>("/ops/suppliers");
  return (
    <>
      <PageHeader title="Suppliers" description="Every supplier integration: feed status, freshness, catalog coverage, data quality and fulfilment reliability."
        meta={<><SourceTag source="measured" /><span>listings, coverage, data issues</span><SourceTag source="simulated" /><span>confirmation and price-change rates (synthetic booking history + simulated bookings)</span></>}
        actions={<Button variant="primary" icon={<Upload size={14} />} onClick={() => nav("/suppliers/ingestion")}>Import supplier data</Button>} />
      <Card pad={false}>
        {error ? <ErrorState error={error} onRetry={() => refetch()} /> : (
          <DataTable rows={data?.items} loading={isLoading} rowKey={(r: any) => r.code} onRowClick={(r: any) => nav(`/suppliers/${r.code}`)}
            columns={[
              { key: "id", header: "ID", cell: (r: any) => <span className="font-mono text-[12px] text-fg-3">{r.code}</span> },
              { key: "name", header: "Supplier", cell: (r: any) => <div><SupplierChip code={r.code} name={r.name} /><div className="pl-3.5 text-[12px] text-fg-3">{r.persona}</div></div> },
              { key: "feed", header: "Feed status", cell: (r: any) => <StatusBadge status={r.feed_health} label={r.feed_health === "degraded" && r.simulated_fault ? "Degraded (simulated)" : undefined} /> },
              { key: "sync", header: "Last sync", cell: (r: any) => r.last_sync ? <span title={`${dateTime(r.last_sync)} (${r.last_sync_source})`}>{ago(r.last_sync)}</span> : <span className="text-fg-3">Never</span> },
              { key: "l", header: "Listings", align: "right", cell: (r: any) => <span className="num">{num(r.listings)}{r.activity_listings ? <span className="text-fg-3"> + {r.activity_listings}</span> : null}</span> },
              { key: "cov", header: "Catalog coverage", cell: (r: any) => <span className="inline-flex items-center gap-2"><span className="num w-12 text-right">{pct(r.coverage, 1)}</span><Bar value={r.coverage} className="w-16" /></span> },
              { key: "err", header: "Data issues", align: "right", cell: (r: any) => <span className={r.validation_errors ? "num font-semibold text-warn" : "num"}>{num(r.validation_errors)}</span> },
              { key: "conf", header: "Confirm rate", align: "right", cell: (r: any) => r.has_history ? <span className="num">{pct(r.confirm_rate, 1)}</span> : "—" },
              { key: "pj", header: "Price change", align: "right", cell: (r: any) => r.has_history ? <span className="num">{pct(r.price_change_rate, 1)}</span> : "—" },
              { key: "rel", header: "Reliability", align: "right", cell: (r: any) => r.has_history ? <span className="num font-semibold text-fg">{pct(r.reliability, 1)}</span> : <span className="text-fg-3">No history</span> },
            ]} />
        )}
      </Card>
      <p className="mt-3 text-[12px] text-fg-3">Data issues count supplier records with a missing address or coordinates, a pin more than 1 km from the consensus location, or a duplicate listing, plus rows rejected by imports. Reliability = confirm rate × (1 − price-change rate) × latency factor.</p>
    </>
  );
}
