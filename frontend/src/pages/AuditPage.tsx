import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { qs } from "../lib/api";
import { useApi, useDebounced, useUrlState } from "../lib/hooks";
import { dateTime, num } from "../lib/fmt";
import { entityLink } from "../ui/activity";
import { Badge, Button, Card, ErrorState, Notice, PageHeader, SearchInput, Select } from "../ui/core";
import { Drawer } from "../ui/overlay";
import { DataTable, Pagination } from "../ui/table";

const DEF = { q: "", actor: "", action: "", entity_type: "", range: "", page: "1" };
const RANGES: Record<string, number> = { "1d": 86400, "7d": 7 * 86400, "30d": 30 * 86400 };

export default function AuditPage() {
  const [s, set, reset] = useUrlState(DEF);
  const [search, setSearch] = useState(s.q);
  const dq = useDebounced(search, 300);
  useEffect(() => { if (dq !== s.q) set({ q: dq }); }, [dq]);
  const since = s.range ? Math.floor(Date.now() / 1000 - RANGES[s.range]) : undefined;
  const { data, error, isFetching, refetch } = useApi<any>(`/audit${qs({ q: s.q, actor: s.actor, action: s.action, entity_type: s.entity_type, since, page: s.page, page_size: 50 })}`);
  const { data: users } = useApi<any[]>("/users");
  const [ev, setEv] = useState<any>(null);
  return (
    <>
      <PageHeader title="Quality & Audit" description="Every operational change: who did it, when, to what, the state before and after, the reason and the request ID. The log is append-only; the database rejects edits and deletions." />
      <Card pad={false}>
        <div className="flex flex-wrap items-center gap-2 border-b border-edge p-3">
          <SearchInput value={search} onChange={setSearch} className="w-full sm:w-[280px]" placeholder="Search entity, action, reason, event ID" label="Search audit log" />
          <Select aria-label="Actor" value={s.actor} onChange={(e) => set({ actor: e.target.value })}><option value="">All actors</option><option value="system">System</option>{users?.map((u) => <option key={u.id} value={u.id}>{u.name}</option>)}</Select>
          <Select aria-label="Action" value={s.action} onChange={(e) => set({ action: e.target.value })}><option value="">All actions</option>{data?.actions?.map((a: string) => <option key={a}>{a}</option>)}</Select>
          <Select aria-label="Entity type" value={s.entity_type} onChange={(e) => set({ entity_type: e.target.value })}>
            <option value="">All entities</option>{["review_case", "hotel", "activity", "supplier", "ingestion_job", "setting", "user", "workspace"].map((t) => <option key={t} value={t}>{t.replace("_", " ")}</option>)}</Select>
          <Select aria-label="Time range" value={s.range} onChange={(e) => set({ range: e.target.value })}><option value="">All time</option><option value="1d">Last 24 hours</option><option value="7d">Last 7 days</option><option value="30d">Last 30 days</option></Select>
          {Object.values(s).some((v, i) => i < 5 && v) && <Button variant="ghost" size="sm" onClick={() => { setSearch(""); reset(); }}>Reset</Button>}
          <span className="ml-auto text-[12px] text-fg-3">{num(data?.total ?? 0)} events</span>
        </div>
        {error ? <ErrorState error={error} onRetry={() => refetch()} /> : (
          <DataTable rows={data?.items} loading={isFetching} rowKey={(r: any) => r.event_id} onRowClick={setEv} dense
            columns={[
              { key: "ts", header: "Time", cell: (r: any) => <span className="num whitespace-nowrap">{dateTime(r.ts)}</span> },
              { key: "actor", header: "Actor", cell: (r: any) => <span><span className="font-semibold text-fg">{r.actor_name}</span><span className="block text-[11px] text-fg-3">{r.actor_role}</span></span> },
              { key: "action", header: "Action", cell: (r: any) => <span className="font-mono text-[12px]">{r.action}</span> },
              { key: "entity", header: "Entity", cell: (r: any) => { const l = entityLink(r.entity_type, r.entity_id); return <span><span className="text-[11px] text-fg-3">{r.entity_type}</span>{" "}{l ? <Link to={l} onClick={(e) => e.stopPropagation()} className="font-mono text-[12px] text-brand-ink hover:underline">{r.entity_id}</Link> : <span className="font-mono text-[12px]">{r.entity_id}</span>}</span>; } },
              { key: "reason", header: "Reason", cell: (r: any) => <span className="line-clamp-1 max-w-[280px]" title={r.reason ?? ""}>{r.reason ?? "—"}</span> },
              { key: "req", header: "Request", cell: (r: any) => <span className="font-mono text-[11px] text-fg-3">{r.request_id ?? "—"}</span> },
            ]} />
        )}
        {data && <Pagination page={Number(s.page)} pageSize={50} total={data.total} onPage={(p) => set({ page: String(p) }, false)} />}
      </Card>
      <Drawer open={!!ev} onClose={() => setEv(null)} title={ev ? `Event ${ev.event_id}` : ""} width={560}>
        {ev && (
          <div className="space-y-4 text-[13px]">
            <div className="grid grid-cols-2 gap-3">
              {[["Time", dateTime(ev.ts)], ["Actor", `${ev.actor_name} (${ev.actor_role})`], ["Action", ev.action], ["Entity", `${ev.entity_type} ${ev.entity_id}`], ["Request ID", ev.request_id ?? "—"], ["Event ID", ev.event_id]].map(([k, v]) => (
                <div key={k}><div className="text-[12px] text-fg-3">{k}</div><div className="break-words font-medium text-fg">{v}</div></div>))}
            </div>
            {ev.reason && <div><div className="text-[12px] text-fg-3">Reason</div><div className="text-fg">“{ev.reason}”</div></div>}
            <div className="grid grid-cols-1 gap-3">
              <div><div className="mb-1 text-[12px] text-fg-3">Previous state</div><pre className="overflow-auto rounded-lg bg-panel-2 p-3 font-mono text-[12px]">{ev.before ? JSON.stringify(ev.before, null, 2) : "—"}</pre></div>
              <div><div className="mb-1 text-[12px] text-fg-3">Updated state</div><pre className="overflow-auto rounded-lg bg-panel-2 p-3 font-mono text-[12px]">{ev.after ? JSON.stringify(ev.after, null, 2) : "—"}</pre></div>
            </div>
            <Notice tone="neutral">Audit events cannot be edited or deleted through the application or the database.</Notice>
            {entityLink(ev.entity_type, ev.entity_id) && <Link to={entityLink(ev.entity_type, ev.entity_id)!} className="text-[13px] font-semibold text-brand-ink hover:underline">Open {ev.entity_type.replace("_", " ")} →</Link>}
          </div>
        )}
      </Drawer>
    </>
  );
}
