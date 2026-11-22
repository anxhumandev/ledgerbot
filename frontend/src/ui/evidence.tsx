import { type ReactNode } from "react";
import { cx } from "./core";

/** Feature contributions from the matcher (log-odds), strongest first: green pushes toward "same", red toward "different". */
export function EvidenceBars({ explain, limit = 9 }: { explain: any; limit?: number }) {
  if (!explain) return null;
  const items = [...(explain.items as { label: string; value: number; group: string }[])].slice(0, limit);
  const max = Math.max(1, ...items.map((i) => Math.abs(i.value)));
  return (
    <div>
      <ul className="space-y-1.5">
        {items.map((it) => (
          <li key={it.label} className="grid grid-cols-[minmax(0,1fr)_120px_48px] items-center gap-3 text-[13px]">
            <span className="truncate text-fg-2" title={it.label}>{it.label}</span>
            <span className="relative h-2 rounded-full bg-panel-3" aria-hidden>
              <span className="absolute inset-y-0 left-1/2 w-px bg-edge-strong" />
              <span className={cx("absolute inset-y-0 rounded-full", it.value >= 0 ? "bg-ok" : "bg-bad")}
                style={{ [it.value >= 0 ? "left" : "right"]: "50%", width: `${(Math.abs(it.value) / max) * 50}%` } as any} />
            </span>
            <span className={cx("num text-right text-[12px] font-semibold", it.value >= 0 ? "text-ok" : "text-bad")}>
              {it.value >= 0 ? "+" : "−"}{Math.abs(it.value).toFixed(1)}
            </span>
          </li>
        ))}
      </ul>
      <div className="mt-3 flex items-center justify-between border-t border-edge pt-3">
        <span className="text-[12px] text-fg-3">Calibrated match probability</span>
        <span className="num text-[18px] font-bold text-fg">p = {explain.p.toFixed(3)}</span>
      </div>
      <p className="mt-2 text-[11px] text-fg-3">Contributions are the model's log-odds evidence per feature. The probability is calibrated on held-out pairs; it is evidence, not a guarantee for this individual pair.</p>
    </div>
  );
}

const STATE_TONE: Record<string, string> = { same: "bg-ok-soft text-ok", similar: "bg-ok-soft text-ok", different: "bg-bad-soft text-bad", missing: "bg-panel-3 text-fg-3" };
const STATE_TEXT: Record<string, string> = { same: "Match", similar: "Close", different: "Differs", missing: "Missing" };

/** Field-aligned comparison of two supplier records, with agreement per field. */
export function FieldCompare({ diffs, headA, headB }: { diffs: any[]; headA: ReactNode; headB: ReactNode }) {
  return (
    <div className="overflow-x-auto scroll-thin">
      <table className="w-full min-w-[620px] text-[13px]">
        <thead>
          <tr className="border-b border-edge bg-panel-2 text-left text-[12px] text-fg-3">
            <th className="w-[110px] px-3 py-2 font-semibold">Field</th>
            <th className="px-3 py-2 font-semibold">{headA}</th>
            <th className="px-3 py-2 font-semibold">{headB}</th>
            <th className="w-[120px] px-3 py-2 font-semibold">Agreement</th>
          </tr>
        </thead>
        <tbody>
          {diffs.map((d) => (
            <tr key={d.field} className={cx("border-b border-edge last:border-0", d.state === "different" && "bg-bad-soft/30")}>
              <td className="px-3 py-2.5 font-semibold text-fg-3">{d.field}</td>
              <td className="break-words px-3 py-2.5 text-fg">{d.a ?? <i className="text-fg-3">missing</i>}</td>
              <td className="break-words px-3 py-2.5 text-fg">{d.b ?? <i className="text-fg-3">missing</i>}</td>
              <td className="px-3 py-2.5"><span className={cx("rounded-full px-2 py-0.5 text-[12px] font-semibold", STATE_TONE[d.state])}>{d.note ?? STATE_TEXT[d.state]}</span></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** Probability bar with the certified decision zones: auto-reject · human review · auto-merge. */
export function DecisionZones({ p, tauAccept, tauReject }: { p: number; tauAccept: number | null; tauReject: number | null }) {
  const a = tauAccept ?? 1, r = tauReject ?? 0;
  return (
    <div>
      <div className="relative h-3 overflow-hidden rounded-full bg-panel-3" aria-label={`p ${p.toFixed(3)}, auto-reject at or below ${r.toFixed(2)}, auto-merge at or above ${a.toFixed(2)}`}>
        <div className="absolute inset-y-0 left-0 bg-edge-strong" style={{ width: `${r * 100}%` }} />
        <div className="absolute inset-y-0 bg-warn/40" style={{ left: `${r * 100}%`, width: `${(a - r) * 100}%` }} />
        <div className="absolute inset-y-0 right-0 bg-ok/40" style={{ width: `${(1 - a) * 100}%` }} />
        <div className="absolute -top-0.5 h-4 w-1 rounded bg-fg" style={{ left: `calc(${p * 100}% - 2px)` }} />
      </div>
      <div className="mt-1 flex justify-between text-[11px] text-fg-3">
        <span>Auto-reject ≤ {r.toFixed(2)}</span><span>Human review</span><span>Auto-merge ≥ {a.toFixed(2)}</span>
      </div>
    </div>
  );
}
