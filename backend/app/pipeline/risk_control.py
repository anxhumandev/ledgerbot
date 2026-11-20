"""Learn-then-Test risk control (Angelopoulos et al., 2021) with fixed-sequence testing.

Unit of risk: a *property pair*. Record pairs are not independent: one wrong merge of two hotels shows
up as up to 16 wrong record pairs (4 suppliers x 4 suppliers), and data are split by canonical hotel.
So we aggregate record pairs into blocks (hotel A, hotel B) and certify, with probability >= 1 - delta,

    false-merge rate = (# auto-merged property pairs that are different hotels) / (# auto-merged property pairs) <= alpha

A block is auto-merged when its strongest record pair clears the threshold (that single edge merges the
clusters). Thresholds are on the raw matcher score, which never saw the calibration data; isotonic
probabilities are only used for display.
"""
from __future__ import annotations

import numpy as np
from scipy.stats import beta as beta_dist

from app import config


def clopper_pearson_upper(k: int, n: int, conf: float) -> float:
    if n == 0 or k >= n:
        return 1.0
    return float(beta_dist.ppf(conf, k + 1, n - k))


def n_min(rate: float, delta: float) -> int:
    """Smallest set size that could ever be certified (zero errors) at this rate. Label-free."""
    return int(np.ceil(np.log(delta) / np.log1p(-rate)))


def to_blocks(scores: np.ndarray, y: np.ndarray, blocks: np.ndarray | None, how: str = "max"):
    if blocks is None or len(scores) == 0:
        return scores, y
    order = np.argsort(blocks, kind="stable")
    b, s, yy = blocks[order], scores[order], y[order]
    starts = np.r_[0, np.flatnonzero(b[1:] != b[:-1]) + 1]
    agg = np.maximum.reduceat(s, starts) if how == "max" else np.minimum.reduceat(s, starts)
    return agg, yy[starts]


def ltt_accept(scores, y, alpha, delta=config.RISK_DELTA, blocks=None) -> dict:
    """Smallest threshold whose auto-merge set has a certified false-merge rate <= alpha.

    Thresholds whose accept set is smaller than n_min(alpha) cannot be certified whatever the labels
    say, so the fixed sequence starts after them (a burn-in that depends on scores only, not labels).
    """
    s_b, y_b = to_blocks(np.asarray(scores), np.asarray(y), blocks, "max")
    order = np.argsort(-s_b, kind="stable")
    s, yy = s_b[order], y_b[order]
    neg_vals, counts = np.unique(-s, return_counts=True)
    lambdas, cum_n = -neg_vals, np.cumsum(counts)
    fp_cum = np.cumsum(1 - yy)
    tau, n_acc, k_acc, ucb_acc = np.inf, 0, 0, None
    nmin = n_min(alpha, delta)
    for lam, n in zip(lambdas, cum_n):
        if n < nmin:
            continue
        k = int(fp_cum[n - 1])
        ucb = clopper_pearson_upper(k, int(n), 1 - delta)
        if ucb <= alpha:
            tau, n_acc, k_acc, ucb_acc = float(lam), int(n), k, ucb
        else:
            break
    return {"tau": tau, "n_accepted": n_acc, "false_merges": k_acc, "ucb": ucb_acc, "n_units": int(len(s_b)),
            "n_min": nmin, "certifiable": bool(np.isfinite(tau))}


def ltt_reject(scores, y, beta, delta=config.RISK_DELTA) -> dict:
    """Largest threshold whose certified missed-match rate (true matches auto-rejected / all true matches)
    is <= beta. Risk is monotone in the threshold, so fixed-sequence testing runs low -> high."""
    scores, y = np.asarray(scores), np.asarray(y)
    pos = np.sort(scores[y == 1])
    n = len(pos)
    lambdas = np.unique(scores)
    tau, k_acc = -np.inf, 0
    for lam in lambdas:
        k = int(np.searchsorted(pos, lam, side="right"))
        if clopper_pearson_upper(k, n, 1 - delta) <= beta:
            tau, k_acc = float(lam), k
        else:
            break
    return {"tau": tau, "missed_matches": k_acc, "n_matches": n}


def bands(raw: np.ndarray, tau_accept: float, tau_reject: float) -> np.ndarray:
    """0 = auto-reject, 1 = uncertain, 2 = auto-merge."""
    out = np.ones(len(raw), dtype=np.int8)
    out[raw <= tau_reject] = 0
    out[raw >= tau_accept] = 2  # accept wins if bands overlap
    return out


def evaluate_on(raw, y, tau_accept, tau_reject, blocks=None) -> dict:
    raw, y = np.asarray(raw), np.asarray(y)
    acc = raw >= tau_accept
    rej = (raw <= tau_reject) & ~acc
    n = len(raw)
    s_b, y_b = to_blocks(raw, y, blocks, "max")
    acc_b = s_b >= tau_accept
    fm_b = int(((y_b == 0) & acc_b).sum())
    n_acc_b = int(acc_b.sum())
    fm = int(((y == 0) & acc).sum())
    return {
        "n": n, "auto_accept": int(acc.sum()), "auto_reject": int(rej.sum()), "uncertain": int(n - acc.sum() - rej.sum()),
        "automation": float((acc | rej).mean()) if n else 0.0,
        "empirical_fmr": (fm_b / n_acc_b) if n_acc_b else 0.0, "false_merges": fm_b, "merges": n_acc_b,
        "pair_fmr": (fm / acc.sum()) if acc.sum() else 0.0, "pair_false_merges": fm,
        "missed_matches": int(((y == 1) & rej).sum()),
    }


def risk_curve(cal_raw, cal_y, cal_blocks, test_raw, test_y, test_blocks, alphas=None, beta=config.DEFAULT_BETA,
               calibrate=None) -> list[dict]:
    alphas = alphas or config.RISK_ALPHA_GRID
    rej = ltt_reject(cal_raw, cal_y, beta)
    return [risk_row(a, cal_raw, cal_y, cal_blocks, test_raw, test_y, test_blocks, rej, calibrate) for a in alphas]


def risk_row(a, cal_raw, cal_y, cal_blocks, test_raw, test_y, test_blocks, rej, calibrate=None) -> dict:
    acc = ltt_accept(cal_raw, cal_y, a, blocks=cal_blocks)
    ev = evaluate_on(test_raw, test_y, acc["tau"], rej["tau"], test_blocks)

    def cal_p(t):
        return float(calibrate(np.array([t]))[0]) if (calibrate is not None and np.isfinite(t)) else None
    return {
        "alpha": a, "tau_accept_raw": acc["tau"], "tau_reject_raw": rej["tau"],
        "tau_accept": cal_p(acc["tau"]), "tau_reject": cal_p(rej["tau"]),
        "certifiable": acc["certifiable"], "n_min": acc["n_min"], "cal_units": acc["n_units"],
        "cal_n_accepted": acc["n_accepted"], "cal_false_merges": acc["false_merges"], "cal_ucb": acc["ucb"],
        "automation": ev["automation"], "auto_accept_rate": ev["auto_accept"] / max(1, ev["n"]),
        "review_rate": ev["uncertain"] / max(1, ev["n"]),
        "empirical_fmr": ev["empirical_fmr"], "test_false_merges": ev["false_merges"], "test_merges": ev["merges"],
        "pair_fmr": ev["pair_fmr"], "test_n": ev["n"],
        "held": ev["empirical_fmr"] <= a if ev["merges"] and acc["certifiable"] else None,
    }
