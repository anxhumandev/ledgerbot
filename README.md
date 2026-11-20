# LedgerBot · Multi Supplier Optimization

TBO aggregates hotels and sightseeing from many suppliers — direct contracts, bed banks, and acquired stacks like Jumbonline, BookaBed and Classic Vacations. The same room arrives many times under different names, prices and terms. The typical approach ("ask an LLM if two listings match") is slow, expensive, overconfident and inconsistent. **LedgerBot** replaces it with a calibrated cascade: cheap candidate generation → a small learned matcher → an LLM only for the hard cases → a human for the rest — backed by a statistically guaranteed false-merge rate, globally consistent clusters, a data model that separates the physical room from the commercial offer, live supplier-reliability scores, and offer ranking by expected booked margin. The result: cleaner listing pages, fewer wrong-room incidents, higher look-to-book, and new suppliers onboarded in minutes.

---

## Quick Start

```bash
make setup && make data && make train && make dev
```

Open **http://localhost:5174** in your browser (1920 × 1080 recommended). The API listens on **8100**; both ports are configurable (`PORT_BACK`, `FRONTEND_PORT`) so LedgerBot can run beside other local dev servers on 5173/8000.

For the recording, build the large world (Dubai + Abu Dhabi, Singapore, Bangkok, Bali): `WORLD=large make data train`. The Scene 05 dial needs its calibration volume to certify α below about 1% (see *How the numbers are made*).

**Windows without `make`** (PowerShell, from the repo root):

```powershell
py -3.11 -m venv .venv; .venv\Scripts\python -m pip install -r backend\requirements.txt; cd frontend; npm ci; cd ..
cd backend; ..\.venv\Scripts\python -m data.generate; ..\.venv\Scripts\python -m app.pipeline.run; cd ..
.venv\Scripts\python dev.py
```

Set `$env:WORLD="large"` before the generate step for the recording world. Set `$env:PYTHONIOENCODING="utf-8"` if the console cannot print ₹ and ★.

---

## Prerequisites

| Requirement | Version |
|-------------|---------|
| Python      | 3.11+   |
| Node.js     | 18+     |
| npm         | (bundled with Node) |

---

## Environment

1. Copy the example env file:
   ```bash
   cp .env.example .env
   ```
2. Set `ANTHROPIC_API_KEY` in `.env` (optional — required only for LLM adjudication and baseline runs; the demo works fully offline without it).

---

## Make Targets

| Target   | Description |
|----------|-------------|
| `setup`  | Install Python and Node dependencies |
| `data`   | Generate the synthetic world (hotels, rooms, offers, activities, logs) |
| `train`  | Train the LightGBM matcher, calibrate, compute LTT thresholds |
| `baseline` | Run the LLM-only baseline evaluation (requires `ANTHROPIC_API_KEY`) |
| `dev`    | Start the FastAPI backend + Vite dev server |
| `reset`  | Reset all demo state (sim, onboarding, votes, sabotage) |
| `teach`  | Run the offline LLM dictionary-learning pass (requires `ANTHROPIC_API_KEY`) |

---

## Demo Hotkeys

| Key | Action |
|-----|--------|
| `→` / `←` | Navigate scenes |
| `R` | Reset demo state |
| `P` | Toggle presenter overlay |
| `Space` | Scene-specific action (cold-open fold, onboarding start, replay, architecture step) |
| `1`, `2` | Start timers — left / right (Scene 01) |
| `O` | Start onboarding (Scene 02) |
| `Shift+1`..`Shift+5` | Sabotage supplier 1–5 (Scene 06) |
| `Shift+0` | Heal all suppliers (Scene 06) |
| `1`, `2`, `3` | Ranking mode toggle — relevance / +margin & platinum / +reliability (Scene 07) |
| `A`, `B` | Toggle sub-views (Scene 08, 09) |
| `L` | Learn from votes (Scene 08) |

---

## URL Parameters

| Parameter | Effect |
|-----------|--------|
| `?record=1` | Recording mode — hides the cursor after 2 s of idle, disables hover tooltips |
| `?reduceMotion=1` | Accessibility — disables animations |

---

## Phone Voting (Judges vs Machine)

1. Connect your phone to the **same Wi-Fi** network as the presenter's laptop.
2. On Scene 08B, scan the **QR code** displayed on screen.
3. Enter a nickname and vote on hotel pairs before the countdown expires.

---

## Stack

**Backend — Python**
- FastAPI · Uvicorn (WebSockets)
- LightGBM · scikit-learn · SciPy (matcher, calibration, LTT)
- sentence-transformers (`all-MiniLM-L6-v2`) · FAISS (embedding ANN)
- rapidfuzz · h3 · rank_bm25 (blocking & string similarity)
- Anthropic SDK (LLM adjudicator, optional)

**Frontend — React**
- Vite · TypeScript
- Tailwind CSS (custom "Paper & Lagoon" design system)
- Framer Motion (animation)
- Lucide React (icons) · react-force-graph-2d (cluster graph) · recharts (charts) · qrcode.react (voting QR)

---

## Credits

Built for **TBO VoyageHack 4.0** · Problem 3 (Multi Supplier Optimization)

---

## Data Disclaimer

> All data is synthetic. Prices, policies, and supplier names are fictional.

---

## Recording the demo video

1. **Start fresh.** Stop any running servers, then from the repo root run `.venv\Scripts\python dev.py` (or `make dev`). A server started before a code change keeps serving the old code.
2. **No API key?** Run `make baseline-sim` once (Windows: `cd backend; ..\.venv\Scripts\python -m app.eval.baseline_sim`). Scene 08 then shows the LLM-only column labelled **SIMULATED**. Say so in the voice-over, e.g. *"The LLM-only column is a simulated profile; LedgerBot's column is measured."*
3. **Open** `http://localhost:5174/?record=1` in Chrome or Edge and press **F11** for full screen. The stage is designed at 1920 × 1080 and stretches to fill any window shape, so nothing is cut off and there are no side bars. Full screen on a 16:9 display (e.g. 1536 × 864 at 125 % scaling, which is 1920 × 1080 physical) is pixel-identical to the design.
4. **Record** with Win + Alt + R (Xbox Game Bar) or OBS at 1920 × 1080. Press `R` before every take.

## Run-of-show (about 8–9 minutes)

Press `R` before every take: it resets simulation, onboarding, votes, sabotage, the dial and any retrained model, so two recordings look the same (the booking stream is seeded).

| Scene | Beat | Keys |
|---|---|---|
| 00 Cold Open | Nine raw rows for one Atlantis The Palm room fold into one card with the best offer and its alternatives. Stats underneath are computed from the world. | `Space` |
| 01 The Mess | A teammate hunts for the cheapest Deluxe King, breakfast, free cancellation on the raw feed, then on LedgerBot. Correct clicks stop the timer. | `1`, `2`, `0` |
| 02 Live Onboarding | NovaBeds (never seen before) is blocked, scored, routed and clustered live; NovaBeds nodes fly into the Dubai graph. Ends with violations and the guarantee. | `O` |
| 03 Inspector | Golden record, supplier diff table, Explain waterfall for the weakest edge, near-miss (Atlantis Palm vs Royal), learned source trust, photo dedup; Rooms tab (physical room → offer slots → competing offers); Activities tab (Burj Khalifa products and options). | `H` `M` `A`, `N` |
| 04 Break It | Presets run the real single-record pipeline and show every stage. Misspellings and the Spanish room name ("Habitación Doble Deluxe Vista Mar – AD" → Deluxe · Sea View, breakfast as an offer term) merge; the sister property stays separate; gibberish becomes a new property. Whether the wrong-pin preset abstains to review depends on the review band left by α and β (see *How the numbers are made*). | `1`–`5`, `Enter` |
| 05 Error Budget | Turn the dial (arrows, drag, or a USB MIDI knob on CC 1). Automation, review volume and the held-out false-merge rate recompute live; below the certifiable range it refuses to auto-merge. | `↑` `↓` |
| 06 Supplier Health | `Shift+2` sabotages GlobalBeds (35% price jumps). Its score falls only as observed bookings fail; offer slots switch suppliers and a toast counts them. `Shift+0` heals. | `Shift+1..5`, `Shift+0` |
| 07 Ranking | Riya vs Mark on the same search; layer margin/platinum and reliability risk with a Kendall-τ guardrail. Proof inset: naive vs IPW NDCG@10. | `1` `2` `3` |
| 08 Arena | A: benchmark board vs the cached LLM-only baseline, corner cases, reliability diagram. B: phones scan the QR and vote; `Space` pushes a pair / reveals; `L` retrains on the votes. | `A` `B`, `Space`, `L` |
| 09 Impact | A: 50,000 simulated searches through both shelves at high speed. B: the production architecture draws itself step by step. | `A` `B`, `Space` |

Move between scenes with `→` / `←`, the large arrows on the left and right edges, or the bottom-right bar (**Reset**, **Back**, a scene menu, **Next: …**, **Keys**). Every hotkey action also has an on-screen button (fold the cold open, start the Scene 01 timers, onboard NovaBeds, run the replay, draw the architecture step by step or all at once). `P` toggles a presenter overlay with the scene's keys. Record with `?record=1`: it hides the on-screen controls and the cursor after 2 s idle.

---

## How the numbers are made

Every number on screen comes from an API response computed by the pipeline. Where a value is simulated or illustrative, the UI says so. Choices that go beyond or deviate from the original spec:

- **Ground truth stays hidden.** The pipeline sees truth only through `labels_sample.json`: 800 training labels (600 LLM-teacher style with 3% injected noise, 200 gold) and a gold *mapping audit* of every plausible pair (same city and ≤1.2 km, same brand, or similar names) between calibration-split hotels. The audit mirrors what blocking proposes; Learn-then-Test is only valid when calibration pairs look like the pairs it will judge, and a hand-picked sample of hard negatives made the held-out check fail.
- **Risk is counted per property pair, not per record pair.** One wrong merge of two hotels shows up as up to 16 wrong record pairs, so record pairs are not independent. Learn-then-Test certifies "≤ α of automatic property merges are wrong" with Clopper–Pearson bounds, δ = 0.05, fixed-sequence testing on the raw matcher score. Thresholds whose accept set is too small to ever certify are skipped before the sequence starts; that burn-in uses scores only, never labels.
- **The auto-reject budget β** is the share of true matches allowed to be lost to auto-reject (`DEFAULT_BETA`, currently 2%). Because the matcher is sharp, the certified reject threshold can land above the accept threshold; auto-merge wins in the overlap, the displayed reject threshold is clamped to the accept threshold, and the review band is then empty at that α. A smaller β (e.g. 1%) keeps a thin review band at α = 1%.
- **The certifiable range depends on audit size.** With the large world the audit holds about 3,000 property pairs, enough for α down to roughly 0.5%. Below that the dial shows "not certifiable" and LedgerBot sends every candidate merge to review. The Dubai-only demo world certifies a narrower range.
- **Held-out check.** Every α on the dial is re-checked on test-split hotels the matcher and the calibrator never saw. The chip turns clay if the empirical rate exceeds α.
- **Human review is simulated.** Pairs sent to review are resolved by a simulated reviewer with a 1% error rate so the clusters are complete. The review rate itself is real.
- **LLM calls are optional and never faked.** Without `ANTHROPIC_API_KEY`, uncertain pairs route straight to review and the UI says "LLM offline". The LLM-only baseline (`make baseline`, `claude-opus-5-5`, one pair per call, zero-shot) is a measured run, cached with its timestamp. Without a key, `make baseline-sim` writes a **simulated profile** instead: answers follow the stated error rates in `config.SIM_BASELINE` (assumptions, applied to the hardest-looking pairs), and F1, consistency violations and calibration are computed from those answers. Every screen that shows it says "simulated", its cost and latency are marked "est.", and a later real run replaces it without reusing any simulated row. Prices for the cost meter are in `backend/app/config.py`.
- **Simulation assumptions** (Scenes 06 and 09) are in `backend/app/config.py` and `backend/app/services/simulator.py`: supplier take rates (direct contracts highest), hidden reliability profiles, a booking-probability model for offer selection, and a two-stage choice model for the A/B replay calibrated to a look-to-book of about 3%. Both replay arms see the same hotels and offer slots; the raw arm shows every supplier's copy cheapest-first, LedgerBot shows one expected-value offer per hotel. The annualized figure is `lift × ₹31,500 Cr annual hotel GTV × 6% gross margin`, labelled illustrative.
- **Photos are procedural.** No stock images are shipped: `data/photos.py` draws editorial placeholder images from a seeded RNG and creates per-supplier degraded copies (crop, resize, JPEG quality, watermark, colour shift) so pHash dedup has real work to do.

`make train` prints the full metrics report (blocking recall and reduction, matcher AUC, the α grid with held-out results, cluster P/R/F1 and B-cubed, consistency violations, duplicate detection, room and activity matching, NDCG). `GET /api/metrics` returns the same numbers.

---

## Tests

```bash
make test
```

`backend/tests`: 40 table-driven room-parser cases (English, Spanish, bed-bank abbreviations), board and cancellation parsing, Learn-then-Test on synthetic scores with a known answer (including a fresh-draw check that the guarantee holds), supplier exclusivity and cannot-links in clustering, BB vs RO offer-slot separation, expected-value offer selection, and the event log. The target also runs the frontend type-check and production build.
