"""Final marker decoder: partial ID match retried on enlarged and sharpened copies of the photo.

Run directly, it re-checks the AI reading test set made by e5_stage2.py (images and answer key are not in this repository)."""
import json, numpy as np, cv2, sys
import e1_sim as E, e5_legibility as F
P = cv2.aruco.DetectorParameters()
P.adaptiveThreshWinSizeMin, P.adaptiveThreshWinSizeMax, P.adaptiveThreshWinSizeStep = 3, 53, 4
P.minMarkerPerimeterRate = 0.01
P.polygonalApproxAccuracyRate = 0.05
P.perspectiveRemovePixelPerCell = 8
P.perspectiveRemoveIgnoredMarginPerCell = 0.2
P.maxErroneousBitsInBorderRate = 0.5
P.errorCorrectionRate = 0.6
P.cornerRefinementMethod = cv2.aruco.CORNER_REFINE_SUBPIX
DET2 = cv2.aruco.ArucoDetector(E.DICT if hasattr(E, "DICT") else cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_1000), P)

def enhance_variants(g):
    out = [g]
    up = cv2.resize(g, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
    out.append(up)
    bl = cv2.GaussianBlur(up, (0, 0), 3)
    out.append(cv2.addWeighted(up, 2.0, bl, -1.0, 0))          # unsharp
    out.append(cv2.createCLAHE(2.0, (8, 8)).apply(out[-1]))
    return out

def match_enh(img, active, min_chunks=4):
    """Try each (channel, enhancement, detector) variant on its own; a variant must
    be internally consistent with one active ID on >= min_chunks chunks."""
    best = 0
    for g in (E.yellowness_masked(img), cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)):
        for v in enhance_variants(g):
            for det in (E.DETECTOR, DET2):
                _, ids, _ = det.detectMarkers(v)
                if ids is None: continue
                m, n = match(ids.flatten(), active, min_chunks)
                best = max(best, n)
                if m is not None and m != -1: return m, n
    return None, best

def match(ids, active, min_chunks=4):
    votes = E.chunk_votes(ids)
    seen = {k: max(v, key=v.get) for k, v in enumerate(votes) if v}
    if len(seen) < min_chunks: return None, len(seen)
    for eid in active:
        pv = E.payload(eid)
        if all(((pv >> (E.BITS * k)) & 127) == val for k, val in seen.items()): return eid, len(seen)
    return -1, len(seen)

if __name__ == "__main__":
    key = json.load(open("e5_stage2/answer_key.json"))
    for k in key:
        img = cv2.cvtColor(cv2.imread("e5_stage2/images/" + k["file"]), cv2.COLOR_BGR2RGB)
        m, n = match_enh(img, F.ACTIVE)
        print(k["photo"], k["group"], k["view"], k["Wc"], k["blur"], "em", k["em_px"], "enh->", m == E.EXAM_ID, "chunks", n, flush=True)
