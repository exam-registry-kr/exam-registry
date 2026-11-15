"""E5: is a photo that an AI could read also a photo whose marker decodes?

Same captured image, two readers:
  marker  : E1 v2 decoder on the full photo (what a provider would run)
  text    : Tesseract (kor+eng) on the target question, given every advantage:
            oracle perspective correction with the true homography and 2x upscaling.
            A stronger reader makes more photos "readable", so this is the strict
            direction for our hypothesis.

Primary metric (security gap): photos in which the question is readable
(CER <= 0.10) or all of its numbers are read correctly, but the marker fails.
"""
import argparse, json, os, re, time, zlib
import numpy as np, cv2
from PIL import Image, ImageDraw, ImageFont
import e1_sim as E
_r = np.random.default_rng(777)

# active exam IDs on test day: ours plus 29 decoys (a busy national exam day)
ACTIVE = [E.EXAM_ID] + [int(x) for x in _r.integers(0, 2**32, 29)]
# Korean font. The published numbers were produced with Noto Sans CJK KR
# (Linux package fonts-noto-cjk). Other Korean fonts work for the demo but
# change the page layout slightly, so E5 numbers may differ a little.
FONT_CANDIDATES = [
    (os.environ.get("EXAM_FONT", ""), int(os.environ.get("EXAM_FONT_INDEX", "0"))),
    ("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc", 1),
    ("/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc", 1),
    ("/System/Library/Fonts/AppleSDGothicNeo.ttc", 0),
    ("C:/Windows/Fonts/malgun.ttf", 0),
]


def _load_font(size):
    for path, idx in FONT_CANDIDATES:
        if path and os.path.exists(path):
            return ImageFont.truetype(path, size, index=idx)
    raise SystemExit("Korean font not found. Set EXAM_FONT to the path of a Korean .ttf/.ttc file.")


PT10 = int(round(10 / 72 * E.DPI))          # 10 pt at 150 dpi = 21 px em
F_Q = _load_font(PT10)
F_H = _load_font(int(PT10 * 1.3))

TEMPL = [
    lambda r: (lambda a, x, b: (f"어떤 수에 {a}를 곱한 후 {b}를 더하면 {a*x+b}이다. 이 수를 구하시오.", x))(int(r.integers(2, 9)), int(r.integers(3, 40)), int(r.integers(5, 90))),
    lambda r: (lambda a, d, n: (f"첫째항이 {a}이고 공차가 {d}인 등차수열의 제{n}항을 구하시오.", a + (n - 1) * d))(int(r.integers(2, 30)), int(r.integers(2, 9)), int(r.integers(5, 20))),
    lambda r: (lambda a, b: (f"가로의 길이가 {a} cm, 세로의 길이가 {b} cm인 직사각형의 넓이를 구하시오.", a * b))(int(r.integers(6, 40)), int(r.integers(6, 40))),
    lambda r: (lambda a, b, c: (f"함수 f(x) = {a}x + {b} 에 대하여 f({c})의 값을 구하시오.", a * c + b))(int(r.integers(2, 12)), int(r.integers(1, 50)), int(r.integers(2, 15))),
    lambda r: (lambda s, d: (f"두 수의 합이 {s}이고 차가 {d}일 때, 두 수 중 큰 수를 구하시오.", (s + d) // 2))(*(lambda big, small: (big + small, big - small))(int(r.integers(30, 99)), int(r.integers(5, 29)))),
    lambda r: (lambda p, q: (f"한 개에 {p}원인 공책을 {q}권 샀을 때, 지불해야 할 금액을 구하시오.", p * q))(int(r.integers(5, 30)) * 100, int(r.integers(3, 12))),
]


def wrap(text, font, width, draw):
    lines, cur = [], ""
    for ch in text:
        if draw.textlength(cur + ch, font=font) > width:
            lines.append(cur); cur = ch
        else:
            cur += ch
    return lines + [cur] if cur else lines


def exam_page(seed):
    """2-column exam page. Returns ink mask (1 = black ink), questions, boxes."""
    r = np.random.default_rng(seed)
    img = Image.new("L", (E.PW, E.PH), 0)
    d = ImageDraw.Draw(img)
    d.text((E.PW // 2, 150), "2027학년도 모의 시험 문제지  수학 영역", font=F_H, fill=255, anchor="mm")
    d.line((130, 190, E.PW - 130, 190), fill=255, width=2)
    d.line((E.PW // 2, 210, E.PW // 2, E.PH - 150), fill=255, width=1)
    colw = (E.PW - 2 * 130 - 60) // 2
    qs, k = [], 0
    for col in range(2):
        x0 = 130 + col * (colw + 60); y = 230
        while y < E.PH - 420:
            text, ans = TEMPL[k % len(TEMPL)](r); k += 1
            lines = wrap(f"{k}. " + text, F_Q, colw, d)
            y0 = y
            for ln in lines:
                d.text((x0, y), ln, font=F_Q, fill=255); y += int(PT10 * 1.6)
            tbox = [x0 - 8, y0 - 6, x0 + colw + 8, y + 4]
            ch = [ans + o for o in r.permutation([-2, -1, 0, 1, 2]) * int(r.integers(1, 4))]
            chline = "   ".join(f"{m} {v}" for m, v in zip("①②③④⑤", ch))
            d.text((x0, y + 8), chline, font=F_Q, fill=255); y += int(PT10 * 1.6) + 8
            qs.append(dict(n=k, text=text, answer=ans, choices=chline, tbox=tbox, box=[x0 - 8, y0 - 6, x0 + colw + 8, y + 6]))
            y += 170
    return np.asarray(img, np.float32) / 255.0, qs


def page_with_marker(seed, ink=0.7):
    text, qs = exam_page(seed)
    page = E.print_sim(E.compose(text, E.aruco_tile_mask(), (1, 1, 1 - ink)), np.random.default_rng(seed + 3))
    return page, qs


def capture_at(page, p, rng, center, meta):
    """E1 capture with the framing centred on a chosen page point."""
    meta["center"] = center
    return E.capture(page, p, rng, meta)


def normalize(s):
    """Keep Hangul, Latin letters and digits; circled choice marks and punctuation
    are dropped from both sides so that CER reflects reading the question itself."""
    return "".join(ch for ch in s if ch.isdigit() or ("a" <= ch.lower() <= "z") or ("\uac00" <= ch <= "\ud7a3"))


def cer(ref, hyp):
    ref = normalize(ref); hyp = normalize(hyp)
    if not ref:
        return 0.0
    dp = list(range(len(hyp) + 1))
    for i in range(1, len(ref) + 1):
        prev, dp[0] = dp[0], i
        for j in range(1, len(hyp) + 1):
            cur = min(dp[j] + 1, dp[j - 1] + 1, prev + (ref[i - 1] != hyp[j - 1]))
            prev, dp[j] = dp[j], cur
    return dp[-1] / len(ref)


def ocr_question(img, H, box):
    """Oracle-rectify the question box from the photo, upscale 2x, OCR."""
    x0, y0, x1, y1 = box
    out_w, out_h = int((x1 - x0) * 2), int((y1 - y0) * 2)
    # map output pixel -> page -> photo
    S = np.array([[0.5, 0, x0], [0, 0.5, y0], [0, 0, 1]])
    M = H @ S
    crop = cv2.warpPerspective(img, M, (out_w, out_h), flags=cv2.INTER_CUBIC | cv2.WARP_INVERSE_MAP,
                               borderValue=(255, 255, 255))
    g = cv2.cvtColor(crop, cv2.COLOR_RGB2GRAY)
    import pytesseract                       # needed only for the E5 text-reading test
    txt = pytesseract.image_to_string(g, lang="kor+eng", config="--psm 6")
    return txt


def nums(s):
    return re.findall(r"\d+", s)


def run(views, Wcs, blurs, reps, seed, out):
    os.makedirs(out, exist_ok=True)
    page, qs = page_with_marker(seed)
    rows = []
    t0 = time.time()
    for view in views:
        for Wc in Wcs:
            for blur in blurs:
                for t in range(reps):
                    q = qs[(t * 3) % len(qs)]
                    bx = q["box"]; c = ((bx[0] + bx[2]) / 2, (bx[1] + bx[3]) / 2)
                    p = dict(E.BASE, view=view, Wc=Wc, defocus=blur, tilt=20)
                    rng = np.random.default_rng(seed * 10 + zlib.crc32(f"{view}|{Wc}|{blur}|{t}".encode()) % 100000)
                    meta = {}
                    img = capture_at(page, p, rng, c, meta)
                    a, _ = E.decode_aruco(E.yellowness_masked(img))
                    if a in (None, -2):
                        a, _ = E.decode_aruco(cv2.cvtColor(img, cv2.COLOR_RGB2GRAY))
                    marker = int(a == E.EXAM_ID)
                    m2 = marker or int(E.match_active(E.yellowness_masked(img), ACTIVE) == E.EXAM_ID
                                       or E.match_active(cv2.cvtColor(img, cv2.COLOR_RGB2GRAY), ACTIVE) == E.EXAM_ID)
                    txt = ocr_question(img, meta["H"], q["tbox"])
                    ref = f"{q['n']}. " + q["text"]
                    e = cer(ref, txt)
                    numbers_ok = int(all(n in nums(txt) for n in nums(q["text"])))
                    # glyph scale: em height of 10 pt text in photo pixels at the question centre
                    cpts = np.float32([[[c[0], c[1]]], [[c[0], c[1] + PT10]]])
                    qq = cv2.perspectiveTransform(cpts, meta["H"]).reshape(-1, 2)
                    em_px = float(np.linalg.norm(qq[1] - qq[0]))
                    rows.append(dict(view=view, Wc=Wc, blur=blur, t=t, q=q["n"], marker=marker, marker_partial=m2, cer=round(e, 4),
                                     numbers_ok=numbers_ok, readable=int(e <= 0.10), em_px=round(em_px, 2)))
                print(f"view={view} Wc={Wc} blur={blur} [{time.time()-t0:.0f}s]", flush=True)
    json.dump(dict(seed=seed, questions=qs, rows=rows), open(f"{out}/e5_rows.json", "w"), indent=1)
    return rows


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--views", default="0.25,0.5,1.0")
    ap.add_argument("--wc", default="320,400,480,560,640,800,960,1280")
    ap.add_argument("--blurs", default="0.5,1.5")
    ap.add_argument("--reps", type=int, default=12)
    ap.add_argument("--seed", type=int, default=5050)
    ap.add_argument("--out", default="e5_out")
    a = ap.parse_args()
    run([float(v) for v in a.views.split(",")], [int(w) for w in a.wc.split(",")],
        [float(b) for b in a.blurs.split(",")], a.reps, a.seed, a.out)
