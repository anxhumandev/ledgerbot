import { AnimatePresence, motion } from "framer-motion";
import { useEffect, useRef, useState } from "react";
import { SCENES, useApp } from "../app/store";
import { Kbd, T } from "../design/primitives";
import { BookOpen, ChevronLeft, ChevronRight, ChevronUp, Keyboard, RotateCcw, Search } from "lucide-react";
import { resetDemo } from "../lib/demo";
import { formatINR, RECORD_MODE } from "../lib/format";

export function TopBar() {
  const scene = useApp((s) => s.scene);
  const cost = useApp((s) => s.cost);
  const llm = useApp((s) => s.llm);
  const ws = useApp((s) => s.wsConnected);
  const sc = SCENES[scene];
  const llmOn = llm?.enabled;
  return (
    <div className="absolute top-0 left-0 right-0 h-14 px-16 flex items-center justify-between z-20 bg-navy text-white shadow-[0_2px_8px_rgba(1,40,80,.25)]">
      <div className="flex items-center gap-3">
        <svg width="26" height="26" viewBox="0 0 32 32"><rect width="32" height="32" rx="8" fill="#FFFFFF" /><g fill="var(--lagoon)"><rect x="7" y="7" width="8" height="8" rx="1.5" /><rect x="17" y="7" width="8" height="8" rx="1.5" opacity=".55" /><rect x="7" y="17" width="8" height="8" rx="1.5" opacity=".55" /><rect x="17" y="17" width="8" height="8" rx="1.5" fill="var(--saffron)" /></g></svg>
        <span className="font-serif text-[24px] leading-none text-white">LedgerBot</span>
        <span className="ml-2 text-[13px] font-semibold uppercase tracking-[0.06em] text-[color:var(--saffron)]">Supply intelligence</span>
      </div>
      <div className="absolute left-1/2 -translate-x-1/2 text-[16px] text-white/70">
        <span className="tabular font-semibold text-white/90">{sc.id}</span><span className="mx-2">·</span><span className="text-white font-medium">{sc.title}</span>
      </div>
      <div className="flex items-center gap-4">
        {!RECORD_MODE && (
          <button onClick={() => useApp.getState().setSearch(true)} title="Find any hotel (Ctrl+K or /)"
            className="flex items-center gap-2 rounded-full bg-white/10 hover:bg-white/20 border border-white/20 px-3 py-1 text-[14px] text-white/90 transition">
            <Search size={14} />Find a hotel<kbd className="ml-1 text-[12px] px-1.5 rounded bg-white/15">Ctrl K</kbd>
          </button>
        )}
        <div className="flex items-center gap-2 rounded-full bg-white/10 border border-white/20 px-3 py-1 text-[14px]" data-tip="LLM spend this session vs. an LLM-only pipeline on the same pairs">
          <span className="text-white/75">LLM spend</span>
          <span className="tabular font-semibold text-white">{formatINR(cost?.tessera_llm_spend_inr, { decimals: 2 })}</span>
          <span className="text-white/60">vs LLM-only</span>
          <span className="tabular font-semibold text-[color:var(--saffron)]">{formatINR(cost?.llm_only_counterfactual_inr, { decimals: 2 })}{cost?.counterfactual_estimated ? " est." : ""}</span>
        </div>
        <div className="flex items-center gap-2 text-[14px] text-white/80" data-tip={llmOn ? `Adjudicator ${llm?.model}` : `LLM offline: ${llm?.reason ?? "unknown"}`}>
          <span className="w-2.5 h-2.5 rounded-full ring-2 ring-white/30" style={{ background: !ws ? "var(--clay)" : llmOn ? "#B59CFF" : "var(--saffron)" }} />
          {!ws ? "reconnecting" : llmOn ? "LLM on" : "LLM offline"}
        </div>
        <div className="tabular text-[15px] text-white/70">{sc.id} / {SCENES[SCENES.length - 1].id}</div>
      </div>
    </div>
  );
}

export function Footer() {
  return (
    <div className="absolute bottom-0 left-0 right-0 h-7 px-16 flex items-center text-[13px] text-ink-3 z-20">
      Synthetic demo data · prices and policies are fictional · LedgerBot prototype for TBO VoyageHack 4.0
      {!RECORD_MODE && <SceneNav />}
    </div>
  );
}

/** Visible navigation for people who do not know the hotkeys. Hidden with ?record=1. */
function SceneNav() {
  const scene = useApp((s) => s.scene);
  const { setScene, next, prev, togglePresenter } = useApp.getState();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => setOpen(false), [scene]);
  useEffect(() => {
    if (!open) return;
    const close = (e: MouseEvent) => { if (!ref.current?.contains(e.target as Node)) setOpen(false); };
    const esc = (e: KeyboardEvent) => { if (e.key === "Escape") setOpen(false); };
    window.addEventListener("mousedown", close);
    window.addEventListener("keydown", esc);
    return () => { window.removeEventListener("mousedown", close); window.removeEventListener("keydown", esc); };
  }, [open]);
  const base = "h-6 inline-flex items-center gap-1 rounded-full border text-[13px] disabled:opacity-30 transition";
  const btn = `${base} border-line bg-surface text-ink-2 hover:bg-surface-2 hover:text-ink`;
  const primary = `${base} border-lagoon bg-lagoon text-white hover:brightness-110`;
  const last = scene === SCENES.length - 1;
  return (
    <div ref={ref} className="ml-auto relative flex items-center gap-1.5">
      <button className={`${btn} px-2.5`} onClick={() => resetDemo()} title="Reset all demo state (R)"><RotateCcw size={12} />Reset</button>
      <span className="w-px h-4 bg-line mx-1" />
      <button className={`${btn} pl-1.5 pr-2.5`} onClick={prev} disabled={scene === 0} aria-label="Previous scene" title="Previous scene (←)">
        <ChevronLeft size={14} />Back
      </button>
      <button className={`${btn} px-3`} onClick={() => setOpen((o) => !o)} aria-haspopup="menu" aria-expanded={open} title="Jump to any scene">
        <span className="font-mono text-ink-3">{SCENES[scene].id}</span>{SCENES[scene].title}<ChevronUp size={12} />
      </button>
      <button className={`${last ? btn : primary} pl-2.5 pr-1.5`}
        onClick={next} disabled={last} aria-label="Next scene" title="Next scene (→)">
        {last ? "Last scene" : <>Next: {SCENES[scene + 1].title}</>}<ChevronRight size={14} />
      </button>
      <button className={`${btn} px-2.5 ml-1`} onClick={togglePresenter} title="Show this scene's keys (P)"><Keyboard size={12} />Keys</button>
      <button className={`${btn} px-2.5`} onClick={() => useApp.getState().toggleResearch()} title="How this scene works and the research behind it (I)"><BookOpen size={12} />Method & research</button>
      <AnimatePresence>
        {open && (
          <motion.div role="menu" initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: 6 }} transition={T}
            className="absolute bottom-8 right-0 w-[260px] rounded-2xl border border-line bg-surface shadow-card p-1.5 z-50">
            {SCENES.map((s, i) => (
              <button key={s.id} role="menuitem" onClick={() => { setScene(i); setOpen(false); }}
                className={`w-full text-left flex items-center gap-3 px-3 py-1.5 rounded-xl text-[14px] ${i === scene ? "bg-lagoon-soft text-lagoon" : "text-ink-2 hover:bg-surface-2"}`}>
                <span className="font-mono text-[13px] text-ink-3 w-5">{s.id}</span>{s.title}
              </button>
            ))}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

/** Large previous/next arrows in the stage's side gutters, so navigation is obvious without the keyboard. */
export function EdgeArrows() {
  const scene = useApp((s) => s.scene);
  const presenter = useApp((s) => s.presenter);
  if (RECORD_MODE) return null;
  const { next, prev } = useApp.getState();
  const base = "absolute top-1/2 -translate-y-1/2 z-30 w-12 h-24 rounded-full flex items-center justify-center " +
    "border shadow-card transition hover:scale-105";
  const back = `${base} bg-surface/80 border-line text-ink-3 opacity-70 hover:opacity-100 hover:text-lagoon`;
  const fwd = `${base} bg-surface border-lagoon/40 text-lagoon opacity-95 hover:bg-lagoon hover:text-white hover:opacity-100`;
  return (
    <>
      {scene > 0 && !presenter && (
        <button className={`${back} left-2`} onClick={prev} aria-label={`Previous scene: ${SCENES[scene - 1].title}`}
          title={`Back: ${SCENES[scene - 1].title} (←)`}><ChevronLeft size={30} /></button>
      )}
      {scene < SCENES.length - 1 && (
        <button className={`${fwd} right-2`} onClick={next} aria-label={`Next scene: ${SCENES[scene + 1].title}`}
          title={`Next: ${SCENES[scene + 1].title} (→)`}><ChevronRight size={30} /></button>
      )}
    </>
  );
}

export function Rail() {
  const scene = useApp((s) => s.scene);
  const setScene = useApp((s) => s.setScene);
  return (
    <div className="absolute left-0 top-14 bottom-7 w-16 flex flex-col items-center justify-center gap-3 z-30">
      {SCENES.map((s, i) => (
        <button key={s.id} aria-label={`Scene ${s.id}, ${s.title}`} aria-current={i === scene ? "step" : undefined} onClick={() => setScene(i)} className="relative w-8 h-8 rounded-full text-[13px] font-mono flex items-center justify-center"
          style={{ background: i === scene ? "var(--lagoon)" : "var(--surface)", color: i === scene ? "#fff" : "var(--ink-3)", border: "1px solid var(--line)" }}>
          {s.id}
        </button>
      ))}
    </div>
  );
}

const KEYS: Record<string, [string, string][]> = {
  all: [["→ / ←", "next / previous scene"], ["Ctrl K or /", "find any hotel"], ["I", "method & research for this scene"], ["R", "reset demo state"], ["P", "presenter overlay"]],
  "00": [["Space", "fold rows"]],
  "01": [["1", "start left timer"], ["2", "start right timer"], ["0", "clear"]],
  "02": [["O", "onboard NovaBeds"], ["scroll / drag", "zoom and pan the graph"], ["click a hotel", "open it in the Inspector"]],
  "03": [["H / M / A / Q", "Hotel · Rooms · Activities · Review queue"], ["N", "near-miss"], ["S / D / K / U", "review: same · different · skip · undo"]],
  "04": [["1-5", "presets"], ["Enter", "run trace"]],
  "05": [["↑ / ↓", "turn the dial"]],
  "06": [["Shift+1..5", "sabotage supplier"], ["Shift+0", "heal all"]],
  "07": [["1 / 2 / 3", "objectives"]],
  "08": [["A / B", "benchmark / voting"], ["Space", "next pair / reveal"], ["L", "learn from votes"]],
  "09": [["A / B", "impact / architecture"], ["Space", "replay / draw next step"]],
};

export function PresenterOverlay() {
  const on = useApp((s) => s.presenter);
  const scene = useApp((s) => s.scene);
  const id = SCENES[scene].id;
  return (
    <AnimatePresence>
      {on && (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={T}
          className="absolute right-16 top-20 z-50 w-[380px] rounded-card bg-ink/90 text-paper p-5 shadow-card">
          <div className="text-[13px] uppercase tracking-[0.08em] opacity-60 mb-3">Presenter · scene {id}</div>
          {[...(KEYS[id] ?? []), ...KEYS.all].map(([k, d]) => (
            <div key={k + d} className="flex items-center justify-between py-1 text-[15px]">
              <span className="opacity-80">{d}</span><Kbd>{k}</Kbd>
            </div>
          ))}
        </motion.div>
      )}
    </AnimatePresence>
  );
}
