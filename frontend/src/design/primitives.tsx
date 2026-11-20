import { AnimatePresence, motion, useMotionValue, useSpring } from "framer-motion";
import { type ReactNode, useEffect, useLayoutEffect, useRef, useState } from "react";
import { REDUCE_MOTION, SUPPLIERS } from "../lib/format";

export const EASE = [0.22, 1, 0.36, 1] as const;
export const T = { duration: REDUCE_MOTION ? 0 : 0.28, ease: EASE };
export const rise = (i = 0) => ({
  initial: { opacity: 0, y: REDUCE_MOTION ? 0 : 8 },
  animate: { opacity: 1, y: 0 },
  transition: { ...T, delay: REDUCE_MOTION ? 0 : i * 0.04 },
});

const cx = (...c: (string | false | null | undefined)[]) => c.filter(Boolean).join(" ");

/* ------------------------------------------------------------------ Stage: designed at 1920x1080, fills any window
   Scaled so the 1920x1080 design always fits, then widened or heightened to the window's own aspect ratio,
   so there are no empty bars on screens or browser windows that are not exactly 16:9. */
export function Stage({ children }: { children: ReactNode }) {
  const [box, setBox] = useState({ scale: 1, w: 1920, h: 1080 });
  useLayoutEffect(() => {
    const fit = () => {
      const vw = window.innerWidth, vh = window.innerHeight;
      const scale = Math.min(vw / 1920, vh / 1080);
      setBox({ scale, w: vw / scale, h: vh / scale });
    };
    fit();
    window.addEventListener("resize", fit);
    return () => window.removeEventListener("resize", fit);
  }, []);
  return (
    <div className="fixed inset-0 bg-paper overflow-hidden">
      <div style={{ width: box.w, height: box.h, transform: `scale(${box.scale})`, transformOrigin: "0 0", position: "absolute", left: 0, top: 0 }}
        className="bg-paper grain overflow-hidden">
        {children}
      </div>
    </div>
  );
}

export function SceneHeader({ headline, subline, right }: { headline: ReactNode; subline?: ReactNode; right?: ReactNode }) {
  return (
    <div className="flex items-end justify-between gap-8 mb-8">
      <div>
        <motion.h1 {...rise(0)} className="font-serif text-[60px] leading-[1.05] tracking-[-0.01em] text-ink max-w-[1250px]">{headline}</motion.h1>
        {subline && <motion.p {...rise(2)} className="mt-3 text-[18px] text-ink-2 max-w-[1100px]">{subline}</motion.p>}
      </div>
      {right && <motion.div {...rise(3)}>{right}</motion.div>}
    </div>
  );
}

export function Card({ children, className, ...rest }: { children: ReactNode; className?: string } & Record<string, any>) {
  return (
    <motion.div {...rest} className={cx("bg-surface border border-line rounded-card shadow-card", className)}>
      {children}
    </motion.div>
  );
}

export function Caption({ children, className }: { children: ReactNode; className?: string }) {
  return <div className={cx("text-[12px] uppercase tracking-[0.08em] text-ink-3 font-medium", className)}>{children}</div>;
}

export function Cite({ children }: { children: ReactNode }) {
  return <span className="text-[11px] text-ink-3">{children}</span>;
}

/* ------------------------------------------------------------------ Ticker: animated number */
export function Ticker({ value, format = (v: number) => v.toFixed(0), className }: { value: number; format?: (v: number) => string; className?: string }) {
  const mv = useMotionValue(value);
  const spring = useSpring(mv, { stiffness: 140, damping: 30, mass: 0.8 });
  const ref = useRef<HTMLSpanElement>(null);
  useEffect(() => {
    if (REDUCE_MOTION) {
      if (ref.current) ref.current.textContent = format(value);
      return;
    }
    mv.set(value);
  }, [value]);
  useEffect(() => spring.on("change", (v) => { if (ref.current) ref.current.textContent = format(v); }), [spring, format]);
  return <span ref={ref} className={cx("font-mono tabular", className)}>{format(REDUCE_MOTION ? value : spring.get())}</span>;
}

export function Stat({ value, format, caption, delta, tone = "ink", size = 56, sub }: {
  value: number | string | null | undefined; format?: (v: number) => string; caption: ReactNode; delta?: ReactNode;
  tone?: string; size?: number; sub?: ReactNode;
}) {
  const color = { ink: "text-ink", lagoon: "text-lagoon", saffron: "text-[color:var(--saffron-ink)]", sage: "text-[color:var(--sage-ink)]",
    clay: "text-[color:var(--clay-ink)]", amber: "text-[color:var(--amber-ink)]", iris: "text-iris" }[tone] ?? "text-ink";
  return (
    <div>
      <Caption>{caption}</Caption>
      <div className={cx("mt-1 font-mono tabular leading-none", color)} style={{ fontSize: size }}>
        {typeof value === "number" ? <Ticker value={value} format={format} /> : value ?? "—"}
      </div>
      {delta && <div className="mt-2 text-[14px] text-ink-2">{delta}</div>}
      {sub && <div className="mt-1 text-[13px] text-ink-3">{sub}</div>}
    </div>
  );
}

/* ------------------------------------------------------------------ chips */
const CHIP = {
  neutral: "bg-surface-2 text-ink-2", lagoon: "bg-lagoon-soft text-lagoon", saffron: "bg-saffron-soft text-[color:var(--saffron-ink)]",
  sage: "bg-sage-soft text-[color:var(--sage-ink)]", clay: "bg-clay-soft text-[color:var(--clay-ink)]",
  amber: "bg-amber-soft text-[color:var(--amber-ink)]", iris: "bg-iris-soft text-iris", ink: "bg-ink text-paper",
};
export type ChipVariant = keyof typeof CHIP;
export function Chip({ children, variant = "neutral", className, icon }: { children: ReactNode; variant?: ChipVariant; className?: string; icon?: ReactNode }) {
  return (
    <span className={cx("inline-flex items-center gap-1.5 rounded-full px-2.5 py-[3px] text-[12px] font-medium whitespace-nowrap", CHIP[variant], className)}>
      {icon}{children}
    </span>
  );
}

export function SupplierChip({ code, short = false, layoutId, className }: { code: string; short?: boolean; layoutId?: string; className?: string }) {
  const s = SUPPLIERS[code] ?? { name: code, color: "#8B909A" };
  return (
    <motion.span layoutId={layoutId} transition={T} className={cx("inline-flex items-center gap-1.5 rounded-full px-2.5 py-[3px] text-[12px] font-medium whitespace-nowrap", className)}
      style={{ background: `${s.color}18`, color: s.color }}>
      <span className="w-2 h-2 rounded-full" style={{ background: s.color }} />
      {short ? code : s.name}
    </motion.span>
  );
}

export function Kbd({ children }: { children: ReactNode }) {
  return <kbd className="font-mono text-[11px] px-1.5 py-0.5 rounded border border-line bg-surface text-ink-2">{children}</kbd>;
}

export function Button({ children, variant = "primary", onClick, disabled, kbd, className }: {
  children: ReactNode; variant?: "primary" | "ghost" | "danger" | "soft"; onClick?: () => void; disabled?: boolean; kbd?: string; className?: string;
}) {
  const v = {
    primary: "bg-lagoon text-white hover:brightness-110",
    ghost: "bg-transparent text-ink-2 border border-line hover:bg-surface-2",
    danger: "bg-transparent text-ink-2 border border-line hover:bg-clay-soft hover:text-[color:var(--clay-ink)] hover:border-clay",
    soft: "bg-lagoon-soft text-lagoon hover:brightness-95",
  }[variant];
  return (
    <button onClick={onClick} disabled={disabled}
      className={cx("inline-flex items-center gap-2 rounded-full px-4 py-2 text-[14px] font-medium transition disabled:opacity-40", v, className)}>
      {children}{kbd && <Kbd>{kbd}</Kbd>}
    </button>
  );
}

export function Toggle<T extends string>({ options, value, onChange }: { options: { value: T; label: ReactNode }[]; value: T; onChange: (v: T) => void }) {
  return (
    <div className="inline-flex rounded-full bg-surface-2 p-1 border border-line">
      {options.map((o) => (
        <button key={o.value} onClick={() => onChange(o.value)} className="relative px-4 py-1.5 text-[14px] font-medium rounded-full">
          {value === o.value && <motion.span layoutId={`tg-${options.map((x) => x.value).join("")}`} transition={T} className="absolute inset-0 rounded-full bg-surface shadow-card border border-line" />}
          <span className={cx("relative", value === o.value ? "text-ink" : "text-ink-3")}>{o.label}</span>
        </button>
      ))}
    </div>
  );
}

/* ------------------------------------------------------------------ Timer */
export function Timer({ startedAt, stoppedAt, limit = 20, tone }: { startedAt: number | null; stoppedAt: number | null; limit?: number; tone?: string }) {
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    if (!startedAt || stoppedAt) return;
    let raf = 0;
    const tick = () => { setNow(Date.now()); raf = requestAnimationFrame(tick); };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [startedAt, stoppedAt]);
  const el = startedAt ? Math.min(limit, ((stoppedAt ?? now) - startedAt) / 1000) : 0;
  const left = Math.max(0, limit - el);
  const frac = el / limit;
  const color = tone ?? (left < 5 && startedAt && !stoppedAt ? "var(--clay)" : "var(--lagoon)");
  return (
    <div className="flex items-center gap-3">
      <svg width="44" height="44" viewBox="0 0 44 44">
        <circle cx="22" cy="22" r="19" fill="none" stroke="var(--line)" strokeWidth="4" />
        <circle cx="22" cy="22" r="19" fill="none" stroke={color} strokeWidth="4" strokeLinecap="round"
          strokeDasharray={`${2 * Math.PI * 19}`} strokeDashoffset={`${2 * Math.PI * 19 * frac}`} transform="rotate(-90 22 22)" />
      </svg>
      <span className="font-mono tabular text-[40px] leading-none" style={{ color }}>{el.toFixed(1)}s</span>
    </div>
  );
}

/* ------------------------------------------------------------------ Sparkline */
export function Sparkline({ data, color = "var(--lagoon)", width = 220, height = 44, min, max }: { data: number[]; color?: string; width?: number; height?: number; min?: number; max?: number }) {
  if (!data || data.length < 2) return <div style={{ width, height }} className="rounded bg-surface-2/60" />;
  const lo = min ?? Math.min(...data), hi = max ?? Math.max(...data);
  const span = hi - lo || 1;
  const pts = data.map((v, i) => `${(i / (data.length - 1)) * width},${height - 3 - ((v - lo) / span) * (height - 6)}`).join(" ");
  return (
    <svg width={width} height={height}>
      <polyline points={pts} fill="none" stroke={color} strokeWidth={2} strokeLinejoin="round" strokeLinecap="round" />
    </svg>
  );
}

/* ------------------------------------------------------------------ ProbBar: reject | review | accept zones */
export function ProbBar({ p, tauAccept, tauReject, width = 360, label = true }: { p: number; tauAccept: number | null; tauReject: number | null; width?: number; label?: boolean }) {
  const ta = tauAccept ?? 1, tr = tauReject ?? 0;
  const x = (v: number) => Math.max(0, Math.min(1, v)) * width;
  const tone = p >= ta ? "var(--sage)" : p <= tr ? "var(--ink-3)" : "var(--amber)";
  return (
    <div style={{ width }}>
      <div className="relative h-3 rounded-full overflow-hidden bg-surface-2">
        <div className="absolute inset-y-0 left-0 bg-[color:var(--line)]" style={{ width: x(tr) }} />
        <div className="absolute inset-y-0 bg-amber-soft" style={{ left: x(tr), width: Math.max(2, x(ta) - x(tr)) }} />
        <div className="absolute inset-y-0 right-0 bg-sage-soft" style={{ left: x(ta) }} />
        <motion.div initial={{ left: 0 }} animate={{ left: x(p) - 7 }} transition={{ ...T, duration: REDUCE_MOTION ? 0 : 0.6 }}
          className="absolute top-1/2 -translate-y-1/2 w-3.5 h-3.5 rounded-full border-2 border-white shadow" style={{ background: tone }} />
      </div>
      {label && (
        <div className="flex justify-between mt-1 text-[11px] text-ink-3 font-mono">
          <span>auto-reject ≤ {tr.toFixed(2)}</span><span>review</span><span>auto-merge ≥ {ta.toFixed(2)}</span>
        </div>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ Explain waterfall */
export function Explain({ explain, width = 520 }: { explain: any; width?: number }) {
  if (!explain) return null;
  const items = explain.items as { label: string; value: number; group: string }[];
  const maxAbs = Math.max(1, ...items.map((i) => Math.abs(i.value)));
  const half = (width - 230) / 2;
  return (
    <div style={{ width }}>
      {items.map((it, k) => (
        <motion.div key={it.label} {...rise(k)} className="flex items-center gap-3 py-[5px]">
          <div className="w-[200px] text-[14px] text-ink-2 truncate" title={it.label}>{it.label}</div>
          <div className="relative h-5" style={{ width: half * 2 }}>
            <div className="absolute top-0 bottom-0 w-px bg-line" style={{ left: half }} />
            <motion.div initial={{ width: 0 }} animate={{ width: (Math.abs(it.value) / maxAbs) * half }} transition={{ ...T, delay: k * 0.05, duration: 0.5 }}
              className="absolute top-1 bottom-1 rounded"
              style={{ [it.value >= 0 ? "left" : "right"]: half, background: it.value >= 0 ? "var(--sage)" : "var(--clay)", opacity: 0.85 } as any} />
          </div>
          <div className={cx("w-[52px] text-right font-mono text-[13px]", it.value >= 0 ? "text-[color:var(--sage-ink)]" : "text-[color:var(--clay-ink)]")}>
            {it.value >= 0 ? "+" : "−"}{Math.abs(it.value).toFixed(1)}
          </div>
        </motion.div>
      ))}
      <div className="flex items-center justify-between mt-3 pt-3 border-t border-line">
        <span className="text-[13px] text-ink-3">Calibrated probability</span>
        <span className="font-mono text-[22px] text-ink">p = {explain.p.toFixed(3)}</span>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ Toast */
export function ToastHost({ toast }: { toast: { id: number; text: string; tone?: string } | null }) {
  const [shown, setShown] = useState(toast);
  useEffect(() => {
    setShown(toast);
    if (!toast) return;
    const t = setTimeout(() => setShown(null), 6000);
    return () => clearTimeout(t);
  }, [toast?.id]);
  return (
    <div className="absolute left-1/2 -translate-x-1/2 bottom-[60px] z-40">
      <AnimatePresence>
        {shown && (
          <motion.div key={shown.id} initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: 12 }} transition={T}
            className={cx("px-5 py-3 rounded-full shadow-card border text-[16px] font-medium",
              shown.tone === "clay" ? "bg-clay-soft border-clay text-[color:var(--clay-ink)]" : shown.tone === "sage" ? "bg-sage-soft border-sage text-[color:var(--sage-ink)]" : "bg-ink text-paper border-ink")}>
            {shown.text}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

export function Skeleton({ className, style }: { className?: string; style?: any }) {
  return <div className={cx("shimmer rounded-lg", className)} style={style} />;
}

export function Placeholder({ name, size = 56, className }: { name: string; size?: number; className?: string }) {
  let h = 0;
  for (const c of name) h = (h * 31 + c.charCodeAt(0)) % 360;
  return (
    <div className={cx("flex items-center justify-center font-serif text-white/90", className)}
      style={{ background: `linear-gradient(135deg, hsl(${h} 28% 62%), hsl(${(h + 40) % 360} 24% 48%))`, fontSize: size * 0.45, filter: "saturate(.9)" }}>
      {name.replace(/^the\s+/i, "").charAt(0).toUpperCase()}
    </div>
  );
}

export function Photo({ src, name, className }: { src?: string | null; name: string; className?: string }) {
  const [err, setErr] = useState(false);
  if (!src || err) return <Placeholder name={name} className={className} />;
  return <img src={src} alt="" onError={() => setErr(true)} className={cx("object-cover", className)} />;
}

export { cx };
