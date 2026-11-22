import { AnimatePresence, motion } from "framer-motion";
import { Play } from "lucide-react";
import { type ReactNode, useEffect, useMemo, useState } from "react";
import { Button, Caption, Card, Chip, Photo, SceneHeader, Skeleton, SupplierChip, T, Toggle, cx, rise } from "../design/primitives";
import { api } from "../lib/api";
import { BOARD, formatINR, ms, num } from "../lib/format";
import { useFetch, useHotkeys } from "../lib/hooks";

type Mode = "portal" | "api";
const AREAS: [string, string][] = [["marina", "Dubai Marina"], ["downtown", "Downtown"], ["jbr", "JBR"], ["palm", "Palm Jumeirah"]];
const NIGHTS = 3;

/** One clean shelf, two channels: the agent portal and the Clean Feed API read the same golden records. */
export default function Shelf() {
  const [mode, setMode] = useState<Mode>("portal");
  useHotkeys({ "1": () => setMode("portal"), "2": () => setMode("api") });
  return (
    <div className="h-full flex flex-col">
      <SceneHeader
        headline="One clean shelf. Two channels."
        subline="Agents book on the portal, API customers call the feed. Both get the same de-duplicated hotels, real rooms and best supplier offer."
        right={<Toggle value={mode} onChange={setMode} options={[{ value: "portal", label: "Agent portal" }, { value: "api", label: "Clean Feed API" }]} />}
      />
      <div className="flex-1 min-h-0">
        <AnimatePresence mode="wait">
          <motion.div key={mode} className="h-full" initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} transition={T}>
            {mode === "portal" ? <Portal /> : <ApiView />}
          </motion.div>
        </AnimatePresence>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ agent portal */
function Portal() {
  const [area, setArea] = useState("marina");
  const [board, setBoard] = useState<string>("any");
  const [freeCancel, setFreeCancel] = useState(false);
  const [sort, setSort] = useState<"recommended" | "price">("recommended");
  const { data } = useFetch<any>(`/listings?area=${area}&strategy=expected_value&nights=${NIGHTS}`, [area]);
  const { data: search } = useFetch<any>(`/v1/search?area=${area}&nights=${NIGHTS}`, [area]);

  const cards = useMemo(() => {
    if (!data) return [];
    const keep = (s: any) => (board === "any" || s.board === board) && (!freeCancel || s.refundable);
    const out = data.cards.map((c: any) => {
      const rooms = c.rooms.map((g: any) => ({ ...g, slots: g.slots.filter(keep) })).filter((g: any) => g.slots.length);
      const prices = rooms.flatMap((g: any) => g.slots.map((s: any) => s.winner.price));
      return { ...c, rooms, from: prices.length ? Math.min(...prices) : null };
    }).filter((c: any) => c.rooms.length);
    if (sort === "price") out.sort((a: any, b: any) => a.from - b.from);
    return out;
  }, [data, board, freeCancel, sort]);

  const boards = useMemo(() => {
    const set = new Set<string>();
    data?.cards.forEach((c: any) => c.rooms.forEach((g: any) => g.slots.forEach((s: any) => set.add(s.board))));
    return ["RO", "BB", "HB", "FB", "AI"].filter((b) => set.has(b));
  }, [data]);

  return (
    <div className="grid grid-cols-[320px_minmax(0,1fr)] gap-6 h-full">
      <div className="flex flex-col gap-4 min-h-0">
        <Card {...rise(0)} className="p-5">
          <Caption>Search</Caption>
          <div className="mt-1 text-[17px] font-medium">Dubai · 2 adults · {NIGHTS} nights</div>
          <div className="mt-3 flex flex-wrap gap-1.5">
            {AREAS.map(([k, label]) => (
              <button key={k} onClick={() => setArea(k)}
                className={cx("rounded-full px-3 py-1 text-[14px] border", area === k ? "bg-ink text-paper border-ink" : "border-line text-ink-2 hover:bg-surface-2")}>{label}</button>
            ))}
          </div>
          <Caption className="mt-5">Meal plan</Caption>
          <div className="mt-2 flex flex-wrap gap-1.5">
            {["any", ...boards].map((b) => (
              <button key={b} onClick={() => setBoard(b)}
                className={cx("rounded-full px-3 py-1 text-[14px] border", board === b ? "bg-lagoon text-white border-lagoon" : "border-line text-ink-2 hover:bg-surface-2")}>
                {b === "any" ? "Any" : BOARD[b] ?? b}
              </button>
            ))}
          </div>
          <label className="mt-5 flex items-center gap-2 text-[15px] cursor-pointer select-none">
            <input type="checkbox" checked={freeCancel} onChange={(e) => setFreeCancel(e.target.checked)} className="w-4 h-4 accent-[color:var(--lagoon)]" />
            Free cancellation only
          </label>
          <Caption className="mt-5">Sort</Caption>
          <div className="mt-2"><Toggle value={sort} onChange={setSort} options={[{ value: "recommended", label: "Recommended" }, { value: "price", label: "Lowest price" }]} /></div>
        </Card>
        <Card {...rise(1)} className="p-5">
          <Caption>Behind this screen</Caption>
          {search ? (
            <div className="mt-2 space-y-2 text-[15px] text-ink-2">
              <div><b className="font-mono text-ink">{num(search.meta.source_supplier_rates)}</b> supplier rates from <b className="font-mono text-ink">{num(search.meta.source_supplier_records)}</b> supplier hotel records</div>
              <div>→ <b className="font-mono text-lagoon">{num(search.results.length)}</b> real hotels in {search.meta.area}</div>
              <div className="text-[13px] text-ink-3">One choice per meal plan and cancellation term; the best supplier offer is pre-selected by expected value, the rest stay as fallbacks.</div>
            </div>
          ) : <Skeleton className="h-20 mt-2" />}
        </Card>
      </div>
      <div className="min-h-0 overflow-y-auto scroll-quiet pr-1 space-y-3">
        {!data && <Skeleton className="w-full h-full" />}
        {data && !cards.length && <div className="h-40 rounded-card border border-dashed border-line flex items-center justify-center text-ink-3 text-[18px]">No hotel matches these filters.</div>}
        {cards.map((c: any, i: number) => <HotelResult key={c.tessera_id} c={c} i={i} />)}
      </div>
    </div>
  );
}

function HotelResult({ c, i }: { c: any; i: number }) {
  const [pick, setPick] = useState<string | null>(null);
  const all = c.rooms.flatMap((g: any) => g.slots.map((s: any) => ({ ...s, room: g.name })));
  const sel = all.find((s: any) => s.slot_ref === pick) ?? all[0];
  return (
    <Card layout initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ ...T, delay: Math.min(i, 6) * 0.04 }} className="p-4 flex gap-5">
      <Photo src={c.hero} name={c.name} className="w-[180px] h-[132px] rounded-xl flex-none" />
      <div className="w-[260px] flex-none min-w-0">
        <div className="text-[19px] font-medium leading-tight">{c.name}</div>
        <div className="text-[14px] text-ink-3 mt-0.5">{"★".repeat(c.stars || 0)} · {c.neighbourhood}</div>
        <div className="mt-2 flex flex-wrap gap-1.5">
          <Chip variant="lagoon">best of {c.suppliers.length} suppliers</Chip>
          <Chip>{c.n_rooms} real rooms</Chip>
        </div>
        <div className="mt-3 text-[13px] text-ink-3">from</div>
        <div className="font-mono text-[22px] leading-none">{formatINR(c.from)}<span className="text-[13px] text-ink-3"> / {NIGHTS} nights</span></div>
      </div>
      <div className="flex-1 min-w-0 space-y-2">
        {c.rooms.map((g: any) => (
          <div key={g.group}>
            <div className="flex items-center gap-2 text-[15px]"><span className="font-medium">{g.name}</span>{g.tier === "Secondary" && <Chip variant="amber">secondary match</Chip>}</div>
            <div className="mt-1 flex flex-wrap gap-1.5">
              {g.slots.map((s: any) => (
                <button key={s.slot_ref} onClick={() => setPick(s.slot_ref)}
                  className={cx("rounded-xl border px-3 py-1.5 text-left text-[14px] transition",
                    sel?.slot_ref === s.slot_ref ? "border-lagoon bg-lagoon-soft" : "border-line hover:border-lagoon")}>
                  <span className="font-medium">{BOARD[s.board] ?? s.board}</span>
                  <span className="text-ink-3"> · {s.refundable ? (s.winner.cancel_hours ? `free cancel ${s.winner.cancel_hours} h` : "free cancel") : "non-refundable"}</span>
                  <span className="ml-2 font-mono">{formatINR(s.winner.price)}</span>
                </button>
              ))}
            </div>
          </div>
        ))}
        {sel && (
          <div className="pt-1 text-[13px] text-ink-2 flex items-center gap-2 min-w-0">
            <Chip variant="saffron">selected</Chip>
            <span className="truncate">{sel.room} · {sel.why}{sel.n_offers > 1 ? ` · ${sel.n_offers - 1} fallback offer${sel.n_offers > 2 ? "s" : ""} held` : ""}</span>
          </div>
        )}
      </div>
    </Card>
  );
}

/* ------------------------------------------------------------------ clean feed API */
function ApiView() {
  const { data: featured } = useFetch<any[]>("/clusters/featured");
  const [tid, setTid] = useState<string | null>(null);
  const id = tid ?? featured?.[0]?.tessera_id ?? null;
  const { data: raw } = useFetch<any>(id ? `/feed/raw/${id}?nights=${NIGHTS}` : null, [id]);
  const [clean, setClean] = useState<any>(null);
  const [rtt, setRtt] = useState<number | null>(null);
  const [calls, setCalls] = useState(0);
  const path = id ? `/v1/hotels/${id}/offers?nights=${NIGHTS}` : null;

  const call = async () => {
    if (!path) return;
    const t0 = performance.now();
    const body = await api(path);
    setRtt(performance.now() - t0);
    setClean(body);
    setCalls((n) => n + 1);
  };
  useEffect(() => { setClean(null); setRtt(null); if (path) call(); }, [path]);
  useHotkeys({ " ": () => call() });

  const st = raw?.stats;
  return (
    <div className="h-full flex flex-col gap-4">
      <div className="flex items-center gap-3">
        <div className="flex gap-2 flex-wrap flex-1">
          {featured?.slice(0, 6).map((f) => (
            <button key={f.tessera_id} onClick={() => setTid(f.tessera_id)}
              className={cx("rounded-full px-3 py-1 text-[14px] border", f.tessera_id === id ? "bg-ink text-paper border-ink" : "border-line text-ink-2 hover:bg-surface-2")}>{f.name}</button>
          ))}
        </div>
      </div>
      <div className="grid grid-cols-2 gap-6 flex-1 min-h-0">
        <div className="flex flex-col min-h-0">
          <div className="flex items-baseline justify-between mb-2">
            <div className="text-[20px] font-medium">What {st ? st.payloads : "the"} suppliers send</div>
            <div className="text-[13px] text-ink-3">field layouts illustrative · values from the raw feed</div>
          </div>
          <div className="flex-1 min-h-0 overflow-y-auto scroll-quiet space-y-3 pr-1">
            {!raw && <Skeleton className="w-full h-full" />}
            {raw?.suppliers.map((s: any, i: number) => (
              <Card key={s.supplier} {...rise(i)} className="overflow-hidden">
                <div className="flex items-center gap-2 px-4 py-2 bg-surface-2 border-b border-line">
                  <SupplierChip code={s.supplier} />
                  <span className="ml-auto text-[13px] text-ink-3 font-mono">{s.n_rates} rates · {num(s.bytes)} bytes</span>
                </div>
                <JsonView value={trimRates(s.payload, 3)} compact className="px-4 py-3 max-h-[250px] overflow-hidden" />
              </Card>
            ))}
          </div>
        </div>
        <div className="flex flex-col min-h-0">
          <div className="flex items-center justify-between mb-2 gap-3">
            <div className="text-[20px] font-medium text-lagoon">What LedgerBot's API returns</div>
            <Button variant="soft" onClick={call} kbd="Space" className="!py-1 !px-3 !text-[14px]"><Play size={14} />Call live</Button>
          </div>
          <Card className="flex-1 min-h-0 flex flex-col overflow-hidden">
            <div className="px-4 py-2 bg-navy text-white font-mono text-[14px] flex items-center gap-3">
              <span className="text-[color:var(--saffron)] font-semibold">GET</span>
              <span className="truncate">/api{path ?? ""}</span>
              {clean && (
                <span key={calls} className="ml-auto flex-none text-white/80 text-[13px]">
                  200 · server {ms(clean.meta.server_ms)} · round trip {ms(rtt)}
                </span>
              )}
            </div>
            <div className="flex-1 min-h-0 overflow-y-auto scroll-quiet">
              {clean ? <JsonView value={clean} className="px-4 py-3" /> : <Skeleton className="m-4 h-[80%]" />}
            </div>
          </Card>
        </div>
      </div>
      {st && (
        <div className="flex items-center gap-x-6 gap-y-1 flex-wrap text-[16px] text-ink-2 font-mono">
          <span><b className="text-ink">{st.payloads}</b> payloads · <b className="text-ink">{st.rates}</b> rates · <b className="text-ink">{st.board_vocabulary}</b> meal-plan spellings · <b className="text-ink">{st.cancellation_vocabulary}</b> cancellation spellings</span>
          <span className="text-lagoon">→ 1 response · <b>{st.clean_rooms}</b> real rooms · <b>{st.clean_offers}</b> offers, each with ranked fallbacks</span>
          <Chip variant="neutral" className="ml-auto">same golden record as the portal · no LLM call at request time</Chip>
        </div>
      )}
    </div>
  );
}

/** Keep the first n entries of every array so a payload fits on screen; note how many were cut. */
function trimRates(v: any, n: number): any {
  if (Array.isArray(v)) return v.length > n ? [...v.slice(0, n).map((x) => trimRates(x, n)), `… ${v.length - n} more`] : v.map((x) => trimRates(x, n));
  if (v && typeof v === "object") return Object.fromEntries(Object.entries(v).map(([k, x]) => [k, trimRates(x, n)]));
  return v;
}

/** Pretty-print the top level, keep every nested object on one line (one line per supplier rate). */
function compactJson(v: any, depth = 0): string {
  const pad = "  ".repeat(depth + 1);
  const NL = "\n";
  const one = (x: any) => JSON.stringify(x, null, 1).replace(/\n\s*/g, " ");
  if (Array.isArray(v)) {
    if (!v.length) return "[]";
    const rows = v.map((x) => pad + (x && typeof x === "object" && !Array.isArray(x) ? one(x) : compactJson(x, depth + 1)));
    return "[" + NL + rows.join("," + NL) + NL + "  ".repeat(depth) + "]";
  }
  if (v && typeof v === "object") {
    if (depth >= 1) return one(v);
    const rows = Object.entries(v).map(([k, x]) => `${pad}${JSON.stringify(k)}: ${compactJson(x, depth + 1)}`);
    return "{" + NL + rows.join("," + NL) + NL + "}";
  }
  return JSON.stringify(v);
}

const TOKEN = /("(?:\\.|[^"\\])*")(\s*:)?|\b(true|false|null)\b|(-?\d+(?:\.\d+)?(?:e[+-]?\d+)?)/g;

/** Minimal JSON pretty-printer with colour for keys, strings, numbers and literals. */
function JsonView({ value, className, compact = false }: { value: any; className?: string; compact?: boolean }) {
  const text = compact ? compactJson(value) : JSON.stringify(value, null, 2);
  const parts: ReactNode[] = [];
  let last = 0;
  let k = 0;
  for (const m of text.matchAll(TOKEN)) {
    const at = m.index ?? 0;
    if (at > last) parts.push(text.slice(last, at));
    if (m[1] && m[2]) parts.push(<span key={k++} className="text-[color:var(--lagoon)]">{m[1]}</span>, m[2]);
    else if (m[1]) parts.push(<span key={k++} className={m[1].startsWith('"…') ? "text-ink-3 italic" : "text-[color:var(--saffron-ink)]"}>{m[1]}</span>);
    else if (m[3]) parts.push(<span key={k++} className="text-iris">{m[3]}</span>);
    else parts.push(<span key={k++} className="text-[color:var(--sage-ink)]">{m[4]}</span>);
    last = at + m[0].length;
  }
  parts.push(text.slice(last));
  return <pre className={cx("font-mono text-[13px] leading-[1.45] whitespace-pre-wrap break-words text-ink-2", className)}>{parts}</pre>;
}
