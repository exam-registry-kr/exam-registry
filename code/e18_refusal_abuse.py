"""E18: can someone make another person's ordinary question be refused?

During an exam a service judges the whole conversation. If exam text is in the conversation
(a shared document, a pasted page, the instructions of an app built on the service), an
ordinary question in the same conversation may be refused. Only someone who already holds
the exam text during the exam can do this, and a refusal lasts only until the exam ends.
This experiment measures how much exam text it takes and how long the effect lasts.

Victim: a conversation of V practice problems (V = 1, 4, 16; same group as the planted
item, the hardest case) followed by a follow-up question.
Planted text, placed before the victim's text
  part of a registered item: a run of consecutive words, 20% to 100% of the item
  stems only: the 10 question stems (public wording), as a check
Rules compared: R2 (E9), R3 (E14), R5 (the registry's rule, values of E19).
Second measurement, lasting effect: the whole item is planted in the first message and the
user then sends 8 ordinary messages (practice problems); counted: after how many of them
the conversation is still refused.
Comparison: the same conversations with nothing planted.

Items: E16's confirm set, every registered item, one conversation per item and setting.

    python e18_refusal_abuse.py          # a few minutes
"""
import json, sys
import numpy as np
import e9_korean_text_items as E9
import e12_split_questions as E12
import e14_sensitivity as E14
import e16_baselines as E16

SEED = 20261129
FRACTIONS = [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]
VICTIM = [1, 4, 16]
AFTER = 8


def main():
    out_path = sys.argv[1] if len(sys.argv) > 1 else "E18-001_results.json"
    C, SPAN = E9.R5_VALUES["C"], E9.R5_VALUES["span"]
    items, stems, qs, _ = E16.build(E14.SEED_CONFIRM)
    reg = E9.Registry(items, stems)
    practice = {g: [q[3] for q in qs if q[0] == g and q[1] == "practice"] for g in E16.GROUPS}
    r = np.random.default_rng(SEED)

    def judge(text):
        return dict(R2=reg.r2(text, E9.M_MIN, E14.E9_SHARE)[0], R3=reg.r3(text)[0], R5=bool(reg.r5(text)[0]))

    out = dict(experiment="E18-001", seed=SEED, R5=dict(C=C, span=SPAN), planted_part={}, lasting={})
    for v in VICTIM:
        for f in FRACTIONS:
            res = {g: dict(R2=0, R3=0, R5=0, of=0) for g in E16.GROUPS}
            for i, t in enumerate(items):
                g = E16.group(i)
                victim = " ".join(practice[g][int(j)] for j in r.choice(240, v, replace=False)) + " " + E12.FOLLOW[int(r.integers(0, len(E12.FOLLOW)))]
                planted = E14.excerpt(t, f, r) if f > 0 else ""
                h = judge((planted + " " + victim).strip())
                res[g]["of"] += 1
                for k in ("R2", "R3", "R5"):
                    res[g][k] += h[k]
            out["planted_part"][f"victim_{v}_planted_{f}"] = res
            print(f"victim {v:2d} practice problems, planted {f:.0%} of an item: refused " +
                  "  ".join(f"{g} R2 {res[g]['R2']:2d} R3 {res[g]['R3']:2d} R5 {res[g]['R5']:2d}" for g in E16.GROUPS) + "  of 60 each")
    res = dict(R2=0, R3=0, R5=0, of=0)
    for i in range(0, len(items), 3):
        h = judge(" ".join(E9.STEMS) + " " + practice[E16.group(i)][int(r.integers(0, 240))])
        res["of"] += 1
        for k in ("R2", "R3", "R5"):
            res[k] += h[k]
    out["planted_stems_only"] = res
    print("planted: the 10 stems only:", res)
    last = {k: [0] * (AFTER + 1) for k in ("R2", "R3", "R5")}
    n = 0
    for i, t in enumerate(items):
        g = E16.group(i); msgs = [t]; n += 1
        for m in range(AFTER + 1):
            h = judge(" ".join(msgs))
            for k in last:
                last[k][m] += h[k]
            msgs.append(practice[g][int(r.integers(0, 240))])
    out["lasting"] = dict(conversations=n, still_refused_after_n_ordinary_messages={k: v for k, v in last.items()},
                          note="index 0 = the planted item alone; index m = after m ordinary messages, the whole conversation judged")
    print("whole item planted first, then ordinary messages; conversations still refused after 0..8 messages (of %d):" % n)
    for k, v in last.items():
        print("  ", k, v)
    json.dump(out, open(out_path, "w"), indent=1, ensure_ascii=False)


if __name__ == "__main__":
    main()
