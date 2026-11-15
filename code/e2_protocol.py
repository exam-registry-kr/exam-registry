"""E2: commitment, provider decision, reveal, and false-refusal tests.

Protocol objects
  Authority      holds an Ed25519 key, issues signed commitment records.
  Record         {exam_id, window_start, window_end, items_hash, authority, published_at}
  Directory      list of accredited authority public keys (who may register exams).
  Provider       decodes the marker (E1 decoder), looks up records, decides REFUSE/ALLOW.

Decision rule (provider):
  REFUSE iff a marker decodes to exam_id X, and a record for X
    (a) is signed by an accredited authority,
    (b) was published before its window starts (no retroactive registration),
    (c) has a window no longer than MAX_WINDOW,
    (d) and the current time is inside the window.
  Otherwise ALLOW.
"""
import json, hashlib, os, time, zlib, argparse
from dataclasses import dataclass, asdict
import numpy as np, cv2
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.hazmat.primitives import serialization
from cryptography.exceptions import InvalidSignature
import e1_sim as E

MAX_WINDOW = 24 * 3600
HOUR = 3600


def pub_bytes(pk):
    return pk.public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)


def items_commitment(items, salt):
    h = hashlib.sha256(salt)
    for q in items:
        h.update(hashlib.sha256(q.encode()).digest())
    return h.hexdigest()


class Authority:
    def __init__(self, name):
        self.name = name
        self.sk = Ed25519PrivateKey.generate()
        self.pk = self.sk.public_key()

    def commit(self, exam_id, start, end, items, salt, published_at):
        rec = dict(exam_id=exam_id, window_start=start, window_end=end,
                   items_hash=items_commitment(items, salt), authority=self.name,
                   published_at=published_at)
        msg = json.dumps(rec, sort_keys=True).encode()
        return dict(record=rec, sig=self.sk.sign(msg).hex())


class Provider:
    def __init__(self, directory):
        self.directory = directory        # name -> public key bytes
        self.records = {}

    def ingest(self, signed):
        """Accept a published record only if every rule holds. Returns reason."""
        rec, sig = signed["record"], bytes.fromhex(signed["sig"])
        pkb = self.directory.get(rec["authority"])
        if pkb is None:
            return "reject:unaccredited"
        try:
            Ed25519PublicKey.from_public_bytes(pkb).verify(sig, json.dumps(rec, sort_keys=True).encode())
        except InvalidSignature:
            return "reject:bad_signature"
        if rec["window_end"] - rec["window_start"] > MAX_WINDOW:
            return "reject:window_too_long"
        if rec["published_at"] >= rec["window_start"]:
            return "reject:retroactive"
        self.records[rec["exam_id"]] = rec
        return "accepted"

    def decide(self, image_rgb, now):
        a, _ = E.decode_aruco(E.yellowness_masked(image_rgb))
        if a in (None, -2):
            a, _ = E.decode_aruco(cv2.cvtColor(image_rgb, cv2.COLOR_RGB2GRAY))
        if a in (None, -2):
            return "ALLOW", "no_marker"
        rec = self.records.get(a)
        if rec is None:
            return "ALLOW", "unknown_exam"
        if rec["window_start"] <= now <= rec["window_end"]:
            return "REFUSE", "in_window"
        return "ALLOW", "outside_window"


def verify_reveal(rec, items, salt):
    return items_commitment(items, salt) == rec["items_hash"]


# ------------------------------------------------------------- benign pages
def benign_page(kind, rng):
    """Pages a student might legitimately photograph, designed to stress the
    detector: yellow highlighter over text, yellow sticky notes, dense yellow
    dot or checker textures, and printed QR-like blocks."""
    text = E.text_layer(rng)
    page = np.ones((E.PH, E.PW, 3), np.float32)
    if kind == "highlighter":
        for _ in range(int(rng.integers(8, 20))):
            y = int(rng.integers(140, E.PH - 140)); x = int(rng.integers(100, E.PW - 400))
            w = int(rng.integers(150, 600)); h = int(rng.integers(18, 30))
            page[y:y + h, x:x + w] *= np.array([1, 1, 1 - rng.uniform(0.4, 0.9)], np.float32)
    elif kind == "sticky":
        for _ in range(int(rng.integers(2, 6))):
            s = int(rng.integers(150, 300)); y = int(rng.integers(0, E.PH - s)); x = int(rng.integers(0, E.PW - s))
            page[y:y + s, x:x + s] *= np.array([1, 0.95, 0.35], np.float32)
    elif kind == "texture":
        cell = int(rng.integers(4, 12))
        yy, xx = np.mgrid[0:E.PH, 0:E.PW]
        pat = (((yy // cell) + (xx // cell)) % 2 == 0) if rng.random() < 0.5 else (rng.random((E.PH, E.PW)) < 0.3)
        page[pat] *= np.array([1, 1, 0.3], np.float32)
    elif kind == "blocks":   # random binary blocks resembling fiducials, in black and in yellow
        for _ in range(int(rng.integers(20, 60))):
            n = int(rng.integers(4, 8)); c = int(rng.integers(5, 12))
            bits = rng.random((n, n)) < 0.5
            blk = np.kron(bits, np.ones((c, c))).astype(bool)
            y = int(rng.integers(0, E.PH - blk.shape[0])); x = int(rng.integers(0, E.PW - blk.shape[1]))
            col = np.array([0.1, 0.1, 0.1] if rng.random() < 0.5 else [1, 1, 0.3], np.float32)
            sub = page[y:y + blk.shape[0], x:x + blk.shape[1]]
            sub[blk] = sub[blk] * col
    page *= (1 - 0.92 * text)[..., None]
    return E.print_sim(page, rng)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--benign", type=int, default=100, help="captures per benign kind")
    ap.add_argument("--marked", type=int, default=60)
    ap.add_argument("--out", default="e2_out")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    rng = np.random.default_rng(20261116)
    res = {}

    # ---- protocol unit scenarios -------------------------------------------
    kice, rogue = Authority("KICE"), Authority("ROGUE")
    directory = {"KICE": pub_bytes(kice.pk)}
    prov = Provider(directory)
    T0 = 1_000_000_000                              # exam window start (abstract clock)
    items = [f"question {i}" for i in range(45)]
    salt = os.urandom(16)
    good = kice.commit(E.EXAM_ID, T0, T0 + 8 * HOUR, items, salt, published_at=T0 - 48 * HOUR)
    scen = {}
    scen["valid_record"] = prov.ingest(good)
    forged = dict(good); forged["record"] = dict(good["record"], window_end=T0 + 30 * 24 * HOUR)
    scen["tampered_record"] = Provider(directory).ingest(forged)
    scen["unaccredited_authority"] = Provider(directory).ingest(
        rogue.commit(0x1234, T0, T0 + HOUR, items, salt, T0 - HOUR))
    scen["window_too_long"] = Provider(directory).ingest(
        kice.commit(0x2222, T0, T0 + 30 * 24 * HOUR, items, salt, T0 - HOUR))
    scen["retroactive_registration"] = Provider(directory).ingest(
        kice.commit(0x3333, T0, T0 + HOUR, items, salt, T0 + 10))
    scen["reveal_matches"] = verify_reveal(good["record"], items, salt)
    scen["reveal_altered_question"] = verify_reveal(good["record"], items[:-1] + ["question X"], salt)
    scen["reveal_wrong_salt"] = verify_reveal(good["record"], items, os.urandom(16))
    res["protocol"] = scen
    print("protocol", json.dumps(scen, indent=1), flush=True)

    # ---- decisions on captured images --------------------------------------
    pages = E.build_pages(20261115, 0.7)
    p = dict(E.BASE)
    t_dec = []

    def cap(page, seed, params=p):
        return E.capture(page, params, np.random.default_rng(seed))

    timing = {}
    for Wc in (1280, 1920, 4032):
        ts = []
        for k in range(5):
            img = cap(pages["M2"], 900 + k, dict(p, Wc=Wc))
            t = time.perf_counter(); prov.decide(img, T0 + HOUR); ts.append(time.perf_counter() - t)
        timing[Wc] = dict(median_s=float(np.median(ts)), max_s=float(np.max(ts)))
    res["decision_time"] = timing
    print("timing", timing, flush=True)

    marked = {}
    for name, now in [("in_window", T0 + HOUR), ("after_window", T0 + 9 * HOUR), ("before_window", T0 - HOUR)]:
        out = {"REFUSE": 0, "ALLOW": 0}
        for k in range(a.marked):
            d, _ = prov.decide(cap(pages["M2"], 5000 + k), now)
            out[d] += 1
        marked[name] = out
        print("marked", name, out, flush=True)
    # copy attack: marker of the exam pasted on unrelated study material,
    # is refused only inside the window, by design; measured for completeness
    res["marked_page"] = marked

    benign = {}
    for kind in ("plain", "highlighter", "sticky", "texture", "blocks"):
        refuse, reasons = 0, {}
        for k in range(a.benign):
            r = np.random.default_rng(7000 + 1000 * len(benign) + k)
            page = pages["M0"] if kind == "plain" else benign_page(kind, r)
            img = E.capture(page, dict(p, view=float(r.uniform(0.25, 1.0)), Wc=int(r.choice([1280, 1920]))), r)
            d, why = prov.decide(img, T0 + HOUR)
            refuse += d == "REFUSE"; reasons[why] = reasons.get(why, 0) + 1
            if kind != "plain" and k == 0:
                cv2.imwrite(f"{a.out}/benign_{kind}.jpg", cv2.cvtColor(img, cv2.COLOR_RGB2BGR))
        benign[kind] = dict(n=a.benign, refused=refuse, reasons=reasons)
        print("benign", kind, benign[kind], flush=True)
    res["benign_in_window"] = benign
    json.dump(res, open(f"{a.out}/e2_results.json", "w"), indent=1)


if __name__ == "__main__":
    main()
