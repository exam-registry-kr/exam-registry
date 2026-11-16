"""E19: the values of rule R5, chosen again with more long conversations, and confirmed on
a set of items that had never been used.

E16 chose R5's two values (C: share of the item's pieces, SPAN: length of the run) on the
selection set with 300 conversations of practice problems. On the three other sets R5 then
refused 1 to 3 of 100 conversations of 16 practice problems. Those three sets cannot be
used to choose again, so this experiment
  1. adds 600 conversations of 16 and 300 conversations of 32 practice problems to the
     SELECTION set and chooses C and SPAN there, by a rule fixed before any other set is
     looked at: no practice problem, stem or practice conversation refused; among the
     settings within 0.5 percentage points of the most must-refuse questions refused, the
     smallest SPAN and the middle of the tied values of C;
  2. evaluates R3 (comparison arm) and R5 once on a FINAL set (seed 20261130) that no
     earlier experiment used, with the same kinds of question as E16 and 300 + 100 long
     conversations.
Check: the rule as built into e9 (Registry.r5) gives the same decisions as this script.
(On the first run 27 of 9,590 decisions differed: the built-in rule skipped items of which
the whole text held less than C, but dropping sentences joins their neighbours and adds
pieces. The skip was corrected to allow for that; C and SPAN were not changed.
E12 then showed that a practice problem with numbers followed by a stem was judged as text
against an item with numbers, without the number test (2 of 600 mixed conversations refused).
This was corrected in the rule, and E16 and this experiment were run again.)

    python e19_adopt_r5.py          # about ten minutes
"""
import json, sys, time
import numpy as np
import e9_korean_text_items as E9
import e14_sensitivity as E14
import e16_baselines as E16

SEED_FINAL = 20261130
MARGIN = 0.005
LONG = dict(selection=((16, 600), (32, 300)), final=((16, 300), (32, 100)))


def build(seed, which):
    items, stems, qs, convs = E16.build(seed)
    r = np.random.default_rng(seed + 19)
    practice = {g: [q[3] for q in qs if q[0] == g and q[1] == "practice"] for g in E16.GROUPS}
    for n, count in LONG[which]:
        for _ in range(count):
            g = E16.GROUPS[int(r.integers(0, 3))]
            convs.append((g, f"long_{n}", -1, " ".join(practice[g][int(j)] for j in r.choice(240, n, replace=False))))
    return items, stems, qs + convs


NOT = lambda k: k in E16.NEG or k.startswith("conv_") or k.startswith("long_")
HARD = lambda k: k in ("practice", "stem_only") or k.startswith("conv_") or k.startswith("long_")


def main():
    out_path = sys.argv[1] if len(sys.argv) > 1 else "E19-001_results.json"
    t0 = time.time()
    out = dict(experiment="E19-001", seeds=dict(selection=E9.SEED_SELECT, final=SEED_FINAL), margin=MARGIN, grid=dict(C=E16.C_GRID, span=E16.SPANS))
    items, stems, allq = build(E9.SEED_SELECT, "selection")
    R = E16.Rules(items, stems)
    st = [dict(base=R.r5_base(q[3]), cov=R.coverage(q[3])) for q in allq]
    grid = []
    for span in E16.SPANS:
        for c in E16.C_GRID:
            h = [E16.r5_hit(o, c, span) for o in st]
            grid.append(dict(span=span, C=c, false_refusals=int(sum(x[0] for q, x in zip(allq, h) if HARD(q[1]))),
                             refused=round(float(np.mean([x[0] and x[1] == q[2] for q, x in zip(allq, h) if not NOT(q[1])])), 4)))
    ok = [g for g in grid if g["false_refusals"] == 0]
    top = max(g["refused"] for g in ok)
    near = sorted([g for g in ok if g["refused"] >= top - MARGIN], key=lambda g: (g["span"], g["C"]))
    near = [g for g in near if g["span"] == near[0]["span"]]
    chosen = near[len(near) // 2]
    out["selection_grid"], out["chosen"] = grid, chosen
    print(f"selection ({time.time() - t0:.0f}s): chosen", chosen)
    for g in grid:
        if g["span"] == chosen["span"]:
            print("   ", g)
    assert (chosen["C"], chosen["span"]) == (E9.R5_VALUES["C"], E9.R5_VALUES["span"]), "set E9.R5_VALUES to the chosen values and run again"

    items, stems, allq = build(SEED_FINAL, "final")
    reg = E9.Registry(items, stems)
    R = E16.Rules(items, stems)
    rows, same = [], 0
    for g, k, qi, q in allq:
        r3 = reg.r3(q)[:2]; r5 = reg.r5(q)[:2]
        o = dict(base=R.r5_base(q), cov=R.coverage(q))
        same += bool(E16.r5_hit(o, chosen["C"], chosen["span"])[0]) == r5[0]
        rows.append((g, k, qi, r3, r5))
    out["built_in_rule_same_decisions"] = [same, len(allq)]
    tab = dict(refused={}, not_to_refuse={})
    for k in dict.fromkeys(r[1] for r in rows):
        sel = [r for r in rows if r[1] == k]
        if NOT(k):
            tab["not_to_refuse"][k] = dict(R3=int(sum(r[3][0] for r in sel)), R5=int(sum(r[4][0] for r in sel)), of=len(sel))
        else:
            tab["refused"][k] = {g: dict(R3=round(float(np.mean([r[3][0] and r[3][1] == r[2] for r in sel if g in ("all", r[0])])), 4),
                                         R5=round(float(np.mean([r[4][0] and r[4][1] == r[2] for r in sel if g in ("all", r[0])])), 4),
                                         of=sum(g in ("all", r[0]) for r in sel))
                                 for g in E16.GROUPS + ("all",) if any(g in ("all", r[0]) for r in sel)}
    out["final_set"] = tab
    print(f"final set ({time.time() - t0:.0f}s): built-in rule gives the same decisions: {same}/{len(allq)}")
    for k, v in tab["refused"].items():
        print(f"   {k:22s} R3 {v['all']['R3']:.3f}  R5 {v['all']['R5']:.3f}")
    for k, v in tab["not_to_refuse"].items():
        print(f"   not to refuse {k:28s} R3 {v['R3']:4d}  R5 {v['R5']:4d}  of {v['of']}")
    json.dump(out, open(out_path, "w"), indent=1, ensure_ascii=False)


if __name__ == "__main__":
    main()
