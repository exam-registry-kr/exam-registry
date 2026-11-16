"""E14: why 4-character pieces, why these piece counts and shares?

E9 fixed four values: piece length 4, share 0.5 for questions with numbers, at least
20 matched pieces and share 0.6 for questions without numbers. Only the last one was
chosen on a separate set of items, and it was chosen against full practice problems only.
This experiment chooses every value the same way and shows what each one costs.

New questions (added to E9's sets)
  short_copy               a run of consecutive words of a registered item, 20% to 60%
                           of its words (must be refused)
  short_practice           the same for practice problems (must not be refused)
  short_practice_verbatim  a run from a practice problem that is word for word part of a
                           registered item; no content rule can tell it from exam text,
                           so it is reported and never used as a constraint

Arms
  A  piece length n = 2..6 with E9's values unchanged (comparison arm)
  B  for each n, values chosen on E9's selection set as in E9 (no full practice problem
     and no stem refused; most rewritten and short-copied items refused; ties: lowest
     share, then the middle of the tied piece counts), tested on the validation set
  C  as B, and short parts of practice problems may be refused at most 1 per 1000
     on the selection set (BUDGET)
  D  n = 4, validation set: the whole grid (pieces x share) for each path, so that the
     cost of every value can be read off
  The numbers path gets a piece floor (m_n) in B to D; E9 has none (m_n = 0).
For every arm: short copies 10% to 100% and E10's reading errors at 2% and 5%.
Check: n = 4 with E9's values reproduces E9's validation table.

    python e14_sensitivity.py          # about a minute
"""
import json, re, sys, time
from collections import Counter
import numpy as np
import e9_korean_text_items as E9
import e10_reading_errors as E10
import e12_split_questions as E12
from e8_registry_scale import numbers_count

LENGTHS = [2, 3, 4, 5, 6]
TH_NUM = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8]
TH_TXT = [0.3, 0.4, 0.5, 0.6, 0.7, 0.8]
M_GRID = [0, 5, 10, 15, 20, 25, 30, 40, 50, 60, 80]
KEEP = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.8, 1.0]
KEEP_SEL = [0.2, 0.3, 0.4, 0.5, 0.6]
ERR = [0.02, 0.05]
SEED_COPY, SEED_ERR = 20261123, 20261124
NEG = E9.NEG + ("short_practice", "short_practice_verbatim")


def make_pieces(n):
    def pieces(text):
        t0 = text.lower().replace(",", "")
        t = re.sub(r"[\s\.,?!·~\"'()]", "", t0)
        return {t[i:i + n] for i in range(max(0, len(t) - n + 1))}, {"#" + x for x in re.findall(r"\d+(?:\.\d+)?", t0)}
    return pieces


def use_length(n):
    E9.pieces = make_pieces(n)          # Registry and r2 look the function up at call time


def stats(reg, q):
    """Everything the decision needs, computed once; thresholds are applied afterwards."""
    if E9.strong_number(q):
        qg, qn = E9.pieces(E9.nk(q))[0], numbers_count(E9.nk(q))
        i, v = reg._top(reg.inv, qg)
        return dict(path="num", i=i, v=v, share=v / max(1, len(qg)), nums_ok=i >= 0 and qn <= reg.n[i])
    rest = E9.pieces(E9.nk(q))[0] - reg.stem
    i, v = reg._top(reg.inv, rest)
    return dict(path="txt", i=i, v=v, share=v / max(1, len(rest)))


def hit(s, th_n, m, th_t, m_n=0):
    """m_n: least matched pieces on the numbers path (0 = the E9 rule, which has no such floor)."""
    if s["i"] < 0:
        return False
    if s["path"] == "num":
        return s["share"] >= th_n and s["nums_ok"] and s["v"] >= m_n
    return s["v"] >= m and s["share"] >= th_t


def excerpt(t, f, r):
    w = t.split()
    k = max(1, round(len(w) * f))
    st = int(r.integers(0, len(w) - k + 1))
    return " ".join(w[st:st + k])


def norm(t):
    return re.sub(r"[\s\.,?!·~\"'()]", "", E9.nk(t).lower())


def add_short(items, qs, seed):
    """Short runs of consecutive words: of registered items (must be refused) and of
    practice problems (must not be refused). A run from a practice problem that is word
    for word part of a registered item cannot be told apart from exam text by any content
    rule; it is kept as 'short_practice_verbatim' and reported, not used as a constraint."""
    r = np.random.default_rng(seed + 7)
    flat = [norm(t) for t in items]
    extra = []
    for f in KEEP_SEL:
        for i, t in enumerate(items):
            extra.append((("EN", "KN", "KT")[i // 60], "short_copy", i, excerpt(t, f, r)))
        for g, k, _, q in [x for x in qs if x[1] == "practice"]:
            e = excerpt(q, f, r)
            same = any(norm(e) in t for t in flat)        # word for word part of a registered item
            extra.append((g, "short_practice_verbatim" if same else "short_practice", -1, e))
    return qs + extra


def compute(seed):
    items, stems, qs, _ = E9.build(seed)
    qs = add_short(items, qs, seed)
    reg = E9.Registry(items, stems)
    return items, stems, qs, reg, [stats(reg, q[3]) for q in qs]


def pick(grid):
    ok = [g for g in grid if g["false_refusals"] == 0]
    top = max((g["refused"] for g in ok), default=None)
    tied = sorted([g for g in ok if g["refused"] == top], key=lambda g: (g["share"], g["min_pieces"]))
    lowest = [g for g in tied if g["share"] == tied[0]["share"]] if tied else []
    return lowest[len(lowest) // 2] if lowest else None        # middle of the flat run of piece counts


def choose(qs, st):
    neg = [s for q, s in zip(qs, st) if q[1] in ("practice", "stem_only")]
    nn = [s for s in neg if s["path"] == "num"]
    wp = [(q, s) for q, s in zip(qs, st) if q[0] in ("EN", "KN") and q[1] not in NEG]
    grid_n = []
    for m in M_GRID:
        for t in TH_NUM:
            grid_n.append(dict(min_pieces=m, share=t, false_refusals=sum(hit(s, t, 0, 9, m) for s in nn),
                               refused=round(float(np.mean([hit(s, t, 0, 9, m) and s["i"] == q[2] for q, s in wp])), 4)))
    best_n = pick(grid_n)
    kt = [(q, s) for q, s in zip(qs, st) if q[0] == "KT" and q[1] not in NEG]
    # numbers: also report how much the share adds once the number rule is applied
    grid = []
    for m in M_GRID:
        for t in TH_TXT:
            false = sum(hit(s, 9, m, t) for s in neg if s["path"] == "txt")
            ref = float(np.mean([hit(s, 9, m, t) and s["i"] == q[2] for q, s in kt]))
            grid.append(dict(min_pieces=m, share=t, false_refusals=false, refused=round(ref, 4)))  # rewritten and short-copied
    return best_n, pick(grid), grid_n, grid


BUDGET = 1.0      # short parts of practice problems refused, per 1000, on the selection set


def choose_budget(qs, st):
    """As choose(), but short parts of practice problems (not word for word exam text) may be
    refused at most BUDGET per 1000 on the selection set."""
    rows = list(zip(qs, st))
    full = [s for q, s in rows if q[1] in ("practice", "stem_only")]
    out = {}
    for path, groups in (("num", ("EN", "KN")), ("txt", ("KT",))):
        pos = [(q, s) for q, s in rows if q[0] in groups and q[1] not in NEG]          # rewritten and short copies
        sp = [s for q, s in rows if q[1] == "short_practice" and s["path"] == path]
        grid = []
        for m in M_GRID:
            for t in (TH_NUM if path == "num" else TH_TXT):
                P = (t, 0, 9, m) if path == "num" else (9, m, t, 0)
                grid.append(dict(min_pieces=m, share=t,
                                 false_refusals=sum(hit(s, *P) for s in full if s["path"] == path)
                                 + (1 if 1000 * sum(hit(s, *P) for s in sp) / max(1, len(sp)) > BUDGET else 0),
                                 refused=round(float(np.mean([hit(s, *P) and s["i"] == q[2] for q, s in pos])), 4)))
        out[path] = pick(grid)
    return out


def table(qs, st, P):
    out = {}
    for g in ("EN", "KN", "KT"):
        rows = [(q, s) for q, s in zip(qs, st) if q[0] == g]
        pos = [(q, s) for q, s in rows if q[1] not in NEG and q[1] != "short_copy"]
        sc = [(q, s) for q, s in rows if q[1] == "short_copy"]
        d = dict(rewritten=len(pos), rewritten_refused=round(float(np.mean([hit(s, *P) and s["i"] == q[2] for q, s in pos])), 4),
                 short_copy=len(sc), short_copy_refused=round(float(np.mean([hit(s, *P) and s["i"] == q[2] for q, s in sc])), 4))
        for k in NEG:
            sel = [(q, s) for q, s in rows if q[1] == k]
            if sel:
                d[k] = [int(sum(hit(s, *P) for q, s in sel)), len(sel)]
        prac = [s["share"] for q, s in rows if q[1] == "practice"]
        lo = [s["share"] for q, s in pos]
        d["practice_highest_share"], d["rewritten_lowest_share"] = round(max(prac), 4), round(min(lo), 4)
        out[g] = d
    return out


def short_copies(items, reg, P):
    r = np.random.default_rng(SEED_COPY)
    out = {}
    for f in KEEP:
        res = {g: [] for g in ("EN", "KN", "KT")}
        for i, t in enumerate(items):
            w = t.split()
            k = max(1, round(len(w) * f))
            st = int(r.integers(0, len(w) - k + 1))
            s = stats(reg, " ".join(w[st:st + k]))
            res[("EN", "KN", "KT")[i // 60]].append(hit(s, *P) and s["i"] == i)
        out[str(f)] = {g: round(float(np.mean(v)), 4) for g, v in res.items()}
    return out


def reading_errors(items, qs, reg, P):
    r = np.random.default_rng(SEED_ERR)
    out = {}
    for p in ERR:
        res = {g: [] for g in ("EN", "KN", "KT")}
        for i, t in enumerate(items):
            for _ in range(3):
                s = stats(reg, E10.damage(t, p, r))
                res[("EN", "KN", "KT")[i // 60]].append(hit(s, *P) and s["i"] == i)
        prac = [q[3] for q in qs if q[1] == "practice"]
        fp = sum(hit(stats(reg, E10.damage(q, p, r)), *P) for q in prac)
        out[str(p)] = {g: round(float(np.mean(v)), 4) for g, v in res.items()} | {"practice_refused": [int(fp), len(prac)]}
    return out


E9_SHARE = 0.6


def tradeoff(qs, st):
    """Validation set, n = 4: what each value costs. Numbers path: floor of pieces x share.
    Text path: least pieces x share. Rates per 1000 short parts of practice problems."""
    rows = list(zip(qs, st))
    def rate(sel, f):
        return round(1000 * sum(f(s) for q, s in sel) / max(1, len(sel)), 2)
    out = dict(numbers=[], text=[])
    for path, groups, key in (("num", ("EN", "KN"), "numbers"), ("txt", ("KT",), "text")):
        pos = [(q, s) for q, s in rows if q[0] in groups and q[1] not in NEG and q[1] != "short_copy"]
        sc = [(q, s) for q, s in rows if q[0] in groups and q[1] == "short_copy"]
        fp = [(q, s) for q, s in rows if q[0] in groups and q[1] == "practice" and s["path"] == path]
        sp = [(q, s) for q, s in rows if q[0] in groups and q[1] == "short_practice" and s["path"] == path]
        sv = [(q, s) for q, s in rows if q[0] in groups and q[1] == "short_practice_verbatim" and s["path"] == path]
        for m in M_GRID:
            for t in (TH_NUM if path == "num" else TH_TXT):
                P = (t, 0, 9, m) if path == "num" else (9, m, t, 0)
                own = lambda sel: round(float(np.mean([hit(s, *P) and s["i"] == q[2] for q, s in sel])), 4)
                out[key].append(dict(min_pieces=m, share=t, rewritten_refused=own(pos), short_copy_refused=own(sc),
                                     practice_refused=int(sum(hit(s, *P) for q, s in fp)),
                                     short_practice_refused_per_1000=rate(sp, lambda s: hit(s, *P)),
                                     verbatim_parts_refused_per_1000=rate(sv, lambda s: hit(s, *P))))
    return out


SEED_FRESH = 20261125
POINTS = [(20, 0.6), (40, 0.6), (40, 0.7), (50, 0.6), (60, 0.6), (60, 0.7)]


def operating_points():
    """n = 4, text path only. Candidate (pieces, share) points on three sets: selection,
    validation and a fresh set (seed SEED_FRESH) that was used only to confirm, after the
    points had been looked at on the first two. Split questions as in E12, validation set."""
    use_length(4)
    out = {}
    for name, seed in (("selection", E9.SEED_SELECT), ("validation", E9.SEED_VALIDATE), ("fresh", SEED_FRESH)):
        items, stems, qs, reg, st = compute(seed)
        rows = list(zip(qs, st))
        sp = [s for q, s in rows if q[1] == "short_practice" and s["path"] == "txt"]
        full = [s for q, s in rows if q[1] in ("practice", "stem_only") and s["path"] == "txt"]
        rw = [(q, s) for q, s in rows if q[0] == "KT" and q[1] not in NEG and q[1] != "short_copy"]
        sc = [(q, s) for q, s in rows if q[0] == "KT" and q[1] == "short_copy"]
        r = np.random.default_rng(SEED_ERR)
        dmg = {p: [(i, stats(reg, E10.damage(items[i], p, r))) for i in range(120, 180) for _ in range(3)] for p in (0.05, 0.10)}
        res = []
        for m, t in POINTS:
            P = (9, m, t, 0)
            d = dict(min_pieces=m, share=t,
                     short_practice_refused_per_1000=round(1000 * sum(hit(s, *P) for s in sp) / len(sp), 2),
                     practice_and_stems_refused=int(sum(hit(s, *P) for s in full)),
                     rewritten_refused=round(float(np.mean([hit(s, *P) and s["i"] == q[2] for q, s in rw])), 4),
                     short_copy_refused=round(float(np.mean([hit(s, *P) and s["i"] == q[2] for q, s in sc])), 4),
                     errors_5_refused=round(float(np.mean([hit(s, *P) and s["i"] == i for i, s in dmg[0.05]])), 4),
                     errors_10_refused=round(float(np.mean([hit(s, *P) and s["i"] == i for i, s in dmg[0.10]])), 4))
            if name == "validation":
                for k in (4, 8):
                    for w in (1, 2, 99):
                        ok = []
                        for i in range(120, 180):
                            msgs = E12.numbers_apart(items[i], k)
                            ok.append(any(hit(stats(reg, " ".join(msgs[max(0, j - w + 1):j + 1])), *P) for j in range(len(msgs))))
                        d[f"split_{k}_last_{'all' if w == 99 else w}"] = round(float(np.mean(ok)), 4)
            res.append(d)
        out[name] = dict(short_practice_parts=len(sp), points=res)
    return out


def main():
    out_path = sys.argv[1] if len(sys.argv) > 1 else "E14-001_results.json"
    t0 = time.time()
    out = dict(experiment="E14-001", seeds=dict(select=E9.SEED_SELECT, validate=E9.SEED_VALIDATE, copies=SEED_COPY, errors=SEED_ERR),
               grids=dict(share_numbers=TH_NUM, share_text=TH_TXT, min_pieces=M_GRID),
               selection_rule=dict(numbers="lowest share with no practice problem refused",
                                   text="most rewritten and short-copied text items refused with no practice problem, no short part of a practice problem and no stem refused; ties: lowest share, then the middle of the tied piece counts"),
               by_length={})

    # check: n = 4 with E9's values reproduces E9's validation table
    use_length(4)
    e9 = json.load(open("../results/E9-001_results.json"))
    _, _, qs, reg, st = compute(E9.SEED_VALIDATE)
    mine = table(qs, st, (E9.TH, E9.M_MIN, e9["share_text_chosen"], 0))
    theirs = e9["validation_set"]
    same = all(mine[g]["rewritten_refused"] == theirs[g]["refused_rewritten_matching_its_own_item"]["R2"] for g in mine) and \
        all(mine[g][k][0] == theirs[g]["refused_other"][k]["R2"] for g in mine for k in E9.NEG if k in mine[g])
    out["check_n4_equals_E9"] = same
    assert e9["share_text_chosen"] == E9_SHARE
    out["n4_with_E9_values"] = mine
    print("check: n = 4 with E9 values reproduces E9 validation:", same)

    for n in LENGTHS:
        use_length(n)
        _, _, qs_s, _, st_s = compute(E9.SEED_SELECT)
        bn, bt, grid_n, grid_t = choose(qs_s, st_s)
        items, stems, qs, reg, st = compute(E9.SEED_VALIDATE)
        d = dict(chosen=dict(share_numbers=bn and bn["share"], min_pieces_numbers=bn and bn["min_pieces"],
                             min_pieces_text=bt and bt["min_pieces"], share_text=bt and bt["share"]),
                 selection_grid_numbers=grid_n, selection_grid_text=grid_t,
                 pieces_per_question_median=int(np.median([len(E9.pieces(E9.nk(q[3]))[0]) for q in qs if q[1] not in ("short_copy", "short_practice")])))
        if bn and bt:
            P = (bn["share"], bt["min_pieces"], bt["share"], bn["min_pieces"])
            d["selection"] = table(qs_s, st_s, P)
            d["validation"] = table(qs, st, P)
            d["short_copies"] = short_copies(items, reg, P)
            d["reading_errors"] = reading_errors(items, qs, reg, P)
            # comparison arm: the same n with E9's numbers rule (no piece floor on the numbers path)
            P0 = (bn["share"], bt["min_pieces"], bt["share"], 0)
            d["validation_without_numbers_floor"] = table(qs, st, P0)
        b = choose_budget(qs_s, st_s)
        d["chosen_with_budget"] = dict(budget_per_1000=BUDGET, numbers=b["num"], text=b["txt"])
        if b["num"] and b["txt"]:
            PB = (b["num"]["share"], b["txt"]["min_pieces"], b["txt"]["share"], b["num"]["min_pieces"])
            d["validation_with_budget"] = table(qs, st, PB)
            d["short_copies_with_budget"] = short_copies(items, reg, PB)
            d["reading_errors_with_budget"] = reading_errors(items, qs, reg, PB)
        PE9 = (E9.TH, E9.M_MIN, E9_SHARE, 0)
        d["validation_with_E9_values"] = table(qs, st, PE9)
        d["short_copies_with_E9_values"] = short_copies(items, reg, PE9)
        d["reading_errors_with_E9_values"] = reading_errors(items, qs, reg, PE9)
        if n == 4:
            d["tradeoff_validation"] = tradeoff(qs, st)
        out["by_length"][str(n)] = d
        v = d.get("validation", {})
        print(f"n={n}: chosen {d['chosen']}  with budget {d['chosen_with_budget']}  ({time.time() - t0:.0f}s)")
        for g in v:
            print(f"   {g}: rewritten {v[g]['rewritten_refused']}  short {v[g]['short_copy_refused']}  "
                  + "  ".join(f"{k} {v[g][k]}" for k in NEG if k in v[g]))
    out["operating_points_text_n4"] = operating_points()
    for name, v in out["operating_points_text_n4"].items():
        print(name)
        for d in v["points"]:
            print("  ", {k: x for k, x in d.items()})
    json.dump(out, open(out_path, "w"), indent=1, ensure_ascii=False)


if __name__ == "__main__":
    main()
