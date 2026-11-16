"""E9: Korean items, and items that contain no numbers.

Two gaps left by E3, E7 and E8:
  1. Every test item so far was an English sentence. The proposal describes 4-character
     pieces of Korean text.
  2. The rule requires the question's numbers to appear in the registered item, and a
     question without numbers is never refused. Reading, social studies and history
     items often have no numbers, so the content lookup could not protect them.

Items (180 registered together)
  EN  60  English word problems of E3 (unchanged)
  KN  60  Korean word problems, 12 templates, same construction as E3
  KT  60  Korean multiple-choice items without numbers: a stem (발문), a passage of
          4 to 6 sentences and five choices marked with circled digits

Questions
  rewrites of every registered item (format, reorder, partial copy, synonym, combined;
  for KT also: choice marks typed as "1)", choices left out, passage only)
  practice problems that must NOT be refused: 240 per group from the same generators
  (same templates, same stems, same vocabulary, different values)
  KT only: the 10 stems alone, and "same passage, different question" (reported
  separately: the passage itself is exam content)

Rules compared
  R0  E8 rule as it is: top item by share of pieces, share >= 0.5, the question has
      numbers and all of them (with repetition) are in the item
  R1  naive extension: Unicode NFKC first (so a circled 1 and a typed 1 are the same),
      and a question with no number other than 1 to 5 is refused on share >= 0.5 alone
  R2  proposed: as R1, but for a question with no number other than 1 to 5
      the authority marks the pieces of its stems when it registers; those pieces are
      removed from the question; the question is refused only if at least 20 of the
      remaining pieces are found in one item and they are at least a share S of what
      remains. S is chosen on one set of items (lowest value in the sweep at which no
      practice problem is refused) and then fixed and tested on a new set of items.
  R3  chosen later in E14 on more kinds of question: as R2, but at least min(60, 60% of the
      matched item's own pieces) must match, share 0.6 (E9's values refused quoted parts of
      practice problems)

A question with a number other than 1 to 5 is handled by R1 and R2 exactly as in E8.
Baseline: R0 on the EN items alone must reproduce E8's figures at 60 items.

The rules use only set operations on piece values, so they can run on encrypted piece
values. This is checked directly on every 5th question with the P-256 lookup of E7.

    python e9_korean_text_items.py          # about two minutes
"""
import json, re, sys, unicodedata
from collections import Counter, defaultdict
import numpy as np
import e3_registry as E3
import e7_oprf_lookup as O7
from e7_oprf_lookup import pieces, regenerate_e3, TH
from e8_registry_scale import numbers_count

SEED_SELECT, SEED_VALIDATE = 20261119, 20261120
M_MIN = 20
# Rule R3, chosen later in E14: for a question without numbers, at least min(CAP, FRAC x the
# matched item's own pieces) pieces must match, and the share must be at least SHARE.
R3_VALUES = dict(cap=60, frac=0.6, share=0.6)
SWEEP_M, SWEEP_TH = [0, 10, 20, 30], [0.5, 0.6, 0.7, 0.8]

# ---------------------------------------------------------------- Korean word problems (KN)
NAMES = ["민지", "준호", "소라", "지수", "태오", "예나", "서하", "다미"]
THINGS = ["사과", "연필", "구슬", "동전", "카드", "스티커"]
KN_TEMPLATES = [
    "{a}는 {it} {x}개를 가지고 있다. {b}가 {a}에게 {it} {y}개를 더 주었고, {a}는 그중 {z}개를 나누어 주었다. 남은 {it}의 개수를 구하시오.",
    "기차가 {y}시간 동안 {x}km를 달렸다. 같은 속력으로 {z}시간 동안 달리면 몇 km를 가는가?",
    "두 수의 합은 {x}이고 차는 {y}이다. 두 수 중 큰 수를 구하시오.",
    "둘레의 길이가 {x}cm이고 가로의 길이가 {y}cm인 직사각형의 넓이는 몇 제곱센티미터인가?",
    "함수 f(x) = {x}x^2 - {y}x + {z}에 대하여 f(2)의 값을 구하시오.",
    "{a}는 매일 {x}원씩 {y}일 동안 저금한 뒤 {z}원을 썼다. 남은 돈은 얼마인가?",
    "주머니에 빨간 공 {x}개와 파란 공 {y}개가 들어 있다. 이 주머니에서 공 {z}개를 차례로 꺼낼 때, 모두 빨간 공일 확률을 구하시오.",
    "첫째항이 {x}이고 공차가 {y}인 등차수열의 제{z}항을 구하시오.",
    "어느 가게에서 {it} 한 개를 {x}원에 판다. {a}가 {it} {y}개를 사고 {z}원짜리 지폐를 냈을 때, 거스름돈은 얼마인가?",
    "반지름의 길이가 {x}cm인 원에 내접하는 정사각형의 넓이를 {y}와 {z}를 이용하여 나타내시오.",
    "첫째항이 {x}이고 공비가 {y}인 등비수열의 첫째항부터 제{z}항까지의 합을 구하시오.",
    "학생 {x}명인 학급에서 수학을 좋아하는 학생은 {y}명, 과학을 좋아하는 학생은 {z}명이고, 모든 학생이 적어도 한 과목을 좋아한다. 두 과목을 모두 좋아하는 학생은 몇 명인가?",
]

# ---------------------------------------------------------------- Korean text items (KT)
STEMS = [
    "다음 글의 중심 내용으로 가장 적절한 것은?",
    "다음 글에 대한 이해로 적절하지 않은 것은?",
    "다음 글의 내용과 일치하는 것은?",
    "다음 글을 읽고 추론한 내용으로 가장 적절한 것은?",
    "다음 글의 주제로 가장 적절한 것은?",
    "다음 자료에 대한 설명으로 옳은 것은?",
    "다음 글에서 글쓴이가 주장하는 바로 가장 적절한 것은?",
    "다음 글의 내용을 바탕으로 <보기>를 이해한 것으로 적절하지 않은 것은?",
    "다음 자료에 대한 분석으로 옳은 것만을 있는 대로 고른 것은?",
    "다음 글의 서술상 특징으로 가장 적절한 것은?",
]
TOPICS = ["산업 혁명", "광합성", "시장 경제", "판소리", "민주주의", "기후 변화", "인쇄술", "도시화", "면역 반응",
          "언어의 변화", "조선 후기 실학", "지각 변동", "삼권 분립", "수요와 공급", "문화 상대주의", "세포 호흡",
          "근대 소설", "정보 사회", "해양 순환", "고려 청자"]
NOUNS = ["사회 구조", "기술 발전", "자원 분배", "개인의 선택", "제도적 장치", "환경 조건", "에너지 흐름", "집단 의식",
         "전통적 가치", "경제적 유인", "정치 참여", "지역 간 교류", "생산 방식", "인구 이동", "교육 기회", "표현 양식",
         "물질 순환", "권력 관계", "소비 습관", "과학적 방법", "역사적 맥락", "국제 협력", "정보 격차", "세대 간 차이"]
FRAMES = [
    "{T}에 대한 기존의 설명은 {A}에 주목하였다.",
    "그러나 최근의 연구는 {B}의 역할을 강조한다.",
    "{T}의 과정에서 {A}의 변화가 먼저 나타난다.",
    "이러한 변화는 {B}에 영향을 주어 새로운 균형을 만든다.",
    "따라서 {T}에 관한 이해는 {A}, {B}의 관계를 함께 살필 때 깊어진다.",
    "일부 학자들은 {A}의 중요성이 과장되었다고 본다.",
    "{B}의 측면에서 보면 {T}의 의미는 달라진다.",
    "당시 사람들은 {A}에 의존하여 생활하였다.",
    "이 시기에 {B}에 대한 관심이 크게 늘어났다.",
    "결국 {T}의 핵심은 {A}에서 찾을 수 있다.",
    "{T}에 대한 평가는 {B}에 따라 엇갈린다.",
    "예를 들어 {A}의 사례는 이 점을 잘 보여 준다.",
    "{A}에 변동이 생기면 {T}의 양상도 함께 바뀐다.",
    "초기에는 {B}의 영향이 거의 드러나지 않았다.",
    "{T}의 확산은 {A}에 뚜렷한 흔적을 남겼다.",
    "이와 달리 {B}에 기반한 설명은 한계를 보인다.",
    "오늘날에는 {A}에 관한 자료가 꾸준히 축적되고 있다.",
    "{T}의 배경에는 오랜 기간 누적된 {B}의 문제가 있었다.",
    "한편 {A}에 대한 규제는 예상과 다른 결과를 낳았다.",
    "{B}의 관점은 {T}에 대한 통념을 뒤집는다.",
    "이 과정에서 {A}, {B}의 경계는 점차 흐려진다.",
    "그 결과 {T}의 속도는 지역마다 다르게 나타났다.",
    "{A}에 주목한 연구자들은 장기적인 추세를 중시한다.",
    "반면 {B}의 효과는 짧은 기간에만 관찰된다.",
    "{T}에 관한 기록은 대부분 {A}의 형태로 전해진다.",
    "이는 {B}의 개념을 다시 정의해야 함을 뜻한다.",
    "실제로 {A}의 수준이 높을수록 {T}의 영향은 커진다.",
    "그럼에도 {B}에 대한 합의는 아직 이루어지지 않았다.",
    "{T}의 사례는 {A}에 관한 논쟁을 다시 불러일으켰다.",
    "이처럼 {B}의 조건이 갖추어질 때 변화가 시작된다.",
]
CHOICES = [
    "{A}의 변화가 {T}의 원인이다.",
    "{T}의 의미는 {B}에 따라 달라진다.",
    "{A}보다 {B}의 역할이 더 중요하다.",
    "{T}에 대한 기존의 설명은 수정될 필요가 없다.",
    "{B}에 대한 관심은 점차 줄어들었다.",
    "{A}의 사례는 {T}에 적용되지 않는다.",
    "{T}의 과정에서 {B}의 변화는 나타나지 않는다.",
    "{A}, {B}의 관계는 {T}에 영향을 주지 않는다.",
    "{T}의 확산은 {A}에 의해 늦추어졌다.",
    "{B}에 기반한 설명이 가장 널리 받아들여진다.",
]
MARKS = "①②③④⑤"
SYN_KO = {"구하시오": "구하여라", "가지고 있다": "갖고 있다", "달렸다": "이동했다", "넓이": "면적", "확률": "가능성",
          "좋아하는": "선호하는", "남은": "남아 있는", "꺼낼 때": "뽑을 때", "나타내시오": "표현하시오", "얼마인가": "얼마일까",
          "가장 적절한 것은": "제일 알맞은 것은", "적절하지 않은 것은": "알맞지 않은 것은", "옳은 것": "맞는 것",
          "다음 글": "아래 글", "다음 자료": "아래 자료", "그러나": "하지만", "따라서": "그러므로", "강조한다": "중시한다",
          "주목하였다": "초점을 두었다", "나타난다": "드러난다", "영향을 주어": "영향을 미쳐", "예를 들어": "가령",
          "보여 준다": "드러낸다", "달라진다": "바뀐다", "크게 늘어났다": "많이 증가하였다", "중요하다": "핵심적이다",
          "줄어들었다": "감소하였다", "결국": "요컨대", "일부 학자들은": "몇몇 연구자는", "한편": "그런데"}


def make_kn(ti, r):
    a, b = r.choice(NAMES, 2, replace=False)
    return KN_TEMPLATES[ti].format(a=a, b=b, it=r.choice(THINGS), x=int(r.integers(5, 400)),
                                   y=int(r.integers(2, 90)), z=int(r.integers(2, 30)))


def fill(frame, topic, r):
    a, b = r.choice(NOUNS, 2, replace=False)
    return frame.format(T=topic, A=a, B=b)


def make_passage(r):
    topic = r.choice(TOPICS)
    k = int(r.integers(4, 7))
    return topic, " ".join(fill(FRAMES[i], topic, r) for i in r.choice(len(FRAMES), k, replace=False))


def make_choices(topic, r):
    return " ".join(f"{MARKS[j]} {fill(CHOICES[i], topic, r)}" for j, i in enumerate(r.choice(len(CHOICES), 5, replace=False)))


def make_kt(si, r):
    """Returns (item text, stem, passage, topic)."""
    topic, passage = make_passage(r)
    return f"{STEMS[si]} {passage} {make_choices(topic, r)}", STEMS[si], passage, topic


def split_sents(q):
    return [s for s in re.split(r"(?<=[.?])\s+", q) if s]


def rewrites(q, r, kt=None):
    out = {}
    out["format"] = re.sub(" ", "  ", q).replace(".", " .\n")
    sents = split_sents(q)
    out["reorder"] = " ".join(sents[1:] + sents[:1]) if len(sents) > 1 else q
    w = q.split(); k = max(6, int(len(w) * 0.6)); st = int(r.integers(0, len(w) - k + 1))
    out["partial"] = " ".join(w[st:st + k])
    s = q
    for a, b in SYN_KO.items():
        s = s.replace(a, b)
    out["synonym"] = s
    ss = split_sents(s)
    out["combined"] = re.sub(" ", "  ", " ".join(ss[1:] + ss[:1])).replace(".", " .\n")
    if kt:
        stem, passage = kt
        t = q
        for j, m in enumerate(MARKS):
            t = t.replace(m, f"{j + 1})")
        out["typed_marks"] = t
        out["no_choices"] = f"{stem} {passage}"
        out["passage_only"] = passage
    return out


# ---------------------------------------------------------------- pieces and rules
def nk(text):
    return unicodedata.normalize("NFKC", text)


def strong_number(text):
    """True if the question has a number other than 1 to 5 (those may be only choice marks).
    Circled digits are always choice marks and are left out here."""
    t = re.sub("[\u2460-\u2473]", " ", text)
    return any(n not in ("1", "2", "3", "4", "5") for n in re.findall(r"\d+(?:\.\d+)?", nk(t).lower().replace(",", "")))


class Registry:
    """What a cooperating service holds: piece sets, number sets and marked stem pieces per item.
    `raw` keeps the E8 form (no NFKC) for the R0 baseline."""

    def __init__(self, items, stems):
        self.g = [pieces(nk(t))[0] for t in items]
        self.n = [numbers_count(nk(t)) for t in items]
        self.stem = set().union(*[pieces(nk(s))[0] for s in stems if s]) if any(stems) else set()
        self.g0 = [pieces(t)[0] for t in items]
        self.n0 = [numbers_count(t) for t in items]
        self.inv, self.inv0 = defaultdict(list), defaultdict(list)
        for i in range(len(items)):
            for x in self.g[i]:
                self.inv[x].append(i)
            for x in self.g0[i]:
                self.inv0[x].append(i)

    @staticmethod
    def _top(inv, qg):
        c = Counter()
        for x in qg:
            for i in inv.get(x, ()):
                c[i] += 1
        if not c:
            return -1, 0
        v = max(c.values())
        return min(k for k, n in c.items() if n == v), v

    def r0(self, q):
        qg, qn = pieces(q)[0], numbers_count(q)
        i, v = self._top(self.inv0, qg)
        s = v / max(1, len(qg))
        return bool(i >= 0 and s >= TH and len(qn) > 0 and qn <= self.n0[i]), i, s

    def _numeric(self, q):
        qg, qn = pieces(nk(q))[0], numbers_count(nk(q))
        i, v = self._top(self.inv, qg)
        s = v / max(1, len(qg))
        return bool(i >= 0 and s >= TH and qn <= self.n[i]), i, s

    def r1(self, q):
        if strong_number(q):
            return self._numeric(q)
        qg = pieces(nk(q))[0]
        i, v = self._top(self.inv, qg)
        s = v / max(1, len(qg))
        return bool(i >= 0 and s >= TH), i, s

    def r3(self, q, cap=R3_VALUES["cap"], frac=R3_VALUES["frac"], th=R3_VALUES["share"]):
        """R2 with a floor that grows with the matched item: min(cap, ceil(frac x its pieces))."""
        if strong_number(q):
            return self._numeric(q)
        rest = pieces(nk(q))[0] - self.stem
        i, v = self._top(self.inv, rest)
        s = v / max(1, len(rest))
        floor = min(cap, -(-frac * len(self.g[i] - self.stem) // 1)) if i >= 0 else cap
        return bool(i >= 0 and v >= floor and s >= th), i, s

    def r2(self, q, m=M_MIN, th=0.5):
        if strong_number(q):
            return self._numeric(q)
        rest = pieces(nk(q))[0] - self.stem
        i, v = self._top(self.inv, rest)
        s = v / max(1, len(rest))
        return bool(i >= 0 and v >= m and s >= th), i, s


def build(seed):
    """All items and questions. Each question: (group, kind, index of its item or -1, text)."""
    en_reg, en_neg, en_pos = regenerate_e3()
    r = np.random.default_rng(seed)
    kn_reg = [make_kn(i % 12, r) for i in range(60)]
    kn_neg = [make_kn(i % 12, r) for i in range(240)]
    kt_full = [make_kt(i % 10, r) for i in range(60)]
    kt_reg = [t[0] for t in kt_full]
    kt_neg = [make_kt(i % 10, r)[0] for i in range(240)]
    items = en_reg + kn_reg + kt_reg
    stems = [""] * 120 + [t[1] for t in kt_full]
    qs = [("EN", k, qi, v) for k, qi, v in en_pos]
    for j, q in enumerate(kn_reg):
        qs += [("KN", k, 60 + j, v) for k, v in rewrites(q, r).items()]
    for j, (q, stem, passage, _) in enumerate(kt_full):
        qs += [("KT", k, 120 + j, v) for k, v in rewrites(q, r, (stem, passage)).items()]
    qs += [("EN", "practice", -1, q) for q in en_neg] + [("KN", "practice", -1, q) for q in kn_neg]
    qs += [("KT", "practice", -1, q) for q in kt_neg]
    qs += [("KT", "stem_only", -1, s) for s in STEMS]
    for j, (q, stem, passage, topic) in enumerate(kt_full):      # same passage, another stem and new choices
        other = STEMS[(STEMS.index(stem) + 1 + int(r.integers(0, 9))) % 10]
        qs.append(("KT", "same_passage_other_question", -1, f"{other} {passage} {make_choices(topic, r)}"))
    return items, stems, qs, len(en_reg)


def encrypted_check(items, stems, qs, reg, th_t, step=5):
    """R2 recomputed from encrypted piece values only (P-256 lookup of E7) on every `step`-th question."""
    auth = O7.Authority(items, lambda t: (pieces(nk(t))[0], numbers_count(nk(t))))
    stem_f = {auth._F(x) for x in reg.stem}                 # published by the authority with the item sets
    same, total = 0, 0
    for group, kind, qi, q in qs[::step]:
        fg = O7.oprf(auth, pieces(nk(q))[0])
        if strong_number(q):
            fn = O7.oprf(auth, numbers_count(nk(q)))
            best, idx = 0, -1
            for i, (pg, pn) in enumerate(auth.published):
                v = len(fg & pg)
                if v > best:
                    best, idx = v, i
            hit = idx >= 0 and best / max(1, len(fg)) >= TH and fn <= auth.published[idx][1]
        else:
            rest = fg - stem_f
            best, idx = 0, -1
            for i, (pg, _) in enumerate(auth.published):
                v = len(rest & pg)
                if v > best:
                    best, idx = v, i
            hit = idx >= 0 and best >= M_MIN and best / max(1, len(rest)) >= th_t
        plain_hit, plain_i, _ = reg.r2(q, M_MIN, th_t)
        same += (bool(hit) == plain_hit) and (idx == plain_i or not plain_hit and not hit)
        total += 1
    return dict(identical=same, total=total, every=step)


NEG = ("practice", "stem_only", "same_passage_other_question")


def evaluate(seed, th_t):
    items, stems, qs, n_en = build(seed)
    reg = Registry(items, stems)
    rules = dict(R0=reg.r0, R1=reg.r1, R2=lambda q: reg.r2(q, M_MIN, th_t), R3=reg.r3)
    rows = []
    for group, kind, qi, q in qs:
        row = dict(group=group, kind=kind, item=qi, strong_number=strong_number(q))
        for name, f in rules.items():
            hit, i, s = f(q)
            row[name], row[name + "_item"], row[name + "_score"] = hit, i, round(s, 4)
        rows.append(row)
    table = {}
    for group in ("EN", "KN", "KT"):
        g = [r for r in rows if r["group"] == group]
        pos = [r for r in g if r["kind"] not in NEG]
        table[group] = dict(
            n_rewritten=len(pos),
            refused_rewritten={n: round(float(np.mean([r[n] for r in pos])), 4) for n in rules},
            refused_rewritten_matching_its_own_item={n: round(float(np.mean([r[n] and r[n + "_item"] == r["item"] for r in pos])), 4) for n in rules},
            refused_by_rewrite={k: {n: round(float(np.mean([r[n] for r in pos if r["kind"] == k])), 4) for n in rules}
                                for k in dict.fromkeys(r["kind"] for r in pos)},
            refused_other={k: {n: int(sum(r[n] for r in g if r["kind"] == k)) for n in rules} | {"of": sum(r["kind"] == k for r in g)}
                           for k in NEG if any(r["kind"] == k for r in g)},
            practice_highest_score={n: max(r[n + "_score"] for r in g if r["kind"] == "practice") for n in rules},
            rewritten_lowest_score_R2=min(r["R2_score"] for r in pos))
    return items, stems, qs, n_en, reg, rows, table


def show(table):
    for group in ("EN", "KN", "KT"):
        t = table[group]
        print("  ", group, "rewritten refused", t["refused_rewritten"])
        for k, v in t["refused_other"].items():
            print(f"      {k}: refused R0 {v['R0']}, R1 {v['R1']}, R2 {v['R2']}, R3 {v['R3']} of {v['of']}")


def main():
    out_path = sys.argv[1] if len(sys.argv) > 1 else "E9-001_results.json"
    out = dict(experiment="E9-001", seeds=dict(select=SEED_SELECT, validate=SEED_VALIDATE),
               n_registered=dict(EN=60, KN=60, KT=60), threshold_numeric=TH, min_pieces_text=M_MIN,
               r3_values_from_E14=R3_VALUES)

    # baseline: R0 with the EN items alone = E8 at 60 items
    items, stems, qs, n_en = build(SEED_SELECT)
    base = Registry(items[:n_en], stems[:n_en])
    e8 = json.load(open("../results/E8-001_results.json"))["by_size"]["60"]
    en = [q for q in qs if q[0] == "EN"]
    kinds_en = ["format", "numbers", "reorder", "partial", "synonym", "combined"]
    mine = {k: round(float(np.mean([(lambda h: h[0] and h[1] == qi)(base.r0(q)) for _, kk, qi, q in en if kk == k])), 4) for k in kinds_en}
    mine_fp = int(sum(base.r0(q)[0] for _, kk, _, q in en if kk == "practice"))
    theirs = {k: e8["detected_by_rewrite"][k]["top_count"] for k in kinds_en}
    ok = mine == theirs and mine_fp == e8["practice_refused"]["top_count"]
    out["baseline_R0_equals_E8_at_60"] = ok
    print("baseline R0 = E8 at 60 items:", ok)

    # step 1: choose the share for text questions on the selection set
    reg = Registry(items, stems)
    kt = [q for q in qs if q[0] == "KT"]
    sweep = []
    for m in SWEEP_M:
        for th in SWEEP_TH:
            res = [(q, reg.r2(q[3], m, th)) for q in kt]
            sweep.append(dict(min_pieces=m, share=th,
                              rewritten_refused=round(float(np.mean([h[0] for q, h in res if q[1] not in NEG])), 4),
                              practice_refused=int(sum(h[0] for q, h in res if q[1] == "practice")),
                              stem_only_refused=int(sum(h[0] for q, h in res if q[1] == "stem_only"))))
    out["selection_sweep_KT"] = sweep
    th_t = min(x["share"] for x in sweep if x["min_pieces"] == M_MIN and x["practice_refused"] == 0 and x["stem_only_refused"] == 0)
    out["share_text_chosen"] = th_t
    out["selection_rule"] = "lowest share in the sweep with no practice problem and no stem refused on the selection set"
    print(f"share for text questions chosen on the selection set: {th_t}")
    _, _, _, _, _, rows_s, table_s = evaluate(SEED_SELECT, th_t)
    out["selection_set"] = table_s
    print(" selection set"); show(table_s)

    # step 2: fixed parameters on new items
    items, stems, qs, n_en, reg, rows, table = evaluate(SEED_VALIDATE, th_t)
    out["validation_set"] = table
    print(" validation set (new items, parameters fixed)"); show(table)
    print("   KT by rewrite (R2):", {k: v["R2"] for k, v in table["KT"]["refused_by_rewrite"].items()})
    print("   KT practice highest score", table["KT"]["practice_highest_score"]["R2"], "rewritten lowest", table["KT"]["rewritten_lowest_score_R2"])
    out["validation_refused_examples"] = {n: [dict(group=r["group"], kind=r["kind"], question=q[3], matched=items[r[n + "_item"]])
                                              for r, q in zip(rows, qs) if r["kind"] in ("practice", "stem_only") and r[n]][:10]
                                          for n in ("R1", "R2")}
    out["validation_not_refused_R2"] = [dict(group=r["group"], kind=r["kind"], question=q[3])
                                        for r, q in zip(rows, qs) if r["kind"] not in NEG and not r["R2"]]
    out["encrypted_check_R2"] = encrypted_check(items, stems, qs, reg, th_t)
    print("encrypted check:", out["encrypted_check_R2"])
    out["examples"] = dict(KN=items[60], KT=items[120])
    out["validation_rows"] = rows
    json.dump(out, open(out_path, "w"), indent=1, ensure_ascii=False)


if __name__ == "__main__":
    main()
