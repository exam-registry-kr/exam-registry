"""E1: printed exam marker survival under simulated print-and-capture.

Markers compared on the same synthetic exam page (one marker type per page):
  M0      : no marker (false-positive control)
  M1      : single black QR code in the top-right margin (standard baseline)
  M2      : tiled yellow ArUco markers over the whole page, decoded on a
            "yellowness" channel ((R+G)/2 - B) that suppresses black text
  M2gray  : same printed page as M2 but decoded on plain grayscale (ablation:
            what the yellowness channel buys)
  M2final : M2 on the yellowness channel, falling back to grayscale. This is the
            "marker" result reported for E1.
  M3      : PDF render-parse watermark (Integrity Shield / DoPE style). Not
            simulated: its signal lives in the PDF text layer, which printing
            removes by construction, so its detection after print is 0.

Payload: 32-bit exam ID + 10-bit CRC = 42 bits, split into 6 chunks of 7 bits.
Marker id = chunk*128+value (ArUco 4x4_1000 dictionary). Tiling uses
idx=(col+3*row)%6 so any 3x2 neighbourhood carries the full payload.

Design notes:
  * Black exam text printed over a yellow marker reads as "white" in the
    yellowness channel and punches holes in marker cells. Two fixes adopted:
    (a) 4x4 dictionary with 8 px cells instead of 5x5 with 6 px cells,
    (b) text pixels (dark in every channel) are masked and inpainted before
        detection, i.e. treated as missing rather than as paper.
  * M2nomask = M2 decoded without the text mask (ablation of fix b).
"""
import argparse, json, os, time, zlib
import numpy as np, cv2

DPI = 150
PW, PH = 1240, 1754            # A4 at 150 dpi
ARUCO = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_1000)
DET_PARAMS = cv2.aruco.DetectorParameters()
DETECTOR = cv2.aruco.ArucoDetector(ARUCO, DET_PARAMS)
QRDETS = (cv2.QRCodeDetector(), cv2.QRCodeDetectorAruco())   # baseline gets both

MARKER_PX = 48                 # 8.1 mm (6 cells x 8 px)
PERIOD_PX = 120                # 20.3 mm tile period
EXAM_ID = 0x5A17C0DE           # arbitrary 32-bit test ID
NCHUNK, BITS, CRCBITS = 6, 7, 10


def payload(exam_id):
    return exam_id | ((zlib.crc32(exam_id.to_bytes(4, "big")) & ((1 << CRCBITS) - 1)) << 32)


def unpack(val):
    """Return exam id if checksum matches, else -2 (detected but invalid)."""
    eid = val & 0xFFFFFFFF
    return eid if payload(eid) == val else -2


# ---------------------------------------------------------------- page
def text_layer(rng):
    """Synthetic exam text as an ink mask (1 = black ink)."""
    m = np.zeros((PH, PW), np.uint8)
    y = 150
    letters = "abcdefghijklmnopqrstuvwxyz0123456789()+-=?"
    while y < PH - 120:
        if rng.random() < 0.08:                         # figure / answer box
            h = int(rng.integers(120, 260))
            cv2.rectangle(m, (160, y), (PW - 160, min(y + h, PH - 120)), 1, 2)
            y += h + 30
            continue
        x = 130
        while x < PW - 200:
            w = "".join(rng.choice(list(letters), int(rng.integers(2, 9))))
            cv2.putText(m, w, (x, y), cv2.FONT_HERSHEY_SIMPLEX, 0.62, 1, 2, cv2.LINE_AA)
            x += 15 * len(w) + 14
        y += 34
    return m.astype(np.float32)


BIG_PX = 96                    # 16.3 mm margin markers
USE_BIG = True


def big_marker_slots():
    """Margin positions (x0, y0) for large markers: 4 on top and bottom
    margins, 2 on each side margin. Chunk index cycles 0..5 around the page."""
    xs = [int(v) for v in np.linspace(140, PW - 140 - BIG_PX, 4)]
    ys = [int(v) for v in np.linspace(PH * 0.3, PH * 0.7 - BIG_PX, 2)]
    slots = [(x, 14) for x in xs] + [(PW - 14 - BIG_PX, y) for y in ys] + \
            [(x, PH - 14 - BIG_PX) for x in xs[::-1]] + [(14, y) for y in ys[::-1]]
    return slots


def aruco_tile_mask():
    """Tiled marker ink mask (1 = ink) and list of chunk layout."""
    m = np.zeros((PH, PW), np.float32)
    off = (PERIOD_PX - MARKER_PX) // 2
    keepout = np.zeros((PH, PW), bool)
    if USE_BIG:
        for x0, y0 in big_marker_slots():
            keepout[max(0, y0 - 24):y0 + BIG_PX + 24, max(0, x0 - 24):x0 + BIG_PX + 24] = True
    for r in range(PH // PERIOD_PX):
        for c in range(PW // PERIOD_PX):
            idx = (c + 3 * r) % NCHUNK
            v = (payload(EXAM_ID) >> (BITS * idx)) & ((1 << BITS) - 1)
            img = cv2.aruco.generateImageMarker(ARUCO, idx * (1 << BITS) + v, MARKER_PX)
            y0, x0 = r * PERIOD_PX + off, c * PERIOD_PX + off
            if keepout[y0:y0 + MARKER_PX, x0:x0 + MARKER_PX].any():
                continue
            m[y0:y0 + MARKER_PX, x0:x0 + MARKER_PX] = (img < 128).astype(np.float32)
    if USE_BIG:
        for k, (x0, y0) in enumerate(big_marker_slots()):
            idx = k % NCHUNK
            v = (payload(EXAM_ID) >> (BITS * idx)) & ((1 << BITS) - 1)
            img = cv2.aruco.generateImageMarker(ARUCO, idx * (1 << BITS) + v, BIG_PX)
            m[y0:y0 + BIG_PX, x0:x0 + BIG_PX] = (img < 128).astype(np.float32)
    return m


QR_SIDE, QR_X0, QR_Y0 = 160, PW - 20 - 160, 20


def qr_visible(meta):
    """Oracle upper bound for any QR decoder: whole QR inside frame, unoccluded."""
    pts = np.float32([[QR_X0 + dx, QR_Y0 + dy] for dx in np.linspace(0, QR_SIDE, 5)
                      for dy in np.linspace(0, QR_SIDE, 5)]).reshape(-1, 1, 2)
    q = cv2.perspectiveTransform(pts, meta["H"]).reshape(-1, 2)
    Wc, Hc = meta["size"]
    if (q[:, 0] < 0).any() or (q[:, 0] >= Wc).any() or (q[:, 1] < 0).any() or (q[:, 1] >= Hc).any():
        return 0
    return int(meta["occ"][q[:, 1].astype(int), q[:, 0].astype(int)].max() == 0)


def qr_mask():
    enc = cv2.QRCodeEncoder.create()
    q = enc.encode("EXAM:%08X" % EXAM_ID)
    side = 160                                            # 27 mm
    q = cv2.resize(q, (side, side), interpolation=cv2.INTER_NEAREST)
    m = np.zeros((PH, PW), np.float32)
    m[20:20 + side, PW - 20 - side:PW - 20] = (q < 128).astype(np.float32)
    return m


def compose(text, marker, ink_rgb_reflect):
    """Subtractive print model: paper * marker ink * black ink. float RGB 0..1."""
    page = np.ones((PH, PW, 3), np.float32)
    if marker is not None:
        refl = np.array(ink_rgb_reflect, np.float32)
        page *= 1 - marker[..., None] * (1 - refl)
    page *= (1 - 0.92 * text)[..., None]
    return page


def print_sim(page, rng):
    page = cv2.GaussianBlur(page, (0, 0), 0.7)            # dot gain
    page *= 1 + rng.normal(0, 0.015, page.shape[:2]).astype(np.float32)[..., None]
    return np.clip(page, 0, 1)


# ---------------------------------------------------------------- capture
def capture(page, p, rng, meta=None):
    """Project a sub-region of the printed page into a camera frame."""
    Wc = int(p["Wc"]); Hc = Wc * 3 // 4
    # view = framed height as a fraction of page height (1.0 = whole page in frame,
    # landscape 4:3 camera so the page sits between table margins)
    rh = p["view"] * PH; rw = rh * 4 / 3
    cx = rng.uniform(rw / 2, PW - rw / 2) if rw < PW else PW / 2
    cy = rng.uniform(rh / 2, PH - rh / 2) if rh < PH else PH / 2
    if meta is not None and "center" in meta:          # E5: frame a chosen point (clipped to page)
        cx = float(np.clip(meta["center"][0], min(rw / 2, PW / 2), max(PW - rw / 2, PW / 2)))
        cy = float(np.clip(meta["center"][1], min(rh / 2, PH / 2), max(PH - rh / 2, PH / 2)))
    th = np.deg2rad(p["tilt"]); rot = rng.uniform(-12, 12)
    # region corners in page coords, centred
    src = np.array([[-rw/2, -rh/2], [rw/2, -rh/2], [rw/2, rh/2], [-rw/2, rh/2]], np.float32)
    a = np.deg2rad(rot); R2 = np.array([[np.cos(a), -np.sin(a)], [np.sin(a), np.cos(a)]])
    src = src @ R2.T
    # 3D tilt about x axis, pinhole projection
    D = 2.2 * max(rw, rh)
    pts3 = np.c_[src[:, 0], src[:, 1] * np.cos(th), src[:, 1] * np.sin(th) + D]
    proj = pts3[:, :2] / pts3[:, 2:3]
    proj -= proj.mean(0)
    s = 0.95 * min(Wc / np.ptp(proj[:, 0]), Hc / np.ptp(proj[:, 1]))
    dst = (proj * s + [Wc / 2, Hc / 2]).astype(np.float32)
    src_page = (src + [cx, cy]).astype(np.float32)
    H = cv2.getPerspectiveTransform(src_page, dst)
    occ_mask = np.zeros((Hc, Wc), np.uint8)
    img = cv2.warpPerspective(page, H, (Wc, Hc), flags=cv2.INTER_AREA,
                              borderMode=cv2.BORDER_CONSTANT, borderValue=(0.35, 0.3, 0.25))
    # optics
    if p["defocus"] > 0:
        img = cv2.GaussianBlur(img, (0, 0), p["defocus"])
    if p.get("motion", 0) > 0:
        L = int(p["motion"]); k = np.zeros((L, L), np.float32); k[L // 2, :] = 1 / L
        k = cv2.warpAffine(k, cv2.getRotationMatrix2D((L / 2, L / 2), rng.uniform(0, 180), 1), (L, L))
        k /= max(k.sum(), 1e-6); img = cv2.filter2D(img, -1, k)
    # illumination: gradient + warm light (scales blue)
    gy, gx = np.mgrid[0:Hc, 0:Wc].astype(np.float32)
    g = 1 - p["shade"] * (gx / Wc * rng.uniform(0.3, 1) + gy / Hc * rng.uniform(0.3, 1)) / 2
    img = img * g[..., None] * np.array([1.0, 0.97, p["warm"]], np.float32)
    # channel crosstalk (sensor colour filter overlap)
    X = np.array([[0.86, 0.10, 0.04], [0.08, 0.84, 0.08], [0.04, 0.12, 0.84]], np.float32)
    img = img @ X.T
    # occlusion: hand-like ellipse
    if p["occl"] > 0:
        mask = np.zeros((Hc, Wc), np.uint8)
        ax = int(np.sqrt(p["occl"] * Wc * Hc / np.pi * 1.6)); ay = int(ax / 1.6)
        c0 = (int(rng.uniform(0, Wc)), int(rng.uniform(0, Hc)))
        cv2.ellipse(mask, c0, (ax, ay), rng.uniform(0, 180), 0, 360, 1, -1)
        occ_mask = mask
        img[mask > 0] = np.array([0.80, 0.60, 0.50], np.float32) * rng.uniform(0.7, 1)
    img = img + rng.normal(0, p["noise"] / 255, img.shape).astype(np.float32)
    if meta is not None:
        meta["H"], meta["occ"], meta["size"] = H, occ_mask, (Wc, Hc)
    img8 = (np.clip(img, 0, 1) * 255).astype(np.uint8)
    ok, buf = cv2.imencode(".jpg", cv2.cvtColor(img8, cv2.COLOR_RGB2BGR),
                           [cv2.IMWRITE_JPEG_QUALITY, int(p["jpeg"])])
    return cv2.cvtColor(cv2.imdecode(buf, cv2.IMREAD_COLOR), cv2.COLOR_BGR2RGB)


# ---------------------------------------------------------------- decoders
def yellowness(rgb):
    r, g, b = [rgb[..., i].astype(np.float32) for i in range(3)]
    y = (r + g) / 2 - b
    y = cv2.normalize(np.clip(y, 0, None), None, 0, 255, cv2.NORM_MINMAX)
    return (255 - y).astype(np.uint8)          # markers dark on light


def yellowness_masked(rgb):
    """Yellowness with black-ink pixels masked out and inpainted."""
    y = yellowness(rgb)
    mx = rgb.max(2)
    bg = cv2.medianBlur(cv2.dilate(mx, np.ones((15, 15), np.uint8)), 15)
    m = (mx.astype(np.float32) < 0.6 * bg).astype(np.uint8)
    m = cv2.dilate(m, np.ones((3, 3), np.uint8))
    return cv2.inpaint(y, m, 3, cv2.INPAINT_TELEA)


def detect_multiscale(gray):
    """Detect at several scales: ArUco's adaptive threshold windows are small, so
    very large markers (close-up, high resolution) are found after downscaling."""
    found = []
    h = gray.shape[0]
    for sc in (1.0, 0.5, 0.25):
        if h * sc < 240:
            break
        g = gray if sc == 1.0 else cv2.resize(gray, None, fx=sc, fy=sc, interpolation=cv2.INTER_AREA)
        _, ids, _ = DETECTOR.detectMarkers(g)
        if ids is not None:
            found.append(ids.flatten())
    return np.concatenate(found) if found else None


def decode_aruco(gray):
    ids = detect_multiscale(gray)
    if ids is None:
        return None, 0
    votes = [dict() for _ in range(NCHUNK)]
    for i in ids:
        idx, v = int(i) >> BITS, int(i) & ((1 << BITS) - 1)
        if idx < NCHUNK:
            votes[idx][v] = votes[idx].get(v, 0) + 1
    if any(len(v) == 0 for v in votes):
        return None, len(ids)
    val = 0
    for idx, v in enumerate(votes):
        val |= max(v, key=v.get) << (BITS * idx)
    return unpack(val), len(ids)


def decode_qr(rgb):
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    for det in QRDETS:
        txt = det.detectAndDecode(gray)[0]
        if txt and txt.startswith("EXAM:"):
            try:
                return int(txt[5:], 16)
            except ValueError:
                return -1
    return None


def visible_fraction(view):
    rh = view * PH; rw = rh * 4 / 3
    return min(rw, PW) * min(rh, PH) / (PW * PH)


# ---------------------------------------------------------------- experiment
BASE = dict(view=0.5, tilt=30, Wc=1280, defocus=1.0, motion=0, shade=0.3,
            warm=0.85, occl=0.0, noise=4, jpeg=75, ink=0.7)
SWEEPS = {
    "view":    [1.0, 0.7, 0.5, 0.35, 0.25, 0.18],
    "tilt":    [0, 20, 40, 55, 65],
    "Wc":      [1920, 1280, 960, 640, 480],
    "defocus": [0, 1, 2, 3, 4],
    "jpeg":    [95, 75, 50, 30, 15],
    "noise":   [0, 4, 8, 16, 24],
    "motion":  [0, 3, 5, 9, 13],
    "occl":    [0, 0.2, 0.4, 0.6],
    "ink":     [0.9, 0.7, 0.5, 0.35, 0.2],
    "warm":    [1.0, 0.85, 0.7, 0.55],
}


def mixed_params(rng):
    return dict(view=float(rng.uniform(0.18, 1.0)), tilt=float(rng.uniform(0, 55)),
                Wc=int(rng.choice([640, 960, 1280, 1920])), defocus=float(rng.uniform(0, 2.5)),
                motion=int(rng.choice([0, 0, 0, 5, 9])), shade=float(rng.uniform(0, 0.5)),
                warm=float(rng.uniform(0.6, 1.0)), occl=float(rng.choice([0, 0, 0.15, 0.3])),
                noise=float(rng.uniform(0, 12)), jpeg=int(rng.uniform(30, 95)),
                ink=float(rng.uniform(0.4, 0.9)))


def build_pages(seed, ink):
    rng = np.random.default_rng(seed)
    text = text_layer(rng)
    yel = (1.0, 1.0, 1.0 - ink)        # yellow ink: absorbs blue by 'ink'
    pages = {
        "M0": print_sim(compose(text, None, None), np.random.default_rng(seed + 1)),
        "M1": print_sim(compose(text, qr_mask(), (0.08, 0.08, 0.08)), np.random.default_rng(seed + 2)),
        "M2": print_sim(compose(text, aruco_tile_mask(), yel), np.random.default_rng(seed + 3)),
    }
    return pages


def score(v):
    """1 = correct ID, 0 = nothing decoded or checksum rejected (safe failure),
    -1 = a wrong ID that passed the checksum (unsafe)."""
    if v == EXAM_ID:
        return 1
    if v is None or v == -2:
        return 0
    return -1


def run_trial(pages, p, rng_seed):
    out = {}
    for name in ("M0", "M1", "M2"):
        rng = np.random.default_rng(rng_seed)       # same geometry for every page
        meta = {}
        img = capture(pages[name], p, rng, meta)
        if name == "M0":
            q = decode_qr(img); a, _ = decode_aruco(yellowness_masked(img))
            ag, _ = decode_aruco(cv2.cvtColor(img, cv2.COLOR_RGB2GRAY))
            # any decode, including checksum-rejected, counts as a false positive here
            out["M0_fp"] = int(q is not None or a is not None or ag is not None)
        elif name == "M1":
            q = decode_qr(img)
            out["M1vis"] = qr_visible(meta)
            out["M1"] = score(q)
        else:
            a, n = decode_aruco(yellowness_masked(img))
            out["M2"] = score(a)
            out["M2_crcrej"] = int(a == -2)
            out["M2_n"] = n
            c = np.float32([[[PW / 2, PH / 2]], [[PW / 2 + MARKER_PX, PH / 2]]])
            q = cv2.perspectiveTransform(c, meta["H"]).reshape(-1, 2)
            out["marker_px"] = float(np.linalg.norm(q[1] - q[0]))
            an, _ = decode_aruco(yellowness(img))
            out["M2nomask"] = score(an)
            ag, _ = decode_aruco(cv2.cvtColor(img, cv2.COLOR_RGB2GRAY))
            out["M2gray"] = score(ag)
            # final decoder: yellowness first (robust to text), luminance fallback
            # (luminance keeps full resolution when chroma is subsampled / tiny markers)
            fin = a if a not in (None, -2) else ag
            out["M2final"] = score(fin)
            out["M2final_crcrej"] = int(a == -2 or ag == -2)
    return out


def summarize(rows):
    s = {}
    for k in ("M1", "M2final", "M2", "M2nomask", "M2gray"):
        v = np.array([r[k] for r in rows])
        s[k] = dict(correct=float((v == 1).mean()), wrong=int((v == -1).sum()))
    s["M1vis"] = float(np.mean([r["M1vis"] for r in rows])) if rows else float("nan")
    s["M0_fp"] = int(sum(r["M0_fp"] for r in rows))
    s["n"] = len(rows)
    return s


def wilson(p, n, z=1.96):
    if n == 0: return (0, 0)
    d = 1 + z * z / n; c = (p + z * z / (2 * n)) / d
    h = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0, c - h), min(1, c + h))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--trials", type=int, default=40)
    ap.add_argument("--mixed", type=int, default=300)
    ap.add_argument("--grid", type=int, default=15)
    ap.add_argument("--factors", default=",".join(SWEEPS))
    ap.add_argument("--grid-views", default="1.0,0.7,0.5,0.35,0.25")
    ap.add_argument("--start", type=int, default=0, help="skip the first N values of each factor")
    ap.add_argument("--seed", type=int, default=20261115)
    ap.add_argument("--out", default="results")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    t0 = time.time()
    page_cache = {}

    def pages_for(ink):
        if ink not in page_cache:
            page_cache[ink] = build_pages(a.seed, ink)
        return page_cache[ink]

    results = {"config": dict(vars(a), exam_id="%08X" % EXAM_ID, base=BASE,
                              marker_px=MARKER_PX, period_px=PERIOD_PX, dpi=DPI),
               "sweeps": {}, "mixed": None}
    for factor in [f for f in a.factors.split(",") if f]:
        values = SWEEPS[factor]
        results["sweeps"][factor] = []
        for vi, v in enumerate(values):
            if vi < a.start:
                continue
            p = dict(BASE); p[factor] = v
            pages = pages_for(p["ink"])
            rows = [run_trial(pages, p, a.seed * 1000 + zlib.crc32(f"{factor}|{vi}|{t}".encode()) % 100000)
                    for t in range(a.trials)]
            s = summarize(rows); s["value"] = v
            if factor == "view":
                s["visible_page_fraction"] = visible_fraction(v)
            for k in ("M1", "M2final", "M2", "M2nomask", "M2gray"):
                s[k]["ci95"] = wilson(s[k]["correct"], s["n"])
            s["rows"] = rows
            results["sweeps"][factor].append(s)
            json.dump(results, open(os.path.join(a.out, "e1_results.json"), "w"), indent=1)
            print(f"{factor:8s}={v!s:6s} M1={s['M1']['correct']:.2f} M2final={s['M2final']['correct']:.2f} M2={s['M2']['correct']:.2f} "
                  f"M2nomask={s['M2nomask']['correct']:.2f} M2gray={s['M2gray']['correct']:.2f} wrong(M1,M2final)={s['M1']['wrong']},{s['M2final']['wrong']} "
                  f"M1vis={s['M1vis']:.2f} FP={s['M0_fp']}  [{time.time()-t0:.0f}s]", flush=True)
    # operating map: framing x camera resolution (the two factors glasses vary most)
    results["grid"] = []
    if a.grid > 0:
        for view in [float(v) for v in a.grid_views.split(",") if v]:
            for Wc in (640, 1280, 1920, 3024, 4032):
                p = dict(BASE, view=view, Wc=Wc)
                pages = pages_for(p["ink"])
                rows = [run_trial(pages, p, a.seed * 3 + zlib.crc32(f"g|{view}|{Wc}|{t}".encode()) % 100000)
                        for t in range(a.grid)]
                s = summarize(rows); s.update(view=view, Wc=Wc,
                                              visible_page_fraction=visible_fraction(view),
                                              marker_px=float(np.mean([r["marker_px"] for r in rows])))
                s["rows"] = rows
                results["grid"].append(s)
                json.dump(results, open(os.path.join(a.out, "e1_results.json"), "w"), indent=1)
                print(f"grid view={view} Wc={Wc} marker_px={s['marker_px']:.0f} M1={s['M1']['correct']:.2f} "
                      f"M1vis={s['M1vis']:.2f} M2final={s['M2final']['correct']:.2f} M2={s['M2']['correct']:.2f} M2gray={s['M2gray']['correct']:.2f} FP={s['M0_fp']} [{time.time()-t0:.0f}s]", flush=True)
    if a.mixed == 0:
        results["runtime_s"] = time.time() - t0
        json.dump(results, open(os.path.join(a.out, "e1_results.json"), "w"), indent=1)
        return
    rng = np.random.default_rng(a.seed + 7)
    rows, plist = [], []
    for t in range(a.mixed):
        p = mixed_params(rng); p["ink"] = round(p["ink"] * 10) / 10
        plist.append(p)
        rows.append(run_trial(pages_for(p["ink"]), p, a.seed * 7 + t))
    s = summarize(rows)
    for k in ("M1", "M2final", "M2", "M2nomask", "M2gray"):
        s[k]["ci95"] = wilson(s[k]["correct"], s["n"])
    results["mixed"] = s
    with open(os.path.join(a.out, "mixed_trials.jsonl"), "w") as f:
        for p, r in zip(plist, rows):
            f.write(json.dumps({"params": p, "result": r}) + "\n")
    print("MIXED", json.dumps(s), flush=True)
    results["runtime_s"] = time.time() - t0
    with open(os.path.join(a.out, "e1_results.json"), "w") as f:
        json.dump(results, f, indent=1)


# ---------------------------------------------------------------- partial match (E5)
def chunk_votes(ids):
    votes = [dict() for _ in range(NCHUNK)]
    for i in (ids if ids is not None else []):
        idx, v = int(i) >> BITS, int(i) & ((1 << BITS) - 1)
        if idx < NCHUNK:
            votes[idx][v] = votes[idx].get(v, 0) + 1
    return votes


def match_active(gray, active_ids, min_chunks=4):
    """Partial decode against the exam IDs whose windows are open now.

    A provider already holds the list of committed, currently open exam IDs.
    Instead of requiring all six chunks, accept an ID when at least `min_chunks`
    chunks are seen and every seen chunk's majority value equals that ID's
    chunk. With 4 chunks this is a 28-bit agreement (chance 2^-28 per active ID
    for a random page). Returns the matched ID or None."""
    votes = chunk_votes(detect_multiscale(gray))
    seen = {k: max(v, key=v.get) for k, v in enumerate(votes) if v}
    if len(seen) < min_chunks:
        return None
    for eid in active_ids:
        pv = payload(eid)
        if all(((pv >> (BITS * k)) & ((1 << BITS) - 1)) == val for k, val in seen.items()):
            return eid
    return None


if __name__ == "__main__":
    main()
