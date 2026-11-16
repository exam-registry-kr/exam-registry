"""OPRF(P-256, SHA-256), base mode, as specified in RFC 9497, with hash_to_curve
P256_XMD:SHA-256_SSWU_RO_ from RFC 9380.

Only the base mode (mode 0x00, "OPRF") is implemented, because the content lookup needs
exactly that: the service learns F(k, piece) without learning k, and the authority
learns nothing about the piece. Verifiable and partially-oblivious modes are not used.

Scalar multiplication goes through the `cryptography` package (OpenSSL). OpenSSL's ECDH
returns only the x-coordinate of k*P; the y-coordinate is recovered by lifting x and
choosing the root for which (candidate + P) has the same x as (k+1)*P. Everything else
(field arithmetic, SSWU map, point addition, encodings, domain separation) follows the
RFCs and is checked against the official test vectors by `python rfc9497.py --check`.

    python rfc9497.py --check DIR   # DIR holds the CFRG vector files (see README)
"""
import hashlib, json, os, secrets, sys
from cryptography.hazmat.primitives.asymmetric import ec

# P-256 (RFC 9380 section 8.2, SEC 2)
p = 2**256 - 2**224 + 2**192 + 2**96 - 1
A = p - 3
B = 0x5AC635D8AA3A93E7B3EBBD55769886BC651D06B0CC53B0F63BCE3C3E27D2604B
N = 0xFFFFFFFF00000000FFFFFFFFFFFFFFFFBCE6FAADA7179E84F3B9CAC2FC632551
Z = p - 10                      # SSWU constant for P-256
L = 48                          # ceil((ceil(log2(p)) + 128) / 8)
_CURVE = ec.SECP256R1()

MODE_OPRF = 0
IDENTIFIER = b"P256-SHA256"
CONTEXT = b"OPRFV1-" + bytes([MODE_OPRF]) + b"-" + IDENTIFIER
DST_GROUP = b"HashToGroup-" + CONTEXT
DST_SCALAR = b"HashToScalar-" + CONTEXT
DST_DERIVE = b"DeriveKeyPair" + CONTEXT


def i2osp(x, n):
    return x.to_bytes(n, "big")


# ---------------------------------------------------------------- RFC 9380
def expand_message_xmd(msg, dst, length):
    h, b_in, r_in = hashlib.sha256, 32, 64
    ell = -(-length // b_in)
    if ell > 255 or length > 65535 or len(dst) > 255:
        raise ValueError("expand_message_xmd: input too long")
    dst_prime = dst + i2osp(len(dst), 1)
    b0 = h(bytes(r_in) + msg + i2osp(length, 2) + b"\x00" + dst_prime).digest()
    b = [h(b0 + b"\x01" + dst_prime).digest()]
    for i in range(2, ell + 1):
        b.append(h(bytes(x ^ y for x, y in zip(b0, b[-1])) + i2osp(i, 1) + dst_prime).digest())
    return b"".join(b)[:length]


def hash_to_field(msg, count, dst, modulus):
    u = expand_message_xmd(msg, dst, count * L)
    return [int.from_bytes(u[L * i:L * (i + 1)], "big") % modulus for i in range(count)]


def _inv(x):
    return pow(x, p - 2, p)


def _is_square(x):
    return x == 0 or pow(x, (p - 1) // 2, p) == 1


def _sqrt(x):
    return pow(x, (p + 1) // 4, p)              # p = 3 mod 4


def _sgn0(x):
    return x % 2


def map_to_curve_sswu(u):
    """Simplified SWU, RFC 9380 section 6.6.2 (straight-line, not constant time)."""
    tv1 = (Z * Z * pow(u, 4, p) + Z * u * u) % p
    tv1 = _inv(tv1) if tv1 else 0
    x1 = (-B * _inv(A) * (1 + tv1)) % p if tv1 else (B * _inv(Z * A)) % p
    gx1 = (pow(x1, 3, p) + A * x1 + B) % p
    x2 = (Z * u * u * x1) % p
    gx2 = (pow(x2, 3, p) + A * x2 + B) % p
    x, y = (x1, _sqrt(gx1)) if _is_square(gx1) else (x2, _sqrt(gx2))
    if _sgn0(u) != _sgn0(y):
        y = p - y
    return (x, y)


def add(P, Q):
    """Affine addition; None is the point at infinity."""
    if P is None:
        return Q
    if Q is None:
        return P
    (x1, y1), (x2, y2) = P, Q
    if x1 == x2:
        if (y1 + y2) % p == 0:
            return None
        lam = (3 * x1 * x1 + A) * _inv(2 * y1) % p
    else:
        lam = (y2 - y1) * _inv(x2 - x1) % p
    x3 = (lam * lam - x1 - x2) % p
    return (x3, (lam * (x1 - x3) - y1) % p)


def hash_to_curve(msg, dst):
    u0, u1 = hash_to_field(msg, 2, dst, p)
    return add(map_to_curve_sswu(u0), map_to_curve_sswu(u1))     # cofactor 1


# ---------------------------------------------------------------- group operations
def _lift(x):
    rhs = (pow(x, 3, p) + A * x + B) % p
    y = _sqrt(rhs)
    if y * y % p != rhs:
        raise ValueError("x is not on the curve")
    return y


def _x_of(k, P):
    """x-coordinate of k*P through OpenSSL ECDH, for 1 <= k < N."""
    pub = ec.EllipticCurvePublicKey.from_encoded_point(_CURVE, b"\x04" + i2osp(P[0], 32) + i2osp(P[1], 32))
    return int.from_bytes(ec.derive_private_key(k, _CURVE).exchange(ec.ECDH(), pub), "big")


def mul(k, P):
    """k*P as a full affine point."""
    k %= N
    if k == 0 or P is None:
        return None
    x = _x_of(k, P)
    y = _lift(x)
    if k + 1 < N:
        ref = _x_of(k + 1, P)
        cand = add((x, y), P)
        return (x, y) if cand is not None and cand[0] == ref else (x, p - y)
    ref = _x_of(k - 1, P)                       # k = N - 1: compare with (k-1)P = Q - P
    cand = add((x, y), (P[0], p - P[1]))
    return (x, y) if cand is not None and cand[0] == ref else (x, p - y)


def serialize_element(P):
    if P is None:
        raise ValueError("cannot serialize the identity")
    return bytes([2 + (P[1] & 1)]) + i2osp(P[0], 32)


def deserialize_element(b):
    if len(b) != 33 or b[0] not in (2, 3):
        raise ValueError("bad element encoding")
    x = int.from_bytes(b[1:], "big")
    if x >= p:
        raise ValueError("bad element encoding")
    y = _lift(x)
    if (y & 1) != (b[0] & 1):
        y = p - y
    return (x, y)


def serialize_scalar(s):
    return i2osp(s, 32)


# ---------------------------------------------------------------- RFC 9497, mode 0x00
def hash_to_group(x):
    return hash_to_curve(x, DST_GROUP)


def hash_to_scalar(x, dst=DST_SCALAR):
    return hash_to_field(x, 1, dst, N)[0]


def derive_key_pair(seed, info):
    derive_input = seed + i2osp(len(info), 2) + info
    for counter in range(256):
        sk = hash_to_scalar(derive_input + i2osp(counter, 1), DST_DERIVE)
        if sk:
            return sk
    raise ValueError("DeriveKeyPairError")


def random_scalar():
    return secrets.randbelow(N - 1) + 1


def blind(inp, r=None):
    """Client. Returns (r, serialized blinded element)."""
    r = random_scalar() if r is None else r
    E = hash_to_group(inp)
    if E is None:
        raise ValueError("InvalidInputError")
    return r, serialize_element(mul(r, E))


def blind_evaluate(sk, blinded):
    """Server."""
    return serialize_element(mul(sk, deserialize_element(blinded)))


def finalize(inp, r, evaluated):
    """Client."""
    unblinded = serialize_element(mul(pow(r, -1, N), deserialize_element(evaluated)))
    return hashlib.sha256(i2osp(len(inp), 2) + inp + i2osp(len(unblinded), 2) + unblinded + b"Finalize").digest()


def evaluate(sk, inp):
    """Server-side evaluation without the client (used to publish the registered pieces)."""
    E = hash_to_group(inp)
    if E is None:
        raise ValueError("InvalidInputError")
    issued = serialize_element(mul(sk, E))
    return hashlib.sha256(i2osp(len(inp), 2) + inp + i2osp(len(issued), 2) + issued + b"Finalize").digest()


# ---------------------------------------------------------------- official test vectors
def check(vector_dir):
    """Checks hash_to_curve against the CFRG P256_XMD:SHA-256_SSWU_RO_ vectors and the
    OPRF against the CFRG P256-SHA256 mode 0 vectors. Returns a report dict."""
    rep = dict(hash_to_curve=[], oprf=[])
    h = json.load(open(os.path.join(vector_dir, "P256_XMD:SHA-256_SSWU_RO_.json")))
    dst = h["dst"].encode()
    for v in h["vectors"]:
        P = hash_to_curve(v["msg"].encode(), dst)
        ok = P == (int(v["P"]["x"], 16), int(v["P"]["y"], 16))
        ok &= hash_to_field(v["msg"].encode(), 2, dst, p) == [int(u, 16) for u in v["u"]]
        rep["hash_to_curve"].append(dict(msg=v["msg"][:24], ok=bool(ok)))
    allv = json.load(open(os.path.join(vector_dir, "allVectors.json")))
    suite = [e for e in allv if e["identifier"] == "P256-SHA256" and e["mode"] == 0][0]
    sk = derive_key_pair(bytes.fromhex(suite["seed"]), bytes.fromhex(suite["keyInfo"]))
    rep["skSm_ok"] = serialize_scalar(sk).hex() == suite["skSm"]
    rep["groupDST_ok"] = DST_GROUP.hex() == suite["groupDST"]
    for v in suite["vectors"]:
        inp, r = bytes.fromhex(v["Input"]), int(v["Blind"], 16)
        _, bl = blind(inp, r)
        ev = blind_evaluate(sk, bl)
        out = finalize(inp, r, ev)
        rep["oprf"].append(dict(input=v["Input"][:16], blinded=bl.hex() == v["BlindedElement"],
                                evaluated=ev.hex() == v["EvaluationElement"], output=out.hex() == v["Output"],
                                evaluate_equals_output=evaluate(sk, inp).hex() == v["Output"]))
    rep["all_ok"] = rep["skSm_ok"] and rep["groupDST_ok"] and all(x["ok"] for x in rep["hash_to_curve"]) and \
        all(all(x[k] for k in ("blinded", "evaluated", "output", "evaluate_equals_output")) for x in rep["oprf"])
    return rep


if __name__ == "__main__":
    if "--check" in sys.argv:
        r = check(sys.argv[sys.argv.index("--check") + 1])
        print(json.dumps(r, indent=1))
        sys.exit(0 if r["all_ok"] else 1)
