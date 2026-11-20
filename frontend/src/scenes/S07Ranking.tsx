import { motion } from "framer-motion";
import { useState } from "react";
import { Caption, Card, Chip, Cite, Photo, SceneHeader, Skeleton, SupplierChip, T, Toggle } from "../design/primitives";
import { formatINR } from "../lib/format";
import { useFetch, useHotkeys } from "../lib/hooks";

type Mode = "relevance" | "business" | "risk";

function Column({ persona, mode }: { persona: string; mode: Mode }) {
  const { data } = useFetch<any>(`/ranking?persona=${persona}&mode=${mode}`, [mode]);
  if (!data) return <Skeleton className="h-full" />;
  const p = data.persona;
  return (
    <div className="flex flex-col gap-3 min-h-0">
      <Card className="p-5 flex items-center gap-4">
        <div className="w-14 h-14 rounded-full bg-lagoon text-white font-serif text-[30px] flex items-center justify-center">{p.initial}</div>
        <div>
          <div className="text-[20px] font-medium">{p.name}, {p.origin}</div>
          <div className="text-[14px] text-ink-2">{p.profile}</div>
        </div>
        <div className="ml-auto text-right">
          <Caption>Kendall τ vs relevance</Caption>
          <div className="font-mono text-[22px]">{data.kendall_tau.toFixed(2)}</div>
          {data.business_scale < 1 && <div className="text-[11px] text-[color:var(--amber-ink)]">guardrail scaled business weights ×{data.business_scale}</div>}
        </div>
      </Card>
      <div className="flex flex-col gap-2">
        {data.results.map((r: any, i: number) => (
          <motion.div key={r.tessera_id} layout transition={{ ...T, duration: 0.45 }}
            className="bg-surface border border-line rounded-2xl shadow-card p-3 flex gap-3 items-center">
            <span className="font-mono text-[18px] text-ink-3 w-6 text-center">{i + 1}</span>
            <Photo src={r.hero} name={r.name} className="w-[64px] h-[64px] rounded-xl flex-none" />
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2">
                <span className="text-[16px] font-medium truncate">{r.name}</span>
                <span className="text-[12px] text-ink-3 whitespace-nowrap">{"★".repeat(r.stars)} · {r.neighbourhood}</span>
              </div>
              <div className="mt-1 flex flex-wrap gap-1.5">
                {r.chips.map((c: string) => <Chip key={c} variant={c.startsWith("Platinum") ? "saffron" : c.includes("confirms") ? "lagoon" : "neutral"}>{c}</Chip>)}
              </div>
            </div>
            <div className="text-right">
              <div className="font-mono text-[16px]">{formatINR(r.price)}</div>
              <div className="mt-1"><SupplierChip code={r.supplier} short /></div>
            </div>
          </motion.div>
        ))}
      </div>
    </div>
  );
}

export default function Ranking() {
  const [mode, setMode] = useState<Mode>("relevance");
  const { data } = useFetch<any>("/ranking?persona=riya&mode=relevance");
  useHotkeys({ "1": () => setMode("relevance"), "2": () => setMode("business"), "3": () => setMode("risk") });
  return (
    <div className="h-full flex flex-col">
      <SceneHeader headline="Same search. Two agents. Two different right answers." subline="Dubai, 2 adults. A learned ranker per agent profile, then business objectives layered on with a guardrail."
        right={<Toggle value={mode} onChange={setMode} options={[{ value: "relevance", label: "Relevance only" }, { value: "business", label: "+ Margin & Platinum" }, { value: "risk", label: "+ Reliability risk" }]} />} />
      <div className="grid grid-cols-2 gap-8 flex-1 min-h-0">
        <Column persona="riya" mode={mode} />
        <Column persona="mark" mode={mode} />
      </div>
      {data?.proof && (
        <div className="absolute right-16 bottom-10 bg-surface/90 border border-line rounded-xl px-4 py-2 text-[13px] text-ink-2">
          Position-bias correction · NDCG@10 vs true relevance: naive <span className="font-mono text-ink">{data.proof.ndcg_naive.toFixed(3)}</span> → IPW <span className="font-mono text-lagoon">{data.proof.ndcg_ipw.toFixed(3)}</span>
          <span className="text-ink-3"> · η̂ = {data.proof.eta.toFixed(2)} from {data.proof.n_randomized} randomized sessions · </span><Cite>Unbiased LTR (Joachims et al., WSDM 2017) · simulated logs</Cite>
        </div>
      )}
    </div>
  );
}
