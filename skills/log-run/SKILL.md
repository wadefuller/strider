---
name: log-run
description: "After a run (or several), pull Garmin laps, judge each session against the plan, apply the plan's rules, and update Garmin, the calendar, the dashboard and the plan log in one pass. Use for \"I ran today\", \"log my run\", \"update the plan\", \"refresh the dashboard\"."
---

# Log a run

One pass that leaves every surface consistent. Shared rules: `../../reference/decisions.md`, `../../reference/data-quality.md`, `../../reference/decision-rules.md`, `../../reference/propagation.md`, `../../reference/garmin.md`. Tools: `../../tools/coach.py`.

## 0. Load context

Read `athlete.md` and `plan.json`. Run `coach.py decisions decisions.md` and apply every active entry (`reference/decisions.md`). The last entry in `plan.log` tells you the date to pull from. If a file is missing, say so and stop; do not recreate a plan from memory. If Garmin cannot be reached, follow the failure protocol in `reference/garmin.md`. Never update a surface from a guess.

## 1. Pull everything since the last log entry

- `get_activities_by_date` from the day after the last logged run through today.
- `get_activity_splits` for **every** run. For key sessions and any single-lap run, `get_activity_typed_splits` too.
- `get_recovery_time_remaining`, `get_training_readiness`, `get_hrv_trend`, `get_sleep_summary_range`, `get_vo2max_trend`, recent `get_rhr_day`.
- Save each result under `data/raw/` (`reference/garmin.md`).

## 2. Sync and read the result

Run `coach.py sync plan.json --raw data/raw --out dashboard --write-plan`, then read `dashboard/snapshot.json`.

- Runs are matched to planned days **by type within the match window** (two days by default), not by date alone. Check `days[*].status` for `moved` and `missed`, and `extras` for runs that match nothing. Record moves explicitly.
- If a match looks wrong (a substitute session, a group run in place of the prescribed workout), correct the plan by hand and sync again.

## 3. Judge each session

If the runner corrects a reading or explains why a session went off-plan in a way that should hold next time, add it with `coach.py decide` and say you have.

For each run logged, in this order:

1. **Data-quality flags first** (`flags`, `notices`). State each one and what it rules out.
2. **Key sessions:** per rep: pace, heart rate, power, fade, jog heart rate; and the form row where the watch recorded it. Then say plainly:
   - pace against the band: inside, faster, or slower;
   - heart rate against the cap, rep by rep;
   - shape: fast opener, uneven reps, power fade, jog heart rate climbing;
   - `over_prescription_streak`: **say the number** whenever it is above zero ("that is the second session in a row run faster than prescribed");
   - form: if `form.drift.drift` is true, form broke down by the last rep at the same pace. For decision sessions and the block's longest reps, run the per-second check (`reference/garmin.md`).
3. **Long and easy runs:** heart rate against the cap, and whether a prescribed finish segment was actually run. If the flag is `structure_unknown`, say you cannot tell from laps.
4. **Distance spike:** if a run carries `distance_spike`, say so with the numbers, and check the next planned long run is no longer than this run. Shorten it if it is.
5. Never describe a session from its whole-run average.

## 4. Decide plan changes

Apply the standing rules in `reference/decision-rules.md`; do not improvise.

- Recovery go/no-go for the next key session, from `recovery.verdict`.
- Missed easy run, moved long run, form drift, faster-than-prescribed streak.
- If the decision session was run, the `decision` block gives the tier. Report it, give the conservative reading, and **ask before changing the goal**. A goal change is never written without the runner's yes.

## 5. Propagate

Work through `reference/propagation.md` in order: plan, Garmin calendar, calendar events, dashboard, plan log, consistency sweep. Confirm each write.

## 6. Report back

Short, in this order. Do not recap the steps.

- A table: planned against run.
- The one or two things that matter (a fitness signal, a control signal).
- What changed and where (Garmin, calendar, dashboard, log), and anything that could not be updated.
- The next key session: date, exact targets, recovery status.
