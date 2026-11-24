# Data-quality checks

Run these before saying anything about a session. Every skill that reads a run follows this file; none of them restates it. `coach.py analyze` and `coach.py sync` apply the mechanical ones and report them as `flags`. Read the flags first and carry each one into what you tell the runner.

## 1. Laps, never the whole-run average

A session is described by its work reps, with warm-up, recoveries and cool-down removed. A 10 km workout that averages 5:10/km can hold three reps at 4:00/km.

- Always pull `get_activity_splits` for a run before describing it.
- If the run is a single lap, or you need to know whether a prescribed finish was run, pull `get_activity_typed_splits` and read the `RWD_RUN` segments (the watch breaks the run wherever running stopped and restarted) and any `INTERVAL_ACTIVE` entries.
- If neither shows the structure, the flag is `structure_unknown`. Say you cannot tell. Do not infer it from the average. The per-second file (see reference/garmin.md) is the last resort.
- A run with no saved laps gets the flag `no_laps` and is not judged.

## 2. Heart rate

- **Cold-start lag** (`hr_lag`, `hr_low_outlier`): a rep whose average heart rate sits 12 or more beats under the session's median rep is sensor lag, almost always on rep 1. It is left out of efficiency and cannot pass or fail a heart-rate cap.
- **Unverified max** (`max_hr_unverified`): until an all-out effort confirms it, max heart rate is a guess. Caps in the plan come from threshold heart rate and stand. Anything phrased as a share of max is provisional, and you say so.
- **New max seen** (`new_max_hr`): a run recorded more than the profile's max. Check it is not a spike (a real max comes at the end of a hard effort with heart rate climbing into it; a spike appears mid-run at easy pace), then update `athlete.md` and the plan.

## 3. Power and elevation

- **Hill-inflated power** (`hill_power`): a rep with more than 25 m net climb or descent distorts wrist power. Do not call the result fade and do not use the rep for efficiency comparisons.
- **Implausible altimeter** (`altimeter_implausible`): more than 8 m of climb per km on a track or a route the plan marks flat is sensor error. Power, fade, efficiency and any grade adjustment are not judged for that session. Set `terrain` on the planned day (`track`, `flat`, `rolling`, `hilly`) so this check can run.
- Efficiency (watts per heartbeat) is only compared between runs on similar routes. The snapshot lists climb per km beside each easy-run value for that reason.

## 4. Distance and pace

- **The watch measures its own distance, and it drifts.** GPS distance can be long or short depending on the surroundings: in an independent test of eight sport watches it ran short by up to 9% among buildings and trees and long on a track (Gilgen-Ammann et al. 2020). Each runner has a `watch_distance_factor` (watch distance divided by certified distance, from races). It is an average for the courses they race on; on a very different route (dense city center, forest trail) treat corrected pace as approximate. Paces from GPS laps are corrected to true distance before they are compared with a band. Track sessions use the measured distance and no correction.
- **Garmin's lactate-threshold speed and race predictor are not targets.** Do not quote them as a pace to train or race at. Pace bands come from recent reps at or under threshold heart rate (`coach.py threshold`).
- **PRs are official chip times.** A GPS time is never recorded as a PR. After every race, ask for the chip time.

## 5. Recovery signals

- HRV is read against the runner's own baseline band, never a population number, and the 7-day value matters more than one night.
- A missing HRV night is reported as missing, not filled in.
- Garmin's recovery time counts down. Report it with the time it was read and count down from there (`recovery_hours_now`).
- VO2max moves in steps of 0.1 and wobbles. A four-week change under 0.5 is noise; report direction, not the number.

## 6. Freshness

`coach.py sync` marks the snapshot `stale` when the newest Garmin data is older than `rules.max_snapshot_age_h` (26 hours by default). A stale snapshot can show the plan but cannot support a go/no-go verdict or a judgement on a run. Refresh first, or say what could not be checked.

**Never update any surface from a guess.** If Garmin cannot be reached, follow the failure protocol in reference/garmin.md.
