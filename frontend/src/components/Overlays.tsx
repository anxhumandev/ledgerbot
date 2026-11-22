import { AnimatePresence, motion } from "framer-motion";
import { BookOpen, Building2, Search, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { SCENES, useApp } from "../app/store";
import { SupplierChip, T } from "../design/primitives";
import { api } from "../lib/api";
import { RESEARCH } from "../lib/research";

/** Ctrl+K hotel finder: canonical names and every supplier's spelling. Opens the golden record in the Inspector. */
export function SearchPalette() {
  const open = useApp((s) => s.searchOpen);
  const [q, setQ] = useState("");
  const [hits, setHits] = useState<any[]>([]);
  const [sel, setSel] = useState(0);
  const input = useRef<HTMLInputElement>(null);
  useEffect(() => { if (open) { setQ(""); setHits([]); setSel(0); setTimeout(() => input.current?.focus(), 30); } }, [open]);
  useEffect(() => {
    if (q.trim().length < 2) { setHits([]); return; }
    const t = setTimeout(() => api(`/search?q=${encodeURIComponent(q)}`).then((h) => { setHits(h); setSel(0); }).catch(() => undefined), 120);
    return () => clearTimeout(t);
  }, [q]);
  const close = () => useApp.getState().setSearch(false);
  const go = (h: any) => h && useApp.getState().openInspector(h.tessera_id);
  return (
    <AnimatePresence>
      {open && (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={T}
          className="absolute inset-0 z-[60] bg-[rgba(1,30,60,0.35)] flex items-start justify-center pt-[140px]" onMouseDown={close}>
          <motion.div initial={{ y: -10 }} animate={{ y: 0 }} transition={T} onMouseDown={(e) => e.stopPropagation()}
            className="w-[760px] rounded-2xl bg-surface shadow-2xl border border-line overflow-hidden">
            <div className="flex items-center gap-3 px-5 py-4 border-b border-line">
              <Search size={22} className="text-lagoon" />
              <input ref={input} value={q} onChange={(e) => setQ(e.target.value)} placeholder="Find any hotel: name, or any supplier's spelling (try “jumeira beach htl”)"
                onKeyDown={(e) => {
                  if (e.key === "Escape") close();
                  if (e.key === "ArrowDown") { e.preventDefault(); setSel((s) => Math.min(hits.length - 1, s + 1)); }
                  if (e.key === "ArrowUp") { e.preventDefault(); setSel((s) => Math.max(0, s - 1)); }
                  if (e.key === "Enter") go(hits[sel]);
                }}
                className="flex-1 bg-transparent outline-none text-[20px] text-ink placeholder:text-ink-3" />
              <button onClick={close} className="text-ink-3 hover:text-ink"><X size={20} /></button>
            </div>
            <div className="max-h-[520px] overflow-y-auto">
              {hits.map((h, i) => (
                <button key={h.tessera_id} onMouseEnter={() => setSel(i)} onClick={() => go(h)}
                  className={`w-full text-left px-5 py-3 flex items-center gap-4 border-b border-line/60 ${i === sel ? "bg-lagoon-soft" : "hover:bg-surface-2"}`}>
                  <Building2 size={20} className="text-lagoon flex-none" />
                  <div className="min-w-0 flex-1">
                    <div className="text-[17px] font-semibold text-ink truncate">{h.name}</div>
                    <div className="text-[14px] text-ink-3 truncate">
                      {h.neighbourhood ?? h.city}{h.stars ? ` · ${"★".repeat(h.stars)}` : ""} · {h.n_records} supplier listing{h.n_records > 1 ? "s" : ""}
                      {h.matched !== h.name && <> · matched “{h.matched}”</>}
                    </div>
                  </div>
                  <div className="flex gap-1 flex-none">{h.suppliers.map((s: string) => <SupplierChip key={s} code={s} short />)}</div>
                </button>
              ))}
              {q.trim().length >= 2 && !hits.length && <div className="px-5 py-6 text-[16px] text-ink-3">No hotel matches “{q}”.</div>}
              {q.trim().length < 2 && (
                <div className="px-5 py-5 text-[15px] text-ink-3">Search every golden record in all five cities. ↑ ↓ to choose, Enter to open in the Inspector, Esc to close.</div>
              )}
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

/** "Method & research" drawer for the current scene. */
export function ResearchPanel() {
  const open = useApp((s) => s.research);
  const scene = useApp((s) => s.scene);
  const { id, key } = SCENES[scene];
  const n = RESEARCH[key];
  return (
    <AnimatePresence>
      {open && n && (
        <motion.aside initial={{ x: 40, opacity: 0 }} animate={{ x: 0, opacity: 1 }} exit={{ x: 40, opacity: 0 }} transition={T}
          className="absolute right-6 top-20 bottom-12 z-[55] w-[560px] rounded-2xl bg-surface shadow-2xl border border-line overflow-y-auto">
          <div className="sticky top-0 bg-navy text-white px-6 py-4 flex items-center gap-3">
            <BookOpen size={20} className="text-[color:var(--saffron)]" />
            <div className="flex-1">
              <div className="text-[13px] uppercase tracking-[0.06em] text-white/70 font-semibold">Method & research · scene {id}</div>
              <div className="text-[19px] font-semibold">{SCENES[scene].title}</div>
            </div>
            <button onClick={() => useApp.getState().toggleResearch()} className="text-white/80 hover:text-white"><X size={20} /></button>
          </div>
          <div className="px-6 py-5 space-y-5 text-[16px] leading-relaxed text-ink">
            <Section title="The problem">{n.problem}</Section>
            <Section title="How LedgerBot solves it"><ul className="list-disc pl-5 space-y-1.5">{n.method.map((m) => <li key={m}>{m}</li>)}</ul></Section>
            <Section title="Research it builds on"><ul className="list-disc pl-5 space-y-1.5 text-ink-2">{n.research.map((m) => <li key={m}>{m}</li>)}</ul></Section>
            <Section title="In the enterprise build">{n.enterprise}</Section>
            <div className="rounded-xl bg-surface-2 px-4 py-3 text-[15px] text-ink-2"><b className="text-ink">What is real here: </b>{n.real}</div>
          </div>
        </motion.aside>
      )}
    </AnimatePresence>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div>
      <div className="text-[13px] uppercase tracking-[0.06em] text-lagoon font-semibold mb-1.5">{title}</div>
      <div>{children}</div>
    </div>
  );
}
