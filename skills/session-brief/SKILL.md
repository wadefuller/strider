---
name: session-brief
description: "Morning-of brief for a key session or race: recovery go/no-go, the exact workout and targets, a check that the watch has it, weather, and one pacing cue from recent history. Use for \"what's my workout today\", on race morning, or as a scheduled task early on key-session days."
---

# Session brief

Short and phone-readable, before the runner leaves the house. Shared rules: `../../reference/decision-rules.md`, `../../reference/data-quality.md`, `../../reference/garmin.md`. Tools: `../../tools/coach.py`.

## 1. Gather (in parallel)

- `plan.json`: today's session, its targets, today's dated logistics, the standing rules. `athlete.md` for context.
- Garmin recovery: `get_recovery_time_remaining`, `get_training_readiness`, `get_hrv_trend` (7 days), `get_sleep_summary_range` (3 nights), recent `get_rhr_day`. Save to `data/raw/` and run `coach.py sync plan.json --raw data/raw --out dashboard`; read `recovery` from the snapshot.
- Garmin watch check: `get_scheduled_workouts` for today, then `get_workout_by_id`. The pace targets on the watch must match the plan (allowing for the watch-distance conversion). If they do not, fix them first (`reference/propagation.md`, step 2) and tell the runner to sync the watch.
- Weather at the run location and start time, if a weather tool is available. The location comes from the plan or the calendar event, never from where the computer is.
- The last two comparable sessions from the snapshot: did they open too fast, fade, break the cap? `over_prescription_streak`.

If Garmin is unreachable, give the brief from the plan with a clear first line that recovery and the watch were not checked.

## 2. Decide

Apply the go/no-go rule from `plan.rules` exactly, using `recovery.verdict`:

- `go`: run it as written.
- `cap_firm`: run it; the heart-rate cap is absolute and pace gives way.
- `by_heart_rate`: keep the session, drop the pace target, hold the cap.
- `move`: move it one day. Never onto a blocked weekday; if tomorrow is blocked, say so and offer the next open day.
- `easy_instead`: the HRV rule fired. Today is an easy run.
- `unknown`: say what is missing and default to the cap being absolute.

Moving or swapping a session changes the plan: follow `reference/propagation.md`.

## 3. The brief (about 12 lines)

1. **Verdict** with the one number behind it.
2. **The session:** warm-up, main set, recoveries, cool-down.
3. **Targets:** pace band and heart-rate cap. For a race: the elapsed-time chart at course markers from `coach.py chart plan.json`, because the watch reads long.
4. **The cue:** one sentence from history, with the numbers ("Last two sessions opened 8 seconds fast. Start rep 1 at the slow end.").
5. **Weather** and what to wear.
6. **Today's logistics** from the plan: shoes, gel, caffeine, strength. Only what the plan dates for today.
7. Races only: breakfast, caffeine and gel timing **only if rehearsed** in the plan; arrival and warm-up times.

When this runs as a scheduled task, send the brief to the runner. If a calendar connector is available, also put it in today's event description so it is on the phone.
