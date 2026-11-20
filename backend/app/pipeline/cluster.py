"""Constrained greedy correlation clustering (Saeedi et al., ESWC 2018 style).

Edges ("same" verdicts) are merged highest-probability first with union-find, but only when
(1) the merged cluster would not hold two records from the same supplier, and
(2) no explicit "different" verdict (cannot-link) exists across the two clusters.
Afterwards weak bridge edges are pruned. Consistency violations are therefore 0 by construction,
and `consistency_report` verifies that independently.
"""
from __future__ import annotations

from collections import defaultdict


class Clusters:
    def __init__(self, supplier_of: dict[str, str]):
        self.parent: dict[str, str] = {}
        self.members: dict[str, set[str]] = {}
        self.suppliers: dict[str, set[str]] = {}
        self.supplier_of = supplier_of
        self.cannot: dict[str, set[str]] = defaultdict(set)
        for r in supplier_of:
            self.add(r)

    def add(self, r: str, supplier: str | None = None):
        if supplier:
            self.supplier_of[r] = supplier
        if r in self.parent:
            return
        self.parent[r] = r
        self.members[r] = {r}
        self.suppliers[r] = {self.supplier_of[r]}

    def find(self, r: str) -> str:
        root = r
        while self.parent[root] != root:
            root = self.parent[root]
        while self.parent[r] != root:
            self.parent[r], r = root, self.parent[r]
        return root

    def add_cannot_link(self, a: str, b: str):
        self.cannot[a].add(b)
        self.cannot[b].add(a)

    def can_merge(self, a: str, b: str) -> tuple[bool, str | None]:
        ra, rb = self.find(a), self.find(b)
        if ra == rb:
            return True, None
        if self.suppliers[ra] & self.suppliers[rb]:
            return False, "supplier_exclusivity"
        small, big = (ra, rb) if len(self.members[ra]) < len(self.members[rb]) else (rb, ra)
        big_m = self.members[big]
        for m in self.members[small]:
            if self.cannot.get(m) and (self.cannot[m] & big_m):
                return False, "cannot_link"
        return True, None

    def union(self, a: str, b: str) -> tuple[bool, str | None]:
        ok, why = self.can_merge(a, b)
        if not ok:
            return False, why
        ra, rb = self.find(a), self.find(b)
        if ra == rb:
            return True, "already"
        if len(self.members[ra]) < len(self.members[rb]):
            ra, rb = rb, ra
        self.parent[rb] = ra
        self.members[ra] |= self.members.pop(rb)
        self.suppliers[ra] |= self.suppliers.pop(rb)
        return True, None

    def groups(self) -> list[set[str]]:
        return [set(m) for m in self.members.values()]

    def split_out(self, part: set[str]):
        """Detach `part` from its cluster into a new cluster (used by bridge pruning)."""
        root = self.find(next(iter(part)))
        rest = self.members[root] - part
        for grp in (rest, part):
            new_root = next(iter(grp))
            for m in grp:
                self.parent[m] = new_root
            self.members[new_root] = set(grp)
            self.suppliers[new_root] = {self.supplier_of[m] for m in grp}
        if root not in rest and root not in part:
            self.members.pop(root, None)
            self.suppliers.pop(root, None)


def cluster_records(supplier_of: dict[str, str], same_edges: list[tuple[str, str, float]],
                    cannot_links: list[tuple[str, str]], prune_below: float = 0.6) -> tuple[Clusters, dict]:
    C = Clusters(dict(supplier_of))
    for a, b in cannot_links:
        C.add_cannot_link(a, b)
    blocked = defaultdict(int)
    used_edges = []
    for a, b, w in sorted(same_edges, key=lambda t: -t[2]):
        ok, why = C.union(a, b)
        if ok:
            used_edges.append((a, b, w))
        else:
            blocked[why] += 1
    pruned = prune_bridges(C, used_edges, prune_below)
    return C, {"blocked": dict(blocked), "pruned": pruned, "edges_used": len(used_edges)}


def prune_bridges(C: Clusters, edges: list[tuple[str, str, float]], thr: float) -> int:
    """GraLMatch-style: split a cluster at a weak bridge edge when both sides are internally dense."""
    by_root = defaultdict(list)
    for a, b, w in edges:
        by_root[C.find(a)].append((a, b, w))
    pruned = 0
    for root, es in by_root.items():
        if len(C.members.get(root, ())) < 3:
            continue
        adj = defaultdict(list)
        for a, b, w in es:
            adj[a].append((b, w))
            adj[b].append((a, w))
        for a, b, w in sorted(es, key=lambda t: t[2]):
            if w >= thr:
                break
            # is (a,b) a bridge? BFS from a without using edge (a,b)
            seen, stack = {a}, [a]
            while stack:
                x = stack.pop()
                for y, _ in adj[x]:
                    if (x == a and y == b) or (x == b and y == a):
                        continue
                    if y not in seen:
                        seen.add(y)
                        stack.append(y)
            if b in seen:
                continue
            side_a, side_b = seen, set(C.members[C.find(a)]) - seen
            if len(side_a) >= 2 and len(side_b) >= 2:
                def density(side):
                    ws = [ww for x in side for y, ww in adj[x] if y in side]
                    return sum(ws) / len(ws) if ws else 0
                if density(side_a) >= 0.8 and density(side_b) >= 0.8:
                    C.split_out(side_a)
                    pruned += 1
                    break
    return pruned


def consistency_report(groups: list[set[str]], supplier_of: dict[str, str],
                       different_pairs: list[tuple[str, str]]) -> dict:
    """Count transitivity violations (explicit 'different' pairs placed in one cluster) and
    supplier-exclusivity violations (two records from one supplier in one cluster)."""
    where = {}
    for gi, g in enumerate(groups):
        for m in g:
            where[m] = gi
    trans = sum(1 for a, b in different_pairs if a in where and b in where and where[a] == where[b])
    excl = 0
    largest = 0
    for g in groups:
        sups = [supplier_of[m] for m in g]
        excl += len(sups) - len(set(sups))
        largest = max(largest, len(g))
    return {"transitivity_violations": trans, "supplier_exclusivity_violations": excl,
            "total_violations": trans + excl, "largest_cluster": largest, "n_clusters": len(groups)}
