"""Combine E1 runs into the published files and print the headline numbers.

Full reproduction (about 2 hours on a laptop; runs can be split by --factors and run in parallel):
    python e1_sim.py --trials 40 --grid 15 --mixed 250 --seed 20261115 --out e1_main
    python e1_sim.py --factors "" --grid 0 --mixed 250 --seed 777 --out e1_seed777
    python e1_merge.py e1_main e1_seed777

Each argument is an e1_sim.py output folder. Sweeps and the grid are taken from
every folder; the mixed trials are kept per seed. Every trial's random seed is
derived from its condition name, so splitting a run into parts gives the same rows.
"""
import json, sys, numpy as np, e1_sim as E

order = list(E.SWEEPS)
M = {"sweeps": {f: [] for f in order}, "grid": [], "mixed": {}, "config": None, "version": "v2"}
mix = []
for d in sys.argv[1:]:
    R = json.load(open(f"{d}/e1_results.json"))
    M["config"] = M["config"] or R["config"]
    for f, pts in R.get("sweeps", {}).items():
        M["sweeps"][f] += pts
    M["grid"] += R.get("grid", [])
    if R.get("mixed"):
        M["mixed"][str(R["config"]["seed"])] = R["mixed"]
        mix += [json.loads(l) for l in open(f"{d}/mixed_trials.jsonl")]
for f in order:
    M["sweeps"][f].sort(key=lambda p: E.SWEEPS[f].index(p["value"]))
M["grid"].sort(key=lambda c: (-c["view"], c["Wc"]))
json.dump(M, open("E1-005_results_v2_merged.json", "w"), indent=1)
open("E1-006_mixed_trials_v2_2seeds.jsonl", "w").write("".join(json.dumps(x) + "\n" for x in mix))

rows = [r for f in M["sweeps"].values() for p in f for r in p["rows"]] + [r for c in M["grid"] for r in c["rows"]]
allr = rows + [x["result"] for x in mix]
print("trials", len(allr), "wrong exam ID", sum(r["M2final"] == -1 for r in allr),
      "false detection on unmarked pages", sum(r["M0_fp"] for r in allr))
for p in M["sweeps"]["view"]:
    print(f"page height {p['value']:.2f}: marker {p['M2final']['correct']:.3f}, single corner code {p['M1']['correct']:.3f}")
