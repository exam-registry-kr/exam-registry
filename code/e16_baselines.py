"""E16: how does the registry's rule compare with simpler ways of recognising an exam item,
and what does it take to get around each of them?

Methods compared (all see the same items and the same questions)
  H    exact hash: SHA-256 of the text after NFKC, lower case, and removal of spaces and
       punctuation
  K    keyword list: per item, the words that occur in at most 5% of the registered items;
       score = share of that list found in the question
  V    vector similarity: TF-IDF over 4-character pieces, cosine (the matcher of E3)
  V+n  V, and for a question with a number other than 1 to 5 its numbers must all be in the item
  L    dense vectors: the TF-IDF vectors reduced to 64 dimensions (truncated SVD), cosine.
       This stands in for a sentence-embedding model. No neural embedding model could be
       installed in the environment this ran in, so a neural model is NOT measured here.
  R2   E9's rule            R3   the registry's rule (E14)
  R3w  candidate: R3 applied to every run of consecutive sentences (at most WINDOW sentences)
  R4   candidate: sentences that do not look like the best-matching item are dropped first
       (a sentence is kept if at least half of its pieces are in that item); the path is
       chosen by the item, not by the question; for an item with numbers the question's
       numbers must all be in the item OR the item's numbers must all be in the question
  R5   candidate, designed after R3w and R4 had been looked at on the selection set:
       everything R3 refuses, and in addition
       (a) a question with numbers whose best-matching item has no numbers is judged as text;
       (b) for an item with numbers the number test passes if the question's numbers are all
           in the item OR the item's numbers are all in the question;
       (c) coverage: sentences that do not look like the item are dropped (as in R4); if some
           run of the remaining sentences, no longer than SPAN x the item, contains at least
           a share C of the ITEM's pieces (and, for an item with numbers, all its numbers),
           the question is refused. C and SPAN are chosen on the selection set (no practice
           problem, stem or practice conversation refused; most must-refuse questions
           refused; ties: smallest SPAN, then the middle of the tied values of C).
           Every item of which the whole text contains at least the smallest C of the grid is
           tried. (A first version tried only the three best-matching items; E18 showed that
           an item hidden among practice problems was then missed, so this was changed and C
           and SPAN were chosen again on the selection set by the same rule. The other three
           sets had been looked at with the first version by then.)
The thresholds of K, V, V+n and L are chosen on the selection set only (fewest practice
problems and stems refused, then highest share of rewritten items refused; ties: lowest value).
R2, R3, R3w and R4 use the values fixed in E9 and E14. Only C and SPAN of R5 are chosen here.

Questions that must be refused (per registered item)
  E9's rewrites and E14's short copies, and new in this experiment:
  stray_number        the item, word for word, with "문제 23번 " / "Question 23: " in front
  padded_1x, _3x      the item with unrelated sentences in front (1x and 3x its words)
  sentence_interleave one unrelated sentence after every sentence of the item
  word_interleave_2   one filler word after every 2 words of the item
  reworded            every sentence rewritten by hand-written paraphrase templates; numbers,
                      names and subject terms are kept (what an AI paraphrase would keep)
  reworded_reordered  the same with the sentence order rotated
  translated          word problems only: the same problem in the other language
  paraphrase_request  "rewrite this problem in other words: " + the item (what a user would
                      have to send to an AI to obtain a paraphrase)
  padded_practice_16  the item, word for word, at a random place among 16 practice problems
                      of its own group (padding that looks like exam material)
Questions that must not be refused
  E9's practice problems and stems, E14's short parts of practice problems, and new:
  reworded_practice   practice problems rewritten with the same paraphrase templates
  conv_4, conv_16     4 and 16 practice problems of one group in one conversation, judged joined

Four item sets as in E14: selection, validation, fresh, confirm. Reported: confirm set.

    python e16_baselines.py          # about ten minutes
"""
import hashlib, json, math, re, sys, time
from collections import Counter
import numpy as np
from sklearn.decomposition import TruncatedSVD
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import normalize
import e3_registry as E3
import e9_korean_text_items as E9
import e14_sensitivity as E14
from e8_registry_scale import numbers_count

SETS = [("selection", E9.SEED_SELECT), ("validation", E9.SEED_VALIDATE), ("fresh", E14.SEED_FRESH), ("confirm", E14.SEED_CONFIRM)]
GRID = [round(0.05 * i, 2) for i in range(1, 20)] + [0.975, 0.99]
C_GRID = [0.6, 0.65, 0.7, 0.75, 0.8, 0.85, 0.9, 0.95]
SPANS = [1.5, 2.0, 3.0, 4.0]
WINDOW = 30
KEEP_SENT = 0.5
GROUPS = ("EN", "KN", "KT")
group = lambda i: GROUPS[i // 60]

# ------------------------------------------------------------------ paraphrase templates
EN_PARA = [
    "{a} starts with {x} {it}. After receiving {y} additional {it} from {b}, {a} hands out {z} of them. What is the count of {it} that {a} still holds?",
    "In {y} hours a train covers {x} km. Keeping that pace, what distance in km will it cover over {z} hours?",
    "Two numbers add up to {x}, and one exceeds the other by {y}. Determine the bigger of the two.",
    "The perimeter of a rectangle measures {x} cm, and it is {y} cm wide. Compute the area, in square centimeters.",
    "Let f(x) = {x}x^2 - {y}x + {z}. Evaluate f at 2.",
    "Each day for {y} days {a} puts aside {x} won, after which {z} won is spent. What amount remains?",
    "There are {x} red and {y} blue balls inside a bag. Drawing {z} of them with no replacement, find the chance every drawn ball is red.",
    "An arithmetic progression begins with {x} and increases by {y} each step. Determine term number {z}.",
    "Each of the {it} in a shop costs {x} won. {a} purchases {y} of them, handing over a {z} won note. What change comes back to {a}?",
    "A square sits inside a circle whose radius is {x} cm, touching it at all four corners. Express the area of that square using {y} and {z}.",
    "A geometric progression opens with {x} and multiplies by {y} each step. Compute the total of its first {z} terms.",
    "A class has {x} pupils. Math is liked by {y} of them and science by {z}, with nobody liking neither. Find how many pupils like the two subjects together.",
]
KN_PARA = [
    "{a}에게는 처음에 {it} {x}개가 있었다. {b}에게서 {it} {y}개를 추가로 받은 다음 {z}개를 남에게 건넸다. 지금 {a}에게 있는 {it}는 모두 몇 개일까?",
    "어떤 열차가 {x}km를 가는 데 {y}시간이 걸렸다. 빠르기가 변하지 않는다면 {z}시간에는 얼마나 멀리 갈까?",
    "어떤 두 수를 더하면 {x}, 빼면 {y}가 된다. 둘 가운데 더 큰 쪽은 얼마일까?",
    "가로가 {y}cm인 직사각형이 있고 네 변을 모두 더하면 {x}cm다. 이 도형의 면적을 제곱센티미터 단위로 답하여라.",
    "f(x) = {x}x^2 - {y}x + {z}일 때 x에 2를 넣은 값은 얼마일까?",
    "{a}는 하루에 {x}원을 {y}일간 모았고 그 뒤 {z}원을 지출했다. 지금 얼마가 남아 있을까?",
    "빨간색 공이 {x}개, 파란색 공이 {y}개 담긴 자루가 있다. 여기서 {z}개를 하나씩 뽑았더니 전부 빨간색일 가능성은 얼마일까?",
    "{x}에서 시작해 {y}씩 커지는 등차수열이 있다. {z}번째 항은 얼마일까?",
    "{it} 하나의 값이 {x}원인 상점이 있다. {a}는 {y}개를 고른 뒤 {z}원권 한 장으로 계산했다. 돌려받을 돈은 얼마일까?",
    "한 정사각형의 네 꼭짓점이 반지름 {x}cm짜리 원 위에 놓여 있다. 그 정사각형의 면적을 {y}, {z}를 써서 표현하여라.",
    "{x}에서 시작해 매번 {y}배가 되는 등비수열이 있다. 처음 {z}개 항을 모두 더한 값은 얼마일까?",
    "어떤 반의 인원은 {x}명이다. 수학을 선호하는 사람이 {y}명, 과학을 선호하는 사람이 {z}명이며 둘 다 싫어하는 사람은 없다. 수학과 과학을 다 선호하는 사람은 몇 명일까?",
]
STEM_PARA = [
    "아래 글이 말하려는 핵심을 가장 잘 정리한 선택지를 고르면?",
    "아래 글을 잘못 이해한 선택지를 고르면?",
    "아래 글에 나온 사실과 맞는 선택지를 고르면?",
    "아래 글로부터 미루어 알 수 있는 것을 고르면?",
    "아래 글이 다루는 주된 화제를 고르면?",
    "아래 자료를 바르게 풀이한 선택지를 고르면?",
    "아래 글에서 필자가 내세우는 견해를 고르면?",
    "아래 글에 비추어 <보기>를 잘못 해석한 선택지를 고르면?",
    "아래 자료를 바르게 분석한 선택지를 모두 모은 것을 고르면?",
    "아래 글이 쓰인 방식의 특색을 고르면?",
]
FRAME_PARA = [
    "지금까지 학계는 {A} 쪽에 초점을 맞추어 {T} 현상을 풀이해 왔다.",
    "하지만 요즘 나온 논문들은 {B} 쪽이 맡는 몫을 더 크게 본다.",
    "{T} 현상이 진행될 때 가장 먼저 달라지는 것은 {A} 쪽이다.",
    "그렇게 달라진 결과가 {B} 쪽으로 번져 이전과 다른 안정 상태가 생긴다.",
    "그러므로 {A} 쪽과 {B} 쪽이 서로 어떻게 얽히는지 같이 보아야 {T} 현상을 제대로 알 수 있다.",
    "몇몇 연구자는 {A} 쪽의 비중을 지나치게 크게 잡았다고 판단한다.",
    "{B} 쪽에서 바라볼 경우 {T} 현상이 뜻하는 바가 바뀐다.",
    "그 무렵의 삶은 {A} 쪽에 크게 기대고 있었다.",
    "이 무렵 {B} 쪽을 향한 흥미가 눈에 띄게 커졌다.",
    "요컨대 {T} 현상의 알맹이는 {A} 쪽에 놓여 있다.",
    "{B} 쪽을 어떻게 보느냐에 맞추어 {T} 현상을 두고 내리는 판단이 갈린다.",
    "가령 {A} 쪽에서 실제로 있었던 일이 이를 뚜렷이 드러낸다.",
    "{A} 쪽이 흔들리면 {T} 현상이 펼쳐지는 모습 역시 달라진다.",
    "처음 단계에서는 {B} 쪽이 끼친 힘이 눈에 잘 띄지 않았다.",
    "{T} 현상이 퍼져 나가면서 {A} 쪽에 분명한 자국이 생겼다.",
    "그와 반대로 {B} 쪽을 바탕에 둔 풀이는 부족한 점을 드러낸다.",
    "요즘은 {A} 쪽을 다룬 데이터가 계속 쌓이는 중이다.",
    "{T} 현상의 뒤편에는 긴 세월 쌓여 온 {B} 쪽의 골칫거리가 놓여 있었다.",
    "그런데 {A} 쪽을 묶어 두려던 조치는 기대와 어긋난 결말로 이어졌다.",
    "{B} 쪽에서 보는 눈은 {T} 현상을 둘러싼 흔한 믿음을 뒤엎는다.",
    "이렇게 진행되는 동안 {A} 쪽과 {B} 쪽을 가르는 선이 조금씩 희미해진다.",
    "그리하여 {T} 현상이 진행되는 빠르기는 곳에 따라 서로 달랐다.",
    "{A} 쪽을 눈여겨본 학자들은 긴 흐름의 방향을 무겁게 여긴다.",
    "이에 비해 {B} 쪽이 내는 결과는 잠깐 동안만 확인된다.",
    "{T} 현상을 적은 문헌은 거의 다 {A} 쪽의 꼴로 남아 있다.",
    "그러니 {B} 쪽이 가리키는 뜻을 새로 정해야 한다는 말이다.",
    "실제 사례에서도 {A} 쪽이 높은 수준일수록 {T} 현상이 미치는 힘이 세진다.",
    "그렇지만 {B} 쪽을 두고는 여태 의견이 하나로 모이지 않았다.",
    "{T} 현상에서 나온 실례가 {A} 쪽을 둘러싼 다툼에 다시 불을 붙였다.",
    "이같이 {B} 쪽의 여건이 마련되는 순간 달라지기 시작한다.",
]
CHOICE_PARA = [
    "{T} 현상을 일으킨 것은 {A} 쪽이 달라졌기 때문이다.",
    "{B} 쪽을 어떻게 보느냐가 {T} 현상의 뜻을 바꾼다.",
    "{B} 쪽이 맡는 몫이 {A} 쪽보다 크다.",
    "지금까지 {T} 현상을 풀이해 온 방식은 고칠 까닭이 없다.",
    "{B} 쪽을 향한 흥미는 차츰 식어 갔다.",
    "{T} 현상에는 {A} 쪽에서 있었던 일을 끌어다 쓸 수 없다.",
    "{T} 현상이 진행되는 동안 {B} 쪽은 그대로 유지된다.",
    "{A} 쪽과 {B} 쪽이 얽힌 방식은 {T} 현상과 무관하다.",
    "{A} 쪽 때문에 {T} 현상이 퍼지는 일이 더뎌졌다.",
    "{B} 쪽을 바탕에 둔 풀이가 가장 많은 지지를 얻는다.",
]
FILL = dict(
    KO=["오늘은 날씨가 맑아서 강가를 따라 오래 걸었다.", "저녁에는 동생과 함께 시장에 들러 반찬거리를 샀다.", "주말에는 미뤄 둔 방 정리를 끝낼 생각이다.",
        "어제 본 영화는 생각보다 길었지만 끝까지 재미있었다.", "버스가 늦게 와서 약속 장소에 조금 늦게 도착했다.", "새로 산 운동화가 발에 잘 맞아서 마음에 든다.",
        "친구가 추천해 준 식당은 줄이 길어서 다음에 가기로 했다.", "창가에 둔 화분에 물을 주는 것을 자꾸 잊어버린다.", "요즘은 아침마다 따뜻한 차를 한 잔 마시고 하루를 시작한다.",
        "이번 여름에는 바닷가 마을에서 며칠 쉬다 오고 싶다.", "책상 서랍을 열어 보니 오래된 편지가 여러 장 나왔다.", "동네 도서관은 저녁 늦게까지 문을 열어서 자주 들른다.",
        "강아지가 산책을 나가자고 현관 앞에서 꼬리를 흔들었다.", "휴대폰 배터리가 금방 닳아서 충전기를 늘 들고 다닌다.", "할머니 댁 마당에는 감나무가 한 그루 서 있다.",
        "점심으로 먹은 국수가 맛있어서 다음 주에 또 가려고 한다."],
    EN=["The weather was clear this morning, so I walked along the river for a long while.", "My sister and I stopped by the market in the evening to pick up vegetables.",
        "I plan to finish tidying my room over the weekend.", "The movie we watched yesterday was longer than expected but fun until the end.",
        "The bus came late, so I arrived at the cafe a little behind schedule.", "My new sneakers fit well and I am happy with them.",
        "The restaurant my friend suggested had a long line, so we will try again later.", "I keep forgetting to water the plant on the windowsill.",
        "These days I begin every morning with a warm cup of tea.", "This summer I would like to rest in a seaside village for a while.",
        "I opened my desk drawer and found a stack of old letters.", "The neighborhood library stays open late, so I visit often.",
        "The dog waited by the front door, wagging its tail for a walk.", "My phone battery drains quickly, so I always carry a charger.",
        "There is a persimmon tree standing in my grandmother's yard.", "The noodles I had for lunch were tasty, so I will go back soon."])
FILL_WORDS = dict(KO=["그리고", "음", "아무튼", "참고로", "그러니까", "말하자면"], EN=["well", "anyway", "basically", "like", "so", "okay"])
REQUEST = dict(KO="다음 문제를 같은 뜻의 다른 문장으로 바꿔 써 줘. ", EN="Rewrite the following problem in different words, keeping its meaning. ")


def tpl_regex(tpl, alts):
    seen, out = set(), []
    for part in re.split(r"(\{\w+\})", tpl):
        if re.fullmatch(r"\{\w+\}", part):
            v = part[1:-1]
            out.append(f"(?P={v})" if v in seen else f"(?P<{v}>{alts[v]})")
            seen.add(v)
        else:
            out.append(re.escape(part))
    return re.compile("".join(out))


alt = lambda xs: "|".join(sorted(map(re.escape, xs), key=len, reverse=True))
NUM = r"\d+"
EN_RX = [tpl_regex(t, dict(a=alt(E3.NAMES), b=alt(E3.NAMES), it=alt(E3.ITEMS), x=NUM, y=NUM, z=NUM)) for t in E3.TEMPLATES]
KN_RX = [tpl_regex(t, dict(a=alt(E9.NAMES), b=alt(E9.NAMES), it=alt(E9.THINGS), x=NUM, y=NUM, z=NUM)) for t in E9.KN_TEMPLATES]
TAB = dict(T=alt(E9.TOPICS), A=alt(E9.NOUNS), B=alt(E9.NOUNS))
FRAME_RX = [tpl_regex(t, TAB) for t in E9.FRAMES]
CHOICE_RX = [tpl_regex(t, TAB) for t in E9.CHOICES]


def parse(rxs, text):
    for i, rx in enumerate(rxs):
        m = rx.fullmatch(text)
        if m:
            return i, m.groupdict()
    raise ValueError("no template matches: " + text)


def reword(text, g, reorder=False):
    """Every sentence replaced by its hand-written paraphrase. Numbers, names and subject terms stay."""
    if g in ("EN", "KN"):
        i, d = parse(EN_RX if g == "EN" else KN_RX, text)
        out = (EN_PARA if g == "EN" else KN_PARA)[i].format(**{"a": "", "b": "", "it": "", **d})
        s = E9.split_sents(out)
        return " ".join(s[1:] + s[:1]) if reorder and len(s) > 1 else out
    head, *ch = re.split("[" + E9.MARKS + "]", text)
    sents = E9.split_sents(head.strip())
    stem = STEM_PARA[E9.STEMS.index(sents[0])]
    body = []
    for s in sents[1:]:
        i, d = parse(FRAME_RX, s)
        body.append(FRAME_PARA[i].format(**d))
    if reorder:
        body = body[1:] + body[:1]
    choices = []
    for j, c in enumerate(ch):
        i, d = parse(CHOICE_RX, c.strip())
        choices.append(f"{E9.MARKS[j]} {CHOICE_PARA[i].format(**d)}")
    return " ".join([stem] + body + choices)


def translate(text, g):
    i, d = parse(EN_RX if g == "EN" else KN_RX, text)
    src_n, dst_n = (E3.NAMES, E9.NAMES) if g == "EN" else (E9.NAMES, E3.NAMES)
    src_t, dst_t = (E3.ITEMS, E9.THINGS) if g == "EN" else (E9.THINGS, E3.ITEMS)
    d = dict(d)
    for k in ("a", "b"):
        if k in d:
            d[k] = dst_n[src_n.index(d[k])]
    if "it" in d:
        d["it"] = dst_t[src_t.index(d["it"])]
    return (E9.KN_TEMPLATES if g == "EN" else E3.TEMPLATES)[i].format(**{"a": "", "b": "", "it": "", **d})


def filler(lang, n_words, r):
    out, n = [], 0
    while n < n_words:
        s = FILL[lang][int(r.integers(0, len(FILL[lang])))]
        out.append(s); n += len(s.split())
    return " ".join(out)


def new_attacks(t, g, r):
    lang = "EN" if g == "EN" else "KO"
    n = int(r.integers(6, 46))
    w, s = t.split(), E9.split_sents(t)
    fw = FILL_WORDS[lang]
    out = {
        "stray_number": (f"Question {n}: " if lang == "EN" else f"문제 {n}번 ") + t,
        "padded_1x": filler(lang, len(w), r) + " " + t,
        "padded_3x": filler(lang, 3 * len(w), r) + " " + t,
        "sentence_interleave": " ".join(x + " " + FILL[lang][int(r.integers(0, 16))] for x in s),
        "word_interleave_2": " ".join(x + (" " + fw[int(r.integers(0, 6))] if j % 2 == 1 else "") for j, x in enumerate(w)),
        "reworded": reword(t, g),
        "reworded_reordered": reword(t, g, True),
        "paraphrase_request": REQUEST[lang] + t,
    }
    if g != "KT":
        out["translated"] = translate(t, g)
    return out


NEW_KINDS = ["stray_number", "padded_1x", "padded_3x", "sentence_interleave", "word_interleave_2", "reworded", "reworded_reordered",
             "translated", "paraphrase_request", "padded_practice_16"]
NEG = E14.NEG + ("reworded_practice",)


def build(seed):
    items, stems, qs, _ = E9.build(seed)
    qs = E14.add_short(items, qs, seed)
    r = np.random.default_rng(seed + 16)
    extra = []
    for i, t in enumerate(items):
        extra += [(group(i), k, i, v) for k, v in new_attacks(t, group(i), r).items()]
    extra += [(g, "reworded_practice", -1, reword(q, g)) for g, k, _, q in qs if k == "practice"]
    practice = {g: [q[3] for q in qs if q[0] == g and q[1] == "practice"] for g in GROUPS}
    for i, t in enumerate(items):
        pad = [practice[group(i)][int(j)] for j in r.choice(240, 16, replace=False)]
        pad.insert(int(r.integers(0, 17)), t)
        extra.append((group(i), "padded_practice_16", i, " ".join(pad)))
    convs = []
    for n, count in ((4, 200), (16, 100)):
        for _ in range(count):
            g = GROUPS[int(r.integers(0, 3))]
            convs.append((g, f"conv_{n}", -1, " ".join(practice[g][int(j)] for j in r.choice(240, n, replace=False))))
    return items, stems, qs + extra, convs


# ------------------------------------------------------------------ the rules
def strip(t):
    return re.sub(r"[\s\.,?!·~\"'()]", "", E9.nk(t).lower().replace(",", ""))


def sentences(q):
    return [s for s in re.split(r"(?<=[.?!])\s+|\n+", q) if s.strip()]


class Rules:
    """R3w and R4 on top of E9's registry."""

    def __init__(self, items, stems):
        self.reg = E9.Registry(items, stems)
        self.strong = [E9.strong_number(t) for t in items]
        self.size = [len(g - self.reg.stem) for g in self.reg.g]
        self.floor = [min(E9.R3_VALUES["cap"], math.ceil(E9.R3_VALUES["frac"] * s)) for s in self.size]

    def r3w(self, q):
        """R3 on every run of at most WINDOW consecutive sentences. Pieces are those of the run as one text."""
        reg, sents = self.reg, sentences(q)
        if len(sents) <= 1:
            return reg.r3(q)[:2]
        flat = [strip(s) for s in sents]
        for a in range(len(sents)):
            seen, cnt, text, tail = set(), Counter(), [], ""
            for b in range(a, min(len(sents), a + WINDOW)):
                cur = tail + flat[b]
                for j in range(max(0, len(cur) - 3)):
                    x = cur[j:j + 4]
                    if x not in seen:
                        seen.add(x)
                        if x not in reg.stem:
                            for i in reg.inv.get(x, ()):
                                cnt[i] += 1
                tail = cur[-3:]
                text.append(sents[b])
                joined = " ".join(text)
                if E9.strong_number(joined):
                    pool, th, floor_on = seen, E9.TH, False
                    # numbers path counts every piece, as E9 does
                    c2 = Counter()
                    for x in seen:
                        for i in reg.inv.get(x, ()):
                            c2[i] += 1
                    use = c2
                else:
                    pool, th, floor_on, use = seen - reg.stem, E9.R3_VALUES["share"], True, cnt
                if not use:
                    continue
                v = max(use.values()); i = min(k for k, n in use.items() if n == v)
                if v / max(1, len(pool)) < th:
                    continue
                if floor_on:
                    if v >= self.floor[i]:
                        return True, i
                elif numbers_count(E9.nk(joined)) <= reg.n[i]:
                    return True, i
        return False, -1

    def r4(self, q):
        reg = self.reg
        rest = E9.pieces(E9.nk(q))[0] - reg.stem
        i, v = reg._top(reg.inv, rest)
        if i < 0:
            return False, -1
        kept = []
        for s in sentences(q):
            p = E9.pieces(E9.nk(s))[0] - reg.stem
            if p and len(p & reg.g[i]) / len(p) >= KEEP_SENT:
                kept.append(s)
        k = " ".join(kept)
        p = E9.pieces(E9.nk(k))[0] - reg.stem
        v = len(p & reg.g[i]); share = v / max(1, len(p))
        if self.strong[i]:
            qn = numbers_count(E9.nk(k))
            return bool(share >= E9.TH and len(qn) > 0 and (qn <= reg.n[i] or reg.n[i] <= qn)), i
        return bool(v >= self.floor[i] and share >= E9.R3_VALUES["share"]), i


    def r5_base(self, q):
        """R3 with (a) and (b). Refuses everything R3 refuses."""
        reg = self.reg
        if not E9.strong_number(q):
            return reg.r3(q)[:2]
        qg, qn = E9.pieces(E9.nk(q))[0], numbers_count(E9.nk(q))
        i, v = reg._top(reg.inv, qg)
        if i >= 0 and self.strong[i]:
            return bool(v / max(1, len(qg)) >= E9.TH and (qn <= reg.n[i] or reg.n[i] <= qn)), i
        rest = qg - reg.stem
        i, v = reg._top(reg.inv, rest)
        return bool(i >= 0 and v >= self.floor[i] and v / max(1, len(rest)) >= E9.R3_VALUES["share"]), i

    def coverage(self, q):
        """For each SPAN: the highest share of an item's pieces found in a run of kept sentences
        no longer than SPAN x the item (for an item with numbers: runs that contain all its numbers)."""
        reg = self.reg
        rest = E9.pieces(E9.nk(q))[0] - reg.stem
        c = Counter()
        for x in rest:
            for i in reg.inv.get(x, ()):
                c[i] += 1
        best = {sp: (0.0, -1) for sp in SPANS}
        sents = sentences(q)
        ps = [E9.pieces(E9.nk(s))[0] - reg.stem for s in sents]
        # a run cannot contain more of an item than the whole text does, so only these items can pass
        for i in sorted(i for i, n in c.items() if n >= C_GRID[0] * self.size[i]):
            keep = [j for j, p in enumerate(ps) if p and len(p & reg.g[i]) / len(p) >= KEEP_SENT]
            for sp in SPANS:
                limit = sp * self.size[i]
                for a in range(len(keep)):
                    b, total = a, len(ps[keep[a]])
                    while b + 1 < len(keep) and total + len(ps[keep[b + 1]]) <= limit:
                        b += 1; total += len(ps[keep[b]])
                    if a > 0 and b == len(keep) - 1 and len(ps[keep[a - 1]]) + total <= limit:
                        continue                      # contained in the previous run
                    text = " ".join(sents[j] for j in keep[a:b + 1])
                    if self.strong[i] and not reg.n[i] <= numbers_count(E9.nk(text)):
                        continue
                    cov = len((E9.pieces(E9.nk(text))[0] - reg.stem) & reg.g[i]) / max(1, self.size[i])
                    if cov > best[sp][0]:
                        best[sp] = (cov, i)
        return best


class Baselines:
    def __init__(self, items):
        self.items = items
        self.hash = {hashlib.sha256(strip(t).encode()).hexdigest(): i for i, t in enumerate(items)}
        toks = [set(self.tokens(t)) for t in items]
        df = Counter(x for s in toks for x in s)
        self.kw = [{x for x in s if df[x] <= 0.05 * len(items)} for s in toks]
        self.kw_exposed = float(np.mean([len(k) / max(1, len(s)) for k, s in zip(self.kw, toks)]))
        self.vec = TfidfVectorizer(analyzer="char", ngram_range=(4, 4), lowercase=True, preprocessor=E9.nk).fit(items)
        self.M = self.vec.transform(items)
        self.svd = TruncatedSVD(n_components=64, random_state=0).fit(self.M)
        self.D = normalize(self.svd.transform(self.M))
        self.nums = [numbers_count(E9.nk(t)) for t in items]

    @staticmethod
    def tokens(t):
        return re.findall(r"\d+(?:\.\d+)?|[a-z]+|[가-힣]+", E9.nk(t).lower().replace(",", ""))

    def score(self, qs):
        texts = [q[3] for q in qs]
        X = self.vec.transform(texts)
        S = (X @ self.M.T).toarray()
        L = normalize(self.svd.transform(X)) @ self.D.T
        out = []
        for j, t in enumerate(texts):
            h = self.hash.get(hashlib.sha256(strip(t).encode()).hexdigest(), -1)
            tk = set(self.tokens(t))
            ks = [len(k & tk) / len(k) if len(k) >= 2 else 0.0 for k in self.kw]
            ki = int(np.argmax(ks)); vi = int(np.argmax(S[j])); li = int(np.argmax(L[j]))
            strong = E9.strong_number(t)
            out.append(dict(H=(1.0 if h >= 0 else 0.0, h), K=(ks[ki], ki), V=(float(S[j, vi]), vi), L=(float(L[j, li]), li),
                            num_ok=(not strong) or numbers_count(E9.nk(t)) <= self.nums[vi]))
        return out


def base_hit(s, m, th):
    if m == "H":
        return s["H"][0] >= 1.0, s["H"][1]
    if m == "V+n":
        return s["V"][0] >= th and s["num_ok"], s["V"][1]
    return s[m][0] >= th, s[m][1]


def evaluate(seed):
    items, stems, qs, convs = build(seed)
    R, B = Rules(items, stems), Baselines(items)
    allq = qs + convs
    sc = B.score(allq)
    ours = []
    for g, k, qi, q in allq:
        d = dict(R2=R.reg.r2(q, E9.M_MIN, E14.E9_SHARE)[:2], R3=R.reg.r3(q)[:2], R3w=R.r3w(q), R4=R.r4(q),
                 base=R.r5_base(q), cov=R.coverage(q))
        assert d["base"][0] or not d["R3"][0], "R5 must refuse everything R3 refuses"
        ours.append(d)
    return items, allq, sc, ours, B, R


def choose(allq, sc):
    """Threshold per baseline on the selection set."""
    out = {}
    for m in ("K", "V", "V+n", "L"):
        best = None
        for th in GRID:
            fr = sum(base_hit(s, m, th)[0] for q, s in zip(allq, sc) if q[1] in ("practice", "stem_only"))
            det = float(np.mean([(lambda h: h[0] and h[1] == q[2])(base_hit(s, m, th)) for q, s in zip(allq, sc)
                                 if q[1] not in NEG and q[1] not in NEW_KINDS and not q[1].startswith("conv_")]))
            if best is None or (fr, -det) < (best[2], -best[1]):
                best = (th, det, fr)
        out[m] = best[0]
    return out


def r5_hit(o, c, span):
    if o["base"][0]:
        return o["base"]
    cov, i = o["cov"][span]
    return (cov >= c, i) if i >= 0 else (False, -1)


def choose_r5(allq, ours):
    grid = []
    for span in SPANS:
        for c in C_GRID:
            false = sum(r5_hit(o, c, span)[0] for q, o in zip(allq, ours) if q[1] in ("practice", "stem_only") or q[1].startswith("conv_"))
            det = float(np.mean([(lambda h: h[0] and h[1] == q[2])(r5_hit(o, c, span)) for q, o in zip(allq, ours)
                                 if q[1] not in NEG and not q[1].startswith("conv_")]))
            sp = sum(r5_hit(o, c, span)[0] for q, o in zip(allq, ours) if q[1] == "short_practice")
            grid.append(dict(span=span, C=c, false_refusals=int(false), short_practice_refused=int(sp), refused=round(det, 4)))
    ok = [g for g in grid if g["false_refusals"] == 0]
    top = max(g["refused"] for g in ok)
    tied = sorted([g for g in ok if g["refused"] == top], key=lambda g: (g["span"], g["C"]))
    tied = [g for g in tied if g["span"] == tied[0]["span"]]
    return tied[len(tied) // 2], grid


METHODS = ["H", "K", "V", "V+n", "L", "R2", "R3", "R3w", "R4", "R5"]


def table(allq, sc, ours, th):
    def hit(j, m):
        if m == "R5":
            return r5_hit(ours[j], th["R5"]["C"], th["R5"]["span"])
        return base_hit(sc[j], m, th.get(m)) if m in ("H", "K", "V", "V+n", "L") else ours[j][m]
    out = dict(refused={}, not_to_refuse={})
    kinds = list(dict.fromkeys(q[1] for q in allq))
    for k in kinds:
        idx = [j for j, q in enumerate(allq) if q[1] == k]
        neg = k in NEG or k.startswith("conv_")
        d = {}
        for g in GROUPS + ("all",):
            sel = [j for j in idx if g == "all" or allq[j][0] == g]
            if not sel:
                continue
            if neg:
                d[g] = {m: int(sum(bool(hit(j, m)[0]) for j in sel)) for m in METHODS} | {"of": len(sel)}
            else:
                d[g] = {m: round(float(np.mean([bool(hit(j, m)[0]) and hit(j, m)[1] == allq[j][2] for j in sel])), 4) for m in METHODS} | {"of": len(sel)}
        out["not_to_refuse" if neg else "refused"][k] = d
    old = [j for j, q in enumerate(allq) if q[1] not in NEG and q[1] not in NEW_KINDS and not q[1].startswith("conv_")]
    out["summary"] = {
        "rewrites_of_E9_and_short_copies": {m: round(float(np.mean([bool(hit(j, m)[0]) and hit(j, m)[1] == allq[j][2] for j in old])), 4) for m in METHODS},
        "practice_and_stems_refused": {m: int(sum(bool(hit(j, m)[0]) for j, q in enumerate(allq) if q[1] in ("practice", "stem_only"))) for m in METHODS},
        "of_practice_and_stems": sum(q[1] in ("practice", "stem_only") for q in allq)}
    return out


def effort(items, allq):
    """What each way around costs the person asking, and what is left of the item for any content rule."""
    out = {}
    for k in NEW_KINDS:
        add, kept = [], []
        for g, kk, qi, q in allq:
            if kk != k:
                continue
            a, b = strip(items[qi]), strip(q)
            pa, pb = E9.pieces(E9.nk(items[qi]))[0], E9.pieces(E9.nk(q))[0]
            add.append(max(0, len(b) - len(a)) / len(a)); kept.append(len(pa & pb) / len(pa))
        out[k] = dict(characters_added_per_item_character=round(float(np.mean(add)), 3),
                      share_of_item_pieces_still_in_question=round(float(np.mean(kept)), 3))
    return out


def main():
    out_path = sys.argv[1] if len(sys.argv) > 1 else "E16-001_results.json"
    t0 = time.time()
    out = dict(experiment="E16-001", seeds={n: s for n, s in SETS}, grid=GRID, window_sentences=WINDOW, keep_sentence_share=KEEP_SENT,
               note_dense_vectors="L is a 64-dimension truncated SVD of TF-IDF vectors, not a neural sentence-embedding model; no neural model was measured",
               fixed_values=dict(R2=dict(min_pieces=E9.M_MIN, share=E14.E9_SHARE), R3=E9.R3_VALUES, numeric_share=E9.TH), sets={})
    th = None
    for name, seed in SETS:
        items, allq, sc, ours, B, R = evaluate(seed)
        if name == "selection":
            th = choose(allq, sc)
            th["R5"], out["selection_grid_R5"] = choose_r5(allq, ours)
            out["thresholds_chosen_on_selection"] = th
            print("thresholds chosen on the selection set:", th)
        out["sets"][name] = table(allq, sc, ours, th)
        if name == "confirm":
            out["effort_confirm"] = effort(items, allq)
            out["exposure_before_exam_confirm"] = dict(
                H="a list of hashes; anyone holding it can test a guessed text without asking the authority",
                K=dict(share_of_item_words_published_in_clear=round(B.kw_exposed, 4)),
                V_L=dict(share_of_item_4char_pieces_in_published_vocabulary=round(float(np.mean(
                    [np.mean([x in B.vec.vocabulary_ for x in set(B.vec.build_analyzer()(t))]) for t in items])), 4),
                    note="a service that computes query vectors needs the vocabulary in clear; pieces as the vectorizer cuts them"),
                registry="ciphertext until the exam starts (E11); afterwards each guess needs an evaluation by the authority")
            out["examples_confirm"] = {k: next(q[3] for q in allq if q[1] == k and q[0] == g) for k in NEW_KINDS for g in ("KT",) if k != "translated"} | \
                {"translated_KN": next(q[3] for q in allq if q[1] == "translated" and q[0] == "KN"), "item_KT": items[120], "item_KN": items[60]}
        s = out["sets"][name]["summary"]
        print(f"{name} ({time.time() - t0:.0f}s)  rewrites+short copies:", s["rewrites_of_E9_and_short_copies"])
        print("   practice and stems refused:", s["practice_and_stems_refused"], "of", s["of_practice_and_stems"])
        for k in NEW_KINDS:
            print(f"   {k:20s}", {m: out['sets'][name]['refused'][k]['all'][m] for m in METHODS})
        for k in ("short_practice", "reworded_practice", "same_passage_other_question", "conv_4", "conv_16"):
            d = out["sets"][name]["not_to_refuse"][k]["all"]
            print(f"   not to refuse {k:28s}", {m: d[m] for m in METHODS}, "of", d["of"])
    json.dump(out, open(out_path, "w"), indent=1, ensure_ascii=False)


if __name__ == "__main__":
    main()
