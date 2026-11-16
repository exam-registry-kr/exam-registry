"""E17: what still works when the lookup server is down during an exam?

A cooperating service holds the encrypted piece values of every item (opened at the start
of the exam). To judge a question it needs the encrypted value of each of the question's
pieces, and only the lookup server can compute those. If the server stops, the service
cannot evaluate new pieces. Marks printed on the paper (E1, E2, E5) do not use the lookup
and are not affected.

Arms during the outage
  answer_all     the service answers everything (comparison arm)
  refuse_all     the service refuses everything (comparison arm)
  cache          the service has kept the value of every piece it had evaluated before the
                 outage and judges with those alone; a piece it has no value for counts as
                 not matching, a number it has no value for fails the number test
  key_release    the authority publishes this exam's lookup key through the log, and the
                 service computes the values itself. This gives up, for the rest of that
                 exam, the protection measured in E11 (an insider can then test guesses
                 without asking anyone). It requires one lookup key per exam.
Stream: questions arrive one after another; 30% are about a registered item (E9's rewrites
and E14's short copies of a random item), 70% are ordinary (practice problems, parts of
them, reworded practice problems). The outage starts after N questions (N = 0 ... 5000);
the next 2000 questions are judged by each arm. Rule: R3. Items: E16's confirm set.
The cache holds plain pieces here; the encrypted value of a piece is a fixed function of
the piece (checked in E9), so the decisions are the same.

    python e17_outage.py          # about a minute
"""
import json, sys
import numpy as np
import e7_oprf_lookup as O7
import e9_korean_text_items as E9
import e14_sensitivity as E14
import e15_lookup_metadata as E15
import e16_baselines as E16
from e8_registry_scale import numbers_count

SEED = 20261128
BEFORE = [0, 10, 100, 1000, 5000]
DURING = 2000
EXAM_SHARE = 0.3


def main():
    out_path = sys.argv[1] if len(sys.argv) > 1 else "E17-001_results.json"
    items, stems, qs, _ = E16.build(E14.SEED_CONFIRM)
    reg = E9.Registry(items, stems)
    exam = [q for q in qs if q[1] in E15.OLD]
    ordinary = [q for q in qs if q[1] in E15.ORDINARY]
    out = dict(experiment="E17-001", seed=SEED, exam_share=EXAM_SHARE, questions_during_outage=DURING, rule="R5", r5=E9.R5_VALUES, by_questions_before_outage={})

    def draw(r):
        pool = exam if r.random() < EXAM_SHARE else ordinary
        return pool[int(r.integers(0, len(pool)))]

    for n0 in BEFORE:
        r = np.random.default_rng(SEED)
        known, asked, new = set(), 0, 0
        for _ in range(n0):
            t = E9.nk(draw(r)[3])
            p = E9.pieces(t)[0] | numbers_count(t)
            asked += len(p); new += len(p - known); known |= p
        res = dict(normal=[], cache=[], cache_only=0, ord_normal=0, ord_cache=0, n_exam=0, n_ord=0, covered=[])
        for _ in range(DURING):
            g, k, qi, q = draw(r)
            full = reg.r5(q)[0]; c = reg.r5(q, known=known)[0]
            t = E9.nk(q); p = E9.pieces(t)[0] | numbers_count(t)
            res["covered"].append(len(p & known) / max(1, len(p)))
            if k in E15.OLD:
                res["n_exam"] += 1; res["normal"].append(full); res["cache"].append(c)
            else:
                res["n_ord"] += 1; res["ord_normal"] += full; res["ord_cache"] += c
            res["cache_only"] += int(c and not full)
        ne, no = res["n_exam"], res["n_ord"]
        out["by_questions_before_outage"][str(n0)] = dict(
            pieces_in_cache=len(known),
            share_of_evaluations_saved_before_outage=round(1 - new / asked, 4) if asked else None,
            share_of_a_question_pieces_in_cache=round(float(np.mean(res["covered"])), 4),
            exam_questions=ne, ordinary_questions=no,
            exam_questions_refused=dict(normal_operation=round(float(np.mean(res["normal"])), 4), answer_all=0.0, refuse_all=1.0,
                                        cache=round(float(np.mean(res["cache"])), 4), key_release=round(float(np.mean(res["normal"])), 4)),
            ordinary_questions_refused=dict(normal_operation=int(res["ord_normal"]), answer_all=0, refuse_all=no, cache=int(res["ord_cache"]),
                                            key_release=int(res["ord_normal"])),
            refused_by_cache_but_not_in_normal_operation=res["cache_only"])
        d = out["by_questions_before_outage"][str(n0)]
        print(f"outage after {n0:5d} questions: cache {d['pieces_in_cache']:6d} pieces, exam questions refused "
              f"normal {d['exam_questions_refused']['normal_operation']:.3f} cache {d['exam_questions_refused']['cache']:.3f}; "
              f"ordinary refused normal {d['ordinary_questions_refused']['normal_operation']} cache {d['ordinary_questions_refused']['cache']} of {no}; "
              f"cache-only refusals {d['refused_by_cache_but_not_in_normal_operation']}; evaluations saved {d['share_of_evaluations_saved_before_outage']}")

    # key release: values computed by the service with the released key equal the authority's values
    auth = O7.Authority(items[:3], lambda t: (E9.pieces(E9.nk(t))[0], numbers_count(E9.nk(t))))
    import rfc9497 as RF
    sample = sorted(E9.pieces(E9.nk(items[0]))[0])[:40]
    out["key_release_check"] = dict(pieces=len(sample), identical=sum(RF.evaluate(auth._k, x.encode()).hex() == auth._F(x) and auth._F(x) in auth.published[0][0] for x in sample))
    print("key release: values computed with the released key equal the published ones:", out["key_release_check"])
    json.dump(out, open(out_path, "w"), indent=1, ensure_ascii=False)


if __name__ == "__main__":
    main()
