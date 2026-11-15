"""E3: text-path registry matching, exact hash vs character n-gram similarity.

Registered items: 60 exam-style word problems generated from 12 templates with
random entities and numbers. Positive queries: each registered item after an
automatic rewrite (format noise, number reformatting, clause reordering, partial
copy, synonym substitution, and all of these combined). Negative queries: problems
from the SAME templates with different numbers and entities, i.e. the kind of
practice problem a student studies, which must not be refused.

Matchers
  exact   : SHA-256 of a normalized string (lowercase, collapsed whitespace)
  ngram   : TF-IDF over character 4-grams, cosine >= threshold
  ngram+num: ngram AND the multiset of numbers in the query is contained in the
            registered item's numbers (numbers carry the identity of a problem)
"""
import hashlib, json, re, sys
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer

rng = np.random.default_rng(20261117)
NAMES = ["Minji", "Junho", "Sora", "Hyun", "Daeun", "Taeyang", "Yerin", "Jisoo"]
ITEMS = ["apples", "pencils", "tickets", "books", "marbles", "coins"]
TEMPLATES = [
    "{a} has {x} {it}. {b} gives {a} {y} more {it} and then {a} gives away {z} {it}. How many {it} does {a} have now?",
    "A train travels {x} km in {y} hours. At the same speed, how many km does it travel in {z} hours?",
    "The sum of two numbers is {x} and their difference is {y}. Find the larger number.",
    "A rectangle has a perimeter of {x} cm and a width of {y} cm. What is its area in square centimeters?",
    "If f(x) = {x}x^2 - {y}x + {z}, find the value of f(2).",
    "{a} saves {x} won every day for {y} days and then spends {z} won. How much money is left?",
    "A bag contains {x} red balls and {y} blue balls. If {z} balls are drawn without replacement, what is the probability that all are red?",
    "The arithmetic sequence starts at {x} with common difference {y}. What is the {z}th term?",
    "A store sells {it} at {x} won each. {a} buys {y} {it} and pays with a {z} won bill. How much change does {a} receive?",
    "A circle has radius {x} cm. A square is inscribed in it. What is the area of the square in terms of {y} and {z}?",
    "The geometric sequence has first term {x} and ratio {y}. Find the sum of the first {z} terms.",
    "In a class of {x} students, {y} like math and {z} like science, and every student likes at least one. How many like both?",
]
SYN = {"How many": "What number of", "has": "owns", "gives": "hands", "travels": "covers", "Find": "Determine",
       "What is": "Compute", "contains": "holds", "buys": "purchases", "receive": "get back", "students": "pupils",
       "probability": "chance", "number": "value", "speed": "rate", "money": "cash", "starts at": "begins with"}


def make(ti, r):
    a, b = r.choice(NAMES, 2, replace=False)
    return TEMPLATES[ti].format(a=a, b=b, it=r.choice(ITEMS), x=int(r.integers(5, 400)),
                                y=int(r.integers(2, 90)), z=int(r.integers(2, 30)))


def norm(s):
    return re.sub(r"\s+", " ", s.lower()).strip()


def attacks(q, r):
    out = {}
    out["format"] = re.sub(r" ", "  ", q).upper().replace(".", " .")
    out["numbers"] = re.sub(r"\d+", lambda m: f"{int(m.group()):,}" if int(m.group()) >= 100 else f" {m.group()} ", q)
    sents = [s for s in re.split(r"(?<=[.?])\s+", q) if s]
    out["reorder"] = " ".join(sents[1:] + sents[:1]) if len(sents) > 1 else q
    w = q.split(); k = max(6, int(len(w) * 0.6)); st = int(r.integers(0, len(w) - k + 1))
    out["partial"] = " ".join(w[st:st + k])
    s = q
    for k_, v in SYN.items():
        s = s.replace(k_, v)
    out["synonym"] = s
    c = out["synonym"]
    c = " ".join([t for t in re.split(r"(?<=[.?])\s+", c) if t][1:] + [t for t in re.split(r"(?<=[.?])\s+", c) if t][:1])
    out["combined"] = c.upper().replace(".", " .")
    return out


def nums(s):
    return re.findall(r"\d+", s.replace(",", ""))


def main():
    reg = [make(i % 12, rng) for i in range(60)]
    neg = [make(i % 12, rng) for i in range(240)]                # same templates, new values
    pos = {}
    for q in reg:
        for k, v in attacks(q, rng).items():
            pos.setdefault(k, []).append((q, v))
    vec = TfidfVectorizer(analyzer="char", ngram_range=(4, 4), lowercase=True).fit(reg + neg)
    R = vec.transform(reg)
    reg_hash = {hashlib.sha256(norm(q).encode()).hexdigest() for q in reg}

    def best(qtext):
        s = (vec.transform([qtext]) @ R.T).toarray()[0]
        i = int(np.argmax(s)); return s[i], reg[i]

    def num_ok(qtext, item):
        qn, rn = nums(qtext), nums(item)
        return len(qn) > 0 and all(qn.count(n) <= rn.count(n) for n in set(qn))

    res = {"n_registered": len(reg), "n_negative": len(neg), "thresholds": {}}
    neg_scores = [best(q) for q in neg]
    for th in (0.5, 0.6, 0.7, 0.8):
        row = {}
        for k, pairs in pos.items():
            ex = np.mean([hashlib.sha256(norm(v).encode()).hexdigest() in reg_hash for _, v in pairs])
            ng, nn = [], []
            for q, v in pairs:
                s, item = best(v)
                ng.append(s >= th and item == q); nn.append(s >= th and item == q and num_ok(v, item))
            row[k] = dict(exact=float(ex), ngram=float(np.mean(ng)), ngram_num=float(np.mean(nn)))
        fp_ng = float(np.mean([s >= th for s, _ in neg_scores]))
        fp_nn = float(np.mean([s >= th and num_ok(q, it) for (s, it), q in zip(neg_scores, neg)]))
        fp_ex = float(np.mean([hashlib.sha256(norm(q).encode()).hexdigest() in reg_hash for q in neg]))
        row["false_match_on_similar_practice_problems"] = dict(exact=fp_ex, ngram=fp_ng, ngram_num=fp_nn)
        res["thresholds"][str(th)] = row
    res["example"] = {"registered": reg[0], **{k: v for k, v in attacks(reg[0], np.random.default_rng(1)).items()}}
    json.dump(res, open(sys.argv[1] if len(sys.argv) > 1 else "E3-001_results.json", "w"), indent=1)
    for th, row in res["thresholds"].items():
        print("th", th)
        for k, v in row.items():
            print(f"  {k:42s} exact={v['exact']:.2f} ngram={v['ngram']:.2f} ngram+num={v['ngram_num']:.2f}")


if __name__ == "__main__":
    main()
