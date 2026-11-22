import { ChevronDown, ChevronRight, Sparkles } from "lucide-react";
import { useState } from "react";
import { BOARD, dateTime, duration, inr, pct } from "../lib/fmt";
import { Badge, cx, Empty, Notice, StatusBadge, SupplierChip } from "../ui/core";

function Reasons({ reasons }: { reasons: string[] }) {
  if (!reasons?.length) return null;
  return (
    <ul className="mt-1.5 flex flex-wrap gap-1.5">
      {reasons.map((r) => <li key={r} className="rounded-full bg-accent-soft px-2 py-0.5 text-[12px] font-medium text-accent-ink">{r}</li>)}
    </ul>
  );
}

function Cancellation({ o }: { o: any }) {
  if (!o.refundable) return <span className="text-fg-2">Non-refundable</span>;
  return <span className="text-fg-2">Free until <b className="num text-fg">{o.cancel_hours ?? "?"} h</b> before</span>;
}

/** Every supplier offer for one property, grouped by physical room and comparable terms (board × refundability). */
export function HotelOffers({ data, compact }: { data: any; compact?: boolean }) {
  const [open, setOpen] = useState<Record<string, boolean>>({});
  if (!data.rates_loaded) return <Empty title="No rates for this property" body={data.note} />;
  if (!data.rooms.length) return <Empty title="No offers match these filters" body="Relax the meal plan, cancellation, payment or supplier filters." />;
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-[12px] text-fg-3">
        <span>{data.n_offers} supplier offers in {data.n_groups} comparable groups</span>
        <span>Prices for {data.nights} night{data.nights > 1 ? "s" : ""}, 2 adults, {data.currency}</span>
        <span>Quoted {dateTime(data.quoted_at)} · feeds carry quotes, not live availability or taxes</span>
        <span>Competitiveness cap {data.cap_pct}%</span>
        {data.paused_suppliers?.length > 0 && <span className="text-warn">Paused: {data.paused_suppliers.join(", ")}</span>}
      </div>
      {data.rooms.map((room: any) => (
        <div key={room.room_id} className="rounded-card border border-edge">
          <div className="flex flex-wrap items-center gap-2 border-b border-edge bg-panel-2 px-4 py-2.5">
            <span className="text-[14px] font-semibold text-fg">{room.name}</span>
            <Badge tone={room.tier === "Primary" ? "brand" : "warn"}>{room.tier} room match</Badge>
            <span className="text-[12px] text-fg-3">{room.suppliers.length} supplier{room.suppliers.length > 1 ? "s" : ""}</span>
            {!compact && <span className="ml-auto hidden truncate text-[12px] text-fg-3 lg:block" title={room.supplier_room_names.map((x: any) => `${x.supplier}: ${x.name}`).join("\n")}>
              Supplier names: {room.supplier_room_names.slice(0, 3).map((x: any) => x.name).join(" · ")}{room.supplier_room_names.length > 3 ? " …" : ""}</span>}
          </div>
          <div className="divide-y divide-edge">
            {room.groups.map((g: any) => {
              const key = `${room.room_id}|${g.label}`;
              const rec = g.recommended;
              const isOpen = open[key] ?? !compact;
              return (
                <div key={key} className="px-4 py-3">
                  <div className="flex flex-wrap items-start gap-3">
                    <button onClick={() => setOpen({ ...open, [key]: !isOpen })} aria-expanded={isOpen}
                      className="mt-0.5 flex items-center gap-1.5 text-[13px] font-semibold text-fg hover:text-brand-ink">
                      {isOpen ? <ChevronDown size={15} /> : <ChevronRight size={15} />}
                      {g.board_label} · {g.refundable ? "Refundable" : "Non-refundable"}
                      <span className="font-normal text-fg-3">({g.offers.length} offer{g.offers.length > 1 ? "s" : ""})</span>
                    </button>
                    {rec ? (
                      <div className="ml-auto flex flex-wrap items-center gap-x-4 gap-y-1 text-[13px]">
                        <Badge tone="accent"><Sparkles size={11} />Recommended</Badge>
                        <SupplierChip code={rec.supplier} name={rec.supplier_name} />
                        <span className="num text-[15px] font-bold text-fg">{inr(rec.total)}</span>
                        <Cancellation o={rec} />
                        <span className="text-fg-3">{rec.payment === "pay_later" ? "Pay later" : "Prepay"}</span>
                      </div>
                    ) : <span className="ml-auto text-[12px] text-bad">No eligible offer</span>}
                  </div>
                  {rec && <div className="pl-6"><Reasons reasons={g.reasons} /></div>}
                  {g.terms_differ && isOpen && <p className="mt-1.5 pl-6 text-[12px] text-fg-3">Cancellation deadlines or payment terms differ between suppliers in this group; each row shows its own terms.</p>}
                  {isOpen && (
                    <div className="mt-2 overflow-x-auto pl-6 scroll-thin">
                      <table className="w-full min-w-[900px] text-[13px]">
                        <thead><tr className="border-b border-edge text-left text-[12px] text-fg-3">
                          <th className="py-1.5 pr-3 font-semibold">Supplier</th><th className="py-1.5 pr-3 font-semibold">Supplier rate text</th>
                          <th className="py-1.5 pr-3 font-semibold">Meal plan</th><th className="py-1.5 pr-3 font-semibold">Cancellation</th>
                          <th className="py-1.5 pr-3 font-semibold">Payment</th><th className="py-1.5 pr-3 text-right font-semibold">Total</th>
                          <th className="py-1.5 pr-3 text-right font-semibold">vs cheapest</th><th className="py-1.5 pr-3 text-right font-semibold">Reliability</th>
                          <th className="py-1.5 pr-3 text-right font-semibold">Exp. value</th><th className="py-1.5 font-semibold">Selection</th>
                        </tr></thead>
                        <tbody>
                          {g.offers.map((o: any) => (
                            <tr key={o.offer_id} className={cx("border-b border-edge last:border-0", o.status === "recommended" && "bg-accent-soft/40")}>
                              <td className="py-2 pr-3"><SupplierChip code={o.supplier} name={o.supplier_name} /></td>
                              <td className="max-w-[220px] truncate py-2 pr-3 font-mono text-[12px] text-fg-3" title={`${o.supplier_room_name} · ${o.board_raw ?? ""} · ${o.cancellation_raw ?? ""}`}>{o.rate_text}</td>
                              <td className="py-2 pr-3">{BOARD[o.board] ?? o.board}</td>
                              <td className="py-2 pr-3"><Cancellation o={o} /></td>
                              <td className="py-2 pr-3">{o.payment === "pay_later" ? "Pay later" : "Prepay"}</td>
                              <td className="num py-2 pr-3 text-right font-semibold text-fg">{inr(o.total)}</td>
                              <td className="num py-2 pr-3 text-right">{o.cheapest ? <Badge tone="ok">Cheapest</Badge> : `+${o.premium_pct.toFixed(1)}%`}</td>
                              <td className="num py-2 pr-3 text-right">{pct(o.reliability, 1)}</td>
                              <td className="num py-2 pr-3 text-right">{inr(o.expected_value)}</td>
                              <td className="py-2"><span title={o.ineligible_reason ?? undefined}><StatusBadge status={o.status} /></span>
                                {o.ineligible_reason && <div className="text-[11px] text-bad">{o.ineligible_reason}</div>}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      ))}
      <p className="text-[12px] text-fg-3">Expected value = P(book) × P(confirm at quoted price) × margin − (1 − P(confirm)) × failure cost. Reliability comes from supplier booking outcomes (synthetic history plus simulated bookings).</p>
    </div>
  );
}

/** Supplier units per experience option; options never mix inclusions, time slots or private/shared. */
export function ActivityOffers({ data }: { data: any }) {
  if (!data.options.length) return <Empty title="No supplier listings match" />;
  return (
    <div className="space-y-4">
      <Notice tone="neutral">{data.price_basis} Access tier: {data.access_tier ? `Level ${data.access_tier}` : "standard"}.</Notice>
      {data.options.map((o: any) => (
        <div key={o.label} className="rounded-card border border-edge">
          <div className="flex flex-wrap items-center gap-2 border-b border-edge bg-panel-2 px-4 py-2.5">
            <span className="text-[14px] font-semibold text-fg">Option · {o.label}</span>
            <Badge tone={o.private ? "brand" : "neutral"}>{o.private ? "Private" : "Shared"}</Badge>
            <Badge tone={o.transfer ? "ok" : "neutral"}>{o.transfer ? "Hotel transfer" : "No transfer"}</Badge>
            <Badge tone={o.meal ? "ok" : "neutral"}>{o.meal ? "Meal included" : "No meal"}</Badge>
            {o.language !== "EN" && <Badge tone="warn">{o.language} guide</Badge>}
            {o.duration_range && <span className="text-[12px] text-fg-3">{duration(o.duration_range[0])}{o.duration_range[1] !== o.duration_range[0] ? `–${duration(o.duration_range[1])}` : ""}</span>}
          </div>
          {o.recommended && (
            <div className="flex flex-wrap items-center gap-3 border-b border-edge px-4 py-2.5 text-[13px]">
              <Badge tone="accent"><Sparkles size={11} />Recommended</Badge>
              <SupplierChip code={o.recommended.supplier} name={o.recommended.supplier_name} />
              <span className="num text-[15px] font-bold text-fg">{inr(o.recommended.adult)}<span className="text-[12px] font-normal text-fg-3"> / adult</span></span>
              <Reasons reasons={o.reasons} />
            </div>
          )}
          <div className="overflow-x-auto scroll-thin">
            <table className="w-full min-w-[860px] text-[13px]">
              <thead><tr className="border-b border-edge text-left text-[12px] text-fg-3">
                <th className="px-4 py-1.5 font-semibold">Supplier</th><th className="py-1.5 pr-3 font-semibold">Listing title</th>
                <th className="py-1.5 pr-3 font-semibold">Duration</th><th className="py-1.5 pr-3 font-semibold">Inclusions</th>
                <th className="py-1.5 pr-3 font-semibold">Meeting point</th><th className="py-1.5 pr-3 text-right font-semibold">Adult</th>
                <th className="py-1.5 pr-3 text-right font-semibold">Child</th><th className="py-1.5 pr-3 font-semibold">Cancellation</th>
                <th className="py-1.5 pr-3 text-right font-semibold">Reliability</th><th className="py-1.5 pr-4 font-semibold">Selection</th>
              </tr></thead>
              <tbody>
                {o.units.map((u: any) => (
                  <tr key={u.listing_id} className={cx("border-b border-edge last:border-0", u.status === "recommended" && "bg-accent-soft/40")}>
                    <td className="px-4 py-2"><SupplierChip code={u.supplier} name={u.supplier_name} /></td>
                    <td className="max-w-[260px] truncate py-2 pr-3" title={u.title}>{u.title}</td>
                    <td className="py-2 pr-3"><span className="num">{u.duration}</span>{u.duration_min ? <span className="text-[11px] text-fg-3"> ({duration(u.duration_min)})</span> : null}</td>
                    <td className="max-w-[180px] truncate py-2 pr-3" title={u.inclusions ?? ""}>{u.inclusions ?? "—"}</td>
                    <td className="max-w-[160px] truncate py-2 pr-3" title={u.meeting_point ?? ""}>{u.meeting_point ?? "—"}</td>
                    <td className="num py-2 pr-3 text-right font-semibold text-fg">{inr(u.adult)}</td>
                    <td className="num py-2 pr-3 text-right">{u.child ? inr(u.child) : "—"}</td>
                    <td className="py-2 pr-3 text-fg-3">Not in feed</td>
                    <td className="num py-2 pr-3 text-right">{pct(u.reliability, 1)}</td>
                    <td className="py-2 pr-4"><StatusBadge status={u.status} />{u.ineligible_reason && <div className="text-[11px] text-bad">{u.ineligible_reason}</div>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ))}
    </div>
  );
}
