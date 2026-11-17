# Propagation: every surface, every time

The plan file is the source of truth. Garmin workouts, calendar events and the dashboard are generated from it. Change the plan, regenerate, then sweep. Never hand-edit one surface.

Work through the list in order and confirm each write succeeded before moving on.

1. **Plan file.** Make the edit in `plan.json` (status, moved date, new targets, goal). Run `coach.py validate plan.json`. Fix errors before touching anything else.
2. **Garmin calendar.**
   - `get_scheduled_workouts` for the next 14 days.
   - For a run done on another day: `unschedule_workout` the old entry (use `scheduled_workout_id`, not the workout id).
   - For a moved session: `schedule_workout` on the new date, then unschedule the old entry.
   - For changed targets: `coach.py workouts plan.json -o workouts --from <date> --to <date>`, `upload_workout` the new file, `schedule_workout` it, then unschedule the old entry. Read the old workout with `get_workout_by_id` first if you need to confirm what the watch currently has.
   - Store the new `garmin.workout_id` and `garmin.scheduled_id` on the day in the plan.
   - Tell the runner to sync the watch.
3. **Calendar** (optional surface).
   - If a calendar connector is available: for each affected event, update the title (done, moved, missed) and the description (the session line, actual splits, the one-line read). Keep anything the runner wrote in the description themselves. Suppress notifications on updates. Store event ids in `calendar_event_id`.
   - If not: `coach.py calendar plan.json -o plan.ics` and tell the runner to re-import it. Say plainly that the calendar was not updated live.
4. **Dashboard.** `coach.py sync plan.json --raw data/raw --out dashboard --write-plan`. This rewrites `dashboard/data.js` and `snapshot.json`. If the dashboard is also published as a Claude artifact, republish the same file.
5. **Plan log.** Append one dated line per day run to `plan.log`: the numbers and the decision.
6. **Consistency sweep.** For any changed goal time, pace band or tier:
   `coach.py sweep --before plan.before.json --after plan.json athlete.md plan.ics dashboard workouts`
   (keep a copy of the plan before editing), or `--old "1:38:00" --old "7:29/mi"` for specific values. Also search upcoming calendar events for the old values. Fix every hit and run the sweep again until it reports none.
7. **Report what changed and where**, one line per surface, including any surface you could not update and why.

If a write fails on an approval prompt, retry once, then stop and say which surfaces are now out of date.
