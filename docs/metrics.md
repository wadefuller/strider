# Metrics

Every metric Strider reads, what it means in plain language, and the rule by which it changes a decision. A metric with no rule is not shown. Thresholds marked *heuristic* are coaching rules of thumb, chosen to be simple and conservative; they live in `plan.rules` or at the top of the relevant tool file, so you can change them.

## Session metrics (from laps)

| Metric | Plain meaning | Source | How it changes a decision |
|---|---|---|---|
| **Rep pace** | How fast each work rep was, corrected to true distance | Laps, joined into reps (`laps.py`) | Compared with the session's pace band, with a small tolerance. More than half the reps faster than the band is "faster than prescribed" and counts toward the streak. Slower with heart rate at the cap means the band is too fast today. |
| **Rep heart rate** | Average heart rate in each rep | Laps | Any reliable rep over the cap makes the verdict "over the HR cap", whatever the pace. In the decision session it is half of every tier. |
| **Running power** | The watch's estimate of mechanical work rate, in watts | Laps (`avg_power_watts`) | Used only through fade and efficiency, below. Not judged on reps with more than 25 m net climb or when the altimeter is implausible. |
| **Power fade** | Power in the last lap of a rep against its first lap | Laps; needs a rep long enough to auto-lap | Over 3% (*heuristic*) means the rep was too hard to hold: the next session of that type keeps its rep length instead of extending. |
| **Jog heart rate** | Average heart rate in each recovery | Recovery laps | Rising 5 beats or more from first recovery to last (*heuristic*) means recoveries were too short for today: reported, and the next session keeps its recovery length. |
| **Efficiency** | Watts per heartbeat: output for a given cardiac cost | Laps, excluding reps with heart-rate lag | Read as a trend on similar routes only. Rising over weeks supports the fitness story; it never sets a pace. Not computed when power is unreliable. |
| **Cadence** | Steps per minute | Laps and typed splits | Not judged against a target number. Used inside form drift. |
| **Ground contact time** | Milliseconds each foot is on the ground | Typed splits, per-second file | Core of form drift. |
| **Vertical ratio** | Bounce as a share of stride length | Typed splits, per-second file | Part of form drift. |
| **Form drift** | Form on the last rep against the first at matching pace | Typed splits (`form_drift`) | Ground contact up 4% or more together with cadence down 2% or vertical ratio up 4%, speed within 2% (*heuristic*): hold the rep length next week. |
| **Late-rep breakdown** | The same test inside one rep: last third against first third | Per-second FIT records (`fitform.py`) | Same thresholds. Also reports when in the rep it started, which sets a sensible rep length or a point in the race to expect it. This is a field measure of durability: when, and how much, performance characteristics deteriorate during prolonged effort (Maunder et al. 2021). |
| **Single-run spike** | How much longer a run was than the longest run of the previous 30 days | Activity distances (`run_spikes`) | Over 10%: flagged, and the next long run stays at or below it. Injury rates rose past that point in a 5,205-runner Garmin cohort (Frandsen et al. 2025). Planned runs are never generated above it. |
| **Faster-than-prescribed streak** | Consecutive sessions run faster than the band | Session verdicts | Stated every time it is above zero. From two, the next brief's cue is to open at the slow end. |

## Recovery metrics (daily)

| Metric | Plain meaning | Source | How it changes a decision |
|---|---|---|---|
| **Recovery time remaining** | Garmin's estimate of hours until fully recovered, counted down from when it was read | `get_recovery_time_remaining` | The go/no-go rule: under 12 h go; 12 to 24 h the heart-rate cap is absolute; over 24 h move the key session a day (*heuristic*). |
| **HRV, last night** | Beat-to-beat variation overnight; lower than usual suggests stress or fatigue | `get_hrv_trend` | Below the runner's own baseline band: run by heart rate, not pace. |
| **HRV, 7-day** | The week's average, which is steadier than one night (Plews et al. 2013) | `get_hrv_trend` | Below the baseline band **and** resting heart rate raised for two days: the next key session becomes easy. HRV adjusts sessions; it does not drive the plan, because HRV-guided training has been at least as good as fixed plans but with a small, non-significant performance edge (Manresa-Rocamora et al. 2021). |
| **Resting heart rate** | Lowest daily heart rate | `get_rhr_day` | Raised 5 bpm or more for two days: the second half of the HRV rule. Within 3 bpm of normal is one of the post-race recovery checks. |
| **Sleep score** | Garmin's 0 to 100 rating of the night | `get_sleep_summary_range` | Under 70 three nights running: run by heart rate (*heuristic*). |
| **Readiness** | Garmin's morning composite of the above | `get_training_readiness` | Under 50: run by heart rate (*heuristic*). Never used alone to move a session. |

## Fitness and reference

| Metric | Plain meaning | Source | How it changes a decision |
|---|---|---|---|
| **VO2max direction** | Whether Garmin's estimate is moving over four weeks | `get_vo2max_trend` | Direction only. A change under 0.5 is noise. A fall alongside falling volume is reported in the weekly review; it does not set paces. |
| **Threshold heart rate (LTHR)** | The heart rate you can hold for about an hour | Garmin detection, cross-checked with a race | Anchors every zone and every heart-rate cap. |
| **Max heart rate** | The highest your heart rate goes in an all-out effort | A scheduled test early in the block | Until verified, statements made as a share of max are provisional. A new credible high updates the profile. |
| **Threshold pace** | The pace that goes with threshold heart rate | Reps of 5+ minutes at or just under LTHR (`coach.py threshold`) | Sets the threshold, easy, steady and fast-rep bands. |
| **Watch distance factor** | How far the watch over- or under-reads against a certified course; GPS runs short among buildings and trees and long in the open (Gilgen-Ammann et al. 2020) | Races with an official distance | Corrects lap paces, converts pace targets sent to the watch, and is why races are paced by course markers. |
| **Heart rate per unit of speed, half against half** | Whether heart rate rose for the same speed late in a race or long run | Race laps (`coach.py review`) | Under 5% is well coupled; over 10% (*heuristic*) says the pace was beyond current endurance: the next block's long runs matter more than its speed. |

## Recorded but deliberately not acted on

These are available from Garmin and were left out because no rule would change on them.

- **Garmin's lactate-threshold speed and race predictor.** Too often wrong for an individual to use as targets. Pace comes from the runner's own reps.
- **Stride length and vertical oscillation on their own.** Stride length is speed divided by cadence, and vertical oscillation is carried by vertical ratio. Shown in the profile's form table for context; no rule.
- **Training status, load ratio (acute:chronic), training effect, body battery, stress.** Composite scores whose inputs are already used directly. The acute:chronic ratio in particular has known conceptual problems as a predictor (Impellizzeri et al. 2020).
- **Cadence against a target such as 180.** Runners differ; chasing a number is not supported.

## Sources

- Frandsen JSB, et al. How much running is too much? Identifying high-risk running sessions in a 5200-person cohort study. *British Journal of Sports Medicine*. 2025;59(17):1203-1210.
- Gilgen-Ammann R, Schweizer T, Wyss T. Accuracy of distance recordings in eight positioning-enabled sport watches: instrument validation study. *JMIR mHealth and uHealth*. 2020;8(6):e17118.
- Manresa-Rocamora A, Sarabia JM, Javaloyes A, Flatt AA, Moya-Ramón M. Heart rate variability-guided training for enhancing cardiac-vagal modulation, aerobic fitness, and endurance performance: a methodological systematic review with meta-analysis. *International Journal of Environmental Research and Public Health*. 2021;18(19):10299.
- Maunder E, Seiler S, Mildenhall MJ, Kilding AE, Plews DJ. The importance of 'durability' in the physiological profiling of endurance athletes. *Sports Medicine*. 2021;51(8):1619-1628.
- Plews DJ, Laursen PB, Stanley J, Kilding AE, Buchheit M. Training adaptation and heart rate variability in elite endurance athletes: opening the door to effective monitoring. *Sports Medicine*. 2013;43(9):773-781.
- Moore IS. Is there an economical running technique? A review of modifiable biomechanical factors affecting running economy. *Sports Medicine*. 2016;46(6):793-807.
- Impellizzeri FM, Tenan MS, Kempton T, Novak A, Coutts AJ. Acute:chronic workload ratio: conceptual issues and fundamental pitfalls. *International Journal of Sports Physiology and Performance*. 2020;15(6):907-913.
- Friel J. *The Triathlete's Training Bible* (heart-rate zones anchored to lactate-threshold heart rate; decoupling under 5% as a marker of aerobic endurance).
