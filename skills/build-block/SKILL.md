---
name: build-block
description: Plan a training block for a goal race (5K, 10K, half marathon or marathon) as one plan file, then generate the Garmin workouts, calendar events and dashboard from it. Use for "build me a plan", "I signed up for a race", "plan my training", or when the goal, schedule or race changes.
---

# Build a training block

`plan.json` is the single source of truth. Garmin workouts, calendar events and the dashboard are generated from it. Later changes are made by editing the plan and regenerating, never by hand-editing one surface.

Shared rules: `../../reference/decision-rules.md`, `../../reference/propagation.md`, `../../reference/garmin.md`. Method and sources: `../../docs/methodology.md`. Tools: `../../tools/coach.py`. Schema: `../../schema/plan.schema.json`.

**Scope.** Road races from 5K to the marathon. Out of scope, and say so plainly if asked: ultras, trail and mountain races, triathlon and other multisport, track racing under 5K, walking plans, and return-from-injury programmes. Do not stretch a marathon plan to cover them.

## 1. Inputs

- `athlete.md`. If it is missing or older than three months, run `setup` first.
- The race: name, date, start time, time zone, distance, location, terrain, course notes.
- The goal: a time, a personal best, or to finish. For a first race at the distance, a finish goal is the default.
- Constraints: available days, key-session day, long-run day, days that are never available, travel and other dated commitments inside the block.
- Current fitness from Garmin, from laps: the last 6 to 8 weeks of workouts and long runs, weekly distance, longest run. Refresh `data/raw/` first.
- Ask only what cannot be derived.

## 2. Draft

1. Threshold pace: `coach.py threshold --raw data/raw --lthr <LTHR> --factor <watch factor>`. Never Garmin's threshold speed, never a whole-run average.
2. Write `block-input.json` (see `../../examples/half-marathon/block-input.json` for the shape) and run `coach.py block block-input.json -o plan.json`. The generator picks block length, key-session types, long-run growth, taper and fueling items for the distance. Read its notes: it says when the block is shorter than the distance needs, and when the goal is ambitious against current threshold pace.
3. If the block is shorter than the minimum for the distance, tell the runner what that means (hold and sharpen, not build) before going further.

## 3. Adjust the draft to the runner

Edit `plan.json` directly. Things the generator cannot know:

- Dated constraints: move sessions around travel and commitments; mark a day `rest` with a note rather than deleting it.
- A tune-up race, a group session the runner will not give up, a hill they always run.
- `terrain` on each day run on a track or a flat route, so the altimeter check works.
- Strength: if the runner lifts, maintenance on hard days and the last lower-body session about 10 days out. If they do not, low-soreness work only. Each session is a dated `logistics` entry.
- Shoes, caffeine and gels: each rehearsal is a dated `logistics` entry. Nothing is used on race day that has no rehearsal date in the plan.

## 4. Checks the plan must pass

Run `coach.py validate plan.json` and fix every error. It enforces:

- Every work step has a pace band **and** a heart-rate cap. Every steady or finishing segment has a heart-rate cap. Easy and long runs have a cap.
- The goal-setting rule covers every outcome, ends in `otherwise`, names the borderline default, and requires the runner's confirmation (`reference/decision-rules.md`).
- If max heart rate is unverified, a max-heart-rate test sits in the first third of the block. Do not move it late. If the runner will not do one, set `rules.max_hr_test_waived` to their reason.
- No key session on a blocked weekday.

Read the warnings too: volume jumps over 12%, a race week that is not a taper, missing logistics.

Then show the runner the plan: the weeks, each key session with its exact targets, the decision rule as a table, and the taper. The goal starts **provisional**. Ask for changes before generating anything.

## 5. Generate every surface

Follow `reference/propagation.md`. For a new block:

- **Garmin:** `coach.py workouts plan.json -o workouts`, then for each file `upload_workout` and `schedule_workout` on its date. Store both ids in the plan. Pace targets are already converted for the runner's watch distance. Tell the runner to sync the watch.
- **Calendar:** if a calendar connector is available, `coach.py calendar plan.json --json` gives one event per run day with targets, the go/no-go line on key days and that day's logistics; create them and store the ids. If not, write `plan.ics` and tell the runner to import it. Either way say which you did.
- **Dashboard:** `coach.py sync plan.json --raw data/raw --out dashboard`, then tell the runner to open `dashboard/index.html`. Publishing it as a Claude artifact is optional.
- **Scheduled tasks** (offer, do not assume): a daily Garmin sync, `weekly-review` on the evening the training week ends, `session-brief` early on key-session days and race morning, `race-week` seven days out, and the recovery check four days after the race.

## 6. Changing the plan later

Copy `plan.json` to `plan.before.json`, edit, validate, regenerate only the changed days, then sweep for the old values (`reference/propagation.md`, step 6). A goal change is one edit to `goal.time_s` plus a regenerate, and it needs the runner's explicit yes.
