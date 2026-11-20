"""Learn-then-Test, constrained clustering and offer-slot grouping."""
import random

import numpy as np

from app.pipeline import offers as off
from app.pipeline.cluster import cluster_records, consistency_report
from app.pipeline.risk_control import clopper_pearson_upper, ltt_accept, ltt_reject, n_min


# ------------------------------------------------------------------ Learn-then-Test
def test_clopper_pearson_known_values():
    # zero errors in n trials: upper bound = 1 - delta**(1/n)
    assert abs(clopper_pearson_upper(0, 100, 0.95) - (1 - 0.05 ** (1 / 100))) < 1e-9
    assert clopper_pearson_upper(5, 5, 0.95) == 1.0
    assert n_min(0.01, 0.05) == 299


def test_ltt_perfect_separation_accepts_everything_positive():
    # 1,000 positives scored above 0.9, 1,000 negatives below 0.1: every positive can be auto-merged
    rng = np.random.default_rng(0)
    s = np.r_[rng.uniform(0.9, 1.0, 1000), rng.uniform(0.0, 0.1, 1000)]
    y = np.r_[np.ones(1000), np.zeros(1000)]
    res = ltt_accept(s, y, alpha=0.01)
    assert res["certifiable"]
    # every positive is automated; LTT may spend part of the budget on a few negatives (max automation
    # within alpha) but the certified bound must still be <= alpha
    assert res["n_accepted"] >= 1000 and res["tau"] <= s[:1000].min() + 1e-12
    assert clopper_pearson_upper(res["false_merges"], res["n_accepted"], 0.95) <= 0.01


def test_ltt_stops_before_the_contaminated_region():
    # top 600 are clean positives; below them a 50/50 mix. alpha=1% must not certify into the mix.
    s = np.r_[np.linspace(0.99, 0.70, 600), np.linspace(0.69, 0.40, 400)]
    y = np.r_[np.ones(600), np.tile([1, 0], 200)]
    res = ltt_accept(s, y, alpha=0.01)
    assert res["certifiable"]
    assert res["tau"] >= 0.69 - 0.02  # at most a couple of mixed thresholds slip in
    ucb = clopper_pearson_upper(res["false_merges"], res["n_accepted"], 0.95)
    assert ucb <= 0.01


def test_ltt_refuses_when_calibration_is_too_small():
    # 100 clean examples can never certify 0.5% (needs >= 598 with zero errors)
    s = np.linspace(1, 0.5, 100)
    y = np.ones(100)
    res = ltt_accept(s, y, alpha=0.005)
    assert not res["certifiable"] and res["n_accepted"] == 0


def test_ltt_guarantee_holds_on_fresh_draws():
    """Certify on one draw, check the false-merge rate on many independent draws from the same model."""
    def draw(rng, n=6000):
        y = rng.random(n) < 0.3
        s = np.where(y, rng.beta(8, 1.5, n), rng.beta(1.5, 6, n))
        return s, y.astype(int)
    rng = np.random.default_rng(42)
    s, y = draw(rng)
    alpha = 0.02
    tau = ltt_accept(s, y, alpha)["tau"]
    rates = []
    for _ in range(40):
        s2, y2 = draw(rng)
        acc = s2 >= tau
        rates.append(((y2 == 0) & acc).sum() / max(1, acc.sum()))
    assert np.mean(rates) <= alpha


def test_ltt_reject_controls_missed_matches():
    rng = np.random.default_rng(1)
    s = np.r_[rng.uniform(0.3, 1.0, 2000), rng.uniform(0.0, 0.5, 4000)]
    y = np.r_[np.ones(2000), np.zeros(4000)]
    res = ltt_reject(s, y, beta=0.02)
    missed = ((y == 1) & (s <= res["tau"])).sum() / 2000
    assert missed <= 0.02


# ------------------------------------------------------------------ clustering
def test_supplier_exclusivity_is_never_violated():
    rng = random.Random(7)
    recs = {f"r{i}": f"S{rng.randint(1, 5)}" for i in range(400)}
    ids = list(recs)
    # dense random "same" edges, including many that would chain same-supplier records together
    edges = [(rng.choice(ids), rng.choice(ids), rng.random()) for _ in range(3000)]
    edges = [(a, b, w) for a, b, w in edges if a != b]
    C, stats = cluster_records(recs, edges, cannot_links=[])
    for g in C.groups():
        sups = [recs[m] for m in g]
        assert len(sups) == len(set(sups))
    assert stats["blocked"].get("supplier_exclusivity", 0) > 0
    assert consistency_report(C.groups(), recs, [])["supplier_exclusivity_violations"] == 0


def test_cannot_links_are_respected_transitively():
    recs = {"a": "S1", "b": "S2", "c": "S3"}
    # a~b and b~c are "same", but a!~c is an explicit "different": the weaker edge must not merge
    C, stats = cluster_records(recs, [("a", "b", 0.99), ("b", "c", 0.80)], cannot_links=[("a", "c")])
    groups = sorted(sorted(g) for g in C.groups())
    assert ["a", "b"] in groups and ["c"] in groups
    assert consistency_report(C.groups(), recs, [("a", "c")])["transitivity_violations"] == 0


# ------------------------------------------------------------------ offer slots
def _offer(oid, sup, board_raw, cancel_raw, price):
    return off.normalize_offer({"offer_id": oid, "supplier": sup, "record_id": "r", "supplier_room_id": "sr",
                                "room_name": "Deluxe King", "board_raw": board_raw, "cancellation_raw": cancel_raw,
                                "price_inr": price, "occupancy": 2, "nights": 1})


def test_bb_and_ro_never_share_a_slot():
    offers = [
        _offer("1", "S1", "Bed & Breakfast", "Free cancellation until 48h before check-in", 10000),
        _offer("2", "S2", "BB", "CXL 72H", 9600),
        _offer("3", "S3", "AD", "Cancelación gratuita hasta 48h antes", 9800),
        _offer("4", "S2", "RO", "NRF", 8500),
        _offer("5", "S5", "ROOM ONLY", "NON REF", 8300),
        _offer("6", "S1", "Room Only", "Free cancellation until 48h before check-in", 9100),
    ]
    slots = {}
    for o in offers:
        slots.setdefault(off.slot_key(0, o), []).append(o["offer_id"])
    assert sorted(slots[(0, "BB", True, 2, 1)]) == ["1", "2", "3"]       # three suppliers compete
    assert sorted(slots[(0, "RO", False, 2, 1)]) == ["4", "5"]
    assert slots[(0, "RO", True, 2, 1)] == ["6"]                        # refundability separates RO slots
    for key, members in slots.items():
        boards = {o["board"] for o in offers if o["offer_id"] in members}
        assert len(boards) == 1


def test_expected_value_can_prefer_a_reliable_supplier_over_the_cheapest():
    offers = [_offer("a", "S1", "BB", "CXL 48H", 10200), _offer("b", "S5", "BB", "CXL 48H", 10000)]
    p = {"S1": 0.99, "S5": 0.80}.get
    ev = off.select(offers, p, "expected_value")
    cheap = off.select(offers, p, "cheapest")
    assert cheap["winner"]["offer_id"] == "b"
    assert ev["winner"]["offer_id"] == "a"
    assert "more than cheapest" in ev["why"]
