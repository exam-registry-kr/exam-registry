"""Merkle tree log of RFC 9162 (Certificate Transparency version 2.0), section 2.1:
tree hash, inclusion proofs and consistency proofs, with SHA-256.

The registry is an append-only public log. With a hash chain, a reader who wants to
check one exam record, or to check that the log was only extended and never rewritten,
must download and rehash the whole log. With the RFC 9162 Merkle tree:
  - a signed tree head (size, root hash) commits to every record,
  - an inclusion proof of about log2(size) hashes shows that one record is in the log,
  - a consistency proof of about log2(size) hashes shows that the log at size m is a
    prefix of the log at size n, so the operator cannot rewrite history unseen.
The algorithms are those of RFC 9162 sections 2.1.1 to 2.1.4. They are checked against
the test data of transparency-dev/merkle (RFC 6962 hashing, which RFC 9162 keeps):
    python transparency_log.py --check DIR     # DIR = the repository's testonly/ and testdata/
"""
import base64, glob, hashlib, json, os, re, sys


def leaf_hash(data):
    return hashlib.sha256(b"\x00" + data).digest()


def node_hash(left, right):
    return hashlib.sha256(b"\x01" + left + right).digest()


def _k(n):
    """Largest power of two smaller than n (n > 1)."""
    k = 1
    while k << 1 < n:
        k <<= 1
    return k


def root(hashes):
    """MTH over leaf hashes (RFC 9162 2.1.1)."""
    n = len(hashes)
    if n == 0:
        return hashlib.sha256(b"").digest()
    if n == 1:
        return hashes[0]
    k = _k(n)
    return node_hash(root(hashes[:k]), root(hashes[k:]))


def inclusion_proof(m, hashes):
    """PATH(m, D[n]) (RFC 9162 2.1.3.1), m counted from 0."""
    n = len(hashes)
    if n <= 1:
        return []
    k = _k(n)
    if m < k:
        return inclusion_proof(m, hashes[:k]) + [root(hashes[k:])]
    return inclusion_proof(m - k, hashes[k:]) + [root(hashes[:k])]


def consistency_proof(m, hashes):
    """PROOF(m, D[n]) (RFC 9162 2.1.4.1)."""
    def sub(m, d, complete):
        n = len(d)
        if m == n:
            return [] if complete else [root(d)]
        k = _k(n)
        if m <= k:
            return sub(m, d[:k], complete) + [root(d[k:])]
        return sub(m - k, d[k:], False) + [root(d[:k])]
    if m == 0:
        raise ValueError("a consistency proof starts from a non-empty tree")
    if m == len(hashes):
        return []
    return sub(m, hashes, True)


def verify_inclusion(index, size, leaf, proof, root_hash):
    """RFC 9162 2.1.3.2. Every hash must be 32 bytes."""
    if index >= size or len(leaf) != 32 or len(root_hash) != 32 or any(len(p) != 32 for p in proof):
        return False
    fn, sn, r = index, size - 1, leaf
    for p in proof:
        if sn == 0:
            return False
        if fn & 1 or fn == sn:
            r = node_hash(p, r)
            if not fn & 1:
                while fn and not fn & 1:
                    fn >>= 1
                    sn >>= 1
        else:
            r = node_hash(r, p)
        fn >>= 1
        sn >>= 1
    return sn == 0 and r == root_hash


def verify_consistency(size1, size2, root1, root2, proof):
    """RFC 9162 2.1.4.2. A consistency proof is defined only from a non-empty tree
    (0 < size1); equal sizes need an empty proof and equal roots."""
    if size1 == 0 or size1 > size2:
        return False
    if size1 == size2:
        return not proof and root1 == root2
    if len(root1) != 32 or len(root2) != 32 or any(len(p) != 32 for p in proof):
        return False
    if not proof:
        return False
    path = list(proof)
    if size1 & (size1 - 1) == 0:                  # exact power of two
        path = [root1] + path
    fn, sn = size1 - 1, size2 - 1
    while fn & 1:
        fn >>= 1
        sn >>= 1
    fr = sr = path[0]
    for c in path[1:]:
        if sn == 0:
            return False
        if fn & 1 or fn == sn:
            fr, sr = node_hash(c, fr), node_hash(c, sr)
            if not fn & 1:
                while fn and not fn & 1:
                    fn >>= 1
                    sn >>= 1
        else:
            sr = node_hash(sr, c)
        fn >>= 1
        sn >>= 1
    return fr == root1 and sr == root2 and sn == 0


class Log:
    """Append-only log of byte strings with RFC 9162 tree heads and proofs."""

    def __init__(self):
        self.leaves, self.hashes = [], []

    def append(self, data):
        self.leaves.append(data)
        self.hashes.append(leaf_hash(data))
        return len(self.hashes) - 1

    def size(self):
        return len(self.hashes)

    def root(self, size=None):
        return root(self.hashes[:self.size() if size is None else size])

    def inclusion(self, index, size=None):
        return inclusion_proof(index, self.hashes[:self.size() if size is None else size])

    def consistency(self, size1, size2=None):
        return consistency_proof(size1, self.hashes[:self.size() if size2 is None else size2])


# ---------------------------------------------------------------- reference data
def _go_hex_list(src, func):
    body = src[src.index(f"func {func}()"):]
    body = body[:body.index("\n}\n")]
    return [bytes.fromhex(h) for h in re.findall(r'hd\("([0-9a-f]*)"\)', body)]


def check(repo):
    """Checks tree hashes, proofs and both verifiers against transparency-dev/merkle data."""
    src = open(os.path.join(repo, "testonly", "constants.go")).read()
    leaves, roots = _go_hex_list(src, "LeafInputs"), _go_hex_list(src, "RootHashes")
    roots = [hashlib.sha256(b"").digest()] + roots          # EmptyRootHash() is a call, not a literal
    hs = [leaf_hash(x) for x in leaves]
    rep = dict(roots=all(root(hs[:n]) == roots[n] for n in range(len(hs) + 1)))
    ok_inc = ok_con = True
    for n in range(1, len(hs) + 1):
        for m in range(n):
            ok_inc &= verify_inclusion(m, n, hs[m], inclusion_proof(m, hs[:n]), root(hs[:n]))
        for m in range(1, n + 1):
            ok_con &= verify_consistency(m, n, root(hs[:m]), root(hs[:n]), consistency_proof(m, hs[:n]))
    rep["own_proofs_verify"] = bool(ok_inc and ok_con)
    b = lambda s: base64.b64decode(s) if s else b""
    for kind in ("inclusion", "consistency"):
        good = bad = wrong = 0
        for f in sorted(glob.glob(os.path.join(repo, "testdata", kind, "*", "*.json"))):
            v = json.load(open(f))
            proof = [b(x) for x in (v.get("proof") or [])]
            if kind == "inclusion":
                got = verify_inclusion(v["leafIdx"], v["treeSize"], b(v["leafHash"]), proof, b(v["root"]))
                if not v["wantErr"]:
                    got &= inclusion_proof(v["leafIdx"], hs[:v["treeSize"]]) == proof if v["treeSize"] <= len(hs) and \
                        root(hs[:v["treeSize"]]) == b(v["root"]) else True
            else:
                got = verify_consistency(v["size1"], v["size2"], b(v["root1"]), b(v["root2"]), proof)
            if got == (not v["wantErr"]):
                good += 1
            else:
                wrong += 1
            bad += v["wantErr"]
        rep[kind] = dict(files=good + wrong, expected_rejections=bad, agree=good, disagree=wrong)
    rep["all_ok"] = rep["roots"] and rep["own_proofs_verify"] and rep["inclusion"]["disagree"] == 0 and rep["consistency"]["disagree"] == 0
    return rep


if __name__ == "__main__":
    if "--check" in sys.argv:
        r = check(sys.argv[sys.argv.index("--check") + 1])
        print(json.dumps(r, indent=1))
        sys.exit(0 if r["all_ok"] else 1)
