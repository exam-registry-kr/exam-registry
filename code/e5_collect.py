"""Merge e5_legibility.py outputs and add the final (enhanced) decoder result.

    python e5_legibility.py --seed 5050 --out e5_s5050
    python e5_legibility.py --seed 6060 --out e5_s6060
    python e5_collect.py e5_s5050 e5_s6060          # writes E5-001_rows.json

Columns
  marker         full six-chunk decode (first decoder)
  marker_partial >= 4 chunks agreeing with an exam whose window is open
  marker_enh     partial decode, retried on enhanced copies of the photo (final decoder)
  readable       question text read with character error rate <= 0.10
  numbers_ok     every number in the question read correctly
  em_px          height of 10 pt text in photo pixels
A "gap" is a photo whose text is readable or whose numbers are read, but whose marker fails.
"""
import json, sys, zlib, numpy as np
import e1_sim as E, e5_legibility as F, e5_enh as X

rows = []
for d in sys.argv[1:]:
    R = json.load(open(f"{d}/e5_rows.json"))
    page, qs = F.page_with_marker(R["seed"])
    for r in R["rows"]:
        r["seed"] = R["seed"]
        if r["marker_partial"]:
            r["marker_enh"] = 1
        else:
            q = qs[(r["t"] * 3) % len(qs)]; bx = q["box"]; c = ((bx[0] + bx[2]) / 2, (bx[1] + bx[3]) / 2)
            p = dict(E.BASE, view=r["view"], Wc=r["Wc"], defocus=r["blur"], tilt=20)
            g = np.random.default_rng(r["seed"] * 10 + zlib.crc32(f"{r['view']}|{r['Wc']}|{r['blur']}|{r['t']}".encode()) % 100000)
            img = F.capture_at(page, p, g, c, {})
            m, _ = X.match_enh(img, F.ACTIVE)
            r["marker_enh"] = int(m == E.EXAM_ID)
        rows.append(r)

gap = lambda r, k: (r["readable"] or r["numbers_ok"]) and not r[k]
for k in ("marker", "marker_partial", "marker_enh"):
    print(f"{k:15s} gaps {sum(gap(r, k) for r in rows)}/{len(rows)}")
json.dump(rows, open("E5-001_rows.json", "w"), indent=1)
