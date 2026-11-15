import sys, numpy as np, cv2, json
sys.path.insert(0, '.')
import e1_sim as E, e2_protocol as P, e5_legibility as F
rng = np.random.default_rng(99)
res = {}
for kind in ["highlighter", "sticky", "texture", "blocks"]:
    hits = raw = 0
    for i in range(40):
        page = P.benign_page(kind, rng)
        for Wc, view in [(1280, 1.0), (640, 0.25)]:
            img = E.capture(page, dict(E.BASE, Wc=Wc, view=view), rng)
            for g in (E.yellowness_masked(img), cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)):
                m = E.match_active(g, F.ACTIVE, min_chunks=4)
                hits += m is not None
                v = E.chunk_votes(E.detect_multiscale(g)); raw += sum(1 for x in v if x)
    res[kind] = dict(pages=40, captures=80, partial_matches=hits, seen_chunk_total=raw)
    print(kind, res[kind], flush=True)
json.dump(res, open("e5_fp.json", "w"), indent=1)
