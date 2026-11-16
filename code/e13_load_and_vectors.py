"""E13: how much load does the lookup put on an exam authority, and how does a service
check its own implementation?

Part 1, load. The authority's only work per question is one elliptic-curve
multiplication per piece. This measures, on one CPU core of this machine:
  - authority: pieces per second, for batches of 1, 70, 1,000 and 10,000 pieces
  - service:   time to blind and unblind the pieces of one question
  - how many questions per second one core can serve, at the median piece count of
    E9's Korean questions and of E7's English questions
It then states how many cores are needed for a stated question rate. The rate is an
assumption written in the output, not a measurement.

Part 2, test vectors. A fixed public test key (never used for a real exam) gives fixed
encrypted piece values, so a service can check, value by value, that its pieces, number
tokens, hashing and decision rule give the same results as this code. The vectors are
written to results/E13-test_vectors.json; `--check` recomputes and compares them.

    python e13_load_and_vectors.py           # about one minute
    python e13_load_and_vectors.py --check   # recompute the vectors and compare
"""
import hashlib, json, statistics, sys, time
import numpy as np
from cryptography.hazmat.primitives.asymmetric import ec
import e7_oprf_lookup as O7
import e9_korean_text_items as E9
from e7_oprf_lookup import pieces, hash_to_point, mul_x, lift, Np
from e8_registry_scale import numbers_count

TEST_KEY = int.from_bytes(hashlib.sha256(b"exam-registry public test key, never for a real exam").digest(), "big") % (Np - 1) + 1
ASSUMED_QPS = 1000           # assumption for the sizing line only
BATCHES = [1, 70, 1000, 10000]
VECTOR_PATH = "../results/E13-test_vectors.json"


def F(k, x):
    y = mul_x(k, hash_to_point(x))
    return hashlib.sha256(y.to_bytes(32, "big") + x.encode()).hexdigest()


def load_test():
    key = ec.derive_private_key(TEST_KEY, O7.CURVE)
    rng = np.random.default_rng(1)
    xs = [f"조각{i:05d}" for i in range(max(BATCHES))]
    blinded = [mul_x(int(r) + 1, hash_to_point(x)) for x, r in zip(xs, rng.integers(1, 2**62, len(xs)))]
    auth = {}
    for b in BATCHES:
        reps = max(1, 10000 // b)
        t = time.perf_counter()
        for i in range(reps):
            for bx in blinded[:b]:
                key.exchange(ec.ECDH(), lift(bx))
        dt = (time.perf_counter() - t) / (reps * b)
        auth[str(b)] = dict(us_per_piece=round(dt * 1e6, 1), pieces_per_second=round(1 / dt))
    # service side for one question
    items, stems, qs, _ = E9.build(E9.SEED_VALIDATE)
    ko = [len(pieces(E9.nk(q[3]))[0]) for q in qs if q[0] in ("KN", "KT")]
    en = [len(pieces(q[3])[0]) for q in qs if q[0] == "EN"]
    sample = [q[3] for q in qs if q[0] == "KT"][:50]
    svc = []
    for q in sample:
        g = sorted(pieces(E9.nk(q))[0])
        t = time.perf_counter()
        rs = [int(r) for r in rng.integers(1, 2**62, len(g))]
        bl = [mul_x(r, hash_to_point(x)) for x, r in zip(g, rs)]
        ev = [mul_x(TEST_KEY, lift(b)) for b in bl]                      # stands in for the authority
        t_mid = time.perf_counter()
        _ = [mul_x(pow(r, -1, Np), lift(e)) for r, e in zip(rs, ev)]
        t_end = time.perf_counter()
        svc.append((t_mid - t) * 1000 - len(g) * auth["70"]["us_per_piece"] / 1000 + (t_end - t_mid) * 1000)
    per = auth["1000"]["pieces_per_second"]
    ko_med, en_med = statistics.median(ko), statistics.median(en)
    return dict(
        cpu="one core of the machine that ran this script",
        authority=auth,
        pieces_per_question_median=dict(korean=ko_med, english=en_med),
        questions_per_second_per_core=dict(korean=round(per / ko_med, 1), english=round(per / en_med, 1)),
        service_ms_per_korean_question_median=round(statistics.median(svc), 1),
        sizing=dict(assumed_questions_per_second=ASSUMED_QPS,
                    cores_needed_korean=int(np.ceil(ASSUMED_QPS / (per / ko_med))),
                    note="assumption, not a measurement: questions per second sent to one authority during an exam"))


def vectors():
    items = ["어떤 수에 6을 곱한 후 59를 더하면 197이다. 이 수를 구하시오.",
             "첫째항이 68이고 공비가 68인 등비수열의 첫째항부터 제5항까지의 합을 구하시오.",
             E9.make_kt(0, np.random.default_rng(7))[0]]
    stems = ["", "", E9.STEMS[0]]
    queries = [items[0], items[0].replace(" ", ""), "어떤 수에 5를 곱한 후 21을 더하면 96이다. 이 수를 구하시오.",
               "첫째항이 68이고 공비가 3인 등비수열의 첫째항부터 제5항까지의 합을 구하시오.", items[2],
               E9.STEMS[0], items[2].replace("①", "1)").replace("②", "2)").replace("③", "3)").replace("④", "4)").replace("⑤", "5)")]
    reg = E9.Registry(items, stems)
    th = json.load(open("../results/E9-001_results.json"))["share_text_chosen"]
    out = dict(note="public test key; the values only check an implementation and never protect a real exam",
               test_key_hex=f"{TEST_KEY:064x}", hash_to_curve="try-and-increment on P-256 as in e7_oprf_lookup.hash_to_point",
               F="sha256(x-coordinate of k*H(piece), 32 bytes big-endian || piece in UTF-8)",
               normalisation="Unicode NFKC, lower case, commas removed; pieces drop whitespace and . , ? ! · ~ \" ' ( )",
               rule=dict(numeric_share=O7.TH, text_share=th, text_min_pieces=E9.M_MIN), items=[], queries=[])
    for t, s in zip(items, stems):
        g, n = pieces(E9.nk(t))[0], numbers_count(E9.nk(t))
        out["items"].append(dict(text=t, stem=s, pieces={x: F(TEST_KEY, x) for x in sorted(g)},
                                 numbers={x: F(TEST_KEY, x) for x in sorted(n)},
                                 stem_pieces=sorted(F(TEST_KEY, x) for x in pieces(E9.nk(s))[0]) if s else []))
    for q in queries:
        hit, i, score = reg.r2(q, E9.M_MIN, th)
        out["queries"].append(dict(text=q, pieces=sorted(pieces(E9.nk(q))[0]), numbers=sorted(numbers_count(E9.nk(q))),
                                   has_number_other_than_1_to_5=E9.strong_number(q),
                                   refuse=bool(hit), matched_item=i if hit else None, score=round(score, 4)))
    return out


def main():
    if "--check" in sys.argv:
        old, new = json.load(open(VECTOR_PATH)), vectors()
        same = old == new
        print("test vectors identical:", same)
        sys.exit(0 if same else 1)
    out_path = sys.argv[1] if len(sys.argv) > 1 else "E13-001_results.json"
    load = load_test()
    for b, v in load["authority"].items():
        print(f"authority, batch {b:>5}: {v['us_per_piece']} us per piece, {v['pieces_per_second']:,} pieces/s")
    print("questions per second per core:", load["questions_per_second_per_core"],
          " service ms per Korean question:", load["service_ms_per_korean_question_median"])
    print("sizing:", load["sizing"])
    vec = vectors()
    json.dump(vec, open(VECTOR_PATH, "w"), indent=1, ensure_ascii=False)
    print("test vectors:", len(vec["items"]), "items,", len(vec["queries"]), "queries ->", VECTOR_PATH,
          "decisions:", [q["refuse"] for q in vec["queries"]])
    json.dump(dict(experiment="E13-001", load=load, vectors_file="results/E13-test_vectors.json"),
              open(out_path, "w"), indent=1, ensure_ascii=False)


if __name__ == "__main__":
    main()
