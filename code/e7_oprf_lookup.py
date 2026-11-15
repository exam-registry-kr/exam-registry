"""E7: does the encrypted content lookup decide exactly like a plaintext lookup, and how fast is it?

The encrypted lookup (oblivious pseudorandom function, OPRF) lets an AI service ask
whether a question matches a registered exam item without the exam authority seeing
the question and without the service seeing the item. The protocol only hides the
4-character pieces; the matching rule applied afterwards is the same as in plaintext.
So the claim to check is simple: every decision must be identical to a plaintext
lookup that uses the same rule. Speed is measured per query.

Data: the 60 registered items, 360 rewritten positive queries (6 rewrites per item)
and 240 practice problems from the same templates, regenerated exactly as in E3
(same seed, same order). Matching rule: share of the query's 4-character pieces found
in the best registered item >= 0.5, and every number in the query appears in that
item.

Arms
  plain : pieces hashed with SHA-256, no encryption (comparison group)
  oprf  : pieces evaluated with a 2HashDH OPRF on the NIST P-256 curve
  e3    : the TF-IDF matcher of E3, reported for reference (different rule)

The OPRF here uses x-coordinate-only scalar multiplication through the
`cryptography` package and a simple try-and-increment hash to the curve. It shows the
cost of the elliptic-curve operations a real deployment performs, but it is NOT an
RFC 9497 implementation (RFC 9497 fixes the hash-to-curve method, encodings and
domain separation). Timings are for this demonstration on one CPU core.

    python e7_oprf_lookup.py            # about one minute
"""
import hashlib, json, re, secrets, statistics, sys, time
import numpy as np
from cryptography.hazmat.primitives.asymmetric import ec
from sklearn.feature_extraction.text import TfidfVectorizer
import e3_registry as E3

# NIST P-256
Pp = 2**256 - 2**224 + 2**192 + 2**96 - 1
Bp = 0x5AC635D8AA3A93E7B3EBBD55769886BC651D06B0CC53B0F63BCE3C3E27D2604B
Np = 0xFFFFFFFF00000000FFFFFFFFFFFFFFFFBCE6FAADA7179E84F3B9CAC2FC632551
CURVE = ec.SECP256R1()
TH = 0.5


def lift(x):
    """A curve point with x-coordinate x, or None. Either root works: kP and k(-P) share x."""
    rhs = (pow(x, 3, Pp) - 3 * x + Bp) % Pp
    y = pow(rhs, (Pp + 1) // 4, Pp)
    if y * y % Pp != rhs:
        return None
    return ec.EllipticCurvePublicKey.from_encoded_point(CURVE, b"\x04" + x.to_bytes(32, "big") + y.to_bytes(32, "big"))


def hash_to_point(s):
    for ctr in range(256):
        x = int.from_bytes(hashlib.sha256(f"exam-registry-e7|{ctr}|{s}".encode()).digest(), "big") % Pp
        P = lift(x)
        if P is not None:
            return P
    raise ValueError("hash_to_point failed")


def mul_x(k, P):
    """x-coordinate of k*P, computed by the cryptography package (OpenSSL)."""
    return int.from_bytes(ec.derive_private_key(k, CURVE).exchange(ec.ECDH(), P), "big")


class Authority:
    """Holds the secret key and the items. Publishes F_k(piece) for every piece before the exam."""

    def __init__(self, items, pieces_fn):
        self._k = secrets.randbelow(Np - 1) + 1
        self._key = ec.derive_private_key(self._k, CURVE)
        self.published = []
        for it in items:
            g, n = pieces_fn(it)
            self.published.append(({self._F(x) for x in g}, {self._F(x) for x in n}))
        self.evaluations = 0
        self.server_seconds = 0.0

    def _F(self, x):
        return hashlib.sha256(int.from_bytes(self._key.exchange(ec.ECDH(), hash_to_point(x)), "big")
                              .to_bytes(32, "big") + x.encode()).hexdigest()

    def evaluate(self, blinded_xs):
        """Sees only blinded x-coordinates; returns x(k * B) for each."""
        t = time.perf_counter()
        out = [int.from_bytes(self._key.exchange(ec.ECDH(), lift(bx)), "big") for bx in blinded_xs]
        self.server_seconds += time.perf_counter() - t
        self.evaluations += len(blinded_xs)
        return out


def oprf(server, xs):
    xs = list(xs)
    rs = [secrets.randbelow(Np - 1) + 1 for _ in xs]
    blinded = [mul_x(r, hash_to_point(x)) for x, r in zip(xs, rs)]            # service -> authority
    evaluated = server.evaluate(blinded)                                       # authority -> service
    out = set()
    for x, r, e in zip(xs, rs, evaluated):
        y = mul_x(pow(r, -1, Np), lift(e))                                     # = x(k * H(x))
        out.add(hashlib.sha256(y.to_bytes(32, "big") + x.encode()).hexdigest())
    return out


def pieces(text):
    """Same 4-character pieces and number tokens as oprf_demo.py, after case and comma normalisation."""
    t0 = text.lower().replace(",", "")
    t = re.sub(r"[\s\.,?!·~\"'()]", "", t0)
    grams = {t[i:i + 4] for i in range(max(0, len(t) - 3))}
    nums = {"#" + n for n in re.findall(r"\d+(?:\.\d+)?", t0)}
    return grams, nums


def decide(fg, fn, published):
    best, ok, idx = 0.0, False, -1
    for i, (pg, pn) in enumerate(published):
        s = len(fg & pg) / max(1, len(fg))
        if s > best:
            best, ok, idx = s, (len(fn) > 0 and fn <= pn), i
    return best >= TH and ok, idx, best


def regenerate_e3():
    """Rebuild E3's registered items, rewrites and practice problems in E3's exact order."""
    E3.rng = np.random.default_rng(20261117)
    reg = [E3.make(i % 12, E3.rng) for i in range(60)]
    neg = [E3.make(i % 12, E3.rng) for i in range(240)]
    pos = []
    for qi, q in enumerate(reg):
        for k, v in E3.attacks(q, E3.rng).items():
            pos.append((k, qi, v))
    return reg, neg, pos


def main():
    out_path = sys.argv[1] if len(sys.argv) > 1 else "E7-001_results.json"
    reg, neg, pos = regenerate_e3()
    queries = [(k, qi, v) for k, qi, v in pos] + [("practice", -1, q) for q in neg]

    plain_pub = [({hashlib.sha256(x.encode()).hexdigest() for x in g},
                  {hashlib.sha256(x.encode()).hexdigest() for x in n}) for g, n in map(pieces, reg)]
    t = time.perf_counter()
    auth = Authority(reg, pieces)
    publish_s = time.perf_counter() - t
    n_pub = sum(len(a) + len(b) for a, b in auth.published)

    vec = TfidfVectorizer(analyzer="char", ngram_range=(4, 4), lowercase=True).fit(reg + neg)
    R = vec.transform(reg)

    rows, lat, srv, npieces = [], [], [], []
    for kind, qi, q in queries:
        g, n = pieces(q)
        pg = {hashlib.sha256(x.encode()).hexdigest() for x in g}
        pn = {hashlib.sha256(x.encode()).hexdigest() for x in n}
        p_hit, p_idx, p_s = decide(pg, pn, plain_pub)

        s0, e0 = auth.server_seconds, auth.evaluations
        t = time.perf_counter()
        og, on = oprf(auth, g), oprf(auth, n)
        o_hit, o_idx, o_s = decide(og, on, auth.published)
        lat.append(time.perf_counter() - t)
        srv.append(auth.server_seconds - s0)
        npieces.append(auth.evaluations - e0)

        sc = (vec.transform([q]) @ R.T).toarray()[0]
        j = int(np.argmax(sc))
        e3_hit = bool(sc[j] >= TH and E3.nums(q) and all(E3.nums(q).count(x) <= E3.nums(reg[j]).count(x) for x in set(E3.nums(q))))

        rows.append(dict(kind=kind, item=qi, plain=bool(p_hit), plain_item=p_idx, plain_score=round(p_s, 4),
                         oprf=bool(o_hit), oprf_item=o_idx, oprf_score=round(o_s, 4),
                         e3=e3_hit, e3_item=j))

    def rate(arm, kind):
        sel = [r for r in rows if r["kind"] == kind]
        if kind == "practice":
            return float(np.mean([r[arm] for r in sel]))
        item_key = {"plain": "plain_item", "oprf": "oprf_item", "e3": "e3_item"}[arm]
        return float(np.mean([r[arm] and r[item_key] == r["item"] for r in sel]))

    kinds = ["format", "numbers", "reorder", "partial", "synonym", "combined", "practice"]
    table = {k: {a: rate(a, k) for a in ("plain", "oprf", "e3")} for k in kinds}
    same = sum(r["plain"] == r["oprf"] and r["plain_item"] == r["oprf_item"] and r["plain_score"] == r["oprf_score"] for r in rows)
    res = dict(
        experiment="E7-001", threshold=TH, n_registered=len(reg), n_queries=len(rows),
        n_positive=len(pos), n_practice=len(neg),
        identical_decisions=dict(count=same, total=len(rows)),
        detection_and_false_match=table,
        timing=dict(
            note="2HashDH OPRF on P-256 via the cryptography package, one CPU core; not RFC 9497",
            publish_seconds=round(publish_s, 3), published_values=n_pub,
            pieces_per_query_median=statistics.median(npieces),
            client_total_ms_median=round(1000 * statistics.median(lat), 2),
            client_total_ms_p95=round(1000 * float(np.percentile(lat, 95)), 2),
            authority_ms_per_query_median=round(1000 * statistics.median(srv), 3),
            authority_us_per_piece=round(1e6 * auth.server_seconds / max(1, auth.evaluations), 2),
            bytes_per_piece_each_way=32),
        rows=rows)
    json.dump(res, open(out_path, "w"), indent=1, ensure_ascii=False)

    print(f"identical decisions (plain vs oprf): {same}/{len(rows)}")
    print(f"{'query':10s} {'plain':>6s} {'oprf':>6s} {'e3':>6s}")
    for k in kinds:
        v = table[k]
        print(f"{k:10s} {v['plain']:6.2f} {v['oprf']:6.2f} {v['e3']:6.2f}")
    print(json.dumps(res["timing"], indent=1))


if __name__ == "__main__":
    main()
