"""E5 stage 2: regenerate the pre-ruled 36 photos for the vision-LLM reading test.

Rule (fixed before any model sees an image):
  A 20 critical: marker fails with the final decoder (partial match + enhancement);
                 largest glyph size first (most likely to be legible), at most 7 per framing.
  B 10 near-boundary passes: marker succeeds, glyph >= 6 px; every 7th from the smallest.
  C  2 duplicates of the first two A images (consistency of the reader).
  D  4 high-resolution controls: glyph >= 25 px (the reader should solve these).
Files get random names; the key stays here until scoring is done.
"""
import json, os, secrets, zlib, numpy as np, cv2
import e1_sim as E, e5_legibility as F

R = json.load(open("../results/E5-001_rows.json"))
fail = sorted([r for r in R if not r["marker_enh"]], key=lambda r: (-r["em_px"], r["cer"]))
A, per = [], {}
for r in fail:
    if per.get(r["view"], 0) < 7 and len(A) < 20:
        A.append(r); per[r["view"]] = per.get(r["view"], 0) + 1
B = sorted([r for r in R if r["marker_enh"] and r["em_px"] >= 6], key=lambda r: r["em_px"])[::7][:10]
rng = np.random.default_rng(42)
big = [r for r in R if r["em_px"] >= 25 and r["marker_enh"]]
D = [big[i] for i in rng.choice(len(big), 4, replace=False)]
sel = [("A", r) for r in A] + [("B", r) for r in B] + [("C", r) for r in A[:2]] + [("D", r) for r in D]

pages = {}
os.makedirs("e5_stage2/images", exist_ok=True)
key = []
order = np.random.default_rng(2027).permutation(len(sel))
for n, i in enumerate(order, 1):
    grp, r = sel[i]
    if r["seed"] not in pages:
        pages[r["seed"]] = F.page_with_marker(r["seed"])
    page, qs = pages[r["seed"]]
    q = qs[(r["t"] * 3) % len(qs)]
    bx = q["box"]; c = ((bx[0] + bx[2]) / 2, (bx[1] + bx[3]) / 2)
    p = dict(E.BASE, view=r["view"], Wc=r["Wc"], defocus=r["blur"], tilt=20)
    g = np.random.default_rng(r["seed"] * 10 + zlib.crc32(f"{r['view']}|{r['Wc']}|{r['blur']}|{r['t']}".encode()) % 100000)
    meta = {}
    img = F.capture_at(page, p, g, c, meta)
    name = f"{n:02d}_{secrets.token_hex(3)}.png"
    cv2.imwrite(f"e5_stage2/images/{name}", cv2.cvtColor(img, cv2.COLOR_RGB2BGR))
    key.append(dict(photo=n, file=name, group=grp, seed=r["seed"], view=r["view"], Wc=r["Wc"], blur=r["blur"], t=r["t"],
                    q=q["n"], question=q["text"], answer=q["answer"], marker=r["marker"], marker_partial=r["marker_partial"], marker_enh=r["marker_enh"],
                    tesseract_cer=r["cer"], em_px=r["em_px"]))
json.dump(key, open("e5_stage2/answer_key.json", "w"), ensure_ascii=False, indent=1)
for k in sorted(key, key=lambda k: k["group"]):
    print(k["photo"], k["group"], k["view"], k["Wc"], k["blur"], "q", k["q"], "cer", k["tesseract_cer"], "em", k["em_px"], "mk", k["marker_partial"])
