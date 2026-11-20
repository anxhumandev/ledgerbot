import { AnimatePresence, motion } from "framer-motion";
import { SCENES, useApp } from "../app/store";
import { Kbd, T } from "../design/primitives";
import { formatINR } from "../lib/format";

export function TopBar() {
  const scene = useApp((s) => s.scene);
  const cost = useApp((s) => s.cost);
  const llm = useApp((s) => s.llm);
  const ws = useApp((s) => s.wsConnected);
  const sc = SCENES[scene];
  const llmOn = llm?.enabled;
  return (
    <div className="absolute top-0 left-0 right-0 h-14 px-16 flex items-center justify-between border-b border-line/70 z-20 bg-paper/80 backdrop-blur-[2px]">
      <div className="flex items-center gap-3">
        <svg width="22" height="22" viewBox="0 0 32 32"><rect width="32" height="32" rx="8" fill="var(--lagoon)" /><g fill="#F7F4EE"><rect x="7" y="7" width="8" height="8" rx="1.5" /><rect x="17" y="7" width="8" height="8" rx="1.5" opacity=".7" /><rect x="7" y="17" width="8" height="8" rx="1.5" opacity=".7" /><rect x="17" y="17" width="8" height="8" rx="1.5" fill="var(--saffron)" /></g></svg>
        <span className="font-serif text-[26px] leading-none text-ink">Tessera</span>
      </div>
      <div className="absolute left-1/2 -translate-x-1/2 text-[14px] text-ink-3">
        <span className="font-mono">{sc.id}</span><span className="mx-2">·</span><span className="text-ink-2">{sc.title}</span>
      </div>
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-2 rounded-full border border-line bg-surface px-3 py-1 text-[13px]" data-tip="LLM spend this session vs. an LLM-only pipeline on the same pairs">
          <span className="text-iris font-medium">LLM spend</span>
          <span className="font-mono text-ink">{formatINR(cost?.tessera_llm_spend_inr, { decimals: 2 })}</span>
          <span className="text-ink-3">vs LLM-only</span>
          <span className="font-mono text-ink-2">{formatINR(cost?.llm_only_counterfactual_inr, { decimals: 2 })}{cost?.counterfactual_estimated ? " est." : ""}</span>
        </div>
        <div className="flex items-center gap-2 text-[13px] text-ink-3" data-tip={llmOn ? `Adjudicator ${llm?.model}` : `LLM offline: ${llm?.reason ?? "unknown"}`}>
          <span className="w-2.5 h-2.5 rounded-full" style={{ background: !ws ? "var(--clay)" : llmOn ? "var(--iris)" : "var(--amber)" }} />
          {!ws ? "reconnecting" : llmOn ? "LLM on" : "LLM offline"}
        </div>
        <div className="font-mono text-[14px] text-ink-2">{sc.id} / {SCENES[SCENES.length - 1].id}</div>
      </div>
    </div>
  );
}

export function Footer() {
  return (
    <div className="absolute bottom-0 left-0 right-0 h-7 px-16 flex items-center text-[12px] text-ink-3 z-20">
      Synthetic demo data · prices and policies are fictional · Tessera prototype for TBO VoyageHack 4.0
    </div>
  );
}

export function Rail() {
  const scene = useApp((s) => s.scene);
  const setScene = useApp((s) => s.setScene);
  return (
    <div className="absolute left-0 top-14 bottom-7 w-16 flex flex-col items-center justify-center gap-3 z-30">
      {SCENES.map((s, i) => (
        <button key={s.id} aria-label={`Scene ${s.id}, ${s.title}`} aria-current={i === scene ? "step" : undefined} onClick={() => setScene(i)} className="relative w-8 h-8 rounded-full text-[11px] font-mono flex items-center justify-center"
          style={{ background: i === scene ? "var(--lagoon)" : "var(--surface)", color: i === scene ? "#fff" : "var(--ink-3)", border: "1px solid var(--line)" }}>
          {s.id}
        </button>
      ))}
    </div>
  );
}

const KEYS: Record<string, [string, string][]> = {
  all: [["→ / ←", "next / previous scene"], ["R", "reset demo state"], ["P", "presenter overlay"]],
  "00": [["Space", "fold rows"]],
  "01": [["1", "start left timer"], ["2", "start right timer"], ["0", "clear"]],
  "02": [["O", "onboard NovaBeds"]],
  "03": [["H / M / A", "Hotel · Rooms · Activities"], ["N", "near-miss"]],
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
          <div className="text-[12px] uppercase tracking-[0.08em] opacity-60 mb-3">Presenter · scene {id}</div>
          {[...(KEYS[id] ?? []), ...KEYS.all].map(([k, d]) => (
            <div key={k + d} className="flex items-center justify-between py-1 text-[14px]">
              <span className="opacity-80">{d}</span><Kbd>{k}</Kbd>
            </div>
          ))}
        </motion.div>
      )}
    </AnimatePresence>
  );
}
