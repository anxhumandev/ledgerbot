# Tessera · Unified Supply Intelligence

TBO aggregates hotels and sightseeing from many suppliers — direct contracts, bed banks, and acquired stacks like Jumbonline, BookaBed and Classic Vacations. The same room arrives many times under different names, prices and terms. The typical approach ("ask an LLM if two listings match") is slow, expensive, overconfident and inconsistent. **Tessera** replaces it with a calibrated cascade: cheap candidate generation → a small learned matcher → an LLM only for the hard cases → a human for the rest — backed by a statistically guaranteed false-merge rate, globally consistent clusters, a data model that separates the physical room from the commercial offer, live supplier-reliability scores, and offer ranking by expected booked margin. The result: cleaner listing pages, fewer wrong-room incidents, higher look-to-book, and new suppliers onboarded in minutes.

---

## Quick Start

```bash
make setup && make data && make train && make dev
```

Open **http://localhost:5174** in your browser (1920 × 1080 recommended).

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
