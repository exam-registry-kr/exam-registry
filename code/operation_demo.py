"""Operation walkthrough: every party acts only on the information it actually holds.

    python operation_demo.py       # about half a minute; writes operation_demo_out/
    python operation_demo.py --html-only operation_demo_out/trace.json   # rebuild the timeline page

Parties and what each one holds
  Ministry of Education   : its accreditation key
  Education office        : a delegated key that accredits schools in its region
  Registry operator       : the append-only log, the operator key that signs the log
                            head, and the shared lookup server for schools
  Exam authority          : its signing key, the exam items, its lookup key
  Printer                 : the exam number to print as the security pattern
  AI service              : the public log, encrypted piece values (locked until the exam
                            starts, see E11), a marker decoder
  Device maker            : exam numbers and time windows only (for AI that runs offline)
  Anyone (auditor)        : the public log, and after the exam the revealed items

A mock exam (period 1, 08:40 to 10:00) is played from accreditation two months
before to the public check after the exam. The preparation covers designation of the
registry operator, accreditation (directly and through an education office),
agreements with AI services and device makers, a compliance test with a test exam,
item freezing, choice of an unused exam number, encrypted piece values, printing and
print inspection, registration with rejected attempts, distribution and independent
verification by AI services and devices, and the public check of the next day's
schedule. Each step prints who acted, what that party saw and what it did not see.
Decisions are computed, not scripted, and are the same on every run. The encrypted
lookup is the demonstration of e7_oprf_lookup.py, not an RFC 9497 implementation.
"""
import argparse, hashlib, html, json, os, secrets
from datetime import datetime, timedelta, timezone
import numpy as np, cv2
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.hazmat.primitives import serialization
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


def op_pieces(text):
    """4-character pieces as in E7; numbers counted with repetition (the rule E8 recommends)."""
    import e7_oprf_lookup as O7
    from e8_registry_scale import numbers_count
    return O7.pieces(text)[0], numbers_count(text)

KST = timezone(timedelta(hours=9))
DAY = datetime(2027, 6, 3, tzinfo=KST)
T = lambda hh, mm, d=0: int((DAY + timedelta(days=d, hours=hh, minutes=mm)).timestamp())
fmt = lambda t: datetime.fromtimestamp(t, KST).strftime("%m-%d %H:%M")
canon = lambda obj: json.dumps(obj, sort_keys=True, ensure_ascii=False).encode()
raw = lambda pk: pk.public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw).hex()
pub_of = lambda hexkey: Ed25519PublicKey.from_public_bytes(bytes.fromhex(hexkey))
set_hash = lambda published: hashlib.sha256(canon([sorted(a) + sorted(b) for a, b in published])).hexdigest()
TRACE = []


def lock(published):
    """Lock a set of piece values; the 32-byte key is released only when the exam starts (E11)."""
    key, nonce = AESGCM.generate_key(256), os.urandom(12)
    blob = json.dumps([[sorted(a), sorted(b)] for a, b in published]).encode()
    return dict(nonce=nonce, ct=AESGCM(key).encrypt(nonce, blob, b"exam-set")), key


def log(t, actor, action, saw="", not_seen="", result="", phase=""):
    TRACE.append(dict(time=fmt(t), phase=phase, actor=actor, action=action, saw=saw, not_seen=not_seen, result=result))
    print(f"[{fmt(t)}] {actor}: {action}")
    for label, v in (("본 것", saw), ("보지 못한 것", not_seen), ("결과", result)):
        if v:
            print(f"           {label}: {v}")


def verify(pub, sig_hex, obj):
    try:
        pub.verify(bytes.fromhex(sig_hex), canon(obj))
        return True
    except (InvalidSignature, ValueError):
        return False


# --------------------------------------------------------------------------- parties
class Accreditor:
    """Ministry (root) or an education office (delegated by the ministry)."""

    def __init__(self, name):
        self.name, self._key = name, Ed25519PrivateKey.generate()
        self.public_key = self._key.public_key()

    def accredit(self, subject_pub, subject, kinds, until, may_delegate=False):
        cert = dict(issuer=self.name, issuer_key=raw(self.public_key), subject=subject,
                    subject_key=raw(subject_pub), kinds=kinds, until=until, may_delegate=may_delegate)
        return dict(cert=cert, sig=self._key.sign(canon(cert)).hex())

    def designate_operator(self, operator_pub, until):
        cert = dict(issuer=self.name, role="등록부 운영", subject_key=raw(operator_pub), until=until)
        return dict(cert=cert, sig=self._key.sign(canon(cert)).hex())


def check_chain(ministry_pub, chain, signer_pub, kind, t):
    """Ministry -> (education office ->) authority. Returns '' if valid, else the reason."""
    if not chain or chain[0]["cert"]["issuer_key"] != raw(ministry_pub):
        return "교육부 인가 없음"
    parent_key, parent_kinds = ministry_pub, None
    for i, c in enumerate(chain):
        cert = c["cert"]
        if not verify(parent_key, c["sig"], cert):
            return "인가서 서명 불일치"
        if t > cert["until"]:
            return "인가 기간 만료"
        if parent_kinds is not None and not set(cert["kinds"]) <= set(parent_kinds):
            return "상위 인가 범위를 넘는 위임"
        if i < len(chain) - 1 and not cert["may_delegate"]:
            return "위임 권한 없는 기관의 인가"
        parent_key, parent_kinds = pub_of(cert["subject_key"]), cert["kinds"]
    if chain[-1]["cert"]["subject_key"] != raw(signer_pub):
        return "인가서와 기관 키 불일치"
    if kind not in chain[-1]["cert"]["kinds"]:
        return f"인가 범위({', '.join(chain[-1]['cert']['kinds'])}) 밖의 시험 종류({kind})"
    return ""


class Registry:
    """Append-only, hash-chained public log run by the designated operator."""

    def __init__(self, ministry_pub, operator_key, operator_cert):
        self.ministry_pub, self._op, self.operator_cert = ministry_pub, operator_key, operator_cert
        self.entries, self.head = [], "0" * 64

    def has(self, exam_id):
        return any(e["record"]["exam_id"] == exam_id for e in self.entries)

    def submit(self, t, record, sig_hex, chain, signer_pub):
        why = check_chain(self.ministry_pub, chain, signer_pub, record["kind"], t)
        if why:
            return "거부: " + why
        if not verify(signer_pub, sig_hex, record):
            return "거부: 기록 서명 불일치(전송 중 변경)"
        if self.has(record["exam_id"]):
            return "거부: 이미 등록된 시험 번호"
        if record["window_end"] - record["window_start"] > 24 * 3600:
            return "거부: 시험 시간 24시간 초과"
        if t >= record["window_start"]:
            return "거부: 시작 후 등록(소급)"
        entry = dict(t=t, record=record, sig=sig_hex, chain=chain, prev=self.head)
        self.head = hashlib.sha256(canon(entry)).hexdigest()
        entry["hash"] = self.head
        self.entries.append(entry)
        return f"등록 (장부 {len(self.entries)}번째)"

    def signed_head(self, t):
        h = dict(size=len(self.entries), head=self.head, t=t)
        return dict(head=h, sig=self._op.sign(canon(h)).hex())


class LookupKeyHolder:
    """Holds an OPRF key. Used by an exam authority, or by the operator as the shared
    lookup server for schools. Sees blinded points only."""

    def __init__(self, O7):
        self._O7 = O7
        self._k = secrets.randbelow(O7.Np - 1) + 1
        self._key = O7.ec.derive_private_key(self._k, O7.CURVE)
        self.queries = 0

    def evaluate(self, blinded):
        self.queries += 1
        return [int.from_bytes(self._key.exchange(self._O7.ec.ECDH(), self._O7.lift(b)), "big") for b in blinded]


class Authority:
    def __init__(self, name, items, lookup=None):
        import e7_oprf_lookup as O7
        self.name, self.O7, self._items = name, O7, items
        self._sign = Ed25519PrivateKey.generate()
        self.public_key = self._sign.public_key()
        self._salt = secrets.token_hex(16)
        self.lookup = lookup or LookupKeyHolder(O7)          # own server, or the shared one
        self.chain = None

    def piece_values(self):
        """F_k of every piece. With the shared server the authority itself runs the
        oblivious protocol, so the shared server never sees the school's items."""
        out = []
        for it in self._items:
            g, n = op_pieces(it)
            out.append((self.O7.oprf(self.lookup, g), self.O7.oprf(self.lookup, n)))
        return out

    def record(self, exam_id, kind, title, start, end, published, server):
        rec = dict(exam_id=f"{exam_id:08X}", kind=kind, title=title, window_start=start, window_end=end,
                   policy="marker_or_content",
                   items_commitment=hashlib.sha256((self._salt + "\n".join(self._items)).encode()).hexdigest(),
                   lookup_set_hash=set_hash(published), lookup_server=server)
        return rec, self._sign.sign(canon(rec)).hex()

    def sign(self, rec):
        return self._sign.sign(canon(rec)).hex()

    def reveal(self):
        return self._salt, list(self._items)


class AIService:
    """Verifies everything itself, keeps only a refusal count per exam."""

    def __init__(self, name, ministry_pub, servers):
        import e5_enh as X, e7_oprf_lookup as O7
        self.name, self.ministry_pub, self.X, self.O7, self.servers = name, ministry_pub, X, O7, servers
        self.schedule, self.values, self.refusals, self.locked = {}, {}, {}, {}

    def sync(self, t, registry, signed_head, distributions):
        oc = registry.operator_cert
        if not verify(self.ministry_pub, oc["sig"], oc["cert"]):
            return "운영 기관 지정 확인 실패"
        if not verify(pub_of(oc["cert"]["subject_key"]), signed_head["sig"], signed_head["head"]):
            return "장부 머리 서명 불일치"
        prev, ok = "0" * 64, 0
        for e in registry.entries:
            body = {k: v for k, v in e.items() if k != "hash"}
            if e["prev"] != prev or hashlib.sha256(canon(body)).hexdigest() != e["hash"]:
                return "장부 연결 불일치"
            prev = e["hash"]
            signer = pub_of(e["chain"][-1]["cert"]["subject_key"])
            if check_chain(self.ministry_pub, e["chain"], signer, e["record"]["kind"], e["t"]) or not verify(signer, e["sig"], e["record"]):
                continue
            ok += 1
            self.schedule[e["record"]["exam_id"]] = e["record"]
        if prev != signed_head["head"]["head"]:
            return "장부 머리 불일치"
        kept = 0
        for eid, box in distributions.items():
            if eid in self.schedule:
                self.locked[eid] = box
                kept += 1
        return f"장부 {len(registry.entries)}건 중 {ok}건을 직접 재검증, 잠긴 조각 값 묶음 {kept}건 보관(열쇠는 각 시험 시작 시각에 공개)"

    def open_sets(self, t, keys):
        """Open the locked sets whose exam has started and check them against the log."""
        opened, bad = 0, 0
        for eid, key in keys.items():
            r, box = self.schedule.get(eid), self.locked.get(eid)
            if r is None or box is None or t < r["window_start"]:
                bad += 1
                continue
            try:
                raw = json.loads(AESGCM(key).decrypt(box["nonce"], box["ct"], b"exam-set"))
            except Exception:
                bad += 1
                continue
            published = [(set(a), set(b)) for a, b in raw]
            if set_hash(published) == r["lookup_set_hash"]:
                self.values[eid] = published
                opened += 1
            else:
                bad += 1
        return f"묶음 {opened}건을 열어 장부의 요약값과 일치 확인" + (f", 열리지 않거나 불일치 {bad}건 폐기" if bad else "")

    def insider_guess(self, server, guesses):
        """What an insider can learn before the start: guessed pieces have nothing to be compared with."""
        fx = self.O7.oprf(server, guesses)
        ct = b"".join(b["ct"] for b in self.locked.values())
        hits = sum(bytes.fromhex(v) in ct for v in fx) + sum(any(v in p for p, _ in pub) for v in fx for pub in self.values.values())
        return hits

    def _open(self, t):
        return [r for r in self.schedule.values() if r["window_start"] <= t <= r["window_end"]]

    def _refuse(self, eid):
        self.refusals[eid] = self.refusals.get(eid, 0) + 1
        return "답변 거절"

    def photo(self, t, img):
        open_ = self._open(t)
        if not open_:
            return "진행 중인 등록 시험 없음 -> 정상 답변"
        found, chunks = self.X.match_enh(img, [int(r["exam_id"], 16) for r in open_])
        if found is None:
            return f"진행 중인 시험 {len(open_)}건의 번호와 대조, 보안 문양 없음 -> 정상 답변"
        return f"보안 문양에서 시험 번호 {found:08X} 판독(조각 {chunks}/6), 시험 시간 중 -> {self._refuse(f'{found:08X}')}"

    def text(self, t, question):
        open_ = [r for r in self._open(t) if r["policy"] == "marker_or_content" and r["exam_id"] in self.values]
        if not open_:
            return "진행 중인 등록 시험 없음 -> 정상 답변", 0
        g, n = op_pieces(question)
        best, by_server = 0.0, {}
        for r in open_:
            by_server.setdefault(r["lookup_server"], []).append(r)
        for server, recs in by_server.items():            # one oblivious query per server
            fg, fn = self.O7.oprf(self.servers[server], g), self.O7.oprf(self.servers[server], n)
            for r in recs:
                hit, _, score = self.O7.decide(fg, fn, self.values[r["exam_id"]])
                best = max(best, score)
                if hit:
                    return f"암호화 조회 일치(조각 {score:.0%}, 숫자 일치) -> {self._refuse(r['exam_id'])}", len(by_server)
        return f"조회 서버 {len(by_server)}곳에 질문 1회씩 조회, 불일치(조각 최고 {best:.0%}) -> 정상 답변", len(by_server)


class Device:
    """Offline AI on glasses or phones: exam numbers and windows only."""

    def __init__(self, maker_pub):
        import e5_enh as X
        self.X, self.maker_pub, self.windows = X, maker_pub, []

    def install(self, package, sig):
        if not verify(self.maker_pub, sig, package):
            return "제조사 서명 불일치, 설치 거부"
        self.windows = package["windows"]
        return f"시험 {len(self.windows)}건의 번호와 시간 설치"

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


def print_page(E, F, seed, exam_id):
    """The printer receives the page and the exam number, and prints the pattern."""
    keep = E.EXAM_ID
    E.EXAM_ID = exam_id
    try:
        return F.page_with_marker(seed, ink=0.7)
    finally:
        E.EXAM_ID = keep


# --------------------------------------------------------------------------- scenario
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="operation_demo_out")
    ap.add_argument("--html-only")
    a = ap.parse_args()
    if a.html_only:
        write_outputs(json.load(open(a.html_only, encoding="utf-8")), os.path.dirname(a.html_only) or ".")
        return
    os.makedirs(a.out, exist_ok=True)
    import e1_sim as E, e5_legibility as F, e5_enh as X, e7_oprf_lookup as O7

    S, E1 = T(8, 40), T(10, 0)
    YEAR_END = T(0, 0, 211)
    P1, P2, P3, P4 = "1. 사전 준비", "2. 연동 시험", "3. 시험 준비", "4. 등록과 배포"
    ministry = Accreditor("교육부")
    office = Accreditor("서울특별시교육청")
    operator_key = Ed25519PrivateKey.generate()
    shared = LookupKeyHolder(O7)

    # 1. preparation (two months to a month before) ----------------------------------
    t = T(10, 0, -60)
    op_cert = ministry.designate_operator(operator_key.public_key(), YEAR_END)
    registry = Registry(ministry.public_key, operator_key, op_cert)
    log(t, "교육부", "국가 등록부와 공용 조회 서버를 운영할 기관을 지정", phase=P1,
        saw="운영 기관의 공개 키", not_seen="운영 기관의 비밀 키",
        result="지정서 발급(교육부 서명). 운영 기관은 장부를 쌓고 장부 머리에 서명하며, 학교용 공용 조회 서버를 운영")

    kice = Authority("시험 기관(한국교육과정평가원)", [])
    kice.chain = [ministry.accredit(kice.public_key, "한국교육과정평가원", ["수능", "모의평가"], YEAR_END)]
    log(t + 3600, "교육부", "한국교육과정평가원을 등록 기관으로 인가", phase=P1,
        saw="평가원의 공개 키", not_seen="문항, 시험지, 평가원의 비밀 키",
        result="인가서 발급: 시험 종류 수능·모의평가, 유효기간 연말까지")
    office_chain = ministry.accredit(office.public_key, "서울특별시교육청", ["학교 내신"], YEAR_END, may_delegate=True)
    log(t + 7200, "교육부", "서울특별시교육청에 학교 인가 권한을 위임", phase=P1,
        saw="교육청의 공개 키", result="위임 인가서 발급: 시험 종류 학교 내신만, 하위 기관 인가 가능")

    t = T(10, 0, -45)
    schools = []
    for i in range(len(F.ACTIVE) - 1):
        sch = Authority(f"학교 {i + 1}", [f"학교 {i + 1} 기말고사 {j + 1}번: {k}에 {k * 3 + j}을 더한 값을 구하시오." for j, k in enumerate(range(3 + i, 6 + i))], lookup=shared)
        sch.chain = [office_chain, office.accredit(sch.public_key, f"학교 {i + 1}", ["학교 내신"], YEAR_END)]
        schools.append(sch)
    log(t, "서울특별시교육청", f"관내 학교 {len(schools)}곳의 교원 키를 인가", phase=P1,
        saw="학교별 공개 키", not_seen="학교 문항",
        result="인가서 발급: 학교 내신만. 교육부 위임 인가서와 이어져 교육부까지 검증 가능")

    t = T(10, 0, -30)
    log(t, "교육부, AI 서비스", "AI 서비스와 업무협약 체결", phase=P1,
        saw="AI 서비스 이름과 연락 창구", not_seen="AI 서비스의 사용자 정보",
        result="협약 내용: 등록 시험 시간에 판정 적용, 시험별 거절 건수 보고, 이행 점검 수용. 판독기와 조회 도구는 공개 소프트웨어로 제공")
    maker_key = Ed25519PrivateKey.generate()
    log(t + 3600, "교육부, 기기 제조사", "안경·휴대폰 제조사와 업무협약 체결", phase=P1,
        result="협약 내용: 기기 내장 AI에 시험 번호·시간 목록과 보안 문양 판독기 탑재. 목록은 제조사 서명으로 배포")
    servers = {"평가원 조회 서버": kice.lookup, "공용 조회 서버": shared}
    ai = AIService("AI 서비스", ministry.public_key, servers)

    # 2. compliance test (two weeks before) ---------------------------------------------
    t = T(10, 0, -14)
    TEST_ID = 0x7E57C0DE
    test_items = ["연동 시험 문항: 어떤 수에 4를 곱한 후 17을 더하면 85이다. 이 수를 구하시오."]
    test_auth = Authority("시험 기관(한국교육과정평가원)", test_items)
    test_auth._sign, test_auth.public_key, test_auth.chain = kice._sign, kice.public_key, kice.chain
    servers["평가원 연동 시험 서버"] = test_auth.lookup
    tpub = test_auth.piece_values()
    trec, tsig = test_auth.record(TEST_ID, "모의평가", "AI 서비스 연동 시험", T(14, 0, -14), T(14, 30, -14), tpub, "평가원 연동 시험 서버")
    r = registry.submit(t, trec, tsig, kice.chain, kice.public_key)
    log(t, "시험 기관(한국교육과정평가원)", "연동 시험용 가짜 시험을 30분짜리로 등록", phase=P2,
        saw="연동 시험 문항(실제 시험과 무관)", result=r)
    tbox, tkey = lock(tpub)
    log(t + 600, "AI 서비스", "장부와 잠긴 조각 값 묶음을 받아 동기화", phase=P2,
        result=ai.sync(t + 600, registry, registry.signed_head(t + 600), {trec["exam_id"]: tbox}))
    log(T(14, 0, -14), "시험 기관(한국교육과정평가원)", "연동 시험 시작 시각에 묶음 열쇠 공개", phase=P2,
        result="열쇠 32바이트 공개. AI 서비스: " + ai.open_sets(T(14, 0, -14), {trec["exam_id"]: tkey}))
    tpage, _ = print_page(E, F, 7070, TEST_ID)
    tphoto = E.capture(tpage, dict(E.BASE, view=0.5, Wc=1280), np.random.default_rng(21))
    for tt, act, fn in [
        (T(14, 10, -14), "평가원 점검자가 연동 시험지 사진을 AI 서비스에 입력", lambda tt: ai.photo(tt, tphoto)),
        (T(14, 12, -14), "평가원 점검자가 연동 시험 문항을 글로 입력", lambda tt: ai.text(tt, test_items[0])[0]),
        (T(14, 31, -14), "연동 시험 시간이 끝난 뒤 같은 사진을 입력", lambda tt: ai.photo(tt, tphoto)),
    ]:
        log(tt, "AI 서비스", act, phase=P2, saw="점검자가 보낸 사진 또는 문장", not_seen="연동 시험 문항 원문", result=fn(tt))
    log(T(15, 0, -14), "시험 기관(한국교육과정평가원)", "이행 점검 결과 기록", phase=P2,
        result="시험 시간 중 사진과 문장 모두 거절, 종료 후 정상 답변. 점검 통과 서비스 명단에 추가")

    # 3. exam preparation (one week to four days before) --------------------------------
    seed = 6060
    _, qs = F.exam_page(seed)
    items = [q["text"] for q in qs]
    kice._items = items
    t = T(10, 0, -7)
    log(t, "시험 기관(한국교육과정평가원)", f"6월 모의평가 1교시 문항 {len(items)}개 확정", phase=P3,
        saw="문항 원문(기관 안에만 보관)", result="문항 약속값용 비밀 문자열 생성(시험 후 공개)")
    cand = E.EXAM_ID
    log(t + 600, "시험 기관(한국교육과정평가원)", f"시험 번호 후보 {cand:08X}를 공개 장부에서 조회", phase=P3,
        saw="공개 장부의 기존 시험 번호", result="사용되지 않은 번호" if not registry.has(f"{cand:08X}") else "이미 사용 중")
    kpub = kice.piece_values()
    log(t + 1800, "시험 기관(한국교육과정평가원)", "평가원 조회 서버의 비밀 키로 문항의 4글자 조각을 암호화", phase=P3,
        saw="문항 원문, 조회 비밀 키", result=f"암호화 조각 값 {sum(len(x) + len(y) for x, y in kpub)}개와 묶음 요약값 {set_hash(kpub)[:12]}…")

    t = T(10, 0, -5)
    page, _ = print_page(E, F, seed, cand)
    log(t, "인쇄소", f"시험 번호 {cand:08X}를 담은 보안 문양과 문항을 함께 인쇄", phase=P3,
        saw="문항과 시험 번호(지금도 인쇄소는 문항을 봄)", not_seen="조회 비밀 키, 서명 키", result="시험지 인쇄")
    t = T(10, 0, -4)
    sample = E.capture(page, dict(E.BASE, view=0.25, Wc=960), np.random.default_rng(22))
    found, chunks = X.match_enh(sample, [cand])
    log(t, "시험 기관(한국교육과정평가원)", "인쇄된 시험지 견본을 촬영해 공개 판독기로 검수", phase=P3,
        saw="견본 사진", result=(f"시험지 높이 25%만 찍은 사진에서 시험 번호 {found:08X} 판독(조각 {chunks}/6), 검수 통과"
                              if found == cand else "판독 실패, 인쇄 재검토"))

    # 4. registration and distribution (the day before) ---------------------------------
    t = T(10, 0, -1)
    rec, sig = kice.record(cand, "모의평가", "2027학년도 6월 모의평가 1교시", S, E1, kpub, "평가원 조회 서버")
    r = registry.submit(t, rec, sig, kice.chain, kice.public_key)
    log(t, "시험 기관(한국교육과정평가원)", "시험 번호, 종류, 시간, 문항 약속값, 조각 값 묶음 요약값, 조회 서버 주소에 서명해 제출", phase=P4,
        result=r)
    log(t, "국가 등록부", "인가 사슬, 서명, 번호 중복, 시간 규칙을 확인하고 공개 장부에 추가", phase=P4,
        saw=f"시험 번호 {rec['exam_id']}, 모의평가, {fmt(S)}~{fmt(E1)}, 약속값 {rec['items_commitment'][:12]}…",
        not_seen="문항 원문, 조각 값을 만든 비밀 키", result=r)

    rogue = Ed25519PrivateKey.generate()
    fake = dict(rec, exam_id="0BADC0DE", title="미인가 단체의 임의 등록")
    log(t + 60, "국가 등록부", "인가받지 않은 단체가 평가원 인가서를 내밀며 등록 시도", phase=P4,
        result=registry.submit(t + 60, fake, rogue.sign(canon(fake)).hex(), kice.chain, rogue.public_key()))
    s0 = schools[0]
    sat = dict(rec, exam_id="5A70C0DE", kind="수능", title="학교가 수능 종류로 등록하려는 시도", lookup_server="공용 조회 서버")
    log(t + 120, "국가 등록부", "학교 교원이 수능 종류의 시험을 등록 시도", phase=P4,
        result=registry.submit(t + 120, sat, s0.sign(sat), s0.chain, s0.public_key))
    dup = dict(rec, title="같은 번호의 다른 시험")
    log(t + 180, "국가 등록부", "이미 등록된 시험 번호로 다시 등록 시도", phase=P4,
        result=registry.submit(t + 180, dup, kice.sign(dup), kice.chain, kice.public_key))
    tamper = dict(rec, exam_id="0A11DA75")
    tsig2 = kice.sign(tamper)
    tamper = dict(tamper, window_end=E1 + 6 * 3600)
    log(t + 240, "국가 등록부", "서명 뒤 전송 중에 종료 시각이 6시간 늘어난 기록", phase=P4,
        result=registry.submit(t + 240, tamper, tsig2, kice.chain, kice.public_key))
    long_ = dict(rec, exam_id="0A11DA76", window_end=S + 30 * 3600)
    log(t + 300, "국가 등록부", "인가 기관이 직접 서명한 30시간짜리 차단", phase=P4,
        result=registry.submit(t + 300, long_, kice.sign(long_), kice.chain, kice.public_key))

    plain = {rec["exam_id"]: kpub}
    for i, (sch, other) in enumerate(zip(schools, F.ACTIVE[1:])):
        spub = sch.piece_values()
        srec, ssig = sch.record(other, "학교 내신", f"학교 {i + 1} 기말고사", S, E1, spub, "공용 조회 서버")
        registry.submit(t + 600, srec, ssig, sch.chain, sch.public_key)
        plain[srec["exam_id"]] = spub
    log(t + 600, f"학교 {len(schools)}곳", "교원이 학교 컴퓨터에서 문항 조각을 가린 채 공용 조회 서버로 암호화하고 같은 시간대 기말고사를 등록", phase=P4,
        saw="자기 학교 문항(학교 안에만 보관)", not_seen="다른 학교 문항, 공용 서버의 비밀 키",
        result=f"장부 {len(registry.entries)}건(연동 시험 포함). 공용 조회 서버가 받은 것은 가려진 값뿐(요청 {shared.queries}회)")
    log(t + 600, "등록부 운영 기관", "공용 조회 서버에서 학교 요청에 비밀 키 적용", phase=P4,
        saw="가려진 값", not_seen="학교 문항")

    t = T(11, 0, -1)
    head = registry.signed_head(t)
    log(t, "등록부 운영 기관", "장부 머리(건수와 마지막 연결값)에 운영 기관 키로 서명해 공개", phase=P4,
        result=f"장부 {head['head']['size']}건, 마지막 연결값 {head['head']['head'][:12]}…. 운영 기관이 나중에 장부를 바꾸면 이 서명과 맞지 않음")
    boxes = {eid: lock(pub) for eid, pub in plain.items()}
    dists = {eid: b for eid, (b, _) in boxes.items()}
    keys = {eid: k for eid, (_, k) in boxes.items()}
    log(t + 1800, "시험 기관과 학교", "암호화 조각 값 묶음을 잠가서 AI 서비스에 배포", phase=P4,
        result=f"잠긴 묶음 {len(dists)}건. 여는 열쇠는 각 시험 기관이 시험 시작 시각까지 보관. 각 묶음의 요약값은 장부의 등록 기록에 들어 있음")
    log(t + 3600, "AI 서비스", "장부를 직접 재검증하고 잠긴 묶음을 보관", phase=P4,
        saw="등록 시험의 번호, 종류, 시간, 잠긴 묶음", not_seen="문항 원문, 조각 값, 조회 비밀 키",
        result=ai.sync(t + 3600, registry, head, dists))
    guesses = sorted(op_pieces(items[0])[0])
    log(t + 3700, "AI 서비스 내부자", "시험 문항을 미리 알아내려고 추측한 조각을 조회 서버로 암호화해 묶음과 대조", phase=P4,
        saw="추측한 조각의 암호화 값, 잠긴 묶음", not_seen="열린 조각 값",
        result=f"실제 문항의 조각 {len(guesses)}개를 그대로 추측해도 대조할 값이 없어 일치 {ai.insider_guess(kice.lookup, guesses)}건. 묶음이 열려 있었다면 추측만으로 문항을 복원할 수 있음(E11)")

    windows = [dict(exam_id=e["record"]["exam_id"], start=e["record"]["window_start"], end=e["record"]["window_end"])
               for e in registry.entries if e["record"]["window_end"] > t]
    package = dict(windows=windows, head=head["head"])
    psig = maker_key.sign(canon(package)).hex()
    device = Device(maker_key.public_key())
    log(t + 7200, "기기 제조사", "장부 머리 서명을 확인하고 시험 번호·시간 목록만 뽑아 제조사 서명으로 기기에 배포", phase=P4,
        saw=f"시험 {len(windows)}건의 번호와 시간", not_seen="문항, 조각 값, 사용자 사진",
        result=device.install(package, psig))
    forged = dict(package, windows=windows + [dict(exam_id="DEADBEEF", start=S, end=S + 20 * 3600)])
    log(t + 7260, "기기", "누군가 시험 하나를 끼워 넣은 목록을 받음", phase=P4,
        result=Device(maker_key.public_key()).install(forged, psig))

    t = T(18, 0, -1)
    tomorrow = [e["record"] for e in registry.entries if e["record"]["window_start"] > t]
    longest = max((r_["window_end"] - r_["window_start"]) // 60 for r_ in tomorrow)
    log(t, "누구나", "공개 장부에서 다음 날 차단될 시험을 미리 확인", phase=P4,
        saw="공개 장부 전체", not_seen="문항, 사용자 정보",
        result=f"내일 등록 시험 {len(tomorrow)}건(모의평가 1, 학교 내신 {len(tomorrow) - 1}), 가장 긴 차단 {longest}분, 모두 교육부까지 인가 사슬 확인")

    # 5. exam day ------------------------------------------------------------------------
    P5, P6 = "5. 시험 당일", "6. 시험 후"
    textbook_text, _ = F.exam_page(seed + 1)
    textbook = E.print_sim(E.compose(textbook_text, None, None), np.random.default_rng(5))
    photo_svc = E.capture(page, dict(E.BASE, view=0.35, Wc=1280), np.random.default_rng(11))
    photo_gls = E.capture(page, dict(E.BASE, view=0.5, Wc=960, defocus=1.0), np.random.default_rng(12))
    photo_book = E.capture(textbook, dict(E.BASE, view=0.35, Wc=1280), np.random.default_rng(13))
    for n, im in (("photo_exam_phone", photo_svc), ("photo_exam_glasses", photo_gls), ("photo_textbook", photo_book), ("photo_print_sample", sample)):
        cv2.imwrite(os.path.join(a.out, n + ".png"), cv2.cvtColor(im, cv2.COLOR_RGB2BGR))
    q_exam = items[0]
    q_practice = "어떤 수에 5를 곱한 후 21을 더하면 96이다. 이 수를 구하시오."
    q_other = "광합성에서 빛 에너지가 화학 에너지로 바뀌는 과정을 설명해 줘."
    for tt, who, act, fn in [
        (T(8, 20), "AI 서비스", "시험 시작 전, 시험지 사진 입력", lambda tt: ai.photo(tt, photo_svc)),
        (S, "KEY", "", None),
        (T(9, 5), "AI 서비스", "시험 중, 휴대폰으로 찍은 시험지 일부 사진", lambda tt: ai.photo(tt, photo_svc)),
        (T(9, 7), "AI 서비스", "시험 중, 교과서 사진(시험지 아님)", lambda tt: ai.photo(tt, photo_book)),
        (T(9, 10), "AI 서비스", "시험 중, 시험 문제를 글로 옮겨 입력", lambda tt: ai.text(tt, q_exam)[0]),
        (T(9, 12), "AI 서비스", "시험 중, 띄어쓰기와 말투를 바꿔 입력", lambda tt: ai.text(tt, q_exam.replace(" ", "").replace("구하시오", "구해줘"))[0]),
        (T(9, 14), "AI 서비스", "시험 중, 숫자만 다른 같은 유형 연습문제", lambda tt: ai.text(tt, q_practice)[0]),
        (T(9, 16), "AI 서비스", "시험 중, 시험과 무관한 학습 질문", lambda tt: ai.text(tt, q_other)[0]),
        (T(9, 20), "기기 내장 AI", "시험 중, 안경 카메라로 찍은 시험지 사진(인터넷 없음)", lambda tt: device.photo(tt, photo_gls)),
        (T(9, 22), "기기 내장 AI", "시험 중, 같은 기기에 문제를 글로 입력", lambda tt: device.text(tt, q_exam)),
        (T(10, 1), "AI 서비스", "시험 종료 1분 뒤, 같은 시험지 사진", lambda tt: ai.photo(tt, photo_svc)),
        (T(10, 2), "AI 서비스", "시험 종료 뒤, 같은 문제를 글로 입력", lambda tt: ai.text(tt, q_exam)[0]),
    ]:
        if who == "KEY":
            log(tt, "시험 기관과 학교", "시험 시작 시각에 묶음 열쇠를 공개", phase=P5,
                result=f"열쇠 {len(keys)}개(각 32바이트) 공개")
            forged_box = dict(dists[rec["exam_id"]], ct=dists[rec["exam_id"]]["ct"][:-1] + bytes([dists[rec["exam_id"]]["ct"][-1] ^ 1]))
            check = AIService("검증용", ministry.public_key, servers)
            check.sync(tt, registry, head, dict(dists, **{rec["exam_id"]: forged_box}))
            log(tt, "AI 서비스", "열쇠로 묶음을 열고 장부의 요약값과 대조(배포 중에 한 묶음이 변조된 경우)", phase=P5,
                saw="열린 조각 값", not_seen="문항 원문, 조회 비밀 키", result=check.open_sets(tt, keys))
            log(tt, "AI 서비스", "열쇠로 묶음을 열고 장부의 요약값과 대조", phase=P5,
                saw="열린 조각 값", not_seen="문항 원문, 조회 비밀 키", result=ai.open_sets(tt, keys))
            continue
        q0 = (kice.lookup.queries, shared.queries)
        res = fn(tt)
        saw = "사용자가 보낸 사진 또는 문장(" + ("서비스" if who == "AI 서비스" else "기기") + " 안에서만 처리)"
        log(tt, who, act, phase=P5, saw=saw, not_seen="문항 원문" if who == "AI 서비스" else "문항 원문, 문장 조회 수단", result=res)
        if (kice.lookup.queries, shared.queries) != q0:
            log(tt, "평가원·공용 조회 서버", "가려진 조각에 비밀 키를 적용해 돌려줌", phase=P5,
                saw="가려진 값(질문마다 무작위로 바뀜)", not_seen="사용자의 질문, 사용자가 누구인지", result="판정은 AI 서비스가 함")
    late = dict(rec, exam_id="1A7E0001", title="시험 시작 뒤 추가 등록")
    log(T(9, 30), "국가 등록부", "시험이 이미 시작된 뒤 평가원이 다른 시험을 추가 등록 시도", phase=P5,
        result=registry.submit(T(9, 30), late, kice.sign(late), kice.chain, kice.public_key))

    # 6. after -------------------------------------------------------------------------
    t = T(12, 0)
    salt, revealed = kice.reveal()
    ok = hashlib.sha256((salt + "\n".join(revealed)).encode()).hexdigest() == rec["items_commitment"]
    log(t, "시험 기관(한국교육과정평가원)", "시험 종료 후 문항과 약속값의 비밀 문자열을 공개", phase=P6, result="공개 완료")
    prev, chain_ok = "0" * 64, True
    for e in registry.entries:
        body = {k: v for k, v in e.items() if k != "hash"}
        chain_ok &= (e["prev"] == prev and hashlib.sha256(canon(body)).hexdigest() == e["hash"])
        prev = e["hash"]
    log(t, "누구나(사후 검증)", "공개 장부와 공개된 문항을 대조", phase=P6,
        saw="공개 장부 전체, 공개된 문항", not_seen="사용자의 질문",
        result=f"장부 연결 {'정상' if chain_ok else '변조'}, 전날 공개된 장부 머리와 {'일치' if prev == head['head']['head'] else '불일치'},"
               f" 문항이 시험 전 약속값과 {'일치' if ok else '불일치'}, 이 시험의 차단 시간은 {fmt(S)}~{fmt(E1)}")
    log(t, "AI 서비스", "시험별 거절 건수를 교육부에 보고(기기 내장 AI의 거절은 제조사가 따로 집계)", phase=P6,
        not_seen="개인 정보(저장하지 않음)",
        result=", ".join(f"시험 {k}: {v}건" for k, v in ai.refusals.items() if k != f"{TEST_ID:08X}") or "0건")

    roles = [
        ("교육부", "인가 키, 인가·지정 기록, 시험별 거절 건수", "문항, 시험지, 사용자 입력"),
        ("교육청", "위임받은 인가 키(학교 내신만)", "학교 문항, 사용자 입력"),
        ("등록부 운영 기관", "공개 장부, 장부 머리 서명 키, 공용 조회 서버 비밀 키", "문항 원문, 사용자의 질문과 신원"),
        ("시험 기관", "자기 문항 원문, 서명 키, 조회 비밀 키", "사용자의 질문과 신원, 다른 기관의 문항"),
        ("인쇄소", "문항과 시험 번호(현행과 같음)", "서명 키, 조회 비밀 키"),
        ("AI 서비스", "공개 장부, 잠긴 암호화 조각 값(시험 시작 시각에 열림), 사용자 입력(서비스 안)", "문항 원문, 조회 비밀 키, 시험 전의 조각 값"),
        ("기기 제조사와 기기", "시험 번호와 시간 목록", "문항, 조각 값, 사용자 사진(기기 밖으로 나가지 않음)"),
        ("누구나", "공개 장부, 시험 후 공개된 문항, 시험별 거절 건수", "사용자의 질문과 신원"),
    ]
    print("\n역할별 정보")
    for r_ in roles:
        print(f"  {r_[0]}: 가진 것 = {r_[1]} / 갖지 않은 것 = {r_[2]}")
    out = dict(exam=dict(exam_id=rec["exam_id"], title=rec["title"], start=fmt(S), end=fmt(E1)),
               trace=TRACE, roles=[dict(role=a_, has=b_, lacks=c_) for a_, b_, c_ in roles])
    json.dump(out, open(os.path.join(a.out, "trace.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    write_outputs(out, a.out)
    print(f"\n기록: {a.out}/trace.json, 시간표: {a.out}/operation_demo.html, {a.out}/operation_demo.md, 사진: {a.out}/photo_*.png")


def write_outputs(out, d):
    esc = html.escape
    ex = out["exam"]
    rows, md_rows, phase = [], [], None
    cell = lambda x: x.replace("|", "/")
    for e in out["trace"]:
        if e.get("phase") and e["phase"] != phase:
            phase = e["phase"]
            rows.append(f"<tr class='ph'><td colspan='6'>{esc(phase)}</td></tr>")
            md_rows.append(f"| **{phase}** | | | | | |")
        cls = "refuse" if "답변 거절" in e["result"] else ("reject" if e["result"].startswith("거부") else "")
        rows.append(f"<tr class='{cls}'><td class='t'>{esc(e['time'])}</td><td class='a'>{esc(e['actor'])}</td>"
                    f"<td>{esc(e['action'])}</td><td>{esc(e['saw'])}</td><td>{esc(e['not_seen'])}</td><td class='r'>{esc(e['result'])}</td></tr>")
        md_rows.append(f"| {e['time']} | {cell(e['actor'])} | {cell(e['action'])} | {cell(e['saw'])} | {cell(e['not_seen'])} | {cell(e['result'])} |")
    roles = "".join(f"<tr><td class='a'>{esc(r['role'])}</td><td>{esc(r['has'])}</td><td>{esc(r['lacks'])}</td></tr>" for r in out["roles"])
    intro = (f"{ex['title']}, 시험 번호 {ex['exam_id']}, 시험 시간 {ex['start']}~{ex['end']}. "
             "각 기관은 자기가 가진 정보만으로 움직입니다. 판정은 `code/operation_demo.py`를 실행한 실제 계산 결과입니다. "
             "사진은 시뮬레이션으로 만든 것이며, 보안 문양은 실험에 쓴 진한 농도(70%)로 인쇄했습니다(목표 외관은 훨씬 옅음). "
             "키는 실행할 때마다 새로 만들어지므로 약속값, 요약값, 연결값은 실행마다 달라집니다.")
    page = f"""<!DOCTYPE html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>시험 보호 국가 등록제: 운영 과정 시연</title><style>
body{{font-family:"Noto Sans KR","Apple SD Gothic Neo","Malgun Gothic",sans-serif;margin:24px;color:#111;line-height:1.55;max-width:1200px}}
h1{{font-size:22px;margin:0 0 4px}} p.sub{{margin:0 0 18px}}
table{{border-collapse:collapse;width:100%;font-size:13px;margin:10px 0 24px}} th,td{{border:1px solid #ccc;padding:6px 8px;vertical-align:top;text-align:left;word-break:keep-all}}
th{{background:#f2f2f2}} td.t{{white-space:nowrap;font-variant-numeric:tabular-nums}} td.a{{font-weight:600}}
tr.ph td{{background:#222;color:#fff;font-weight:700}} tr.refuse td.r{{background:#fff3c4;font-weight:600}} tr.reject td.r{{background:#f3e0e0}}
.wrap{{overflow-x:auto}}</style></head><body>
<h1>시험 보호 국가 등록제: 운영 과정 시연</h1><p class="sub">{esc(intro)}</p>
<h2>시간 순서</h2><div class="wrap"><table><tr><th>시각</th><th>주체</th><th>한 일</th><th>본 것</th><th>보지 못한 것</th><th>결과</th></tr>{''.join(rows)}</table></div>
<h2>역할별 정보</h2><div class="wrap"><table><tr><th>역할</th><th>가진 것</th><th>갖지 않은 것</th></tr>{roles}</table></div>
<p class="sub">코드: github.com/exam-registry-kr/exam-registry · <code>python operation_demo.py</code></p></body></html>"""
    open(os.path.join(d, "operation_demo.html"), "w", encoding="utf-8").write(page)
    md = ["# 운영 과정 시연\n", intro + "\n", "## 시간 순서\n", "| 시각 | 주체 | 한 일 | 본 것 | 보지 못한 것 | 결과 |", "|---|---|---|---|---|---|"]
    md += md_rows + ["", "## 역할별 정보\n", "| 역할 | 가진 것 | 갖지 않은 것 |", "|---|---|---|"]
    md += [f"| {r['role']} | {r['has']} | {r['lacks']} |" for r in out["roles"]]
    open(os.path.join(d, "operation_demo.md"), "w", encoding="utf-8").write("\n".join(md) + "\n")


if __name__ == "__main__":
    main()
