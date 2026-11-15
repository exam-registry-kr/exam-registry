"""Apply the printed exam marker to page 1 of a real exam PDF (A3, 150 dpi)."""
import sys, numpy as np, cv2
import e1_sim as E

src = cv2.cvtColor(cv2.imread(sys.argv[1] if len(sys.argv) > 1 and sys.argv[1].endswith(".png") else "page.png"), cv2.COLOR_BGR2RGB).astype(np.float32) / 255
PH, PW = src.shape[:2]
M, P, BIG = E.MARKER_PX, E.PERIOD_PX, 96

def chunk_img(idx, size):
    v = (E.payload(E.EXAM_ID) >> (E.BITS * idx)) & ((1 << E.BITS) - 1)
    return (cv2.aruco.generateImageMarker(E.ARUCO, idx * (1 << E.BITS) + v, size) < 128).astype(np.float32)

def big_slots():
    xs = [int(v) for v in np.linspace(150, PW - 150 - BIG, 5)]
    ys = [int(v) for v in np.linspace(PH * 0.3, PH * 0.7 - BIG, 3)]
    return [(x, 30) for x in xs] + [(PW - 30 - BIG, y) for y in ys] + \
           [(x, PH - 30 - BIG) for x in xs[::-1]] + [(30, y) for y in ys[::-1]]

def marker_mask(big=True):
    m = np.zeros((PH, PW), np.float32); keep = np.zeros((PH, PW), bool)
    if big:
        for x0, y0 in big_slots():
            keep[max(0, y0 - 24):y0 + BIG + 24, max(0, x0 - 24):x0 + BIG + 24] = True
    off = (P - M) // 2
    for r in range(PH // P):
        for c in range(PW // P):
            y0, x0 = r * P + off, c * P + off
            if keep[y0:y0 + M, x0:x0 + M].any(): continue
            m[y0:y0 + M, x0:x0 + M] = chunk_img((c + 3 * r) % E.NCHUNK, M)
    if big:
        for k, (x0, y0) in enumerate(big_slots()):
            m[y0:y0 + BIG, x0:x0 + BIG] = chunk_img(k % E.NCHUNK, BIG)
    return m

def apply(ink):
    tint = np.array([1, 1, 1 - ink], np.float32)          # yellow: absorbs blue only
    return np.clip(src * (1 - marker_mask()[..., None] * (1 - tint)), 0, 1)

if __name__ == "__main__":
    for ink in (0.7, 0.35, 0.2):
        out = apply(ink)
        cv2.imwrite(f"sample_ink{int(ink*100):02d}.png", cv2.cvtColor((out * 255).astype(np.uint8), cv2.COLOR_RGB2BGR))
    print(PW, PH)
