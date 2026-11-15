"""Quick demonstration of the exam registry (about one minute on a laptop).

    python demo.py                 # default: ink 0.7, photo of 35% of the page height
    python demo.py --ink 0.5 --view 0.25

Steps
  1. Registry   : an accredited authority signs an exam record (ID, time window,
                  item hash). The AI service verifies the signature and the window.
  2. Marker     : a simulated exam page is printed with the yellow marker, then
                  photographed in part by a simulated phone camera. The service
                  decodes the marker and refuses only if the exam is registered
                  and the window is open. An unmarked page is checked as a control.
  3. Content    : the question text is checked against the registered items by an
                  oblivious lookup (see oprf_demo.py). Neither side sees the other's text.

Images are written to demo_out/ so the result can be checked by eye.
"""
import argparse, hashlib, json, os, time
import numpy as np, cv2
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.exceptions import InvalidSignature
import e1_sim as E, e5_legibility as F, e5_enh as X, oprf_demo as O


def canon(rec):
    return json.dumps(rec, sort_keys=True, ensure_ascii=False).encode()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ink", type=float, default=0.7, help="marker strength: share of blue light absorbed by the yellow ink")
    ap.add_argument("--view", type=float, default=0.35, help="photographed height as a share of the page height")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--out", default="demo_out")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    now = int(time.time())

    # 1. registry --------------------------------------------------------------
    print("[1] 시험 등록")
    authority = Ed25519PrivateKey.generate()
    accredited = [authority.public_key()]
    text, qs = F.exam_page(a.seed)
    items = [q["text"] for q in qs]
    record = dict(exam_id=f"{E.EXAM_ID:08X}", title="2027학년도 모의 시험 수학 영역",
                  window_start=now - 600, window_end=now + 6000,
                  items_hash=hashlib.sha256("".join(items).encode()).hexdigest(),
                  policy="content_match")
    sig = authority.sign(canon(record))
    print("    등록 기록:", json.dumps({k: record[k] for k in ("exam_id", "title", "policy")}, ensure_ascii=False))

    def registered_and_open(exam_id, t):
        if exam_id != int(record["exam_id"], 16):
            return False
        for pk in accredited:
            try:
                pk.verify(sig, canon(record)); break
            except InvalidSignature:
                continue
        else:
            return False
        return record["window_start"] <= t <= record["window_end"]

    # 2. marker -----------------------------------------------------------------
    print("[2] 시험지 표식")
    page = E.print_sim(E.compose(text, E.aruco_tile_mask(), (1, 1, 1 - a.ink)), np.random.default_rng(a.seed + 3))
    plain = E.print_sim(E.compose(text, None, None), np.random.default_rng(a.seed + 1))
    p = dict(E.BASE, view=a.view, Wc=1280)
    cv2.imwrite(os.path.join(a.out, "page_marked.png"), cv2.cvtColor((page * 255).astype(np.uint8), cv2.COLOR_RGB2BGR))
    for name, pg in (("marked", page), ("unmarked", plain)):
        photo = E.capture(pg, p, np.random.default_rng(a.seed + 10))
        cv2.imwrite(os.path.join(a.out, f"photo_{name}.png"), cv2.cvtColor(photo, cv2.COLOR_RGB2BGR))
        found, chunks = X.match_enh(photo, F.ACTIVE)
        if found is None:
            print(f"    {'표식 있는' if name == 'marked' else '표식 없는'} 시험지 사진: 표식 없음 -> 정상 답변")
        else:
            ok_now = registered_and_open(found, now)
            ok_later = registered_and_open(found, record["window_end"] + 1)
            print(f"    {'표식 있는' if name == 'marked' else '표식 없는'} 시험지 사진: 시험 번호 {found:08X} 판독 (조각 {chunks}/6)"
                  f" -> 시험 시간 중 {'거절' if ok_now else '정상 답변'}, 종료 후 {'거절' if ok_later else '정상 답변'}")

    # 3. content lookup ------------------------------------------------------------
    print("[3] 문항 내용 조회")
    server = O.Authority(items)
    tests = [("원문 그대로", items[0]),
             ("띄어쓰기·표현 변경", items[0].replace(" ", "").replace("구하시오", "구해줘")),
             ("다른 숫자의 같은 유형 문제", O.change_numbers(items[0])),
             ("무관한 질문", "광합성에서 빛 에너지가 화학 에너지로 바뀌는 과정을 설명해 줘")]
    for label, q in tests:
        score, nums_ok = O.lookup(server, q)
        verdict = "거절" if score >= 0.5 and nums_ok else "정상 답변"
        print(f"    {label}: 일치율 {score:4.0%}, 숫자 일치 {'예' if nums_ok else '아니오'} -> {verdict}")
    print(f"\n사진은 {a.out}/ 폴더에 저장되었습니다.")


if __name__ == "__main__":
    main()
