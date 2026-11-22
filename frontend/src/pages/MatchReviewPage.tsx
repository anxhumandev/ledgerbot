import { useMutation, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, ArrowUpRight, Check, ChevronRight, CornerUpLeft, Flag, MessageSquarePlus, SkipForward, UserPlus, X } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { ApiError, newIdempotencyKey, post, qs } from "../lib/api";
import { typing, useApi, useDebounced } from "../lib/hooks";
import { ago, dateTime, num, pct } from "../lib/fmt";
import { toast, useSession } from "../lib/session";
import { ActivityTimeline } from "../ui/activity";
import { Badge, Button, Card, CopyId, cx, Empty, ErrorState, Notice, PageHeader, SearchInput, Select, Skeleton, StatusBadge, SupplierChip } from "../ui/core";
import { DecisionZones, EvidenceBars, FieldCompare } from "../ui/evidence";
import { ConfirmDialog } from "../ui/overlay";

type Action = "confirm" | "reject" | "escalate" | "reopen" | null;

export default function MatchReviewPage() {
  const [params, setParams] = useSearchParams();
  const caseId = params.get("case");
  const [status, setStatus] = useState("open,escalated");
  const [priority, setPriority] = useState("");
  const [assignee, setAssignee] = useState("");
  const [source, setSource] = useState("");
  const [search, setSearch] = useState("");
  const dq = useDebounced(search, 250);
  const userId = useSession((s) => s.userId);
  const list = useApi<any>(`/review/cases${qs({ status, priority, assignee: assignee === "me" ? userId : assignee, q: dq, source, page_size: 200 })}`);
  const items: any[] = list.data?.items ?? [];
  const select = (id: string | null) => setParams((p) => { const n = new URLSearchParams(p); id ? n.set("case", id) : n.delete("case"); return n; }, { replace: true });
  useEffect(() => { if (!caseId && items.length) select(items[0].id); }, [caseId, items.length]);
  const idx = items.findIndex((c) => c.id === caseId);
  const next = () => { const n = items[idx + 1] ?? items.find((c) => c.id !== caseId); if (n) select(n.id); };
  const counts = list.data?.counts ?? {};

  return (
    <>
      <PageHeader title="Match Review"
        description="Pairs the engine would not decide alone: the certified review band at the current risk budget, plus ambiguous listings from supplier imports. Decisions change the canonical catalog and are recorded in the audit trail."
        meta={<>
          <Badge tone="warn">{num(counts.open ?? 0)} open</Badge><Badge tone="bad">{num(counts.escalated ?? 0)} escalated</Badge>
          <Badge tone="ok">{num(counts.confirmed ?? 0)} confirmed</Badge><Badge>{num(counts.rejected ?? 0)} rejected</Badge>
          <Link to="/matching/policies" className="text-brand-ink hover:underline">Review band policy →</Link>
        </>} />
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[320px_minmax(0,1fr)]">
        <Card pad={false} className="lg:sticky lg:top-0 lg:max-h-[calc(100vh-190px)] lg:overflow-hidden lg:flex lg:flex-col">
          <div className="space-y-2 border-b border-edge p-3">
            <SearchInput value={search} onChange={setSearch} placeholder="Property name or case ID" label="Search cases" />
            <div className="grid grid-cols-2 gap-2">
              <Select aria-label="Status" value={status} onChange={(e) => setStatus(e.target.value)}>
                <option value="open,escalated">To decide</option><option value="open">Open</option><option value="escalated">Escalated</option>
                <option value="confirmed,rejected">Decided</option><option value="all">All</option>
              </Select>
              <Select aria-label="Priority" value={priority} onChange={(e) => setPriority(e.target.value)}>
                <option value="">Any priority</option><option value="high">High</option><option value="medium">Medium</option><option value="low">Low</option>
              </Select>
              <Select aria-label="Assignment" value={assignee} onChange={(e) => setAssignee(e.target.value)}>
                <option value="">Anyone</option><option value="me">Assigned to me</option><option value="unassigned">Unassigned</option>
              </Select>
              <Select aria-label="Source" value={source} onChange={(e) => setSource(e.target.value)}>
                <option value="">All sources</option><option value="review_band">Review band</option><option value="ingestion">Supplier import</option>
              </Select>
            </div>
          </div>
          <div className="flex items-center justify-between px-3 py-2 text-[12px] text-fg-3"><span>{num(list.data?.total ?? 0)} cases</span><span>Most uncertain first</span></div>
          <ul className="flex-1 overflow-y-auto scroll-thin" aria-label="Review queue">
            {list.isLoading && Array.from({ length: 6 }).map((_, i) => <li key={i} className="px-3 py-3"><Skeleton className="h-12" /></li>)}
            {!list.isLoading && !items.length && <li><Empty title="Queue is clear" body="No cases match these filters." /></li>}
            {items.map((c) => (
              <li key={c.id}>
                <button onClick={() => select(c.id)} aria-current={c.id === caseId}
                  className={cx("w-full border-l-[3px] px-3 py-2.5 text-left transition-colors", c.id === caseId ? "border-brand bg-brand-soft/60" : "border-transparent hover:bg-panel-2")}>
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-[11px] text-fg-3">{c.id}</span>
                    <StatusBadge status={c.status === "open" ? c.priority : c.status} label={c.status === "open" ? `${c.priority[0].toUpperCase()}${c.priority.slice(1)}` : undefined} />
                    <span className="num ml-auto text-[12px] font-semibold text-fg">p {c.p.toFixed(3)}</span>
                  </div>
                  <div className="mt-1 truncate text-[13px] font-semibold text-fg">{c.name_a}</div>
                  <div className="truncate text-[13px] text-fg-2">↔ {c.name_b}</div>
                  <div className="mt-1 flex items-center gap-2 text-[11px] text-fg-3">
                    <span>{c.city}</span>·<span>{c.source === "ingestion" ? "Import" : "Review band"}</span>
                    {c.assignee_name && <>·<span>{c.assignee_name}</span></>}
                    {c.mapping.merge_conflict_suppliers?.length > 0 && <span className="text-bad">· supplier conflict</span>}
                  </div>
                </button>
              </li>
            ))}
          </ul>
        </Card>
        {caseId ? <CaseWorkspace key={caseId} caseId={caseId} onNext={next} hasNext={items.length > 1} /> : <Card><Empty title="Select a case" body="Choose a case from the queue to compare the two supplier records." /></Card>}
      </div>
    </>
  );
}

function CaseWorkspace({ caseId, onNext, hasNext }: { caseId: string; onNext: () => void; hasNext: boolean }) {
  const { data: c, error, isLoading, refetch } = useApi<any>(`/review/cases/${caseId}`, { placeholderData: undefined });
  const { data: me } = useApi<any>("/me");
  const qc = useQueryClient();
  const [action, setAction] = useState<Action>(null);
  const [note, setNote] = useState("");
  const idemKey = useMemo(() => newIdempotencyKey(), [caseId, c?.version]);
  const can = (p: string) => me?.user?.permissions?.includes(p);
  const open = c && (c.status === "open" || c.status === "escalated");

  const afterChange = (title: string, body?: string) => { toast({ tone: "success", title, body }); qc.invalidateQueries(); };
  const onError = (e: unknown) => {
    const err = e as ApiError;
    toast({ tone: "error", title: err.code === "stale_version" || err.code === "already_decided" ? "This case changed" : "Action failed", body: err.message });
    if (err.status === 409) refetch();
  };
  const decide = useMutation({
    mutationFn: ({ decision, reason }: { decision: string; reason: string }) =>
      post(`/review/cases/${caseId}/decision`, { decision, reason, version: c.version }, { idempotencyKey: idemKey }),
    onSuccess: (r: any, v) => {
      setAction(null);
      const ch = r.catalog_change;
      afterChange(v.decision === "confirm" ? "Match confirmed" : v.decision === "reject" ? "Match rejected" : "Case escalated",
        ch?.absorbed ? `${ch.absorbed} merged into ${ch.tessera_id}.` : ch?.created ? `Record split out as ${ch.created}.` : v.decision === "escalate" ? "Visible to administrators in the escalated queue." : "Catalog already reflected this decision.");
    },
    onError: (e) => { setAction(null); onError(e); },
  });
  const reopen = useMutation({
    mutationFn: (reason: string) => post(`/review/cases/${caseId}/reopen`, { reason }),
    onSuccess: () => { setAction(null); afterChange("Decision reverted", "The catalog change was undone and the case is open again."); },
    onError: (e) => { setAction(null); onError(e); },
  });
  const assign = useMutation({ mutationFn: (uid: string | null) => post(`/review/cases/${caseId}/assign`, { assignee: uid }), onSuccess: () => afterChange("Assignment updated"), onError });
  const addNote = useMutation({ mutationFn: () => post(`/review/cases/${caseId}/notes`, { body: note }), onSuccess: () => { setNote(""); afterChange("Note added"); }, onError });

  useEffect(() => {
    const on = (e: KeyboardEvent) => {
      if (typing() || e.ctrlKey || e.metaKey || e.altKey || action) return;
      if (!open || !can("review.decide")) { if (e.key.toLowerCase() === "n" && hasNext) onNext(); return; }
      const k = e.key.toLowerCase();
      if (k === "c" && !c.mapping.merge_conflict_suppliers?.length) setAction("confirm");
      else if (k === "x") setAction("reject");
      else if (k === "e") setAction("escalate");
      else if (k === "n" && hasNext) onNext();
    };
    window.addEventListener("keydown", on);
    return () => window.removeEventListener("keydown", on);
  }, [c, action, open, me]);

  if (error) return <Card><ErrorState error={error} onRetry={() => refetch()} /></Card>;
  if (isLoading || !c) return <Card><Skeleton className="h-[420px]" /></Card>;
  const m = c.mapping;
  const conflict = m.merge_conflict_suppliers?.length > 0;
  const decided = !open;
  return (
    <div className="grid grid-cols-1 gap-4 2xl:grid-cols-[minmax(0,1fr)_380px]">
      <div className="min-w-0 space-y-4">
        <Card>
          <div className="flex flex-wrap items-start gap-3">
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-center gap-2"><CopyId value={c.id} /><StatusBadge status={c.status} /><StatusBadge status={c.priority} label={`${c.priority} priority`} />
                <Badge>{c.source === "ingestion" ? "From supplier import" : "Review band"}</Badge><Badge>{c.match_type}</Badge></div>
              <h2 className="mt-2 text-[16px] font-semibold text-fg">{c.a.name} <span className="font-normal text-fg-3">↔</span> {c.b.name}</h2>
              <div className="mt-1 text-[12px] text-fg-3">Opened {ago(c.created_at)} · {c.city}{c.assignee_name ? ` · assigned to ${c.assignee_name}` : " · unassigned"}</div>
            </div>
            <div className="w-full max-w-[340px]">
              <div className="mb-1 flex items-baseline justify-between"><span className="text-[12px] text-fg-3">Calibrated match probability</span><span className="num text-[18px] font-bold text-fg">{c.p.toFixed(3)}</span></div>
              <DecisionZones p={c.p} tauAccept={c.policy.tau_accept} tauReject={c.policy.tau_reject} />
            </div>
          </div>
          <div className="mt-4 space-y-2">
            <Notice tone={m.same_property ? "brand" : "neutral"}>
              Current mapping: {m.same_property ? <>both records belong to <Link className="font-semibold underline" to={`/inventory/hotel/${m.property_a}`}>{m.property_a_name} ({m.property_a})</Link></>
                : <>separate properties, <Link className="font-semibold underline" to={`/inventory/hotel/${m.property_a}`}>{m.property_a}</Link> and <Link className="font-semibold underline" to={`/inventory/hotel/${m.property_b}`}>{m.property_b}</Link></>}.
              {decided ? "" : c.source === "review_band" ? " Provisional: the pipeline build resolved this pair with a simulated reviewer. Your decision replaces it." : " Created by the import as a separate property until reviewed."}
            </Notice>
            {conflict && !decided && <Notice tone="bad">Confirming would put two listings from {m.merge_conflict_suppliers.join(", ")} in one property, which the catalog does not allow. Reject the match, or escalate so the duplicate listing can be resolved first.</Notice>}
          </div>
        </Card>

        <Card title="Side-by-side comparison" subtitle="Fields aligned; differences highlighted" pad={false}>
          <FieldCompare diffs={c.diffs}
            headA={<span className="flex items-center gap-2"><SupplierChip code={c.a.supplier} name={c.a.supplier_name} /><span className="font-mono text-[11px] font-normal">{c.a.record_id}</span></span>}
            headB={<span className="flex items-center gap-2"><SupplierChip code={c.b.supplier} name={c.b.supplier_name} /><span className="font-mono text-[11px] font-normal">{c.b.record_id}</span></span>} />
        </Card>

        <Card>
          {decided ? (
            <div className="flex flex-wrap items-center gap-3">
              <div className="min-w-0 flex-1 text-[13px]">
                <div className="font-semibold text-fg">{c.status === "confirmed" ? "Confirmed as the same property" : c.status === "rejected" ? "Rejected: different properties" : c.status}</div>
                <div className="text-fg-3">by {c.decided_by_name ?? c.decided_by} · {dateTime(c.decided_at)}{c.decision_reason ? ` · “${c.decision_reason}”` : ""}</div>
              </div>
              {can("review.decide") && <Button icon={<CornerUpLeft size={14} />} onClick={() => setAction("reopen")}>Reopen and undo</Button>}
              {hasNext && <Button variant="primary" icon={<ChevronRight size={14} />} onClick={onNext}>Next case</Button>}
            </div>
          ) : (
            <div className="flex flex-wrap items-center gap-2">
              <Button variant="primary" icon={<Check size={15} />} disabled={!can("review.decide") || conflict} onClick={() => setAction("confirm")} title={conflict ? "Blocked by a supplier conflict" : "Shortcut: C"}>Confirm match</Button>
              <Button variant="danger" icon={<X size={15} />} disabled={!can("review.decide")} onClick={() => setAction("reject")} title="Shortcut: X">Reject match</Button>
              <Button icon={<Flag size={14} />} disabled={!can("review.decide") || c.status === "escalated"} onClick={() => setAction("escalate")} title="Shortcut: E">Escalate</Button>
              <Button variant="ghost" icon={<SkipForward size={14} />} disabled={!hasNext} onClick={onNext} title="Shortcut: N">Skip</Button>
              <span className="ml-auto text-[12px] text-fg-3">{can("review.decide") ? "Shortcuts: C confirm · X reject · E escalate · N next" : `Your role (${me?.user?.role_label}) can add notes but not decide.`}</span>
            </div>
          )}
        </Card>
      </div>

      <div className="space-y-4">
        <Card title="Matching explanation" subtitle="Evidence for and against, from the same model that scored the pair">
          <EvidenceBars explain={c.explain} />
        </Card>
        <Card title="Policy">
          <dl className="grid grid-cols-2 gap-3 text-[13px]">
            <div><dt className="text-[12px] text-fg-3">Risk budget α</dt><dd className="num font-semibold text-fg">{pct(c.policy.alpha, 1)}</dd></div>
            <div><dt className="text-[12px] text-fg-3">Pair band</dt><dd className="font-semibold text-fg">{{ auto_merge: "Auto-merge", auto_reject: "Auto-reject", uncertain: "Review" }[c.policy.band as string] ?? c.policy.band}</dd></div>
            <div><dt className="text-[12px] text-fg-3">Auto-merge at</dt><dd className="num text-fg">p ≥ {c.policy.tau_accept?.toFixed(3) ?? "disabled"}</dd></div>
            <div><dt className="text-[12px] text-fg-3">Auto-reject at</dt><dd className="num text-fg">p ≤ {c.policy.tau_reject?.toFixed(3) ?? "disabled"}</dd></div>
          </dl>
          <p className="mt-3 text-[12px] text-fg-3">Thresholds are certified with Learn-then-Test so that at most α of automatic merges are wrong (95% confidence). Anything between them comes here.</p>
        </Card>
        <Card title="Assignment & notes">
          <div className="mb-3 flex items-center gap-2">
            <span className="text-[13px] text-fg-2">{c.assignee_name ? `Assigned to ${c.assignee_name}` : "Unassigned"}</span>
            {can("review.assign") && (c.assignee === me?.user?.id
              ? <Button size="sm" variant="ghost" onClick={() => assign.mutate(null)} loading={assign.isPending}>Unassign</Button>
              : <Button size="sm" icon={<UserPlus size={13} />} onClick={() => assign.mutate(me.user.id)} loading={assign.isPending}>Assign to me</Button>)}
          </div>
          <ul className="mb-3 space-y-2">
            {c.notes.map((n: any) => <li key={n.id} className="rounded-lg bg-panel-2 px-3 py-2 text-[13px]"><div className="text-fg">{n.body}</div><div className="mt-0.5 text-[11px] text-fg-3">{n.author_name} · {ago(n.created_at)}</div></li>)}
          </ul>
          {can("review.note") && (
            <form onSubmit={(e) => { e.preventDefault(); if (note.trim()) addNote.mutate(); }} className="space-y-2">
              <label htmlFor="note" className="sr-only">Add a note</label>
              <textarea id="note" value={note} onChange={(e) => setNote(e.target.value)} rows={2} maxLength={2000} placeholder="Add context for other analysts"
                className="w-full rounded-lg border border-edge-strong bg-panel px-3 py-2 text-[13px] outline-none focus:border-brand focus:shadow-[var(--focus)]" />
              <Button size="sm" type="submit" icon={<MessageSquarePlus size={13} />} disabled={!note.trim()} loading={addNote.isPending}>Add note</Button>
            </form>
          )}
        </Card>
        <Card title="Case history"><ActivityTimeline events={c.history} compact /></Card>
      </div>

      <ConfirmDialog open={action === "confirm"} onClose={() => setAction(null)} busy={decide.isPending} confirmLabel="Confirm match"
        title="Confirm these records are the same property?"
        body={m.same_property ? "The catalog already maps them together; confirming makes that a verified human decision." : <>This merges <b>{m.property_b}</b> into <b>{m.property_a}</b>. Supplier listings, rooms and offers of both become one canonical record. You can undo it from this case.</>}
        reason="Reason (optional)" onConfirm={(r) => decide.mutate({ decision: "confirm", reason: r })} />
      <ConfirmDialog open={action === "reject"} onClose={() => setAction(null)} busy={decide.isPending} confirmLabel="Reject match" tone="danger"
        title="Reject this match?" body={m.same_property ? <>This splits <b>{c.b.record_id}</b> out of <b>{m.property_a}</b> into its own canonical record.</> : "The records stay separate and the pair is marked as different."}
        reason="Why are these different properties?" reasonRequired onConfirm={(r) => decide.mutate({ decision: "reject", reason: r })} />
      <ConfirmDialog open={action === "escalate"} onClose={() => setAction(null)} busy={decide.isPending} confirmLabel="Escalate"
        title="Escalate this case?" body="The mapping stays as it is and the case moves to the escalated queue for a senior reviewer or administrator."
        reason="What needs a second opinion?" reasonRequired onConfirm={(r) => decide.mutate({ decision: "escalate", reason: r })} />
      <ConfirmDialog open={action === "reopen"} onClose={() => setAction(null)} busy={reopen.isPending} confirmLabel="Reopen and undo"
        title="Reopen this case?" body="Any catalog change this decision made is reverted and the case returns to the open queue."
        reason="Why is the decision being corrected?" reasonRequired onConfirm={(r) => reopen.mutate(r)} />
    </div>
  );
}
