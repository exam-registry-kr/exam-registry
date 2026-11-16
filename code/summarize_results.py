"""Print every number quoted in the documents, read directly from results/.

    python summarize_results.py           # Korean
    python summarize_results.py --en      # English

Takes a few seconds and needs only the Python standard library.
"""
import json, os, sys

EN = "--en" in sys.argv
R = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "results")
load = lambda f: json.load(open(os.path.join(R, f), encoding="utf-8"))


def say(ko, en):
    print(en if EN else ko)


def yes(b):
    return ("yes" if b else "no") if EN else ("예" if b else "아니오")


say("1. 표식 판독 (E1-005, E1-006)", "1. Marker decoding (E1-005, E1-006)")
e1 = load("E1-005_results_v2_merged.json")
mix = [json.loads(l)["result"] for l in open(os.path.join(R, "E1-006_mixed_trials_v2_2seeds.jsonl"))]
rows = [r for f in e1["sweeps"].values() for p in f for r in p["rows"]] + [r for c in e1["grid"] for r in c["rows"]] + mix
wrong, fp0 = sum(r["M2final"] == -1 for r in rows), sum(r["M0_fp"] for r in rows)
say(f"   판독 시행 {len(rows):,}회, 다른 시험 번호로 잘못 판독 {wrong}건, 표식 없는 페이지 오인 {fp0}건",
    f"   {len(rows):,} decoding trials, {wrong} read as a wrong exam ID, {fp0} unmarked pages taken as marked")
for p in e1["sweeps"]["view"]:
    say(f"   시험지 높이 {p['value']:.0%} 촬영: 노란 표식 {p['M2final']['correct']:.1%}, 모서리 코드 1개 {p['M1']['correct']:.1%} (n={p['n']})",
        f"   photo of {p['value']:.0%} of the page height: yellow marker {p['M2final']['correct']:.1%}, single corner code {p['M1']['correct']:.1%} (n={p['n']})")

say("2. 서명된 시간 창에 따른 거절 (E2-001)", "2. Refusal by signed time window (E2-001)")
e2 = load("E2-001_results.json")
say(f"   등록 검증: {e2['protocol']}", f"   registration checks: {e2['protocol']}")
say(f"   표식 있는 시험지: {e2['marked_page']}", f"   marked exam page: {e2['marked_page']}")
b = e2["benign_in_window"]
n_b, r_b = sum(v["n"] for v in b.values()), sum(v["refused"] for v in b.values())
say(f"   일반 페이지 {n_b}장 중 거절 {r_b}건", f"   ordinary pages: {r_b} of {n_b} refused")

say("3. 문항 조각 대조와 숫자 검사 (E3-001, 일치 기준 0.5)", "3. Piece matching with number check (E3-001, threshold 0.5)")
e3 = load("E3-001_results.json")["thresholds"]["0.5"]
for k, v in e3.items():
    say(f"   {k:42s} 조각+숫자 {v['ngram_num']:.1%}", f"   {k:42s} pieces+numbers {v['ngram_num']:.1%}")

say("4. 문장은 읽히나 표식은 판독되지 않는 사진 (E5-001)", "4. Photos whose text is readable but whose marker is not (E5-001)")
e5 = load("E5-001_rows.json")
gap = lambda r, k: (r["readable"] or r["numbers_ok"]) and not r[k]
for k, ko, en in (("marker", "완전 판독만", "full decoding only"), ("marker_partial", "4조각 부분 판독", "partial decoding (4 chunks)"),
                  ("marker_enh", "부분 판독 + 확대·선명화 (최종)", "partial + upscale and sharpen (final)")):
    say(f"   {ko}: {sum(gap(r, k) for r in e5)}/{len(e5)}장", f"   {en}: {sum(gap(r, k) for r in e5)}/{len(e5)} photos")
fails = [r for r in e5 if not r["marker_enh"]]
mx, mc = max(r["em_px"] for r in fails), min(r["cer"] for r in fails)
say(f"   최종 판독기가 실패한 사진의 최대 글자 크기 {mx:.1f}픽셀, 최소 글자 인식 오류율 {mc:.0%}",
    f"   photos where the final decoder failed: largest text {mx:.1f} px, lowest character error rate {mc:.0%}")
fp = load("E5-002_false_positives.json")["decoder_final_enhanced"]
m_fp, c_fp = sum(v["matches"] for v in fp.values()), sum(v["captures"] for v in fp.values())
say(f"   최종 판독기의 일반 문서 오인 {m_fp}/{c_fp}", f"   final decoder on ordinary documents: {m_fp}/{c_fp} false matches")
e53 = load("E5-003_scored.json")
say(f"   상용 AI 판독 시험(E5-003): 사진 {e53['n_photos']}장 중 AI가 푼 사진 {e53['solved']}장, 그중 표식 판독 {e53['solved_with_marker']}장,"
    f" 표식 미판독인데 AI가 푼 사진 {len(e53['gaps'])}장",
    f"   commercial AI test (E5-003): of {e53['n_photos']} photos the AI solved {e53['solved']}, marker readable in {e53['solved_with_marker']} of them,"
    f" solved without a readable marker: {len(e53['gaps'])}")

say("5. 실제 시험지 적용 (E6-001, 조건당 10회, 최종 판독기)", "5. Real exam page (E6-001, 10 captures per condition, final decoder)")
e6 = load("E6-001_realpage_decode.json")["results"]
for ink in ("0.7", "0.5", "0.35", "0.2", "0.12"):
    cells = ", ".join(f"{k.split('_', 1)[1]}={v['final']}/{v['n']}" for k, v in e6.items() if k.startswith(f"ink{ink}_"))
    say(f"   인쇄 농도 {float(ink):.0%}: {cells}", f"   ink {float(ink):.0%}: {cells}")

say("6. 암호화된 문항 내용 조회 (E7-001, 일치 기준 0.5)", "6. Encrypted content lookup (E7-001, threshold 0.5)")
e7 = load("E7-001_results.json")
d = e7["identical_decisions"]
say(f"   암호화 조회와 일반 대조의 판정 일치 {d['count']}/{d['total']}건", f"   same decision as plaintext matching: {d['count']}/{d['total']}")
for k, v in e7["detection_and_false_match"].items():
    ko = "같은 유형 연습문제 오인" if k == "practice" else f"바꿔 쓴 질문({k}) 탐지"
    en = "practice problems of the same type refused" if k == "practice" else f"rewritten questions ({k}) detected"
    say(f"   {ko}: 일반 대조 {v['plain']:.1%}, 암호화 조회 {v['oprf']:.1%}, E3 방식 {v['e3']:.1%}",
        f"   {en}: plaintext {v['plain']:.1%}, encrypted {v['oprf']:.1%}, E3 method {v['e3']:.1%}")
t = e7["timing"]
say(f"   질문 1건당 조각 {t['pieces_per_query_median']:.0f}개(중앙값), AI 서비스 측 총 {t['client_total_ms_median']}ms,"
    f" 시험 기관 서버 {t['authority_ms_per_query_median']}ms, 조각당 전송 {t['bytes_per_piece_each_way']}바이트(각 방향)",
    f"   per question: {t['pieces_per_query_median']:.0f} pieces (median), service total {t['client_total_ms_median']} ms,"
    f" authority {t['authority_ms_per_query_median']} ms, {t['bytes_per_piece_each_way']} bytes per piece each way")
say("   (이 저장소의 RFC 9497 구현 기준. 타원곡선 곱셈 외에는 Python이며 측정 환경에 따라 달라짐)",
    "   (this repository's RFC 9497 implementation; Python except the elliptic-curve multiplication; timings depend on the machine)")

say("7. 등록 문항 수를 늘렸을 때 (E8-001, 모든 문항이 같은 12개 유형인 가장 불리한 조건)",
    "7. Growing the registry (E8-001, worst case: every item from the same 12 templates)")
e8 = load("E8-001_results.json")
b = e8["by_size"][str(e8["sizes"][0])]["baseline_top_set_matches_E7_plain"]
say(f"   기준선: 등록 {e8['sizes'][0]}개에서 E7 일반 대조와 같은 판정 {b['count']}/{b['total']}건",
    f"   baseline: with {e8['sizes'][0]} items, same decision as E7 plaintext on {b['count']}/{b['total']}")
names = {"top_set": ("E7 규칙(숫자 한 번씩)", "E7 rule (each number once)"),
         "top_count": ("보완 규칙(반복 숫자 횟수 반영)", "revised rule (repeated numbers counted)")}
for N in e8["sizes"]:
    e = e8["by_size"][str(N)]
    ko = " | ".join(f"{names[a][0]} 탐지 {e['detected_correct_item'][a]:.1%}, 연습문제 오인 {e['practice_refused'][a]}/{e8['n_practice']}" for a in ("top_set", "top_count"))
    en = " | ".join(f"{names[a][1]} detected {e['detected_correct_item'][a]:.1%}, practice refused {e['practice_refused'][a]}/{e8['n_practice']}" for a in ("top_set", "top_count"))
    say(f"   등록 {N:,}개: {ko}", f"   {N:,} items: {en}")

say("8. 한국어 문항과 숫자 없는 문항 (E9-001, 영어 계산형 60 + 한국어 계산형 60 + 한국어 서술형 60을 함께 등록)",
    "8. Korean items and items without numbers (E9-001, 60 English word problems + 60 Korean word problems + 60 Korean text items)")
e9 = load("E9-001_results.json")
ok9 = yes(e9["baseline_R0_equals_E8_at_60"])
say(f"   기준선: 영어 문항만 등록하고 E8 규칙을 쓰면 E8(등록 60개)과 같은 결과: {ok9}",
    f"   baseline: English items only with the E8 rule give the E8 result at 60 items: {ok9}")
sh, mp = e9["share_text_chosen"], e9["min_pieces_text"]
say(f"   서술형 질문의 일치 기준: 선정용 문항에서 {sh}(으)로 정한 뒤 새 문항으로 확인 (최소 조각 {mp}개)",
    f"   share for text questions: {sh}, chosen on a selection set and tested on new items (at least {mp} pieces)")
names9 = {"EN": ("영어 계산형", "English word problems"), "KN": ("한국어 계산형", "Korean word problems"),
          "KT": ("한국어 서술형(숫자 없음)", "Korean text items (no numbers)")}
for g, t in e9["validation_set"].items():
    r, o = t["refused_rewritten"], t["refused_other"]
    ko = (f"   {names9[g][0]}: 바꿔 쓴 질문 {t['n_rewritten']}건 거절 E8 규칙 {r['R0']:.1%}, 단순 확장 {r['R1']:.1%}, 제안 규칙 {r['R2']:.1%}"
          f" | 연습문제 오인 {o['practice']['R0']}, {o['practice']['R1']}, {o['practice']['R2']} /{o['practice']['of']}")
    en = (f"   {names9[g][1]}: {t['n_rewritten']} rewritten questions refused, E8 rule {r['R0']:.1%}, naive extension {r['R1']:.1%}, proposed rule {r['R2']:.1%}"
          f" | practice refused {o['practice']['R0']}, {o['practice']['R1']}, {o['practice']['R2']} of {o['practice']['of']}")
    if "stem_only" in o:
        s, so = o["same_passage_other_question"], o["stem_only"]
        ko += f" | 발문만 입력 시 거절 {so['R0']}, {so['R1']}, {so['R2']} /{so['of']} | 같은 지문에 다른 발문·선지: 제안 규칙 {s['R2']}/{s['of']} 거절"
        en += f" | stem alone refused {so['R0']}, {so['R1']}, {so['R2']} of {so['of']} | same passage, other stem and choices: proposed rule refused {s['R2']}/{s['of']}"
    say(ko, en)
c = e9["encrypted_check_R2"]
say(f"   암호화 조회로 다시 판정: {c['identical']}/{c['total']}건 같은 판정 (질문 {c['every']}건마다 1건)",
    f"   re-judged with the encrypted lookup: {c['identical']}/{c['total']} identical (every {c['every']}th question)")

say("9. 사진에서 읽은 글자에 오류가 있을 때 (E10-001, E9 제안 규칙)", "9. Reading errors in photos (E10-001, E9 proposed rule)")
e10 = load("E10-001_results.json")
for p, e in e10["by_rate"].items():
    r, fpr = e["copies_refused"], sum(e["practice_refused"].values())
    say(f"   글자 오류율 {float(p):.0%}: 거절 영어 계산형 {r['EN']:.1%}, 한국어 계산형 {r['KN']:.1%}, 한국어 서술형 {r['KT']:.1%}, 연습문제 오인 {fpr}/{3 * e['practice_of']}",
        f"   character error rate {float(p):.0%}: refused English word problems {r['EN']:.1%}, Korean word problems {r['KN']:.1%}, Korean text items {r['KT']:.1%}, practice refused {fpr}/{3 * e['practice_of']}")

say("10. AI 서비스 내부자의 사전 추측 (E11-001, 출제 틀을 모두 아는 공격자)",
    "10. Guessing by an insider at an AI service (E11-001, attacker who knows the item generator)")
e11 = load("E11-001_results.json")
w, tx, co = e11["word_problems"], e11["text_items"], e11["cost"]
say(f"   계산형 전체 복원 {w['rebuilt_exactly']}/{w['of']}, 서술형 모든 문장 복원 {tx['all_parts_recovered']}/{tx['of']},"
    f" 추측 {co['distinct_pieces_guessed']:,}조각(보통 질문 약 {co['same_as_ordinary_questions']}건 분량)",
    f"   word problems rebuilt {w['rebuilt_exactly']}/{w['of']}, text items with every sentence recovered {tx['all_parts_recovered']}/{tx['of']},"
    f" {co['distinct_pieces_guessed']:,} pieces guessed (about {co['same_as_ordinary_questions']} ordinary questions)")
l = e11["locked_distribution"]
say(f"   잠근 배포: 시작 전 일치 {l['guesses_matched_before_start']}/{l['guesses_tried']}, 열쇠 공개 후 원래 값과 같음: {yes(l['sets_identical_after_key_release'])}",
    f"   locked distribution: {l['guesses_matched_before_start']}/{l['guesses_tried']} guesses matched before the start, sets identical after key release: {yes(l['sets_identical_after_key_release'])}")

say("11. 문제를 나눠 물을 때 (E12-001)", "11. Questions split across messages (E12-001)")
e12 = load("E12-001_results.json")
for key, ko, en in (("verbatim_8", "그대로 8개로 나눔", "verbatim, 8 parts"), ("numbers_apart_8", "숫자 따로, 본문 8개", "numbers apart, text in 8 parts"),
                    ("numbers_apart_8_resolve", "숫자 따로, 본문 8개, 값 되돌리기", "numbers apart, text in 8 parts, values put back")):
    r = e12["attack"][key]
    one, allc = "/".join(f"{r['1'][g]:.0%}" for g in ("EN", "KN", "KT")), "/".join(f"{r['all'][g]:.0%}" for g in ("EN", "KN", "KT"))
    say(f"   {ko}: 메시지마다 {one}, 대화 전체 {allc} (영어 계산형/한국어 계산형/서술형)",
        f"   {en}: each message {one}, whole conversation {allc} (English word / Korean word / Korean text)")
o = e12["ordinary"]
s1, s2 = o["same_template_practice"], o["mixed_study"]
say(f"   학습 대화 오인: 같은 유형 연속 {s1['all']}/{s1['of']}, 섞은 대화 {s2['all']}/{s2['of']}",
    f"   study conversations refused: same-type practice {s1['all']}/{s1['of']}, mixed {s2['all']}/{s2['of']}")
r3 = e12["attack_R3"]["numbers_apart_8_resolve"]["all"]
o3 = e12["ordinary_R3"]
say(f"   최종 규칙 R3: 숫자 따로, 본문 8개, 값 되돌리기, 대화 전체 " + "/".join(f"{r3[g]:.0%}" for g in ("EN", "KN", "KT"))
    + f", 학습 대화 오인 {o3['same_template_practice']['all'] + o3['mixed_study']['all']}/1200",
    f"   final rule R3: numbers apart, text in 8 parts, values put back, whole conversation " + "/".join(f"{r3[g]:.0%}" for g in ("EN", "KN", "KT"))
    + f", study conversations refused {o3['same_template_practice']['all'] + o3['mixed_study']['all']}/1200")

say("12. 시험 기관 서버의 부하 (E13-001, 이 컴퓨터의 CPU 1개)", "12. Authority load (E13-001, one CPU core of the machine that ran it)")
e13 = load("E13-001_results.json")["load"]
say("   조각당 처리 시간: " + ", ".join(f"묶음 {k}개 {v['us_per_piece']}us" for k, v in e13["authority"].items()),
    "   time per piece: " + ", ".join(f"batch {k}: {v['us_per_piece']} us" for k, v in e13["authority"].items()))
q, z = e13["questions_per_second_per_core"], e13["sizing"]
say(f"   CPU 1개당 초당 질문: 한국어 {q['korean']}건, 영어 {q['english']}건 / 가정 초당 {z['assumed_questions_per_second']:,}건이면 CPU {z['cores_needed_korean']}개",
    f"   questions per second per core: Korean {q['korean']}, English {q['english']} / {z['cores_needed_korean']} cores for an assumed {z['assumed_questions_per_second']:,} Korean questions per second")
qb = e13["questions_per_second_per_core_bare"]
say(f"   타원곡선 곱셈만의 비용: 한국어 {qb['korean']}건, 영어 {qb['english']}건 / CPU {z['cores_needed_korean_bare']}개",
    f"   at the cost of the multiplication alone: Korean {qb['korean']}, English {qb['english']} / {z['cores_needed_korean_bare']} cores")

say("13. 기준값의 근거 (E14-001, 4글자, 서술형, 묶음 4개)", "13. Thresholds (E14-001, 4 characters, text items, four sets)")
op = load("E14-001_results.json")["operating_points_text_n4"]
for lab, key in (("R2 (20, 0.6)", 20), ("R3", "R3")):
    pts = [p_ for v in op.values() for p_ in v["points"] if p_["min_pieces"] == key and p_["share"] == 0.6]
    fp = [p_["short_practice_refused_per_1000"] for p_ in pts]
    say(f"   {lab}: 연습문제 일부 오인 1,000건당 {min(fp)}~{max(fp)}건, 연습문제 전체와 발문 오인 {sum(p_['practice_and_stems_refused'] for p_ in pts)}건",
        f"   {lab}: parts of practice problems refused {min(fp)} to {max(fp)} per 1,000, whole practice problems and stems refused {sum(p_['practice_and_stems_refused'] for p_ in pts)}")

say("14. 국제 표준 적합성 (STD-001)", "14. Conformance to standards (STD-001)")
txt = open(os.path.join(R, "STD-001_standards_check.txt")).read()
dec, i, objs = json.JSONDecoder(), 0, []
while i < len(txt):
    if txt[i] == "{":
        o_, i = dec.raw_decode(txt, i)
        objs.append(o_)
    else:
        i += 1
v, m = objs[0], objs[1]
say(f"   RFC 9497/9380 공식 시험 값: hash_to_curve {sum(x['ok'] for x in v['hash_to_curve'])}/{len(v['hash_to_curve'])}, OPRF 전부 일치: {yes(v['all_ok'])}",
    f"   RFC 9497/9380 official vectors: hash_to_curve {sum(x['ok'] for x in v['hash_to_curve'])}/{len(v['hash_to_curve'])}, OPRF all match: {yes(v['all_ok'])}")
say(f"   RFC 9162 참조 자료: 포함 증명 {m['inclusion']['agree']}/{m['inclusion']['files']}, 일관성 증명 {m['consistency']['agree']}/{m['consistency']['files']} 같은 판정",
    f"   RFC 9162 reference data: inclusion {m['inclusion']['agree']}/{m['inclusion']['files']}, consistency {m['consistency']['agree']}/{m['consistency']['files']} decided alike")
