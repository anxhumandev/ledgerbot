"""Offline build: normalize -> block -> features -> matcher -> calibration -> LTT -> decide -> cluster -> eval.

    python -m app.pipeline.run          # full build, prints a metrics report, writes cache/state.pkl
"""
from __future__ import annotations

import pickle
import hashlib
import random
import time
from collections import defaultdict

import numpy as np
import orjson
from sklearn.metrics import roc_auc_score

from app import config
from app.eval import metrics as M
from app.pipeline import adjudicator, blocking, cluster, normalize, risk_control
from app.pipeline.features import FEATURES, feature_matrix, mask_phone, pair_features
from app.pipeline.matcher import Matcher, fit_calibrator, train
from app.pipeline.cost import METER

STATE_PATH = config.CACHE_DIR / "state.pkl"


def load_json(name):
    return orjson.loads((config.WORLD_DIR / name).read_bytes())


def world_digest():
    """Identify every generated input used by the cached pipeline and live scenes."""
    digest = hashlib.sha256()
    for path in sorted(config.WORLD_DIR.iterdir()):
        if path.suffix in (".json", ".parquet"):
            digest.update(path.name.encode())
            digest.update(hashlib.sha256(path.read_bytes()).digest())
    return digest.hexdigest()


def log(msg, t0):
    print(f"[{time.time() - t0:6.1f}s] {msg}")


class Truth:
    """Thin accessor; only evaluation + the simulated human reviewer touch it."""

    def __init__(self):
        t = load_json("truth.json")
        self.hotel_of = t["hotel_of_record"]
        self.splits = t["splits"]
        self.raw = t

    def same(self, a, b) -> int:
        return int(self.hotel_of.get(a) is not None and self.hotel_of.get(a) == self.hotel_of.get(b))


def simulated_reviewer(truth: Truth, a: str, b: str, rng: random.Random, err=0.01) -> bool:
    y = bool(truth.same(a, b))
    return (not y) if rng.random() < err else y


def build(verbose: bool = True) -> dict:
    t0 = time.time()
    config.ensure_dirs()
    recs = load_json("hotels_raw.json")
    labels = load_json("labels_sample.json")
    truth = Truth()

    norms = [normalize.normalize_hotel(r) for r in recs]
    log(f"normalized {len(norms)} supplier hotel records", t0)
    emb_path = config.CACHE_DIR / "emb.npy"
    ids_path = config.CACHE_DIR / "emb_ids.json"
    embedding_inputs = hashlib.sha256(orjson.dumps([(n["record_id"], blocking.embed_text(n)) for n in norms])).hexdigest()
    if emb_path.exists() and ids_path.exists() and orjson.loads(ids_path.read_bytes()) == embedding_inputs:
        emb = np.load(emb_path)
    else:
        emb = blocking.embed(norms)
        np.save(emb_path, emb)
        ids_path.write_bytes(orjson.dumps(embedding_inputs))
    log("embeddings ready", t0)
    index = blocking.build_index(norms, emb)
    cross, same_sup = index.all_pairs()
    pairs = sorted(cross)
    log(f"blocking: {len(pairs)} cross-supplier candidate pairs, {len(same_sup)} same-supplier", t0)

    rid = [n["record_id"] for n in norms]
    X = feature_matrix(pairs, norms, emb, index.hashes)
    log(f"features: {X.shape}", t0)

    # ---------------------------------------------------------------- training data
    row = index.by_id
    train_lab = [l for l in labels if l["split"] == "train"]
    cal_lab = [l for l in labels if l["split"] == "cal"]

    def lab_features(lst):
        P = [(row[l["a"]], row[l["b"]]) for l in lst]
        return feature_matrix(P, norms, emb, index.hashes), np.array([l["label"] for l in lst])

    Xtr, ytr = lab_features(train_lab)
    train_records = {l["a"] for l in train_lab} | {l["b"] for l in train_lab}
    rng = random.Random(config.SEED)
    tsr_i, dist_i = FEATURES.index("tsr_name"), FEATURES.index("dist_m")
    pc_i = FEATURES.index("phone_conflict")
    in_train = [k for k, (i, j) in enumerate(pairs) if rid[i] in train_records and rid[j] in train_records]
    labelled = {(l["a"], l["b"]) for l in train_lab} | {(l["b"], l["a"]) for l in train_lab}
    # weak negatives (heuristic, not truth): both phones present and different -> different property.
    weak = [k for k in in_train if X[k, pc_i] == 1 and X[k, tsr_i] >= 0.45 and (rid[pairs[k][0]], rid[pairs[k][1]]) not in labelled]
    rng.shuffle(weak)
    weak = weak[:3000]
    easy = [k for k in in_train if X[k, tsr_i] < 0.5 and X[k, dist_i] > 800]
    rng.shuffle(easy)
    easy = easy[:1000]
    Xw = X[weak]
    Xall = np.vstack([Xtr, mask_phone(Xtr), Xw, mask_phone(Xw), X[easy]])
    yall = np.concatenate([ytr, ytr, np.zeros(2 * len(Xw) + len(easy))])
    wall = np.concatenate([np.full(len(ytr), 1.0), np.full(len(ytr), 0.7), np.full(2 * len(Xw), 0.5), np.full(len(easy), 0.5)])
    booster = train(Xall, yall, wall)

    # ---------------------------------------------------------------- calibration + LTT
    cand_set = {(rid[i], rid[j]) for i, j in pairs}
    cand_set |= {(b, a) for a, b in cand_set}
    cal_in = [l for l in cal_lab if (l["a"], l["b"]) in cand_set]
    Xc, yc = lab_features(cal_in)
    matcher = Matcher(booster, None)
    cal_raw = matcher.raw(Xc)
    matcher.calibrator = fit_calibrator(cal_raw, yc)
    matcher.save()
    raw = matcher.raw(X)
    p = matcher.calibrate(raw)

    # test split (held-out hotels; truth labels used for evaluation only)
    test_idx = [k for k, (i, j) in enumerate(pairs)
                if truth.splits.get(truth.hotel_of[rid[i]]) == "test" and truth.splits.get(truth.hotel_of[rid[j]]) == "test"]
    y_test = np.array([truth.same(rid[pairs[k][0]], rid[pairs[k][1]]) for k in test_idx])
    test_raw = raw[test_idx]
    auc = roc_auc_score(y_test, test_raw) if len(set(y_test)) > 1 else float("nan")
    # property blocks. Calibration: hotels = connected components of positive gold-audit labels (no truth access).
    comp = _components([(l["a"], l["b"]) for l in cal_lab if l["label"] == 1])
    cal_blocks = _block_ids([(comp.get(l["a"], l["a"]), comp.get(l["b"], l["b"])) for l in cal_in])
    test_blocks = _block_ids([(truth.hotel_of[rid[pairs[k][0]]], truth.hotel_of[rid[pairs[k][1]]]) for k in test_idx])
    curve = risk_control.risk_curve(cal_raw, yc, cal_blocks, test_raw, y_test, test_blocks, calibrate=matcher.calibrate)
    log(f"calibration n={len(yc)} pairs / {len(set(cal_blocks.tolist()))} property pairs ({int(yc.sum())} matches) · "
        f"test pairs n={len(y_test)} · AUC={auc:.4f}", t0)

    alpha = config.DEFAULT_ALPHA
    acc = risk_control.ltt_accept(cal_raw, yc, alpha, blocks=cal_blocks)
    rej = risk_control.ltt_reject(cal_raw, yc, config.DEFAULT_BETA)
    rej["tau"] = risk_control.effective_reject(acc["tau"], rej["tau"])
    band = risk_control.bands(raw, acc["tau"], rej["tau"])

    # ---------------------------------------------------------------- decisions
    route = np.array(["auto_reject", "uncertain", "auto_merge"], dtype=object)[band]
    uncertain_idx = [k for k in range(len(pairs)) if band[k] == 1]
    sub_i = FEATURES.index("subbrand_conflict")
    usage_before = dict(METER.session)
    llm = adjudicator.adjudicate([
        {"pair_id": f"{rid[pairs[k][0]]}|{rid[pairs[k][1]]}", "a": recs[pairs[k][0]], "b": recs[pairs[k][1]],
         "p": float(p[k]), "subbrand_conflict": bool(X[k, sub_i])} for k in uncertain_idx])
    adjudication_usage = {key: METER.session[key] - usage_before[key]
                          for key in ("inr", "calls", "input_tokens", "output_tokens")}
    rrng = random.Random(config.SEED + 99)
    final = np.zeros(len(pairs), dtype=np.int8)  # 1 same, 0 different
    final[band == 2] = 1
    reviewer = {}
    for k in uncertain_idx:
        key = f"{rid[pairs[k][0]]}|{rid[pairs[k][1]]}"
        v = llm.get(key)
        if v and v["route"] == "llm":
            route[k] = "llm"
            final[k] = 1 if v["verdict"] == "same" else 0
        else:
            route[k] = "review"
            ok = simulated_reviewer(truth, rid[pairs[k][0]], rid[pairs[k][1]], rrng)
            final[k] = int(ok)
            reviewer[key] = ok

    # ---------------------------------------------------------------- intra-supplier duplicates
    same_pairs = sorted(same_sup)
    Xs = feature_matrix(same_pairs, norms, emb, index.hashes) if same_pairs else np.zeros((0, len(FEATURES)))
    raw_s = matcher.raw(Xs)
    pe_i = FEATURES.index("phone_exact")
    dup_pairs = [(rid[i], rid[j]) for (i, j), s, x in zip(same_pairs, raw_s, Xs)
                 if s >= acc["tau"] and x[tsr_i] >= 0.8 and (x[pe_i] == 1 or x[dist_i] < 150)]
    alias = {}
    for a, b in dup_pairs:
        pa, pb = alias.get(a, a), alias.get(b, b)
        prim, sec = (pa, pb) if pa < pb else (pb, pa)
        if prim != sec:
            alias[sec] = prim
    for k in list(alias):
        while alias[k] in alias:
            alias[k] = alias[alias[k]]
    true_dups = {tuple(sorted(d)) for d in truth.raw["intra_dups"]}
    found_dups = {tuple(sorted(d)) for d in dup_pairs}
    dup_stats = M.prf(len(true_dups & found_dups), len(found_dups - true_dups), len(true_dups - found_dups))
    log(f"intra-supplier duplicates flagged: {len(found_dups)} (precision {dup_stats['precision']:.2f}, recall {dup_stats['recall']:.2f})", t0)

    # ---------------------------------------------------------------- clustering
    supplier_of = {r: norms[row[r]]["supplier"] for r in rid if r not in alias}
    same_edges, cannot = [], []
    for k, (i, j) in enumerate(pairs):
        a, b = alias.get(rid[i], rid[i]), alias.get(rid[j], rid[j])
        if a == b:
            continue
        if final[k] == 1:
            same_edges.append((a, b, float(p[k])))
        elif route[k] != "auto_reject" or X[k, sub_i] or raw[k] <= rej["tau"]:
            cannot.append((a, b))
    C, cstats = cluster.cluster_records(supplier_of, same_edges, cannot)
    groups = [set(g) for g in C.groups()]
    for sec, prim in alias.items():
        for g in groups:
            if prim in g:
                g.add(sec)
                break
    different = [(rid[i], rid[j]) for k, (i, j) in enumerate(pairs) if final[k] == 0]
    entity_groups = [{alias.get(m, m) for m in g} for g in groups]
    cons = cluster.consistency_report(entity_groups, supplier_of, [(alias.get(a, a), alias.get(b, b)) for a, b in different])
    log(f"clusters: {len(groups)} · blocked merges {cstats['blocked']} · pruned {cstats['pruned']} · violations {cons['total_violations']}", t0)

    # ---------------------------------------------------------------- evaluation
    true_label = {r: truth.hotel_of[r] for r in rid}
    test_label = {r: h for r, h in true_label.items() if truth.splits.get(h) == "test"}
    dubai_label = {r: h for r, h in true_label.items() if norms[row[r]]["city"] == "dubai"}
    true_pairs = set()
    byh = defaultdict(list)
    for r, h in true_label.items():
        byh[h].append(r)
    sup_of_all = {r: norms[row[r]]["supplier"] for r in rid}
    for h, rs in byh.items():
        for a in rs:
            for b in rs:
                if a < b and sup_of_all[a] != sup_of_all[b]:
                    true_pairs.add((a, b))
    cand_named = {tuple(sorted((rid[i], rid[j]))) for i, j in pairs}
    n_same_sup = sum(c * (c - 1) // 2 for c in [sum(1 for n in norms if n["supplier"] == s) for s in config.ACTIVE_SUPPLIERS])
    block = M.blocking_stats(cand_named, true_pairs, len(norms), n_same_sup)
    src_counts = defaultdict(int)
    for k, (i, j) in enumerate(pairs):
        for s in cross[(i, j)]:
            src_counts[s] += 1
    block["by_source"] = dict(src_counts)
    auto_groups = _auto_only_groups(rid, pairs, band, alias, supplier_of, p)
    evals = {
        "test_pairwise": M.pairwise_cluster_prf(groups, test_label),
        "test_bcubed": M.bcubed(groups, test_label),
        "dubai_pairwise": M.pairwise_cluster_prf(groups, dubai_label),
        "all_pairwise": M.pairwise_cluster_prf(groups, true_label),
        "test_pairwise_auto_only": M.pairwise_cluster_prf(auto_groups, test_label),
        "auc_test": auc,
    }
    routes = defaultdict(int)
    for r_ in route:
        routes[r_] += 1
    test_band = band[test_idx]
    state = {
        "built_at": time.strftime("%Y-%m-%d %H:%M:%S"), "world": truth.raw.get("world"), "world_digest": world_digest(),
        "norms": norms, "recs": recs, "emb": emb, "index": index, "pairs": pairs,
        "sources": [sorted(cross[pq]) for pq in pairs], "X": X, "raw": raw, "p": p, "band": band,
        "route": route, "final": final, "llm": llm, "reviewer": reviewer, "alias": alias,
        "adjudication_usage": adjudication_usage,
        "dup_pairs": sorted(found_dups), "dup_stats": dup_stats,
        "groups": groups, "cluster_stats": cstats, "consistency": cons,
        "risk": {"alpha": alpha, "beta": config.DEFAULT_BETA, "tau_accept_raw": acc["tau"], "tau_reject_raw": rej["tau"],
                 "tau_accept": float(matcher.calibrate(np.array([acc["tau"]]))[0]) if np.isfinite(acc["tau"]) else None,
                 "tau_reject": float(matcher.calibrate(np.array([rej["tau"]]))[0]) if np.isfinite(rej["tau"]) else None,
                 "curve": curve, "cal_n": int(len(yc)), "cal_matches": int(yc.sum()), "delta": config.RISK_DELTA,
                 "cal_units": int(len(set(cal_blocks.tolist()))), "test_units": int(len(set(test_blocks.tolist()))),
                 "test_n": int(len(y_test))},
        "cal_raw": cal_raw, "cal_y": yc, "test_raw": test_raw, "test_y": y_test,
        "cal_blocks": cal_blocks, "test_blocks": test_blocks, "cal_X": Xc,
        "train_X": Xall, "train_y": yall, "train_w": wall,
        "test_band_counts": {k: int((test_band == v).sum()) for k, v in (("reject", 0), ("uncertain", 1), ("accept", 2))},
        "blocking": block, "evals": evals, "routes": dict(routes),
    }
    log("core build done", t0)
    if verbose:
        report(state)
    return state


def _components(edges):
    parent = {}

    def f(x):
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    for a, b in edges:
        ra, rb = f(a), f(b)
        if ra != rb:
            parent[ra] = rb
    return {x: f(x) for x in parent}


def _block_ids(pairs_of_units):
    ids = {}
    out = np.zeros(len(pairs_of_units), dtype=np.int64)
    for k, (a, b) in enumerate(pairs_of_units):
        key = (a, b) if a <= b else (b, a)
        out[k] = ids.setdefault(key, len(ids))
    return out


def _auto_only_groups(rid, pairs, band, alias, supplier_of, p):
    edges = []
    for k, (i, j) in enumerate(pairs):
        if band[k] == 2:
            a, b = alias.get(rid[i], rid[i]), alias.get(rid[j], rid[j])
            if a != b:
                edges.append((a, b, float(p[k])))
    C, _ = cluster.cluster_records(supplier_of, edges, [])
    groups = [set(g) for g in C.groups()]
    for sec, prim in alias.items():
        for g in groups:
            if prim in g:
                g.add(sec)
    return groups


def report(s: dict) -> None:
    b, e, r = s["blocking"], s["evals"], s["risk"]
    print("\n================ TESSERA METRICS REPORT ================")
    print(f"world={s['world']} records={len(s['norms'])} candidate pairs={len(s['pairs'])}")
    print(f"Blocking  recall={b['recall']:.4f}  reduction={b['reduction_ratio']:.5f}  by_source={b['by_source']}")
    print(f"Matcher   test AUC={e['auc_test']:.4f}")
    print(f"LTT       cal n={r['cal_n']} (matches {r['cal_matches']}), test n={r['test_n']}, delta={r['delta']}")
    for row in r["curve"]:
        print(f"   alpha={row['alpha'] * 100:5.2f}%  tau_p={row['tau_accept'] if row['tau_accept'] is None else round(row['tau_accept'], 4)}"
              f"  automation={row['automation'] * 100:5.1f}%  review={row['review_rate'] * 100:5.2f}%"
              f"  test FMR={row['empirical_fmr'] * 100:5.3f}% ({row['test_false_merges']}/{row['test_merges']} property merges; pair-level {row['pair_fmr'] * 100:.2f}%)  held={row['held']}")
    print(f"Routes    {s['routes']}")
    print(f"Clusters  {s['consistency']}")
    for k in ("test_pairwise", "test_pairwise_auto_only", "dubai_pairwise", "all_pairwise"):
        v = e[k]
        print(f"{k:<26} P={v['precision']:.4f} R={v['recall']:.4f} F1={v['f1']:.4f}")
    print(f"test_bcubed                P={e['test_bcubed']['precision']:.4f} R={e['test_bcubed']['recall']:.4f} F1={e['test_bcubed']['f1']:.4f}")
    print(f"Intra-supplier dups {s['dup_stats']}")


def save(state: dict) -> None:
    temporary = STATE_PATH.with_suffix(".tmp")
    with open(temporary, "wb") as f:
        pickle.dump(state, f, protocol=pickle.HIGHEST_PROTOCOL)
    temporary.replace(STATE_PATH)


def load() -> dict:
    with open(STATE_PATH, "rb") as f:
        state = pickle.load(f)
    if state.get("world_digest") and state["world_digest"] != world_digest():
        raise ValueError("The generated world has changed. Run make train to rebuild the matching pipeline.")
    return state


if __name__ == "__main__":
    from app.pipeline import enrich, ranking
    st = build()
    enrich.enrich(st)
    ranking.train(st)
    save(st)
    print(f"state saved to {STATE_PATH}")
