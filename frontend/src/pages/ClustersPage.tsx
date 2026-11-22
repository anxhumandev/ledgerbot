import { FlaskConical } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import MatchTester from "../features/MatchTester";
import { qs } from "../lib/api";
import { useApi, useDebounced, useUrlState } from "../lib/hooks";
import { num, pct } from "../lib/fmt";
import { Button, Card, Confidence, CopyId, ErrorState, Metric, PageHeader, SearchInput, SourceTag, StatusBadge, SupplierChip } from "../ui/core";
import { Drawer } from "../ui/overlay";
import { DataTable, Pagination } from "../ui/table";

export default function ClustersPage() {
  const nav = useNavigate();
  const [s, set] = useUrlState({ q: "", sort: "confidence", order: "asc", page: "1" });
  const [search, setSearch] = useState(s.q);
  const dq = useDebounced(search, 300);
  useEffect(() => { if (dq !== s.q) set({ q: dq }); }, [dq]);
  const [tester, setTester] = useState(false);
  const { data, error, isFetching, refetch } = useApi<any>(`/matching/clusters${qs({ q: s.q, sort: s.sort, order: s.order, page: s.page, page_size: 25 })}`);
  const { data: an } = useApi<any>("/analytics", { staleTime: 60_000 });
  const mt = an?.matching;
  return (
    <>
      <PageHeader title="Clusters" description="Canonical properties formed from two or more supplier listings, weakest evidence first, so analysts can audit the merges the engine is least sure about."
        actions={<Button variant="primary" icon={<FlaskConical size={14} />} onClick={() => setTester(true)}>Test a supplier record</Button>} />
      <div className="mb-4 grid grid-cols-2 gap-3 xl:grid-cols-4">
        <Metric label="Pair precision" value={mt ? pct(mt.pairwise.precision, 2) : "—"} hint="Held-out test hotels" source="measured" />
        <Metric label="Pair recall" value={mt ? pct(mt.pairwise.recall, 2) : "—"} hint="Held-out test hotels" source="measured" />
        <Metric label="Consistency violations" value={mt ? num(mt.consistency.total_violations) : "—"} hint="Transitivity and one-listing-per-supplier" source="measured" />
        <Metric label="Candidate recall" value={mt?.blocking?.recall != null ? pct(mt.blocking.recall, 2) : "—"} hint={mt?.blocking?.reduction_ratio != null ? `Work cut by ${pct(mt.blocking.reduction_ratio, 2)}` : undefined} source="measured" />
      </div>
      <Card pad={false} title="Multi-supplier records" actions={<SourceTag source="measured" />}>
        <div className="border-b border-edge p-3"><SearchInput value={search} onChange={setSearch} className="max-w-[320px]" placeholder="Search properties" label="Search clusters" /></div>
        {error ? <ErrorState error={error} onRetry={() => refetch()} /> : (
          <DataTable rows={data?.items} loading={isFetching} rowKey={(r: any) => r.id} onRowClick={(r: any) => nav(`/inventory/hotel/${r.id}?tab=evidence`)}
            sort={{ key: s.sort, order: s.order as any }} onSort={(k) => set({ sort: k, order: s.sort === k && s.order === "asc" ? "desc" : "asc" })}
            columns={[
              { key: "id", header: "Canonical ID", cell: (r: any) => <CopyId value={r.id} /> },
              { key: "name", header: "Property", sortKey: "name", cell: (r: any) => <Link to={`/inventory/hotel/${r.id}`} onClick={(e) => e.stopPropagation()} className="font-semibold text-fg hover:text-brand-ink">{r.name}</Link> },
              { key: "city", header: "City", sortKey: "city_name", cell: (r: any) => r.city_name },
              { key: "sup", header: "Suppliers", sortKey: "n_suppliers", cell: (r: any) => <span className="flex gap-1.5">{r.suppliers.map((c: string) => <SupplierChip key={c} code={c} compact />)}</span> },
              { key: "lst", header: "Listings", sortKey: "n_listings", align: "right", cell: (r: any) => <span className="num">{r.n_listings}</span> },
              { key: "conf", header: "Weakest link", sortKey: "confidence", cell: (r: any) => <Confidence p={r.confidence} /> },
              { key: "st", header: "Status", cell: (r: any) => <StatusBadge status={r.status} /> },
            ]} />
        )}
        {data && <Pagination page={Number(s.page)} pageSize={25} total={data.total} onPage={(p) => set({ page: String(p) }, false)} />}
      </Card>
      <Drawer open={tester} onClose={() => setTester(false)} title="Test a supplier record" width={620}><MatchTester /></Drawer>
    </>
  );
}
