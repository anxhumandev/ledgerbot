# LedgerBot prototype guide
### What every screen does, what it proves, and how it becomes TBO's production platform

**LedgerBot** turns TBO's multi-supplier chaos into one trustworthy shelf. The same hotel, room and tour arrive from many suppliers (direct contracts, bed banks, and the acquired BookaBed, Jumbonline and Classic Vacations stacks) under different names, codes and prices. LedgerBot matches them with a calibrated cascade (cheap candidate search → small learned model → LLM only for hard cases → human for the rest), **guarantees** the false-merge rate it promises, keeps the physical room separate from the commercial offer, learns supplier reliability from bookings, and ranks offers by expected booked margin.

The prototype runs on a realistic synthetic world (2,490 hotels in five cities, 8,426 supplier listings from five fictional suppliers, plus a new supplier, NovaBeds, with 802 listings). Everything is computed by real code; anything simulated is labelled on screen.

---

## 1. Getting around

| To… | Do |
|---|---|
| Start the app | From the `tessera` folder: `.venv\Scripts\python dev.py`, then open http://localhost:5174 |
| Move between the 10 scenes | `→` / `←`, the large arrows on the screen edges, or the bottom-right bar (Back · scene menu · Next) |
| Find any hotel | **Ctrl K** or `/`, or "Find a hotel" in the top bar. Works with any supplier's spelling ("jumeira beach htl" finds Jumeirah Beach Hotel) and opens its golden record |
| Understand a scene | **Method & research** (bottom bar) or `I`: the problem, the method, the research behind it, what is real, and the enterprise counterpart |
| See a scene's shortcuts | **Keys** (bottom bar) or `P` |
| Reset everything | **Reset** (bottom bar) or `R` |
| Record the video | add `?record=1` to the URL: hides on-screen controls and the idle cursor |

Colour language (TBO palette): **blue** = LedgerBot / primary, **orange** = money and the best offer, **green** = automatic and safe, **yellow** = sent to a human, **purple** = the LLM was involved, **red** = failure or sabotage.

---

## 2. Scene by scene

### 00 · Cold open: "Nine listings. One room."
- **You see:** nine supplier rows for one Atlantis The Palm room (five suppliers, different names, codes, prices) fold into one card with the best offer and "+15 alternatives".
- **It proves:** hotel matching, room matching and offer selection working together on real data.
- **Numbers:** Dubai has 865 supplier listings → 253 hotels; 4,063 supplier room names → 1,640 real rooms; 0 consistency violations.
- **Enterprise:** the golden-record store (hotel → room → offer) that the search path reads.

### 01 · The mess: the 20-second challenge
- **You see:** the same Dubai Marina search as today's raw supplier feed (61 rows) and as LedgerBot (12 hotel cards). Find the cheapest Deluxe King with breakfast and free cancellation against a timer.
- **It proves:** normalised board and cancellation codes (12 raw board strings → 2 meanings in this search), duplicates collapsed (48 hidden), and rates re-attached to the right room. Two raw rows here are attached to the wrong room, exactly as feeds do.
- **Analyst value:** an agent finds the answer in seconds instead of scanning duplicates.
- **Enterprise:** the de-duplicated shelf for the B2B portal and API buyers.

### 02 · Live onboarding: a new supplier mapped in under a minute
- **You see:** the Dubai supply graph (each dot a supplier listing, each tinted circle a real hotel). Press `O`: NovaBeds' 802 listings stream through the five-stage funnel; orange dots fly into their hotels.
- **The graph is interactive:** hover a dot for the hotel, supplier and listing name; scroll to zoom (names appear as you zoom in); drag to pan; search "Find a hotel on the map"; **click any hotel to open it in the Inspector**.
- **Numbers (recording build):** candidates cut the work by 99.3% and still catch 100% of true matches; 730 listings (91%) merged automatically, 71 new hotels created, 1 sent to review, 0 contradictions, about 50 seconds.
- **Method:** blocking by H3 location cells, BM25 names, MiniLM embeddings (FAISS) and photo hashes; a LightGBM matcher; certified routing; constrained clustering (one listing per supplier per hotel).
- **Enterprise:** streaming candidate and matcher services; a new feed only touches the hotels it overlaps.

### 03 · The Inspector: every merge has a reason
Four tabs:
- **Hotel:** golden record, a row per supplier with ✓/≠ against the golden values, the evidence waterfall for the weakest link in the cluster, learned supplier trust (truth discovery: DirectConnect 0.98 … RapidStay 0.76), photo de-duplication with hero pick. `N` shows the near-miss: Atlantis The Palm vs Atlantis The Royal kept apart (different addresses, sub-brand conflict).
- **Rooms:** physical room → offer slots → competing supplier offers, with the raw supplier names under each room. Board and cancellation never decide room identity.
- **Activities:** Burj Khalifa products and options (OCTO model): level 148 and levels 124/125 are different products; prime and non-prime are options.
- **Review queue (new):** the pairs LedgerBot refused to decide alone (101 at the default 1% risk budget), **most uncertain first**. Side-by-side fields with match/differs badges, LedgerBot's lean and where it sits between the thresholds, and the evidence for and against. Decide with **S** (same) / **D** (different) / **K** (skip) / **U** (undo). Progress and median seconds per decision are tracked; every decision is kept as a gold label for the next retrain.
- **Analyst value:** the analyst sees the same evidence the model used, so a review takes seconds, and their time goes only where the model is genuinely unsure.
- **Enterprise:** the ops review console with versioned mappings and rollback; decisions flow into training data (active learning).

### 04 · Break it: try to fool it
- **You see:** type any listing or use five presets. The real single-record pipeline animates: parsed → candidates (tagged by which search found them) → scored against the thresholds → decision.
- **Presets:** misspelled (merges), wrong pin 400 m off with no phone or address (**abstains to human review** and says why), sister property (stays with the right sister), Spanish room name "Habitación Doble Deluxe Vista Mar – AD" (parsed and matched; breakfast treated as an offer term), gibberish (new property).
- **It proves:** the system knows when it doesn't know.

### 05 · Error budget dial: you choose the risk, we guarantee it
- **You see:** a dial from 0.1% to 5% maximum false merges; automation, review volume, held-out error and an illustrative ops cost recompute live.
- **Numbers:** at 0.5% the held-out error is 0.34%; at 1%, 0.84%; at 5%, 3.41%. The guarantee held at every certifiable setting. Below about 0.5% the audit set is too small to certify, and LedgerBot refuses to auto-merge rather than pretend.
- **Method:** Learn-then-Test risk control with Clopper–Pearson bounds (δ = 0.05), risk counted per property pair.
- **Enterprise:** the risk-controlled decision service, recalibrated weekly per supplier.

### 06 · Supplier health: the shelf heals itself
- **You see:** five supplier reliability cards with 90% credible bands, a live booking ticker (simulated), and four hotel cards with their chosen supplier. `Shift+2` sabotages GlobalBeds (35% price jumps): its score falls only as bookings fail, and about 300 offers switch to more reliable suppliers automatically.
- **Method:** Beta posteriors per supplier; offers chosen by expected value = P(book) × P(confirm at quoted price) × margin − failure cost.
- **Enterprise:** the booking-outcome feedback loop feeding reliability on the search path.

### 07 · Ranking for agents: same search, two right answers
- **You see:** Riya (Delhi, refundable 4★ family stays) and Mark (US luxury advisor) get different top 6 lists with "why" chips. Layer margin/Platinum and reliability risk with a Kendall-τ guardrail.
- **Numbers:** correcting for position bias lifts ranking quality against the true relevance from NDCG@10 0.888 to 0.916 (simulated logs with a known truth).
- **Enterprise:** the ranker on the search path, retrained from logged outcomes.

### 08 · The Arena: LedgerBot vs an LLM-only pipeline
- **Benchmark:** same held-out pairs. LedgerBot's column is measured (hotel F1 0.91, room-and-offer F1 1.00, 0 contradictions, p95 0.3 ms per pair). The LLM-only column is a **simulated** profile with stated error-rate assumptions (F1 0.87 and 0.70, 19 contradictions) until a real baseline run (`make baseline`, needs an API key) replaces it.
- **Judges vs Machine:** phones scan a QR code and vote on hard pairs; "Learn from your votes" retrains and re-certifies the thresholds.

### 09 · Impact and architecture
- **Impact replay (simulated):** 50,000 searches through both shelves with the same agents and suppliers: +22.5% gross profit per search, failed bookings 91 → 42, wrong-room incidents 26 → 6, look-to-book 2.99% → 3.36%. The annualised figure is illustrative and its formula is on screen.
- **Architecture:** draws itself step by step (see section 4).

---

## 3. Built for analysts

| Pain today | What LedgerBot gives the analyst |
|---|---|
| Hunting for a hotel across supplier extranets and codes | **Ctrl K search** across every supplier's spelling, straight to the golden record |
| Not knowing why two listings were merged | **Evidence waterfall** for any merge or near-miss, in plain language ("Same phone number", "157 m apart", "Sub-brand conflict: Palm vs Royal") |
| Reviewing thousands of pairs, most of them easy | **Review queue** of only the genuinely uncertain pairs (about 0.05% of candidates at the default budget), most informative first, one keystroke per decision |
| Undo and audit | Undo in the queue; in production every mapping is versioned with one-click rollback |
| Trusting an AI number | **Guaranteed** error budget checked on unseen hotels, and every screen labels what is simulated |
| Learning how it works | **Method & research** drawer on every scene |

---

## 4. From prototype to enterprise solution

| Capability | In the prototype | In TBO's production platform |
|---|---|---|
| Ingest | JSON files for five suppliers + NovaBeds | Supplier pull/push (XML, JSON, OCTO) → a Kafka topic per supplier → schema registry |
| Normalise | Dictionaries for EN, ES and bed-bank codes; optional offline LLM teacher (`make teach`) | Same dictionaries plus a distilled tagger; the LLM teaches rules offline, rules run free online |
| Candidates | H3 cells, BM25, MiniLM + FAISS, photo pHash, in memory | OpenSearch (BM25), a vector index (HNSW), H3 keys and a pHash index as services |
| Matcher | LightGBM with monotone constraints, isotonic calibration | Same model exported to ONNX on CPU, under 2 ms per pair |
| Risk-controlled decisions | Learn-then-Test on a gold audit set; per-property risk | Per-supplier calibration, thresholds recertified weekly, drift monitors |
| LLM adjudicator | Batched, cached; offline in the recording, so hard cases go to review | Asynchronous and batched on the uncertain band only, **never on the search path** |
| Human review | Review queue tab with active-learning order | Ops console with queues per region/supplier, SLAs, and labels flowing into retraining |
| Golden records | In-memory clusters with supplier exclusivity and cannot-links | Postgres + graph tables, versioned mappings, one-click rollback |
| Rooms and offers | Room identity on physical attributes; offer slots by board, refundability, occupancy, nights | Same data model behind the B2B portal and the API (a clean de-duplicated feed is itself a product) |
| Offer selection | Expected value with Beta-posterior reliability | Offer selector on the search path, under 3 ms |
| Ranking | IPW LambdaRank per agent persona, Kendall-τ guardrail | Ranker retrained from logged searches and bookings; triggered A/B tests |
| Feedback loop | Simulated booking stream and sabotage | Real outcomes (confirmations, 409/price mismatch, timeouts, wrong-room complaints) → feature store → reliability + retraining |
| Search-path latency | Measured per pair in the benchmark | Design target: under 5 ms added per search (cache → offer selector → ranker) |
| Rollout | Shadow-style comparisons in the Arena and replay | 3-month shadow pilot beside today's mapping → triggered A/B (only searches where rankings differ) → ramp to every destination, sightseeing and API buyers |

---

## 5. What is real and what is simulated

- **Real computation:** the synthetic world and its noise, normalisation and parsing, candidate search, matcher, calibration, risk control and its held-out check, clustering, rooms and offers, activities, truth discovery, photo de-duplication, ranking (trained on simulated logs), the Break-It pipeline, the review queue and search.
- **Simulated, and labelled:** booking outcomes and sabotage (Scene 06), the 50,000-search replay (Scene 09), the LLM-only benchmark column (Scene 08), human review resolution inside the offline build.
- **Illustrative:** crore figures, always shown with their formula.
- **Offline by default:** without an API key, the LLM adjudicator is off and uncertain pairs go to review; the cost meter shows ₹0.00 LLM spend.

---

## 6. Research it rests on

- Entity resolution and blocking: Papadakis et al., *Blocking and Filtering Techniques for Entity Resolution*, ACM Computing Surveys, 2020.
- Risk control: Angelopoulos, Bates, Candès, Jordan & Lei, *Learn then Test*, 2021; Angelopoulos et al., *Conformal Risk Control*, ICLR 2024.
- Constrained clustering: Saeedi et al., ESWC 2018.
- Explanations: Lundberg et al., TreeSHAP, Nature Machine Intelligence, 2020.
- Truth discovery: Yin, Han & Yu, *TruthFinder*, KDD 2007.
- Active learning: Settles, *Active Learning Literature Survey*, 2009.
- Abstention: Geifman & El-Yaniv, *Selective Classification*, NeurIPS 2017.
- Supplier reliability: Russo et al., *A Tutorial on Thompson Sampling*, 2018.
- Ranking: Joachims, Swaminathan & Schnabel, *Unbiased Learning-to-Rank*, WSDM 2017; Burges, *From RankNet to LambdaRank to LambdaMART*, 2010.
- LLM entity matching and calibration: Peeters, Steiner & Bizer, EDBT 2025; Xiong et al., ICLR 2024.
- Choice behaviour: Iyengar & Lepper, 2000; Chernev, Böckenholt & Goodman, 2015; McFadden, 1978; Train, *Discrete Choice Methods*, 2009.
- Activities data model: OCTO (Open Connectivity for Tours, Activities and Attractions).

---

## 7. Questions judges may ask

- **Why not just use an LLM?** Cost and latency at TBO's search volume, no guaranteed error rate, contradictory groupings, and merging rate plans that must stay separate. We use it only on the small uncertain band, off the search path.
- **How can you guarantee an error rate?** Learn-then-Test certifies thresholds on a held-out gold audit set with 95% confidence, and every setting is re-checked on hotels the model never saw. Where the data can't support a guarantee, LedgerBot says so and sends pairs to people.
- **What happens when it's unsure?** It abstains, explains why, and puts the pair in the review queue, most informative first.
- **Does it replace TBO's mapping team or vendor?** No. It runs alongside them, removes the easy 99.9% of decisions, and turns their reviews into training data.
- **How fast is a new supplier live?** In the demo, 802 listings in about 50 seconds; in production a new feed only touches the hotels it overlaps.
- **Is the data real?** Synthetic, with realistic supplier noise; prices and policies are fictional. The pipeline is real.
