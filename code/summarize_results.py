"""Print every number quoted in the documents, read directly from results/.

    python summarize_results.py

Takes a few seconds and needs only the Python standard library.
"""
import json, os

R = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "results")
load = lambda f: json.load(open(os.path.join(R, f), encoding="utf-8"))

print("1. 표식 판독 (E1-005, E1-006)")
e1 = load("E1-005_results_v2_merged.json")
mix = [json.loads(l)["result"] for l in open(os.path.join(R, "E1-006_mixed_trials_v2_2seeds.jsonl"))]
rows = [r for f in e1["sweeps"].values() for p in f for r in p["rows"]] + [r for c in e1["grid"] for r in c["rows"]] + mix
print(f"   판독 시행 {len(rows):,}회, 다른 시험 번호로 잘못 판독 {sum(r['M2final'] == -1 for r in rows)}건,"
      f" 표식 없는 페이지 오인 {sum(r['M0_fp'] for r in rows)}건")
for p in e1["sweeps"]["view"]:
    print(f"   시험지 높이 {p['value']:.0%} 촬영: 노란 표식 {p['M2final']['correct']:.1%}, 모서리 코드 1개 {p['M1']['correct']:.1%} (n={p['n']})")

print("2. 서명된 시간 창에 따른 거절 (E2-001)")
e2 = load("E2-001_results.json")
print("   등록 검증:", e2["protocol"])
print("   표식 있는 시험지:", e2["marked_page"])
b = e2["benign_in_window"]
print(f"   일반 페이지 {sum(v['n'] for v in b.values())}장 중 거절 {sum(v['refused'] for v in b.values())}건")

print("3. 문항 조각 대조와 숫자 검사 (E3-001, 일치 기준 0.5)")
e3 = load("E3-001_results.json")["thresholds"]["0.5"]
for k, v in e3.items():
    print(f"   {k:42s} 조각+숫자 {v['ngram_num']:.1%}")

print("4. 문장은 읽히나 표식은 판독되지 않는 사진 (E5-001)")
e5 = load("E5-001_rows.json")
gap = lambda r, k: (r["readable"] or r["numbers_ok"]) and not r[k]
for k, name in (("marker", "완전 판독만"), ("marker_partial", "4조각 부분 판독"), ("marker_enh", "부분 판독 + 확대·선명화 (최종)")):
    print(f"   {name}: {sum(gap(r, k) for r in e5)}/{len(e5)}장")
fails = [r for r in e5 if not r["marker_enh"]]
print(f"   최종 판독기가 실패한 사진의 최대 글자 크기 {max(r['em_px'] for r in fails):.1f}픽셀, 최소 글자 인식 오류율 {min(r['cer'] for r in fails):.0%}")
fp = load("E5-002_false_positives.json")["decoder_final_enhanced"]
print(f"   최종 판독기의 일반 문서 오인 {sum(v['matches'] for v in fp.values())}/{sum(v['captures'] for v in fp.values())}")

e53 = load("E5-003_scored.json")
print(f"   상용 AI 판독 시험(E5-003): 사진 {e53['n_photos']}장 중 AI가 푼 사진 {e53['solved']}장, 그중 표식 판독 {e53['solved_with_marker']}장,"
      f" 표식 미판독인데 AI가 푼 사진 {len(e53['gaps'])}장")

print("5. 실제 시험지 적용 (E6-001, 조건당 10회, 최종 판독기)")
e6 = load("E6-001_realpage_decode.json")["results"]
for ink in ("0.7", "0.5", "0.35", "0.2", "0.12"):
    cells = [f"{k.split('_', 1)[1]}={v['final']}/{v['n']}" for k, v in e6.items() if k.startswith(f"ink{ink}_")]
    print(f"   인쇄 농도 {float(ink):.0%}: " + ", ".join(cells))

print("6. 암호화된 문항 내용 조회 (E7-001, 일치 기준 0.5)")
e7 = load("E7-001_results.json")
d = e7["identical_decisions"]
print(f"   암호화 조회와 일반 대조의 판정 일치 {d['count']}/{d['total']}건")
for k, v in e7["detection_and_false_match"].items():
    label = "같은 유형 연습문제 오인" if k == "practice" else f"바꿔 쓴 질문({k}) 탐지"
    print(f"   {label}: 일반 대조 {v['plain']:.1%}, 암호화 조회 {v['oprf']:.1%}, E3 방식 {v['e3']:.1%}")
t = e7["timing"]
print(f"   질문 1건당 조각 {t['pieces_per_query_median']:.0f}개(중앙값), AI 서비스 측 총 {t['client_total_ms_median']}ms,"
      f" 시험 기관 서버 {t['authority_ms_per_query_median']}ms, 조각당 전송 {t['bytes_per_piece_each_way']}바이트(각 방향)")
print("   (시연 구현 기준. RFC 9497 구현이 아니며 측정 환경에 따라 달라짐)")

print("7. 등록 문항 수를 늘렸을 때 (E8-001, 모든 문항이 같은 12개 유형인 가장 불리한 조건)")
e8 = load("E8-001_results.json")
b = e8["by_size"][str(e8["sizes"][0])]["baseline_top_set_matches_E7_plain"]
print(f"   기준선: 등록 {e8['sizes'][0]}개에서 E7 일반 대조와 같은 판정 {b['count']}/{b['total']}건")
names = {"top_set": "E7 규칙(숫자 한 번씩)", "top_count": "보완 규칙(반복 숫자 횟수 반영)"}
for N in e8["sizes"]:
    e = e8["by_size"][str(N)]
    cells = [f"{names[a]} 탐지 {e['detected_correct_item'][a]:.1%}, 연습문제 오인 {e['practice_refused'][a]}/{e8['n_practice']}"
             for a in ("top_set", "top_count")]
    print(f"   등록 {N:,}개: " + " | ".join(cells))

print("8. 한국어 문항과 숫자 없는 문항 (E9-001, 영어 계산형 60 + 한국어 계산형 60 + 한국어 서술형 60을 함께 등록)")
e9 = load("E9-001_results.json")
print(f"   기준선: 영어 문항만 등록하고 E8 규칙을 쓰면 E8(등록 60개)과 같은 결과: {'예' if e9['baseline_R0_equals_E8_at_60'] else '아니오'}")
print(f"   서술형 질문의 일치 기준: 선정용 문항에서 {e9["share_text_chosen"]}(으)로 정한 뒤 새 문항으로 확인 (최소 조각 {e9['min_pieces_text']}개)")
names9 = {"EN": "영어 계산형", "KN": "한국어 계산형", "KT": "한국어 서술형(숫자 없음)"}
for g, t in e9["validation_set"].items():
    r, o = t["refused_rewritten"], t["refused_other"]
    line = f"   {names9[g]}: 바꿔 쓴 질문 {t['n_rewritten']}건 거절 E8 규칙 {r['R0']:.1%}, 단순 확장 {r['R1']:.1%}, 제안 규칙 {r['R2']:.1%}"
    line += f" | 연습문제 오인 {o['practice']['R0']}, {o['practice']['R1']}, {o['practice']['R2']} /{o['practice']['of']}"
    if "stem_only" in o:
        line += f" | 발문만 입력 시 거절 {o['stem_only']['R0']}, {o['stem_only']['R1']}, {o['stem_only']['R2']} /{o['stem_only']['of']}"
        s = o["same_passage_other_question"]
        line += f" | 같은 지문에 다른 발문·선지: 제안 규칙 {s['R2']}/{s['of']} 거절"
    print(line)
c = e9["encrypted_check_R2"]
print(f"   암호화 조회로 다시 판정: {c['identical']}/{c['total']}건 같은 판정 (질문 {c['every']}건마다 1건)")

print("9. 사진에서 읽은 글자에 오류가 있을 때 (E10-001, E9 제안 규칙)")
e10 = load("E10-001_results.json")
for p, e in e10["by_rate"].items():
    r = e["copies_refused"]
    print(f"   글자 오류율 {float(p):.0%}: 거절 영어 계산형 {r['EN']:.1%}, 한국어 계산형 {r['KN']:.1%}, 한국어 서술형 {r['KT']:.1%},"
          f" 연습문제 오인 {sum(e['practice_refused'].values())}/{3 * e['practice_of']}")

print("10. AI 서비스 내부자의 사전 추측 (E11-001, 출제 틀을 모두 아는 공격자)")
e11 = load("E11-001_results.json")
print(f"   계산형 전체 복원 {e11['word_problems']['rebuilt_exactly']}/{e11['word_problems']['of']},"
      f" 서술형 모든 문장 복원 {e11['text_items']['all_parts_recovered']}/{e11['text_items']['of']},"
      f" 추측 {e11['cost']['distinct_pieces_guessed']:,}조각(보통 질문 약 {e11['cost']['same_as_ordinary_questions']}건 분량)")
l = e11["locked_distribution"]
print(f"   잠근 배포: 시작 전 일치 {l['guesses_matched_before_start']}/{l['guesses_tried']}, 열쇠 공개 후 원래 값과 같음: {'예' if l['sets_identical_after_key_release'] else '아니오'}")

print("11. 문제를 나눠 물을 때 (E12-001)")
e12 = load("E12-001_results.json")
for key, label in (("verbatim_8", "그대로 8개로 나눔"), ("numbers_apart_8", "숫자 따로, 본문 8개"), ("numbers_apart_8_resolve", "숫자 따로, 본문 8개, 값 되돌리기")):
    r = e12["attack"][key]
    print(f"   {label}: 메시지마다 " + "/".join(f"{r['1'][g]:.0%}" for g in ("EN", "KN", "KT")) +
          ", 대화 전체 " + "/".join(f"{r['all'][g]:.0%}" for g in ("EN", "KN", "KT")) + " (영어 계산형/한국어 계산형/서술형)")
o = e12["ordinary"]
print(f"   학습 대화 오인: 같은 유형 연속 {o['same_template_practice']['all']}/{o['same_template_practice']['of']}, 섞은 대화 {o['mixed_study']['all']}/{o['mixed_study']['of']}")

print("12. 시험 기관 서버의 부하 (E13-001, 이 컴퓨터의 CPU 1개)")
e13 = load("E13-001_results.json")["load"]
print("   조각당 처리 시간: " + ", ".join(f"묶음 {b}개 {v['us_per_piece']}us" for b, v in e13["authority"].items()))
q = e13["questions_per_second_per_core"]
print(f"   CPU 1개당 초당 질문: 한국어 {q['korean']}건, 영어 {q['english']}건 / 가정 초당 {e13['sizing']['assumed_questions_per_second']:,}건이면 CPU {e13['sizing']['cores_needed_korean']}개")
