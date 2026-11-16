# Operation walkthrough (English translation)

This is an English translation of one run of `code/operation_demo.py`. The Korean original of the same run is [`운영과정_시연.md`](운영과정_시연.md). The script itself prints Korean.

Mock exam: June mock exam of the 2027 academic year, period 1, exam ID 5A17C0DE, exam window 06-03 08:40 to 06-03 10:00. Every party acts only on the information it actually holds. Every decision below was computed by the script, not written by hand. The photos are simulated, and the security pattern was printed at the strong ink level used in the experiments (70%); the target appearance is much fainter. Keys are generated anew on every run, so commitments, set digests and Merkle roots change from run to run. Decisions do not.

Terms used below
- KICE: Korea Institute for Curriculum and Evaluation, which sets the national college entrance exam (CSAT) and its mock exams.
- Log: the national exam registry, a public append-only log.
- Log head: the number of entries and the Merkle root of the log (RFC 9162), signed by the registry operator. An inclusion proof shows that one entry is in the log; a consistency proof shows that an earlier log is a prefix of a later one. Each takes only a few hashes.
- Pieces: 4-character pieces of an exam item, encrypted with the authority's lookup key (oblivious PRF).
- Locked set: the encrypted pieces of one exam, sealed with AES-256-GCM; the key is released when the exam starts (E11).

## Timeline

| Time | Party | Action | Saw | Did not see | Result |
|---|---|---|---|---|---|
| **1. Preparation** | | | | | |
| 04-04 10:00 | Ministry of Education | Designates the body that will run the national registry and the shared lookup server | Operator's public key | Operator's private key | Designation issued (signed by the Ministry). The operator keeps the log, signs the log head (Merkle root) and runs the shared lookup server for schools |
| 04-04 11:00 | Ministry of Education | Accredits KICE as a registering authority | KICE's public key | Items, exam papers, KICE's private key | Accreditation issued: exam types CSAT and mock exam, valid until the end of the year |
| 04-04 12:00 | Ministry of Education | Delegates school accreditation to the Seoul Metropolitan Office of Education | Office's public key | | Delegated accreditation issued: school exams only, may accredit others below it |
| 04-19 10:00 | Seoul Metropolitan Office of Education | Accredits teacher keys of 29 schools in its region | Each school's public key | School items | Accreditations issued: school exams only. Chained to the Ministry's delegation, so verifiable up to the Ministry |
| 05-04 10:00 | Ministry of Education, AI service | Signs an agreement with an AI service | Service name and contact | The service's user data | Terms: apply the check during registered exam windows, report refusal counts per exam, accept compliance tests. The marker decoder and lookup tools are provided as open software |
| 05-04 11:00 | Ministry of Education, device makers | Signs an agreement with glasses and phone makers | | | Terms: on-device AI carries the list of exam IDs and windows and a marker decoder. The list is distributed under the maker's signature |
| **2. Compliance test** | | | | | |
| 05-20 10:00 | Exam authority (KICE) | Registers a 30-minute test exam | Test item (unrelated to any real exam) | | Registered (log entry 1) |
| 05-20 10:10 | AI service | Syncs the log and the locked set | | | Merkle root recomputed from the whole log (1 entry) matches the signed root, 1 entry re-verified independently, 1 locked set stored (keys released at each exam's start) |
| 05-20 14:00 | Exam authority (KICE) | Releases the set key at the start of the test exam | | | 32-byte key released. AI service: 1 set opened, matches the digest in the log |
| 05-20 14:10 | AI service | KICE tester sends a photo of the test exam page | Photo or text sent by the tester | Test item text | Exam ID 7E57C0DE read from the security pattern (6/6 chunks), exam in progress -> refused |
| 05-20 14:12 | AI service | KICE tester types the test item | Photo or text sent by the tester | Test item text | Encrypted lookup match (100% of pieces, numbers match) -> refused |
| 05-20 14:31 | AI service | Same photo after the test window ends | Photo or text sent by the tester | Test item text | No registered exam in progress -> normal answer |
| 05-20 15:00 | Exam authority (KICE) | Records the compliance result | | | Photo and text refused during the window, normal answer after it. Added to the list of services that passed |
| **3. Exam preparation** | | | | | |
| 05-27 10:00 | Exam authority (KICE) | Freezes 9 items of period 1 | Item text (kept inside the authority) | | Secret string for the item commitment generated (published after the exam) |
| 05-27 10:10 | Exam authority (KICE) | Checks candidate exam ID 5A17C0DE against the public log | Existing exam IDs in the log | | ID not in use |
| 05-27 10:30 | Exam authority (KICE) | Encrypts the 4-character pieces of the items with its lookup key | Item text, lookup key | | 241 encrypted piece values, set digest 668d73dc19d7… |
| 05-29 10:00 | Printer | Prints the items with the security pattern carrying exam ID 5A17C0DE | Items and exam ID (printers see items today as well) | Lookup key, signing key | Exam papers printed |
| 05-30 10:00 | Exam authority (KICE) | Photographs a printed sample and checks it with the public decoder | Sample photo | | Exam ID 5A17C0DE read from a photo of 25% of the page height (6/6 chunks), check passed |
| **4. Registration and distribution** | | | | | |
| 06-02 10:00 | Exam authority (KICE) | Signs and submits exam ID, type, window, item commitment, set digest and lookup server address | | | Registered (log entry 2) |
| 06-02 10:00 | National registry | Checks the accreditation chain, signature, duplicate ID and time rules, then appends to the public log | Exam ID 5A17C0DE, mock exam, 06-03 08:40 to 06-03 10:00, commitment a6bae3e44f6c… | Item text, the key that made the piece values | Registered (log entry 2) |
| 06-02 10:01 | National registry | An unaccredited group tries to register with KICE's accreditation | | | Rejected: accreditation does not match the signing key |
| 06-02 10:02 | National registry | A school teacher tries to register a CSAT-type exam | | | Rejected: exam type (CSAT) outside the accredited scope (school exams) |
| 06-02 10:03 | National registry | Registration with an exam ID already in the log | | | Rejected: exam ID already registered |
| 06-02 10:04 | National registry | A record whose end time was moved 6 hours later in transit, after signing | | | Rejected: signature does not match the record (changed in transit) |
| 06-02 10:05 | National registry | A 30-hour block signed by an accredited authority itself | | | Rejected: window longer than 24 hours |
| 06-02 10:10 | 29 schools | Teachers blind the item pieces on a school computer, have them encrypted by the shared lookup server, and register final exams in the same time slot | Own school's items (kept inside the school) | Other schools' items, the shared server's key | 31 log entries (test exam included). The shared lookup server received only blinded values (174 requests) |
| 06-02 10:10 | Registry operator | Applies the key to school requests on the shared lookup server | Blinded values | School items | |
| 06-02 11:00 | Registry operator | Signs and publishes the log head (entry count and Merkle root, RFC 9162) | | | 31 entries, root e07ab5bde544…. A consistency proof of 5 hashes against the log head of the compliance test (1 entry) confirms that no earlier entry was changed |
| 06-02 11:30 | Exam authorities and schools | Distribute the encrypted piece sets to the AI service, locked | | | 30 locked sets. Each authority keeps the key until its exam starts. The digest of each set is in the registration record |
| 06-02 12:00 | AI service | Re-verifies the log independently and stores the locked sets | Exam IDs, types, windows, locked sets | Item text, piece values, lookup keys | Merkle root recomputed from the whole log (31 entries) matches the signed root, 31 entries re-verified, 30 locked sets stored (keys released at each exam's start) |
| 06-02 12:01 | Insider at the AI service | Tries to learn the items in advance by encrypting guessed pieces through the lookup server and comparing them with the sets | Encrypted values of the guesses, locked sets | Opened piece values | Even the 24 true pieces of a real item, guessed exactly, give 0 matches because there is nothing open to compare with. Had the sets been open, guessing alone could rebuild the items (E11) |
| 06-02 13:00 | Device maker | Checks the log head signature and an inclusion proof for each exam, extracts only exam IDs and windows, and pushes them to devices under its own signature | IDs and windows of 30 exams | Items, piece values, user photos | Inclusion proofs checked for 30/30 exams (at most 5 hashes each, without downloading the whole log). IDs and windows of 30 exams installed |
| 06-02 13:01 | Device | Receives a list with one exam slipped in | | | Maker signature does not match, installation refused |
| 06-02 18:00 | Anyone | Checks in the public log which exams will be blocked tomorrow | Whole public log | Items, user data | 30 exams tomorrow (1 mock exam, 29 school exams), longest block 80 minutes, every accreditation chain verified up to the Ministry |
| **5. Exam day** | | | | | |
| 06-03 08:20 | AI service | Before the exam starts, a photo of the exam page | Photo or text sent by the user (processed inside the service only) | Item text | No registered exam in progress -> normal answer |
| 06-03 08:40 | Exam authorities and schools | Release the set keys at the start of the exam | | | 30 keys (32 bytes each) released |
| 06-03 08:40 | AI service | Opens the sets with the keys and checks them against the digests in the log (case where one set was tampered with in distribution) | Opened piece values | Item text, lookup keys | 29 sets opened and match the log, 1 set that did not open or did not match discarded |
| 06-03 08:40 | AI service | Opens the sets with the keys and checks them against the digests in the log | Opened piece values | Item text, lookup keys | 30 sets opened and match the log |
| 06-03 09:05 | AI service | During the exam, a phone photo of part of the exam page | Photo or text sent by the user (processed inside the service only) | Item text | Exam ID 5A17C0DE read from the security pattern (6/6 chunks), exam in progress -> refused |
| 06-03 09:07 | AI service | During the exam, a photo of a textbook (not the exam) | Photo or text sent by the user (processed inside the service only) | Item text | Compared with the IDs of the 30 exams in progress, no security pattern -> normal answer |
| 06-03 09:10 | AI service | During the exam, an exam question typed as text | Photo or text sent by the user (processed inside the service only) | Item text | Encrypted lookup match (100% of pieces, numbers match) -> refused |
| 06-03 09:10 | KICE and shared lookup servers | Apply the key to the blinded pieces and return them | Blinded values (different random values for every question) | The user's question, who the user is | The decision is made by the AI service |
| 06-03 09:12 | AI service | During the exam, the same question with spacing and wording changed | Photo or text sent by the user (processed inside the service only) | Item text | Encrypted lookup match (91% of pieces, numbers match) -> refused |
| 06-03 09:12 | KICE and shared lookup servers | Apply the key to the blinded pieces and return them | Blinded values (different random values for every question) | The user's question, who the user is | The decision is made by the AI service |
| 06-03 09:14 | AI service | During the exam, a practice problem of the same type with different numbers | Photo or text sent by the user (processed inside the service only) | Item text | One query to each of 2 lookup servers, no match (best 35% of pieces) -> normal answer |
| 06-03 09:14 | KICE and shared lookup servers | Apply the key to the blinded pieces and return them | Blinded values (different random values for every question) | The user's question, who the user is | The decision is made by the AI service |
| 06-03 09:16 | AI service | During the exam, a study question unrelated to the exam | Photo or text sent by the user (processed inside the service only) | Item text | One query to each of 2 lookup servers, no match (best 0% of pieces) -> normal answer |
| 06-03 09:16 | KICE and shared lookup servers | Apply the key to the blinded pieces and return them | Blinded values (different random values for every question) | The user's question, who the user is | The decision is made by the AI service |
| 06-03 09:20 | On-device AI | During the exam, a photo of the exam page from a glasses camera (no internet) | Photo or text sent by the user (processed on the device only) | Item text, any text lookup | Exam ID 5A17C0DE read from the security pattern (6/6 chunks), exam in progress -> refused |
| 06-03 09:22 | On-device AI | During the exam, the question typed into the same device | Photo or text sent by the user (processed on the device only) | Item text, any text lookup | Text lookup impossible without internet -> normal answer (a limit of this proposal: on-device AI checks photos only) |
| 06-03 09:30 | National registry | After the exam has started, KICE tries to register another exam | | | Rejected: registration after the start (retroactive) |
| 06-03 10:01 | AI service | One minute after the exam ends, the same exam photo | Photo or text sent by the user (processed inside the service only) | Item text | No registered exam in progress -> normal answer |
| 06-03 10:02 | AI service | After the exam ends, the same question typed as text | Photo or text sent by the user (processed inside the service only) | Item text | No registered exam in progress -> normal answer |
| **6. After the exam** | | | | | |
| 06-03 12:00 | Exam authority (KICE) | Publishes the items and the secret string of the commitment | | | Published |
| 06-03 12:00 | Anyone (audit) | Compares the public log with the published items | Whole public log, published items | User questions | Log root matches, a consistency proof shows the log continues the log head published the day before, items match the commitment made before the exam, this exam was blocked only 06-03 08:40 to 06-03 10:00 |
| 06-03 12:00 | Anyone (audit) | Checks a log in which the operator is assumed to have changed one past entry (end time of the 3rd exam) | Changed log and its consistency proof, log head published the day before | User questions | The proof that it continues the day-before log head fails, so the change is caught |
| 06-03 12:00 | AI service | Reports refusal counts per exam to the Ministry (refusals by on-device AI are counted separately by the maker) | | Personal data (not stored) | Exam 5A17C0DE: 3 |

## What each party holds

| Party | Holds | Does not hold |
|---|---|---|
| Ministry of Education | Accreditation key, accreditation and designation records, refusal counts per exam | Items, exam papers, user input |
| Office of Education | Delegated accreditation key (school exams only) | School items, user input |
| Registry operator | Public log, log head signing key, shared lookup server key | Item text, user questions and identities |
| Exam authority | Its own item text, signing key, lookup key | User questions and identities, other authorities' items |
| Printer | Items and exam ID (as today) | Signing key, lookup key |
| AI service | Public log, locked encrypted piece values (opened at the exam start), user input (inside the service) | Item text, lookup keys, piece values before the exam |
| Device maker and device | List of exam IDs and windows | Items, piece values, user photos (they never leave the device) |
| Anyone | Public log, items published after the exam, refusal counts per exam | User questions and identities |
