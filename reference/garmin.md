# Garmin: tools, saved data, and what to do when it fails

Strider reads and writes Garmin Connect through [Taxuspt/garmin_mcp](https://github.com/Taxuspt/garmin_mcp) (MIT licence), an MCP server built on the unofficial `python-garminconnect` library. It is a dependency you install yourself; nothing from it is copied here. Because the API is unofficial, any of this can break when Garmin changes something.

## Tools this project calls

Read-only (safe to pre-allow, see the README):

| Tool | Used for |
|---|---|
| `get_activities_by_date` | Runs since the last log entry; history at setup |
| `get_activity_splits` | Laps for every run. The basis of every judgement |
| `get_activity_typed_splits` | Structure of single-lap runs; per-rep form (ground contact, stride, vertical ratio) |
| `get_activity` | Race-day summary for the race review |
| `get_activity_weather` | Conditions on a run or race, for the review |
| `get_activity_fit_messages` | Per-second records for short runs |
| `get_hrv_trend`, `get_hrv_data` | HRV against the personal baseline |
| `get_sleep_summary_range` | 7-night sleep |
| `get_rhr_day` | Resting heart rate, for the HRV rule |
| `get_training_readiness` | Morning readiness |
| `get_recovery_time_remaining` | The go/no-go clock |
| `get_vo2max_trend` | Fitness direction |
| `get_lactate_threshold` | Threshold **heart rate** only. Its speed is not used |
| `get_user_profile`, `get_unit_system` | Units and basics at setup |
| `get_scheduled_workouts`, `get_workout_by_id` | Check what the watch has |

Write (each asks for approval unless you allow it):

| Tool | Used for |
|---|---|
| `upload_workout` | Create a workout from `coach.py workouts` output |
| `schedule_workout` | Put it on a date |
| `unschedule_workout` | Remove a calendar entry (takes `scheduled_workout_id`) |
| `download_activity_file` | Save a `.fit` file for per-second form analysis |

Not used: Garmin's race predictor, training status and load ratio, body battery, stress, nutrition, weight, gear, challenges, or any delete tool.

## Saving results so the tools can read them

The Python tools never talk to Garmin. A skill saves each tool result as JSON under `data/raw/` and `coach.py sync` reads them:

```
data/raw/
  activities.json            get_activities_by_date
  splits/<activity_id>.json  get_activity_splits
  typed_splits/<activity_id>.json   get_activity_typed_splits (key sessions, single-lap runs)
  hrv_trend.json             get_hrv_trend (28 days)
  readiness.json             get_training_readiness (today)
  recovery_time.json         get_recovery_time_remaining (today)
  sleep.json                 get_sleep_summary_range (7 nights)
  vo2max_trend.json          get_vo2max_trend (12 weeks)
  rhr.json                   {"days": [{"date": "YYYY-MM-DD", "resting_hr_bpm": 48}]} built from get_rhr_day
```

Write each file as `{"fetched_at": "<ISO time>", "result": <the tool result, unchanged>}`. To keep files small you may drop lap fields other than: `start_time_gmt`, `distance_meters`, `duration_seconds`, `avg_hr_bpm`, `max_hr_bpm`, `avg_power_watts`, `avg_cadence`, `intensity_type`, `elevation_gain_meters`, `elevation_loss_meters`. Do not change values. Do not write a file for a call that failed.

Field shapes for activities, splits, typed splits, readiness, recovery time and FIT records were checked against a live server in November 2026. The shapes for HRV trend, sleep range and VO2max trend follow how the original dashboard read them and may need adjusting if the server changes; `snapshot.py` is the one place that reads them.

## Per-second data (form late in a rep)

`download_activity_file(activity_id, format="fit", output_dir="data/fit")`, then
`coach.py form --records data/fit/<file>.fit --splits data/raw/splits/<id>.json` (needs `pip install fitparse`).
For a run under about ten minutes, `get_activity_fit_messages(activity_id, message_types=["record"], include_records=true)` saved as JSON works without the extra package. Use this for decision sessions, the longest reps of the block, and any session where a rep felt like it fell apart but the pace did not show it.

## When Garmin cannot be reached

The connection is the weakest link. The server runs on the runner's computer: it stops when the computer sleeps, tokens expire about every six months, and a tool call can sit waiting on an approval prompt nobody sees.

1. Retry the failed call once.
2. If it fails again, stop. Do not continue from memory, from the last snapshot, or from a guess.
3. Tell the runner what to do: wake the computer and open the Claude desktop app; check the Garmin server is listed and connected; if it reports a login error, re-run `garmin-mcp-auth` in a terminal.
4. Offer the fallback: a screenshot of the activity's laps page in Garmin Connect, or the lap times typed in. Mark anything logged this way as `"source": "screenshot"` in the plan log, and judge only what the screenshot shows (usually pace and heart rate, not power or form).
5. For a session brief, give the brief from the plan and state plainly that recovery and the watch were not checked.
6. When unattended, send one short message saying the data could not be refreshed and why. Write nothing.

Three habits prevent most of this: pre-allow the read-only tools so nothing waits on a prompt; run a daily sync (a scheduled task that pulls the files above and runs `coach.py sync`) so the dashboard is never more than a day old; keep the computer awake at the time scheduled tasks run.
