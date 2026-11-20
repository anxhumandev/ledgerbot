# LedgerBot: video script (one narrator)
### TBO VoyageHack 4.0 · Problem 3 · Team TravellerTech · narrated by Anshuman

**Runtime:** about 9 minutes, about 1,150 words at a calm 135 words per minute.
**Sources:** **[PROTO]** is the LedgerBot prototype (scene numbers match the app). **[DECK]** is the 6-slide proposal deck.
**Story:** this is TBO's next supply platform. The prototype is the proof; the deck is the plan.

---

## How to use this script

- **SAY** is your narration. Loosen it into your own voice; keep the facts.
- **DO** is what you press. Every key also has an on-screen button, but in recording mode (`?record=1`) the on-screen controls are hidden, so use the keys.
- **Numbers** are the values the prototype shows after a reset (`R`), measured on our recording build. Two depend on timing and can differ slightly in your take: the onboarding time in Scene 02 and the number of switched offers in Scene 06. If the screen shows a different value, say the screen's value. Never say a number that isn't on screen or in the deck.
- **Two-pass recording (strongly recommended, since you are alone):** pass 1, record the screen while you operate it, silently. Pass 2, record your voice over the edited footage. You never have to talk and press keys at the same time.

---

## Before you hit record (5 minutes)

1. Start the app from the `tessera` folder: `.venv\Scripts\python dev.py`. Wait until http://localhost:5174 shows the cold open.
2. Open **http://localhost:5174/?record=1** in the browser, press **F11** (full screen), set the screen to 1920×1080.
3. Click once on the page so it has keyboard focus, then press **R** (reset). Nothing appears on screen when you reset in recording mode; that is intended.
4. Have the deck open in present mode in a second window for the slide sections.
5. Start screen capture (60 fps). Leave 2 s of stillness at the start and end of each scene for clean cuts.

If anything ever looks wrong mid-take: press **R**, go back with **←**, and redo that scene. Each scene can be recorded as its own clip.

---

## 0:00–0:30 · COLD OPEN: "Nine listings. One room." [PROTO 00]

**ON SCREEN:** nine supplier rows for one Atlantis The Palm room: different names, codes and prices, from five suppliers.
**DO:** hold 2 s in silence. Press `Space`: the rows slide together and fold into one card.

> **SAY:** These are nine listings from five suppliers.
> *(beat)*
> They're all the same room.
> *(`Space`, the rows fold into one card)*
> Every day, TBO's agents have to work this out themselves, thousands of times, on every search. And when somebody gets it wrong, a family arrives in Dubai to the wrong room.
> We built LedgerBot: a system that gets it right, proves it, and gets smarter with every booking.

**Note:** don't talk over the fold animation. Let it land, then speak.

---

## 0:30–1:00 · WHO WE ARE AND WHY IT MATTERS [DECK: Cover]

> **SAY:** I'm Anshuman, from team TravellerTech, with Parv and Aarav. This is LedgerBot.
> TBO receives the same hotel, room and tour from many suppliers: direct contracts, bed banks, and now three acquired supply stacks: BookaBed, Jumbonline and Classic Vacations.
> Hotels and ancillaries are about eighty-six percent of TBO's revenue, and TBO's own IPO prospectus lists manual mapping as a business risk.
> So we treated this as the core of the business, not a cleanup job.

---

## 1:00–1:45 · THE 20-SECOND CHALLENGE [PROTO 01]

**ON SCREEN:** left, "Today: raw supplier feed" (about 60 rows); right, LedgerBot's clean cards. Target on top: *Deluxe King · Breakfast · Free cancellation · cheapest.*
**DO (screen pass):** press `1` and genuinely hunt on the left; let the timer run out. Press `2`, find the Deluxe King breakfast/free-cancel chip on the right and click it (green flash). Press `0` if you need to redo it.

> **SAY:** Let's make it real. Twenty seconds to find the cheapest Deluxe King with breakfast and free cancellation, the kind of request agents get every day.
> *(left timer running)*
> Same hotel, different names. "BB", "AD", "B&B": all the same breakfast. Many of these rows are duplicates, and a couple are even attached to the wrong room.
> *(timer runs out and turns red)*
> Now the same search, with LedgerBot.
> *(right side, one click, green)*
> Sixty-one rows became twelve clean cards. Nothing was hidden; every alternative is one click away. It's organised the way an agent thinks.

---

## 1:45–2:20 · WHY THE OBVIOUS AI SOLUTION FAILS [DECK: Typical AI build vs LedgerBot]

> **SAY:** The obvious answer in 2026 is to ask a large language model: "are these two the same hotel?"
> At TBO's scale that has four problems.
> One, cost and speed: about ten billion searches a year at IPO, and LLM calls cost cents and take seconds.
> Two, no known error rate: "ninety-five percent confident" is not a guarantee.
> Three, its answers contradict each other: A equals B, B equals C, but A doesn't equal C.
> Four, it merges things that must stay separate: "breakfast, free cancellation" is not "room only, non-refundable".
> So we use the LLM only where it earns its cost, and built everything else to be measurable.

---

## 2:20–2:35 · THE SIX CAPABILITIES [DECK: Six capabilities]

> **SAY:** LedgerBot has six capabilities: guaranteed accuracy, rooms and offers kept apart, one truth per hotel, self-healing suppliers, the best offer rather than the cheapest, and ranking built for agents. Here they are, running.

---

## 2:35–3:20 · A NEW SUPPLIER, MAPPED LIVE [PROTO 02]

**ON SCREEN:** the Dubai supply graph: every dot a supplier record, every soft circle one real hotel. The NovaBeds card on the left, the five-stage funnel on top.
**DO:** press `O`. Orange NovaBeds dots fly in and snap into clusters. Let it run to the green banner (under a minute). Stay on the wide shot.

> **SAY:** This is TBO's supply graph. Every dot is a supplier record; every cluster is one real hotel.
> A new supplier just signed: NovaBeds, 802 hotels and 3,416 rooms. Today that means weeks of manual mapping.
> *(press `O`)*
> First, LedgerBot finds candidates cheaply: by location, by name, by meaning, and by matching photos. It never compares all pairs; that cuts the work by 99.3% and still catches 100% of the true matches.
> Then a small learned model scores each pair in milliseconds.
> *(orange dots snap into clusters)*
> Each orange dot that snaps into a cluster was merged automatically. Brand-new hotels get their own spot. Anything it isn't sure about pulses amber and goes to a human. In production an LLM looks at those first; in this recording the LLM is switched off, so they go straight to review.
> *(green banner)*
> About fifty seconds. 730 records, 91 percent, merged automatically; 71 brand-new hotels created; one sent to a human. Zero contradictions.

---

## 3:20–4:15 · EVERY MERGE HAS A REASON [PROTO 03]

**ON SCREEN:** the Inspector on Atlantis The Palm: golden record, a row per supplier, the explanation waterfall on the right.
**DO:** hold on the hotel → press `N` (near-miss) → `M` (Rooms) → `A` (Activities).

> **SAY:** Every merge is explainable. Here's Atlantis The Palm from five suppliers: the same phone number, identical names once the noise is cleaned up, and 157 metres apart. That's why it merged.
> Now the hard case.
> *(`N`: Atlantis The Palm vs Atlantis The Royal)*
> Two Atlantis hotels: same brand, same island. A naive system merges them. LedgerBot sees different street addresses and a sub-brand conflict, Palm versus Royal, and keeps them separate.
> *(`M`, Rooms tab)*
> This is the key idea in our design: we separate the **room** from the **offer**. "Deluxe King, Sea View" is the physical room. Breakfast, cancellation and payment terms are the offer. The grey lines under each room are the names suppliers actually sent: bed-bank codes, Spanish, marketing names. They become one room, but the breakfast rate and the room-only rate stay separate choices, and suppliers compete inside each one.
> *(`A`, Activities tab)*
> Tours follow the same logic, the industry's OCTO model. Burj Khalifa level 148 and levels 124/125 are different products; prime time and non-prime are options of one product.

---

## 4:15–4:50 · TRY TO FOOL IT [PROTO 04]

**ON SCREEN:** the "Try to fool it" card with five presets.
**DO:** press `2` (Wrong pin, 400 m off). Wait for the amber "HUMAN REVIEW" card. Then press `4` (Spanish room name).

> **SAY:** Let's try to fool it. I'll take a real hotel, Address Downtown, drop the phone and address, and move its pin four hundred metres.
> *(trace: parsed → candidates → scored → amber)*
> It found the right hotel. But the name matches and the location doesn't, and there's no phone or address to settle it. So it says: "I'm not sure, sending to a human," and shows exactly why.
> That's what you want from a production system: it knows when it doesn't know.
> *(`4`)*
> And a room name in Spanish, "Habitación Doble Deluxe Vista Mar, AD"? Parsed as a Deluxe sea-view room with breakfast as the offer, and matched.

---

## 4:50–5:30 · YOU CHOOSE THE RISK. WE GUARANTEE IT. [PROTO 05]

**ON SCREEN:** the dial, the automation-vs-risk chart, stats on the right.
**DO:** press `↑` until the dial reads about 5%, pause, then press `↓` slowly, one press at a time, down to about 0.5%. (A USB MIDI knob on CC 1 also works if you have one.)

> **SAY:** This is the core of the platform.
> TBO decides how much risk it accepts. Say, at most half a percent of automatic merges may be wrong.
> *(turn down slowly; review volume rises)*
> LedgerBot then sets its own thresholds using Learn-then-Test, a conformal risk-control method that guarantees that ceiling with ninety-five percent confidence.
> Tighter risk, more human review. Looser risk, more automation. It's a business decision, and now it comes with a guarantee.
> *(point at the green chip)*
> And on hotels the model has never seen: 0.34 percent actual error against a 0.5 percent budget. The guarantee held.

---

## 5:30–6:20 · WHEN A SUPPLIER GOES BAD [PROTO 06]

**ON SCREEN:** five supplier health cards, the live booking ticker, four hotel cards showing their chosen supplier.
**DO:** hold 3 s on the calm state. Press `Shift+2` (sabotage GlobalBeds). Stay quiet for about 15 s while the score drops and the hotel cards switch supplier. `Shift+0` heals afterwards.

> **SAY:** Matching is half the problem. The other half is choosing which supplier to show.
> Every booking teaches LedgerBot something: did it confirm, did the price jump, how long did it take. These are live reliability scores, with uncertainty bands. The bookings here are simulated.
> Now a supplier starts misbehaving.
> *(`Shift+2`; red events appear; the GlobalBeds score slides)*
> Price jumps at checkout. Nobody told LedgerBot. It notices from the bookings themselves.
> *(hotel cards switch supplier; message appears at the bottom)*
> And it moves about three hundred offers to more reliable suppliers, on its own. The shelf heals itself.
> We don't show the cheapest offer. We show the one most likely to book, confirm and earn: probability of booking, times probability of confirming, times margin.

---

## 6:20–6:50 · SAME SEARCH, TWO AGENTS [PROTO 07]

**ON SCREEN:** Riya (Delhi, family packages) and Mark (US luxury advisor), top 6 results each.
**DO:** press `1`, then `2`, then `3`, about 4 s apart. The cards reorder.

> **SAY:** TBO's users are professionals who come back every day. Riya in Delhi sells refundable four-star family stays. Mark in the US sells suites on the Palm. Same search, two different right answers.
> *(`2`, then `3`)*
> On top, TBO can blend in margin and its Platinum partner hotels, and supplier reliability, with a guardrail that keeps relevance first. And we correct for the fact that people click what's on top, not just what's best.

---

## 6:50–7:40 · LEDGERBOT VS AN LLM-ONLY PIPELINE [PROTO 08]

**ON SCREEN (A):** the benchmark board. LedgerBot's column is measured; the LLM-only column is labelled **simulated**.
**DO:** hold on the table 6–8 s. Optional: press `B` for the voting view and vote from your own phone (scan the QR; phone on the same Wi-Fi). Skip the voting if you're short on time; the 6-minute cut drops it anyway.

> **SAY:** How does that compare with an LLM-only pipeline? We haven't run a full live LLM baseline yet, so this column is a simulated profile: the error rates are our stated assumptions for a zero-shot model judging one pair at a time, listed in our code, applied to the hardest-looking pairs of the same held-out test set. LedgerBot's column is measured.
> *(read from the table)*
> Under those assumptions: hotel F1 0.87 versus 0.91. Room-and-offer corner cases: 0.70 versus 1.00. Contradictory groups: 19 versus zero.
> The point isn't the exact simulated number. It's that LedgerBot's side is measured and guaranteed, and an LLM-only design can't give you either.
>
> *(optional voting, `B`)* At the finale, the judges can play against it. Scan, and vote "same", "different", or "same room, different offer".
> *(after a few pairs, press `L`)* On pairs where people disagree, LedgerBot abstains, and with one click it retrains on the votes and re-certifies its thresholds; the review band started at 101 pairs, and the new size appears on screen.

**Do not say:** "we ran an LLM-only pipeline", or describe a specific LLM mistake as something the LLM actually did. The corner-case carousel shows simulated answers; if it's on screen, call it "the kind of mistake we assumed".

---

## 7:40–8:20 · THE ENTERPRISE SOLUTION [PROTO 09B → DECK: System architecture]

**DO:** press `B` (Architecture), then `Space` once per step, about one step per sentence. Then cut to the deck's architecture slide.

> **SAY:** Here's how this runs at TBO scale.
> Two paths. The mapping pipeline runs continuously, off the search path: supplier feeds stream in, get normalised, matched by a small model on CPU, and decided within the guaranteed error budget. The LLM only handles hard cases, asynchronously. Everything lands in a versioned golden-record graph (hotel, room, offer) with one-click rollback.
> The search path only reads that graph: a cache lookup, the offer selector and the ranker. Our design target is under five milliseconds added per search.
> And every booking outcome (confirmations, price jumps, timeouts, complaints) flows back to update reliability and retrain. The platform improves with use.

---

## 8:20–8:35 · BUILT FOR PRODUCTION [DECK: Scalable, feasible and cutting-edge]

> **SAY:** It's scalable: we never compare all pairs, and a new feed only touches what it affects. It's feasible: an open-source stack and data TBO already logs, working alongside TBO's existing mapping vendor rather than replacing it. And it's grounded in current research: conformal risk control, distilled matching, unbiased ranking.

---

## 8:35–9:05 · THE MONEY [PROTO 09A → DECK: Business impact and rollout]

**DO:** press `A` (Impact replay), then `Space`. The two lanes race for about 12 s. Cut to the deck as the numbers settle.

> **SAY:** In simulation, with the same agents and the same suppliers, the LedgerBot shelf delivers 22.5 percent more gross profit per search, failed bookings drop from 91 to 42, and wrong-room incidents from 26 to 6.
> *(cut to deck)*
> At TBO's scale, about thirty-one and a half thousand crore of hotel bookings a year, a one percent lift in hotel look-to-book is worth about nineteen crore a year, and a tenth of a point of take rate from better offer selection is about thirty-one crore. Around fifty crore from two levers. These are illustrative; the pilot proves them.
> The plan: a three-month shadow pilot beside today's mapping, a triggered A/B test, then every destination, sightseeing, and a clean feed for API buyers.

---

## 9:05–9:20 · CLOSE [PROTO 00, folded card]

**DO:** press `R`, go to scene 00, press `Space` so the card folds, hold.

> **SAY:** Nine listings. One room. A guarantee on every merge, and a shelf that heals itself.
> I'm Anshuman, for TravellerTech. This is LedgerBot, and we'd love to build it with TBO.

End on 2 s of silence on the card, then cut to black with the team name and the prototype link.

---

# Notes

## Delivery
- Confident, not salesy. Short sentences. Pause after every number.
- Say "measured" and "guaranteed" only for LedgerBot's own numbers. Say **"simulated"** for the bookings, the A/B replay and the LLM-only column, and **"illustrative"** for the crore figures, exactly where the script does. Judges trust teams that label their own assumptions.
- Don't read slides aloud. The slides carry detail; your voice carries the story.

## Recording tips (solo)
- Two passes: silent screen capture first, voice-over second, with a USB or lapel mic in a quiet, soft room.
- Record each scene as its own clip; press `R` between takes of the same scene.
- Optional picture-in-picture: your hands on the keyboard during the 20-second challenge, or your phone voting in the arena. Skip both if short on time.
- Music: one quiet instrumental bed at about −24 dB under the voice; drop it out during the 20-second challenge and the sabotage.
- Cut on actions (the fold, the click, a key press); 6–10 frame cross-dissolves between prototype and deck.
- Burn in subtitles; judges often watch muted first.

## If you need a 6-minute cut
Drop, in this order: the six-capabilities slide; Scene 07; the voting half of Scene 08; the production slide; the Spanish example in Break It.

## Final checklist
- [ ] The deck's cover and titles say **LedgerBot** (the prototype does).
- [ ] Numbers spoken match the screen in this take (especially the Scene 02 time and Scene 06 switched offers).
- [ ] "Simulated" is said for the LLM-only column, the bookings and the replay; "illustrative" for the crore figures.
- [ ] The deck's prototype/video link is real (it was a placeholder, `example.com`).
- [ ] Runtime between 6:00 and 10:00 after editing; subtitles burned in; audio checked on speakers and headphones.
