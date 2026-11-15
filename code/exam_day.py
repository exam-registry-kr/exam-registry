"""Exam-day walkthrough: every party acts only on the information it actually holds.

    python exam_day.py            # about one minute; writes exam_day_out/
    python exam_day.py --html-only exam_day_out/trace.json   # rebuild the timeline page

Parties and what each one holds
  Ministry of Education : its accreditation key and the list of accredited authorities
  Exam authority        : its signing key, the exam items, the lookup key
  National registry     : signed records in an append-only, hash-chained log
  AI service            : the public registry, a marker decoder, encrypted piece values
  Device maker          : exam numbers and time windows only (for AI that runs offline)
  Anyone (auditor)      : the public log, and after the exam the revealed items

One simulated exam day (a mock exam, period 1, 08:40 to 10:00) is played in time
order: accreditation, registration (with a forged and a retroactive attempt), inputs
from users before, during and after the window, automatic release, and the public
check after the exam. Each step prints who acted, what that party saw and what it did
not see. Decisions are the same on every run; the photos and lookups are computed,
not scripted. The encrypted lookup is the demonstration of e7_oprf_lookup.py, not an
RFC 9497 implementation.
"""
import argparse, hashlib, html, json, os, secrets, sys, time
from datetime import datetime, timedelta, timezone
import numpy as np, cv2
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization
from cryptography.exceptions import InvalidSignature

KST = timezone(timedelta(hours=9))
DAY = datetime(2027, 6, 3, tzinfo=KST)                     # a mock-exam day
T = lambda hh, mm, d=0: int((DAY + timedelta(days=d, hours=hh, minutes=mm)).timestamp())
fmt = lambda t: datetime.fromtimestamp(t, KST).strftime("%m-%d %H:%M")
canon = lambda obj: json.dumps(obj, sort_keys=True, ensure_ascii=False).encode()
raw = lambda pk: pk.public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw).hex()
TRACE = []


def log(t, actor, action, saw="", not_seen="", result=""):
    TRACE.append(dict(time=fmt(t), actor=actor, action=action, saw=saw, not_seen=not_seen, result=result))
    print(f"[{fmt(t)}] {actor}: {action}")
    for label, v in (("본 것", saw), ("보지 못한 것", not_seen), ("결과", result)):
        if v:
            print(f"           {label}: {v}")


# ---------------------------------------------------------------------------
class Ministry:
    name = "교육부"

    def __init__(self):
        self._key = Ed25519PrivateKey.generate()
        self.public_key = self._key.public_key()

    def accredit(self, authority_pub, scope):
        cert = dict(authority=raw(authority_pub), scope=scope)
        return dict(cert=cert, sig=self._key.sign(canon(cert)).hex())


class Registry:
    """Append-only log. Accepts a record only with a valid accreditation and signature,
    a window of at most 24 hours, and registration before the window opens."""
    name = "국가 등록부"

    def __init__(self, ministry_pub):
        self.ministry_pub = ministry_pub
        self.entries, self.head = [], "0" * 64

    def submit(self, t, record, sig_hex, accreditation, authority_pub):
        try:
            self.ministry_pub.verify(bytes.fromhex(accreditation["sig"]), canon(accreditation["cert"]))
            if accreditation["cert"]["authority"] != raw(authority_pub):
                return "거부: 인가서와 기관 키 불일치"
        except InvalidSignature:
            return "거부: 교육부 인가 없음"
        try:
            authority_pub.verify(bytes.fromhex(sig_hex), canon(record))
        except InvalidSignature:
            return "거부: 서명 불일치"
        if record["window_end"] - record["window_start"] > 24 * 3600:
            return "거부: 시험 시간 24시간 초과"
        if t >= record["window_start"]:
            return "거부: 시작 후 등록(소급)"
        entry = dict(t=t, record=record, sig=sig_hex, authority=raw(authority_pub), prev=self.head)
        self.head = hashlib.sha256(canon(entry)).hexdigest()
        entry["hash"] = self.head
        self.entries.append(entry)
        return f"등록 (장부 {len(self.entries)}번째, 연결값 {self.head[:12]}…)"

    def open_exams(self, t):
        return [e["record"] for e in self.entries if e["record"]["window_start"] <= t <= e["record"]["window_end"]]

    def windows(self):
        return [dict(exam_id=e["record"]["exam_id"], start=e["record"]["window_start"], end=e["record"]["window_end"])
                for e in self.entries]


class Authority:
    """Exam authority: keeps the items. Publishes only signed metadata, a salted
    commitment to the items and encrypted piece values (see e7_oprf_lookup.py)."""

    def __init__(self, name, items):
        import e7_oprf_lookup as O7
        self.name, self._O7 = name, O7
        self._sign = Ed25519PrivateKey.generate()
        self.public_key = self._sign.public_key()
        self._items = items
        self._salt = secrets.token_hex(16)
        self._lookup = O7.Authority(items, O7.pieces)            # holds the lookup key
        self.lookup_queries = 0

    def make_record(self, exam_id, title, start, end):
        self.exam_id = f"{exam_id:08X}"
        commit = hashlib.sha256((self._salt + "\n".join(self._items)).encode()).hexdigest()
        rec = dict(exam_id=f"{exam_id:08X}", title=title, window_start=start, window_end=end,
                   policy="marker_or_content", items_commitment=commit,
                   lookup_values=len(self._lookup.published))
        return rec, self._sign.sign(canon(rec)).hex()

    def published_lookup(self):
        return self._lookup.published                              # values only, no key

    def evaluate(self, blinded):                                   # sees only blinded points
        self.lookup_queries += 1
        return self._lookup.evaluate(blinded)

    def reveal(self):
        return self._salt, list(self._items)


class AIService:
    """Checks a photo with the marker decoder and a text with the encrypted lookup.
    Keeps only a refusal count per exam; stores no question and no user identity."""
    name = "AI 서비스"

    def __init__(self, registry, authority):
        import e5_enh as X, e7_oprf_lookup as O7
        self.registry, self.X, self.O7, self.auth = registry, X, O7, authority
        self.published = authority.published_lookup()
        self.refusals = {}

    def _refuse(self, exam_id):
        self.refusals[exam_id] = self.refusals.get(exam_id, 0) + 1
        return "답변 거절"

    def photo(self, t, img):
        open_ = self.registry.open_exams(t)
        if not open_:
            return "진행 중인 등록 시험 없음 -> 정상 답변", None
        ids = [int(r["exam_id"], 16) for r in open_]
        found, chunks = self.X.match_enh(img, ids)
        if found is None:
            return "보안 문양 없음 -> 정상 답변", None
        return f"보안 문양에서 시험 번호 {found:08X} 판독(조각 {chunks}/6), 시험 시간 중 -> {self._refuse(f'{found:08X}')}", found

    def text(self, t, question):
        open_ = [r for r in self.registry.open_exams(t) if r["policy"] == "marker_or_content"]
        if not open_:
            return "진행 중인 등록 시험 없음 -> 정상 답변"
        g, n = self.O7.pieces(question)
        fg, fn = self.O7.oprf(_Proxy(self.auth), g), self.O7.oprf(_Proxy(self.auth), n)
        hit, idx, score = self.O7.decide(fg, fn, self.published)
        if hit:
            return f"암호화 조회 일치(조각 {score:.0%}, 숫자 일치) -> {self._refuse(self.auth.exam_id)}"
        return f"암호화 조회 불일치(조각 최고 {score:.0%}) -> 정상 답변"


class _Proxy:
    """What the authority's lookup server receives: blinded points, nothing else."""
    def __init__(self, auth):
        self.auth = auth

    def evaluate(self, blinded):
        return self.auth.evaluate(blinded)


class DeviceMaker:
    """Offline AI on glasses or phones: only exam numbers and windows are preloaded."""
    name = "기기 제조사(기기 내장 AI)"

    def __init__(self, windows):
        import e5_enh as X
        self.X, self.windows = X, windows

    def photo(self, t, img):
        ids = [int(w["exam_id"], 16) for w in self.windows if w["start"] <= t <= w["end"]]
        if not ids:
            return "진행 중인 등록 시험 없음 -> 정상 답변"
        found, chunks = self.X.match_enh(img, ids)
        if found is None:
            return "보안 문양 없음 -> 정상 답변"
        return f"보안 문양에서 시험 번호 {found:08X} 판독(조각 {chunks}/6), 시험 시간 중 -> 답변 거절"

    def text(self, t, question):
        return "인터넷 없이 문장 조회 불가 -> 정상 답변 (본 제안의 한계: 기기 내장 AI는 사진만 확인)"


# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="exam_day_out")
    ap.add_argument("--html-only")
    a = ap.parse_args()
    if a.html_only:
        write_html(json.load(open(a.html_only, encoding="utf-8")), os.path.dirname(a.html_only) or ".")
        return
    os.makedirs(a.out, exist_ok=True)
    import e1_sim as E, e5_legibility as F

    seed = 6060
    page, qs = F.page_with_marker(seed, ink=0.7)                      # printed page with marker
    items = [q["text"] for q in qs]
    plain_text, _ = F.exam_page(seed + 1)
    textbook = E.print_sim(E.compose(plain_text, None, None), np.random.default_rng(5))
    p_service = dict(E.BASE, view=0.35, Wc=1280)
    p_glasses = dict(E.BASE, view=0.5, Wc=960, defocus=1.0)
    photo_svc = E.capture(page, p_service, np.random.default_rng(11))
    photo_gls = E.capture(page, p_glasses, np.random.default_rng(12))
    photo_book = E.capture(textbook, p_service, np.random.default_rng(13))
    for n, im in (("photo_exam_phone", photo_svc), ("photo_exam_glasses", photo_gls), ("photo_textbook", photo_book)):
        cv2.imwrite(os.path.join(a.out, n + ".png"), cv2.cvtColor(im, cv2.COLOR_RGB2BGR))

    S, E1 = T(8, 40), T(10, 0)
    ministry = Ministry()
    registry = Registry(ministry.public_key)
    kice = Authority("시험 기관(한국교육과정평가원)", items)
    rogue = Ed25519PrivateKey.generate()

    # day before ------------------------------------------------------------------
    t = T(9, 0, -1)
    acc = ministry.accredit(kice.public_key, "수능·모의평가")
    log(t, "교육부", "시험 기관의 서명 키를 등록 기관으로 인가",
        saw="시험 기관의 공개 키", not_seen="문항, 시험지", result="인가서 발급(교육부 서명)")

    t = T(10, 0, -1)
    rec, sig = kice.make_record(E.EXAM_ID, "2027학년도 6월 모의평가 1교시", S, E1)
    r = registry.submit(t, rec, sig, acc, kice.public_key)
    log(t, kice.name, "시험 번호, 시험 시간, 문항 약속값에 서명해 등록",
        saw="자기 문항 원문(기관 안에만 보관)", not_seen="", result=r)
    log(t, "국가 등록부", "인가서와 서명, 시간 규칙을 확인하고 공개 장부에 추가",
        saw=f"시험 번호 {rec['exam_id']}, 시험 시간 {fmt(S)}~{fmt(E1)}, 문항 약속값 {rec['items_commitment'][:12]}…",
        not_seen="문항 원문", result=r)

    fake = dict(rec, exam_id="0BADC0DE", title="미인가 단체의 임의 등록")
    r = registry.submit(t + 60, fake, rogue.sign(canon(fake)).hex(), acc, rogue.public_key())
    log(t + 60, "국가 등록부", "인가받지 않은 단체가 다른 기관의 인가서를 내밀며 시험을 등록하려 함",
        saw="인가서와 맞지 않는 서명 키", result=r)

    long_ = dict(rec, exam_id="0A11DA75", window_end=S + 30 * 3600)
    r = registry.submit(t + 120, long_, kice._sign.sign(canon(long_)).hex(), acc, kice.public_key)
    log(t + 120, "국가 등록부", "인가 기관이라도 30시간짜리 차단을 등록하려 함", result=r)

    for i, other in enumerate(F.ACTIVE[1:]):                         # other exams running at the same time
        auth = Authority(f"학교 {i + 1}", [f"학교 {i + 1} 문항 {j}" for j in range(3)])
        oacc = ministry.accredit(auth.public_key, "학교 내신")
        orec, osig = auth.make_record(other, f"학교 {i + 1} 기말고사", S, E1)
        registry.submit(t + 300, orec, osig, oacc, auth.public_key)
    log(t + 300, "국가 등록부", f"같은 시간에 진행되는 다른 시험 {len(F.ACTIVE) - 1}건도 각 인가 기관이 등록",
        result=f"장부 {len(registry.entries)}건, 마지막 연결값 {registry.head[:12]}…")

    ai = AIService(registry, kice)
    log(t + 600, "AI 서비스", "공개 장부와 암호화된 조각 값을 받음",
        saw=f"등록 시험 {len(registry.entries)}건의 번호와 시간, 암호화 조각 값 {sum(len(a) + len(b) for a, b in ai.published)}개",
        not_seen="문항 원문, 조각 값을 만든 비밀 키")
    dev = DeviceMaker(registry.windows())
    log(t + 600, "기기 제조사", "시험 번호와 시험 시간 목록만 기기에 미리 내려받음",
        saw=f"시험 {len(dev.windows)}건의 번호와 시간", not_seen="문항, 조각 값, 사용자 사진")

    # exam day ----------------------------------------------------------------------
    q_exam = items[0]
    q_practice = "어떤 수에 5를 곱한 후 21을 더하면 96이다. 이 수를 구하시오."
    q_other = "광합성에서 빛 에너지가 화학 에너지로 바뀌는 과정을 설명해 줘."
    for tt, who, act, fn in [
        (T(8, 20), "AI 서비스", "시험 시작 전, 시험지 사진 입력", lambda tt: ai.photo(tt, photo_svc)[0]),
        (T(9, 5), "AI 서비스", "시험 중, 휴대폰으로 찍은 시험지 일부 사진", lambda tt: ai.photo(tt, photo_svc)[0]),
        (T(9, 7), "AI 서비스", "시험 중, 같은 시간대 교과서 사진(시험지 아님)", lambda tt: ai.photo(tt, photo_book)[0]),
        (T(9, 10), "AI 서비스", "시험 중, 시험 문제를 글로 옮겨 입력", lambda tt: ai.text(tt, q_exam)),
        (T(9, 12), "AI 서비스", "시험 중, 띄어쓰기와 말투를 바꿔 입력", lambda tt: ai.text(tt, q_exam.replace(" ", "").replace("구하시오", "구해줘"))),
        (T(9, 14), "AI 서비스", "시험 중, 숫자만 다른 같은 유형 연습문제", lambda tt: ai.text(tt, q_practice)),
        (T(9, 16), "AI 서비스", "시험 중, 시험과 무관한 학습 질문", lambda tt: ai.text(tt, q_other)),
        (T(9, 20), "기기 제조사(기기 내장 AI)", "시험 중, 안경 카메라로 찍은 시험지 사진(인터넷 없음)", lambda tt: dev.photo(tt, photo_gls)),
        (T(9, 22), "기기 제조사(기기 내장 AI)", "시험 중, 같은 기기에 문제를 글로 입력", lambda tt: dev.text(tt, q_exam)),
        (T(10, 1), "AI 서비스", "시험 종료 1분 뒤, 같은 시험지 사진", lambda tt: ai.photo(tt, photo_svc)[0]),
        (T(10, 2), "AI 서비스", "시험 종료 뒤, 같은 문제를 글로 입력", lambda tt: ai.text(tt, q_exam)),
    ]:
        before = kice.lookup_queries
        res = fn(tt)
        is_text = "글로" in act or "질문" in act or "연습문제" in act
        saw = "사용자가 보낸 사진 또는 문장(" + ("서비스" if who == "AI 서비스" else "기기") + " 안에서만 처리)"
        not_seen = "문항 원문" if who == "AI 서비스" else "문항 원문, 문장 조회 수단"
        log(tt, who, act, saw=saw, not_seen=not_seen, result=res)
        if kice.lookup_queries > before:
            log(tt, kice.name, "조회 서버가 가려진 조각에 비밀 키를 적용해 돌려줌",
                saw="가려진 값(조각마다 무작위로 바뀜)", not_seen="사용자의 질문, 사용자가 누구인지", result="판정은 AI 서비스가 함")

    # after --------------------------------------------------------------------------
    t = T(12, 0)
    salt, revealed = kice.reveal()
    ok = hashlib.sha256((salt + "\n".join(revealed)).encode()).hexdigest() == rec["items_commitment"]
    log(t, kice.name, "시험 종료 후 문항과 약속값의 비밀 문자열을 공개", result="공개 완료")
    prev, chain_ok = "0" * 64, True
    for e in registry.entries:
        body = {k: v for k, v in e.items() if k != "hash"}
        chain_ok &= (e["prev"] == prev and hashlib.sha256(canon(body)).hexdigest() == e["hash"])
        prev = e["hash"]
    log(t, "누구나(사후 검증)", "공개 장부와 공개된 문항을 대조",
        saw="공개 장부 전체, 공개된 문항", not_seen="사용자의 질문",
        result=f"장부 연결 {'정상' if chain_ok else '변조'}, 문항이 시험 전 약속값과 {'일치' if ok else '불일치'},"
               f" 등록된 시험 {len(registry.entries)}건 모두 인가 기관 서명과 24시간 이내 시간, 이 시험의 차단 시간은 {fmt(S)}~{fmt(E1)}")
    log(t, "AI 서비스", "시험별 거절 건수 보고(기기 내장 AI의 거절은 제조사가 따로 집계)",
        saw="", not_seen="개인 정보(저장하지 않음)",
        result=", ".join(f"시험 {k}: {v}건" for k, v in ai.refusals.items()) or "0건")

    roles = [
        ("교육부", "등록 기관 인가 키, 인가 목록", "문항, 시험지, 사용자 입력"),
        ("시험 기관", "자기 문항 원문, 서명 키, 조회 비밀 키", "사용자의 질문과 신원, 다른 기관의 문항"),
        ("국가 등록부", "서명된 시험 번호·시간·약속값, 장부 연결값", "문항 원문, 사용자 입력"),
        ("AI 서비스", "공개 장부, 암호화 조각 값, 사용자 입력(서비스 안)", "문항 원문, 조회 비밀 키"),
        ("기기 제조사", "시험 번호와 시간 목록", "문항, 조각 값, 사용자 사진"),
        ("누구나(사후 검증)", "공개 장부, 시험 후 공개된 문항, 시험별 거절 건수", "사용자의 질문과 신원"),
    ]
    print("\n역할별 정보")
    for r_ in roles:
        print(f"  {r_[0]}: 가진 것 = {r_[1]} / 갖지 않은 것 = {r_[2]}")
    out = dict(exam=dict(exam_id=rec["exam_id"], title=rec["title"], start=fmt(S), end=fmt(E1)),
               trace=TRACE, roles=[dict(role=a_, has=b_, lacks=c_) for a_, b_, c_ in roles])
    json.dump(out, open(os.path.join(a.out, "trace.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    write_html(out, a.out)
    print(f"\n기록: {a.out}/trace.json, 시간표: {a.out}/exam_day.html, 사진: {a.out}/photo_*.png")


def write_html(out, d):
    esc = html.escape
    lanes = ["교육부", "시험 기관(한국교육과정평가원)", "국가 등록부", "AI 서비스", "기기 제조사(기기 내장 AI)", "기기 제조사", "누구나(사후 검증)"]
    rows = []
    for e in out["trace"]:
        cls = "refuse" if "거절" in e["result"] and "->" in e["result"] else ("reject" if e["result"].startswith("거부") else "")
        rows.append(f"<tr class='{cls}'><td class='t'>{esc(e['time'])}</td><td class='a'>{esc(e['actor'])}</td>"
                    f"<td>{esc(e['action'])}</td><td>{esc(e['saw'])}</td><td>{esc(e['not_seen'])}</td><td class='r'>{esc(e['result'])}</td></tr>")
    roles = "".join(f"<tr><td class='a'>{esc(r['role'])}</td><td>{esc(r['has'])}</td><td>{esc(r['lacks'])}</td></tr>" for r in out["roles"])
    ex = out["exam"]
    page = f"""<!DOCTYPE html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>시험 보호 국가 등록제: 시험 하루 시연</title><style>
body{{font-family:"Noto Sans KR","Apple SD Gothic Neo","Malgun Gothic",sans-serif;margin:24px;color:#111;line-height:1.55;max-width:1200px}}
h1{{font-size:22px;margin:0 0 4px}} p.sub{{margin:0 0 18px;color:#333}}
table{{border-collapse:collapse;width:100%;font-size:13px;margin:10px 0 24px}} th,td{{border:1px solid #ccc;padding:6px 8px;vertical-align:top;text-align:left;word-break:keep-all}}
th{{background:#f2f2f2}} td.t{{white-space:nowrap;font-variant-numeric:tabular-nums}} td.a{{font-weight:600;white-space:nowrap}}
tr.refuse td.r{{background:#fff3c4;font-weight:600}} tr.reject td.r{{background:#f3e0e0}}
.wrap{{overflow-x:auto}}</style></head><body>
<h1>시험 보호 국가 등록제: 시험 하루 시연</h1>
<p class="sub">{esc(ex['title'])} · 시험 번호 {esc(ex['exam_id'])} · 시험 시간 {esc(ex['start'])}~{esc(ex['end'])}.
각 기관은 자기가 가진 정보만으로 움직입니다. 판정은 실제 계산 결과이며, 사진은 시뮬레이션으로 만든 것입니다.</p>
<h2>시간 순서</h2><div class="wrap"><table><tr><th>시각</th><th>주체</th><th>한 일</th><th>본 것</th><th>보지 못한 것</th><th>결과</th></tr>{''.join(rows)}</table></div>
<h2>역할별 정보</h2><div class="wrap"><table><tr><th>역할</th><th>가진 것</th><th>갖지 않은 것</th></tr>{roles}</table></div>
<p class="sub">코드: github.com/exam-registry-kr/exam-registry · <code>python exam_day.py</code></p></body></html>"""
    open(os.path.join(d, "exam_day.html"), "w", encoding="utf-8").write(page)
    cell = lambda x: x.replace("|", "/").replace("\n", " ")
    md = [f"# 시험 하루 시연\n",
          f"{ex['title']}, 시험 번호 {ex['exam_id']}, 시험 시간 {ex['start']}~{ex['end']}. "
          "각 기관은 자기가 가진 정보만으로 움직입니다. 판정은 `code/exam_day.py`를 실행한 실제 계산 결과이며, "
          "사진은 시뮬레이션으로 만든 것이며, 보안 문양은 실험에 쓴 진한 농도(70%)로 인쇄했습니다(목표 외관은 훨씬 옅음). 장부 연결값과 약속값은 실행할 때마다 새 키로 만들어져 달라집니다.\n",
          "## 시간 순서\n", "| 시각 | 주체 | 한 일 | 본 것 | 보지 못한 것 | 결과 |", "|---|---|---|---|---|---|"]
    md += [f"| {e['time']} | {cell(e['actor'])} | {cell(e['action'])} | {cell(e['saw'])} | {cell(e['not_seen'])} | {cell(e['result'])} |" for e in out["trace"]]
    md += ["", "## 역할별 정보\n", "| 역할 | 가진 것 | 갖지 않은 것 |", "|---|---|---|"]
    md += [f"| {r['role']} | {r['has']} | {r['lacks']} |" for r in out["roles"]]
    open(os.path.join(d, "exam_day.md"), "w", encoding="utf-8").write("\n".join(md) + "\n")


if __name__ == "__main__":
    main()
