"""E12: can a user get around the lookup by sending a question in several parts?

Each part alone may have too few matching pieces to be refused. A service can judge the
last few messages of the same conversation together. This experiment measures both, and
checks that judging messages together does not refuse ordinary study conversations.

Items and rule: E9's validation set (60 English word problems, 60 Korean word problems,
60 Korean text items) and E9's proposed rule (R2) with its fixed parameters; as a second arm,
rule R3 with the values E14 chose (E9.R3_VALUES).

Attacks on every registered item
  verbatim      : the item is cut into k consecutive word chunks (k = 2, 4, 8), one per
                  message
  numbers apart : every number is replaced by a letter (A, B, C, ...), the text is cut
                  into k chunks (k = 1, 2, 4, 8) and the values follow in a last message
                  ("A=168, B=75, C=4")
The service judges each message alone (m = 1), or the last m messages of the
conversation joined (m = 2, 4), or the whole conversation during the exam (m = all).
Second arm ("resolve"): before judging joined messages the service puts values given as
"A=168" back in place of the letter, a plain text substitution with no understanding of
the problem.
Ordinary conversations that must NOT be refused: 600 conversations of 4 messages, made
of practice problems of the same templates (the hardest case: a student working
through similar problems one after another), and 600 conversations that mix practice
problems with stems and short follow-up questions.

    python e12_split_questions.py          # about one minute
"""
import json, sys
import numpy as np
import e9_korean_text_items as E9

ATTACKS = [("verbatim", 2), ("verbatim", 4), ("verbatim", 8), ("numbers_apart", 1), ("numbers_apart", 2),
           ("numbers_apart", 4), ("numbers_apart", 8)]
MS = [1, 2, 4, 99]
SEED = 20261122
FOLLOW = ["이 문제 풀이 과정을 단계별로 설명해 줘.", "답이 왜 그렇게 나오는지 모르겠어.", "비슷한 문제를 하나 더 내 줘.",
          "Can you explain the second step again?", "이 개념을 쉽게 설명해 줄래?", "다른 풀이 방법도 있어?"]


def chunks(text, k):
    w = text.split()
    cuts = np.linspace(0, len(w), k + 1).astype(int)
    return [" ".join(w[cuts[i]:cuts[i + 1]]) for i in range(k)]


def numbers_apart(text, k):
    import re
    vals, letters = [], iter("ABCDEFGHIJKLMNOP")
    def sub(mo):
        vals.append(mo.group(0))
        return next(letters)
    body = re.sub(r"\d+(?:\.\d+)?", sub, text)
    tail = ", ".join(f"{chr(65 + i)}={v}" for i, v in enumerate(vals))
    return chunks(body, k) + ([tail] if vals else [])


def resolve(text):
    """Put values given as 'A=168' back in place of the letter A."""
    import re
    pairs = dict(re.findall(r"\b([A-Z])\s*=\s*(\d+(?:\.\d+)?)", text))
    if not pairs:
        return text
    text = re.sub(r"\b[A-Z]\s*=\s*\d+(?:\.\d+)?,?", " ", text)
    return re.sub(r"(?<![A-Za-z])([A-Z])(?![A-Za-z])", lambda mo: pairs.get(mo.group(1), mo.group(1)), text)


def conversation_refused(reg, msgs, m, th, fix=False, r3=False, r5=False):
    """Refused if, at any message, the last m messages (joined) are refused."""
    for i in range(len(msgs)):
        joined = " ".join(msgs[max(0, i - m + 1):i + 1])
        q = resolve(joined) if fix else joined
        hit = (reg.r5(q) if r5 else reg.r3(q) if r3 else reg.r2(q, E9.M_MIN, th))[0]
        if hit:
            return True
    return False


def main():
    out_path = sys.argv[1] if len(sys.argv) > 1 else "E12-001_results.json"
    th = json.load(open("../results/E9-001_results.json"))["share_text_chosen"]
    items, stems, qs, _ = E9.build(E9.SEED_VALIDATE)
    reg = E9.Registry(items, stems)
    group = lambda i: ("EN", "KN", "KT")[i // 60]
    rng = np.random.default_rng(SEED)
    out = dict(experiment="E12-001", share_text=th, min_pieces_text=E9.M_MIN, r3=E9.R3_VALUES,
               last_m_messages=["1", "2", "4", "all"], attack={}, attack_R3={}, attack_R5={}, ordinary={}, ordinary_R3={}, ordinary_R5={}, r5=E9.R5_VALUES)
    mname = lambda m: "all" if m == 99 else str(m)
    for kind, k in ATTACKS:
        for fix in (False, True):
            res = {}
            for m in MS:
                ok = {g: [] for g in ("EN", "KN", "KT")}
                for i, t in enumerate(items):
                    msgs = chunks(t, k) if kind == "verbatim" else numbers_apart(t, k)
                    ok[group(i)].append(conversation_refused(reg, msgs, m, th, fix))
                res[mname(m)] = {g: round(float(np.mean(v)), 4) for g, v in ok.items()}
            out["attack"][f"{kind}_{k}" + ("_resolve" if fix else "")] = res
            print(f"{kind:13s} k={k} {'resolve' if fix else 'plain  '}: " + "  ".join(f"m={mname(m)}: " + "/".join(f"{res[mname(m)][g]:.0%}" for g in ("EN", "KN", "KT")) for m in MS))
            res3 = {}
            for m in MS:
                ok = {g: [] for g in ("EN", "KN", "KT")}
                for i, t in enumerate(items):
                    msgs = chunks(t, k) if kind == "verbatim" else numbers_apart(t, k)
                    ok[group(i)].append(conversation_refused(reg, msgs, m, th, fix, r3=True))
                res3[mname(m)] = {g: round(float(np.mean(v)), 4) for g, v in ok.items()}
            out["attack_R3"][f"{kind}_{k}" + ("_resolve" if fix else "")] = res3
            res5 = {}
            for m in MS:
                ok = {g: [] for g in ("EN", "KN", "KT")}
                for i, t in enumerate(items):
                    msgs = chunks(t, k) if kind == "verbatim" else numbers_apart(t, k)
                    ok[group(i)].append(conversation_refused(reg, msgs, m, th, fix, r5=True))
                res5[mname(m)] = {g: round(float(np.mean(v)), 4) for g, v in ok.items()}
            out["attack_R5"][f"{kind}_{k}" + ("_resolve" if fix else "")] = res5

    practice = {g: [q[3] for q in qs if q[0] == g and q[1] == "practice"] for g in ("EN", "KN", "KT")}
    convs_same, convs_mixed = [], []
    for _ in range(600):
        g = ("EN", "KN", "KT")[int(rng.integers(0, 3))]
        convs_same.append([practice[g][int(j)] for j in rng.choice(240, 4, replace=False)])
        mixed = []
        for _ in range(4):
            u = rng.random()
            if u < 0.5:
                gg = ("EN", "KN", "KT")[int(rng.integers(0, 3))]
                mixed.append(practice[gg][int(rng.integers(0, 240))])
            elif u < 0.75:
                mixed.append(E9.STEMS[int(rng.integers(0, 10))])
            else:
                mixed.append(FOLLOW[int(rng.integers(0, len(FOLLOW)))])
        convs_mixed.append(mixed)
    for name, convs in (("same_template_practice", convs_same), ("mixed_study", convs_mixed)):
        out["ordinary"][name] = {mname(m): int(sum(conversation_refused(reg, c, m, th, True) for c in convs)) for m in MS} | {"of": len(convs)}
        out["ordinary_R3"][name] = {mname(m): int(sum(conversation_refused(reg, c, m, th, True, r3=True) for c in convs)) for m in MS} | {"of": len(convs)}
        out["ordinary_R5"][name] = {mname(m): int(sum(conversation_refused(reg, c, m, th, True, r5=True) for c in convs)) for m in MS} | {"of": len(convs)}
        print(f"ordinary {name}: refused " + ", ".join(f"m={mname(m)}: {out['ordinary'][name][mname(m)]}" for m in MS) + f" of {len(convs)}")
    for key in ("numbers_apart_8", "numbers_apart_8_resolve"):
        print("R5", key, out["attack_R5"][key])
    print("R5 ordinary", out["ordinary_R5"])
    json.dump(out, open(out_path, "w"), indent=1, ensure_ascii=False)


if __name__ == "__main__":
    main()
