# LedgerBot · Inventory Intelligence Platform
### Multi-supplier inventory and optimization · TBO VoyageHack 4.0 · Problem 3 (Multi Supplier Optimization)

LedgerBot is an operations platform for travel inventory that arrives from many suppliers at once: direct contracts, bed banks and acquired supply stacks. It consolidates duplicate hotels and sightseeing products into canonical records, keeps meaningful differences apart (physical rooms vs rate plans, experience options with different inclusions), compares every supplier's offer and recommends one with reasons, tracks supplier reliability, and previews how optimized inventory ranks in search.

It is built for four roles: **Inventory Analyst** (resolve matches), **Supplier Operations Manager** (feeds, imports, supplier health), **Commercial / Revenue Analyst** (offers, competitiveness, ranking) and **Platform Administrator** (policies, users, settings).

> **Demo workspace.** All supplier data is synthetic, and prices and policies are fictional. Supplier booking outcomes and the commercial replay are simulated, and every screen labels them as simulated. Identities are local demo users chosen in the sidebar; there is no sign-in (see [Known limitations](#known-limitations)).

---

## What you can do

| Module | Route | What it does |
|---|---|---|
| Operations Overview | `/overview` | KPIs with their source (measured, simulated or live), inventory health, supplier health, a "Needs attention" table that links to the right screen, recent activity from the audit trail, and an issues CSV export. |
| Inventory Catalog | `/inventory/hotels`, `/inventory/sightseeing` | Server-side search (matches any supplier's spelling), filters (country, city, supplier, status, quality, confidence), sorting, paging, column visibility, bulk export, URL-backed state. |
| Record detail | `/inventory/:type/:id` | Hotels: golden record, supplier records compared field by field, physical rooms and rate-plan groups, every supplier offer, matching evidence (why merged and why nearby properties were kept separate), photos and content, activity history. Sightseeing: product, options and supplier units, the merge rule and products deliberately kept separate. |
| Match Review | `/matching/review` | Queue (priority, status, assignee, source) with side-by-side comparison, the model's evidence, the decision zones and policy. Confirm, reject or escalate with confirmation; decisions merge or split canonical records, persist, and can be undone. Includes notes, assignment and case history. |
| Clusters | `/matching/clusters` | Multi-supplier records with the weakest evidence first, plus **Test a supplier record**: runs one listing through the live pipeline without changing the catalog. |
| Matching Policies | `/matching/policies` | Choose the guaranteed false-merge budget α. Thresholds are re-certified with Learn-then-Test; automation, review volume and the held-out error are previewed before applying. |
| Suppliers | `/suppliers/directory`, `/suppliers/:id` | Feed status, last sync, listings, coverage, data-quality findings, confirmation and price-change rates and reliability. Each supplier profile has tabs for inventory, ingestion runs, reliability trends, errors, configuration (pause or resume) and a **what-if degradation simulation**. |
| Data Ingestion | `/suppliers/ingestion` | Upload JSON or CSV, validate (schema, duplicates, unknown cities, coordinates), preview, confirm, then watch the job match every record against the catalog. Results list merged, new, updated, sent-to-review and rejected records; failed jobs can be retried. |
| Offer Intelligence | `/offers/comparison`, `/offers/optimization` | Compare all offers for a property or experience under meal-plan, cancellation, payment and supplier requirements. Each group gets a recommended offer with reasons and its own terms. Also shows the Clean Feed API payload, the selection policy (price-competitiveness cap), win share by supplier, and the commercial replay simulation. |
| Search Ranking | `/ranking/preview`, `/ranking/experiments` | Result pages per agent profile and strategy (relevance, commercial, balanced, price-first) with the selected eligible offer and explanation chips; sightseeing uses rule-based scoring, labelled as such. Experiments compare A vs B: position changes, offer changes, Kendall τ, offline NDCG; the ranking weights are configured here. |
| Analytics | `/analytics` | Precision, recall, F1 and B-cubed; hotels vs sightseeing; false-merge monitoring per α; review workload; supplier reliability trends; consolidation; competitiveness; ranking quality; LLM-only comparison; LLM spend. |
| Quality & Audit | `/audit` | Searchable, append-only event log with actor, action, entity, before and after state, reason and request ID. |
| Settings | `/settings` | Workspace name, user roles, matching, offers and ranking configuration, system information, and **Reset demo workspace** (administrators only). |

Use **Ctrl/Cmd + K** for the command palette (properties, experiences and pages).

---

## Architecture

```
frontend/ (React 18 · TypeScript · Vite · Tailwind · TanStack Query · React Router · Recharts)
  src/app/App.tsx           routes (lazy-loaded pages)
  src/layouts/AppShell.tsx  sidebar, breadcrumbs, command palette, notifications, identity menu
  src/pages/                one file per screen
  src/features/             shared feature components (offer tables, match tester)
  src/ui/                   design system: core, table, overlay (dialogs, drawers, menus, toasts), evidence, activity
  src/lib/                  API client (identity, idempotency, structured errors), hooks, formatting, tokens

backend/ (Python 3.11 · FastAPI)
  app/pipeline/             matching engine: normalisation, blocking (H3, BM25, MiniLM+FAISS, pHash), LightGBM matcher,
                            calibration, Learn-then-Test risk control, clustering, rooms, offers, activities, ranking, reliability
  app/store.py              SQLite operational store (versioned migrations, PostgreSQL-ready query layer)
  app/identity.py           demo identities, roles, permission checks on every mutation
  app/audit.py              append-only audit log (database triggers reject UPDATE/DELETE)
  app/errors.py             structured errors {"error": {code, message, details, request_id}}, request IDs
  app/services/catalog.py   canonical catalog read models + mutations (merge, split, ingest), replayed on startup
  app/services/review.py    review cases, versioned decisions, idempotency, undo
  app/services/ingestion.py file validation and background import jobs through the real matcher
  app/services/offers_svc.py offer comparison and eligibility-aware selection
  app/services/…            suppliers, insights (overview, analytics), ranking, settings, detail views
  app/routers/workspace.py  identity, overview, inventory, matching, review, analytics, audit, settings
  app/routers/operations.py suppliers, simulation, ingestion, offers, ranking
```

**Source of truth.** The pipeline build (`backend/data/cache/state.pkl`) is the immutable base catalog and is never modified. Operator decisions live in SQLite (`backend/data/ledgerbot.sqlite3`): review cases, notes, the ordered log of catalog mutations (merges, splits, imported records), ingestion jobs and results, supplier configuration, settings, users and the audit log. On startup the server replays every active mutation on top of the base catalog, so decisions and imports survive restarts. Undoing a decision deactivates its mutation and rebuilds.

**Offer rules.** Hotels have two levels of equivalence. A *comparable group* is the same physical room, meal plan and refundability; an *identical rate plan* also matches the cancellation deadline and payment method. Offer Comparison can compare by either. Sightseeing offers compete within one experience option. Paused suppliers are ineligible. The price-competitiveness cap is measured against the cheapest offer from a supplier that can actually be booked, so a paused supplier's price never sets the bar. Among eligible offers the highest expected value wins: P(book) × P(confirm at quoted price) × margin − (1 − P(confirm)) × failure cost. The displayed price, cancellation and payment terms always come from that one offer.

**Sightseeing options.** Listings share an option only if time slot, transfer, meal, private/shared, language and add-ons agree, their durations can overlap, and (when a feed provides them) their cancellation terms match. Durations are compared as intervals: "4h" and "240 minutes" agree, "half day" and "full day" are wide ranges, and "2h" vs "4h" are different options.

**Ranking inputs.** Each hotel's ranking features (price, supplier, meal plan, refundability) describe one coherent lead offer: the cheapest of the eligible expected-value winners across its comparable groups. That is the same offer the search preview shows. Whether refundable or breakfast rates exist at any price is modelled as separate availability features.

---

## Setup

Requirements: Python 3.11+, Node.js 18+.

```bash
make setup && make data && make train && make dev
```

Then open **http://localhost:5174** (API on **8100**; set `PORT_BACK` / `FRONTEND_PORT` to change). For the full five-city world used in the demo: `WORLD=large make data train`.

**Windows without `make`** (PowerShell, from `tessera/`):

```powershell
py -3.11 -m venv .venv; .venv\Scripts\python -m pip install -r backend\requirements.txt; cd frontend; npm ci; cd ..
$env:WORLD="large"; cd backend; ..\.venv\Scripts\python -m data.generate; ..\.venv\Scripts\python -m app.pipeline.run; cd ..
.venv\Scripts\python dev.py
```

The workspace database is created and migrated automatically on first start; demo users are seeded and review cases are generated from the current review band. To start over, use **Settings → Reset demo workspace** as the administrator, or delete `backend/data/ledgerbot.sqlite3` while the server is stopped.

### Environment variables (`.env`)

| Variable | Default | Purpose |
|---|---|---|
| `WORLD` | `demo` | `demo` = Dubai only; `large` = Dubai, Abu Dhabi, Singapore, Bangkok, Bali |
| `ANTHROPIC_API_KEY` | empty | Optional. Enables the LLM adjudicator for uncertain pairs and `make baseline` |
| `LLM_ENABLED` | `true` | Set `false` to keep the LLM off even with a key |
| `LEDGERBOT_DB` | `backend/data/ledgerbot.sqlite3` | Workspace database path |
| `ALLOWED_ORIGINS` | `http://localhost:5174,http://127.0.0.1:5174` | CORS allow-list (comma-separated) |
| `MAX_UPLOAD_MB` | `5` | Ingestion upload limit |
| `PRICE_CAP_PCT` | `5` | Default price-competitiveness cap (editable in the app) |
| `WORKSPACE_NAME` | `Demo Workspace` | Default workspace name (editable in the app) |
| `PORT_BACK`, `FRONTEND_PORT` | `8100`, `5174` | Ports used by `dev.py` |

### Commands

| Command | What it does |
|---|---|
| `make data` | Generate the synthetic world |
| `make train` | Build the pipeline: matcher, calibration, risk thresholds, clusters, rooms, offers, ranking |
| `make dev` | Start API and frontend |
| `make test` | Backend tests, frontend unit tests, type-check and production build |
| `make e2e` | End-to-end tests against the running app (uses the installed Microsoft Edge) |
| `make baseline` / `make baseline-sim` | LLM-only benchmark (measured with an API key / simulated profile without) |

---

## Tests

- **Backend** (`backend/tests`, 96 tests): room parser (EN, ES, bed-bank codes), Learn-then-Test with known answers, clustering constraints, offer-slot separation, plus `test_workspace_api.py` covering identity and permissions, inventory filter, sort and search, record detail, offer groups never mixing terms, the recommendation keeping its own price and terms, the price cap, sightseeing option separation, review decisions changing the catalog, idempotent replays, stale-version and duplicate-decision rejection, split on reject, undo, ingestion validation (malformed JSON, CSV schema, unsupported type, duplicate IDs, unknown cities), an import job running the real pipeline, catalog rebuild reproducing state, the append-only audit log, overview, analytics and ranking, and structured validation errors; sightseeing duration and cancellation option rules (`test_option_rules.py`); identical rate-plan keys and comparison; the price-cap baseline ignoring paused suppliers; and ranking features matching one coherent offer.
- **Frontend unit** (`frontend/src/**/*.test.ts(x)`, Vitest): formatting, the API client (identity header, structured errors, network errors, idempotency keys), table sorting, selection and empty state, pagination, status labels, error states, and confirmation dialogs requiring a reason.
- **End-to-end** (`frontend/e2e`, Playwright): dashboard and every sidebar module; search a hotel, open it and inspect supplier records and evidence; confirm a review case, reload, verify persistence and the audit trail, then undo; role restrictions; offer recommendation coherence; sightseeing tiers and options.

---

## Demo walkthrough

`VIDEO_SCRIPT.md` is the step-by-step recording guide (what to click and what to say). In short:

1. **Overview** → open a high-priority item in *Needs attention*.
2. **Match Review** → compare the two records, read the evidence, confirm or reject. Open the property and see it changed.
3. **Inventory** → Atlantis The Palm: supplier records, rooms vs rate plans, offers, and why Atlantis The Royal was kept separate.
4. **Data Ingestion** → as Rahul (Supplier Ops) download the sample feed, validate, import, and read the outcomes.
5. **Suppliers** → GlobalBeds → Reliability → simulate price changes and watch offers move to other suppliers. Then clear the fault.
6. **Offer Intelligence** → compare offers with requirements; open the Clean Feed API view; run the commercial simulation.
7. **Search Ranking** → preview per agent profile; compare strategies in Experiments.
8. **Matching Policies**, **Analytics**, **Quality & Audit** → the guarantee, the measurements, and the trail of everything done above.

---

## How the numbers are made

- **Ground truth stays hidden.** The pipeline sees truth only through `labels_sample.json` (800 training labels and a gold mapping audit of calibration-split hotels). Evaluation uses held-out test hotels the matcher and calibrator never saw.
- **Risk is counted per property pair.** Learn-then-Test certifies that at most α of automatic property merges are wrong (Clopper–Pearson, δ = 0.05). Below the certifiable range, LedgerBot refuses to auto-merge and routes candidates to review.
- **The pipeline build resolves its review band with a simulated reviewer** so the base catalog is complete. In the app, those pairs are open review cases and show the mapping as provisional until a person decides.
- **Supplier reliability** is a Beta posterior per supplier, with its prior taken from the synthetic 30-day booking history. The what-if simulation changes a supplier's hidden profile, and scores move only through simulated booking outcomes.
- **The commercial replay** runs simulated agent searches through the raw shelf and LedgerBot's shelf, using a two-stage choice model calibrated to about 3% look-to-book. The annualised figure is `lift × ₹31,500 Cr annual hotel GTV × 6% gross margin` and is labelled illustrative.
- **Quality score** (0–100) is the weighted completeness and corroboration of a golden record: phone 15, address 15, coordinates 10, stars 10, hero photo 15, room mapping 15, two or more suppliers 10, no open review 10. Checks that do not apply (rooms and photos outside Dubai) are excluded.
- **Offer competitiveness** is the share of comparable offer groups (two or more suppliers) where the recommended offer is also the cheapest; the average premium is shown next to it.
- **The LLM is optional and never faked.** Without `ANTHROPIC_API_KEY`, uncertain pairs go to human review and the UI says "LLM off". The LLM-only comparison column is labelled simulated unless a real `make baseline` run exists.

---

## Known limitations

- **No authentication.** Identities are seeded demo users selected in the UI and sent as `X-LedgerBot-User`; the API enforces role permissions on every mutation, but anyone who can reach it can claim any identity. Production needs SSO (OIDC/SAML) in front of the identity dependency.
- **Synthetic data.** Rooms, rates and photos exist only for Dubai properties; other cities have property-level records. Supplier feeds carry quotes, not live availability, taxes or (for sightseeing) cancellation terms, and the UI says so.
- **Review cases cover hotel property matches.** Room-level and sightseeing matches are rule-based and shown with their evidence, but are not routed to the review queue.
- **Sightseeing ranking is rule-based**, with no learned ranker for experiences.
- **Single-process store.** SQLite with a process-wide lock; background imports run in threads. Moving to PostgreSQL and a job queue is the path to multiple instances.
- **Notifications** (email and chat) are planned; high-severity items appear in the bell menu and on the Overview.
