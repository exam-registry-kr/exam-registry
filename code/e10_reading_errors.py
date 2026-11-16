"""E10: what happens to the content lookup when the text read from a photo has errors?

When a service receives a photo, it first reads the text and then looks the text up.
Reading is not perfect. This experiment damages the questions with character errors
and applies the rule proposed in E9 (R2, parameters fixed there).

Items: the 180 items of E9's validation set (60 English word problems, 60 Korean word
problems, 60 Korean text items without numbers).
Questions: every registered item copied in full, 3 damaged copies per error rate;
720 practice problems, 1 damaged copy per error rate.
Error model: each non-space character is damaged with probability p. Of the damaged
characters 60% are replaced by a similar one (Hangul: another final consonant or vowel;
digit: another digit; letter: another letter; circled digit: another circled digit),
20% are dropped and 20% are doubled.
Baseline: p = 0 must give E9's decisions for undamaged copies.
Arms: rule R2 with E9's values, and rule R3 with the values E14 chose (E9.R3_VALUES),
on the same damaged copies.

    python e10_reading_errors.py          # about half a minute
"""
import json, sys
import numpy as np
import e9_korean_text_items as E9

RATES = [0.0, 0.01, 0.02, 0.05, 0.10, 0.15, 0.20]
SEED, COPIES = 20261121, 3


def damage_char(c, r):
    o = ord(c)
    if 0xAC00 <= o <= 0xD7A3:                               # Hangul syllable = 588*initial + 28*vowel + final
        k = o - 0xAC00
        ini, vow, fin = k // 588, (k % 588) // 28, k % 28
        if r.random() < 0.5:
            fin = int(r.choice([x for x in range(28) if x != fin]))
        else:
            vow = int(r.choice([x for x in range(21) if x != vow]))
        return chr(0xAC00 + ini * 588 + vow * 28 + fin)
    if c.isdigit() and c.isascii():
        return str(r.choice([d for d in "0123456789" if d != c]))
    if c in E9.MARKS:
        return str(r.choice([m for m in E9.MARKS if m != c]))
    if c.isascii() and c.isalpha():
        pool = "abcdefghijklmnopqrstuvwxyz"
        n = str(r.choice([x for x in pool if x != c.lower()]))
        return n.upper() if c.isupper() else n
    return ""


def damage(text, p, r):
    out = []
    for c in text:
        if c.isspace() or r.random() >= p:
            out.append(c); continue
        u = r.random()
        out.append(damage_char(c, r) if u < 0.6 else "" if u < 0.8 else c + c)
    return "".join(out)


def main():
    out_path = sys.argv[1] if len(sys.argv) > 1 else "E10-001_results.json"
    e9 = json.load(open("../results/E9-001_results.json"))
    th_t = e9["share_text_chosen"]
    items, stems, qs, _ = E9.build(E9.SEED_VALIDATE)
    reg = E9.Registry(items, stems)
    group = lambda i: ("EN", "KN", "KT")[i // 60]
    practice = [(g, q) for g, k, _, q in qs if k == "practice"]
    r = np.random.default_rng(SEED)
    out = dict(experiment="E10-001", seed=SEED, share_text=th_t, min_pieces_text=E9.M_MIN, r3=E9.R3_VALUES, r5=E9.R5_VALUES, rates=RATES,
               copies_per_item=COPIES, by_rate={})
    base_ok = all(reg.r2(t, E9.M_MIN, th_t)[:2] == (True, i) for i, t in enumerate(items))
    out["baseline_undamaged_copies_all_refused"] = base_ok
    print("baseline: undamaged copies all refused with their own item:", base_ok)
    for p in RATES:
        hit = {g: [] for g in ("EN", "KN", "KT")}
        hit3 = {g: [] for g in ("EN", "KN", "KT")}
        hit5 = {g: [] for g in ("EN", "KN", "KT")}
        num_fail = {g: 0 for g in ("EN", "KN")}
        for i, t in enumerate(items):
            for _ in range(COPIES):
                d = damage(t, p, r)
                h, j, s = reg.r2(d, E9.M_MIN, th_t)
                hit[group(i)].append(h and j == i)
                h3, j3, _ = reg.r3(d)
                hit3[group(i)].append(h3 and j3 == i)
                h5, j5, _ = reg.r5(d)
                hit5[group(i)].append(h5 and j5 == i)
                if not h and i < 120 and s >= E9.TH:
                    num_fail[group(i)] += 1                 # enough pieces matched, numbers did not
        fp = {g: 0 for g in ("EN", "KN", "KT")}
        fp3 = {g: 0 for g in ("EN", "KN", "KT")}
        fp5 = {g: 0 for g in ("EN", "KN", "KT")}
        for g, q in practice:
            d = damage(q, p, r)
            fp[g] += reg.r2(d, E9.M_MIN, th_t)[0]
            fp3[g] += reg.r3(d)[0]
            fp5[g] += reg.r5(d)[0]
        out["by_rate"][str(p)] = dict(
            copies_refused={g: round(float(np.mean(v)), 4) for g, v in hit.items()},
            copies_refused_R3={g: round(float(np.mean(v)), 4) for g, v in hit3.items()},
            practice_refused_R3={g: int(v) for g, v in fp3.items()},
            copies_refused_R5={g: round(float(np.mean(v)), 4) for g, v in hit5.items()},
            practice_refused_R5={g: int(v) for g, v in fp5.items()},
            missed_because_of_numbers_only={g: round(num_fail[g] / (60 * COPIES), 4) for g in num_fail},
            practice_refused={g: int(v) for g, v in fp.items()}, practice_of=240)
        e = out["by_rate"][str(p)]
        print(f"p={p:4.0%}  refused EN {e['copies_refused']['EN']:.3f}  KN {e['copies_refused']['KN']:.3f}  KT {e['copies_refused']['KT']:.3f}"
              f"   missed on numbers only EN {e['missed_because_of_numbers_only']['EN']:.3f} KN {e['missed_because_of_numbers_only']['KN']:.3f}"
              f"   practice refused {sum(e['practice_refused'].values())}/720"
              f"   | R3: KT {e['copies_refused_R3']['KT']:.3f}, practice {sum(e['practice_refused_R3'].values())}/720"
              f"   | R5: EN {e['copies_refused_R5']['EN']:.3f} KN {e['copies_refused_R5']['KN']:.3f} KT {e['copies_refused_R5']['KT']:.3f}, practice {sum(e['practice_refused_R5'].values())}/720")
    out["example"] = dict(original=items[120][:80], damaged_5_percent=damage(items[120][:80], 0.05, np.random.default_rng(1)))
    json.dump(out, open(out_path, "w"), indent=1, ensure_ascii=False)


if __name__ == "__main__":
    main()
