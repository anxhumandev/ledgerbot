/** Per-scene method notes: the problem, how LedgerBot solves it, the research it rests on, and where it lives
 *  in the enterprise build. Shown in the "Method & research" drawer and mirrored in PROTOTYPE_GUIDE.md. */
export type Note = { problem: string; method: string[]; research: string[]; enterprise: string; real: string };

export const RESEARCH: Record<string, Note> = {
  cold: {
    problem: "TBO receives the same room many times over: different suppliers, names, codes and prices. Agents de-duplicate by eye on every search.",
    method: ["Match supplier hotels into one golden record per property.", "Match rooms on physical attributes only (class, bed, view, occupancy, accessibility).", "Group rates into offer slots; pick the best offer by expected value, not price alone."],
    research: ["Entity resolution with blocking and learned matchers (Papadakis et al., ACM CSUR 2020).", "OCTO / OTA room and rate separation used across the travel industry."],
    enterprise: "Golden-record store (hotel → room → offer) read by the search path through a mapping cache.",
    real: "Computed from the synthetic world: every count on screen comes from the pipeline.",
  },
  mess: {
    problem: "Raw multi-supplier shelves bury the right answer under duplicates and inconsistent codes (BB / AD / B&B), and some rates are attached to the wrong room.",
    method: ["Normalise board and cancellation vocabularies across suppliers (EN, ES, bed-bank codes).", "Re-attach every rate to a physical room from the rate's own text, fixing feed mis-mappings.", "Show one card per hotel, one row per real room, one chip per offer slot."],
    research: ["Choice overload (Iyengar & Lepper, 2000); a meta-analysis shows it is strongest when options are hard to compare, as raw supplier rows are (Chernev, Böckenholt & Goodman, 2015)."],
    enterprise: "B2B portal and API buyers receive the de-duplicated shelf; the raw feed stays available for audit.",
    real: "Same search, same data on both sides; the timer is a live challenge.",
  },
  onboard: {
    problem: "Onboarding a new supplier today means weeks of manual mapping, and acquisitions (BookaBed, Jumbonline, Classic Vacations) multiply it.",
    method: ["Blocking: H3 geo cells, BM25 on names, MiniLM embeddings with FAISS, photo pHash. Never compare all pairs.", "A small LightGBM matcher with monotone constraints, isotonic-calibrated.", "Route each decision by certified thresholds: auto-merge, LLM for hard cases, human review.", "Constrained clustering: one listing per supplier per hotel, no contradictions."],
    research: ["Blocking survey (Papadakis et al., 2020).", "Correlation clustering with constraints (Saeedi et al., ESWC 2018).", "Learn-then-Test risk control (Angelopoulos et al., 2021)."],
    enterprise: "Streaming candidate and matcher services: a new feed only touches the hotels it overlaps.",
    real: "Real computation on 802 NovaBeds records; only the pacing between decisions is slowed for viewing.",
  },
  inspect: {
    problem: "Mapping teams cannot trust a black box: every merge must be explainable and every near-miss defensible.",
    method: ["Per-pair feature contributions (LightGBM SHAP-style) shown as an evidence waterfall.", "Truth discovery picks each attribute's value and learns how much to trust each supplier.", "pHash photo de-duplication and hero image selection.", "Try to fool it: the full single-record pipeline runs on whatever is typed (parse → candidates → score → decide) and abstains with a reason when evidence conflicts."],
    research: ["TreeSHAP contributions (Lundberg et al., 2020).", "Truth discovery (Yin, Han & Yu, TruthFinder, KDD 2007).", "Selective prediction / learning to abstain (Geifman & El-Yaniv, 2017)."],
    enterprise: "Ops review console with versioned mappings and one-click rollback; analyst decisions become training labels.",
    real: "Explanations and trust scores are computed live from the matcher; the fool-it trace runs the real pipeline and its timings are measured.",
  },
  review: {
    problem: "Full automation is neither safe nor necessary: a production matcher must know which decisions it may take alone and hand the rest to people efficiently.",
    method: ["Only pairs inside the certified review band reach a person; everything else is decided automatically within the chosen error budget.", "Most uncertain pairs first, with the same field-level evidence and contribution waterfall the model used.", "Every decision is timed and stored as a gold label for the next calibration and retraining run."],
    research: ["Active learning by uncertainty sampling (Settles, 2009).", "Human-in-the-loop entity resolution (Wang et al., CrowdER, VLDB 2012)."],
    enterprise: "Ops review console with versioned mappings, undo and one-click rollback; analyst throughput and agreement are monitored.",
    real: "The queue is the live review band at the current α; decisions and their timings are recorded in this session.",
  },
  shelf: {
    problem: "TBO sells through two channels, agents on the B2B portal and API customers, and both receive the duplicated, inconsistently coded supplier shelf.",
    method: ["Agent portal: one card per hotel, one row per physical room, one choice per board and cancellation term, best supplier offer pre-selected.", "Clean Feed API: the same golden record as JSON, with canonical board and cancellation fields, a confirm probability and ranked fallbacks per offer.", "Side by side with the payloads suppliers actually send, so the normalisation work is visible."],
    research: ["OpenTravel / OCTO style separation of property, room and rate.", "Choice overload on comparison screens (Chernev, Böckenholt & Goodman, 2015)."],
    enterprise: "Both channels read the same mapping cache; the API adds no LLM call and no matching work at request time.",
    real: "Portal and API responses are computed live from the golden records; supplier field layouts are illustrative, values are the raw feed values; server time is measured.",
  },
  dial: {
    problem: "\"95% confident\" is not a guarantee. TBO needs to choose its false-merge risk and know it holds.",
    method: ["Learn-then-Test with fixed-sequence testing and Clopper–Pearson bounds at δ = 0.05.", "Risk is counted per property pair (one wrong hotel merge = up to 16 wrong record pairs).", "Every α is re-checked on hotels the model never saw; below the certifiable range it refuses to auto-merge."],
    research: ["Learn-then-Test (Angelopoulos, Bates, Candès, Jordan, Lei, 2021).", "Conformal risk control (Angelopoulos et al., ICLR 2024)."],
    enterprise: "Risk-controlled decision service; thresholds recalibrated weekly per supplier.",
    real: "Recomputed live from the calibration audit; held-out check uses the test split.",
  },
  health: {
    problem: "The cheapest supplier is not the best if it fails to confirm or changes the price at checkout.",
    method: ["Beta posteriors per supplier for confirm rate and price jumps, updated by every booking outcome.", "Expected value per offer: P(book) × P(confirm at quoted price) × margin − failure cost.", "Offers switch supplier automatically when expected value flips."],
    research: ["Bayesian bandits / Thompson-style posteriors for supplier reliability (Russo et al., 2018)."],
    enterprise: "Feedback loop from bookings (409s, price mismatches, timeouts) into reliability posteriors on the search path.",
    real: "Bookings are simulated from hidden supplier profiles; the scores move only because of observed events.",
  },
  rank: {
    problem: "TBO's users are professional agents with very different needs; one global ranking fits none of them.",
    method: ["LambdaRank learned from search logs, per agent profile.", "Position-bias correction: propensities from randomised sessions, inverse-propensity weighting.", "Business objectives (margin, Platinum, reliability) layered on with a Kendall-τ guardrail."],
    research: ["Unbiased learning to rank (Joachims, Swaminathan & Schnabel, WSDM 2017).", "LambdaMART (Burges, 2010)."],
    enterprise: "Ranker on the search path, under 3 ms, retrained from logged outcomes.",
    real: "Trained on simulated logs with a known true relevance, so the IPW gain is measured.",
  },
  arena: {
    problem: "The obvious build (ask an LLM about every pair) is costly, slow, uncalibrated and self-contradictory at TBO's scale.",
    method: ["Same held-out pairs for both systems.", "LedgerBot's numbers are measured; the LLM-only column here is a simulated profile with stated assumptions.", "Judges vs Machine: humans vote on hard pairs; LedgerBot abstains where people disagree."],
    research: ["Entity matching with LLMs (Peeters, Steiner & Bizer, EDBT 2025).", "LLM over-confidence and calibration (Xiong et al., ICLR 2024)."],
    enterprise: "The LLM is an asynchronous adjudicator for the uncertain band only, never on the search path.",
    real: "LedgerBot measured; LLM-only simulated until a real baseline run replaces it.",
  },
  impact: {
    problem: "The business case: does a cleaner, reliability-aware shelf earn more per search?",
    method: ["Replay 50,000 simulated searches through both shelves with the same agents and suppliers.", "Two-stage choice model calibrated to about 3% look-to-book; duplicates add choice overload."],
    research: ["Discrete choice / nested logit (McFadden, 1978; Train, 2009)."],
    enterprise: "Shadow mode → triggered A/B test (only searches where rankings differ) → ramp.",
    real: "Simulated; the annualised figure is illustrative and its formula is on screen.",
  },
};
