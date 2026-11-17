# Exam Registry: a national registry that keeps AI from answering exams in progress

[한국어](README.md) | English

An AI does not know where an exam is being held right now, or which one. It cannot tell a question sent from an exam room from the same question sent by a student studying at home, and it answers both. Korea is a country that delays the morning commute for the one day of its college entrance exam (CSAT) and stops aircraft from taking off and landing during the listening test. The whole society has agreed that exams, at least, must be fair, and the state has taken responsibility from writing the items to delivering the papers so that about 500,000 examinees receive the same questions at the same moment. This proposal extends that responsibility to AI. The state keeps a registry of exam information signed by the exam authorities, and cooperating AI services decline to answer the registered items, and only those, for the duration of that exam. Proctoring and the ban on electronic devices guard the exam room; the registry keeps a device that slips past them from getting an answer out of an AI. With this much experience of running nationwide exams strictly, we think Korea can write this specification first and propose it as an international standard.

The design gives the most weight to three things.

1. **Privacy that is free from censorship.** The exam authority never sees a user's question and the AI service never sees the text of an exam item, and the decision is still made. On a match the answer is declined and nothing else happens: nobody is identified or reported. Every registration is signed and stays in a public log, so after the exam anyone can check whether anything other than exam items was blocked.
2. **A burden an AI company can accept.** An AI company does not have to judge for itself what is an exam question; it declines only what is on a list signed by the state. It never receives the item text, so it carries no responsibility for a leak, and once the specification is a standard no company has to build its own.
3. **An exam where solving it yourself beats cheating.** A photo of the page is caught by the marker printed on the page, and a typed copy of the question by the content lookup. What remains takes time, such as rewriting every sentence by hand or translating the item, and the aim is that an examinee decides it is better to solve the question than to do that within the exam time.

This repository publishes the design documents, the simulation code and the experimental results. The experiment behind each point above can be run directly, and what is not caught and what has not been measured yet are written down as well (At a glance, section 4).

The proposal was submitted to the Korean Ministry of Education on 15 November 2026 as a public proposal through e-People (국민신문고), the government's national petition and proposal portal. The policy proposal and the design specification were updated on 16 November 2026 to include the experiments added after submission and the move to published standards (encrypted lookup on RFC 9497, public log on RFC 9162, decision rule R5). The gap in the decision rule found after submission is described in 3.14, and the rule that closes it in 3.18. The versions as submitted are in `docs/` at commit 25b230f.

Contact: Dongwhi Kim (Department of Electrical Engineering, Hanyang University), dongwhi01@hanyang.ac.kr

- Policy proposal (Korean): [`docs/정책제안서.pdf`](docs/정책제안서.pdf)
- Technical specification (Korean): [`docs/설계명세.pdf`](docs/설계명세.pdf)
- Operation walkthrough: [`docs/operation_walkthrough_en.md`](docs/operation_walkthrough_en.md) (English translation of one run), Korean original [`docs/운영과정_시연.md`](docs/운영과정_시연.md)

Background terms
- CSAT: Korea's national college entrance exam (수능), taken by about half a million students on one day each November.
- KICE: Korea Institute for Curriculum and Evaluation (한국교육과정평가원), which sets the CSAT and its mock exams.
- School exams (내신): midterm and final exams set by each school; they count toward university admission.

## At a glance

As of 16 November 2026. Every figure comes from computer simulation and test items made for the experiments; each line below can be checked in the section named and in the raw results under `results/`.

| | |
|---|---|
| Rule adopted | R5 (definition and values in 3.18). It closes a gap in the rule of the submitted proposal, found by the author after submission (3.14). |
| Checked | Questions that copy an item as printed, or change its spacing, sentence order or some words, are refused at 99.4 to 100% (3.7). An item with a number or unrelated sentences put in front is refused at 100% (3.18), and an item split across messages at 100% when the whole conversation is judged (3.10). None of 720 practice problems that differ only in their numbers was refused (3.18). The authority never sees the question and the AI service never sees the item text, and the decision is the same (3.5). |
| Not caught | A short quote of 20 to 60% of an item is refused only 77.3% of the time. A question with every sentence reworded (2.8% refused), a translated question (0%), a filler word after every two words (5%). Services that do not cooperate, self-installed AI, a person solving for the examinee. |
| Cost | About 130 pieces per question and one elliptic-curve multiplication per piece (3.11). One of 100 conversations of 32 practice problems in a row was wrongly refused (3.18). A conversation that holds a whole item is refused until the exam ends (3.17). |
| Not measured yet | Real cameras and real prints, real textbooks and real study questions, a neural sentence embedding as a baseline, rewording by an AI, the throughput of an optimized implementation. The full list is in section 4. |

To run it yourself in five minutes go to 2.2; the summary of all experiments is the first table of section 3; the limits are in section 4.

## 1. Overview

AI services today cannot tell which exam is being held where and when, so they have no way to respond to cheating during exams. The exam registry gives them that information. A school zone speed limit applies only to the roads around a school and leaves every other road alone; in the same way, the registry acts only on registered exam items, and only while the exam is running.

1\. Registration: before the exam, an accredited exam authority signs the exam name, the time window of each period and a hash of the items (a one-way digest from which the items cannot be recovered), and registers them in the national registry, a public append-only log. The item text itself is not registered.

2\. Two keys: during a registered window, a cooperating AI service checks whether an input photo or text matches an exam in progress, in the two ways below, and declines to answer if it does. Either key is enough to refuse, so each key covers inputs the other cannot check.

a. Content lookup (core): the service cuts the input text into 4-character pieces and looks them up at the exam authority's server in blinded form (an oblivious pseudorandom function, as in IRTF RFC 9497). The authority never sees the user's input and the service never sees the item text. Section 3.5 checks that the encrypted lookup gives the same decisions as plain matching.

b. Exam page marker (supplement): a faint yellow security pattern carrying the exam ID is printed in the background of the exam page. It repeats a small grid marker (ArUco), so the exam ID can be read even from a photo of part of the page. Decoding runs inside the AI service and needs no outside call. On-device AI that runs without internet cannot use the content lookup, so it is covered only where phone and glasses makers receive the list of registered windows in advance and build the marker decoder into the device.

3\. Automatic release and audit: the restriction ends when the registered window ends. After the exam the items are published, and anyone can compare them with the registered hash to confirm that nothing but the exam items was blocked.

4\. Refusal, not detection: a match only makes the service decline to answer. By default nobody is identified or reported; only the number of refusals per exam is counted. Tracing a classroom or reporting a person is left as a separate option for the government to decide.

### Who does what

| Role | Party |
|---|---|
| Accrediting registering authorities, compliance requirements for AI services in education | Ministry of Education |
| Running the national registry and the shared lookup server | An education information system operator designated by the state |
| Registering and signing exams, printing the marker | Exam authorities (KICE for the CSAT and mock exams, the administering body for certification exams) |
| Registering school and university exams | Teachers accredited by the regional office of education or the university; they use the shared lookup server and need no server of their own |
| Deciding, refusing, reporting refusal counts | Cooperating AI services |
| Marker decoding in on-device AI | Cooperating phone and glasses makers |

Chapter 7 of the policy proposal describes the procedures and how cooperation is requested.

Once the state builds this system and takes charge of accreditation and management, the same registration format can cover not only national exams but certification exams, university exams, school exams and online exams. Each country can run its own registry in the same format, and registries can be linked.

## 2. Try it (about five minutes)

### 2.1 Setup

Python 3.10 or later. In a terminal (Command Prompt on Windows), go to the repository folder and run:

```
pip install -r requirements.txt
cd code
```

A Korean font is needed for the simulated exam pages. Windows (Malgun Gothic), macOS (Apple SD Gothic Neo) and Linux (Noto Sans CJK) are found automatically. Otherwise set the environment variable `EXAM_FONT` to the path of a Korean font file.

### 2.2 Demo

```
python demo.py --en
```

Runs exam registration and signature checking, decoding of the marker from a partial photo of a marked exam page, the content lookup and the adopted rule (about one minute). Output:

```
[1] Exam registration
    Registered record: {"exam_id": "5A17C0DE", "title": "2027학년도 모의 시험 수학 영역", "policy": "content_match"}
[2] Exam page marker
    Photo of the marked exam page: exam ID 5A17C0DE read (6/6 chunks) -> during the exam refused, after it normal answer
    Photo of the unmarked exam page: no marker -> normal answer
[3] Content lookup
    Item as printed: pieces matched 100%, numbers match yes -> refused
    Spacing and wording changed: pieces matched  91%, numbers match yes -> refused
    Same type, different numbers: pieces matched  40%, numbers match no -> normal answer
    Unrelated question: pieces matched   0%, numbers match no -> normal answer
[4] The adopted rule R5 (3.18). The earlier rule R3 in brackets
    Registered item as printed: 36 of 36 pieces match -> refused (R3: refused)
    "문제 23번" (question 23) put in front: 36 of 41 pieces match -> refused (R3: normal answer)
    Three unrelated sentences put in front: 36 of 93 pieces match -> refused (R3: normal answer)
    Practice problem, other numbers: 25 of 36 pieces match -> normal answer (R3: normal answer)
    Every sentence reworded (not caught): 7 of 43 pieces match -> normal answer (R3: normal answer)
```

Step [3] shows the principle of the lookup with the first rule (share of pieces and the number check). Step [4] shows the adopted rule R5 on one Korean item ("A train ran 150 km in 43 hours. How many km does it run in 16 hours at the same speed?"). Its second and third lines are the gap found after submission; its last line is a case that is still not caught.

The marked page (`page_marked.png`) and simulated photos (`photo_marked.png`, `photo_unmarked.png`) are saved in `demo_out/`. You can change the marker strength and the photographed area:

```
python demo.py --en --ink 0.5 --view 0.25
```

`--ink` is the share of blue light absorbed by the yellow ink (print strength); `--view` is the photographed height as a share of the page height. Without `--en` the output is in Korean.

### 2.3 Operation walkthrough

```
python operation_demo.py
```

Plays one mock exam day from preparation two months ahead to the audit after the exam. The Ministry, a regional office of education, the registry operator, the exam authority, the printer, an AI service, a device maker and an auditor each act only on the information they hold (about 15 seconds).

1. Preparation: the Ministry designates the registry operator, accredits KICE directly, and delegates school accreditation to an office of education. Agreements are signed with an AI service and device makers.
2. Compliance test: a 30-minute test exam is registered to check that the AI service refuses only during the window.
3. Exam preparation: items are frozen, an unused exam ID is confirmed in the log, item pieces are encrypted, the papers are printed, and a printed sample is checked with the decoder.
4. Registration and distribution: a signed record is registered; an unaccredited group, a school registering a CSAT-type exam, a duplicate ID, a record changed in transit and a 30-hour block are rejected. Schools register without revealing their items by having pieces encrypted through the shared lookup server. The operator signs the log head (Merkle root). Encrypted piece sets are distributed locked; the AI service re-verifies the log and stores the locked sets, so an insider has nothing to compare guesses with (3.9). The device maker checks an inclusion proof for each exam and pushes only exam IDs and windows under its own signature, and a list with an extra exam slipped in is refused. Anyone can see which exams will be blocked the next day.
5. Exam day: set keys are released and the sets opened at the start (a tampered set is discarded); photos and text before, during and after the exam; on-device AI; an attempt to register after the start.
6. After the exam: the items and the commitment secret are published and checked, a consistency proof shows the log was not rewritten (a log with a changed past record is caught), and refusal counts per exam are reported.

Each step prints who acted, what that party saw and what it did not see. Decisions are computed, not scripted, and are the same on every run. The script prints Korean; an English translation of one run is in [`docs/operation_walkthrough_en.md`](docs/operation_walkthrough_en.md). Results are written to `operation_demo_out/` as a timeline (`operation_demo.html`, `operation_demo.md`) and photos.

### 2.4 Check the numbers quoted in the documents

```
python summarize_results.py --en
```

Computes every number quoted in the policy proposal and the specification directly from the raw data in `results/` and prints it.

## 3. Results and how to reproduce them

All experiments are computer simulations that model printing and photographing numerically. The random seed of each trial is derived from the name of its condition, so the same command gives the same result. Run times are for one ordinary laptop.

| Item | Result | Command (in `code/`) | Time |
|---|---|---|---|
| Marker decoding (2,835 trials) | 0 read as a wrong exam ID, 0 ordinary documents taken as marked. 100% decoded from a photo of 25% of the page height, 93% at 18% (a single corner code: 0% at both) | see 3.1 | about 2 h (photographed area only: about 7 min) |
| Refusal by signed time window | 60/60 refused inside the window, none outside it, 0 of 500 ordinary pages refused. Forged signature, unaccredited authority, window over 24 h and retroactive registration all rejected | `python e2_protocol.py` | about 15 min |
| Piece matching with number check | 0% of same-type practice problems refused, 97 to 100% of rewritten questions detected (test items, threshold 0.5) | `python e3_registry.py` | seconds |
| Photos whose text is readable but whose marker is not (1,152 photos) | 33 with full decoding only, 0 with the final decoder. Final decoder on ordinary documents: 0/152 false matches | see 3.2 | about 30 min |
| Can a commercial AI read them (36 photos) | Every photo the AI solved (10) also had a readable marker. The AI solved none of the 22 photos whose marker could not be read | `python e5_stage2_score.py` | seconds |
| Real exam page | Lowest print strength currently decodable: 50% | see 3.3 | about 5 min |
| Encrypted content lookup (RFC 9497) | Same decision as plain matching with the same rule on all 600 queries. Per question about 37 ms at the authority and about 174 ms in total at the service (this repository's Python implementation, one CPU) | `python e7_oprf_lookup.py` | about 1 min |
| Registry grown to 60,000 items | Detection of rewritten questions stays at 99.4%. Practice problems refused: 1/240 from 6,000 items with the E7 rule, 0/240 up to 60,000 with a revised rule that counts repeated numbers | `python e8_registry_scale.py` | about 30 s |
| Korean items, items without numbers | The earlier rule refused 0% of number-free text items. The proposed rule (R2), E14's rule (R3) and the final rule (R5) all refused 100% of 480 rewritten questions, 0/240 practice problems, 0/10 stems typed alone. Korean word problems: 99.7% (on new items) | `python e9_korean_text_items.py` | about 3 min |
| Reading errors in photos | At a 5% character error rate, 100% of text items and 70 to 76% of word problems refused (same under R2, R3 and R5). A single misread digit lets a word problem through. 0/720 practice problems refused at every error rate | `python e10_reading_errors.py` | seconds |
| Can an insider at an AI service learn the items before the exam | With open sets, an insider who knows how the items were generated rebuilds all 120 Korean items from 18,605 guessed pieces (about 140 ordinary questions). With sets distributed locked and the key released at the start: 0 matches before the start | `python e11_insider_guessing.py` | about 1 min |
| Questions split across messages | Verbatim splits are all refused. With numbers replaced by letters and the values sent separately, judging each message alone refuses 0 to 58% of Korean word problems; judging the whole conversation and putting values such as "A=168" back refuses 97 to 100% under R2 and 100% under R3 and R5. 0 of 1,200 study conversations refused | `python e12_split_questions.py` | about 30 s |
| Authority load, test vectors for integration | One CPU core serves about 15 Korean questions per second with this repository's RFC 9497 implementation, about 123 counting the elliptic-curve multiplication alone; batching does not lower the cost per piece. RFC 9497 piece values and 11 decisions of the final rule (R5) under a public test key are published | `python e13_load_and_vectors.py` | about 1 min |
| Why these piece lengths and thresholds | 2-character pieces refuse whole practice problems and are ruled out; 4 is the longest length that still refuses every text item at 5% reading errors. Share 0.5 for word problems is the highest value that loses no detection. R2 refuses 76 to 102 of every 1,000 study questions that quote part of a practice problem; replaced by R3, which requires 60% of the matched item's pieces (at most 60): 0.8 to 8.6 per 1,000 over four sets | `python e14_sensitivity.py` | about 1 min |
| Conformance to international standards | Encrypted lookup: RFC 9497 (with RFC 9380) official vectors, hash_to_curve 5/5, OPRF 2/2, key derivation matches. Log moved to the RFC 9162 Merkle tree: all 86 inclusion and 98 consistency reference cases (172 must-reject) decided as the reference implementation does | see 3.13 | seconds |
| Comparison with simpler methods, cheap ways around (E16) | An exact hash refuses 16.7% of the earlier rewritten questions, a keyword list 33.1%, vector similarity 40.4%, R3 90%. **R3 refuses 0% when one number is put in front of the item and 0 to 24% when unrelated sentences are added in front or in between.** Rule R5 was designed to close this, its values were chosen again in E19, and it was adopted. Fully reworded or translated questions get past every method | `python e16_baselines.py` | about 4 minutes |
| What the lookup server can learn from request sizes (E15) | From the element count alone it names the item of a question with probability 10.7% (chance 0.6%). Padding to multiples of 32: 1.6% (load x1.218); batching 4 questions: 0.7% (no extra load) | `python e15_lookup_metadata.py` | seconds |
| When the lookup server is down (E17) | No new piece can be looked up; a service that keeps answering refuses 0% of exam questions. Judging with the piece values kept from earlier lookups: 41.6% after 100 questions, 82.7% after 1,000, 89.8% after 5,000 (normal operation 89.8%) | `python e17_outage.py` | about 1 minute |
| Can someone make another person's question be refused (E18) | With a whole item planted in a conversation, R5 refuses the study questions of that conversation until the exam ends (180/180); 22/180 with 80% planted, 3/180 with 60%. Stems only: 0. R3 did not refuse (0/540), and for the same reason was open to padding | `python e18_refusal_abuse.py` | about 3 minutes |
| Adoption of rule R5 and its values (E19) | Values chosen again with 900 more long practice conversations on the selection set (90% of the item's pieces, run 1.5x). On 180 new items never used before: all five padding-type ways around refused at 100%, everything R3 refused unchanged. Wrongly refused: 1 of 100 conversations of 32 practice problems; none of 600 shorter conversations and 720 practice problems | `python e19_adopt_r5.py` | about 5 minutes |
![Marker decoding by condition](figures/fig_e1_sweeps_v2.png)

### 3.1 Marker decoding

```
python e1_sim.py --trials 40 --grid 15 --mixed 250 --seed 20261115 --out e1_main
python e1_sim.py --factors "" --grid 0 --mixed 250 --seed 777 --out e1_seed777
python e1_merge.py e1_main e1_seed777
python e1_plot.py E1-005_results_v2_merged.json
```

To check only the photographed-area sweep, run `python e1_sim.py --trials 40 --grid 0 --mixed 0 --factors view --out e1_view`. The result matches the corresponding rows of `results/E1-005_results_v2_merged.json`.

### 3.2 Photos whose text is readable but whose marker is not

Needs Tesseract OCR with Korean and English language data (Windows: UB Mannheim build, macOS: `brew install tesseract tesseract-lang`, Linux: `tesseract-ocr-kor`).

```
python e5_legibility.py --seed 5050 --out e5_s5050
python e5_legibility.py --seed 6060 --out e5_s6060
python e5_collect.py e5_s5050 e5_s6060
NP=40 python e5_fp2.py highlighter
NP=20 python e5_fp2.py sticky
NP=8 python e5_fp2.py blocks
NP=8 python e5_fp2.py texture
```

Each photo is read in two ways: by the marker decoder an AI service would use, and by OCR, which reads the question text in the photo. The experiment counts photos whose text can be read while the marker cannot. On Windows Command Prompt use `set NP=40` and then `python ...` instead of `NP=40 python ...`.

#### Rechecked with a commercial AI (E5-003)

The same question was checked with a commercial AI, which reads photos better than OCR. 36 photos from 3.2 were chosen by a rule fixed before any photo was shown to the AI (header of `code/e5_stage2.py`): the 20 photos where the final decoder failed (largest text first), 2 repeats of those, 10 small-text photos only the final decoder could read, and 4 clear control photos. For each photo, ChatGPT (model shown on screen as GPT-Astra) was asked for the question number, the text it read and the answer.

| Group | Photos | Solved by the AI | Marker decoded |
|---|---|---|---|
| Final decoder could not read the marker (2 repeats included) | 22 | 0 | 0 |
| Small text, read only by the final decoder | 10 | 6 | 10 |
| Clear controls | 4 | 4 | 4 |

Every photo the AI solved also had a readable marker, so a cooperating service would have refused it. Conversely, in 4 photos with text about 6 pixels high the AI could not read the text while the marker was decoded. Photo 9 was first answered from the content of the same exam page (the same question 1) shown just before in the same chat; asked again in a new chat with that photo alone and two different prompts, it was unreadable both times. Answers are scored automatically by regenerating the items from the page ID in each photo. Photos, answer key, prompts and raw responses are in `results/E5-003_*` (prompts in Korean).

```
python e5_stage2_score.py
```

### 3.3 Real exam page

The original exam paper is not included for copyright reasons. The published result was obtained on page 1 (A3) of the Korean language section of the 2026 CSAT, which can be downloaded from KICE's website. Save the first page of the exam PDF as a 150 dpi image `page.png` and run:

```
python e6_make_sample.py
python e6_check_decode.py 0.7 0.5 0.35 0.2 0.12
```

The first command saves sample images with the marker (`sample_ink70.png` and so on); the second prints decoding results for 10 simulated photos per print strength.

### 3.4 How the content lookup works

```
python oprf_demo.py
```

Shows in a few lines how a lookup works in which the authority cannot see the user's input and the service cannot see the item text. It explains the principle and is not an RFC 9497 implementation. The experiments (E7 onwards) and the operation walkthrough use `rfc9497.py`, which follows RFC 9497 (3.13).

### 3.5 Does encryption change the decisions, and how long does it take

```
python e7_oprf_lookup.py
```

Regenerates, in the same order as E3, the same 60 test items, 360 automatically rewritten questions and 240 practice problems of the same types. The same rule (at least half of the question's 4-character pieces found in one item, and every number in the question present in that item) is applied in two ways:

- Control (plain matching): pieces compared as hashes, without encryption
- Encrypted lookup: pieces looked up at the authority while blinded, with OPRF(P-256, SHA-256) of RFC 9497 in base mode (`rfc9497.py`, 3.13)

All 600 queries get the same decision, the same matched item and the same match share under both. Detection of rewritten questions and the false refusal rate on practice problems (0%) are also the same as in E3. Decisions are the same on every run; timings depend on the machine. The implementation passes the official RFC 9497 test vectors, but it does everything except the elliptic-curve multiplication in Python and is slower than an optimized library (per question about 37 ms at the authority, about 174 ms in total at the service).

### 3.6 A larger registry (E8)

```
python e8_registry_scale.py
```

When many schools register exams on the same day, as in midterm weeks, the registry holds tens of thousands of items. The registry was grown from 60 to 600, 6,000 and 60,000 items and the same 600 queries of 3.5 were judged again. All added items come from the same 12 templates as the practice problems, so the registry fills with items similar to what students practise: the least favourable case. At 60 items the decisions were first checked to be identical to the plain matching of 3.5 on all 600 queries.

| Registered items | Rewritten questions detected | Practice refused (E7 rule) | Practice refused (revised rule) |
|---|---|---|---|
| 60 | 99.4% | 0/240 | 0/240 |
| 600 | 99.4% | 0/240 | 0/240 |
| 6,000 | 99.4% | 1/240 | 0/240 |
| 60,000 | 99.4% | 1/240 | 0/240 |

The E7 rule checks each distinct number in the question once. A practice problem in which the same number appears twice ("first term 68, ratio 68") was therefore matched to another registered item containing 68 only once. With the revised rule, a repeated number must appear the same number of times in the registered item; there were then no false refusals up to 60,000 items and detection was unchanged. The revised rule is recommended for operation and is used in the demonstration code (`demo.py`, `oprf_demo.py`, `operation_demo.py`); the demonstrations' decisions did not change. A variant that checks every item above the threshold instead of only the best-matching one was also compared and rejected, because it raised false refusals (3 to 5 at 60,000 items). The result file records the text of each refused practice problem and of the registered item it matched.

### 3.7 Korean items and items without numbers (E9)

```
python e9_korean_text_items.py
```

The items in 3.5 and 3.6 were all English word problems. And because the rule required the question's numbers to appear in the registered item, items without numbers, as in Korean language or social studies, could not be protected by the content lookup. This experiment registers 60 English word problems, 60 Korean word problems and 60 Korean multiple-choice text items without numbers (a stem, a passage of 4 to 6 sentences and choices ① to ⑤) together and compares three rules:

- E8 rule: the revised rule of 3.6 as it is
- Naive extension: a question without numbers is refused if at least half of its pieces match
- Proposed rule: when registering, the authority marks the pieces of the item's stem (the question line, such as "Which of the following best states the main idea?"). For a question without numbers (or with only choice numbers 1 to 5), the stem pieces are removed, and the question is refused only if at least 20 of the remaining pieces match one item and their share reaches a set level. ① and 1) are treated as the same character. A question with any other number is judged by the E8 rule.

The share for text questions was chosen on one set of items (the lowest value with no practice problem refused: 0.6), then fixed and tested on newly generated items. The table shows the new items. Practice problems were made from the same stems, the same vocabulary and the same 30 sentence frames as the registered items.

| Item type | Question | E8 rule | Naive extension | Proposed rule |
|---|---|---|---|---|
| Korean text items | 480 rewritten questions refused | 0% | 100% | 100% |
| | Practice problems refused | 0/240 | 0/240 (2/240 on the selection set) | 0/240 |
| | Stem typed alone, refused | 0/10 | 10/10 | 0/10 |
| Korean word problems | 300 rewritten questions refused | 100% | 100% | 99.7% |
| | Practice problems refused | 0/240 | 0/240 | 0/240 |
| English word problems | 360 rewritten questions refused | 99.4% | 100% | 99.4% |
| | Practice problems refused | 0/240 | 0/240 | 0/240 |

Rewrites of text items include reordered sentences, partial copies, synonyms, choice marks typed as 1), choices left out, and the passage alone. The naive extension refuses a stem such as "Which of the following best states the topic of the passage?" typed on its own, so it cannot be used; the proposed rule removes the stem pieces and does not. The 3 questions the proposed rule let through are short quotes such as "+ 3, find the value of f(2).", with fewer than 20 pieces and only numbers of 5 or less. With only the 60 English items registered, the E8 rule was first checked to give the same result as 3.6 at 60 items.

The proposed rule uses only set operations on piece values, so it can run on encrypted piece values as well. Every 5th question, 386 in all, was judged again with the encrypted lookup of 3.5, and every decision was the same.

Questions with the same passage but a different stem and different choices were refused in 59 of 60 cases. The passage itself is exam content, so during the exam other questions quoting the same passage are refused too.

Later, E14 (3.12) tested more questions that quote part of a practice problem and found that the proposed rule refused 76 to 102 of every 1,000 such study questions. Rule R3 therefore replaces the fixed minimum of 20 pieces for questions without numbers with "60% of the matched item's own pieces, at most 60". On the new items of the table above R3 gave the same values as the proposed rule (rewritten questions, practice problems, stems, same passage 59/60); the result file records an R3 column as well. The rule adopted now is R5, which closes a gap in R3 (3.18); the values of the table above are the same under R5.

### 3.8 Reading errors in photos (E10)

```
python e10_reading_errors.py
```

When a service receives a photo it first reads the text and then looks it up. To see what reading errors do, copies of the registered items of 3.7 had characters replaced, dropped or doubled at a set rate and were judged with the proposed rule (3 copies per item, 720 practice problems once each).

| Character error rate | English word problems refused | Korean word problems refused | Korean text items refused | Practice refused |
|---|---|---|---|---|
| 0% | 100% | 100% | 100% | 0/720 |
| 1% | 92.2% | 92.8% | 100% | 0/720 |
| 2% | 85.0% | 90.0% | 100% | 0/720 |
| 5% | 76.1% | 70.0% | 100% | 0/720 |
| 10% | 56.1% | 50.0% | 87.2% | 0/720 |
| 15% | 24.4% | 28.9% | 10.0% | 0/720 |
| 20% | 12.8% | 12.2% | 0% | 0/720 |

Text items were all refused up to a 5% error rate. A word problem fails the number check if a single digit is misread, so about 7% were missed even at 1%. Loosening the number check would refuse practice problems that differ only in their numbers (3.6), so the rule was not changed. This is why word problems arriving as photos need the exam page marker (3.1 to 3.3), which does not depend on reading the text. Errors only ever reduced refusals; no practice problem was refused. R3 and the adopted rule R5 gave the same results as the table at every error rate on the same damaged copies.

### 3.9 Guessing by an insider at an AI service (E11)

```
python e11_insider_guessing.py
```

A cooperating AI service receives the encrypted piece sets of the registered items and, as in every lookup, can have any piece encrypted by the authority's server. So someone inside the service could guess pieces, have them encrypted, and check whether they are in a set, possibly rebuilding the items before the exam. The attacker was made as strong as possible on purpose: an insider who knows the exact generator of the test items (sentence frames, names, stems, topics, nouns) and lacks only the values that were drawn. Real item writers do not publish their templates, so a real attacker is weaker. Targets: the 60 Korean word problems and 60 Korean text items of the new set in 3.7.

| Measure | Result |
|---|---|
| Number guesses (0 to 999, with repetitions, 3,000 in all) | Every number of all 120 items recovered |
| Word problems rebuilt completely | 60/60 |
| Stems, passage sentences and choices of text items recovered | 60/60 (all 651 sentences) |
| Distinct pieces guessed | 18,605, about 140 ordinary questions at 132.6 pieces each, about 0.1 CPU minutes at the authority |
| Checked directly on encrypted values | Same result as plain matching for all 2,100 guesses |

The guessing needed is only about 140 ordinary questions' worth, so in a service with many users it cannot be caught by rate limits or anomaly detection. The sets therefore must not be open before the exam. Distributing the sets a day ahead, locked with AES-256-GCM, and releasing the 32-byte key when the exam starts was tested as well: before the start 0 of 200 guesses matched, and after the key was released the sets opened to exactly the original values. The operation walkthrough (2.3) now works this way. While the exam is running an insider could still learn the items the same way, but by then every candidate already has the exam paper.

### 3.10 Questions split across messages (E12)

```
python e12_split_questions.py
```

A message with few pieces may fall below the threshold, so questions split into several messages were tested, with the 180 new items of 3.7 and the proposed rule unchanged.

- Verbatim split: the item cut into 2, 4 or 8 consecutive word chunks, sent one by one
- Numbers apart: numbers replaced by A, B, C, the text cut into 1, 2, 4 or 8 chunks, then "A=168, B=75, C=4" sent last

| Attack | Judged | English word | Korean word | Korean text |
|---|---|---|---|---|
| Verbatim split (2 to 8 parts) | each message | 100% | 100% | 100% |
| Numbers apart (text in 1 part) | each message | 92% | 58% | 100% |
| Numbers apart (text in 8 parts) | each message | 0% | 0% | 100% |
| Numbers apart (text in 8 parts) | whole conversation | 92% | 58% | 100% |
| Numbers apart (text in 1 to 8 parts) | whole conversation, values put back | 97% | 100% | 100% |

Verbatim chunks, however short, are exact copies of part of a registered item and were all refused. With the numbers sent apart, word problems mostly passed when each message was judged alone. Judging all messages of the conversation together during the exam, and putting values given as "A=168" back in place of the letter (a plain text substitution with no understanding of the problem), refused 97 to 100%. The 3% missed among English word problems are cases where the article "A" in the text collided with the placeholder letter. 600 conversations asking four practice problems of the same type in a row, and 600 mixing practice problems, stems and short follow-up questions, were not refused under any way of judging.

E14's rule (R3), and the final rule (R5) which contains it, ask for more pieces from questions without numbers, so it is weaker when each message is judged alone: a text item split verbatim into 8 parts is refused 0% per message and 57% over the last 2 messages. Judged over the whole conversation, every attack was refused 100% for all three kinds of item, and with values put back the 3% missed among English word problems disappeared as well (R2 97%, R3 100%). The 1,200 study conversations were not refused under R3 either. R3 should therefore be used with whole-conversation judgement.

### 3.11 Authority load and test vectors (E13)

```
python e13_load_and_vectors.py
python e13_load_and_vectors.py --check
```

The authority's only work per question is one elliptic-curve multiplication per piece (RFC 9497 BlindEvaluate). Pieces were processed on one CPU core of this machine in batches of 1, 70, 1,000 and 10,000. This repository's RFC 9497 implementation took about 513 to 541 microseconds per piece; the elliptic-curve multiplication inside it, timed alone, about 58 to 69 microseconds. Both hardly depend on the batch size. The difference is the point decompression and encoding done in Python. Batching does not lower the server cost, which is proportional to the number of pieces. At the median Korean question (132 pieces) one core serves about 15 questions per second with this implementation and about 123 at the cost of the multiplication alone. For an assumed 1,000 Korean questions per second this implementation would need about 68 cores, an optimized one about 9. On the service side, blinding and unblinding one Korean question took about 374 ms with this implementation.

Measured on one core (one thread) of an Intel Xeon 2.10 GHz CPU in a cloud virtual machine, with Python 3.13 and `cryptography` 50 (OpenSSL 4.0). The figures above are the first run (`results/E13-001_results.json`). A second run in the same environment (`results/E13-002_results.json`, which records the environment) gave 529 to 551 microseconds per piece, 57 to 68 for the multiplication alone, and 70 and 8 cores. The figures move by a few percent from run to run and will differ on another CPU. Batched multiplication on a GPU or an FPGA, and scaling across several cores, were not measured.

So that a service can check its own implementation, RFC 9497 outputs under a test key derived with RFC 9497 DeriveKeyPair from a published seed (never used for a real exam) are in `results/E13-test_vectors.json`: the pieces and number tokens of 3 items (2 word problems, 1 text item), the encrypted value of each piece, the stem pieces, and the pieces and final-rule (R5) decisions of 11 queries (item as printed, spaces removed, practice problem with different numbers, repeated number, text item as printed, stem alone, choice marks typed as 1), a word problem and a text item with "문제 23번" in front, an item with unrelated sentences in front, a practice problem with "문제 23번" in front). The R3 decision is recorded as well, so the queries on which the two rules differ can be seen. `--check` recomputes the values and confirms they are unchanged.

### 3.12 Why these piece lengths and thresholds (E14)

```
python e14_sensitivity.py
```

Up to E9 the values were: 4-character pieces, share 0.5 for word problems, and at least 20 pieces with share 0.6 for items without numbers. Only 0.6 was chosen on a separate set of items, and only against whole practice problems. E14 chooses every value the same way (on a selection set, then checked on new items) and shows what each value gains and costs. Two new kinds of question were added: a run of 10% to 100% of an item's words, and a run taken from a practice problem. When a run from a practice problem is word for word part of a registered item, no content rule can tell it from exam text, so those runs are counted separately. First, n = 4 with E9's values was checked to reproduce E9's results.

Piece length (E9's values unchanged, 180 new items)

| Piece length | Whole practice problems refused (text) | Parts of practice problems refused (text) | Text items refused at 5% reading errors | Text items refused from a 10% run |
|---|---|---|---|---|
| 2 | 19/240 | 746/1200 | 100% | 72% |
| 3 | 0/240 | 232/1200 | 100% | 73% |
| 4 | 0/240 | 82/1200 | 100% | 65% |
| 5 | 0/240 | 34/1200 | 99.4% | 53% |
| 6 | 0/240 | 19/1200 | 97.2% | 43% |

Two characters refuse whole practice problems and cannot be used. Longer pieces refuse fewer parts of practice problems but tolerate fewer reading errors and shorter quotes. Four is the longest length that refuses every text item at 5% reading errors. The number of pieces per question (median 51 to 64) hardly depends on the length, so the server cost is the same.

Share for word problems: from 0.0 to 0.5 the rewritten questions are refused at the same 98.5%; at 0.6 98.3%, at 0.7 93.2%, at 0.8 77.3%. 0.5 is the highest value that loses no detection. Word problems get no minimum piece count. A minimum would refuse fewer short parts of same-template practice problems that happen to share one number (about 9 per 1,000), but at 20 pieces the refusal of rewritten questions falls to 94.2% and of partial copies to 35.8%.

Thresholds for items without numbers (4 characters, text items, range over four sets of items)

| Minimum pieces, share | Parts of practice problems refused (per 1,000) | Partial copies refused | Refused at 10% reading errors | Same passage, other question refused (should be refused) | Numbers apart: whole conversation, values put back (English / Korean word problems) |
|---|---|---|---|---|---|
| 20, 0.6 (R2) | 76 to 102 | 100% | 85 to 88% | 53 to 59 of 60 | 97% / 100% |
| 40, 0.6 | 14 to 27 | 96 to 97% | 85 to 88% | 53 to 59 of 60 | 97% / 92% |
| 60, 0.6 | 0.8 to 6.3 | 76 to 78% | 85 to 88% | 53 to 59 of 60 | 80% / 92% |
| 60, 0.7 | 0 to 2.4 | 76 to 78% | 18 to 23% | 20 to 28 of 60 | 80% / 92% |
| 60% of the item's pieces, at most 60 (R3) | 0.8 to 8.6 | 76 to 78% | 85 to 88% | 53 to 59 of 60 | 100% / 100% |

No whole practice problem and no stem was refused at any of these values, and at least 98.6% of rewritten questions were refused. R2 refuses 76 to 102 of every 1,000 study questions that quote part of a practice problem, an over-refusal E9 did not test. A fixed floor of 60 pieces brings this down to 0.8 to 6.3 per 1,000, but word problems have fewer than 60 pieces, so questions with the numbers sent apart are missed (English 80%). Raising the share to 0.7 makes reading errors and same-passage questions much more harmful. So the floor was tied to the matched item itself: R3 refuses only when the question contains 60% of the matched item's pieces, at most 60. For long passages this equals the fixed 60; for short word problems it scales down with the item. R3 cuts the over-refusal to a tenth of R2's or less and keeps detection under reading errors, for same-passage questions and under whole-conversation judgement. What it gives up is short quotes of 20 to 60% of an item (text items 100% to 76 to 78%) and per-message detection (3.10).

The order in which values were chosen: the fixed candidates were looked at on the selection and validation sets, and the third set (seed 20261125) was used to confirm them. The form of R3 (60% of the item) was settled after looking at all three, so it was confirmed again on a fourth set opened only afterwards (seed 20261126). On that set R3 refused 4.7 of every 1,000 quoted parts of practice problems (R2: 101.6), and the other values stayed within the ranges above.

### 3.13 Conformance to international standards

```
sh check_standards.sh
```

The two core mechanisms of the registry now stand on published standards, so that AI services, device makers and other countries can build their own implementations from the standards rather than from this repository's code.

| Mechanism | Standard followed | How it was checked | Result |
|---|---|---|---|
| Encrypted lookup | RFC 9497 OPRF(P-256, SHA-256), base mode; RFC 9380 hash_to_curve P256_XMD:SHA-256_SSWU_RO_ | Official test vectors from the CFRG repositories | hash_to_curve 5/5, key derivation (DeriveKeyPair) matches, OPRF 2/2 (blinded element, server output and final output all match) |
| Public log | RFC 9162 (Certificate Transparency 2.0) section 2.1: Merkle tree, inclusion proofs, consistency proofs | Reference test data of transparency-dev/merkle | Root hashes 9/9; all 86 inclusion and 98 consistency cases decided as the reference implementation does (including the 172 that must be rejected) |
| Authority signatures, accreditation chain | RFC 8032 Ed25519 | `cryptography` package (OpenSSL) | unchanged |
| Locked distribution | NIST SP 800-38D AES-256-GCM | `cryptography` package (OpenSSL) | unchanged |
| Text normalisation | Unicode NFKC (UAX #15) | Python standard library | unchanged |

`check_standards.sh` fetches the three public repositories at fixed commits and reruns these checks (needs an internet connection). Its output is in `results/STD-001_standards_check.txt`.

What changed with the Merkle tree log: with the earlier hash chain, checking one record, or checking that the log had not been rewritten, meant downloading and rehashing the whole log. Now the operator publishes a log head signed over the record count and the Merkle root; a device maker checks that each exam is in the log with an inclusion proof of at most 5 hashes; and anyone can check with a consistency proof of a few hashes that today's log extends yesterday's published log without changing it. The operation walkthrough (2.3) includes these checks and a step in which the operator is assumed to have changed one past record: the consistency proof fails and the change is caught (57 steps).

After moving the encrypted lookup to RFC 9497, plain matching and encrypted lookup still gave the same decisions on all 600 queries of E7, 386 of E9 and 2,100 of E11, because the matching rule only uses set operations on piece values and does not depend on the cryptography.

### 3.14 Comparison with simpler methods, and cheap ways around (E16)

```
python e16_baselines.py
```

Five methods were compared on the same items and the same questions: an exact hash (SHA-256 of the normalised text), a keyword list (words found in at most 5% of the registered items), vector similarity (TF-IDF cosine over 4-character pieces, with the number test), reduced vectors (those vectors reduced to 64 dimensions), and the registry's rule R3. The thresholds of the other methods were chosen on the selection set only (keywords 0.95, vector + numbers 0.85, reduced vector 0.99). The figures below are from the confirm set (180 items), which was never used to choose a value. The reduced vectors stand in for a sentence-embedding model. No neural embedding model could be installed where this ran, so a neural embedding was not measured.

This experiment exposed a gap in R3. If the item is pasted word for word with "Question 23:" in front, R3 refuses none of them. A question containing a number other than 1 to 5 is judged on the numbers path, and that path requires every number of the question to be in the item. Adding unrelated sentences to lower the share also works.

Questions that must be refused (confirm set, one per item)

| Question | Exact hash | Keywords | Vector + numbers | Reduced vector | R3 | R5 (E16 value 70%) |
|---|---|---|---|---|---|---|
| E9's rewrites and E14's short copies | 16.7% | 33.1% | 40.4% | 43.2% | 90% | 90% |
| "Question 23:" put in front of the item | 0% | 100% | 0% | 100% | 0% | 100% |
| unrelated sentences in front, as long as the item | 0% | 100% | 99.4% | 81.1% | 11.1% | 100% |
| unrelated sentences in front, 3 times the item | 0% | 100% | 71.1% | 64.4% | 0% | 100% |
| an unrelated sentence after every sentence | 0% | 100% | 99.4% | 78.9% | 24.4% | 100% |
| the item among 16 practice problems | 0% | 60.6% | 0% | 0% | 0% | 100% |
| "rewrite this in other words" + the item | 0% | 100% | 100% | 81.7% | 97.2% | 100% |
| a filler word after every 2 words | 0% | 100% | 69.4% | 71.7% | 2.8% | 5% |
| every sentence reworded | 0% | 0% | 0% | 0.6% | 2.8% | 2.8% |
| translated (word problems) | 0% | 0% | 0% | 0% | 0% | 0% |

Questions that must not be refused (counts)

| Question | Exact hash | Keywords | Vector + numbers | Reduced vector | R3 | R5 (E16 value 70%) | Of |
|---|---|---|---|---|---|---|---|
| Whole practice problems | 0 | 2 | 0 | 349 | 0 | 0 | 720 |
| Parts of practice problems | 0 | 0 | 0 | 692 | 17 | 17 | 3119 |
| Reworded practice problems | 0 | 0 | 0 | 20 | 0 | 0 | 720 |
| Conversations of 4 practice problems | 0 | 7 | 0 | 0 | 0 | 0 | 200 |
| Conversations of 16 practice problems | 0 | 63 | 0 | 0 | 0 | 1 | 100 |

How to read this:

- The exact hash only catches differences in spacing and punctuation. The keyword list resists padding but catches a third of the earlier rewrites and wrongly refuses more than half of the 16-problem conversations. The reduced vectors cannot tell a practice problem of the same type from a registered item (349 of 720 whole practice problems refused).
- What a service holds before the exam also differs. With a list of hashes anyone can test a guessed text without asking the authority. The keyword list shows 45.8% of an item's words in clear. A vector method needs every piece of every item in clear to compute query vectors. The registry distributes ciphertext only until the exam starts (E11).
- R5 in the tables uses the values E16 chose with 300 practice conversations on the selection set (70% of the item's pieces, run 1.5x). It closed the five ways around, but conversations of 16 practice problems, none of which were refused on the selection set, were wrongly refused 2, 3 and 1 times in 100 on the other three sets. The values were therefore chosen again in E19 (3.18); the adopted value is 90%. R5 is defined in 3.18.
- R5 in E16 first tried only the three best-matching items. E18 showed that an item hidden among practice problems was then missed, so every item that can meet the condition is now tried. The other three sets had already been looked at before this change.
- A filler word after every two words is caught by the keyword and vector methods but gets past R3 and R5 almost always (only 53.3% of the item's pieces remain in the question). Full rewording or translation gets past every method, because only 16.6% and 4.7% of the item's pieces remain in the question. To have an AI do the rewording the user must send the original item, and that request is refused 97.2% of the time by R3 and 100% by R5. The time it takes to reword by hand was not measured.

### 3.15 What the lookup server can learn from request sizes (E15)

```
python e15_lookup_metadata.py
```

The encrypted lookup hides the pieces of a question from the lookup server, but the server sees how many elements arrive per question, when, and from which service. Assuming the server knows every registered item and the rewriting methods and has already seen half of the questions with their answers, we measured what the element count alone gives away (confirm set, 2,040 exam questions, 4,559 ordinary questions).

| Arm | Names the item (chance 0.6%) | Tells exam questions from others (0.5 = cannot) | Server load |
|---|---|---|---|
| Sent as is | 10.7% | 0.5396 | x1 |
| Padded to multiples of 32 | 1.6% | 0.5415 | x1.218 |
| Padded to multiples of 64 | 1.4% | 0.5367 | x1.468 |
| Padded to multiples of 128 | 1.3% | 0.5225 | x2.031 |
| Always 512 | 0.8% | 0.501 | x6.722 |
| 4 questions in one request | 0.7% | 0.5171 | x1 |
| 16 questions in one request | 0.5% | 0.5098 | x1 |

Sent as is, the server names the item for about one exam question in ten. Sending four questions of different users as one request brings this down to chance at no extra load, at the price of waiting until four questions have arrived. The number of requests per service and their times are hidden by none of these; hiding them needs cover requests at a constant rate, whose cost was not measured. Practice problems here are as long as registered items because they share their frames, so the second column may differ on real conversations.

### 3.16 When the lookup server is down (E17)

```
python e17_outage.py
```

A service holds the piece values of the items in advance, but only the lookup server can compute the piece values of a question. When the server stops, new pieces cannot be judged. Marks printed on the paper do not use the lookup and are not affected. In a stream in which 30% of the questions are about a registered item, the 2,000 questions after the stop were judged in four ways (confirm set, rule R5).

| Questions before the stop | Pieces kept | Keep answering | Refuse all | Judge with kept piece values | Release the lookup key | Normal operation |
|---|---|---|---|---|---|---|
| 0 | 0 | 0% | 100% | 0% | 89.2% | 89.2% |
| 10 | 682 | 0% | 100% | 0% | 89.2% | 89.2% |
| 100 | 3,904 | 0% | 100% | 41.6% | 89% | 89% |
| 1,000 | 13,990 | 0% | 100% | 82.7% | 90.6% | 90.6% |
| 5,000 | 21,212 | 0% | 100% | 89.8% | 89.8% | 89.8% |

Values are the share of exam questions refused. "Refuse all" also refuses every ordinary question. Judging with kept values counts an unknown piece as not matching, so it does not refuse more ordinary questions (1 of 10,000 questions were refused that normal operation would not refuse). After the first 1,000 questions of an exam it keeps 91.3% of normal operation. The same store lowers the everyday load (after 5,000 questions 94.5% of the pieces were already known). If the server stops right at the start there is nothing kept and no effect.

"Release the lookup key" means the authority publishes that exam's lookup key through the log and the service computes the values itself. Decisions then equal normal operation, but until that exam ends an insider can test guesses without asking anyone (the protection of E11 is given up). It needs a separate lookup key per exam. Which default to use is a matter for the operating design.

### 3.17 Can someone make another person's question be refused (E18)

```
python e18_refusal_abuse.py
```

During an exam the whole conversation is judged, so exam text in a shared document or in the instructions of an app can make an ordinary question in the same conversation be refused. Only someone who holds the item during the exam can do this, and the refusal ends with the exam. Part of a registered item was planted in front of a victim's conversation (4 practice problems and a follow-up question), for all 180 items. R5 uses the values of E19.

| Planted | R2 | R3 | R5 |
|---|---|---|---|
| nothing | 0/180 | 0/180 | 0/180 |
| 20% | 0/180 | 0/180 | 0/180 |
| 40% | 0/180 | 0/180 | 0/180 |
| 60% | 0/180 | 0/180 | 3/180 |
| 80% | 0/180 | 0/180 | 22/180 |
| 100% | 0/180 | 0/180 | 180/180 |

With the whole item planted as the first message and ordinary messages after it, R3 still refuses 5/180 conversations after one message and 0/180 after two; R5 still refuses 180/180 after eight. Planting only the 10 stems: 0/60 for all three rules.

These are two sides of one property. R3 looks at the share of the question that matches, so it stops refusing once other text is mixed in. That makes it robust against this abuse and open to padding (3.14). R5 looks at how much of the item is present, so it closes padding and keeps refusing a conversation that holds most of an item until the exam ends: 22/180 with 80% of an item planted, all with the whole item. Someone who holds an item during the exam and puts it into a shared document or the instructions of an app thereby stops the users of that conversation from getting answers until the exam ends. R5 in the table uses the values of E19 (90%).

### 3.18 Adoption of rule R5 and its values (E19)

```
python e19_adopt_r5.py
```

To close the gap found in E16 the decision rule was changed to R5. R5 refuses every question R3 refuses and adds three things.

- (a) A question with numbers whose best-matching item has no numbers is judged as text. An item with numbers always goes through the number test.
- (b) The number test passes if the question's numbers are all in the item, or the item's numbers are all in the question.
- (c) Sentences that do not look like the item (fewer than half of their pieces are in it) are dropped. If a run of the remaining sentences is at most 1.5 times as long as the item and holds at least 90% of the item's pieces, the question is refused. For an item with numbers the run must contain all its numbers.

E16 chose the two values with 300 practice conversations (70%) and then wrongly refused 1 to 3 of 100 conversations of 16 practice problems on the other sets. Those sets had been seen and could not be used to choose again. So 600 conversations of 16 and 300 conversations of 32 practice problems were added to the selection set, the values were chosen again there, and they were checked once on a new set (seed 20261130) that no experiment had used. The selection rule was fixed before the new set was looked at: among the values that refuse no practice problem, stem or practice conversation and are within 0.5 percentage points of the most must-refuse questions refused, the shortest run and the middle share.

Selection set (run 1.5x)

| Share of the item's pieces | 60% | 65% | 70% | 75% | 80% | 85% | 90% | 95% |
|---|---|---|---|---|---|---|---|---|
| Wrongly refused (of 1,930: 720 practice problems, 10 stems, 1,200 practice conversations) | 353 | 233 | 32 | 1 | 0 | 0 | 0 | 0 |
| Must-refuse questions refused | 77.3% | 77.3% | 77.3% | 77.2% | 77.2% | 77.2% | 77.2% | 77.2% |

0.8 to 0.95 meet the condition and the middle, 90%, was taken. E16's 0.7 wrongly refused 32 once there were more conversations.

Check on the new set (180 items, values fixed)

| Must be refused | R3 | R5 |
|---|---|---|
| "Question 23:" in front of the item | 0% | 100% |
| unrelated sentences, as long as the item | 10% | 100% |
| unrelated sentences, 3 times the item | 0% | 100% |
| an unrelated sentence after every sentence | 23.3% | 100% |
| the item among 16 practice problems | 0% | 100% |
| "rewrite this in other words" + the item | 97.2% | 100% |
| 60% of the words | 97.2% | 97.2% |
| 20 to 60% of the words | 77.3% | 77.3% |
| a filler word after every 2 words | 5% | 5% |
| every sentence reworded | 2.8% | 2.8% |
| translated (word problems) | 0% | 0% |

| Must not be refused (counts) | R3 | R5 | Of |
|---|---|---|---|
| whole practice problems | 0 | 0 | 720 |
| parts of practice problems | 18 | 18 | 3117 |
| reworded practice problems | 0 | 0 | 720 |
| conversations of 4 practice problems | 0 | 0 | 200 |
| conversations of 16 | 0 | 0 | 100 |
| conversations of 16 (more) | 0 | 0 | 300 |
| conversations of 32 | 0 | 1 | 100 |

All five padding-type ways around are refused at 100%. What R3 refused and the practice problems it did not refuse are unchanged; the added wrong refusals are 1 of 100 conversations of 32 practice problems. These practice problems share their sentence frames with the registered items, which is harder than real use. Filler words, full rewording and translation still get past R5.

The result files of E9, E10 and E12 have an R5 column with the same values as R3 (E9 rewritten questions and practice problems, E10 reading errors, E12 whole-conversation judging 100%/100%/100%, study conversations refused 0/1200). The test vectors (E13) now carry R5 decisions and include questions with an added number and with added sentences, 11 in all. The test key and the piece values are unchanged.

The rule was corrected twice during this work; the values were not touched. First, the pre-filter of items in (c) did not allow for the pieces that appear when a dropped sentence lets its neighbours join, so 27 of 9,590 decisions on the new set differed. Second, a practice problem with numbers followed by a stem was judged as text against an item with numbers, without the number test, which wrongly refused 2 of 600 mixed conversations in E12. Both corrections were made after the new set had been looked at once.

## 4. Reading the results

- All results are simulations. Measurements with real cameras and real printed pages are tasks for the pilot stage.
- The final decoder (partial decoding with upscaling and sharpening) was improved after inspecting the results of 3.2. The pre-improvement result (33 photos) is published as well.
- On the test page the marker was decoded even at low print strength, but on a real exam page dense with text and figures the lowest decodable strength is currently 50%. The goal is a strength barely visible to the eye (`figures/sample_target_faint.png`), which needs further research.
- The accuracy of the content lookup was evaluated only on test items made for the experiments. The "rewritten questions" of E3 and 3.5 apply automatic changes to spacing, number formatting, sentence order, partial excerpts and word substitution. Questions completely reworded by hand are detected only to a limited extent.
- The E8 items are test items built from 12 English sentence templates. They should be checked again on real exam items and real study questions. The matching time in E8 (about 40 ms per question at 60,000 items) was measured with a simple implementation and grows with the number of registered items.
- The rule for items without numbers was verified in the experiment code. In the demonstrations, step [4] of `demo.py` shows the adopted rule R5 on one word problem; step [3] of `demo.py` and `operation_demo.py` keep the first rule, with items that all contain numbers. The text items are test items built from sentence frames and should be checked again on real passages and real study questions. The share of 0.6 was chosen on these test items. The minimum of 20 pieces made no difference for E9's questions, but it mattered a lot for questions that quote part of a practice problem (3.12).
- Under E9, a quote of 20 or more pieces that matches a registered item exactly is refused even without its numbers; a practice problem with the same sentence frame typed without its numbers is one such case. A question with the same meaning in entirely different words cannot be caught by piece matching.
- The reading errors of E10 come from a simple model in which each character fails independently. The error rate and error patterns of real services reading photos were not measured.
- The locked sets of E11 prevent leaks before the exam starts but not guessing by an insider during the exam. How the key is delivered reliably at the start (for example published in the log under a signature) is left to the operational design. The guessing cost for a realistic attacker who does not know the item templates was not measured.
- The value restoration of E12 handles only the "A=168" form. Numbers written in Korean words, or values described in words such as "the first value is 168", remain a limit, like synonyms. Judging the whole conversation requires the service to hold the conversation briefly during the exam.
- In E14 the practice passages were built from the same sentence frames as the registered items, so the refusal rate for parts of practice problems may be higher than in real use. It should be measured again on real textbooks and real exam passages. R3 is recorded in the result files of E9, E10 and E12.
- The throughput of E13 is that of this repository's Python implementation, and of the elliptic-curve multiplication (OpenSSL) inside it timed alone. The throughput of an optimized RFC 9497 library was not measured. During exam windows every text question sent to a cooperating service is subject to lookup, so actual question volumes in weeks crowded with school exams should be checked together with the services. Whether to answer or refuse when the authority's server is down must also be decided in the operational design.
- E16 found a gap in the rule used until then (R3), and the rule was changed to R5 (3.14, 3.18). The specification, the test vectors and step [4] of `demo.py` use R5; step [3] of `demo.py` and `operation_demo.py` still use the E7 rule, with items that all contain numbers. R5 wrongly refused 1 of 100 conversations of 32 practice problems, and it keeps refusing a conversation that holds most of an item until the exam ends (3.17). A filler word after every two words, full rewording and translation still get past R5. Breaking both sides of the number test at once, by leaving one number out and adding another, was not measured.- The "fully reworded" questions of E16 come from hand-written paraphrase templates; rewording by an AI was not measured. The reduced vectors are not a neural sentence embedding. How many reworded questions a neural embedding catches, and how many practice problems it wrongly refuses, was not measured.
- E15 assumes an observer who sees the element count only. An observer who also uses the gaps between requests, or several requests of one user, was not measured. The stream of E17 (30% exam questions, every item equally often) is an assumption.
- The timing of the encrypted lookup was measured on this repository's implementation with one CPU. Throughput at operating scale has to be measured after the shared lookup server is built. Conformance (3.13) was checked with official test vectors and reference test data; no third-party audit or interoperability test has been done.
- The commercial AI test covers one model (GPT-Astra) and 36 photos. The exact text of the first-round prompt was not kept (`results/E5-003_prompts.md`). It should be checked again when the model changes.
- With very different library versions, image processing results may differ in a few trials. The tested versions are listed in `requirements.txt`.
- A local AI set up by the user, services that do not cooperate, and solving by another person cannot be stopped by this proposal; they remain the job of existing enforcement and invigilation.

## 5. Repository layout

| Path | Contents |
|---|---|
| `code/demo.py` | One-minute demo: registration, marker, content lookup, adopted rule R5 (`--en` for English output) |
| `code/operation_demo.py` | Operation walkthrough by role (Korean output) |
| `code/summarize_results.py` | Prints every number quoted in the documents (`--en` for English output) |
| `code/e1_sim.py`, `e1_merge.py`, `e1_plot.py` | Marker printing, capture and decoding simulation |
| `code/e2_protocol.py` | Exam registration, signatures, refusal by time window |
| `code/e3_registry.py` | Piece matching with number check |
| `code/oprf_demo.py` | Principle of the blinded content lookup |
| `code/e7_oprf_lookup.py` | Encrypted lookup vs plain matching, timing |
| `code/e8_registry_scale.py` | Detection and false refusals as the registry grows |
| `code/e9_korean_text_items.py` | Rules for Korean items and items without numbers |
| `code/e10_reading_errors.py` | Decisions under reading errors |
| `code/e11_insider_guessing.py` | Insider guessing and locked distribution |
| `code/e12_split_questions.py` | Split questions and judging whole conversations |
| `code/e13_load_and_vectors.py` | Authority load, making and checking test vectors |
| `code/e14_sensitivity.py` | Why these piece lengths and thresholds, and what each value costs |
| `code/e15_lookup_metadata.py` | What the lookup server can learn from request sizes, and the cost of hiding it |
| `code/e16_baselines.py` | Comparison with exact hash, keywords and vectors; cheap ways around; first design of R5 |
| `code/e17_outage.py` | What still works when the lookup server is down |
| `code/e18_refusal_abuse.py` | Planting exam text to make another person's question be refused |
| `code/e19_adopt_r5.py` | R5's values chosen again and checked on new items |
| `code/rfc9497.py` | RFC 9497 OPRF(P-256, SHA-256) and RFC 9380 hash_to_curve, with the official vector check |
| `code/transparency_log.py` | RFC 9162 Merkle tree log (inclusion and consistency proofs), with the reference data check |
| `code/check_standards.sh` | Fetches the official vectors and reference data at fixed commits and checks both modules |
| `code/e5_legibility.py`, `e5_enh.py`, `e5_collect.py`, `e5_fp.py`, `e5_fp2.py` | Text reading vs marker decoding, final decoder, false matches on ordinary documents |
| `code/e5_stage2.py`, `e5_stage2_score.py` | Photos for the commercial AI test and scoring |
| `code/e6_make_sample.py`, `e6_check_decode.py` | Real exam page |
| `results/` | Raw results (E1 to E19 are experiment numbers; E4 was never used) |
| `figures/` | Result figures, sample test pages |
| `docs/` | Policy proposal and specification (Korean), operation walkthrough (Korean and English) |

## 6. Not included

- Original exam papers and sample images made from them (copyright)

## 7. License

Apache License 2.0
