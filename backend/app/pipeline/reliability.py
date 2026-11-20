"""Supplier reliability: Beta posteriors per (supplier, city), updated live from booking outcomes."""
from __future__ import annotations

import math
import threading
from collections import deque

import pandas as pd
from scipy.stats import beta as beta_dist

from app import config

EFFECTIVE_N = 200.0


def latency_factor(p50: float) -> float:
    """1.0 at <= 2 s, decaying linearly to 0.9 at 6 s (floor 0.85)."""
    if p50 <= 2.0:
        return 1.0
    return max(0.85, 1.0 - 0.1 * (p50 - 2.0) / 4.0)


class SupplierPosterior:
    def __init__(self, code: str, confirm_rate: float, jump_rate: float, p50: float, n_eff: float = EFFECTIVE_N):
        self.code = code
        self.a_c, self.b_c = confirm_rate * n_eff + 1, (1 - confirm_rate) * n_eff + 1
        self.a_j, self.b_j = jump_rate * n_eff + 1, (1 - jump_rate) * n_eff + 1
        self.p50 = p50
        self.n_obs = 0
        self.history: deque = deque(maxlen=240)  # (ts, score) for sparklines
        self.recent: deque = deque(maxlen=200)
        self.init = (self.a_c, self.b_c, self.a_j, self.b_j, p50)

    def reset(self):
        self.a_c, self.b_c, self.a_j, self.b_j, self.p50 = self.init
        self.n_obs = 0
        self.history.clear()
        self.recent.clear()

    def observe(self, confirmed: bool, price_jump: bool, latency: float, forget: float = 0.997):
        # mild exponential forgetting keeps the posterior responsive to regime changes (sabotage)
        self.a_c, self.b_c = self.a_c * forget, self.b_c * forget
        self.a_j, self.b_j = self.a_j * forget, self.b_j * forget
        self.a_c += 1 if confirmed else 0
        self.b_c += 0 if confirmed else 1
        if confirmed:
            self.a_j += 1 if price_jump else 0
            self.b_j += 0 if price_jump else 1
        self.p50 = 0.95 * self.p50 + 0.05 * latency
        self.n_obs += 1
        self.recent.append((confirmed, price_jump, latency))

    @property
    def confirm(self) -> float:
        return self.a_c / (self.a_c + self.b_c)

    @property
    def jump(self) -> float:
        return self.a_j / (self.a_j + self.b_j)

    @property
    def p_success(self) -> float:
        """Probability a booking confirms at the quoted price."""
        return self.confirm * (1 - self.jump)

    @property
    def score(self) -> float:
        return self.confirm * (1 - self.jump) * latency_factor(self.p50)

    def interval(self, q=0.90) -> tuple[float, float]:
        """90% credible interval of the reliability score (confirm interval x point jump/latency)."""
        lo = beta_dist.ppf((1 - q) / 2, self.a_c, self.b_c)
        hi = beta_dist.ppf(1 - (1 - q) / 2, self.a_c, self.b_c)
        f = (1 - self.jump) * latency_factor(self.p50)
        return float(lo * f), float(hi * f)

    def snapshot(self) -> dict:
        lo, hi = self.interval()
        rc = list(self.recent)
        return {
            "code": self.code, "name": config.SUPPLIERS[self.code]["name"], "color": config.SUPPLIERS[self.code]["color"],
            "score": round(self.score, 4), "ci": [round(lo, 4), round(hi, 4)], "confirm": round(self.confirm, 4),
            "price_jump": round(self.jump, 4), "p50_latency": round(self.p50, 2), "n_obs": self.n_obs,
            "recent_confirm": round(sum(1 for c in rc if c[0]) / len(rc), 3) if rc else None,
            "spark": [round(s, 4) for _, s in list(self.history)[-120:]],
        }


class ReliabilityBook:
    def __init__(self):
        self.lock = threading.Lock()
        self.post: dict[str, SupplierPosterior] = {}
        self.load_priors()

    def load_priors(self):
        hist = pd.read_parquet(config.WORLD_DIR / "booking_history.parquet")
        for code in config.SUPPLIERS:
            h = hist[hist.supplier == code]
            if len(h):
                conf = float(h.confirmed.mean())
                jump = float(h[h.confirmed].price_jump.mean())
                p50 = float(h.latency_s.median())
                self.post[code] = SupplierPosterior(code, conf, jump, p50)
            else:  # new supplier: weak, generic prior
                self.post[code] = SupplierPosterior(code, 0.97, 0.03, 2.5, n_eff=20)

    def reset(self):
        with self.lock:
            for p in self.post.values():
                p.reset()

    def get(self, code: str) -> SupplierPosterior:
        return self.post[code]

    def p_success(self, code: str) -> float:
        return self.post[code].p_success

    def snapshot(self, codes=None) -> list[dict]:
        codes = codes or config.ACTIVE_SUPPLIERS
        return [self.post[c].snapshot() for c in codes]


def sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))
