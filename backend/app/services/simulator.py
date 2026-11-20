"""Simulation (clearly labelled as such in the UI).

- Booking stream: ~15 bookings/s across showcase hotels. Each booking takes the currently selected offer and
  rolls confirm / price-jump / latency from the supplier's *hidden true* profile. Reliability posteriors
  move only because of these observed events, never because of the sabotage toggle directly.
- Sabotage changes a supplier's hidden profile.
- A/B replay: N simulated searches through `cheapest + raw shelf` vs `expected value + deduplicated` arms.
"""
from __future__ import annotations

import asyncio
import math
import random
import time
from collections import Counter

import numpy as np

from app import config
from app.demo import DEMO
from app.pipeline import offers as off
from app.pipeline.ranking import PERSONA, features_for
from app.ws import HUB

SLOT_DAILY_BOOKINGS = 2.0  # simulated demand per offer slot per day (for the "failures avoided" toast)


def true_profile(code: str) -> dict:
    base = dict(config.SUPPLIERS[code]["profile"])
    sab = DEMO.sabotage.get(code)
    if sab:
        sev = sab["severity"]
        if sab["mode"] == "price_jump":
            base["price_jump"] = max(base["price_jump"], sev)
        elif sab["mode"] == "timeouts":
            base["latency"] = base["latency"] * (1 + 6 * sev)
            base["confirm"] = base["confirm"] * (1 - sev / 2)
        elif sab["mode"] == "failures":
            base["confirm"] = 1 - sev
    return base


class Simulator:
    def __init__(self):
        self.task: asyncio.Task | None = None
        self.rng = random.Random(config.SEED)
        self.showcase: list[dict] = []
        self.baseline_winners: dict = {}
        self.last_toast = None

    # -------------------------------------------------------------- setup
    def prepare(self):
        self.rng = random.Random(config.SEED)
        self.last_toast = None
        slots = []
        for h in DEMO.hotels.values():
            if h["city"] != "dubai" or not h.get("rooms"):
                continue
            for gi, g in enumerate(h["rooms"]):
                for s in g["slots"]:
                    if len(s["offers"]) >= 2:
                        slots.append((h["tessera_id"], gi, s))
        self.all_slots = slots
        self.stream_hotels = DEMO.hotels.copy()
        self.baseline_winners = {(t, gi, s["board"], s["refundable"]): off.select(s["offers"], DEMO.p_success)["winner"]["supplier"]
                                 for t, gi, s in slots}
        # showcase cards: hotels whose headline slot is won by GlobalBeds at baseline (the sabotage target)
        cards = []
        for (t, gi, b, rf), w in self.baseline_winners.items():
            if w == "S2" and b == "BB" and rf:
                h = DEMO.hotels[t]
                g = h["rooms"][gi]
                if any(c["tessera_id"] == t for c in cards):
                    continue
                cards.append({"tessera_id": t, "group": gi, "board": b, "refundable": rf, "hotel": h["name"],
                              "room": g["name"], "hero": (h.get("photos") or {}).get("hero"), "stars": h["stars"],
                              "n_suppliers": len(g["suppliers"])})
        cards.sort(key=lambda c: (c["hero"] is None, -c["n_suppliers"], c["hotel"]))
        self.showcase = cards[:4]
        self.showcase_slots = {c["tessera_id"]: next(s for t, gi, s in slots if t == c["tessera_id"] and gi == c["group"] and s["board"] == c["board"] and s["refundable"] == c["refundable"]) for c in self.showcase}
        # stream hotels: showcase + a spread of other multi-supplier slots
        self.stream_slots = [x for x in slots if x[0] in {c["tessera_id"] for c in self.showcase}] + \
            [x for x in slots if len(x[2]["offers"]) >= 3][:400]

    def slot_of(self, card):
        return self.showcase_slots[card["tessera_id"]]

    def showcase_view(self) -> list[dict]:
        out = []
        for c in self.showcase:
            sel = off.select(self.slot_of(c)["offers"], DEMO.p_success)
            w = sel["winner"]
            out.append({**c, "supplier": w["supplier"], "price": w["price"], "why": sel["why"], "p_success": round(w["p_success"], 4),
                        "ev": round(w["ev"], 1), "n_offers": len(sel["ranked"])})
        return out

    # -------------------------------------------------------------- stream
    def running(self) -> bool:
        return self.task is not None and not self.task.done()

    async def start(self):
        if not self.running():
            if not self.showcase:
                self.prepare()
            self.task = asyncio.create_task(self._loop())
        return {"status": "running"}

    def stop(self):
        if self.task and not self.task.done():
            self.task.cancel()
        self.task = None

    async def _loop(self):
        try:
            await self._loop_inner()
        except asyncio.CancelledError:
            raise
        except Exception:
            import traceback
            traceback.print_exc()

    async def _loop_inner(self):
        period = 1.0 / config.BOOKINGS_PER_SEC
        last_sup, last_flip = 0.0, 0.0
        prev_cards = {c["tessera_id"]: c["supplier"] for c in self.showcase_view()}
        while True:
            t0 = time.time()
            ev = self.book_one()
            await HUB.broadcast("bookings", "booking", ev)
            now = time.time()
            if now - last_sup >= 0.25:
                last_sup = now
                with DEMO.reliability.lock:
                    for p in DEMO.reliability.post.values():
                        p.history.append((now, p.score))
                await HUB.broadcast("suppliers", "snapshot", DEMO.reliability.snapshot())
            if now - last_flip >= 1.0:
                last_flip = now
                cards = self.showcase_view()
                cur = {c["tessera_id"]: c["supplier"] for c in cards}
                if cur != prev_cards:
                    await HUB.broadcast("offers", "showcase", cards)
                    prev_cards = cur
                toast = self.switch_report()
                if toast and toast["switched"] and (self.last_toast is None or toast["switched"] != self.last_toast["switched"]):
                    self.last_toast = toast
                    await HUB.broadcast("offers", "switch", toast)
            await asyncio.sleep(max(0.0, period - (time.time() - t0)))

    def book_one(self) -> dict:
        tid, gi, slot = self.rng.choice(self.stream_slots[:4 * len(self.showcase)] if self.rng.random() < 0.35 and self.showcase
                                        else self.stream_slots)
        sel = off.select(slot["offers"], DEMO.p_success)
        w = sel["winner"]
        prof = true_profile(w["supplier"])
        confirmed = self.rng.random() < prof["confirm"]
        jump = confirmed and self.rng.random() < prof["price_jump"]
        latency = self.rng.lognormvariate(math.log(prof["latency"]), 0.3)
        timeout = latency > 12
        if timeout:
            confirmed = False
        with DEMO.reliability.lock:
            DEMO.reliability.get(w["supplier"]).observe(confirmed, jump, min(latency, 30))
        h = self.stream_hotels[tid]
        status = "confirmed" if confirmed and not jump else ("price_jump" if jump else ("timeout" if timeout else "failed"))
        return {"hotel": h["name"], "supplier": w["supplier"], "status": status, "latency": round(latency, 2),
                "jump_inr": int(w["price"] * self.rng.uniform(0.04, 0.12)) if jump else 0, "price": w["price"],
                "room": h["rooms"][gi]["name"]}

    def switch_report(self) -> dict | None:
        """Slots whose EV winner moved away from a sabotaged supplier vs baseline."""
        if not DEMO.sabotage:
            return None
        switched, avoided = Counter(), 0.0
        for t, gi, s in self.all_slots:
            key = (t, gi, s["board"], s["refundable"])
            base = self.baseline_winners.get(key)
            if base not in DEMO.sabotage:
                continue
            sel = off.select(s["offers"], DEMO.p_success)
            new = sel["winner"]["supplier"]
            if new != base:
                switched[base] += 1
                tp_old, tp_new = true_profile(base), true_profile(new)
                f_old = 1 - tp_old["confirm"] * (1 - tp_old["price_jump"])
                f_new = 1 - tp_new["confirm"] * (1 - tp_new["price_jump"])
                avoided += max(0.0, f_old - f_new) * SLOT_DAILY_BOOKINGS
        if not switched:
            return {"switched": 0}
        sup = switched.most_common(1)[0][0]
        return {"switched": int(sum(switched.values())), "from": sup, "from_name": config.SUPPLIERS[sup]["name"],
                "failures_avoided_per_day": round(avoided), "simulated": True}

    # -------------------------------------------------------------- sabotage
    def sabotage(self, supplier: str, mode: str, severity: float):
        DEMO.sabotage[supplier] = {"mode": mode, "severity": float(severity)}
        self.last_toast = None

    def heal(self):
        DEMO.sabotage = {}
        self.last_toast = None

    def reset(self):
        self.stop()
        self.prepare()


SIM = Simulator()


# ======================================================================== A/B replay
class Replay:
    def __init__(self):
        self.task: asyncio.Task | None = None

    def running(self):
        return self.task is not None and not self.task.done()

    async def start(self, n: int):
        if self.running():
            return {"status": "running"}
        self.task = asyncio.create_task(self._run(n))
        return {"status": "started", "n": n}

    def stop(self):
        if self.task and not self.task.done():
            self.task.cancel()

    def _build_arms(self):
        """Per persona, the first screen (10 options) of each arm and its choice model inputs."""
        table = DEMO.hotel_table
        res = DEMO.ranking
        rel_live = {c: DEMO.p_success(c) for c in config.SUPPLIERS}
        mapping_err_raw = DEMO.state["offer_eval"]["raw_rate"]
        mapping_err_tess = DEMO.state["offer_eval"]["tessera_rate"]
        arms = {}
        for pid, p in PERSONA.items():
            rows = list(table.values())
            X = features_for(p, rows, rel_live, res["popularity"])
            rel = res["models"]["ipw"].predict(X)
            relz = (rel - rel.mean()) / (rel.std() + 1e-9)
            util = {r["tid"]: float(z) for r, z in zip(rows, relz)}
            # Both arms show the same 10 most relevant hotels and the same headline offer slot per hotel.
            top = sorted(rows, key=lambda r: -util[r["tid"]])[:10]
            raw_screen, tess = [], []
            for r in top:
                h = DEMO.hotels[r["tid"]]
                g = max(h["rooms"], key=lambda g: len(g["suppliers"]))
                s_ = max(g["slots"], key=lambda s_: len(s_["offers"]))
                # raw shelf: every supplier's copy, cheapest first, duplicates crowd the first screen
                for o in sorted(s_["offers"], key=lambda o: o["price"]):
                    raw_screen.append((r["tid"], o, util[r["tid"]]))
                tess.append((r["tid"], off.select(s_["offers"], DEMO.p_success)["winner"], util[r["tid"]]))
            raw_screen = raw_screen[:10]
            dup = len(raw_screen) - len({t[0] for t in raw_screen})
            arms[pid] = {"raw": (raw_screen, dup, mapping_err_raw), "tessera": (tess, 0, mapping_err_tess)}
        return arms

    @staticmethod
    def _arm_probs(screen, dup):
        prices = np.array([o["price"] for _, o, _ in screen], dtype=float)
        # utility: hotel relevance, minus price relative to the same hotel's cheapest copy on screen
        tids = [t for t, _, _ in screen]
        hotel_min = {t: min(p for (tt, _, _), p in zip(screen, prices) if tt == t) for t in set(tids)}
        rel_price = np.array([p / hotel_min[t] for t, p in zip(tids, prices)])
        u = np.array([z for *_, z in screen]) * 1.1 - 6.0 * (rel_price - 1)
        # Two-stage (nested-logit style) choice. Stage 1, book at all: most B2B searches end without a booking
        # (look-to-book of a few %); a better screen helps only weakly (LAMBDA x inclusive value), and each
        # near-duplicate on the first screen adds a small choice-overload penalty. Stage 2: which option.
        iv = float(np.log(np.exp(u).sum()))
        p_book = 1.0 / (1.0 + np.exp(Replay.U0 - Replay.LAMBDA * iv + Replay.OVERLOAD * dup))
        within = np.exp(u) / np.exp(u).sum()
        return np.r_[1.0 - p_book, p_book * within]

    U0, LAMBDA, OVERLOAD = 3.9, 0.1, 0.015

    async def _run(self, n: int):
        rng = np.random.default_rng(config.SEED + 5)
        arms = await asyncio.to_thread(self._build_arms)
        pids = list(PERSONA)
        weights = np.array([0.24, 0.16, 0.18, 0.16, 0.14, 0.12])
        probs = {pid: {a: self._arm_probs(arms[pid][a][0], arms[pid][a][1]) for a in ("raw", "tessera")} for pid in pids}
        tot = {a: {"searches": 0, "bookings": 0, "gross_profit": 0.0, "failed": 0, "wrong_room": 0} for a in ("raw", "tessera")}
        ticks = 120
        per = max(1, n // ticks)
        done = 0
        await HUB.broadcast("replay", "start", {"n": n})
        while done < n:
            m = min(per, n - done)
            ps = rng.choice(len(pids), size=m, p=weights / weights.sum())
            for arm in ("raw", "tessera"):
                for pi in np.unique(ps):
                    k = int((ps == pi).sum())
                    pid = pids[pi]
                    screen, dup, err = arms[pid][arm]
                    pr = probs[pid][arm]
                    choice = rng.choice(len(pr), size=k, p=pr)
                    t = tot[arm]
                    t["searches"] += k
                    for c in choice[choice > 0]:
                        _, o, _ = screen[c - 1]
                        prof = true_profile(o["supplier"])
                        ok = rng.random() < prof["confirm"] * (1 - prof["price_jump"])
                        t["bookings"] += 1
                        if ok:
                            t["gross_profit"] += o["price"] * 3 * config.SUPPLIERS[o["supplier"]]["take_rate"]
                        else:
                            t["failed"] += 1
                        if rng.random() < err:
                            t["wrong_room"] += 1
            done += m
            await HUB.broadcast("replay", "tick", self._view(tot, done, n))
            await asyncio.sleep(0.1)
        final = self._view(tot, done, n)
        DEMO.last_replay = final
        await HUB.broadcast("replay", "done", final)

    @staticmethod
    def _view(tot, done, n):
        out = {"done": done, "n": n, "arms": {}}
        for a, t in tot.items():
            out["arms"][a] = {**t, "look_to_book": t["bookings"] / max(1, t["searches"]),
                              "gp_per_search": t["gross_profit"] / max(1, t["searches"])}
        r, s = out["arms"]["raw"]["gp_per_search"], out["arms"]["tessera"]["gp_per_search"]
        lift = (s - r) / r if r else 0.0
        out["lift_gp_per_search"] = lift
        out["annualized_inr_illustrative"] = lift * config.TBO_ANNUAL_HOTEL_GTV_INR * config.TBO_GROSS_MARGIN
        out["formula"] = "lift % × ₹31,500 Cr annual hotel GTV × 6% gross margin"
        return out


REPLAY = Replay()
