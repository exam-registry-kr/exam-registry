"""E15: what can the lookup server learn from what it does see?

The encrypted lookup hides every piece of a question from the lookup server (RFC 9497:
each blinded element is a uniformly random point). The server still sees how many
elements arrive per question, when, and from which service. This experiment measures
what the element count alone gives away, and what hiding it costs.

Observer: the lookup server. Worst case on purpose: it knows every registered item and
the generators of the rewrites, and has already seen a labelled half of the questions.
Guesses from the count of one question
  item        which registered item a must-refuse question is about (chance: 1 in 180)
  exam or not whether a question is about a registered item or an ordinary one (0.5 = no
              better than a coin; reported as area under the curve)
Arms
  none        the service sends exactly the question's elements (comparison arm)
  pad_32/64/128  dummy elements are added up to the next multiple of 32, 64, 128
  fixed_512   every question is sent as 512 elements (longer ones in several blocks of 512)
  batch_4/16  the service sends 4 or 16 questions of different users as one request
Cost: elements the server must process per real element (multiplies the load of E13).
Not hidden by any arm: the number of requests per service and their times.

Items and questions: E16's confirm set (E9's rewrites, E14's short copies, practice
problems, parts of practice problems, reworded practice problems).

    python e15_lookup_metadata.py          # under a minute
"""
import json, math, sys
import numpy as np
import e9_korean_text_items as E9
import e14_sensitivity as E14
import e16_baselines as E16
from e8_registry_scale import numbers_count

SEED = 20261127
OLD = ("format", "numbers", "reorder", "partial", "synonym", "combined", "typed_marks", "no_choices", "passage_only", "short_copy")
ORDINARY = ("practice", "short_practice", "reworded_practice")


def elements(q):
    t = E9.nk(q)
    return len(E9.pieces(t)[0]) + len(numbers_count(t))


def auc(pos, neg):
    allv = np.concatenate([pos, neg]); order = allv.argsort(kind="mergesort")
    ranks = np.empty(len(allv)); ranks[order] = np.arange(1, len(allv) + 1)
    for v in np.unique(allv):                      # average ranks of ties
        m = allv == v; ranks[m] = ranks[m].mean()
    a = (ranks[:len(pos)].sum() - len(pos) * (len(pos) + 1) / 2) / (len(pos) * len(neg))
    return max(a, 1 - a)


def nearest(train_o, train_y, o):
    j = np.abs(train_o - o).argmin()
    return train_y[j]


def main():
    out_path = sys.argv[1] if len(sys.argv) > 1 else "E15-001_results.json"
    items, stems, qs, _ = E16.build(E14.SEED_CONFIRM)
    r = np.random.default_rng(SEED)
    exam = [(elements(q), qi) for g, k, qi, q in qs if k in OLD]
    ordinary = [elements(q) for g, k, qi, q in qs if k in ORDINARY]
    n = np.array([e for e, _ in exam]); y = np.array([i for _, i in exam]); o = np.array(ordinary)
    half = r.permutation(len(n)); tr, te = half[:len(n) // 2], half[len(n) // 2:]
    arms = {"none": lambda x: x}
    for b in (32, 64, 128):
        arms[f"pad_{b}"] = lambda x, b=b: np.ceil(x / b) * b
    arms["fixed_512"] = lambda x: np.ceil(x / 512) * 512
    out = dict(experiment="E15-001", seed=SEED, registered_items=len(items), must_refuse_questions=len(n), ordinary_questions=len(o),
               elements_per_question=dict(median=float(np.median(np.concatenate([n, o]))), max=int(max(n.max(), o.max()))),
               chance_item=round(1 / len(items), 4), arms={})
    for name, f in arms.items():
        a, b = f(n), f(o)
        acc = float(np.mean([nearest(a[tr], y[tr], v) == t for v, t in zip(a[te], y[te])]))
        out["arms"][name] = dict(item_guess_accuracy=round(acc, 4), exam_or_not_auc=round(float(auc(a, b)), 4),
                                 distinct_values_seen=int(len(np.unique(np.concatenate([a, b])))),
                                 elements_per_real_element=round(float((a.sum() + b.sum()) / (n.sum() + o.sum())), 3))
    allq = np.concatenate([n, o]); is_exam = np.concatenate([np.ones(len(n)), np.zeros(len(o))])
    for bsz in (4, 16):
        def batches(idx, m):
            other = r.integers(0, len(allq), (m, bsz - 1))
            return allq[other].sum(1)
        a_tr = n[tr] + batches(tr, len(tr)); a_te = n[te] + batches(te, len(te))
        acc = float(np.mean([nearest(a_tr, y[tr], v) == t for v, t in zip(a_te, y[te])]))
        pos = n + batches(None, len(n)); neg = o + batches(None, len(o))
        out["arms"][f"batch_{bsz}"] = dict(item_guess_accuracy=round(acc, 4), exam_or_not_auc=round(float(auc(pos, neg)), 4),
                                           elements_per_real_element=1.0, questions_waiting_for_one_request=bsz,
                                           note="the guess is about one chosen question inside the batch; the others are drawn at random from all questions")
    out["not_hidden"] = "requests per service and their times; a service that wants to hide its volume has to send cover requests at a constant rate"
    json.dump(out, open(out_path, "w"), indent=1, ensure_ascii=False)
    print("elements per question:", out["elements_per_question"], " chance for the item guess:", out["chance_item"])
    for k, v in out["arms"].items():
        print(f"  {k:10s}", v)


if __name__ == "__main__":
    main()
