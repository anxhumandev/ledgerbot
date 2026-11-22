import { Link } from "react-router-dom";
import { ago, dateTime } from "../lib/fmt";
import { cx, Empty } from "./core";

const ACTION_LABEL: Record<string, string> = {
  "review.confirmed": "confirmed a match", "review.rejected": "rejected a match", "review.escalated": "escalated a match",
  "review.reopened": "reopened a decision", "review.note_added": "added a review note", "review.assigned": "assigned a case",
  "review.case_created": "opened a review case", "catalog.mapping_changed": "changed a property mapping",
  "ingestion.validated": "validated a supplier file", "ingestion.started": "started an import", "ingestion.completed": "completed an import",
  "ingestion.failed": "had an import fail", "ingestion.retried": "retried an import", "supplier.config_updated": "updated supplier settings",
  "settings.updated": "changed a workspace setting", "simulation.fault_started": "started a supplier fault simulation",
  "simulation.faults_cleared": "cleared simulated supplier faults", "simulation.replay_started": "ran a commercial simulation",
  "workspace.reset": "reset the demo workspace", "workspace.initialized": "initialised the workspace", "user.role_changed": "changed a user role",
};

export function entityLink(type: string, id: string): string | null {
  switch (type) {
    case "review_case": return `/matching/review?case=${id}`;
    case "hotel": return `/inventory/hotel/${id}`;
    case "activity": return `/inventory/activity/${id}`;
    case "supplier": return `/suppliers/${id}`;
    case "ingestion_job": return `/suppliers/ingestion?job=${id}`;
    case "setting": return "/settings";
    default: return null;
  }
}

const DOT: Record<string, string> = { review: "bg-brand", catalog: "bg-accent", ingestion: "bg-ok", simulation: "bg-sim", settings: "bg-fg-3", supplier: "bg-warn" };

export function ActivityTimeline({ events, compact }: { events: any[]; compact?: boolean }) {
  if (!events?.length) return <Empty title="No activity yet" body="Decisions, imports and configuration changes appear here as they happen." />;
  return (
    <ol className="relative space-y-3">
      {events.map((e) => {
        const link = entityLink(e.entity_type, e.entity_id);
        const kind = e.action.split(".")[0];
        return (
          <li key={e.event_id} className="flex gap-3">
            <span className={cx("mt-1.5 h-2 w-2 flex-none rounded-full", DOT[kind] ?? "bg-fg-3")} aria-hidden />
            <div className="min-w-0 flex-1">
              <div className="text-[13px] text-fg-2">
                <span className="font-semibold text-fg">{e.actor_name}</span> {ACTION_LABEL[e.action] ?? e.action}
                {" "}{link ? <Link to={link} className="font-mono text-[12px] text-brand-ink hover:underline">{e.entity_id}</Link>
                  : <span className="font-mono text-[12px] text-fg-3">{e.entity_id}</span>}
              </div>
              {!compact && e.reason && <div className="mt-0.5 text-[12px] text-fg-3">“{e.reason}”</div>}
              <div className="mt-0.5 text-[11px] text-fg-3" title={dateTime(e.ts)}>{ago(e.ts)}</div>
            </div>
          </li>
        );
      })}
    </ol>
  );
}
