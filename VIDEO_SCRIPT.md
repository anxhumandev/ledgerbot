# LedgerBot: recording guide (enterprise app)
### TBO VoyageHack 4.0 · Problem 3 · Team TravellerTech · narrated by Anshuman

A run sheet for recording the product as an operations team would use it. Each step says **what to do** (👆) and **what to say** (🎙). Do a step, say its line, then move on.

**Length:** about 9 minutes (about 1,100 spoken words plus pauses). TBO's limit is 10 minutes.
**You need:** the app at http://localhost:5174, a screen recorder at 1920×1080, a mic. The deck is optional (two cut-ins are marked).

---

## Before you start (5 minutes)

1. **Start the app** if it isn't running (PowerShell, in the `tessera` folder): `.venv\Scripts\python dev.py`. Wait until http://localhost:5174 shows *Operations Overview*.
2. Open the app in Chrome or Edge, full screen (F11).
3. **Clean slate:** the app opens as **Dev Admin** (bottom of the sidebar). Go to **Settings → Workspace → Reset workspace…**, give a reason ("Recording"), confirm. Stay as Dev Admin.
4. Start recording. Stay silent for 2 seconds before you speak.

**Rules for what you say:** keep numbers exactly as the screen shows them (if the screen differs from this guide, say the screen's number). Say "simulated" for supplier bookings and the commercial simulation, and "synthetic" for the data.

**Easiest way alone:** record the clicks silently first, then record your voice over the video.

---

## 1 · Operations Overview (0:00–1:00)

**You start on:** *Operations Overview*, with eight KPI cards.

1. 👆 Do nothing for 2 seconds.
   🎙 "This is LedgerBot, an inventory intelligence platform for TBO's multi-supplier catalog. I'm Anshuman, from team TravellerTech.
   TBO gets the same hotel, room and tour from many suppliers. LedgerBot turns those listings into one trustworthy catalog, and runs the operations around it."
2. 👆 Point at the KPI cards from left to right.
   🎙 "Here's the workspace on a Monday morning: over eight thousand supplier listings consolidated into about two and a half thousand properties and thirty-three experiences, ninety-nine percent of listings consolidated, and the matches waiting for an analyst. Every number is tagged: measured, simulated or live."
3. 👆 Scroll down to **Needs attention**.
   🎙 "Below, the work: match reviews, supplier problems, failed imports, location mismatches. Each row opens the screen where it gets fixed."

---

## 2 · One property, every supplier (1:00–2:30)

1. 👆 Press **Ctrl K**, type `atlantis the palm`, press **Enter**.
   🎙 "Let's open a property. Search works with any supplier's spelling."
2. 👆 Click the **Supplier records** tab.
   🎙 "Atlantis The Palm, from five suppliers: different names, phone formats and pins, each compared with the golden record."
3. 👆 Click the **Rooms** tab.
   🎙 "Rooms are matched on what the room physically is: class, bed, view, occupancy. Meal plan and cancellation are rate terms, so they never decide room identity."
4. 👆 Click the **Offers** tab.
   🎙 "Offers only compete inside the same room and the same terms. Each group gets one recommended offer, with its own price, cancellation deadline and payment terms, and the reasons it won."
5. 👆 Click the **Matching evidence** tab.
   🎙 "And here's why. On the left, every link that merged these listings. On the right, what was kept apart: Atlantis The Royal, same brand, same island, but a different property."

---

## 3 · Match Review (2:30–3:45)

1. 👆 Click **Match Review** in the sidebar. In the queue, click a case **without** the red "supplier conflict" label.
   🎙 "Some pairs the engine won't decide alone. They come here, most uncertain first."
2. 👆 Point at the comparison table, then the evidence bars on the right.
   🎙 "The two records side by side, differences highlighted, and the model's own evidence for and against, with the thresholds it is allowed to act within."
3. 👆 Click **Confirm match**, read the dialog for a second, click **Confirm match**.
   🎙 "I confirm. That merges the two properties in the catalog, records who decided and why, and can be undone from this case."
4. 👆 Click the property link in the *Current mapping* notice.
   🎙 "The canonical record already shows both listings."
5. 👆 Go back. In the queue, click a case **with** the red "supplier conflict" label.
   🎙 "And when a merge would put two listings from the same supplier into one hotel, LedgerBot blocks it and tells the analyst why."

---

## 4 · Matching policy (3:45–4:20)

1. 👆 Click **Policies** under Match Review. Drag the **Risk budget** slider slowly from 1% down to about 0.5%, then back. Don't apply.
   🎙 "The business chooses the risk: say, at most one percent of automatic merges may be wrong. LedgerBot certifies its thresholds for that budget and checks them on hotels it has never seen. Tighter budget, more human review; the preview shows the trade-off before anyone applies it."

---

## 5 · A new supplier feed (4:20–5:30)

1. 👆 Switch identity to **Rahul Mehta** (Supplier Operations). Click **Data Ingestion**. Click **Sample JSON** to download, then drag the file onto the drop zone (or **Browse files**). Supplier: **S6 · NovaBeds**. Click **Validate file**.
   🎙 "Now a new supplier, NovaBeds, sends its first feed. Supplier operations upload it, and LedgerBot validates it before anything changes: schema, duplicates, coordinates, unknown cities."
2. 👆 Point at the issues and the preview. Click **Import … valid records**, then **Start import**.
   🎙 "Warnings are shown up front. On confirmation, every record runs through the same matching pipeline as the catalog."
3. 👆 Wait for **Completed**. Point at the outcome counts and the record list.
   🎙 "Most NovaBeds hotels merge into properties we already have. Genuinely new ones become new properties, and anything ambiguous goes to review. Every outcome is recorded, and a failed job can be retried."

---

## 6 · When a supplier degrades (5:30–6:30)

1. 👆 Click **Suppliers**, then **GlobalBeds**, then the **Reliability** tab.
   🎙 "Every supplier has a live reliability score: how often bookings confirm at the quoted price. It's built from booking outcomes; here, a synthetic thirty-day history."
2. 👆 Under *What-if*, keep **Price changes at booking** and **35%**. Click **Start simulation**, then **Start simulation** in the dialog. Stay quiet for about 15 seconds.
   🎙 *(after a few seconds)* "This is a simulation. GlobalBeds starts changing prices at checkout. Nobody tells LedgerBot; its score falls only as simulated bookings fail."
3. 👆 Wait for the orange message about offer groups.
   🎙 "And offer selection reacts: about a hundred offer groups move to more reliable suppliers on their own."
4. 👆 Click **Clear simulated faults**, then **Stop booking stream**.

---

## 7 · Offer intelligence (6:30–7:35)

1. 👆 Switch identity to **Sara Khan** (Revenue). Click **Offer Intelligence**. Search `atlantis the palm` and select it. Under *Requirements*, click **BB** and choose **Free cancellation only**.
   🎙 "Revenue analysts compare every supplier offer under the customer's requirements: breakfast, free cancellation."
2. 👆 Point at a recommended row and its reasons.
   🎙 "The recommendation is explained: lowest eligible price, or a small premium within the competitiveness cap for a much more reliable supplier. A supplier can never win on margin alone."
3. 👆 Switch the view to **Clean Feed API**.
   🎙 "API customers get exactly the same answer as data: canonical rooms, one offer per term, and backup suppliers."
4. 👆 Click **Optimization** in the sidebar. Click **Run 50,000 searches** and wait for the table.
   🎙 "In simulation, with the same agents and suppliers, the clean shelf earns more per search, with fewer failed bookings and wrong-room incidents. Simulated, not measured, and labelled that way."

---

## 8 · Search ranking (7:35–8:15)

1. 👆 Click **Search Ranking**. Switch **Agent profile** between *Riya* and *Mark*.
   🎙 "Agents are different. A Delhi family-holiday agent and a US luxury advisor get different first pages for the same search, each with the eligible offer and why it's there."
2. 👆 Click **Experiments**.
   🎙 "Before changing ranking for real traffic, the team compares strategies here: positions, offers, and offline ranking quality."

---

## 9 · Measured, and traceable (8:15–9:10)

1. 👆 Click **Analytics**.
   🎙 "The matching is measured on held-out hotels: precision and recall above ninety-eight percent, and zero contradictions in the catalog. Sightseeing keeps products and options apart just as reliably."
2. 👆 Click **Quality & Audit**.
   🎙 "And everything we just did, the confirmed match, the import, the simulation, is in an append-only audit trail: who, when, what changed, and why."
3. 👆 Click **Overview** and hold.
   🎙 "LedgerBot: one trustworthy catalog, decisions you can explain and undo, and offers chosen for value and reliability. Built on TBO's data, ready for a shadow pilot. I'm Anshuman, for TravellerTech. Thank you."
4. 👆 Stay silent 2 seconds, stop recording.

---

## If you run long (cut in this order)

1. Section 8 step 2 (Experiments).
2. Section 4 (Policies).
3. Section 7 step 3 (Clean Feed API).
4. Section 3 step 5 (supplier conflict).
5. Section 2 step 3 (Rooms).

## Final checklist

- [ ] Workspace reset before recording; identity is Dev Admin.
- [ ] Simulated fault cleared and booking stream stopped after Section 6.
- [ ] "Simulated" said for the supplier simulation and the commercial replay; "synthetic" for the data.
- [ ] Numbers you said match the screen.
- [ ] Final length under 10:00; subtitles burned in; audio checked.
