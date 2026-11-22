# LedgerBot technical guide
### How each capability works, where it lives in the app, the research behind it, and its production path

This complements the README (product and setup). Every capability below is computed by real code on synthetic data; simulated parts are labelled in the app.

---

## 1. Matching: one canonical record per property

**Where:** Inventory Catalog → record → *Supplier records* and *Matching evidence*; Clusters; Analytics → Matching quality.

- **Normalisation** (`pipeline/normalize.py`): Unicode folding, abbreviation expansion (EN, ES, bed-bank codes), brand extraction, E.164 phones, address tokens, and a room parser that separates room identity (class, bed, view, occupancy, accessibility) from rate terms (meal plan, refundability).
- **Candidate generation** (`pipeline/blocking.py`): union of H3 geo cells, BM25 on names, MiniLM embeddings with FAISS, and photo pHash. All pairs are never compared; candidate recall and work reduction are shown on the Clusters page.
- **Matcher** (`pipeline/matcher.py`): a LightGBM classifier with isotonic calibration. Per-pair feature contributions produce the evidence bars on every record and review case.
- **Clustering** (`pipeline/cluster.py`): constrained correlation clustering with one listing per supplier per property and cannot-links; bridge pruning. Consistency violations are reported, and are 0 in the build.
- **Truth discovery** (`pipeline/content.py`): learns how much to trust each supplier when choosing golden attributes; photo de-duplication by perceptual hash with hero selection.

Research: entity resolution with blocking and learned matchers (Papadakis et al., ACM CSUR 2020); correlation clustering with constraints (Saeedi et al., ESWC 2018); TruthFinder (Yin, Han & Yu, KDD 2007); TreeSHAP (Lundberg et al., 2020).

## 2. Risk control: a guaranteed false-merge budget

**Where:** Matching Policies; Match Review → Policy panel; Analytics → False-merge monitoring.

Learn-then-Test (`pipeline/risk_control.py`) certifies thresholds so that at most α of automatic property merges are wrong with 95% confidence (Clopper–Pearson, fixed-sequence testing). Risk is counted per property pair, not per record pair. Every α is re-checked on held-out hotels. Below the certifiable range the engine refuses to auto-merge. Changing α in the app re-certifies the thresholds and adds the new review-band pairs to the queue.

Research: Learn-then-Test (Angelopoulos, Bates, Candès, Jordan & Lei, 2021); conformal risk control (Angelopoulos et al., ICLR 2024).

## 3. Human review: decisions that change the catalog

**Where:** Match Review; record → *Activity history*; Quality & Audit.

Review cases (`services/review.py`) are persisted in SQLite, from the review band and from ambiguous imports. A decision is version-checked (optimistic concurrency) and idempotent (`Idempotency-Key`). It is applied as a catalog mutation (merge or split, `services/catalog.py`) and audited. Undo deactivates the mutation and rebuilds the catalog from base plus the active mutations. The supplier-exclusivity invariant is enforced: a merge that would put two listings from one supplier into one property is refused with a clear reason.

Research: uncertainty sampling for active learning (Settles, 2009); human-in-the-loop entity resolution (Wang et al., CrowdER, VLDB 2012).

## 4. Rooms, rate plans and offers

**Where:** record → *Rooms* and *Offers*; Offer Intelligence.

Rooms (`pipeline/rooms.py`) are grouped on physical attributes only. Offers form comparable groups by physical room × meal plan × refundability × occupancy × nights. Selection (`services/offers_svc.py`): paused suppliers and offers above the price-competitiveness cap are ineligible; among the rest, the highest expected value wins (P(book) × P(confirm at quoted price) × margin − (1 − P(confirm)) × failure cost). The recommended offer is always shown with its own price, cancellation deadline and payment terms, and the reasons are listed. The Clean Feed API (`GET /api/v1/hotels/{id}/offers`) serves the same selection to API buyers.

## 5. Sightseeing: product, option, unit

**Where:** Inventory → Sightseeing; record → *Options* and *Matching evidence*; Offer Intelligence → Sightseeing.

`pipeline/activities.py` follows the OCTO model. A different attraction or access tier is a different product (Burj Khalifa levels 124/125 vs 148). Within a product, time slot, transfer, meal, private vs shared, language and add-ons define the options, so tours with different inclusions are never merged. Product and option F1 on the synthetic ground truth are shown in Analytics.

## 6. Supplier reliability and fault simulation

**Where:** Suppliers → profile → *Reliability*.

`pipeline/reliability.py` keeps a Beta posterior per supplier for confirmation and price changes, plus a latency factor, with the prior taken from the synthetic 30-day booking history. The what-if simulation changes a supplier's hidden behaviour in the booking simulator. Scores move only through simulated outcomes, and offer selection reacts (offer groups switch supplier).

Research: Bayesian posteriors for bandit-style reliability estimation (Russo et al., 2018).

## 7. Ranking

**Where:** Search Ranking → Preview and Experiments.

`pipeline/ranking.py` is LambdaRank trained on simulated search logs with inverse-propensity weighting (propensities estimated from randomised sessions). Business weights (margin, Platinum, reliability risk) are blended in under a Kendall-τ guardrail. Offline NDCG@10 against the known true relevance is shown (naive vs IPW). Sightseeing uses transparent rule-based scoring.

Research: unbiased learning to rank (Joachims, Swaminathan & Schnabel, WSDM 2017); LambdaMART (Burges, 2010).

## 8. Commercial simulation

**Where:** Offer Intelligence → Optimization.

`services/simulator.py` replays simulated agent searches through the raw shelf (every supplier copy, cheapest first) and LedgerBot's shelf (deduplicated, expected-value offer). It uses a two-stage choice model calibrated to about 3% look-to-book, with duplicates adding choice overload. Results are labelled simulated; the annualised figure is labelled illustrative and shows its formula.

Research: discrete choice and nested logit (McFadden, 1978; Train, 2009); choice overload (Chernev, Böckenholt & Goodman, 2015).

---

## From this build to production

| Capability | In this build | In production |
|---|---|---|
| Ingest | JSON/CSV upload validated and matched as a background job | Supplier pull/push (XML, JSON, OCTO) → a stream per supplier → schema registry; same validation and matching services |
| Candidates and matcher | In-memory indexes; LightGBM on CPU | OpenSearch (BM25), HNSW vector index, H3 and pHash indexes as services; matcher exported to ONNX |
| Decisions | Learn-then-Test thresholds; review cases in SQLite | Per-supplier calibration recertified weekly; review console with queues and SLAs |
| LLM adjudicator | Optional, batched, cached; off without a key | Asynchronous on the uncertain band only, never on the search path |
| Catalog | Base build + ordered mutation log, replayed on start | Postgres with versioned mappings and one-click rollback |
| Identity | Demo identities with role checks | SSO (OIDC/SAML) in front of the same permission checks |
| Search path | Offer selection and ranking computed on request | Mapping cache → offer selector → ranker, design target under 5 ms added per search |
| Rollout | Experiments page and replay | Shadow mode → triggered A/B on searches where rankings differ → ramp |
