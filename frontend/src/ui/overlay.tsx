import { AnimatePresence, motion } from "framer-motion";
import { CheckCircle2, Info, X, XCircle } from "lucide-react";
import { type ReactNode, useEffect, useId, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { useSession } from "../lib/session";
import { Button, cx, Field } from "./core";

const FOCUSABLE = 'a[href],button:not([disabled]),textarea,input:not([disabled]),select,[tabindex]:not([tabindex="-1"])';

/** Traps focus, closes on Escape, restores focus to the opener. */
function useModal(open: boolean, onClose: () => void) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const opener = document.activeElement as HTMLElement | null;
    const t = setTimeout(() => {
      const el = ref.current?.querySelector<HTMLElement>("[data-autofocus]") ?? ref.current?.querySelector<HTMLElement>(FOCUSABLE);
      el?.focus();
    }, 20);
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") { e.stopPropagation(); onClose(); }
      if (e.key === "Tab" && ref.current) {
        const items = [...ref.current.querySelectorAll<HTMLElement>(FOCUSABLE)];
        if (!items.length) return;
        const first = items[0], last = items[items.length - 1];
        if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
        else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
      }
    };
    document.addEventListener("keydown", onKey, true);
    return () => { clearTimeout(t); document.removeEventListener("keydown", onKey, true); opener?.focus?.(); };
  }, [open]);
  return ref;
}

export function Dialog({ open, onClose, title, description, children, footer, width = 520 }: {
  open: boolean; onClose: () => void; title: ReactNode; description?: ReactNode; children?: ReactNode; footer?: ReactNode; width?: number;
}) {
  const ref = useModal(open, onClose);
  const id = useId();
  return createPortal(
    <AnimatePresence>
      {open && (
        <motion.div className="fixed inset-0 z-[80] flex items-center justify-center bg-[rgba(16,24,40,0.45)] p-4"
          initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.12 }}
          onMouseDown={(e) => { if (e.target === e.currentTarget) onClose(); }}>
          <motion.div ref={ref} role="dialog" aria-modal="true" aria-labelledby={id}
            initial={{ y: 8, opacity: 0 }} animate={{ y: 0, opacity: 1 }} exit={{ y: 8, opacity: 0 }} transition={{ duration: 0.15 }}
            className="max-h-[90vh] w-full overflow-y-auto rounded-xl border border-edge bg-panel shadow-pop" style={{ maxWidth: width }}>
            <div className="flex items-start justify-between gap-3 border-b border-edge px-5 py-4">
              <div>
                <h2 id={id} className="text-[16px] font-semibold text-fg">{title}</h2>
                {description && <p className="mt-1 text-[13px] text-fg-3">{description}</p>}
              </div>
              <button aria-label="Close" onClick={onClose} className="rounded-full p-1 text-fg-3 hover:bg-panel-3 hover:text-fg"><X size={16} /></button>
            </div>
            {children && <div className="px-5 py-4">{children}</div>}
            {footer && <div className="flex justify-end gap-2 border-t border-edge bg-panel-2 px-5 py-3">{footer}</div>}
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>,
    document.body,
  );
}

/** Confirmation for consequential actions; optionally asks for a reason (stored in the audit log). */
export function ConfirmDialog({ open, onClose, onConfirm, title, body, confirmLabel = "Confirm", tone = "primary", reason, reasonRequired, busy }: {
  open: boolean; onClose: () => void; onConfirm: (reason: string) => void; title: string; body?: ReactNode; confirmLabel?: string;
  tone?: "primary" | "accent" | "danger"; reason?: string; reasonRequired?: boolean; busy?: boolean;
}) {
  const [text, setText] = useState("");
  const [touched, setTouched] = useState(false);
  useEffect(() => { if (open) { setText(""); setTouched(false); } }, [open]);
  const invalid = reasonRequired && text.trim().length < 3;
  return (
    <Dialog open={open} onClose={onClose} title={title}
      footer={<>
        <Button variant="secondary" onClick={onClose} disabled={busy}>Cancel</Button>
        <Button variant={tone === "danger" ? "danger" : tone} loading={busy}
          onClick={() => { setTouched(true); if (!invalid) onConfirm(text.trim()); }}>{confirmLabel}</Button>
      </>}>
      {body && <div className="text-[13px] text-fg-2">{body}</div>}
      {reason !== undefined && (
        <div className="mt-4">
          <Field label={reason} error={touched && invalid ? "Give a short reason (at least 3 characters)." : null} htmlFor="confirm-reason"
            hint="Saved with the decision in the audit trail.">
            <textarea id="confirm-reason" data-autofocus value={text} onChange={(e) => setText(e.target.value)} rows={3}
              className="w-full rounded-lg border border-edge-strong bg-panel px-3 py-2 text-[13px] outline-none focus:border-brand focus:shadow-[var(--focus)]" />
          </Field>
        </div>
      )}
    </Dialog>
  );
}

export function Drawer({ open, onClose, title, children, width = 480 }: { open: boolean; onClose: () => void; title: ReactNode; children: ReactNode; width?: number }) {
  const ref = useModal(open, onClose);
  return createPortal(
    <AnimatePresence>
      {open && (
        <motion.div className="fixed inset-0 z-[70] bg-[rgba(16,24,40,0.3)]" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
          onMouseDown={(e) => { if (e.target === e.currentTarget) onClose(); }}>
          <motion.aside ref={ref} role="dialog" aria-modal="true" aria-label={typeof title === "string" ? title : "Details"}
            initial={{ x: 24, opacity: 0 }} animate={{ x: 0, opacity: 1 }} exit={{ x: 24, opacity: 0 }} transition={{ duration: 0.16 }}
            className="absolute right-0 top-0 flex h-full w-full flex-col border-l border-edge bg-panel shadow-pop" style={{ maxWidth: width }}>
            <div className="flex items-center justify-between border-b border-edge px-5 py-3.5">
              <h2 className="text-[15px] font-semibold text-fg">{title}</h2>
              <button aria-label="Close" onClick={onClose} className="rounded-full p-1 text-fg-3 hover:bg-panel-3 hover:text-fg"><X size={16} /></button>
            </div>
            <div className="flex-1 overflow-y-auto p-5 scroll-thin">{children}</div>
          </motion.aside>
        </motion.div>
      )}
    </AnimatePresence>,
    document.body,
  );
}

/** Simple accessible dropdown menu. */
export function Menu({ trigger, children, align = "right", width = 240 }: { trigger: (p: { open: boolean; toggle: () => void }) => ReactNode; children: (close: () => void) => ReactNode; align?: "left" | "right"; width?: number }) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const off = (e: MouseEvent) => { if (!ref.current?.contains(e.target as Node)) setOpen(false); };
    const esc = (e: KeyboardEvent) => { if (e.key === "Escape") setOpen(false); };
    document.addEventListener("mousedown", off);
    document.addEventListener("keydown", esc);
    return () => { document.removeEventListener("mousedown", off); document.removeEventListener("keydown", esc); };
  }, [open]);
  return (
    <div ref={ref} className="relative">
      {trigger({ open, toggle: () => setOpen((o) => !o) })}
      {open && (
        <div role="menu" className={cx("absolute top-full z-[60] mt-1.5 rounded-xl border border-edge bg-panel p-1 shadow-pop", align === "right" ? "right-0" : "left-0")} style={{ width }}>
          {children(() => setOpen(false))}
        </div>
      )}
    </div>
  );
}

export function MenuItem({ children, onClick, active, icon }: { children: ReactNode; onClick: () => void; active?: boolean; icon?: ReactNode }) {
  return (
    <button role="menuitem" onClick={onClick}
      className={cx("flex w-full items-center gap-2 rounded-lg px-2.5 py-2 text-left text-[13px] transition-colors", active ? "bg-brand-soft text-brand-ink" : "text-fg-2 hover:bg-panel-2 hover:text-fg")}>
      {icon}{children}
    </button>
  );
}

export function Toaster() {
  const toasts = useSession((s) => s.toasts);
  const dismiss = useSession((s) => s.dismiss);
  return createPortal(
    <div className="pointer-events-none fixed bottom-4 right-4 z-[90] flex w-[360px] max-w-[calc(100vw-32px)] flex-col gap-2" aria-live="polite">
      <AnimatePresence>
        {toasts.map((t) => (
          <motion.div key={t.id} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, x: 16 }} transition={{ duration: 0.15 }}
            role={t.tone === "error" ? "alert" : "status"}
            className="pointer-events-auto flex items-start gap-3 rounded-xl border border-edge bg-panel p-3 shadow-pop">
            {t.tone === "success" ? <CheckCircle2 size={18} className="mt-0.5 flex-none text-ok" /> : t.tone === "error"
              ? <XCircle size={18} className="mt-0.5 flex-none text-bad" /> : <Info size={18} className="mt-0.5 flex-none text-brand" />}
            <div className="min-w-0 flex-1">
              <div className="text-[13px] font-semibold text-fg">{t.title}</div>
              {t.body && <div className="mt-0.5 text-[12px] text-fg-3">{t.body}</div>}
            </div>
            <button aria-label="Dismiss" onClick={() => dismiss(t.id)} className="rounded p-0.5 text-fg-3 hover:text-fg"><X size={14} /></button>
          </motion.div>
        ))}
      </AnimatePresence>
    </div>,
    document.body,
  );
}
