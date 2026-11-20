"""Process-wide demo state: the built pipeline state plus live, resettable components."""
from __future__ import annotations

import copy
import threading
import time

import numpy as np

from app import config
from app.pipeline import ranking, risk_control
from app.pipeline import run as pipeline_run
from app.pipeline.cost import METER
from app.pipeline.matcher import Matcher
from app.pipeline.reliability import ReliabilityBook


class Demo:
    def __init__(self):
        self.lock = threading.RLock()
        self.ready = False
        self.error: str | None = None

    def load(self):
        t0 = time.time()
        self.state = pipeline_run.load()
        self.matcher = Matcher.load()
        self.ranking = ranking.load()
        self.reliability = ReliabilityBook()
        self.base_hotels = self.state["hotels"]
        self.base_record_cluster = self.state["record_cluster"]
        self.norm_by_id = {n["record_id"]: n for n in self.state["norms"]}
        self.rec_by_id = {r["record_id"]: r for r in self.state["recs"]}
        self.row = self.state["index"].by_id
        self.pair_index = {(self.state["norms"][i]["record_id"], self.state["norms"][j]["record_id"]): k
                           for k, (i, j) in enumerate(self.state["pairs"])}
        # dense alpha grid for the dial chart
        s = self.state
        self.rej = risk_control.ltt_reject(s["cal_raw"], s["cal_y"], config.DEFAULT_BETA)
        grid = np.unique(np.round(np.exp(np.linspace(np.log(0.001), np.log(0.05), 36)), 5))
        self.dense_curve = [self.risk_at(float(a)) for a in grid]
        self.reset(initial=True)
        self.ready = True
        print(f"Demo state loaded in {time.time() - t0:.1f}s")

    # ------------------------------------------------------------------ risk
    def risk_at(self, alpha: float) -> dict:
        s = self.state
        row = risk_control.risk_row(alpha, s["cal_raw"], s["cal_y"], s["cal_blocks"], s["test_raw"], s["test_y"],
                                    s["test_blocks"], self.rej, self.matcher.calibrate)
        rr = row["review_rate"]
        row["reviews_per_10k"] = rr * 10_000
        row["ops_cost_month_inr"] = config.PAIRS_PER_MONTH * rr * config.REVIEW_MINUTES_PER_PAIR / 60 * config.REVIEW_COST_INR_PER_HOUR
        row["cal_n"] = int(len(s["cal_y"]))
        row["cal_units_total"] = int(len(set(s["cal_blocks"].tolist())))
        row["delta"] = config.RISK_DELTA
        return row

    def set_alpha(self, alpha: float) -> dict:
        row = self.risk_at(alpha)
        with self.lock:
            self.alpha = alpha
            self.tau_accept_raw = row["tau_accept_raw"]
            self.tau_reject_raw = row["tau_reject_raw"]
            self.current_risk = row
        return row

    def band_of(self, raw: float) -> str:
        if raw >= self.tau_accept_raw:
            return "auto_merge"
        if raw <= self.tau_reject_raw:
            return "auto_reject"
        return "uncertain"

    # ------------------------------------------------------------------ reset
    def reset(self, initial: bool = False):
        with self.lock:
            self.state["hotels"] = copy.deepcopy(self.base_hotels)
            self.hotels = self.state["hotels"]
            self.record_cluster = dict(self.base_record_cluster)
            self.extra_nodes = []
            self.onboarding = {"status": "idle"}
            self.reliability.reset()
            self.sabotage = {}
            self.alpha = config.DEFAULT_ALPHA
            self.set_alpha(config.DEFAULT_ALPHA)
            METER.reset()
            self.hotel_table = ranking.hotel_table(self.state)
            self.reset_epoch = time.time()

    # ------------------------------------------------------------------ helpers
    def p_success(self, code: str) -> float:
        return self.reliability.p_success(code)


DEMO = Demo()
