"""Figures for E1 from results_s1/e1_results.json and both mixed runs."""
import json, sys, os
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

OURS, QR = "#2a78d6", "#eb6834"
INK, MUTED, GRID = "#1f1f1e", "#6b6a64", "#e4e3de"
plt.rcParams.update({"font.size": 9, "axes.edgecolor": MUTED, "axes.labelcolor": INK,
                     "xtick.color": MUTED, "ytick.color": MUTED, "axes.spines.top": False,
                     "axes.spines.right": False, "axes.grid": True, "grid.color": GRID,
                     "grid.linewidth": 0.6, "lines.linewidth": 2})

R = json.load(open(sys.argv[1]))
out = sys.argv[2]
os.makedirs(out, exist_ok=True)

LABEL = {"view": "Page height in frame (fraction)", "tilt": "Tilt (deg)", "Wc": "Camera width (px)",
         "defocus": "Defocus blur sigma (px)", "jpeg": "JPEG quality", "noise": "Sensor noise (8-bit sigma)",
         "occl": "Occluded frame fraction", "motion": "Motion blur length (px)", "ink": "Yellow ink absorption", "warm": "Blue light level (warm light)"}

fig, axes = plt.subplots(2, 5, figsize=(13, 5.6), constrained_layout=True)
for ax, (f, pts) in zip(axes.flat, R["sweeps"].items()):
    x = [p["value"] for p in pts]
    xs = np.arange(len(x))
    m2 = [p["M2final"]["correct"] for p in pts]
    lo = [p["M2final"]["ci95"][0] for p in pts]; hi = [p["M2final"]["ci95"][1] for p in pts]
    ax.fill_between(xs, lo, hi, color=OURS, alpha=0.15, linewidth=0)
    ax.plot(xs, m2, color=OURS, marker="o", ms=4, label="Tiled yellow marker (ours)")
    ax.plot(xs, [p["M1"]["correct"] for p in pts], color=QR, marker="s", ms=4, label="Single QR, decoded")
    ax.plot(xs, [p["M1vis"] for p in pts], color=QR, ls="--", lw=1.5,
            label="Single QR, fully in frame (not decoded)")
    ax.set_xticks(xs); ax.set_xticklabels([str(v) for v in x])
    ax.set_ylim(-0.03, 1.03); ax.set_xlabel(LABEL[f])
    ax.set_title(f"n={pts[0]['n']} per point", fontsize=8, color=MUTED, loc="right")
axes[0, 0].set_ylabel("Exam ID recovered"); axes[1, 0].set_ylabel("Exam ID recovered")
h, l = axes[0, 0].get_legend_handles_labels()
fig.legend(h, l, loc="outside upper center", ncol=3, frameon=False)
fig.savefig(f"{out}/fig_e1_sweeps.png", dpi=200)

# operating map
g = R["grid"]
views = sorted({c["view"] for c in g}, reverse=True); ws = sorted({c["Wc"] for c in g})
fig, axs = plt.subplots(1, 2, figsize=(9, 3.6), constrained_layout=True)
for ax, key, title in [(axs[0], "M2final", "Tiled yellow marker (ours)"), (axs[1], "M1", "Single QR, decoded")]:
    Z = np.array([[next(c for c in g if c["view"] == v and c["Wc"] == w)[key]["correct"] for w in ws] for v in views])
    im = ax.imshow(Z, vmin=0, vmax=1, cmap="Blues", aspect="auto")
    for i, v in enumerate(views):
        for j, w in enumerate(ws):
            c = next(c for c in g if c["view"] == v and c["Wc"] == w)
            txt = f"{Z[i, j]:.2f}"
            if key == "M2final":
                txt += f"\n{c['marker_px']:.0f}px"
            ax.text(j, i, txt, ha="center", va="center", fontsize=7,
                    color="white" if Z[i, j] > 0.6 else INK)
    ax.set_xticks(range(len(ws))); ax.set_xticklabels(ws); ax.set_xlabel("Camera width (px)")
    ax.set_yticks(range(len(views))); ax.set_yticklabels([f"{v} ({c:.0%})" for v, c in
                                                          zip(views, [next(c for c in g if c['view'] == v)['visible_page_fraction'] for v in views])])
    ax.set_ylabel("Page height in frame (page visible)"); ax.set_title(title); ax.grid(False)
fig.colorbar(im, ax=axs, shrink=0.8, label="Exam ID recovered")
fig.savefig(f"{out}/fig_e1_operating_map.png", dpi=200)
print("ok")

# mixed conditions, pooled seeds, by effective marker size
rows = []
for f in sys.argv[3:]:
    rows += [json.loads(l) for l in open(f)]
if rows:
    mp = np.array([r["result"]["marker_px"] for r in rows])
    bins = [(0, 20), (20, 30), (30, 45), (45, 70), (70, 1e9)]
    names = ["<20", "20-30", "30-45", "45-70", ">=70"]
    def rate(key, cond):
        return [np.mean([cond(r["result"][key]) for r, m in zip(rows, mp) if lo <= m < hi]) for lo, hi in bins]
    ns = [int(((mp >= lo) & (mp < hi)).sum()) for lo, hi in bins]
    x = np.arange(len(bins)); w = 0.38
    fig, ax = plt.subplots(figsize=(6.2, 3.4), constrained_layout=True)
    ax.bar(x - w / 2 - 0.01, rate("M2final", lambda v: v == 1), w, color=OURS, label="Tiled yellow marker (ours)")
    ax.bar(x + w / 2 + 0.01, rate("M1", lambda v: v == 1), w, color=QR, label="Single QR, decoded")
    ax.set_xticks(x); ax.set_xticklabels([f"{n}\n(n={k})" for n, k in zip(names, ns)])
    ax.set_xlabel("Marker size in the captured image (px)"); ax.set_ylabel("Exam ID recovered")
    ax.set_ylim(0, 1); ax.legend(frameon=False, loc="upper left")
    ax.set_title(f"Randomized capture conditions, two seeds pooled (n={len(rows)})", fontsize=9, color=MUTED)
    fig.savefig(f"{out}/fig_e1_mixed_by_size.png", dpi=200)
print("ok")
