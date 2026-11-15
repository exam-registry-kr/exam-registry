# 「시험 보호 국가 등록제」 제안 (Exam Registry)

진행 중인 시험 문제에 AI가 답하지 않도록 하는 국가 단위 등록 체계의 설계 문서, 시뮬레이션 코드, 실험 결과입니다. 수능에서 시작하여 자격시험, 대학 시험, 학교 내신으로 단계적으로 확대하고, 국제 표준으로 제안하는 것을 목표로 합니다. 누구나 아래 절차에 따라 결과를 직접 확인하고 재현할 수 있습니다.

이 제안은 2026년 11월 15일 국민신문고 일반제안으로 교육부에 제출하였습니다.

- 정책 제안서: [`docs/정책제안서.pdf`](docs/정책제안서.pdf)
- 기술 명세: [`docs/설계명세.pdf`](docs/설계명세.pdf)
- 시험 하루 시연 결과: [`docs/시험하루_시연.md`](docs/시험하루_시연.md)

## 1. 개요

AI 서비스는 지금 어디서 어떤 시험이 진행 중인지 알 수 없어 시험 부정행위에 대응하지 못하고 있습니다. 시험 보호 국가 등록제는 이 정보를 AI 서비스에 제공합니다. 어린이 보호구역이 학교 주변 도로에만 적용되어 다른 도로의 통행에는 영향을 주지 않듯이, 이 제도는 등록된 시험 문항에만 작동하며 시험이 끝나면 자동으로 해제됩니다.

1\. 시험 등록: 인가된 시험 기관이 시험 전에 시험명, 교시별 시간, 문항 해시(문항을 되돌릴 수 없는 요약값)를 전자서명하여 공개 장부인 국가 등록부에 등록합니다. 문항 원문은 등록하지 않습니다.

2\. 두 가지 열쇠: 협조하는 AI 서비스는 등록된 시간 동안 입력된 사진이나 문장이 진행 중인 시험과 일치하는지 다음 두 가지로 확인하고, 일치하면 답변을 거절합니다. 둘 중 하나만 일치해도 거절하므로, 한쪽이 확인하지 못하는 입력을 다른 쪽이 보완합니다.

가. 시험지 표식: 시험지 바탕에 시험 번호를 담은 옅은 노란 보안 문양을 인쇄합니다. 보안 문양은 작은 격자형 표식(ArUco)을 반복한 것으로, 시험지 일부만 촬영되어도 시험 번호를 읽을 수 있습니다. 판독은 AI 서비스 내부에서 이루어지며 외부 통신이 필요하지 않습니다. 인터넷 없이 작동하는 기기 내장 AI에는 문항 내용 조회를 쓸 수 없으므로, 휴대폰과 안경 제조사가 등록된 시험 시간 목록을 미리 받아 기기에 표식 판독을 넣는 경우에만 적용됩니다.

나. 문항 내용 조회: AI 서비스가 입력 문장을 4글자 조각으로 나누어 가린 상태로 시험 기관 서버에 조회합니다(망각 의사난수함수, IRTF RFC 9497). 시험 기관은 사용자의 입력을, AI 서비스는 문항 원문을 볼 수 없습니다. 암호화 조회가 일반 대조와 같은 판정을 내리는지는 3.5에서 확인합니다.

3\. 자동 해제와 사후 검증: 등록된 시간이 지나면 제한은 자동으로 해제됩니다. 시험 종료 후 공개되는 문항을 등록된 해시와 대조하면, 시험 문항 외에는 막지 않았는지 누구나 확인할 수 있습니다.

4\. 적발이 아니라 거절: 일치했을 때 일어나는 일은 답변 거절뿐이며, 기본값으로는 개인을 적발하거나 신고하지 않습니다. 시험별 거절 건수만 집계합니다. 교실 번호 추적이나 신고는 정부가 따로 결정할 선택지로만 남겨 두었습니다.

### 운영 체계

| 역할 | 담당 |
|---|---|
| 등록 기관 인가, 교육 분야 AI 서비스 준수 요건 | 교육부 |
| 국가 등록부와 공용 조회 서버 운영 | 국가가 지정한 교육 정보 시스템 운영 기관 |
| 시험 등록과 서명, 표식 인쇄 | 시험 기관 (수능과 모의평가는 한국교육과정평가원, 자격시험은 시행 기관) |
| 학교·대학 시험 등록 | 교육청과 대학 본부의 인가를 받은 교원. 자체 서버 없이 공용 조회 서버를 이용 |
| 판정과 거절, 거절 건수 보고 | 협조하는 AI 서비스 |
| 기기 내장 AI의 표식 판독 | 협조하는 휴대폰·안경 제조사 |

자세한 절차와 협조 요청 방식은 정책 제안서 7장에 있습니다.

국가가 이 체계를 한 번 구축하여 인가와 관리를 맡으면, 같은 등록 규격으로 국가시험뿐 아니라 자격시험, 대학 시험, 학교 내신, 온라인 시험도 등록할 수 있습니다. 같은 규격으로 나라마다 등록부를 운영하고 서로 연동할 수 있습니다.

## 2. 직접 확인하기 (약 5분)

### 2.1 준비

Python 3.10 이상이 필요합니다. 터미널(Windows는 명령 프롬프트)에서 저장소 폴더로 이동한 뒤 다음을 실행합니다.

```
pip install -r requirements.txt
cd code
```

한국어 글꼴이 필요합니다. Windows(맑은 고딕), macOS(Apple SD 산돌고딕 Neo), Linux(Noto Sans CJK)는 자동으로 찾습니다. 찾지 못하면 환경 변수 `EXAM_FONT`에 한국어 글꼴 파일 경로를 지정하십시오.

### 2.2 시연

```
python demo.py
```

시험 등록과 서명 확인, 표식이 인쇄된 시험지의 일부 촬영과 판독, 문항 내용 조회를 차례로 실행합니다. 다음과 같은 결과가 출력됩니다.

```
[1] 시험 등록
    등록 기록: {"exam_id": "5A17C0DE", "title": "2027학년도 모의 시험 수학 영역", "policy": "content_match"}
[2] 시험지 표식
    표식 있는 시험지 사진: 시험 번호 5A17C0DE 판독 (조각 6/6) -> 시험 시간 중 거절, 종료 후 정상 답변
    표식 없는 시험지 사진: 표식 없음 -> 정상 답변
[3] 문항 내용 조회
    원문 그대로: 일치율 100%, 숫자 일치 예 -> 거절
    띄어쓰기·표현 변경: 일치율  91%, 숫자 일치 예 -> 거절
    다른 숫자의 같은 유형 문제: 일치율  40%, 숫자 일치 아니오 -> 정상 답변
    무관한 질문: 일치율   0%, 숫자 일치 아니오 -> 정상 답변
```

`demo_out/` 폴더에 표식을 인쇄한 시험지(`page_marked.png`)와 모의 촬영 사진(`photo_marked.png`, `photo_unmarked.png`)이 저장됩니다. 표식의 진하기와 촬영 범위를 바꿔 볼 수 있습니다.

```
python demo.py --ink 0.5 --view 0.25
```

`--ink`는 노란 잉크가 청색광을 흡수하는 비율(인쇄 농도), `--view`는 사진에 담기는 시험지 높이의 비율입니다.

### 2.3 시험 하루 시연

```
python exam_day.py
```

교육부, 시험 기관, 국가 등록부, AI 서비스, 기기 제조사, 사후 검증자가 각자 가진 정보만으로 움직이는 시험 하루를 시간 순서대로 재생합니다(약 10초). 인가와 등록, 미인가 단체와 30시간 차단 등록의 거부, 시험 전·중·후의 사진과 문장 입력, 시험 종료 후 자동 해제, 문항 공개 후 누구나 하는 대조까지 차례로 실행하고, 단계마다 누가 무엇을 보았고 무엇을 보지 못했는지를 출력합니다. 판정은 실제로 계산한 결과입니다. 결과는 `exam_day_out/`에 시간표(`exam_day.html`, `exam_day.md`)와 사진으로 저장되며, 한 번 실행한 결과를 [`docs/시험하루_시연.md`](docs/시험하루_시연.md)에 올려 두었습니다.

### 2.4 문서에 인용된 수치 확인

```
python summarize_results.py
```

정책 제안서와 기술 명세에 인용된 모든 수치를 `results/` 폴더의 원자료에서 직접 계산하여 출력합니다.

## 3. 실험 결과와 재현 명령

모든 실험은 인쇄와 촬영 과정을 수치로 재현한 컴퓨터 시뮬레이션입니다. 각 시행의 난수 시드는 실험 조건의 이름으로 정해지므로, 같은 명령을 실행하면 같은 결과가 나옵니다. 소요 시간은 일반 노트북 1대 기준입니다.

| 항목 | 결과 | 재현 명령 (`code/` 폴더에서) | 소요 시간 |
|---|---|---|---|
| 표식 판독 (2,835회) | 다른 시험 번호로 잘못 판독 0건, 일반 문서 오인 0건. 시험지 높이의 25%만 촬영되어도 100%, 18%에서 93% 판독 (모서리 코드 1개 방식은 각각 0%) | 아래 3.1 | 약 2시간 (촬영 범위만: 약 7분) |
| 서명된 시험 시간에 따른 거절 | 시험 시간 안 60/60 거절, 시간 밖 거절 0건, 일반 페이지 500장 거절 0건. 위조 서명, 미인가 기관, 24시간 초과, 소급 등록은 모두 거부 | `python e2_protocol.py` | 약 15분 |
| 문항 조각 대조와 숫자 검사 | 같은 유형 연습문제 오인 0%, 바꿔 쓴 문장 97~100% 탐지 (실험용 문항, 일치 기준 0.5) | `python e3_registry.py` | 수 초 |
| 문장은 읽히나 표식은 판독되지 않는 사진 (1,152장) | 완전 판독만 사용 시 33장, 최종 판독기 0장. 최종 판독기의 일반 문서 오인 0/152 | 아래 3.2 | 약 30분 |
| 상용 AI가 읽을 수 있는지 (사진 36장) | 상용 AI가 문제를 푼 사진 10장은 모두 표식도 판독됨. 표식이 판독되지 않은 사진 22장은 상용 AI도 풀지 못함 | `python e5_stage2_score.py` | 수 초 |
| 실제 시험지 적용 | 현재 판독 가능한 최저 인쇄 농도 50% | 아래 3.3 | 약 5분 |
| 암호화된 문항 내용 조회 | 같은 판정 규칙의 일반 대조와 600건 모두 같은 판정. 질문 1건당 시험 기관 서버 처리 약 13ms, AI 서비스 측 전체 약 53ms (시연 구현, CPU 1개) | `python e7_oprf_lookup.py` | 약 1분 |

### 3.1 표식 판독

```
python e1_sim.py --trials 40 --grid 15 --mixed 250 --seed 20261115 --out e1_main
python e1_sim.py --factors "" --grid 0 --mixed 250 --seed 777 --out e1_seed777
python e1_merge.py e1_main e1_seed777
python e1_plot.py E1-005_results_v2_merged.json
```

촬영 범위 실험만 확인하려면 `python e1_sim.py --trials 40 --grid 0 --mixed 0 --factors view --out e1_view`를 실행합니다. 결과는 `results/E1-005_results_v2_merged.json`의 해당 행과 같습니다.

### 3.2 문장은 읽히나 표식은 판독되지 않는 사진

Tesseract OCR과 한국어·영어 언어 데이터가 필요합니다(Windows: UB Mannheim 배포판, macOS: `brew install tesseract tesseract-lang`, Linux: `tesseract-ocr-kor`).

```
python e5_legibility.py --seed 5050 --out e5_s5050
python e5_legibility.py --seed 6060 --out e5_s6060
python e5_collect.py e5_s5050 e5_s6060
NP=40 python e5_fp2.py highlighter
NP=20 python e5_fp2.py sticky
NP=8 python e5_fp2.py blocks
NP=8 python e5_fp2.py texture
```

같은 사진을 두 방법으로 읽습니다. 하나는 AI 서비스가 사용할 표식 판독기이고, 다른 하나는 문자 인식(OCR)으로 사진 속 문제 문장을 읽는 것입니다. 문장을 읽을 수 있는데 표식은 판독되지 않는 사진을 셉니다. Windows 명령 프롬프트에서는 `NP=40 python ...` 대신 `set NP=40` 후 `python ...`을 실행합니다.

#### 상용 AI로 다시 확인 (E5-003)

문자 인식 프로그램보다 사진을 잘 읽는 상용 AI로도 같은 질문을 확인했습니다. 3.2의 사진 가운데 36장을 AI에 보이기 전에 정한 규칙(`code/e5_stage2.py` 머리말)으로 골랐습니다. 최종 판독기가 표식을 읽지 못한 사진 20장(글자가 가장 큰 순), 그중 2장의 반복, 최종 판독기만 읽어 낸 작은 글씨 사진 10장, 선명한 대조 사진 4장입니다. 사진마다 ChatGPT(화면 표시 모델명 GPT-Astra)에 문제 번호, 읽은 문장, 답을 물었습니다.

| 묶음 | 장수 | 상용 AI가 푼 사진 | 표식 판독 |
|---|---|---|---|
| 최종 판독기가 표식을 읽지 못한 사진 (반복 2장 포함) | 22 | 0 | 0 |
| 최종 판독기만 읽어 낸 작은 글씨 사진 | 10 | 6 | 10 |
| 선명한 대조 사진 | 4 | 4 | 4 |

상용 AI가 푼 사진은 모두 표식도 판독되어, 협조하는 AI 서비스라면 답을 거절했을 사진입니다. 반대로 글자 크기가 6픽셀 안팎인 사진 4장은 상용 AI가 문장을 읽지 못했지만 표식은 판독되었습니다. 9번 사진은 처음에 같은 대화에서 바로 앞에 넣은 같은 시험지 사진(같은 1번 문항)의 내용으로 답했으나, 새 대화에서 사진 한 장만 넣어 두 가지 질문으로 다시 물었을 때는 모두 판독 불가였습니다. 정답은 사진의 시험지 번호로 문항을 다시 만들어 자동으로 채점합니다. 사진, 정답표, 질문, 응답 원문은 `results/E5-003_*`에 있습니다.

```
python e5_stage2_score.py
```

### 3.3 실제 시험지 적용

실제 시험지 원본은 저작권 때문에 포함하지 않았습니다. 공개 결과는 2026학년도 대학수학능력시험 국어 영역 1쪽(A3)으로 얻은 것이며, 이 시험지는 한국교육과정평가원 누리집에서 받을 수 있습니다. 시험지 PDF의 첫 쪽을 150 dpi 이미지 `page.png`로 저장한 뒤 실행합니다.

```
python e6_make_sample.py
python e6_check_decode.py 0.7 0.5 0.35 0.2 0.12
```

첫 명령은 표식을 입힌 견본 이미지(`sample_ink70.png` 등)를 저장하고, 둘째 명령은 인쇄 농도별로 모의 촬영 10회씩 판독 결과를 출력합니다.

### 3.4 문항 내용 조회의 원리

```
python oprf_demo.py
```

시험 기관이 사용자 입력을 보지 못하고 AI 서비스가 문항 원문을 보지 못하는 조회 방식을 짧은 코드로 보여줍니다. 원리 설명용이며 RFC 9497 구현이 아닙니다. 실제 운영에는 RFC 9497을 따르는 검증된 라이브러리를 사용해야 합니다.

### 3.5 암호화 조회가 판정을 바꾸는지와 처리 시간

```
python e7_oprf_lookup.py
```

위 표의 문항 조각 대조 실험(E3)과 같은 실험용 문항 60개, 자동으로 바꿔 쓴 질문 360개, 같은 유형의 연습문제 240개를 E3과 같은 순서로 다시 만들어 씁니다. 같은 판정 규칙(질문의 4글자 조각 중 한 문항에서 찾은 비율이 0.5 이상이고 질문의 숫자가 모두 그 문항에 있음)을 두 방식으로 적용해 비교합니다.

- 비교군(일반 대조): 조각을 암호화하지 않고 해시값으로 대조
- 암호화 조회: 조각을 P-256 타원곡선 기반 2HashDH 방식으로 가린 채 시험 기관에 조회

600건 모두 두 방식의 판정, 일치한 문항, 일치 비율이 같습니다. 바꿔 쓴 질문 탐지율과 연습문제 오인율(0%)도 E3 방식과 같습니다. 판정은 실행할 때마다 같고, 처리 시간은 컴퓨터에 따라 달라집니다. 이 구현은 처리 비용을 보이기 위한 시연이며 RFC 9497 구현이 아닙니다(곡선 위의 점으로 바꾸는 방식과 인코딩이 다름).

## 4. 결과를 읽을 때 유의할 점

- 모든 결과는 시뮬레이션입니다. 실제 카메라 촬영과 실제 인쇄물 측정은 시범 운영 단계에서 수행할 과제입니다.
- 최종 판독기(부분 판독과 확대·선명화)는 3.2 실험 결과를 확인한 뒤 개선한 것입니다. 개선 전 결과(33장)도 함께 공개합니다.
- 실험용 시험지에서는 낮은 인쇄 농도에서도 표식이 판독되었지만, 글자와 그림이 많은 실제 시험지에서는 현재 50%가 최저 농도입니다. 목표는 육안으로 거의 구분되지 않는 농도(`figures/sample_target_faint.png`)이며, 이를 위한 추가 연구를 진행할 예정입니다.
- 문항 내용 조회의 정확도는 실험용으로 만든 문항으로만 평가했습니다. 문항 조각 대조 실험(E3)과 3.5의 "바꿔 쓴 질문"은 띄어쓰기, 숫자 표기, 문장 순서, 일부 발췌, 단어 치환을 자동으로 적용한 것입니다. 문장을 완전히 바꿔 글로 입력한 질문은 탐지가 제한적입니다.
- 암호화 조회의 처리 시간은 시연 구현을 CPU 1개로 측정한 값입니다. 실제 운영 규모의 처리량은 공용 조회 서버를 구현한 뒤 측정해야 합니다.
- 상용 AI 판독 시험은 한 모델(GPT-Astra), 사진 36장의 결과입니다. 1차 질문의 원문은 보관하지 못했습니다(`results/E5-003_prompts.md`). 모델이 바뀌면 다시 확인해야 합니다.
- 라이브러리 버전이 크게 다르면 영상 처리 결과가 소수의 시행에서 달라질 수 있습니다. 시험한 버전은 `requirements.txt`에 적었습니다.
- 사용자가 직접 구성한 로컬 AI, 협조하지 않는 서비스, 사람에 의한 대리 풀이는 본 제안으로 막을 수 없으며 기존 단속과 감독이 담당합니다.

## 5. 저장소 구성

| 경로 | 내용 |
|---|---|
| `code/demo.py` | 5분 시연 |
| `code/exam_day.py` | 기관별 역할에 따른 시험 하루 시연 |
| `code/summarize_results.py` | 문서에 인용된 수치 출력 |
| `code/e1_sim.py`, `e1_merge.py`, `e1_plot.py` | 표식 인쇄·촬영·판독 시뮬레이션 |
| `code/e2_protocol.py` | 시험 등록, 서명, 시험 시간에 따른 거절 |
| `code/e3_registry.py` | 문항 조각 대조와 숫자 검사 |
| `code/oprf_demo.py` | 가린 상태의 문항 내용 조회 원리 |
| `code/e7_oprf_lookup.py` | 암호화 조회와 일반 대조의 판정 비교, 처리 시간 |
| `code/e5_legibility.py`, `e5_enh.py`, `e5_collect.py`, `e5_fp.py`, `e5_fp2.py` | 문장 판독과 표식 판독 비교, 최종 판독기, 일반 문서 오인 검사 |
| `code/e5_stage2.py`, `e5_stage2_score.py` | 상용 AI 판독 시험용 사진 생성과 채점 |
| `code/e6_make_sample.py`, `e6_check_decode.py` | 실제 시험지 적용 |
| `results/` | 실험 원자료 (파일명 앞의 E1~E7은 위 실험 순서) |
| `figures/` | 결과 그래프, 실험용 시험지 견본 |
| `docs/` | 정책 제안서, 기술 명세 |

## 6. 미포함 자료

- 실제 시험지 원본과 이를 이용한 견본 이미지 (저작권)

## 7. 라이선스

Apache License 2.0

## Summary (English)

Design documents, simulation code and results for an exam registry that lets cooperating AI services decline to answer questions from exams in progress. Accredited exam authorities register signed exam time windows and item hashes in a public append-only log. During a window, a service checks inputs with two keys: a printed yellow marker that carries the exam ID, and an oblivious content lookup (OPRF, as in RFC 9497) in which neither side sees the other's text. A match only makes the service decline to answer; by default nobody is identified or reported. In E7 the encrypted lookup reached the same decision as a plaintext lookup with the same rule on all 600 test queries (demonstration implementation, not RFC 9497). The proposal was submitted to the Korean Ministry of Education through the national e-People portal on 15 November 2026. Restrictions expire automatically. A commercial vision AI (ChatGPT, model shown as GPT-Astra) was also given 36 photos: every photo it could solve also had a readable marker, and it solved none of the 22 photos where the final decoder failed (E5-003). The same format extends from national exams to university, certification and online exams.

Quick start: `pip install -r requirements.txt`, then `cd code && python demo.py` (about five minutes). `python summarize_results.py` prints every number quoted in the documents from the raw results. All results come from print-and-capture simulation; the final marker decoder was revised after inspecting the E5 results, and the pre-revision numbers are also published.
