import { Caption, SceneHeader } from "../design/primitives";
import { num, pct } from "../lib/format";
import { useFetch } from "../lib/hooks";
import ReviewQueue from "./ReviewQueue";

/** Human-in-the-loop as a first-class step: how much is automatic, and how fast a person settles the rest. */
export default function Review() {
  const { data: m } = useFetch<any>("/metrics");
  const r = m?.routes;
  const total = r ? (r.auto_merge ?? 0) + (r.auto_reject ?? 0) + (r.review ?? 0) : 0;
  return (
    <div className="h-full flex flex-col">
      <SceneHeader
        headline="When it isn't sure, a person decides in seconds."
        subline="Only pairs inside the certified review band reach a human, most uncertain first, with the model's own evidence. Every decision becomes a training label."
        right={r && (
          <div className="flex items-center gap-8 pb-1">
            <div className="text-right">
              <div className="font-mono tabular text-[40px] leading-none text-lagoon">{pct(1 - (r.review ?? 0) / Math.max(1, total), 2)}</div>
              <Caption className="mt-1">of {num(total)} candidate pairs decided automatically</Caption>
            </div>
            <div className="text-right">
              <div className="font-mono tabular text-[40px] leading-none text-[color:var(--amber-ink)]">{num(r.review ?? 0)}</div>
              <Caption className="mt-1">pairs need a person <span className="normal-case tracking-normal font-medium">(at α = {pct(m.config.alpha, 1)})</span></Caption>
            </div>
          </div>
        )}
      />
      <div className="flex-1 min-h-0"><ReviewQueue /></div>
    </div>
  );
}
