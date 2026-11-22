# LedgerBot: recording guide (8 minutes)
### TBO VoyageHack 4.0 · Problem 3, Multi Supplier Optimization · Team TravellerTech · narrated by Anshuman, for the judges

A run sheet for an 8-minute recording of the live product. Each step says **what to do** (👆) and **what to say** (🎙). Do a step, say its line, then move on.

**Length:** 8:00. That's about 650 spoken words (under 5 minutes at a calm pace) plus clicking and waiting. Every section's slot leaves room for its clicks; the timestamps are targets, so check them when you edit.
**You stay as Dev Admin the whole time.** The admin can do everything, so there's no switching identities on camera.

---

## Before you start (5 minutes)

1. **Start the app** if it isn't running (PowerShell, in the `tessera` folder): `.venv\Scripts\python dev.py`. Wait until http://localhost:5174 shows *Operations Overview*.
2. Open the app in Chrome or Edge, full screen (F11), 1920×1080 if you can.
3. **Clean slate:** check the bottom of the sidebar says **Dev Admin**. Go to **Settings → Workspace → Reset workspace…**, reason "Recording", confirm.
4. **Get the sample feed ready:** go to **Data Ingestion**, click **Sample JSON**. The file `novabeds_sample.json` lands in your Downloads folder.
5. Click **Overview**. Start recording. Stay silent for 2 seconds.

**When you speak:** keep numbers exactly as the screen shows them; if the screen differs from this guide, say the screen's number. Say "simulated" for the supplier simulation and the commercial replay, and "synthetic" for the data.

**Easiest way alone:** record the clicks silently first, then record your voice over the video.

---

## 1 · The problem, and the platform (0:00–0:45)

**You start on:** *Operations Overview*.

1. 👆 Do nothing for 2 seconds.
   🎙 "Hello judges, I'm Anshuman from team TravellerTech, and this is LedgerBot.
   TBO gets the same hotel, room and tour from many suppliers, under different names, codes and terms. That creates duplicate results, wrong-room bookings, and the wrong supplier winning. LedgerBot is the operations platform that fixes this: one trustworthy catalog, and the best offer for every search."
2. 👆 Point across the KPI cards.
   🎙 "This is the workspace: over eight thousand supplier listings consolidated into about two and a half thousand properties and thirty-three experiences, and the matches still waiting for a person. Every number is tagged measured, simulated or live."

---

## 2 · One hotel, every supplier (0:45–1:55)

1. 👆 Press **Ctrl K**, type `atlantis the palm`, press **Enter**. Click the **Supplier records** tab.
   🎙 "Atlantis The Palm, from five suppliers: different spellings, phone formats and map pins, matched into one canonical record."
2. 👆 Click the **Offers** tab.
   🎙 "Rooms are matched on what the room physically is, never on meal plan or cancellation. Offers only compete inside the same room and terms, and each group gets one recommended offer, with its own price, deadline and payment terms, and the reasons it won."
3. 👆 Click the **Matching evidence** tab.
   🎙 "And it's explainable. Left: every link that merged these listings. Right: what was kept apart. Atlantis The Royal: same brand, same island, but a different hotel."

---

## 3 · One experience, several options (1:55–2:25)

1. 👆 Click **Inventory Catalog**, then **Sightseeing**. Search `burj`. Open **Burj Khalifa: At the Top · Levels 124/125**, then click the **Options** tab.
   🎙 "Sightseeing too. Level 148 and levels 124 and 125 are different products. Inside a product, options keep apart what the customer buys: time slot, private or shared, transfers, meals and duration. A two-hour and a four-hour tour are never merged; '4h' and '240 minutes' are recognised as the same."

---

## 4 · A person decides the hard cases (2:25–3:25)

1. 👆 Click **Match Review**. In the queue, click a case **without** the red "supplier conflict" label.
   🎙 "Most matches are automatic, within a risk budget the business sets: at most one percent of automatic merges may be wrong, certified statistically and checked on hotels the model never saw. The uncertain pairs come here."
2. 👆 Point at the comparison table, then the evidence bars.
   🎙 "Both records side by side, with the model's evidence for and against."
3. 👆 Click **Confirm match**, then **Confirm match** in the dialog.
   🎙 "I confirm. The two properties merge in the catalog, the decision is recorded with who and why, and it can be undone. If a merge would put two listings from one supplier into one hotel, LedgerBot blocks it."

---

## 5 · A new supplier feed (3:25–4:30)

1. 👆 Click **Data Ingestion**. Drag `novabeds_sample.json` from Downloads onto the drop zone (or **Browse files**). Supplier: **S6 · NovaBeds**. Click **Validate file**.
   🎙 "A new supplier, NovaBeds, sends its first feed. LedgerBot validates it before anything changes, and shows every issue up front."
2. 👆 Click **Import 40 valid records**, then **Start import**. Wait for **Completed**.
   🎙 "On confirmation, every record runs through the same matching pipeline. Hotels we already have are merged; genuinely new ones become new properties; anything ambiguous goes to review. What used to take weeks of manual mapping takes seconds, and every outcome is recorded."

---

## 6 · When a supplier degrades (4:30–5:25)

1. 👆 Click **Suppliers**, then **GlobalBeds**, then the **Reliability** tab.
   🎙 "Each supplier has a reliability score: how often bookings confirm at the quoted price."
2. 👆 Under *What-if*, keep **Price changes at booking** and **35%**. Click **Start simulation**, then **Start simulation** in the dialog. Stay quiet for about 15 seconds.
   🎙 *(after a few seconds)* "This is a simulation. GlobalBeds starts changing prices at checkout. Nobody tells LedgerBot; its score falls only as simulated bookings fail."
3. 👆 When the orange message about offer groups appears, point at it. Then click **Clear simulated faults** and **Stop booking stream**.
   🎙 "And offer selection reacts on its own, moving these offer groups to more reliable suppliers."

---

## 7 · The best offer, and what it's worth (5:25–6:35)

1. 👆 Click **Offer Intelligence**. Search `atlantis the palm` and select it. Under *Requirements*, click **BB** and choose **Free cancellation only**.
   🎙 "Revenue teams compare every supplier offer under the customer's needs: here, breakfast and free cancellation."
2. 👆 Point at a recommended row and its reasons. Then set **Compare offers by** to **Identical rate plan**.
   🎙 "The pick is explained: lowest price, or a small premium within a competitiveness cap for a far more reliable supplier. A supplier can never win on margin alone. And analysts can go strictly like for like: same deadline, same payment terms."
3. 👆 Click **Optimization** in the sidebar. Click **Run 50,000 searches** and wait for the table.
   🎙 "What is it worth? In a simulation with the same agents and suppliers, the clean shelf earns more gross profit per search, with fewer failed bookings and wrong-room incidents. That's simulated, and labelled that way; a shadow pilot measures it for real."

---

## 8 · Search ranking (6:35–7:05)

1. 👆 Click **Search Ranking**. Switch **Agent profile** between *Riya* and *Mark*.
   🎙 "Different agents get different first pages for the same search: a Delhi family-holiday agent and a US luxury advisor. Every result shows one real, bookable offer, the same offer the ranking model scored."

---

## 9 · Measured, traceable, ready (7:05–8:00)

1. 👆 Click **Analytics**.
   🎙 "The matching is measured on held-out hotels: precision and recall above ninety-eight percent, and zero contradictions in the catalog."
2. 👆 Click **Quality & Audit**.
   🎙 "Everything I just did, the merge, the import, the simulation, is in an append-only audit trail."
3. 👆 Click **Overview** and hold.
   🎙 "This runs today on synthetic supplier feeds built to behave like real ones, and it is ready to plug into TBO's sandbox data in the prototype round. LedgerBot: one trustworthy catalog, decisions you can explain, and offers chosen for value and reliability. I'm Anshuman, for TravellerTech. Thank you."
4. 👆 Stay silent 2 seconds, stop recording.

---

## If a take runs over 8:00 (cut in this order)

1. Section 8 (ranking), about 30 s.
2. Section 7, step 2, the second half (identical rate plan), about 10 s.
3. Section 2, step 3 (matching evidence), about 20 s.

## Final checklist

- [ ] Workspace reset before recording; identity is Dev Admin; the sample file is in Downloads.
- [ ] Simulated fault cleared and booking stream stopped after Section 6.
- [ ] "Simulated" said for the supplier simulation and the replay; "synthetic" for the data.
- [ ] Numbers you said match the screen.
- [ ] Final length 8:00 or less; subtitles burned in; audio checked on speakers and headphones.
