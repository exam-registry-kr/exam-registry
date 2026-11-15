import json, sys, zlib, numpy as np, cv2
import e1_sim as E, e2_protocol as P, e5_legibility as F, e5_enh as X
res = {}
for kind in sys.argv[1:]:
    rng = np.random.default_rng(zlib.crc32(kind.encode()))
    hits = 0
    for i in range(int(__import__("os").environ.get("NP", 40))):
        page = P.benign_page(kind, rng)
        for Wc, view in [(1280, 1.0), (640, 0.25)]:
            img = E.capture(page, dict(E.BASE, Wc=Wc, view=view), rng)
            m, n = X.match_enh(img, F.ACTIVE); hits += m is not None
    res[kind] = dict(captures=2*int(__import__("os").environ.get("NP", 40)), matches=hits); print(kind, res[kind], flush=True)
json.dump(res, open(f"e5_fp2_{sys.argv[1]}.json", "w"), indent=1)
