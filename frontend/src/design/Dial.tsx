import { motion } from "framer-motion";
import { useEffect, useRef, useState } from "react";

/** Rotary knob on a log scale. Drag vertically/rotationally, arrow keys, or a USB MIDI knob (CC 1). */
export function Dial({ value, min, max, onChange, onCommit, size = 260, format }: {
  value: number; min: number; max: number; onChange: (v: number) => void; onCommit?: (v: number) => void; size?: number;
  format: (v: number) => string;
}) {
  const START = -135, SWEEP = 270;
  const toT = (v: number) => (Math.log(v) - Math.log(min)) / (Math.log(max) - Math.log(min));
  const fromT = (t: number) => Math.exp(Math.log(min) + Math.max(0, Math.min(1, t)) * (Math.log(max) - Math.log(min)));
  const t = toT(value);
  const angle = START + t * SWEEP;
  const ref = useRef<HTMLDivElement>(null);
  const drag = useRef<{ y: number; t: number } | null>(null);
  const [midi, setMidi] = useState(false);
  const valRef = useRef(value);
  valRef.current = value;

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== "ArrowUp" && e.key !== "ArrowDown" && e.key !== "ArrowRight" && e.key !== "ArrowLeft") return;
      if (e.key === "ArrowLeft" || e.key === "ArrowRight") {
        if (!e.shiftKey) return; // plain left/right navigate scenes
      }
      e.preventDefault();
      e.stopPropagation();
      const step = (e.key === "ArrowUp" || e.key === "ArrowRight" ? 1 : -1) * 0.025;
      const v = fromT(toT(valRef.current) + step);
      onChange(v);
      onCommit?.(v);
    };
    window.addEventListener("keydown", onKey, true);
    return () => window.removeEventListener("keydown", onKey, true);
  }, [onChange, onCommit]);

  useEffect(() => {
    let access: any;
    const nav: any = navigator;
    if (!nav.requestMIDIAccess) return;
    let commitTimer: any;
    nav.requestMIDIAccess().then((a: any) => {
      access = a;
      const attach = () => {
        a.inputs.forEach((inp: any) => {
          setMidi(true);
          inp.onmidimessage = (m: any) => {
            const [status, cc, val] = m.data;
            if ((status & 0xf0) === 0xb0 && cc === 1) {
              const v = fromT(val / 127);
              onChange(v);
              clearTimeout(commitTimer);
              commitTimer = setTimeout(() => onCommit?.(v), 120);
            }
          };
        });
      };
      attach();
      a.onstatechange = attach;
    }).catch(() => undefined);
    return () => access?.inputs?.forEach((i: any) => (i.onmidimessage = null));
  }, []);

  const onDown = (e: React.PointerEvent) => {
    (e.target as HTMLElement).setPointerCapture(e.pointerId);
    drag.current = { y: e.clientY, t };
  };
  const onMove = (e: React.PointerEvent) => {
    if (!drag.current) return;
    const dt = (drag.current.y - e.clientY) / 320;
    onChange(fromT(drag.current.t + dt));
  };
  const onUp = () => {
    if (drag.current) onCommit?.(valRef.current);
    drag.current = null;
  };

  const r = size / 2;
  const ticks = Array.from({ length: 28 }, (_, i) => START + (i / 27) * SWEEP);
  const arc = (a0: number, a1: number, rad: number) => {
    const p = (a: number) => [r + rad * Math.sin((a * Math.PI) / 180), r - rad * Math.cos((a * Math.PI) / 180)];
    const [x0, y0] = p(a0), [x1, y1] = p(a1);
    return `M ${x0} ${y0} A ${rad} ${rad} 0 ${a1 - a0 > 180 ? 1 : 0} 1 ${x1} ${y1}`;
  };
  return (
    <div className="flex flex-col items-center select-none">
      <div ref={ref} style={{ width: size, height: size }} className="relative cursor-grab active:cursor-grabbing touch-none"
        onPointerDown={onDown} onPointerMove={onMove} onPointerUp={onUp} onPointerCancel={onUp}>
        <svg width={size} height={size} className="absolute inset-0">
          <path d={arc(START, START + SWEEP, r - 10)} fill="none" stroke="var(--line)" strokeWidth={6} strokeLinecap="round" />
          <path d={arc(START, Math.max(START + 0.5, angle), r - 10)} fill="none" stroke="var(--lagoon)" strokeWidth={6} strokeLinecap="round" />
          {ticks.map((a, i) => {
            const rad1 = r - 24, rad2 = r - (i % 9 === 0 ? 34 : 29);
            const s = Math.sin((a * Math.PI) / 180), c = Math.cos((a * Math.PI) / 180);
            return <line key={i} x1={r + rad1 * s} y1={r - rad1 * c} x2={r + rad2 * s} y2={r - rad2 * c} stroke="var(--ink-3)" strokeWidth={i % 9 === 0 ? 2 : 1} opacity={0.6} />;
          })}
        </svg>
        <motion.div animate={{ rotate: angle }} transition={{ type: "spring", stiffness: 260, damping: 30 }}
          className="absolute rounded-full bg-surface border border-line shadow-card"
          style={{ inset: 44, boxShadow: "0 1px 2px rgba(21,23,28,.06), 0 18px 40px rgba(21,23,28,.12), inset 0 -6px 14px rgba(21,23,28,.05)" }}>
          <div className="absolute left-1/2 -translate-x-1/2 top-3 w-1.5 h-7 rounded-full bg-lagoon" />
        </motion.div>
        <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
          <div className="font-mono text-[34px] text-ink leading-none">{format(value)}</div>
          <div className="mt-1 text-[11px] uppercase tracking-[0.08em] text-ink-3">max false merges</div>
        </div>
      </div>
      <div className="mt-2 text-[12px] text-ink-3">drag · ↑/↓ {midi ? "· MIDI knob connected" : ""}</div>
    </div>
  );
}
