# LedgerBot: recording guide
### TBO VoyageHack 4.0 · Problem 3 · Team TravellerTech · narrated by Anshuman

This is a run sheet. Each scene is a list of steps. Every step tells you **what to do on screen** (👆) and then **exactly what to say** (🎙). Do one step, say its line, move to the next.

**Length:** about 9 min 40 s (about 1,100 spoken words at a calm pace, plus the moments where you stay quiet). TBO's limit is 10 minutes.
**What you need:** the app at http://localhost:5174, the deck in a second window, a screen recorder, a mic.

---

## Before you start (5 minutes)

1. **Start the app** (skip if it's already running). In PowerShell:
   `cd "D:\Coding\PROJECTS\TBO\TESSERA Unified Supply Intelligence\tessera"; .venv\Scripts\python dev.py`
   Wait until http://localhost:5174 shows "Nine listings."
2. **Open http://localhost:5174/?short=1** in Chrome or Edge and press **F11** for full screen. Set the screen to 1920×1080 if you can. (`?short=1` makes **Next** skip the optional Ranking scene. Use plain http://localhost:5174 if you want to include it.)
3. **Click once anywhere on the page** so it listens to your keys.
4. **Click Reset** (bottom right). A "Demo state reset" message flashes; wait until it disappears.
5. **Open the deck** in present mode in a second window. You'll switch to it four times (marked **DECK**).
6. **Start recording** (Win + Alt + R, or OBS at 1920×1080, 60 fps). Stay silent for 2 seconds before you speak.

### How to move around
- **Next scene:** click **Next: …** (bottom right, blue) or the big **›** arrow on the right edge, or press **→**.
- **Previous scene:** **Back** (bottom right), the **‹** arrow, or **←**.
- **Something went wrong?** Click **Reset**, go back to the scene, and redo it. You can record every scene as its own clip and join them later.
- **Forgot a key?** Click **Keys** (bottom right) or press **P**.

### Rules for what you say
- Say the lines in your own words if you like, but **keep the numbers exactly as written**. If the screen shows a different number, say the screen's number.
- Say **"simulated"** for the bookings, the replay and the LLM-only column, and **"illustrative"** for the crore figures. Always say "at three minutes a record" with the mapping hours.
- Short sentences. Pause after every number.

### Easiest way to record alone (recommended)
Record in **two passes**: first record the screen while you follow the 👆 steps **without talking**. Then play the video back and record your voice reading the 🎙 lines over it. You never have to click and talk at the same time.

---

## Scene 00 · Cold open (0:00–0:30)

**You start on:** "Nine listings." Nine supplier rows for one Atlantis The Palm room.

1. 👆 Do nothing for 2 seconds.
   🎙 "These are nine listings from five suppliers."
   *(short pause)*
   🎙 "They're all the same room."
2. 👆 Click **Fold into one card** (top right) or press **Space**. Let the animation finish before you speak.
   🎙 "TBO's agents untangle this thousands of times a day. Get it wrong, and a family lands in Dubai to the wrong room."
3. 👆 Point the mouse at the orange counter, top left, for a second.
   🎙 "We built LedgerBot: it gets it right, proves it, and learns from every booking. Everything here is running code, and this counter keeps score as we go."

---

## DECK · Cover slide (0:30–1:00)

👆 Switch to the deck, cover slide.

🎙 "I'm Anshuman, from team TravellerTech, with Parv and Aarav.
TBO gets the same hotel, room and tour from many suppliers: direct contracts, bed banks, and three acquired stacks: BookaBed, Jumbonline and Classic Vacations.
Hotels and ancillaries are about eighty-six percent of revenue, and TBO's IPO prospectus names manual mapping as a risk. So this is core business, not cleanup."

👆 Switch back to the app. Click **Next: The Mess**.

---

## Scene 01 · The 20-second challenge (1:00–1:40)

**You start on:** two panels. Left "Today: raw supplier feed", right "LedgerBot". The target on top: *Deluxe King · Breakfast · Free cancellation · cheapest.*

1. 👆 Do nothing yet.
   🎙 "Twenty seconds: find the cheapest Deluxe King with breakfast and free cancellation."
2. 👆 Click **Start left** (or press **1**). Really try to find it in the left list; let the timer run out and turn red.
   🎙 *(while you search)* "Same hotel, different names. 'BB', 'AD', 'B&B': all breakfast. Duplicates everywhere, and a couple of rates sit on the wrong room."
3. 👆 When the left timer is red, click **Start right** (or press **2**). In the right panel, find the **Deluxe King** row with the **BB · free cancel** chip at the cheapest price and click it. It flashes green.
   🎙 "Now with LedgerBot." *(click)* "Sixty-one rows became twelve clean cards. Nothing hidden; every alternative is one click away."

*If you click the wrong thing, click **Clear** (or press **0**) and start again.*

---

## DECK · "Typical AI build vs LedgerBot" slide (1:40–2:10)

👆 Switch to the deck, the "Typical AI build vs LedgerBot" slide.

🎙 "The obvious 2026 build asks a large language model about every pair. At TBO's scale that's slow and costly, has no known error rate, contradicts itself, and merges things that must stay apart, like breakfast-refundable and room-only non-refundable.
So we use AI where it pays: a small model for the easy millions, the LLM for the hard cases, and a person only when neither is sure."

👆 Switch back to the app. Click **Next: Live Onboarding**.

---

## Scene 02 · A new supplier, mapped live (2:10–3:05)

**You start on:** the Dubai supply graph (dots and tinted circles). On the left, the orange **NovaBeds** card.

1. 👆 Do nothing yet.
   🎙 "This is TBO's supply graph: every dot a supplier record, every cluster one real hotel.
   A new supplier just signed: NovaBeds, 802 hotels. Today that's weeks of manual mapping."
2. 👆 Click **Click to onboard NovaBeds** on the left card (or press **O**). Orange dots start flying in. Don't touch anything until the green banner appears (about 50 seconds).
   🎙 "LedgerBot finds candidates by location, name, meaning and photos, never comparing all pairs: 99.3 percent less work, and 100 percent of true matches still caught. A small model scores each pair in milliseconds."
3. 👆 Keep watching. The counter top left climbs.
   🎙 "Orange dots that snap in were merged automatically. New hotels get their own spot. Anything uncertain pulses yellow and goes to a person; the LLM is switched off in this recording."
4. 👆 Wait for the green banner at the bottom.
   🎙 "About fifty seconds: 730 records merged automatically, 71 new hotels, one sent to a human, zero contradictions."

👆 Click **Next: The Inspector**.

---

## Scene 03 · Every merge has a reason, and try to fool it (3:05–4:10)

**You start on:** the Inspector showing Atlantis The Palm. Tabs top right: **Hotel · Rooms · Activities · Try to fool it**.

1. 👆 Do nothing; let the viewer see the table and the evidence bars on the right.
   🎙 "Every merge comes with its evidence. Atlantis The Palm, from five suppliers: same phone, same name once cleaned, 157 metres apart."
2. 👆 Click **Show a near-miss** (top of the right card) or press **N**.
   🎙 "The hard case: Atlantis The Royal. Same brand, same island, but a different street address and a sub-brand conflict, so they stay separate."
3. 👆 Click the **Rooms** tab (or press **M**).
   🎙 "Our key design idea: the room is not the offer. 'Deluxe King, Sea View' is the physical room; breakfast and cancellation are the offer. The grey lines are what suppliers actually sent. One room, separate offers, suppliers competing inside each."
4. 👆 Click the **Activities** tab (or press **A**).
   🎙 "Tours work the same way, on the industry's OCTO model."
5. 👆 Click the **Try to fool it** tab (or press **F**). Then click the **Sister property** chip (or press **3**). Wait until the green AUTO-MERGE card appears.
   🎙 "Now, try to fool it. The sister property's listing: parsed, matched, scored, and it joins The Royal, not The Palm."
6. 👆 Click the **Spanish room name** chip (or press **4**). Wait for the green card.
   🎙 "A Spanish room name, 'Habitación Doble Deluxe Vista Mar, AD': a Deluxe sea-view room, breakfast as the offer. Matched."

*Don't use the "Wrong pin" chip unless it shows the amber HUMAN REVIEW card in your take; its result sits right on the threshold. If it does show HUMAN REVIEW, you can say: "Name matches, location doesn't, no phone or address to settle it. So it says: I'm not sure, sending to a human."*

👆 Click **Next: Human Review**.

---

## Scene 04 · When it isn't sure, a person decides (4:10–4:40)

**You start on:** "When it isn't sure, a person decides in seconds." Top right: 99.95% and 101. Below, one pair of listings side by side.

1. 👆 Do nothing for 2 seconds.
   🎙 "How much does the AI decide alone? 99.95 percent of candidate pairs. 101 need a person.
   This is their queue: most uncertain first, with the model's own evidence."
2. 👆 Look at the **Agreement** badges, then click **Same hotel** (or press **S**) or **Different** (or press **D**). Do this for two pairs. Decide honestly. The median time appears in the top strip.
   🎙 "One keystroke, a few seconds, and each decision trains the next model. It knows when it doesn't know."

👆 Click **Next: Error Budget**.

---

## Scene 05 · You choose the risk; we guarantee it (4:40–5:15)

**You start on:** a big dial in the middle, a chart on the left, numbers on the right.

1. 👆 Press **↑** until the dial reads about **5%** (or drag the dial). Pause.
   🎙 "This is the core. TBO picks its risk: say, at most half a percent of automatic merges may be wrong."
2. 👆 Press **↓** slowly, one press at a time, down to about **0.5%**. Watch the review volume rise.
   🎙 "LedgerBot sets its own thresholds and proves it stays under that limit, with ninety-five percent confidence. Tighter risk, more review; looser, more automation. A business decision, with a guarantee."
3. 👆 Point the mouse at the green **Guarantee held** chip.
   🎙 "On hotels it has never seen: 0.34 percent error against a 0.5 percent budget. The guarantee held."

👆 Click **Next: Supplier Health**.

---

## Scene 06 · When a supplier goes bad (5:15–6:05)

**You start on:** five supplier cards on top, a live booking list, four hotel cards at the bottom.

1. 👆 Do nothing for 3 seconds; let the bookings scroll.
   🎙 "Matching is half the problem; the other half is which supplier to show.
   Every booking updates live reliability scores: did it confirm, did the price jump, how fast. The bookings here are simulated."
2. 👆 Click **Sabotage** on the **GlobalBeds** card (second card), or press **Shift+2**. Then **stay quiet for about 15 seconds** while red events appear and the GlobalBeds score falls.
   🎙 *(after a few seconds)* "Now GlobalBeds starts jumping prices at checkout. Nobody tells LedgerBot; it sees it in the bookings."
3. 👆 Wait until the hotel cards at the bottom switch supplier and the message appears. The counter top left now shows failed bookings avoided per day.
   🎙 "It moves about three hundred offers to reliable suppliers on its own. We don't show the cheapest offer; we show the one most likely to book, confirm and earn."
4. 👆 Click **Heal all** (or press **Shift+0**). **Important:** do this before you leave, or the replay in Scene 10 shows different numbers.

👆 Click **Next: Portal & API**.

---

## Scene 07 · One clean shelf, two channels (6:05–7:00)

**You start on:** "One clean shelf. Two channels." An agent's search page for Dubai Marina: filters on the left, hotel cards on the right.

1. 👆 Do nothing for 2 seconds.
   🎙 "TBO sells through two channels, the agent portal and the API. Both get the same clean shelf.
   Here's the agent's view: one card per hotel, one row per real room, one choice per meal plan and cancellation term, best supplier already picked."
2. 👆 Under **Meal plan**, click **Breakfast**. Then tick **Free cancellation only**.
   🎙 "Breakfast, free cancellation: two clicks. Behind this screen: 981 supplier rates, 27 real hotels."
3. 👆 Click **Clean Feed API** (top right toggle) or press **2**. Atlantis The Palm is selected.
   🎙 "API customers get it as data. Left: what five suppliers send for Atlantis The Palm, with seventeen spellings of the meal plan. Right: our response, with canonical rooms, a confirm probability per offer, and backup suppliers."
4. 👆 Click **Call live** (above the response) or press **Space**.
   🎙 "Sixty-five rates in; six rooms and twenty-five offers out, in milliseconds, with no AI call."

👆 Click **Next: The Arena**. (With `?short=1` the optional Ranking scene is skipped. Without it, the button says **Next: Ranking for Agents**; see the optional section at the end.)

---

## Scene 09 · LedgerBot vs an LLM-only pipeline (7:00–7:40)

**You start on:** the **Benchmark** table. The LLM-only column says SIMULATED.

1. 👆 Do nothing for 6–8 seconds; let the table be read.
   🎙 "Against an LLM-only pipeline: we haven't run a live LLM baseline yet, so that column is simulated, using our stated error assumptions on the same held-out pairs. Our column is measured."
2. 👆 Point at the rows as you read them.
   🎙 "Hotel matching accuracy 0.87 versus 0.91. Room-and-offer corner cases 0.70 versus 1.00. Contradictory groups 19 versus zero.
   The point: our side is measured and guaranteed. An LLM-only design can't offer either."

**Never say** "we ran an LLM-only pipeline", and don't describe a mistake in the examples carousel as something an LLM actually did. Call it "the kind of mistake we assumed".

*Optional, only if you have time: click **Judges vs Machine**, scan the QR with your phone (same Wi-Fi), vote on a few pairs (**Space** pushes the next pair), then click **Learn from your votes**. Say: "At the finale, you can play against it on your phones. Where people disagree, LedgerBot abstains, and one click retrains it on your votes. The review band started at 101 pairs; the new size is on screen."*

👆 Click **Next: Impact & Architecture**.

---

## Scene 10B · The enterprise solution (7:40–8:20)

**You start on:** the Impact replay. You'll do the architecture first.

1. 👆 Click **Architecture** (top right toggle) or press **B**. Then click **Start drawing**.
   🎙 "At TBO scale there are two paths."
2. 👆 Click **Next step** once per sentence below (or press **Space**).
   🎙 "The mapping pipeline runs off the search path: feeds stream in, get normalised, matched on CPU and decided within the error budget; the LLM handles hard cases in the background, and people handle the rest. Everything lands in a versioned hotel, room and offer graph with one-click rollback."
   🎙 "The search path only reads that graph, for the portal and the API alike: under five milliseconds per search, by design."
   🎙 "And every booking outcome flows back to retrain. It improves with use."
3. 👆 Switch to the deck, the system architecture slide, for a few seconds. Then switch to the **Scalable, feasible and cutting-edge** slide.
   🎙 "Scalable: no all-pairs comparison, and a new feed touches only what it affects. Feasible: open-source, on data TBO already logs, beside today's mapping vendor. And grounded in current research."

👆 Switch back to the app.

---

## Scene 10A · The money (8:20–9:25)

1. 👆 Click **Impact replay** (top right toggle) or press **A**. Click **Replay 50,000 searches** (or press **Space**). The two lanes race for about 12 seconds; start talking while they run.
   🎙 "In simulation, same agents, same suppliers: 22.5 percent more gross profit per search, failed bookings from 91 to 42, wrong-room incidents from 26 to 6."
2. 👆 Click the orange **counter** top left. A breakdown opens. Hold 3 seconds.
   🎙 "And the counter kept score: 5,884 duplicates removed, 421 mapping hours saved at three minutes a record, each figure labelled measured, simulated or assumed."
   *(If you recorded onboarding earlier in the same session without a Reset, the counter shows bigger numbers. Say what it shows.)*
3. 👆 Click anywhere to close it. Switch to the deck, the business impact and rollout slide.
   🎙 "At TBO's scale, thirty-one and a half thousand crore of hotel bookings a year, one percent more look-to-book is about nineteen crore a year, and a tenth of a point of take rate about thirty-one crore. Illustrative; the pilot proves them.
   The plan: a three-month shadow pilot, a triggered A/B test, then every destination, sightseeing and the API feed."

---

## Scene 00 again · Close (9:25–9:40)

1. 👆 Switch back to the app. Click **Reset**. Open the scene menu in the bottom bar (the button showing the current scene name) and choose **00 Cold Open**. Click **Fold into one card**.
   🎙 "Nine listings. One room. A guarantee on every merge, one clean shelf for every channel, and a shelf that heals itself.
   I'm Anshuman, for TravellerTech. This is LedgerBot, and we'd love to build it with TBO."
2. 👆 Stay silent for 2 seconds, then stop recording. In the edit, end on black with the team name and the prototype link.

---

## Optional · Scene 08 · Same search, two agents (+25 s)

Only include this if you also cut the deck's "Scalable, feasible" slide and the Activities tab in Scene 03, to stay under 10 minutes. It goes between Scene 07 and Scene 09.

1. 👆 On **Ranking for Agents**, click **Relevance only**.
   🎙 "TBO's users are professionals. Riya in Delhi sells refundable four-star family stays; Mark in the US sells suites on the Palm. Same search, two right answers."
2. 👆 Click **+ Margin & Platinum**, wait 4 seconds, then click **+ Reliability risk**. The cards reorder.
   🎙 "TBO can blend in margin, Platinum hotels and supplier reliability, with a guardrail that keeps relevance first."

---

## If the video runs long (cut in this order)
1. The voting part of Scene 09 (already optional).
2. The deck's "Scalable, feasible" slide.
3. Step 6 of Scene 03 (Spanish room name).
4. Steps 1–2 of Scene 07 (the portal); keep the API.
5. Step 4 of Scene 03 (Activities).

## Editing tips
- Cut on actions: the fold, a click, a key press. Use short cross-dissolves (6–10 frames) between the app and the deck.
- Music: one quiet instrumental track at about −24 dB under your voice; mute it during the 20-second challenge and the sabotage.
- Burn in subtitles; judges often watch muted first.
- The bottom bar and edge arrows are visible in the recording. That's fine; you can crop them out in the edit if you prefer.

## Final checklist
- [ ] Clicked **Reset** before recording.
- [ ] Numbers you said match the screen (especially the Scene 02 time, the Scene 04 median time, the Scene 06 switched offers and the counter in the finale).
- [ ] Clicked **Heal all** in Scene 06 before the replay.
- [ ] Said "simulated" for the bookings, the replay and the LLM-only column; "illustrative" for the crore figures; "at three minutes a record" with the mapping hours.
- [ ] The deck's cover and titles say **LedgerBot**; the deck's prototype/video link is real (it was a placeholder, `example.com`).
- [ ] Final length under 10:00; subtitles burned in; audio checked on speakers and headphones.
