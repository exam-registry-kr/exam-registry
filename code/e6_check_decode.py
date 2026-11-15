"""Quick decode check of the real-page sample under simulated capture (not the full E1 sweep)."""
import sys, json, numpy as np, cv2
import e1_sim as E, e5_legibility as F, e5_enh as X
import e6_make_sample as S
E.PW, E.PH = S.PW, S.PH                      # capture() reads the page size from module globals
res = {}
for ink in [float(a) for a in sys.argv[1:]] or (0.2, 0.12):
    page = E.print_sim(S.apply(ink), np.random.default_rng(1))
    for view, Wc in ((1.0, 1280), (0.5, 960), (0.25, 640), (0.25, 480)):
        ok = okenh = 0; n = 10
        for t in range(n):
            rng = np.random.default_rng(1000 * t + int(view * 100) + Wc)
            img = E.capture(page, dict(E.BASE, view=view, Wc=Wc), rng)
            ok += E.match_active(E.yellowness_masked(img), F.ACTIVE) == E.EXAM_ID or \
                  E.match_active(cv2.cvtColor(img, cv2.COLOR_RGB2GRAY), F.ACTIVE) == E.EXAM_ID
            okenh += X.match_enh(img, F.ACTIVE)[0] == E.EXAM_ID
        res[f"ink{ink}_view{view}_W{Wc}"] = dict(n=n, partial=ok, final=okenh)
        print(ink, view, Wc, ok, okenh, flush=True)
json.dump(res, open("E6-001_realpage_check_" + "_".join(sys.argv[1:]) + ".json", "w"), indent=1)
