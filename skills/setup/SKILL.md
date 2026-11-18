---
name: setup
description: "Build a runner's athlete profile (athlete.md) from their Garmin history, asking only what cannot be derived. Use for a new runner, \"set up my profile\", \"onboard me\", or when athlete.md is missing or out of date before building a training block."
---

# Set up the athlete profile

Produce `athlete.md` in the runner's training folder, following the template at `../../schema/athlete.md`. Assume nothing about the runner: not their zones, paces, schedule, units or location. Everything is either read from Garmin, asked, or marked unknown.

Shared rules: `../../reference/data-quality.md` and `../../reference/garmin.md`. The tools are in `../../tools/` (`${CLAUDE_PLUGIN_ROOT}/tools` when installed as a plugin).

## 1. Check the connection and choose a folder

- Call `get_user_profile` and `get_unit_system`. If Garmin does not answer, follow the failure protocol in `reference/garmin.md` and stop.
- Ask where the training folder should live if the current folder is not obviously it. All files (`athlete.md`, `plan.json`, `data/`, `dashboard/`) go there. It holds health data, so it should not be a public repository.

## 2. Pull history

- `get_activities_by_date` for the last 26 weeks, running only, paging until `has_more` is false.
- `get_activity_splits` for: every run tagged `event_type: "race"`, and the 8 to 12 most recent runs that look like workouts (laps of mixed intensity) or long runs. Save all of it under `data/raw/` in the layout in `reference/garmin.md`.
- `get_lactate_threshold`, `get_hrv_trend` (28 days or more), `get_sleep_summary_range` (14 nights), `get_training_readiness`, `get_vo2max_trend` (12 weeks), `get_rhr_day` for recent days.

## 3. Derive, with the checks applied

- **Units:** from `get_unit_system`. Confirm in one line.
- **Threshold heart rate:** take Garmin's detected value from `get_lactate_threshold` if it is under six months old, then look for corroboration: a race of 30 to 70 minutes whose average heart rate sits within a few beats of it. Record the source and the cross-check. If there is no detected value, estimate from the hardest sustained effort and mark it an estimate.
- **Do not use Garmin's threshold speed or race predictor** for any pace. Run `coach.py threshold --raw data/raw --lthr <LTHR>`: it derives threshold pace from reps of five minutes or more at or just under threshold heart rate. If fewer than two reps qualify, estimate from the most recent official race time and say it is an estimate to confirm with a threshold session.
- **Max heart rate:** list the highest readings with the kind of run each came from. A high reading in an easy run is a spike, not a max. Set `Verified: no` unless there is an all-out effort behind it. Never infer max from age.
- **HRV baseline:** mean plus or minus one standard deviation of 21 or more nights. If the last month contains two clearly different regimes (illness, travel, altitude), use the current one and note it.
- **Watch distance factor:** for each race with a certified distance, watch distance divided by certified distance. Use the median. With no certified race, record 1.000 and say so.
- **Form table:** cadence, stride, ground contact and vertical ratio at easy, threshold and race pace, from typed splits where the watch records them. Leave rows blank rather than guess.
- **Training context:** typical weekly distance and longest run over the last 8 weeks, from activities.

## 4. Ask only what Garmin cannot tell you

Ask these together, once:

1. For each race found: "Garmin has <time> for <race>. What was your official chip time?" A PR is only recorded from a chip time. Until then the row says watch time, not confirmed.
2. Which days can you run, which day suits a hard session, which day suits the long run, and are there days that are never available?
3. Do you do strength training now? What and how often?
4. Which shoes do you train and race in?
5. Caffeine and gels: what have you actually used in training or races?
6. Any injury history or current niggle? (Record it. Do not diagnose. Suggest a clinician for anything that changes how they run.)
7. What is the goal race and goal, if they have one? (Optional here; `build-block` asks in detail.)

## 5. Write and report

Write `athlete.md`. Then give a short summary: what came from Garmin, what was estimated, what is unverified, and the single most useful next step (usually: confirm max heart rate with the test the block schedules in week 2, or supply a chip time). Offer to run `build-block` next.

Never write a number you did not read or derive. An honest blank is better than a plausible guess that later sessions build on.
