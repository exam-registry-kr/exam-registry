"""Quick demonstration of the exam registry (about one minute on a laptop).

    python demo.py                 # default: ink 0.7, photo of 35% of the page height
    python demo.py --ink 0.5 --view 0.25
    python demo.py --en            # English output

Steps
  1. Registry   : an accredited authority signs an exam record (ID, time window,
                  item hash). The AI service verifies the signature and the window.
  2. Marker     : a simulated exam page is printed with the yellow marker, then
                  photographed in part by a simulated phone camera. The service
                  decodes the marker and refuses only if the exam is registered
                  and the window is open. An unmarked page is checked as a control.
  3. Content    : the question text is checked against the registered items by an
                  oblivious lookup (see oprf_demo.py). Neither side sees the other's text.
  4. Rule R5    : the rule adopted after E16 and E19, on one item, next to the
                  rule it replaced (R3): a number or unrelated sentences put in
                  front of the item, a practice problem, a full rewording.

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
    ap.add_argument("--en", action="store_true", help="print in English")
    a = ap.parse_args()
    L = (lambda ko, en: en) if a.en else (lambda ko, en: ko)
    os.makedirs(a.out, exist_ok=True)
    now = int(time.time())

    # 1. registry --------------------------------------------------------------
    print(L("[1] 시험 등록", "[1] Exam registration"))
    authority = Ed25519PrivateKey.generate()
    accredited = [authority.public_key()]
    text, qs = F.exam_page(a.seed)
    items = [q["text"] for q in qs]
    record = dict(exam_id=f"{E.EXAM_ID:08X}", title="2027학년도 모의 시험 수학 영역",
                  window_start=now - 600, window_end=now + 6000,
                  items_hash=hashlib.sha256("".join(items).encode()).hexdigest(),
                  policy="content_match")
    sig = authority.sign(canon(record))
    print(L("    등록 기록:", "    Registered record:"), json.dumps({k: record[k] for k in ("exam_id", "title", "policy")}, ensure_ascii=False))

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
    print(L("[2] 시험지 표식", "[2] Exam page marker"))
    page = E.print_sim(E.compose(text, E.aruco_tile_mask(), (1, 1, 1 - a.ink)), np.random.default_rng(a.seed + 3))
    plain = E.print_sim(E.compose(text, None, None), np.random.default_rng(a.seed + 1))
    p = dict(E.BASE, view=a.view, Wc=1280)
    cv2.imwrite(os.path.join(a.out, "page_marked.png"), cv2.cvtColor((page * 255).astype(np.uint8), cv2.COLOR_RGB2BGR))
    for name, pg in (("marked", page), ("unmarked", plain)):
        photo = E.capture(pg, p, np.random.default_rng(a.seed + 10))
        cv2.imwrite(os.path.join(a.out, f"photo_{name}.png"), cv2.cvtColor(photo, cv2.COLOR_RGB2BGR))
        found, chunks = X.match_enh(photo, F.ACTIVE)
        what = L("표식 있는" if name == "marked" else "표식 없는", "Photo of the " + name + " exam page")
        if found is None:
            print(L(f"    {what} 시험지 사진: 표식 없음 -> 정상 답변", f"    {what}: no marker -> normal answer"))
        else:
            ok_now = registered_and_open(found, now)
            ok_later = registered_and_open(found, record["window_end"] + 1)
            v = lambda ok: L("거절" if ok else "정상 답변", "refused" if ok else "normal answer")
            print(L(f"    {what} 시험지 사진: 시험 번호 {found:08X} 판독 (조각 {chunks}/6) -> 시험 시간 중 {v(ok_now)}, 종료 후 {v(ok_later)}",
                    f"    {what}: exam ID {found:08X} read ({chunks}/6 chunks) -> during the exam {v(ok_now)}, after it {v(ok_later)}"))

    # 3. content lookup ------------------------------------------------------------
    print(L("[3] 문항 내용 조회", "[3] Content lookup"))
    server = O.Authority(items)
    tests = [(L("원문 그대로", "Item as printed"), items[0]),
             (L("띄어쓰기·표현 변경", "Spacing and wording changed"), items[0].replace(" ", "").replace("구하시오", "구해줘")),
             (L("다른 숫자의 같은 유형 문제", "Same type, different numbers"), O.change_numbers(items[0])),
             (L("무관한 질문", "Unrelated question"), "광합성에서 빛 에너지가 화학 에너지로 바뀌는 과정을 설명해 줘")]
    for label, q in tests:
        score, nums_ok = O.lookup(server, q)
        hit = score >= 0.5 and nums_ok
        print(L(f"    {label}: 일치율 {score:4.0%}, 숫자 일치 {'예' if nums_ok else '아니오'} -> {'거절' if hit else '정상 답변'}",
                f"    {label}: pieces matched {score:4.0%}, numbers match {'yes' if nums_ok else 'no'} -> {'refused' if hit else 'normal answer'}"))

    # 4. the adopted rule (R5) -----------------------------------------------------
    # [3] shows the principle with the first rule (share of pieces + number check).
    # The rule adopted after E16 and E19 is R5; R3 is the rule it replaced.
    import e9_korean_text_items as E9
    print(L("[4] 채택한 판정 규칙 R5 (3.18). 괄호 안은 이전 규칙 R3",
            "[4] The adopted rule R5 (3.18). The earlier rule R3 in brackets"))
    item = "기차가 43시간 동안 150km를 달렸다. 같은 속력으로 16시간 동안 달리면 몇 km를 가는가?"
    reg = E9.Registry(items + [item], [""] * (len(items) + 1))
    filler = "오늘은 날씨가 맑아서 강가를 따라 오래 걸었다. 저녁에는 동생과 함께 시장에 들러 반찬거리를 샀다. 주말에는 미뤄 둔 방 정리를 끝낼 생각이다. "
    cases = [(L("등록 문항 그대로", "Registered item as printed"), item),
             (L("앞에 \"문제 23번\"을 붙임", "\"문제 23번\" (question 23) put in front"), "문제 23번 " + item),
             (L("무관한 문장 3개를 앞에 붙임", "Three unrelated sentences put in front"), filler + item),
             (L("숫자만 다른 연습문제", "Practice problem, other numbers"),
              "기차가 59시간 동안 319km를 달렸다. 같은 속력으로 16시간 동안 달리면 몇 km를 가는가?"),
             (L("문장을 전부 바꿔 씀 (막지 못하는 경우)", "Every sentence reworded (not caught)"),
              "어떤 열차가 150km를 가는 데 43시간이 걸렸다. 빠르기가 변하지 않는다면 16시간에는 얼마나 멀리 갈까?")]
    target = reg.g[-1]
    v = lambda hit: L("거절" if hit else "정상 답변", "refused" if hit else "normal answer")
    for label, q in cases:
        qp = E9.pieces(E9.nk(q))[0]
        r5, r3 = bool(reg.r5(q)[0]), bool(reg.r3(q)[0])
        print(L(f"    {label}: 질문 조각 {len(qp)}개 중 {len(qp & target)}개 일치 -> {v(r5)} (R3: {v(r3)})",
                f"    {label}: {len(qp & target)} of {len(qp)} pieces match -> {v(r5)} (R3: {v(r3)})"))
    print(L(f"\n사진은 {a.out}/ 폴더에 저장되었습니다.", f"\nPhotos were saved to {a.out}/."))


if __name__ == "__main__":
    main()
