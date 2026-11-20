"""Offer slots and expected-value offer selection.

Offers inside one physical room group merge into an *offer slot* only when
(board, refundable, occupancy, nights) are all equal. Inside a slot, suppliers compete:

    EV = P(book | price_rel, terms) x P(success | supplier) x margin - (1 - P(success)) x failure_cost
    P(book) = sigmoid(a - b*(price_rel - 1) + c*refundable + d*pay_later),  price_rel = price / slot min
    P(success) = posterior confirm rate x (1 - posterior price-jump rate)
    margin = price x take_rate(supplier)
"""
from __future__ import annotations

from app import config
from app.pipeline.normalize import BOARD_LABEL, parse_board, parse_cancellation, parse_room
from app.pipeline.reliability import sigmoid


def normalize_offer(o: dict) -> dict:
    board = parse_board(o.get("board_raw")) or parse_room(o.get("room_name", ""))["board"] or "RO"
    refundable, hours = parse_cancellation(o.get("cancellation_raw"))
    if refundable is None:
        refundable = bool(parse_room(o.get("room_name", "")).get("refundable"))
    return {
        "offer_id": o["offer_id"], "supplier": o["supplier"], "record_id": o["record_id"],
        "supplier_room_id": o["supplier_room_id"], "room_name": o["room_name"], "board": board,
        "refundable": bool(refundable), "cancel_hours": hours, "payment": o.get("payment", "prepay"),
        "price": int(o["price_inr"]), "occupancy": int(o.get("occupancy", 2)), "nights": int(o.get("nights", 1)),
        "board_raw": o.get("board_raw"), "cancellation_raw": o.get("cancellation_raw"), "rate_code": o.get("rate_code"),
    }


def slot_key(group_idx: int, o: dict) -> tuple:
    return (group_idx, o["board"], o["refundable"], o["occupancy"], o["nights"])


def slot_label(board: str, refundable: bool, hours: int | None = None) -> str:
    b = {"RO": "RO", "BB": "BB", "HB": "HB", "FB": "FB", "AI": "AI"}[board]
    if refundable:
        return f"{b} · Free cancel{f' {hours} h' if hours else ''}"
    return f"{b} · Non-refundable"


def p_book(price_rel: float, refundable: bool, pay_later: bool) -> float:
    k = config.PBOOK
    return sigmoid(k["a"] - k["b"] * (price_rel - 1.0) + k["c"] * refundable + k["d"] * pay_later)


def score_slot(offers: list[dict], p_success) -> list[dict]:
    """Annotate offers in one slot with EV terms. p_success: supplier -> probability."""
    if not offers:
        return []
    mn = min(o["price"] for o in offers)
    out = []
    for o in offers:
        rel = o["price"] / mn
        pb = p_book(rel, o["refundable"], o["payment"] == "pay_later")
        ps = p_success(o["supplier"])
        margin = o["price"] * config.SUPPLIERS[o["supplier"]]["take_rate"]
        ev = pb * ps * margin - (1 - ps) * config.FAILURE_COST_INR
        out.append({**o, "price_rel": rel, "p_book": pb, "p_success": ps, "margin": margin, "ev": ev})
    return out


def select(offers: list[dict], p_success, strategy: str = "expected_value") -> dict:
    scored = score_slot(offers, p_success)
    if not scored:
        return {}
    if strategy == "cheapest":
        ranked = sorted(scored, key=lambda o: (o["price"], o["supplier"]))
    else:
        ranked = sorted(scored, key=lambda o: (-o["ev"], o["price"]))
    win = ranked[0]
    cheapest = min(scored, key=lambda o: (o["price"], o["supplier"]))
    return {"winner": win, "ranked": ranked, "cheapest": cheapest, "why": why_chip(win, cheapest, ranked, strategy)}


def why_chip(win, cheapest, ranked, strategy) -> str:
    name = config.SUPPLIERS[win["supplier"]]["name"]
    if strategy == "cheapest":
        return f"Cheapest of {len(ranked)} offers"
    if len(ranked) == 1:
        return f"Only offer · {name} confirms {win['p_success'] * 100:.1f}%"
    if win["offer_id"] == cheapest["offer_id"]:
        runner = ranked[1]
        return f"Cheapest and +₹{max(0, win['ev'] - runner['ev']):,.0f} expected vs next"
    diff = win["price"] - cheapest["price"]
    gain = win["ev"] - cheapest["ev"]
    return (f"₹{diff:,} more than cheapest but {win['p_success'] * 100:.1f}% success "
            f"→ +₹{gain:,.0f} expected")


__all__ = ["normalize_offer", "slot_key", "slot_label", "select", "score_slot", "BOARD_LABEL"]
