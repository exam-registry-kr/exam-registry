"""E13: how much load does the lookup put on an exam authority, and how does a service
check its own implementation?

Part 1, load. The authority's only work per question is one elliptic-curve
multiplication per piece (RFC 9497 BlindEvaluate). This measures, on one CPU core:
  - authority: pieces per second, for batches of 1, 70, 1,000 and 10,000 pieces, with
    this repository's RFC 9497 implementation (rfc9497.py) and, as the cost an optimized
    implementation would have, one bare OpenSSL scalar multiplication per piece
  - service:   time to blind and unblind the pieces of one question
  - how many questions per second one core can serve, at the median piece count of
    E9's Korean questions and of E7's English questions
It then states how many cores are needed for a stated question rate. The rate is an
assumption written in the output, not a measurement.

Part 2, test vectors. A fixed public test key (never used for a real exam), derived with
RFC 9497 DeriveKeyPair from a published seed, gives fixed encrypted piece values (RFC 9497
OPRF outputs), so a service can check, value by value, that its pieces, number
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
import rfc9497 as R
from e7_oprf_lookup import pieces
from e8_registry_scale import numbers_count

TEST_SEED = hashlib.sha256(b"exam-registry public test key, never for a real exam").digest()
TEST_INFO = b"exam-registry test vectors v2"   # the key is unchanged in v3 of the vectors; only the rule and the queries changed
TEST_KEY = R.derive_key_pair(TEST_SEED, TEST_INFO)
ASSUMED_QPS = 1000           # assumption for the sizing line only
BATCHES = [1, 70, 1000, 10000]
VECTOR_PATH = "../results/E13-test_vectors.json"


def F(k, x):
    return R.evaluate(k, x.encode()).hex()


def load_test():
    key = ec.derive_private_key(TEST_KEY, O7.CURVE)
    rng = np.random.default_rng(1)
    xs = [f"조각{i:05d}".encode() for i in range(max(BATCHES))]
    blinded = [R.blind(x, int(r) + 1)[1] for x, r in zip(xs, rng.integers(1, 2**62, len(xs)))]
    pubs = [ec.EllipticCurvePublicKey.from_encoded_point(O7.CURVE, b) for b in blinded]
    auth, bare = {}, {}
    for b in BATCHES:
        reps = max(1, 2000 // b)
        t = time.perf_counter()
        for i in range(reps):
            for bx in blinded[:b]:
                R.blind_evaluate(TEST_KEY, bx)
        dt = (time.perf_counter() - t) / (reps * b)
        auth[str(b)] = dict(us_per_piece=round(dt * 1e6, 1), pieces_per_second=round(1 / dt))
        reps = max(1, 10000 // b)
        t = time.perf_counter()
        for i in range(reps):
            for pk in pubs[:b]:
                key.exchange(ec.ECDH(), pk)
        dt = (time.perf_counter() - t) / (reps * b)
        bare[str(b)] = dict(us_per_piece=round(dt * 1e6, 1), pieces_per_second=round(1 / dt))
    # service side for one question
    items, stems, qs, _ = E9.build(E9.SEED_VALIDATE)
    ko = [len(pieces(E9.nk(q[3]))[0]) for q in qs if q[0] in ("KN", "KT")]
    en = [len(pieces(q[3])[0]) for q in qs if q[0] == "EN"]
    sample = [q[3] for q in qs if q[0] == "KT"][:50]
    svc = []
    for q in sample:
        g = [x.encode() for x in sorted(pieces(E9.nk(q))[0])]
        t = time.perf_counter()
        bl = [R.blind(x) for x in g]
        t_mid = time.perf_counter()
        ev = [R.blind_evaluate(TEST_KEY, b) for _, b in bl]          # stands in for the authority, not timed
        t_fin = time.perf_counter()
        _ = [R.finalize(x, r, e) for x, (r, _), e in zip(g, bl, ev)]
        t_end = time.perf_counter()
        svc.append((t_mid - t + t_end - t_fin) * 1000)
    per, per_bare = auth["1000"]["pieces_per_second"], bare["1000"]["pieces_per_second"]
    ko_med, en_med = statistics.median(ko), statistics.median(en)
    return dict(
        cpu="one core of the machine that ran this script",
        authority=auth, authority_bare_scalar_multiplication=bare,
        pieces_per_question_median=dict(korean=ko_med, english=en_med),
        questions_per_second_per_core=dict(korean=round(per / ko_med, 1), english=round(per / en_med, 1)),
        questions_per_second_per_core_bare=dict(korean=round(per_bare / ko_med, 1), english=round(per_bare / en_med, 1)),
        service_ms_per_korean_question_median=round(statistics.median(svc), 1),
        sizing=dict(assumed_questions_per_second=ASSUMED_QPS,
                    cores_needed_korean=int(np.ceil(ASSUMED_QPS / (per / ko_med))),
                    cores_needed_korean_bare=int(np.ceil(ASSUMED_QPS / (per_bare / ko_med))),
                    note="assumption, not a measurement: questions per second sent to one authority during an exam"))


def vectors():
    items = ["어떤 수에 6을 곱한 후 59를 더하면 197이다. 이 수를 구하시오.",
             "첫째항이 68이고 공비가 68인 등비수열의 첫째항부터 제5항까지의 합을 구하시오.",
             E9.make_kt(0, np.random.default_rng(7))[0]]
    stems = ["", "", E9.STEMS[0]]
    queries = [items[0], items[0].replace(" ", ""), "어떤 수에 5를 곱한 후 21을 더하면 96이다. 이 수를 구하시오.",
               "첫째항이 68이고 공비가 3인 등비수열의 첫째항부터 제5항까지의 합을 구하시오.", items[2],
               E9.STEMS[0], items[2].replace("①", "1)").replace("②", "2)").replace("③", "3)").replace("④", "4)").replace("⑤", "5)"),
               "문제 23번 " + items[0], "문제 23번 " + items[2],
               "오늘은 날씨가 맑아서 강가를 따라 오래 걸었다. 저녁에는 동생과 함께 시장에 들러 반찬거리를 샀다. 주말에는 미뤄 둔 방 정리를 끝낼 생각이다. " + items[1],
               "문제 23번 어떤 수에 5를 곱한 후 21을 더하면 96이다. 이 수를 구하시오."]
    reg = E9.Registry(items, stems)
    out = dict(note="public test key; the values only check an implementation and never protect a real exam",
               standard="RFC 9497 OPRF(P-256, SHA-256), mode 0x00; hash_to_curve P256_XMD:SHA-256_SSWU_RO_ (RFC 9380)",
               test_key_derivation=dict(seed_hex=TEST_SEED.hex(), info=TEST_INFO.decode(), method="RFC 9497 DeriveKeyPair"),
               test_key_hex=R.serialize_scalar(TEST_KEY).hex(),
               F="RFC 9497 Finalize output (32 bytes, hex) for the piece in UTF-8",
               normalisation="Unicode NFKC, lower case, commas removed; pieces drop whitespace and . , ? ! · ~ \" ' ( )",
               rule=dict(name="R5", numeric_share=O7.TH, text=E9.R3_VALUES,
                         text_floor="min(cap, ceil(frac x pieces of the matched item outside the stems))",
                         coverage=E9.R5_VALUES,
                         summary="refuse if (1) the question has a number other than 1 to 5, its best item has one too, the share is at least "
                                 "numeric_share and the question's numbers are all in the item or the item's numbers are all in the question; or "
                                 "(2) otherwise, pieces outside the stems: matched >= text_floor and share >= text.share; or (3) coverage: a run of "
                                 "sentences that each have at least `keep` of their pieces in the item, no longer than span x the item, holds at "
                                 "least C of the item's pieces (and all its numbers if it has a number other than 1 to 5). "
                                 "score: 1.0 if refused by (1) or (2), else the coverage found"), items=[], queries=[])
    for t, s in zip(items, stems):
        g, n = pieces(E9.nk(t))[0], numbers_count(E9.nk(t))
        out["items"].append(dict(text=t, stem=s, pieces={x: F(TEST_KEY, x) for x in sorted(g)},
                                 numbers={x: F(TEST_KEY, x) for x in sorted(n)},
                                 stem_pieces=sorted(F(TEST_KEY, x) for x in pieces(E9.nk(s))[0]) if s else []))
    for q in queries:
        hit, i, score = reg.r5(q)
        r3 = bool(reg.r3(q)[0])
        out["queries"].append(dict(text=q, pieces=sorted(pieces(E9.nk(q))[0]), numbers=sorted(numbers_count(E9.nk(q))),
                                   has_number_other_than_1_to_5=E9.strong_number(q),
                                   refuse=bool(hit), matched_item=i if hit else None, score=round(score, 4), refused_by_R3=r3))
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
        w = load["authority_bare_scalar_multiplication"][b]
        print(f"authority, batch {b:>5}: {v['us_per_piece']} us per piece ({v['pieces_per_second']:,}/s); bare OpenSSL {w['us_per_piece']} us")
    print("questions per second per core:", load["questions_per_second_per_core"], "bare:", load["questions_per_second_per_core_bare"],
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
