import { AlertTriangle, Check, Copy, Info, Loader2, RefreshCw, Search, X } from "lucide-react";
import { forwardRef, type ButtonHTMLAttributes, type InputHTMLAttributes, type ReactNode, type SelectHTMLAttributes, useState } from "react";
import { SUPPLIER_COLOR, SUPPLIER_NAME } from "../lib/fmt";

export const cx = (...c: (string | false | null | undefined)[]) => c.filter(Boolean).join(" ");

/* ------------------------------------------------------------------ buttons */
type BtnVariant = "primary" | "accent" | "secondary" | "ghost" | "danger";
const BTN: Record<BtnVariant, string> = {
  primary: "bg-brand text-white hover:bg-brand-hover border border-transparent",
  accent: "bg-accent text-white hover:bg-accent-hover border border-transparent",
  secondary: "bg-panel text-fg-2 border border-edge-strong hover:bg-panel-2 hover:text-fg",
  ghost: "bg-transparent text-fg-2 border border-transparent hover:bg-panel-3 hover:text-fg",
  danger: "bg-panel text-bad border border-bad/40 hover:bg-bad-soft",
};

export const Button = forwardRef<HTMLButtonElement, ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: BtnVariant; size?: "sm" | "md"; loading?: boolean; icon?: ReactNode;
}>(function Button({ variant = "secondary", size = "md", loading, icon, className, children, disabled, ...rest }, ref) {
  return (
    <button ref={ref} disabled={disabled || loading} {...rest}
      className={cx("inline-flex items-center justify-center gap-2 rounded-full font-semibold whitespace-nowrap transition-colors",
        "disabled:opacity-50 disabled:cursor-not-allowed", size === "sm" ? "h-8 px-3 text-[13px]" : "h-9 px-4 text-[13px]", BTN[variant], className)}>
      {loading ? <Loader2 size={15} className="animate-spin" /> : icon}
      {children}
    </button>
  );
});

export function IconButton({ label, children, className, ...rest }: ButtonHTMLAttributes<HTMLButtonElement> & { label: string }) {
  return (
    <button aria-label={label} title={label} {...rest}
      className={cx("inline-flex h-8 w-8 items-center justify-center rounded-full text-fg-3 hover:bg-panel-3 hover:text-fg transition-colors disabled:opacity-40", className)}>
      {children}
    </button>
  );
}

/* ------------------------------------------------------------------ badges */
export type Tone = "neutral" | "brand" | "accent" | "ok" | "warn" | "bad" | "sim";
const TONE: Record<Tone, string> = {
  neutral: "bg-panel-3 text-fg-2", brand: "bg-brand-soft text-brand-ink", accent: "bg-accent-soft text-accent-ink",
  ok: "bg-ok-soft text-ok", warn: "bg-warn-soft text-warn", bad: "bg-bad-soft text-bad", sim: "bg-sim-soft text-sim",
};
export function Badge({ tone = "neutral", children, className, dot }: { tone?: Tone; children: ReactNode; className?: string; dot?: boolean }) {
  return (
    <span className={cx("inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-[12px] font-semibold whitespace-nowrap", TONE[tone], className)}>
      {dot && <span className="h-1.5 w-1.5 rounded-full bg-current" aria-hidden />}
      {children}
    </span>
  );
}

const STATUS: Record<string, [Tone, string]> = {
  verified: ["ok", "Verified"], needs_review: ["warn", "Needs review"], low_confidence: ["warn", "Low confidence"],
  single_source: ["neutral", "Single source"], new: ["brand", "New"], open: ["warn", "Open"], escalated: ["bad", "Escalated"],
  confirmed: ["ok", "Confirmed"], rejected: ["neutral", "Rejected"], healthy: ["ok", "Healthy"], degraded: ["bad", "Degraded"],
  error: ["bad", "Error"], paused: ["neutral", "Paused"], onboarding: ["brand", "Onboarding"], active: ["ok", "Active"],
  completed: ["ok", "Completed"], failed: ["bad", "Failed"], running: ["brand", "Running"], queued: ["brand", "Queued"],
  validated: ["warn", "Ready to import"], recommended: ["accent", "Recommended"], alternative: ["neutral", "Alternative"],
  ineligible: ["bad", "Ineligible"], high: ["bad", "High"], medium: ["warn", "Medium"], low: ["neutral", "Low"],
  attach: ["ok", "Merged"], update: ["brand", "Updated"], review: ["warn", "Sent to review"], rejected_row: ["bad", "Rejected"],
};
export function StatusBadge({ status, label }: { status: string; label?: string }) {
  const [tone, text] = STATUS[status] ?? ["neutral", status.replace(/_/g, " ")];
  return <Badge tone={tone} dot>{label ?? text}</Badge>;
}

/** Where a number comes from. Shown next to every metric that is not a plain catalog count. */
export function SourceTag({ source }: { source: string }) {
  const map: Record<string, [Tone, string, string]> = {
    measured: ["neutral", "Measured", "Computed from the catalog or the held-out evaluation set"],
    simulated: ["sim", "Simulated", "Produced by the booking simulator or replay; not real booking outcomes"],
    live: ["brand", "Live", "Operational records in this workspace"],
    assumption: ["warn", "Assumption", "A measured count multiplied by a stated assumption"],
    synthetic: ["sim", "Synthetic", "Synthetic demo data"],
  };
  const [tone, text, tip] = map[source] ?? ["neutral", source, source];
  return <span title={tip}><Badge tone={tone} className="!text-[11px] !px-1.5">{text}</Badge></span>;
}

export function SupplierChip({ code, name, compact }: { code: string; name?: string; compact?: boolean }) {
  const c = SUPPLIER_COLOR[code] ?? "#808285";
  return (
    <span className="inline-flex items-center gap-1.5 whitespace-nowrap text-[13px] text-fg-2" title={SUPPLIER_NAME[code] ?? code}>
      <span className="h-2 w-2 rounded-full flex-none" style={{ background: c }} aria-hidden />
      {compact ? code : name ?? SUPPLIER_NAME[code] ?? code}
    </span>
  );
}

/* ------------------------------------------------------------------ layout */
export function Card({ children, className, title, actions, subtitle, pad = true }: {
  children: ReactNode; className?: string; title?: ReactNode; actions?: ReactNode; subtitle?: ReactNode; pad?: boolean;
}) {
  return (
    <section className={cx("rounded-card border border-edge bg-panel shadow-card", className)}>
      {(title || actions) && (
        <header className="flex items-start justify-between gap-3 border-b border-edge px-4 py-3">
          <div className="min-w-0">
            {title && <h2 className="text-[14px] font-semibold text-fg">{title}</h2>}
            {subtitle && <p className="mt-0.5 text-[12px] text-fg-3">{subtitle}</p>}
          </div>
          {actions && <div className="flex flex-none items-center gap-2">{actions}</div>}
        </header>
      )}
      <div className={pad ? "p-4" : ""}>{children}</div>
    </section>
  );
}

export function PageHeader({ title, description, actions, meta }: { title: ReactNode; description?: ReactNode; actions?: ReactNode; meta?: ReactNode }) {
  return (
    <div className="mb-5 flex flex-wrap items-end justify-between gap-4">
      <div className="min-w-0">
        <h1 className="text-[22px] font-bold leading-tight text-fg">{title}</h1>
        {description && <p className="mt-1 max-w-[860px] text-[13px] text-fg-3">{description}</p>}
        {meta && <div className="mt-2 flex flex-wrap items-center gap-2 text-[12px] text-fg-3">{meta}</div>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  );
}

export function Metric({ label, value, hint, source, tone, onClick }: {
  label: string; value: ReactNode; hint?: ReactNode; source?: string; tone?: "accent" | "brand"; onClick?: () => void;
}) {
  const Tag = onClick ? "button" : "div";
  return (
    <Tag onClick={onClick} className={cx("min-w-0 rounded-card border border-edge bg-panel p-4 text-left shadow-card",
      onClick && "transition-colors hover:border-brand/50")}>
      <div className="flex items-start justify-between gap-2">
        <span className="text-[12px] font-semibold uppercase leading-tight tracking-[0.03em] text-fg-3">{label}</span>
        {source && <SourceTag source={source} />}
      </div>
      <div className={cx("num mt-2 text-[26px] font-bold leading-none", tone === "accent" ? "text-accent-ink" : tone === "brand" ? "text-brand-ink" : "text-fg")}>{value}</div>
      {hint && <div className="mt-2 text-[12px] leading-snug text-fg-3">{hint}</div>}
    </Tag>
  );
}

export function KeyValue({ items, cols = 2 }: { items: [ReactNode, ReactNode][]; cols?: number }) {
  return (
    <dl className={cx("grid gap-x-6 gap-y-3", cols === 3 ? "sm:grid-cols-3" : cols === 1 ? "" : "sm:grid-cols-2")}>
      {items.map(([k, v], i) => (
        <div key={i} className="min-w-0">
          <dt className="text-[12px] text-fg-3">{k}</dt>
          <dd className="mt-0.5 break-words text-[13px] text-fg">{v ?? "—"}</dd>
        </div>
      ))}
    </dl>
  );
}

export function Bar({ value, tone = "brand", className }: { value: number; tone?: "brand" | "accent" | "ok" | "warn" | "bad"; className?: string }) {
  const c = { brand: "bg-brand", accent: "bg-accent", ok: "bg-ok", warn: "bg-warn", bad: "bg-bad" }[tone];
  return (
    <div className={cx("h-1.5 overflow-hidden rounded-full bg-panel-3", className ?? "w-full")} role="meter" aria-valuenow={Math.round(value * 100)} aria-valuemin={0} aria-valuemax={100}>
      <div className={cx("h-full rounded-full", c)} style={{ width: `${Math.max(0, Math.min(1, value)) * 100}%` }} />
    </div>
  );
}

/* ------------------------------------------------------------------ states */
export function Skeleton({ className }: { className?: string }) {
  return <div className={cx("animate-pulse rounded-md bg-panel-3", className)} aria-hidden />;
}

export function Spinner({ label = "Loading" }: { label?: string }) {
  return <span className="inline-flex items-center gap-2 text-[13px] text-fg-3"><Loader2 size={15} className="animate-spin" />{label}</span>;
}

export function Empty({ title, body, action, icon }: { title: string; body?: ReactNode; action?: ReactNode; icon?: ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 px-6 py-12 text-center">
      <div className="text-fg-3">{icon ?? <Info size={22} />}</div>
      <div className="text-[14px] font-semibold text-fg">{title}</div>
      {body && <div className="max-w-[460px] text-[13px] text-fg-3">{body}</div>}
      {action && <div className="mt-2">{action}</div>}
    </div>
  );
}

export function ErrorState({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const e = error as any;
  return (
    <div role="alert" className="flex flex-col items-center justify-center gap-2 px-6 py-10 text-center">
      <AlertTriangle size={22} className="text-bad" />
      <div className="text-[14px] font-semibold text-fg">{e?.code === "not_found" ? "Not found" : "Something went wrong"}</div>
      <div className="max-w-[520px] text-[13px] text-fg-3">{e?.message ?? String(error)}</div>
      {e?.requestId && <div className="font-mono text-[11px] text-fg-3">Request {e.requestId}</div>}
      {onRetry && <Button size="sm" icon={<RefreshCw size={14} />} onClick={onRetry} className="mt-1">Retry</Button>}
    </div>
  );
}

export function Notice({ tone = "brand", children, className }: { tone?: Tone; children: ReactNode; className?: string }) {
  return <div className={cx("flex items-start gap-2 rounded-lg px-3 py-2 text-[13px]", TONE[tone], className)}><Info size={15} className="mt-0.5 flex-none" /><div>{children}</div></div>;
}

/* ------------------------------------------------------------------ inputs */
export const Input = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement> & { invalid?: boolean }>(
  function Input({ className, invalid, ...rest }, ref) {
    return <input ref={ref} aria-invalid={invalid || undefined} {...rest}
      className={cx("h-9 w-full rounded-lg border bg-panel px-3 text-[13px] text-fg placeholder:text-fg-3 outline-none transition-colors",
        "focus:border-brand focus:shadow-[var(--focus)]", invalid ? "border-bad" : "border-edge-strong", className)} />;
  });

export function Select({ className, children, ...rest }: SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <select {...rest} className={cx("h-9 rounded-lg border border-edge-strong bg-panel pl-3 pr-8 text-[13px] text-fg outline-none focus:border-brand focus:shadow-[var(--focus)]", className)}>
      {children}
    </select>
  );
}

export function Field({ label, hint, error, children, htmlFor }: { label: string; hint?: ReactNode; error?: string | null; children: ReactNode; htmlFor?: string }) {
  return (
    <div className="space-y-1">
      <label htmlFor={htmlFor} className="block text-[12px] font-semibold text-fg-2">{label}</label>
      {children}
      {error ? <p role="alert" className="text-[12px] text-bad">{error}</p> : hint ? <p className="text-[12px] text-fg-3">{hint}</p> : null}
    </div>
  );
}

export function SearchInput({ value, onChange, placeholder, className, autoFocus, label = "Search" }: {
  value: string; onChange: (v: string) => void; placeholder?: string; className?: string; autoFocus?: boolean; label?: string;
}) {
  return (
    <div className={cx("relative", className)}>
      <Search size={15} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-fg-3" aria-hidden />
      <Input aria-label={label} value={value} autoFocus={autoFocus} onChange={(e) => onChange(e.target.value)} placeholder={placeholder} className="pl-9 pr-8" />
      {value && <button aria-label="Clear search" onClick={() => onChange("")} className="absolute right-2 top-1/2 -translate-y-1/2 rounded p-0.5 text-fg-3 hover:text-fg"><X size={14} /></button>}
    </div>
  );
}

export function Segmented<T extends string>({ value, onChange, options, label }: { value: T; onChange: (v: T) => void; options: { value: T; label: ReactNode }[]; label: string }) {
  return (
    <div role="radiogroup" aria-label={label} className="inline-flex rounded-full border border-edge-strong bg-panel p-0.5">
      {options.map((o) => (
        <button key={o.value} role="radio" aria-checked={value === o.value} onClick={() => onChange(o.value)}
          className={cx("h-7 rounded-full px-3 text-[13px] font-semibold transition-colors", value === o.value ? "bg-brand text-white" : "text-fg-3 hover:text-fg")}>
          {o.label}
        </button>
      ))}
    </div>
  );
}

export function Tabs<T extends string>({ value, onChange, tabs }: { value: T; onChange: (v: T) => void; tabs: { value: T; label: ReactNode; count?: number }[] }) {
  return (
    <div role="tablist" className="flex gap-1 overflow-x-auto border-b border-edge scroll-thin">
      {tabs.map((t) => (
        <button key={t.value} role="tab" aria-selected={value === t.value} onClick={() => onChange(t.value)}
          className={cx("-mb-px flex items-center gap-1.5 whitespace-nowrap border-b-2 px-3 py-2.5 text-[13px] font-semibold transition-colors",
            value === t.value ? "border-brand text-brand-ink" : "border-transparent text-fg-3 hover:text-fg")}>
          {t.label}
          {t.count !== undefined && <span className={cx("rounded-full px-1.5 text-[11px]", value === t.value ? "bg-brand-soft" : "bg-panel-3")}>{t.count}</span>}
        </button>
      ))}
    </div>
  );
}

export function CopyId({ value, className }: { value: string; className?: string }) {
  const [ok, setOk] = useState(false);
  return (
    <button onClick={(e) => { e.stopPropagation(); navigator.clipboard?.writeText(value).then(() => { setOk(true); setTimeout(() => setOk(false), 1200); }); }}
      className={cx("group inline-flex items-center gap-1 rounded font-mono text-[12px] text-fg-3 hover:text-fg", className)} title="Copy ID" aria-label={`Copy ${value}`}>
      {value}
      {ok ? <Check size={12} className="text-ok" /> : <Copy size={12} className="opacity-0 group-hover:opacity-100" />}
    </button>
  );
}

export function Confidence({ p, tauAccept }: { p: number | null | undefined; tauAccept?: number | null }) {
  if (p === null || p === undefined) return <span className="text-[13px] text-fg-3">—</span>;
  const tone = tauAccept != null && p < tauAccept ? "warn" : p >= 0.9 ? "ok" : "warn";
  return (
    <span className="inline-flex items-center gap-2">
      <span className="num w-11 text-[13px] text-fg">{p.toFixed(3)}</span>
      <Bar value={p} tone={tone} className="w-12" />
    </span>
  );
}
