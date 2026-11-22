import { Download, ExternalLink, FilterX } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { qs } from "../lib/api";
import { useApi, useDebounced, useUrlState } from "../lib/hooks";
import { ago, dateTime, num } from "../lib/fmt";
import { Badge, Bar, Button, Card, Confidence, CopyId, ErrorState, PageHeader, SearchInput, Segmented, Select, StatusBadge, SupplierChip } from "../ui/core";
import { type Column, ColumnPicker, DataTable, Pagination } from "../ui/table";

const DEFAULTS = { q: "", country: "", city: "", supplier: "", status: "", quality: "", conf: "", sort: "relevance", order: "asc", page: "1", page_size: "25" };
const CONF: Record<string, [number | null, number | null]> = { "": [null, null], low: [0, 0.9], mid: [0.9, 0.99], high: [0.99, 1] };
const STATUS_ORDER = ["verified", "needs_review", "low_confidence", "single_source", "new"];

function loadHidden(kind: string): Set<string> {
  try {
    return new Set(JSON.parse(localStorage.getItem(`lb.cols.${kind}`) ?? '["updated","cat"]'));
  } catch {
    return new Set(["updated", "cat"]);
  }
}

export default function InventoryPage({ kind }: { kind: "hotel" | "activity" }) {
  const nav = useNavigate();
  const [s, set, reset] = useUrlState(DEFAULTS);
  const [search, setSearch] = useState(s.q);
  const dq = useDebounced(search, 300);
  useEffect(() => { if (dq !== s.q) set({ q: dq, sort: dq ? "relevance" : s.sort === "relevance" ? "name" : s.sort }); }, [dq]);
  const [hidden, setHidden] = useState(() => loadHidden(kind));
  useEffect(() => { try { localStorage.setItem(`lb.cols.${kind}`, JSON.stringify([...hidden])); } catch { /* ignore */ } }, [hidden, kind]);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [cmin, cmax] = CONF[s.conf] ?? [null, null];
  const sort = s.sort === "relevance" && !s.q ? "name" : s.sort;
  const path = `/inventory${qs({ type: kind, q: s.q, country: s.country, city: s.city, supplier: s.supplier, status: s.status, quality: s.quality,
    conf_min: cmin, conf_max: cmax, sort, order: s.order, page: s.page, page_size: s.page_size })}`;
  const { data, error, isFetching, refetch } = useApi<any>(path);
  useEffect(() => setSelected(new Set()), [path]);
  const filtered = Object.entries(s).some(([k, v]) => !["sort", "order", "page", "page_size"].includes(k) && v);

  const toggleSort = (key: string) => set({ sort: key, order: s.sort === key && s.order === "asc" ? "desc" : key === "name" || key === "city_name" ? "asc" : "desc" }, true);
  const open = (r: any) => nav(`/inventory/${kind}/${r.id}`);

  const columns: Column<any>[] = useMemo(() => [
    { key: "id", header: "Canonical ID", sortKey: "id", cell: (r) => <CopyId value={r.id} /> },
    { key: "name", header: kind === "hotel" ? "Property" : "Experience", sortKey: "name", cell: (r) => (
      <Link to={`/inventory/${kind}/${r.id}`} onClick={(e) => e.stopPropagation()} className="block min-w-[200px] max-w-[320px]">
        <span className="block truncate font-semibold text-fg hover:text-brand-ink">{r.name}</span>
        {r.subcategory && <span className="text-[12px] text-fg-3">{r.subcategory}</span>}
      </Link>) },
    { key: "loc", header: "Location", sortKey: "city_name", hideable: true, cell: (r) => (
      <span className="block min-w-[140px]"><span className="block text-fg-2">{r.area ? `${r.area}, ` : ""}{r.city_name}</span><span className="text-[12px] text-fg-3">{r.country}</span></span>) },
    { key: "cat", header: "Category", hideable: true, cell: (r) => <Badge tone={r.category === "Hotel" ? "brand" : "accent"}>{r.category}</Badge> },
    { key: "sup", header: "Suppliers", sortKey: "n_suppliers", align: "right", hideable: true, cell: (r) => (
      <span className="inline-flex items-center justify-end gap-2" title={r.suppliers.join(", ")}>
        <span className="hidden gap-1 2xl:flex">{r.suppliers.slice(0, 5).map((c: string) => <SupplierChip key={c} code={c} compact />)}</span>
        <span className="num font-semibold text-fg">{r.n_suppliers}</span>
      </span>) },
    { key: "lst", header: "Listings", sortKey: "n_listings", align: "right", hideable: true, cell: (r) => <span className="num">{num(r.n_listings)}</span> },
    { key: "conf", header: "Match confidence", sortKey: kind === "hotel" ? "confidence" : undefined, hideable: true, cell: (r) =>
      kind === "hotel" ? <Confidence p={r.confidence} /> : <span className="text-[12px] text-fg-3" title="Products are formed by an exact rule, not a probability">{r.match_rule}</span> },
    { key: "q", header: "Quality", sortKey: "quality", hideable: true, cell: (r) => r.quality === null ? "—" : (
      <span className="inline-flex items-center gap-2"><span className="num w-7 text-right">{r.quality}</span>
        <Bar value={r.quality / 100} tone={r.quality >= 85 ? "ok" : r.quality >= 60 ? "warn" : "bad"} className="w-14" /></span>) },
    { key: "status", header: "Status", sortKey: "status", hideable: true, cell: (r) => <StatusBadge status={r.status} /> },
    { key: "updated", header: "Last updated", sortKey: "updated_at", hideable: true, cell: (r) => <span title={dateTime(r.updated_at)}>{ago(r.updated_at)}</span> },
    { key: "act", header: <span className="sr-only">Actions</span>, align: "right", cell: (r) => (
      <Link to={`/inventory/${kind}/${r.id}`} onClick={(e) => e.stopPropagation()} aria-label={`Open ${r.name}`} className="inline-flex rounded-full p-1.5 text-fg-3 hover:bg-panel-3 hover:text-brand-ink"><ExternalLink size={15} /></Link>) },
  ], [kind]);

  const exportSelected = () => {
    const rows = (data?.items ?? []).filter((r: any) => selected.has(r.id));
    const head = ["id", "name", "city", "country", "category", "suppliers", "listings", "confidence", "quality", "status"];
    const esc = (v: any) => `"${String(v ?? "").replace(/"/g, '""')}"`;
    const csv = [head.join(","), ...rows.map((r: any) => [r.id, r.name, r.city_name, r.country, r.category, r.suppliers.join(" "), r.n_listings, r.confidence, r.quality, r.status_label].map(esc).join(","))].join("\n");
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob([csv], { type: "text/csv" }));
    a.download = `ledgerbot-${kind}-selection.csv`;
    a.click();
  };

  return (
    <>
      <PageHeader title="Inventory Catalog"
        description={kind === "hotel"
          ? "Canonical properties consolidated from every supplier feed. Open a record to see its supplier listings, rooms, rate plans and matching evidence."
          : "Canonical experiences grouped by attraction and access tier, with options that keep inclusions, time slots and private/shared tours apart."}
        actions={<Segmented label="Product category" value={kind} onChange={(v) => nav(`/inventory/${v === "hotel" ? "hotels" : "sightseeing"}`)}
          options={[{ value: "hotel", label: "Hotels" }, { value: "activity", label: "Sightseeing" }]} />} />

      <Card pad={false}>
        <div className="flex flex-wrap items-center gap-2 border-b border-edge p-3">
          <SearchInput value={search} onChange={setSearch} className="w-full sm:w-[300px]"
            placeholder={kind === "hotel" ? "Name, ID or any supplier's spelling" : "Experience name or ID"} label="Search inventory" />
          <Select aria-label="Country" value={s.country} onChange={(e) => set({ country: e.target.value })}>
            <option value="">All countries</option>{data?.facets.countries.map((c: string) => <option key={c}>{c}</option>)}
          </Select>
          <Select aria-label="City" value={s.city} onChange={(e) => set({ city: e.target.value })}>
            <option value="">All cities</option>{data?.facets.cities.map((c: any) => <option key={c.id} value={c.id}>{c.name}</option>)}
          </Select>
          <Select aria-label="Supplier" value={s.supplier} onChange={(e) => set({ supplier: e.target.value })}>
            <option value="">All suppliers</option>{data?.facets.suppliers.map((c: string) => <option key={c} value={c}>{c}</option>)}
          </Select>
          <Select aria-label="Quality" value={s.quality} onChange={(e) => set({ quality: e.target.value })}>
            <option value="">Any quality</option><option value="high">High (85+)</option><option value="medium">Medium (60–84)</option><option value="low">Low (&lt;60)</option>
          </Select>
          {kind === "hotel" && (
            <Select aria-label="Match confidence" value={s.conf} onChange={(e) => set({ conf: e.target.value })}>
              <option value="">Any confidence</option><option value="low">Below 0.90</option><option value="mid">0.90–0.99</option><option value="high">0.99 and above</option>
            </Select>
          )}
          {filtered && <Button variant="ghost" size="sm" icon={<FilterX size={14} />} onClick={() => { setSearch(""); reset(); }}>Reset filters</Button>}
          <div className="ml-auto flex items-center gap-2">
            {selected.size > 0 && <Button size="sm" icon={<Download size={14} />} onClick={exportSelected}>Export {selected.size} selected</Button>}
            <ColumnPicker columns={columns} hidden={hidden} onChange={setHidden} />
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-1.5 border-b border-edge px-3 py-2">
          <button onClick={() => set({ status: "" })} className={`rounded-full px-2.5 py-1 text-[12px] font-semibold ${!s.status ? "bg-brand text-white" : "text-fg-3 hover:bg-panel-3"}`}>All</button>
          {STATUS_ORDER.filter((k) => data?.status_counts?.[k] || s.status === k).map((k) => (
            <button key={k} onClick={() => set({ status: s.status === k ? "" : k })}
              className={`rounded-full px-2.5 py-1 text-[12px] font-semibold ${s.status === k ? "bg-brand text-white" : "text-fg-3 hover:bg-panel-3"}`}>
              {{ verified: "Verified", needs_review: "Needs review", low_confidence: "Low confidence", single_source: "Single source", new: "New" }[k]}
              <span className="num ml-1 opacity-80">{num(data?.status_counts?.[k] ?? 0)}</span>
            </button>
          ))}
        </div>
        {error ? <ErrorState error={error} onRetry={() => refetch()} /> : (
          <DataTable rows={data?.items} columns={columns} rowKey={(r) => r.id} loading={isFetching} onRowClick={open}
            sort={{ key: sort, order: s.order as "asc" | "desc" }} onSort={toggleSort} hidden={hidden} selected={selected} onSelect={setSelected} />
        )}
        {data && <Pagination page={Number(s.page)} pageSize={Number(s.page_size)} total={data.total}
          onPage={(p) => set({ page: String(p) }, false)} onPageSize={(n) => set({ page_size: String(n) })} />}
      </Card>
    </>
  );
}
