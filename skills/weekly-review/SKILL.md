---
name: weekly-review
description: Review the training week just ended from Garmin data (planned against run, key-session reads, recovery trend, fitness direction) and set up next week on every surface. Use for "weekly review", "how did my week go", or as a scheduled task on the evening the training week ends.
---

# Weekly review

Works on demand and unattended. Shared rules: `../../reference/data-quality.md`, `../../reference/decision-rules.md`, `../../reference/propagation.md`, `../../reference/garmin.md`. Tools: `../../tools/coach.py`.

## 0. Context

- Read `athlete.md` and `plan.json`. If no block is active (between races), do the recovery and load parts only and say so.
- If Garmin cannot be reached after one retry: stop. Unattended, send one short message saying the computer needs to be awake with the Claude desktop app open. Do not report from stale data.

## 1. Pull the week

Everything `log-run` step 1 pulls, for the Monday-to-Sunday week just ended, with 28 days of HRV and 12 weeks of VO2max. Then `get_scheduled_workouts` for the next 7 days. Save under `data/raw/` and run `coach.py sync plan.json --raw data/raw --out dashboard --write-plan`.

## 2. Analyse

Data-quality flags come first and are stated before any conclusion.

- **Planned against run:** a table of day, planned, ran (distance, pace, heart rate), status (done, moved, missed, substituted).
- **Volume:** distance run against planned, and the week-on-week change.
- **Key sessions:** reps, heart rate, fade, jog heart rate, efficiency, form; adherence to the band and cap. State `over_prescription_streak` as a number.
- **Recovery trend:** 7-day HRV against the runner's baseline band, resting heart rate, sleep. Apply the HRV rule exactly: it needs both signals.
- **Fitness direction:** VO2max over four weeks (`vo2_note`; under 0.5 is noise). Easy-run efficiency only between runs with similar climb per km.
- **Logistics:** which dated strength, fueling, shoe and caffeine items were due this week and whether they happened. Ask if unknown.
- **Max heart rate test:** if it was scheduled and not run, reschedule it inside the next seven days. It does not get dropped.

## 3. Next week

- Each day's session with exact targets: pace band, heart-rate cap, distance.
- Apply the standing rules to adjust. Small schedule moves are fine. A change to the goal or to a pace band needs the runner's confirmation: when unattended, propose it and do not write it.
- One execution cue for the week, taken from recent history ("two sessions in a row faster than the band: open the first rep at the slow end").
- The dated logistics items falling in the week.
- Check the watch: every key session next week must appear in `get_scheduled_workouts` with the plan's targets.

## 4. Propagate

Follow `reference/propagation.md`.

## 5. Output

- In conversation: the table, three bullets (fitness, control, recovery), next week's sessions, what changed.
- Unattended: send the same summary to the runner, and a notification only if something needs their decision.
