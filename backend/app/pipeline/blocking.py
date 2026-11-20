"""Candidate generation: union of H3 geo cells, BM25, MiniLM+FAISS ANN, and photo pHash collisions."""
from __future__ import annotations

import time
from collections import defaultdict
from functools import lru_cache

import h3
import numpy as np
import orjson
from rank_bm25 import BM25Okapi

from app import config

H3_RES = 9
TOPK = 10
PHASH_MAX_HAMMING = 8


@lru_cache(maxsize=1)
def embedder():
    import os
    os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
    if (config.CACHE_DIR / "hf").exists() and any((config.CACHE_DIR / "hf").iterdir()):
        os.environ.setdefault("HF_HUB_OFFLINE", "1")  # model cached: never touch the network
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2", cache_folder=str(config.CACHE_DIR / "hf"))


def embed_text(n: dict) -> str:
    return f"{n['name_norm']} | {n['brand'] or ''} | {n['city']}"


def embed(norms: list[dict]) -> np.ndarray:
    if not norms:
        return np.zeros((0, 384), dtype=np.float32)
    v = embedder().encode([embed_text(n) for n in norms], batch_size=128, show_progress_bar=False,
                          normalize_embeddings=True)
    return np.asarray(v, dtype=np.float32)


def bm25_tokens(n: dict) -> list[str]:
    toks = list(n["core_tokens"])
    if n["brand"]:
        toks += n["brand"].lower().replace("&", " and ").split()
    return toks or n["name_norm"].split()


# ---------------------------------------------------------------- photo hashes
def photo_hashes(norms: list[dict]) -> dict[str, list[int]]:
    """pHash of every supplier photo (cached on disk by URL)."""
    import imagehash
    from PIL import Image
    cache_p = config.CACHE_DIR / "phash.json"
    cache = orjson.loads(cache_p.read_bytes()) if cache_p.exists() else {}
    out, dirty = {}, False
    for n in norms:
        hs = []
        for ph in n.get("photos", []):
            url = ph["url"] if isinstance(ph, dict) else ph
            if url not in cache:
                path = config.FRONTEND_PUBLIC / url.lstrip("/")
                if not path.exists():
                    continue
                cache[url] = int(str(imagehash.phash(Image.open(path))), 16)
                dirty = True
            hs.append(cache[url])
        if hs:
            out[n["record_id"]] = hs
    if dirty:
        cache_p.write_bytes(orjson.dumps(cache))
    return out


_POP8 = np.array([bin(i).count("1") for i in range(256)], dtype=np.int64)


def popcount64(x: np.ndarray) -> np.ndarray:
    x = np.asarray(x, dtype=np.uint64)
    table = _POP8
    c = np.zeros(x.shape, dtype=np.int64)
    for s in range(0, 64, 8):
        c += table[((x >> np.uint64(s)) & np.uint64(0xFF)).astype(np.int64)]
    return c


class CandidateIndex:
    """Holds everything needed to propose candidates for existing and incoming records."""

    def __init__(self, norms: list[dict], emb: np.ndarray, hashes: dict[str, list[int]]):
        self.norms = list(norms)
        self.emb = emb
        self.hashes = hashes
        self.by_id = {n["record_id"]: i for i, n in enumerate(self.norms)}
        self._build()

    def _build(self):
        self.cell = [h3.latlng_to_cell(n["lat"], n["lng"], H3_RES) for n in self.norms]
        self.cell_index = defaultdict(list)
        for i, c in enumerate(self.cell):
            self.cell_index[c].append(i)
        self.city_rows = defaultdict(list)
        for i, n in enumerate(self.norms):
            self.city_rows[n["city"]].append(i)
        self.bm25 = {}
        self.faiss = {}
        import faiss
        for city, rows in self.city_rows.items():
            self.bm25[city] = BM25Okapi([bm25_tokens(self.norms[i]) for i in rows])
            idx = faiss.IndexFlatIP(self.emb.shape[1])
            idx.add(self.emb[rows])
            self.faiss[city] = idx
        # photo hash table
        self.ph_rows, self.ph_vals = [], []
        for rid, hs in self.hashes.items():
            if rid in self.by_id:
                for h in hs:
                    self.ph_rows.append(self.by_id[rid])
                    self.ph_vals.append(h)
        self.ph_rows = np.array(self.ph_rows, dtype=np.int64)
        self.ph_vals = np.array(self.ph_vals, dtype=np.uint64)

    # -------------------------------------------------------------- queries
    def query(self, n: dict, vec: np.ndarray, hashes: list[int] | None = None, self_row: int | None = None,
              topk: int = TOPK) -> dict[int, set[str]]:
        """Return {row: sources} for one record (existing or new)."""
        out: dict[int, set[str]] = defaultdict(set)
        cell = h3.latlng_to_cell(n["lat"], n["lng"], H3_RES)
        for c in h3.grid_disk(cell, 1):
            for j in self.cell_index.get(c, ()):
                out[j].add("geo")
        rows = self.city_rows.get(n["city"], [])
        if rows:
            scores = self.bm25[n["city"]].get_scores(bm25_tokens(n))
            k = min(topk + 1, len(rows))
            top = np.argpartition(-scores, k - 1)[:k]
            for t in top:
                if scores[t] > 0:
                    out[rows[t]].add("bm25")
            D, I = self.faiss[n["city"]].search(vec.reshape(1, -1), min(topk + 1, len(rows)))
            for t in I[0]:
                if t >= 0:
                    out[rows[t]].add("ann")
        if hashes and len(self.ph_vals):
            for h in hashes:
                d = popcount64(self.ph_vals ^ np.uint64(h))
                for j in self.ph_rows[d <= PHASH_MAX_HAMMING]:
                    out[int(j)].add("photo")
        if self_row is not None:
            out.pop(self_row, None)
        return out

    def all_pairs(self) -> tuple[dict[tuple[int, int], set[str]], dict[tuple[int, int], set[str]]]:
        """Candidate pairs among all indexed records. Returns (cross_supplier, same_supplier)."""
        cross: dict[tuple[int, int], set[str]] = defaultdict(set)
        same: dict[tuple[int, int], set[str]] = defaultdict(set)
        sup = [n["supplier"] for n in self.norms]
        # geo
        for i, c in enumerate(self.cell):
            for cc in h3.grid_disk(c, 1):
                for j in self.cell_index.get(cc, ()):
                    if j > i:
                        (cross if sup[i] != sup[j] else same)[(i, j)].add("geo")
        # bm25 + ann per city (batched)
        for city, rows in self.city_rows.items():
            rows_a = np.array(rows)
            bm = self.bm25[city]
            k = min(TOPK + 1, len(rows))
            for li, i in enumerate(rows):
                scores = bm.get_scores(bm25_tokens(self.norms[i]))
                top = np.argpartition(-scores, k - 1)[:k]
                for t in top:
                    j = int(rows_a[t])
                    if j != i and scores[t] > 0:
                        a, b = min(i, j), max(i, j)
                        (cross if sup[a] != sup[b] else same)[(a, b)].add("bm25")
            D, I = self.faiss[city].search(self.emb[rows], k)
            for li, i in enumerate(rows):
                for t in I[li]:
                    if t < 0:
                        continue
                    j = int(rows_a[t])
                    if j != i:
                        a, b = min(i, j), max(i, j)
                        (cross if sup[a] != sup[b] else same)[(a, b)].add("ann")
        # photo collisions
        if len(self.ph_vals):
            for k in range(len(self.ph_vals)):
                d = popcount64(self.ph_vals ^ self.ph_vals[k])
                for t in np.where(d <= PHASH_MAX_HAMMING)[0]:
                    i, j = int(self.ph_rows[k]), int(self.ph_rows[t])
                    if i < j:
                        (cross if sup[i] != sup[j] else same)[(i, j)].add("photo")
        return dict(cross), dict(same)


def build_index(norms: list[dict], emb: np.ndarray | None = None) -> CandidateIndex:
    t0 = time.time()
    if emb is None:
        emb = embed(norms)
    hashes = photo_hashes(norms)
    idx = CandidateIndex(norms, emb, hashes)
    print(f"  index built for {len(norms)} records in {time.time() - t0:.1f}s")
    return idx
