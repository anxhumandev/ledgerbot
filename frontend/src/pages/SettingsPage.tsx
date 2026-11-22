import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { patch, post, put } from "../lib/api";
import { useApi } from "../lib/hooks";
import { dateTime, pct } from "../lib/fmt";
import { toast } from "../lib/session";
import { Badge, Button, Card, ErrorState, Field, Input, KeyValue, Notice, PageHeader, Select, Skeleton, Tabs } from "../ui/core";
import { ConfirmDialog } from "../ui/overlay";
import { DataTable } from "../ui/table";

const TABS = ["workspace", "users", "matching", "commercial", "notifications", "system"] as const;
const LABEL: Record<string, string> = { workspace: "Workspace", users: "Users & roles", matching: "Matching", commercial: "Offers & ranking", notifications: "Notifications", system: "System" };

export default function SettingsPage() {
  const [tab, setTab] = useState<string>("workspace");
  const { data, error, isLoading, refetch } = useApi<any>("/settings");
  const { data: me } = useApi<any>("/me");
  if (error) return <ErrorState error={error} onRetry={() => refetch()} />;
  if (isLoading || !data || !me) return <Skeleton className="h-96" />;
  const can = (p: string) => me.user?.permissions?.includes(p);
  return (
    <>
      <PageHeader title="Settings" description="Workspace configuration. Every control here changes application behaviour; controls that are not available in this build are labelled." />
      <Tabs value={tab} onChange={setTab} tabs={TABS.map((t) => ({ value: t, label: LABEL[t] }))} />
      <div className="mt-4 max-w-[980px]">
        {tab === "workspace" && <WorkspaceTab s={data.settings} can={can("workspace.configure")} canReset={can("workspace.reset")} />}
        {tab === "users" && <UsersTab me={me} can={can("users.manage")} />}
        {tab === "matching" && (
          <Card title="Matching thresholds" subtitle="Managed on the Policies page with a live preview of automation and held-out error">
            <KeyValue cols={2} items={[["Risk budget α", pct(data.settings.alpha.value, 2)], ["Lost-match budget β", `${pct(data.beta, 1)} (configuration)`],
              ["Confidence", pct(1 - data.delta, 0)], ["LLM adjudicator", data.llm.enabled ? `On · ${data.llm.adjudicator}` : "Off (no ANTHROPIC_API_KEY)"]]} />
            <Link to="/matching/policies" className="mt-4 inline-block text-[13px] font-semibold text-brand-ink hover:underline">Open matching policies →</Link>
          </Card>
        )}
        {tab === "commercial" && (
          <Card title="Offer and ranking configuration">
            <KeyValue cols={2} items={[["Price competitiveness cap", `${data.settings.price_cap_pct.value}%`], ["Failure cost per failed booking", `₹${data.failure_cost_inr.toLocaleString("en-IN")} (configuration)`],
              ["Ranking weights", Object.entries(data.settings.rank_weights.value).map(([k, v]) => `${k} ${v}`).join(" · ")], ["Relevance guardrail", `Kendall τ ≥ ${data.kendall_guardrail}`]]} />
            <div className="mt-4 flex gap-4 text-[13px]"><Link to="/offers/optimization" className="font-semibold text-brand-ink hover:underline">Edit the price cap →</Link><Link to="/ranking/experiments" className="font-semibold text-brand-ink hover:underline">Edit ranking weights →</Link><Link to="/suppliers/directory" className="font-semibold text-brand-ink hover:underline">Supplier settings →</Link></div>
          </Card>
        )}
        {tab === "notifications" && (
          <Card title="Notification preferences" actions={<Badge>Planned</Badge>}>
            <p className="text-[13px] text-fg-2">Email and chat alerts for escalations, failed imports and supplier degradation are not available in this build. High-severity items appear in the bell menu and on the Overview's Needs Attention table.</p>
          </Card>
        )}
        {tab === "system" && (
          <Card title="System">
            <KeyValue cols={2} items={[["Authentication", "Local demo identities only (no sign-in). Production needs SSO in front of the API."], ["Allowed origins (CORS)", data.cors.join(", ")],
              ["Upload limit", `${data.max_upload_mb} MB · .json or .csv`], ["Data", "Synthetic supplier feeds; prices and policies are fictional"], ["Persistence", "SQLite (operational records); pipeline artifacts read-only"]]} />
          </Card>
        )}
      </div>
    </>
  );
}

function WorkspaceTab({ s, can, canReset }: { s: any; can: boolean; canReset: boolean }) {
  const qc = useQueryClient();
  const [name, setName] = useState(s.workspace_name.value);
  const [ask, setAsk] = useState<"name" | "reset" | null>(null);
  useEffect(() => setName(s.workspace_name.value), [s.workspace_name.value]);
  const invalid = name.trim().length < 2 || name.trim().length > 60;
  const save = useMutation({ mutationFn: (reason: string) => put("/settings/workspace_name", { value: name, reason }),
    onSuccess: () => { setAsk(null); toast({ tone: "success", title: "Workspace renamed" }); qc.invalidateQueries(); }, onError: (e: any) => { setAsk(null); toast({ tone: "error", title: "Could not save", body: e.message }); } });
  const reset = useMutation({ mutationFn: (reason: string) => post("/workspace/reset", { reason }),
    onSuccess: () => { setAsk(null); toast({ tone: "success", title: "Workspace reset", body: "All decisions, imports and settings were cleared; the catalog is back to the pipeline build." }); qc.invalidateQueries(); },
    onError: (e: any) => { setAsk(null); toast({ tone: "error", title: "Reset failed", body: e.message }); } });
  return (
    <div className="space-y-4">
      <Card title="Workspace">
        <div className="max-w-[420px] space-y-3">
          <Field label="Workspace name" error={invalid ? "2–60 characters." : null} hint={s.workspace_name.updated_at ? `Changed ${dateTime(s.workspace_name.updated_at)}` : undefined}>
            <Input value={name} onChange={(e) => setName(e.target.value)} disabled={!can} invalid={invalid} />
          </Field>
          <Button variant="primary" disabled={!can || invalid || name === s.workspace_name.value} onClick={() => setAsk("name")}>Save</Button>
        </div>
      </Card>
      <Card title="Reset demo workspace" subtitle="Administrators only">
        <p className="text-[13px] text-fg-2">Clears every review decision, catalog change, import job, setting and audit event, and restores the catalog to the pipeline build. Use before a demo or recording.</p>
        <Button variant="danger" className="mt-3" disabled={!canReset} onClick={() => setAsk("reset")}>Reset workspace…</Button>
        {!canReset && <p className="mt-2 text-[12px] text-fg-3">Switch to the administrator identity to reset.</p>}
      </Card>
      <ConfirmDialog open={ask === "name"} onClose={() => setAsk(null)} busy={save.isPending} title="Rename workspace?" reason="Reason (optional)" onConfirm={(r) => save.mutate(r)} />
      <ConfirmDialog open={ask === "reset"} onClose={() => setAsk(null)} busy={reset.isPending} tone="danger" confirmLabel="Reset everything" title="Reset the demo workspace?"
        body="This permanently deletes all operational records in this workspace. The trained model and synthetic data are not affected." reason="Reason" reasonRequired onConfirm={(r) => reset.mutate(r)} />
    </div>
  );
}

function UsersTab({ me, can }: { me: any; can: boolean }) {
  const qc = useQueryClient();
  const [pending, setPending] = useState<{ id: string; role: string } | null>(null);
  const save = useMutation({ mutationFn: ({ id, role, reason }: any) => patch(`/users/${id}`, { role, reason }),
    onSuccess: () => { setPending(null); toast({ tone: "success", title: "Role updated" }); qc.invalidateQueries(); }, onError: (e: any) => { setPending(null); toast({ tone: "error", title: "Could not update", body: e.message }); } });
  return (
    <Card title="Users & roles" subtitle="Seeded demo identities" pad={false}>
      <Notice tone="warn" className="m-4">No sign-in in this build. Identities are chosen in the sidebar and sent as a header; the API enforces role permissions, but this is not authentication.</Notice>
      <DataTable rows={me.users} rowKey={(r: any) => r.id}
        columns={[
          { key: "n", header: "User", cell: (r: any) => <span><span className="font-semibold text-fg">{r.name}</span><span className="block text-[12px] text-fg-3">{r.email}</span></span> },
          { key: "r", header: "Role", cell: (r: any) => can && r.id !== me.user.id
            ? <Select value={r.role} onChange={(e) => setPending({ id: r.id, role: e.target.value })}>{Object.entries(me.roles).map(([k, v]: any) => <option key={k} value={k}>{v}</option>)}</Select>
            : <span>{r.role_label}</span> },
          { key: "p", header: "Permissions", cell: (r: any) => <span className="flex flex-wrap gap-1">{r.permissions.map((p: string) => <Badge key={p}>{p}</Badge>)}</span> },
        ]} />
      <ConfirmDialog open={!!pending} onClose={() => setPending(null)} busy={save.isPending} title="Change this user's role?" reason="Reason" reasonRequired
        onConfirm={(reason) => save.mutate({ ...pending, reason })} />
    </Card>
  );
}
