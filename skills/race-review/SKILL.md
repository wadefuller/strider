---
name: race-review
description: Review a completed race from its laps (result against goal, pacing shape, heart-rate drift, form, conditions), record the official chip time and watch-distance correction, and run the post-race recovery check before training resumes. Use for "how did my race go", "race review", "race debrief", and as a scheduled recovery check four days after a race.
---

# Race review and recovery check

Two parts, usually days apart. Shared rules: `../../reference/data-quality.md`, `../../reference/propagation.md`, `../../reference/garmin.md`. Tools: `../../tools/coach.py`.

## Part 1: the race (as soon as it has synced)

### 1. Find it and pull it

- `get_activities_by_date` for race day. The race is the long one; warm-up and cool-down are separate activities. Do not rely on `event_type` being `race`; many runners never tag it.
- `get_activity_splits`, `get_activity_typed_splits`, `get_activity`, `get_activity_weather`. Save under `data/raw/`.
- Per-second form (`reference/garmin.md`) is worth pulling for a half marathon or marathon.

### 2. Ask for the chip time first

"What was your official chip time?" Until the runner gives it:

- the result is reported as **watch time**,
- no PR is recorded,
- no watch-distance correction is stored.

Do not adjust the GPS time yourself and call it a result.

### 3. Analyse

`coach.py review plan.json --splits data/raw/splits/<id>.json --chip <H:MM:SS>` gives halves, the opening against average pace, the close against the middle, heart rate per unit of speed between halves, the result against the goal, and the watch-distance factor. Add:

- **Data quality first:** altimeter and power caveats, heart-rate lag in the first kilometre or mile.
- **Pacing against the plan:** did the opening match the race-week plan? Where did pace move, and did heart rate lead it or follow it?
- **Conditions:** temperature and wind from `get_activity_weather` against the forecast.
- **Form late in the race**, if per-second data was pulled: when ground contact and cadence started to change.
- **What the block showed that the race confirmed or contradicted.** Use the plan log: the decision-session tier, the faster-than-prescribed streak, missed sessions.

### 4. Record

After the chip time is given:

- `athlete.md`: the PR table (if it is one), and `watch distance factor` (median across certified races).
- `plan.json`: race day `status: done` and `actual`; a line in `plan.log`; `athlete.watch_distance_factor` if it changed. Then propagate (`reference/propagation.md`).
- Threshold heart rate or max heart rate only if the race gives clear evidence, and say what the evidence is.

### 5. Report

The result against the goal, three things that went to plan or did not, with numbers, and one thing to carry into the next block. No score out of ten. Then set the recovery check: four days after the race, and say what it will look at.

## Part 2: the recovery check (four days after, then weekly until clear)

1. Pull `get_hrv_trend`, recent `get_rhr_day`, `get_recovery_time_remaining`, `get_sleep_summary_range`, `get_training_readiness`; save and run `coach.py recovery-check plan.json --raw data/raw`.
2. Ask the three questions it returns: any pain that changes how you run, soreness on stairs out of 10, do you want to run yet.
3. Read the verdict:
   - `easy_only`: a signal is still off. Easy running or rest, check again in three days.
   - `easy_running_ok`: signals are normal, but it is too soon after the race for hard running. Easy runs only until the earliest-quality date.
   - `quality_ok`: signals normal and enough days have passed. Hard sessions can resume, starting short.
   - `unknown`: Garmin data was missing. Say so; go by the three answers and stay easy.
4. Pain that changes how the runner moves overrides every signal: no running, and suggest a clinician. This check is not medical advice.
5. Offer the next step: an easy fortnight, then `setup` (to refresh the profile from the block) and `build-block` for the next race.
