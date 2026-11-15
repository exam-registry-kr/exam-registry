"""E8: does the content lookup still hold when many exams are registered at once?

E3 and E7 used 60 registered items. In a midterm week thousands of schools could be
registered at the same time, so the registry can hold tens of thousands of items. Two
things could break as it grows:

  1. False refusals: a practice problem might share most pieces and all its numbers
     with one of the many registered items.
  2. Missed detections: a rewritten exam question might score higher against some
     other registered item of the same kind, so the number check is applied to the
     wrong item.

Worst case by construction: every added item comes from the SAME 12 templates as the
60 original items and the 240 practice problems, so the registry fills with near
duplicates of what students practise.

Rule of E7: pieces = 4-character pieces and number tokens; take the registered item
with the highest share of the query's pieces (ties: lowest index); refuse if the share
is at least 0.5 and every number in the query appears in that item. E7 showed the
encrypted lookup gives the same decision as this plaintext rule on every query, so the
plaintext rule is used here. Encryption cost does not change with registry size: the
authority evaluates only the query's own pieces.

Arms (2 x 2)
  which item   : top  = only the item with the highest share (E7)
                 any  = every item whose share is at least 0.5
  number check : set   = each distinct number once (E7)
                 count = repeated numbers must be repeated in the item too
                         ("ratio 68 and first term 68" needs two 68s)

Baseline: at 60 items the top/set arm must reproduce E7's plaintext decisions exactly.

    python e8_registry_scale.py          # about two minutes
"""
import json, re, statistics, sys, time
from collections import Counter, defaultdict
import numpy as np
import e3_registry as E3
from e7_oprf_lookup import pieces, regenerate_e3, TH

SIZES = [60, 600, 6000, 60000]
EXTRA_SEED = 20261118
ARMS = ["top_set", "any_set", "top_count", "any_count"]


def numbers_count(text):
    """Number tokens counted with repetition: two 68s give #68 and #68*2."""
    c = Counter(re.findall(r"\d+(?:\.\d+)?", text.lower().replace(",", "")))
    return {f"#{k}" + ("" if j == 1 else f"*{j}") for k, v in c.items() for j in range(1, v + 1)}


def build_items():
    """E3's items, rewrites and practice problems, plus extra items from the same templates."""
    reg, neg, pos = regenerate_e3()
    rng = np.random.default_rng(EXTRA_SEED)
    neg_set = set(neg)
    extra, replaced = [], 0
    while len(extra) < SIZES[-1] - len(reg):
        x = E3.make(len(extra) % 12, rng)
        if x in neg_set:          # an exact copy would be a registered item, not a practice problem
            replaced += 1
            continue
        extra.append(x)
    return reg, neg, pos, extra, replaced


class Index:
    def __init__(self, items):
        self.nset, self.ncount = [], []
        self.inv = defaultdict(list)
        for i, it in enumerate(items):
            g, n = pieces(it)
            self.nset.append(n)
            self.ncount.append(numbers_count(it))
            for x in g:
                self.inv[x].append(i)

    def counts(self, qg):
        c = Counter()
        for x in qg:
            for i in self.inv.get(x, ()):
                c[i] += 1
        return c

    def decide(self, c, n_g, qset, qcount):
        out = {}
        if not c:
            return {a: (False, -1) for a in ARMS}, 0.0
        top_v = max(c.values())
        top = min(k for k, v in c.items() if v == top_v)
        score = top_v / max(1, n_g)
        need = TH * max(1, n_g)
        cand = [i for i, v in c.items() if v >= need]
        for nk, q, store in (("set", qset, self.nset), ("count", qcount, self.ncount)):
            def ok(i, q=q, store=store):
                return len(q) > 0 and q <= store[i]
            out["top_" + nk] = (score >= TH and ok(top), top)
            hits = [i for i in cand if ok(i)]
            out["any_" + nk] = (True, max(hits, key=lambda i: (c[i], -i))) if hits else (False, -1)
        return out, score


def main():
    out_path = sys.argv[1] if len(sys.argv) > 1 else "E8-001_results.json"
    reg, neg, pos, extra, replaced = build_items()
    queries = [(k, qi, v) for k, qi, v in pos] + [("practice", -1, q) for q in neg]
    qp = [(pieces(q)[0], pieces(q)[1], numbers_count(q)) for _, _, q in queries]
    e7 = json.load(open("../results/E7-001_results.json"))["rows"]
    kinds = ["format", "numbers", "reorder", "partial", "synonym", "combined"]
    out = dict(experiment="E8-001", threshold=TH, sizes=SIZES, arms=ARMS, n_queries=len(queries),
               n_positive=len(pos), n_practice=len(neg), templates=12, extra_seed=EXTRA_SEED,
               extra_exact_copies_of_practice_replaced=replaced, by_size={})
    for N in SIZES:
        items = reg + extra[:N - len(reg)]
        t = time.perf_counter()
        idx = Index(items)
        build_s = time.perf_counter() - t
        rows, lat = [], []
        for (kind, qi, q), (g, nset, ncount) in zip(queries, qp):
            t = time.perf_counter()
            d, score = idx.decide(idx.counts(g), len(g), nset, ncount)
            lat.append(time.perf_counter() - t)
            r = dict(kind=kind, item=qi, score=round(score, 4))
            for a in ARMS:
                r[a], r[a + "_item"] = bool(d[a][0]), d[a][1]
            rows.append(r)

        pos_rows = [r for r in rows if r["kind"] != "practice"]
        prac = [r for r in rows if r["kind"] == "practice"]
        hit = lambda r, a: r[a] and r[a + "_item"] == r["item"]
        entry = dict(
            n_registered=N, index_build_seconds=round(build_s, 3),
            detected_correct_item={a: round(float(np.mean([hit(r, a) for r in pos_rows])), 4) for a in ARMS},
            detected_by_rewrite={k: {a: round(float(np.mean([hit(r, a) for r in pos_rows if r["kind"] == k])), 4)
                                     for a in ARMS} for k in kinds},
            practice_refused={a: int(sum(r[a] for r in prac)) for a in ARMS},
            practice_refused_examples={a: [dict(practice=neg[j], matched=items[r[a + "_item"]])
                                           for j, r in enumerate(prac) if r[a]] for a in ARMS},
            lookup_ms_median=round(1000 * statistics.median(lat), 3),
            lookup_ms_p95=round(1000 * float(np.percentile(lat, 95)), 3))
        line = ""
        if N == len(reg):
            same = sum(r["top_set"] == e["plain"] and r["top_set_item"] == e["plain_item"] and r["score"] == e["plain_score"]
                       for r, e in zip(rows, e7))
            entry["baseline_top_set_matches_E7_plain"] = dict(count=same, total=len(rows))
            line = f"  baseline top_set = E7 plain: {same}/{len(rows)}"
        out["by_size"][str(N)] = entry
        print(f"N={N:6d}  lookup median {entry['lookup_ms_median']:.3f} ms{line}")
        for a in ARMS:
            print(f"    {a:10s} detected {entry['detected_correct_item'][a]:.3f}   practice refused {entry['practice_refused'][a]}/{len(neg)}")
    json.dump(out, open(out_path, "w"), indent=1, ensure_ascii=False)


if __name__ == "__main__":
    main()
