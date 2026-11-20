"""Scene 08B: Judges vs Machine. Phones vote on curated pairs; Tessera and the cached baseline answer too."""
from __future__ import annotations

import random
import secrets
import time
from collections import Counter

import lightgbm as lgb
import numpy as np

from app import config
from app.demo import DEMO
from app.eval import baseline_llm
from app.pipeline import risk_control
from app.pipeline.features import FEATURES, pair_features
from app.pipeline.matcher import N_ROUNDS, PARAMS
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
    unc = [k for k in np.where(st["band"] == 1)[0]]
    rng.shuffle(unc)
    for k in unc[:3]:
        i, j = st["pairs"][k]
        pairs.append(("hotel", rid[i], rid[j]))
    # 5. noisy true match Tessera merged automatically
    pos = [x for x in sets["hotel"] if x["label"] == 1 and {x["a"]["supplier"], x["b"]["supplier"]} & {"S5", "S2"}]
    pos.sort(key=lambda x: x["pair_id"])
    if pos:
        pairs.append(("hotel", pos[3]["a"]["record_id"], pos[3]["b"]["record_id"]))
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
        self.reset()

    def reset(self):
        self.session = secrets.token_hex(3)
        self.pairs = []
        self.current = -1
        self.votes: dict[int, dict[str, dict]] = {}
        self.opened_at = 0.0
        self.revealed = set()
        self.learned = None

    def ensure(self):
        if not self.pairs:
            self.pairs = curate()

    def public_pair(self, i: int) -> dict:
        p = self.pairs[i]
        return {"idx": i, "kind": p["kind"], "a": p["a"], "b": p["b"], "countdown": COUNTDOWN_S, "opened_at": self.opened_at,
                "total": len(self.pairs)}

    async def next(self) -> dict:
        self.ensure()
        if self.current + 1 >= len(self.pairs):
            return {"status": "finished"}
        self.current += 1
        self.opened_at = time.time()
        self.votes.setdefault(self.current, {})
        payload = self.public_pair(self.current)
        await HUB.broadcast("vote", "pair", payload)
        return payload

    async def cast(self, nickname: str, idx: int, answer: str) -> dict:
        if answer not in ANSWERS or idx != self.current or idx in self.revealed:
            return {"ok": False}
        nick = (nickname or "anon").strip()[:24]
        ms = (time.time() - self.opened_at) * 1000
        if ms > (COUNTDOWN_S + 1.5) * 1000:
            return {"ok": False, "reason": "time"}
        self.votes[idx][nick] = {"answer": answer, "ms": ms}  # idempotent per (session, pair, nickname)
        await HUB.broadcast("vote", "tally", self.tally(idx))
        return {"ok": True}

    def tally(self, idx: int) -> dict:
        v = self.votes.get(idx, {})
        c = Counter(x["answer"] for x in v.values())
        return {"idx": idx, "counts": {a: c.get(a, 0) for a in ANSWERS}, "n": len(v)}

    async def reveal(self) -> dict:
        i = self.current
        if i < 0:
            return {}
        self.revealed.add(i)
        p = self.pairs[i]
        v = self.votes.get(i, {})
        human_ms = float(np.mean([x["ms"] for x in v.values()])) if v else None
        payload = {"idx": i, "truth": p["truth"], "tessera": p["tessera"], "baseline": p["baseline"],
                   "tally": self.tally(i), "human_avg_ms": human_ms, "leaderboard": self.leaderboard()}
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
            rows.append({"name": "LLM-only", "kind": "llm", "score": sum((self.pairs[i]["baseline"] or {}).get("answer") == self.pairs[i]["truth"] for i in self.revealed)})
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

    def state(self) -> dict:
        self.ensure()
        return {"session": self.session, "current": self.current, "total": len(self.pairs),
                "pair": self.public_pair(self.current) if self.current >= 0 else None,
                "revealed": self.current in self.revealed, "tally": self.tally(self.current) if self.current >= 0 else None,
                "leaderboard": self.leaderboard(), "twist": self.twist(), "learned": self.learned}

    def learn(self) -> dict:
        """Append majority votes as labels, retrain the matcher, recompute LTT and the review band."""
        t0 = time.time()
        st = DEMO.state
        new_X, new_y = [], []
        for i in self.revealed:
            p = self.pairs[i]
            if p["kind"] != "hotel" or not self.votes.get(i):
                continue
            maj = Counter(x["answer"] for x in self.votes[i].values()).most_common(1)[0][0]
            if maj not in ("same", "different"):
                continue
            a, b = p["_ids"]
            ia, ib = DEMO.row[a], DEMO.row[b]
            new_X.append(pair_features(DEMO.norm_by_id[a], DEMO.norm_by_id[b], float(st["emb"][ia] @ st["emb"][ib]),
                                       st["index"].hashes.get(a), st["index"].hashes.get(b)))
            new_y.append(1 if maj == "same" else 0)
        before = int((st["band"] == 1).sum())
        X = np.vstack([st["train_X"]] + ([np.array(new_X, dtype=np.float32)] * 5 if new_X else []))
        y = np.concatenate([st["train_y"]] + ([np.array(new_y)] * 5 if new_y else []))
        w = np.concatenate([st["train_w"]] + ([np.full(len(new_y), 3.0)] * 5 if new_y else []))
        b = lgb.train(PARAMS, lgb.Dataset(X, label=y, weight=w, feature_name=FEATURES), num_boost_round=N_ROUNDS)
        cal_raw = b.predict(st["cal_X"])
        acc = risk_control.ltt_accept(cal_raw, st["cal_y"], DEMO.alpha, blocks=st["cal_blocks"])
        rej = risk_control.ltt_reject(cal_raw, st["cal_y"], config.DEFAULT_BETA)
        raw_all = b.predict(st["X"])
        after = int(((raw_all < acc["tau"]) & (raw_all > rej["tau"])).sum())
        n = len(raw_all)
        self.learned = {"labels_added": len(new_y), "review_before": before, "review_after": after,
                        "review_before_pct": before / n, "review_after_pct": after / n, "seconds": round(time.time() - t0, 2)}
        return self.learned


VOTE = VoteSession()
