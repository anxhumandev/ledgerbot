"""Evaluation metrics: pairwise P/R/F1, B-cubed, blocking recall/reduction, latency percentiles."""
from __future__ import annotations

from collections import defaultdict
from itertools import combinations

import numpy as np


def prf(tp: int, fp: int, fn: int) -> dict:
    p = tp / (tp + fp) if tp + fp else 1.0
    r = tp / (tp + fn) if tp + fn else 1.0
    f = 2 * p * r / (p + r) if p + r else 0.0
    return {"precision": p, "recall": r, "f1": f, "tp": tp, "fp": fp, "fn": fn}


def pairs_of(groups) -> set[tuple[str, str]]:
    out = set()
    for g in groups:
        for a, b in combinations(sorted(g), 2):
            out.add((a, b))
    return out


def pairwise_cluster_prf(pred_groups, true_label: dict[str, str]) -> dict:
    """Pairwise P/R/F1 of predicted clusters vs truth, restricted to records in true_label."""
    pred = [set(m for m in g if m in true_label) for g in pred_groups]
    pred_pairs = pairs_of([g for g in pred if len(g) > 1])
    tg = defaultdict(set)
    for r, h in true_label.items():
        tg[h].add(r)
    true_pairs = pairs_of([g for g in tg.values() if len(g) > 1])
    tp = len(pred_pairs & true_pairs)
    return prf(tp, len(pred_pairs) - tp, len(true_pairs) - tp)


def bcubed(pred_groups, true_label: dict[str, str]) -> dict:
    pc = {}
    for gi, g in enumerate(pred_groups):
        for m in g:
            if m in true_label:
                pc[m] = gi
    tg, pg = defaultdict(set), defaultdict(set)
    for m, h in true_label.items():
        tg[h].add(m)
        if m in pc:
            pg[pc[m]].add(m)
    ps, rs = [], []
    for m, h in true_label.items():
        if m not in pc:
            continue
        P = pg[pc[m]]
        T = tg[h]
        inter = len(P & T)
        ps.append(inter / len(P))
        rs.append(inter / len(T))
    p = float(np.mean(ps)) if ps else 0.0
    r = float(np.mean(rs)) if rs else 0.0
    return {"precision": p, "recall": r, "f1": 2 * p * r / (p + r) if p + r else 0.0}


def decision_prf(pred: list[bool], truth: list[int]) -> dict:
    tp = sum(1 for p, t in zip(pred, truth) if p and t)
    fp = sum(1 for p, t in zip(pred, truth) if p and not t)
    fn = sum(1 for p, t in zip(pred, truth) if (not p) and t)
    return prf(tp, fp, fn)


def blocking_stats(cand_pairs: set[tuple[str, str]], true_pairs: set[tuple[str, str]], n_records: int,
                   n_same_supplier_pairs: int = 0) -> dict:
    total = n_records * (n_records - 1) // 2 - n_same_supplier_pairs
    hit = len(cand_pairs & true_pairs)
    return {"candidate_pairs": len(cand_pairs), "true_pairs": len(true_pairs),
            "recall": hit / len(true_pairs) if true_pairs else 1.0,
            "reduction_ratio": 1 - len(cand_pairs) / total if total else 0.0, "all_pairs": total}


def percentiles(xs, ps=(50, 95)) -> dict:
    if not len(xs):
        return {f"p{p}": None for p in ps}
    a = np.asarray(xs, dtype=float)
    return {f"p{p}": float(np.percentile(a, p)) for p in ps}
