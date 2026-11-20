"""Scene 08B: Judges vs Machine. Phones vote on curated pairs; Tessera and the cached baseline answer too."""
from __future__ import annotations

import random
import secrets
import threading
import time
from collections import Counter

import numpy as np

from app import config
from app.demo import DEMO
from app.eval import baseline_llm
from app.pipeline import risk_control
from app.pipeline.matcher import Matcher, fit_calibrator, train
from app.services import arena
from app.ws import HUB

ANSWERS = ("same", "different", "same_room_diff_offer")
COUNTDOWN_S = 10


def _hotel_card(rid):
    r = DEMO.rec_by_id[rid]
    return {"supplier": r["supplier"], "name": r["name"], "address": r.get("address"), "phone": r.get("phone"),
            "stars": r.get("stars"), "coords": f"{r['lat']:.4f}, {r['lng']:.4f}"}


def curate() -> list[dict]:
    sets = arena.build_sets()
    t = arena._truth()
    st = DEMO.state
    rng = random.Random(config.SEED + 8)
    pairs = []
    # 1. famous sister properties
    sc = st["showcase"]
    A = [m for m in DEMO.base_hotels[sc["Atlantis The Palm"]]["members"] if DEMO.rec_by_id[m]["supplier"] == "S5"] or DEMO.base_hotels[sc["Atlantis The Palm"]]["members"]
    B = [m for m in DEMO.base_hotels[sc["Atlantis The Royal"]]["members"] if DEMO.rec_by_id[m]["supplier"] == "S2"] or DEMO.base_hotels[sc["Atlantis The Royal"]]["members"]
    pairs.append(("hotel", A[0], B[0]))
    # 2-4. pairs Tessera is unsure about (uncertain band)
    rid = [n["record_id"] for n in st["norms"]]
    def train_pair(k):
        i, j = st["pairs"][k]
        return all(t["splits"].get(t["hotel_of_record"][rid[n]]) == "train" for n in (i, j))
    unc = [k for k in np.where(st["band"] == 1)[0] if train_pair(k)]
    if len(unc) < 3:
        nearest = sorted(range(len(st["pairs"])), key=lambda k: abs(st["p"][k] - 0.5))
        for k in nearest:
            if len(unc) >= 3:
                break
            if k not in unc and train_pair(k):
                unc.append(k)
    rng.shuffle(unc)
    for k in unc[:3]:
        i, j = st["pairs"][k]
        pairs.append(("hotel", rid[i], rid[j]))
    # 5. noisy true match Tessera merged automatically
    pos = [x for x in sets["hotel"] if x["label"] == 1 and {x["a"]["supplier"], x["b"]["supplier"]} & {"S5", "S2"}]
    pos.sort(key=lambda x: x["pair_id"])
    if pos:
        pairs.append(("hotel", pos[0]["a"]["record_id"], pos[0]["b"]["record_id"]))
    # 6. hard negative from the test set
    hn = [x for x in sets["hotel"] if x["kind"] == "hard_negative"]
    if hn:
        pairs.append(("hotel", hn[0]["a"]["record_id"], hn[0]["b"]["record_id"]))
    # 7-8. room-offer corner cases
    for kind in ("same_room_diff_offer", "same_offer"):
        r = next((x for x in sets["room"] if x["kind"] == kind and x["a"]["supplier"] != x["b"]["supplier"]
                  and {x["a"]["supplier"], x["b"]["supplier"]} & {"S2", "S3"}), None)
        if r:
            pairs.append(("room", r["a"], r["b"]))
    out = []
    base = baseline_llm.load_results() or {}
    bh = {x["pair_id"]: x for x in base.get("hotel", [])}
    br = {x["pair_id"]: x for x in base.get("room", [])}
    for n, (kind, a, b) in enumerate(pairs[:8]):
        if kind == "hotel":
            truth = "same" if t["hotel_of_record"][a] == t["hotel_of_record"][b] else "different"
            t0 = time.perf_counter()
            td = arena.tessera_hotel_decision(a, b)
            ms = (time.perf_counter() - t0) * 1000 + arena.tessera_latency()["p50"]
            bl = bh.get(f"{a}|{b}") or bh.get(f"{b}|{a}")
            out.append({"idx": n, "kind": "hotel", "a": _hotel_card(a), "b": _hotel_card(b), "truth": truth,
                        "tessera": {**td, "ms": round(ms, 2)}, "_ids": [a, b],
                        "baseline": {"answer": "same" if bl["same"] else "different", "confidence": bl["confidence"],
                                     "latency_s": bl["latency_s"]} if bl else None})
        else:
            ta, tb = t["offer_terms"][a["offer_id"]], t["offer_terms"][b["offer_id"]]
            same_room = t["room_of_offer"][a["offer_id"]] == t["room_of_offer"][b["offer_id"]]
            truth = "same" if same_room and (ta["board"], ta["refundable"]) == (tb["board"], tb["refundable"]) else \
                ("same_room_diff_offer" if same_room else "different")
            td = arena.tessera_room_decision(a["offer_id"], b["offer_id"])
            ans = "same_room_diff_offer" if td.get("detail") == "same room, different offer" else td["answer"]
            bl = br.get(f"{a['offer_id']}|{b['offer_id']}")
            card = lambda o: {"supplier": o["supplier"], "name": o["room_name"], "address": o["board_raw"],
                              "phone": o["cancellation_raw"], "stars": None, "coords": f"₹{o['price_inr']:,}/night"}
            out.append({"idx": n, "kind": "room", "a": card(a), "b": card(b), "truth": truth,
                        "tessera": {"answer": ans, "p": None, "route": "auto", "ms": round(arena.tessera_latency()["p50"], 2)},
                        "baseline": {"answer": "same" if bl["same"] else "different", "confidence": bl["confidence"]} if bl else None})
    return out


class VoteSession:
    def __init__(self):
        self.learn_lock = threading.Lock()
        self.reset()

    def reset(self):
        self.session = secrets.token_hex(3)
        self.pairs = []
        self.current = -1
        self.votes: dict[int, dict[str, dict]] = {}
        self.opened_at = 0.0
        self.revealed = set()
        self.learned = None
        self.learned_labels = ()
        self.last_reveal = None

    def ensure(self):
        if not self.pairs:
            self.pairs = curate()

    def public_pair(self, i: int) -> dict:
        p = self.pairs[i]
        return {"session": self.session, "idx": i, "kind": p["kind"], "a": p["a"], "b": p["b"], "countdown": COUNTDOWN_S, "opened_at": self.opened_at,
                "total": len(self.pairs)}

    async def next(self) -> dict:
        self.ensure()
        if self.current + 1 >= len(self.pairs):
            return {"status": "finished"}
        self.current += 1
        self.last_reveal = None
        self.opened_at = time.time()
        self.votes.setdefault(self.current, {})
        payload = self.public_pair(self.current)
        await HUB.broadcast("vote", "pair", payload)
        return payload

    async def cast(self, nickname: str, idx: int, answer: str) -> dict:
        nick = nickname.strip()[:24]
        if not nick or idx < 0 or idx != self.current or answer not in ANSWERS:
            return {"ok": False, "reason": "invalid vote"}
        previous = self.votes.get(idx, {}).get(nick)
        if previous:
            return {"ok": True, "answer": previous["answer"]}
        ms = (time.time() - self.opened_at) * 1000
        if idx in self.revealed or ms >= COUNTDOWN_S * 1000:
            return {"ok": False, "reason": "voting closed"}
        self.votes[idx][nick] = {"answer": answer, "ms": ms}
        await HUB.broadcast("vote", "tally", self.tally(idx))
        return {"ok": True, "answer": answer}

    def tally(self, idx: int) -> dict:
        v = self.votes.get(idx, {})
        c = Counter(x["answer"] for x in v.values())
        return {"session": self.session, "idx": idx, "counts": {a: c.get(a, 0) for a in ANSWERS}, "n": len(v)}

    async def reveal(self) -> dict:
        i = self.current
        if i < 0:
            return {}
        self.revealed.add(i)
        p = self.pairs[i]
        v = self.votes.get(i, {})
        human_ms = float(np.mean([x["ms"] for x in v.values()])) if v else None
        payload = {"session": self.session, "idx": i, "truth": p["truth"], "tessera": p["tessera"], "baseline": p["baseline"],
                   "tally": self.tally(i), "human_avg_ms": human_ms, "leaderboard": self.leaderboard()}
        self.last_reveal = payload
        await HUB.broadcast("vote", "reveal", payload)
        return payload

    def leaderboard(self) -> list[dict]:
        scores = Counter()
        for i in self.revealed:
            truth = self.pairs[i]["truth"]
            for nick, x in self.votes.get(i, {}).items():
                scores[nick] += x["answer"] == truth
        rows = [{"name": k, "kind": "human", "score": v} for k, v in scores.items()]
        rows.append({"name": "Tessera", "kind": "tessera", "score": sum(self.pairs[i]["tessera"]["answer"] == self.pairs[i]["truth"] for i in self.revealed)})
        if any(self.pairs[i]["baseline"] for i in self.revealed):
            rows.append({"name": "LLM-only", "kind": "llm", "score": sum((self.pairs[i]["baseline"] or {}).get("answer") == ("different" if self.pairs[i]["truth"] == "same_room_diff_offer" else self.pairs[i]["truth"]) for i in self.revealed)})
        rows.sort(key=lambda r: -r["score"])
        return rows

    def twist(self) -> dict:
        disagreed = []
        for i in self.revealed:
            v = self.votes.get(i, {})
            if len(v) < 2:
                continue
            top = Counter(x["answer"] for x in v.values()).most_common(1)[0][1]
            if top / len(v) < 0.67:
                disagreed.append(i)
        abst = [i for i in disagreed if self.pairs[i]["tessera"]["answer"] == "abstain"]
        return {"disagreed": len(disagreed), "tessera_abstained": len(abst), "pairs": disagreed}

    def state(self, nickname: str = "") -> dict:
        self.ensure()
        return {"session": self.session, "current": self.current, "total": len(self.pairs),
                "pair": self.public_pair(self.current) if self.current >= 0 else None,
                "reveal": self.last_reveal, "answer": self.votes.get(self.current, {}).get(nickname.strip()[:24], {}).get("answer"),
                "revealed": self.current in self.revealed, "tally": self.tally(self.current) if self.current >= 0 else None,
                "leaderboard": self.leaderboard(), "twist": self.twist(), "learned": self.learned}

    def learn(self) -> dict:
        """Append majority votes as labels, retrain the matcher, recompute LTT and the review band."""
        with self.learn_lock:
            return self._learn()

    def _learn(self):
        started = time.perf_counter()
        session = self.session
        st = DEMO.base_state
        truth = arena._truth()
        split = {rid: truth["splits"].get(h) for rid, h in truth["hotel_of_record"].items()}
        labels = {}
        for i in sorted(self.revealed):
            p = self.pairs[i]
            if p["kind"] != "hotel" or not self.votes.get(i):
                continue
            a, b = p["_ids"]
            # Keep the calibration and evaluation properties held out.
            if split[a] != "train" or split[b] != "train":
                continue
            answers = [v["answer"] for v in self.votes[i].values()]
            answer, count = Counter(answers).most_common(1)[0]
            if count > len(answers) / 2 and answer in ("same", "different"):
                k = DEMO.pair_index.get((a, b), DEMO.pair_index.get((b, a)))
                if k is not None:
                    labels[k] = int(answer == "same")
        signature = tuple(sorted(labels.items()))
        if signature == self.learned_labels and self.learned is not None:
            return self.learned
        old = DEMO.state["raw"]
        before = int((risk_control.bands(old, DEMO.tau_accept_raw, DEMO.tau_reject_raw) == 1).sum())
        n = len(old)
        result = {"labels_added": len(labels), "review_before": before, "review_after": before,
                  "review_before_pct": before / n, "review_after_pct": before / n, "seconds": 0}
        if not labels:
            return {**result, "reason": "No training-split hotel pairs with a majority vote yet."}
        X = np.vstack((st["train_X"], st["X"][list(labels)]))
        y = np.r_[st["train_y"], list(labels.values())]
        w = np.r_[st["train_w"], np.full(len(labels), 3.0)]
        booster = train(X, y, w)
        cal_raw = booster.predict(st["cal_X"])
        matcher = Matcher(booster, fit_calibrator(cal_raw, st["cal_y"]))
        raw, probabilities = matcher.predict(st["X"])
        test_rows = [i for i, (a, b) in enumerate(st["pairs"])
                     if split[st["norms"][a]["record_id"]] == split[st["norms"][b]["record_id"]] == "test"]
        test_raw = raw[test_rows]
        reject = risk_control.ltt_reject(cal_raw, st["cal_y"], config.DEFAULT_BETA)
        def curve(alphas):
            return risk_control.risk_curve(cal_raw, st["cal_y"], st["cal_blocks"], test_raw, st["test_y"],
                                           st["test_blocks"], alphas, calibrate=matcher.calibrate)
        grid = curve(config.RISK_ALPHA_GRID)
        dense = curve([r["alpha"] for r in DEMO.base_curve])
        with DEMO.lock:
            if self.session != session:
                return {**result, "reason": "Voting session reset during training."}
            DEMO.matcher = matcher
            DEMO.state = {**DEMO.state, "raw": raw, "p": probabilities, "cal_raw": cal_raw, "test_raw": test_raw,
                          "risk": {**st["risk"], "curve": grid}}
            DEMO.rej = reject
            DEMO.dense_curve = dense
            current = DEMO.set_alpha(DEMO.alpha)
            DEMO.state["band"] = risk_control.bands(raw, current["tau_accept_raw"], current["tau_reject_raw"])
            after = int((DEMO.state["band"] == 1).sum())
            self.learned_labels = signature
            self.learned = {**result, "review_after": after, "review_after_pct": after / n,
                            "seconds": round(time.perf_counter() - started, 2)}
            return self.learned


VOTE = VoteSession()
