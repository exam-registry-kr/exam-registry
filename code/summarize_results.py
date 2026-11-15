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
