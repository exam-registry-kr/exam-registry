"""E11: can someone inside a cooperating AI service learn the exam questions in advance?

A service receives the encrypted piece values of every registered item, F_k(piece), and
it may ask the authority to evaluate F_k on any piece (that is how every lookup works).
So an insider can guess a piece, have it evaluated, and see whether the value is in an
item's set. With enough guesses the item could be rebuilt before the exam.

Attacker (worst case on purpose): knows the exact generator of the exam items, i.e. all
templates, names, objects, stems, sentence frames, topics and nouns, and only lacks the
values that were drawn. Real exam writers do not publish their templates, so a real
attacker is weaker than this one.

Items: the 120 Korean items of E9's validation set (60 word problems with numbers, 60
multiple-choice text items without numbers).

Measured, per item
  - recovered numbers: every number token "#n" (with repetitions) for n = 0..999
  - full reconstruction: the attacker builds every text the generator could produce
    with the recovered numbers and keeps the one whose pieces are all in the item's set
    (word problems), or keeps every stem, sentence and choice whose pieces are all in the
    set (text items)
  - cost: how many distinct pieces the attacker had to have evaluated

Equivalence: F_k is deterministic, so testing a guessed piece against the encrypted set
gives the same answer as testing the plain piece against the plain set. This is checked
directly with the P-256 lookup of E7 on a sample of guesses.

Defence compared: the authority sends the sets locked (AES-256-GCM) a day before and
releases the 32-byte key only at the start of the exam. Before the start the insider
holds ciphertext only. The script checks that nothing matches before the key is released
and that the sets open to exactly the same values afterwards.

    python e11_insider_guessing.py          # about one minute
"""
import itertools, json, os, re, secrets, sys, time
import numpy as np
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
import e7_oprf_lookup as O7
import e9_korean_text_items as E9
from e7_oprf_lookup import pieces
from e8_registry_scale import numbers_count

NUM_MAX = 1000
SAMPLE_OPRF = 2000


def grams(text):
    return pieces(E9.nk(text))[0]


def kn_candidates(nums):
    """Every word problem the generator can write with these numbers (any order)."""
    vals = sorted({int(n.split("*")[0][1:]) for n in nums})
    out = []
    for ti, tpl in enumerate(E9.KN_TEMPLATES):
        need = len(set(re.findall(r"\{([xyz])\}", tpl)))
        for combo in itertools.product(vals, repeat=need) if vals else []:
            xyz = dict(zip("xyz", combo + (0,) * (3 - need)))
            for a, b in itertools.permutations(E9.NAMES, 2):
                if "{a}" not in tpl and a != E9.NAMES[0]:
                    continue
                if "{b}" not in tpl and b != E9.NAMES[1]:
                    continue
                for it in E9.THINGS if "{it}" in tpl else E9.THINGS[:1]:
                    out.append(tpl.format(a=a, b=b, it=it, **xyz))
    return out


def kt_parts():
    """Every stem, passage sentence and marked choice the generator can write."""
    parts = list(E9.STEMS)
    for topic in E9.TOPICS:
        for a, b in itertools.permutations(E9.NOUNS, 2):
            parts += [f.format(T=topic, A=a, B=b) for f in E9.FRAMES]
            parts += [f"{m} {c.format(T=topic, A=a, B=b)}" for m in E9.MARKS for c in E9.CHOICES]
    return parts


def main():
    out_path = sys.argv[1] if len(sys.argv) > 1 else "E11-001_results.json"
    items, stems, qs, _ = E9.build(E9.SEED_VALIDATE)
    kn, kt = items[60:120], items[120:180]
    S = [(grams(t), numbers_count(E9.nk(t))) for t in kn + kt]
    out = dict(experiment="E11-001", attacker="knows the item generator (templates and vocabulary), not the drawn values",
               n_items=dict(KN=60, KT=60))

    # 1. numbers
    num_guesses = [f"#{n}" + ("" if j == 1 else f"*{j}") for n in range(NUM_MAX) for j in (1, 2, 3)]
    rec_nums = [{g for g in num_guesses if g in s[1]} for s in S]
    out["numbers"] = dict(guesses=len(num_guesses),
                          items_with_all_numbers_recovered=sum(r == s[1] for r, s in zip(rec_nums, S)), of=len(S))

    # 2. word problems: rebuild full text
    t0 = time.perf_counter()
    kn_guessed, kn_full, kn_examples = set(), 0, []
    for i, t in enumerate(kn):
        g_i = S[i][0]
        hit = None
        for c in kn_candidates(rec_nums[i]):
            cg = grams(c)
            kn_guessed |= cg
            if hit is None and cg <= g_i and numbers_count(E9.nk(c)) == S[i][1]:
                hit = c
        kn_full += hit is not None and grams(hit) == g_i
        if i < 2:
            kn_examples.append(dict(original=t, rebuilt=hit))
    out["word_problems"] = dict(rebuilt_exactly=kn_full, of=60, distinct_pieces_guessed=len(kn_guessed),
                                seconds=round(time.perf_counter() - t0, 1), examples=kn_examples)
    print(f"word problems: {kn_full}/60 rebuilt, {len(kn_guessed):,} pieces guessed")

    # 3. text items: recover stems, sentences and choices
    t0 = time.perf_counter()
    parts = kt_parts()
    part_grams = [grams(p) for p in parts]
    kt_guessed = set().union(*part_grams)
    kt_rows = []
    for j, t in enumerate(kt):
        g_j = S[60 + j][0]
        found = [p for p, pg in zip(parts, part_grams) if pg and pg <= g_j]
        true_parts = [s for s in re.split(r"(?<=[.?])\s+(?=[^①②③④⑤])|\s(?=[①②③④⑤])", t) if s]
        got = sum(any(E9.nk(tp).strip() == E9.nk(f).strip() for f in found) for tp in true_parts)
        cover = len(set().union(*[grams(f) for f in found]) & g_j) / len(g_j) if found else 0.0
        kt_rows.append(dict(parts=len(true_parts), recovered=got, pieces_covered=round(cover, 4), extra=len(found) - got))
    out["text_items"] = dict(
        all_parts_recovered=sum(r["recovered"] == r["parts"] for r in kt_rows), of=60,
        parts_recovered=sum(r["recovered"] for r in kt_rows), parts_total=sum(r["parts"] for r in kt_rows),
        mean_pieces_covered=round(float(np.mean([r["pieces_covered"] for r in kt_rows])), 4),
        candidates_tested=len(parts), distinct_pieces_guessed=len(kt_guessed),
        seconds=round(time.perf_counter() - t0, 1), rows=kt_rows)
    print(f"text items: all parts recovered for {out['text_items']['all_parts_recovered']}/60,"
          f" {len(kt_guessed):,} pieces guessed")

    # cost in terms of ordinary traffic
    per_query = float(np.mean([len(grams(q[3])) for q in qs if q[0] != "EN"]))
    total = len(num_guesses) + len(kn_guessed) + len(kt_guessed)
    e7 = json.load(open("../results/E7-001_results.json"))
    ms_per_piece = e7["timing"]["authority_ms_per_query_median"] / e7["timing"]["pieces_per_query_median"]
    out["cost"] = dict(distinct_pieces_guessed=total, pieces_per_ordinary_question=round(per_query, 1),
                       same_as_ordinary_questions=round(total / per_query),
                       authority_cpu_minutes=round(total * ms_per_piece / 60000, 1),
                       note="authority time per piece from E7 on one CPU")
    print(f"cost: {total:,} pieces = about {total / per_query:,.0f} ordinary questions,"
          f" {total * ms_per_piece / 60000:.1f} CPU minutes at the authority")

    # 4. encrypted-equivalence check on a sample
    auth = O7.Authority(kn + kt, lambda t: (grams(t), numbers_count(E9.nk(t))))
    rng = np.random.default_rng(1)
    pool = sorted(kn_guessed | kt_guessed)
    sample = [pool[i] for i in rng.choice(len(pool), SAMPLE_OPRF, replace=False)]
    sample += [x for x in sorted(S[0][0])[:50]] + [x for x in sorted(S[60][0])[:50]]
    same = 0
    for x in sample:
        fx = O7.oprf(auth, [x])
        enc = [bool(fx & pg) for pg, _ in auth.published]
        plain = [x in s[0] for s in S]
        same += enc == plain
    out["encrypted_equivalence"] = dict(identical=same, total=len(sample))
    print(f"encrypted check: {same}/{len(sample)} guesses give the same answer for every item")

    # 5. defence: locked distribution, key released at the start
    key = AESGCM.generate_key(256)
    blob = json.dumps([[sorted(g), sorted(n)] for g, n in auth.published]).encode()
    nonce = os.urandom(12)
    locked = AESGCM(key).encrypt(nonce, blob, b"exam-set")
    hits_before = 0
    for x in sample[:200]:                       # the insider guesses, but has only ciphertext to compare with
        fx = O7.oprf(auth, [x])
        hits_before += any(v in locked.hex() for v in fx)
    opened = json.loads(AESGCM(key).decrypt(nonce, locked, b"exam-set"))
    same_after = all(set(a) == g and set(b) == n for (a, b), (g, n) in zip(opened, auth.published))
    out["locked_distribution"] = dict(
        guesses_matched_before_start=hits_before, guesses_tried=200,
        sets_identical_after_key_release=same_after, ciphertext_bytes=len(locked), key_bytes=len(key))
    print(f"locked sets: {hits_before}/200 guesses matched before the start; identical after release: {same_after}")
    json.dump(out, open(out_path, "w"), indent=1, ensure_ascii=False)


if __name__ == "__main__":
    main()
