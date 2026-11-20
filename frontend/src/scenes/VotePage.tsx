import { AnimatePresence, motion } from "framer-motion";
import { useEffect, useRef, useState } from "react";
import { useApp } from "../app/store";
import { T } from "../design/primitives";
import { api, post } from "../lib/api";
import { qs, SUPPLIERS } from "../lib/format";
import { connectWS, useTopic } from "../lib/ws";

const NICK_KEY = "tessera.nickname";
const ANS = [
  { v: "same", label: "Same" },
  { v: "different", label: "Different" },
  { v: "same_room_diff_offer", label: "Same room, different offer" },
];
const LABEL: Record<string, string> = { same: "Same", different: "Different", same_room_diff_offer: "Same room, different offer", abstain: "Abstain → human review" };

function readNick() {
  try { return localStorage.getItem(NICK_KEY) ?? ""; } catch { return ""; }
}

export default function VotePage() {
  const [nick, setNick] = useState(readNick());
  const [draft, setDraft] = useState("");
  const [pair, setPair] = useState<any>(null);
  const [mine, setMine] = useState<string | null>(null);
  const [reveal, setReveal] = useState<any>(null);
  const [now, setNow] = useState(Date.now());
  const requestedSession = qs.get("s");
  const activeSession = useRef<string | null>(null);
  const [stale, setStale] = useState(false);
  const [message, setMessage] = useState("");
  const [sending, setSending] = useState(false);
  const roundVersion = useRef(0);
  const connected = useApp((s) => s.wsConnected);
  useEffect(() => {
    connectWS();
    const id = setInterval(() => setNow(Date.now()), 200);
    return () => clearInterval(id);
  }, []);
  useEffect(() => {
    let active = true;
    const restore = async () => {
      const version = roundVersion.current;
      try {
        const s = await api("/vote/state?nickname=" + encodeURIComponent(nick));
        if (!active || version !== roundVersion.current) return;
        activeSession.current = s.session;
        setStale(!!requestedSession && s.session !== requestedSession);
        setPair(s.pair);
        setReveal(s.reveal ?? null);
        setMine(s.answer ?? null);
        setMessage("");
      } catch { if (active) setMessage("Waiting for the voting server…"); }
    };
    restore();
    window.addEventListener("focus", restore);
    return () => { active = false; window.removeEventListener("focus", restore); };
  }, [nick, connected, requestedSession]);

  useTopic("vote", (m) => {
    if (m.type === "reset" || (requestedSession && m.payload.session !== requestedSession)) {
      roundVersion.current++;
      setStale(!!requestedSession && m.payload.session !== requestedSession);
      activeSession.current = m.payload.session;
      setPair(null); setMine(null); setReveal(null); setSending(false); setMessage("");
      return;
    }
    if (m.type === "pair" || m.type === "reveal") {
      activeSession.current = m.payload.session;
      roundVersion.current++;
      setSending(false); setMessage("");
    }
    if (m.type === "pair") { setPair(m.payload); setMine(null); setReveal(null); }
    if (m.type === "reveal") setReveal(m.payload);
  });
  const cast = async (v: string) => {
    if (!pair || mine || sending || reveal || !activeSession.current) return;
    const version = roundVersion.current;
    setSending(true); setMessage("");
    try {
      const result = await post("/vote/cast", { nickname: nick, idx: pair.idx, answer: v, session: activeSession.current });
      if (version !== roundVersion.current) return;
      if (result.ok) setMine(result.answer ?? v);
      else if (result.reason === "stale session") setStale(true);
      else setMessage("Voting has closed for this pair.");
    } catch { if (version === roundVersion.current) setMessage("Vote could not be confirmed. Tap your answer to retry."); }
    finally { if (version === roundVersion.current) setSending(false); }
  };
  const duration = pair?.countdown ?? 10;
  const left = pair ? Math.max(0, Math.min(duration, pair.opened_at + duration - now / 1000)) : 0;

  if (stale) return <div className="px-5 py-10 text-xl">This session has ended. Scan the current QR code on the screen to join.</div>;

  if (!nick) {
    return (
      <div className="min-h-full bg-paper px-5 py-10">
        <div className="font-serif text-[40px] leading-tight">Judges vs Machine</div>
        <p className="text-ink-2 mt-2 text-[16px]">Pick a nickname for the leaderboard.</p>
        <input value={draft} onChange={(e) => setDraft(e.target.value)} maxLength={24} placeholder="Nickname"
          className="mt-6 w-full rounded-2xl border border-line bg-surface px-4 py-4 text-[20px] outline-none focus:border-lagoon" />
        <button disabled={!draft.trim()} onClick={() => { try { localStorage.setItem(NICK_KEY, draft.trim()); } catch { /* private mode */ } setNick(draft.trim()); }}
          className="mt-4 w-full rounded-2xl bg-lagoon text-white py-4 text-[18px] font-medium disabled:opacity-40">Join</button>
      </div>
    );
  }
  return (
    <div className="min-h-full bg-paper px-4 py-5 overflow-y-auto" style={{ height: "100%" }}>
      <div className="flex items-center justify-between">
        <div className="font-serif text-[26px]">LedgerBot</div>
        <div className="text-[14px] text-ink-3">{nick}</div>
      </div>
      {message && <p role="status" className="mt-4 text-sm text-ink-2">{message}</p>}
      {!pair ? (
        <div className="mt-24 text-center text-[22px] text-ink-2">Look at the screen 👀</div>
      ) : (
        <div className="mt-4">
          <div className="flex items-center justify-between text-[14px] text-ink-3">
            <span>Pair {pair.idx + 1} / {pair.total} · {pair.kind === "room" ? "two rate offers" : "two hotel listings"}</span>
            {!reveal && (
              <svg width="40" height="40" viewBox="0 0 40 40">
                <circle cx="20" cy="20" r="16" fill="none" stroke="var(--line)" strokeWidth="4" />
                <circle cx="20" cy="20" r="16" fill="none" stroke={left < 3 ? "var(--clay)" : "var(--lagoon)"} strokeWidth="4" strokeLinecap="round"
                  strokeDasharray={`${2 * Math.PI * 16}`} strokeDashoffset={`${2 * Math.PI * 16 * (1 - left / duration)}`} transform="rotate(-90 20 20)" />
                <text x="20" y="25" textAnchor="middle" fontSize="13" fontFamily="Geist Mono" fill="var(--ink)">{Math.ceil(left)}</text>
              </svg>
            )}
          </div>
          {[pair.a, pair.b].map((x: any, k: number) => {
            const other = k === 0 ? pair.b : pair.a;
            const diff = (f: string) => (x[f] ?? "") !== (other[f] ?? "");
            return (
              <div key={k} className="mt-3 rounded-2xl bg-surface border border-line p-4">
                <span className="text-[12px] font-medium rounded-full px-2 py-0.5" style={{ background: `${SUPPLIERS[x.supplier]?.color}18`, color: SUPPLIERS[x.supplier]?.color }}>{SUPPLIERS[x.supplier]?.name}</span>
                <div className={`text-[18px] mt-2 font-medium ${diff("name") ? "bg-saffron-soft rounded px-1 -mx-1" : ""}`}>{x.name}</div>
                <div className={`text-[14px] text-ink-2 mt-1 ${diff("address") ? "bg-saffron-soft rounded px-1 -mx-1" : ""}`}>{x.address ?? "—"}</div>
                <div className={`text-[14px] text-ink-2 font-mono ${diff("phone") ? "bg-saffron-soft rounded px-1 -mx-1" : ""}`}>{x.phone ?? "—"}</div>
                <div className="text-[13px] text-ink-3 font-mono">{x.coords}{x.stars ? ` · ${x.stars}★` : ""}</div>
              </div>
            );
          })}
          <AnimatePresence mode="wait">
            {!reveal ? (
              <motion.div key="btns" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={T} className="mt-4 space-y-3">
                {ANS.map((a) => (
                  <button key={a.v} onClick={() => cast(a.v)} disabled={sending || !!mine || left <= 0}
                    className={`w-full rounded-2xl py-5 text-[19px] font-medium border transition ${mine === a.v ? "bg-lagoon text-white border-lagoon" : "bg-surface border-line text-ink"} disabled:opacity-60`}>
                    {a.label}
                  </button>
                ))}
                {mine && <div className="text-center text-[16px] text-[color:var(--sage-ink)]">Locked in ✓</div>}
              </motion.div>
            ) : (
              <motion.div key="rev" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={T}
                className={`mt-4 rounded-2xl p-5 ${mine === reveal.truth ? "bg-sage-soft" : "bg-clay-soft"}`}>
                <div className="text-[22px] font-medium">{mine === reveal.truth ? "Correct ✓" : mine ? "Not quite" : "No vote"}</div>
                <div className="text-[16px] mt-1">Answer: {LABEL[reveal.truth]}</div>
                <div className="text-[16px] text-lagoon mt-1">LedgerBot: {LABEL[reveal.tessera.answer]}</div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      )}
      <div className="mt-8 text-[11px] text-ink-3">Synthetic demo data · prices and policies are fictional</div>
    </div>
  );
}
