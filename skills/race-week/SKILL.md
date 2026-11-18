---
name: race-week
description: "Race-week preparation, seven days out through race morning: confirm the goal, taper check, forecast, pace chart at course markers, watch workout check, fueling and kit from what was rehearsed, logistics timeline. Use for \"race week\", \"race plan\", \"what should I do this week before my race\", or as a scheduled task seven days before the race."
---

# Race week

Run it seven days out, then again two days out (forecast, kit, watch). Race morning is `session-brief`. Shared rules: `../../reference/decision-rules.md`, `../../reference/propagation.md`, `../../reference/garmin.md`. Method: `../../docs/methodology.md`. Tools: `../../tools/coach.py`.

## 1. Is the goal settled?

- If `goal.status` is `provisional`, settle it now. If the decision session was run, apply the rule and ask the runner to confirm. If it was never run, do not invent a result: propose the conservative tier and ask.
- Nothing about the goal changes after this point without the runner asking. Race week is not the time to chase a faster tier.
- After a confirmed change: regenerate and sweep (`reference/propagation.md`).

## 2. Taper check

From the snapshot, after a fresh sync:

- Volume this week against the plan. The taper cuts volume, keeps how often the runner runs, and keeps a short race-pace session.
- No new workouts, no make-up sessions for anything missed, no new strength work, no new shoes.
- Recovery signals. A dip in HRV or a restless night in race week is common and is not a reason to change the goal. Illness is: say so and suggest the runner decide with a clinician if there is fever or chest symptoms.

## 3. The race plan

- **Pace chart:** `coach.py chart plan.json`. Give elapsed time at each course marker and at halfway. The runner paces by the markers, because the watch reads long and its average pace will flatter them. Mention what the watch will roughly show.
- **Effort plan in three parts**, from the runner's own history rather than a template: the opening (at or just slower than goal pace; quote their fastest recent opener as the thing not to repeat), the middle (hold the band; the heart-rate cap is the brake), the close (when they may go, by distance).
- **Heart-rate cap** for the race from `bands.goal.hr_cap`, and that heart rate drifts up late in long races so the cap applies to the first two thirds.
- **Course:** hills, turns, wind exposure from the plan's course notes. If the notes are thin, ask.

## 4. Forecast (seven days out, then two)

Use a weather tool if one is available, at the race location and start time. Report temperature, wind, rain. Heat and strong wind change the plan: say by how much you would slow the opening and that the heart-rate cap matters more than pace in heat. If no weather tool is available, say so and ask the runner to check.

## 5. Fueling, caffeine, kit

- Only what the plan shows was rehearsed (`logistics` entries marked done, or confirmed by the runner). Nothing new on race day.
- Carbohydrate before and during, by distance: see `docs/methodology.md`. A 5K or 10K needs no fuel during the race.
- Kit: race shoes (the pair used in the decision session), clothing for the forecast, bib, gels, watch charged.

## 6. Watch and surfaces

- `get_scheduled_workouts` for race day and the remaining sessions; confirm targets match the plan. Fix and re-sync if not.
- The race-day calendar event carries the pace chart and the timeline.

## 7. Timeline

A dated list from now to the start: the remaining runs with targets, the dated logistics items, travel, bib pickup, bedtime, breakfast time, arrival, warm-up, start. Ask for anything unknown rather than guessing it.

## 8. After the race

Tell the runner two things will be asked for afterwards: the official chip time (a PR and the watch correction are only recorded from it), and a recovery check four days later. Offer to schedule `race-review` for both.
