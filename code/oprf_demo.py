"""Illustration of the oblivious content lookup (2HashDH OPRF).

This file shows the idea in a few lines of plain Python. It is NOT an
implementation of RFC 9497: it uses the 2048-bit MODP group of RFC 3526 and
Python integers instead of an elliptic-curve suite, and it is not hardened
against timing attacks. A real deployment should use an RFC 9497 library.

Roles
  Authority : holds the secret key k and the exam items. Before the exam it
              gives AI services F_k(piece) for every 4-character piece and every
              number in each item. F_k values cannot be reversed without k.
  Service   : cuts a user's question into the same pieces, blinds each piece
              with a fresh random r, and asks the authority to apply k.
              The authority sees only blinded values, so it learns nothing about
              the question; the service learns only which pieces match.

    python oprf_demo.py
"""
import hashlib, re, secrets

# RFC 3526, group 14: p is a safe prime (p = 2q + 1)
P = int("FFFFFFFFFFFFFFFFC90FDAA22168C234C4C6628B80DC1CD129024E088A67CC74020BBEA63B139B22514A08798E3404DD"
        "EF9519B3CD3A431B302B0A6DF25F14374FE1356D6D51C245E485B576625E7EC6F44C42E9A637ED6B0BFF5CB6F406B7ED"
        "EE386BFB5A899FA5AE9F24117C4B1FE649286651ECE45B3DC2007CB8A163BF0598DA48361C55D39A69163FA8FD24CF5F"
        "83655D23DCA3AD961C62F356208552BB9ED529077096966D670C354E4ABC9804F1746C08CA18217C32905E462E36CE3B"
        "E39E772C180E86039B2783A2EC07A28FB5C55DF06F4C52C9DE2BCBF6955817183995497CEA956AE515D2261898FA0510"
        "15728E5A8AACAA68FFFFFFFFFFFFFFFF", 16)
Q = (P - 1) // 2


def hash_to_group(x: str) -> int:
    h = b"".join(hashlib.sha256(f"{i}|{x}".encode()).digest() for i in range(9))
    return pow(int.from_bytes(h, "big") % P, 2, P)          # square -> subgroup of order Q


def finalize(x: str, y: int) -> str:
    return hashlib.sha256(x.encode() + y.to_bytes(256, "big")).hexdigest()


def pieces(text: str):
    t = re.sub(r"[\s\.,?!·~\"'()]", "", text)
    grams = {t[i:i + 4] for i in range(max(0, len(t) - 3))}
    nums = {"#" + n for n in re.findall(r"\d+(?:\.\d+)?", text)}
    return grams, nums


class Authority:
    def __init__(self, items):
        self._k = secrets.randbelow(Q - 1) + 1
        self.published = []                         # per item: (piece PRFs, number PRFs)
        for it in items:
            g, n = pieces(it)
            self.published.append(({finalize(x, pow(hash_to_group(x), self._k, P)) for x in g},
                                   {finalize(x, pow(hash_to_group(x), self._k, P)) for x in n}))

    def evaluate(self, blinded):                    # sees only blinded group elements
        return [pow(b, self._k, P) for b in blinded]


def oprf(server, xs):
    xs = list(xs)
    rs = [secrets.randbelow(Q - 1) + 1 for _ in xs]
    blinded = [pow(hash_to_group(x), r, P) for x, r in zip(xs, rs)]
    evaluated = server.evaluate(blinded)
    return {finalize(x, pow(e, pow(r, -1, Q), P)) for x, r, e in zip(xs, rs, evaluated)}


def lookup(server, question):
    """Returns (share of the question's pieces found in the best item, all numbers match)."""
    g, n = pieces(question)
    fg, fn = oprf(server, g), oprf(server, n)
    best, nums_ok = 0.0, False
    for pg, pn in server.published:
        s = len(fg & pg) / max(1, len(fg))
        if s > best:
            best, nums_ok = s, fn <= pn
    return best, nums_ok


def change_numbers(text):
    return re.sub(r"\d+", lambda m: str(int(m.group()) + 7), text)


if __name__ == "__main__":
    items = ["어떤 수에 6을 곱한 후 59를 더하면 197이다. 이 수를 구하시오.",
             "첫째항이 22이고 공차가 6인 등차수열의 제13항을 구하시오."]
    s = Authority(items)
    for q in [items[0], "어떤수에6을곱한후59를더하면197이다 이수를 구해줘", change_numbers(items[0]), "오늘 날씨 어때"]:
        sc, ok = lookup(s, q)
        print(f"{sc:4.0%}  numbers={'match' if ok else 'differ'}  {q}")
