# Athlete profile: {name}

<!-- Template. Replace every {placeholder}. The setup skill fills this in from Garmin history and asks only for what it cannot derive.
     One fact per line, each with where it came from and the date. Mark estimates as estimates.
     Keep this file in your training folder, not in a public repository: it is personal health data. -->

Generated {date} from {N} runs between {date} and {date}. Units: {km | mi}.

## Physiology

- **Threshold heart rate (LTHR):** {bpm}. Source: {Garmin-detected on DATE | 30-minute test on DATE | estimated from RACE}. Cross-check: {race or session that corroborates it, or "none yet"}.
- **Max heart rate:** {bpm}. **Verified: {yes, all-out effort on DATE | no}.** Highest credible reading: {bpm on DATE, in what kind of run}. Readings ignored as spikes: {list or none}.
- **Resting heart rate:** {bpm}, 28-day typical.
- **Heart-rate zones** (Friel, anchored to LTHR): Z1 under {85%} · Z2 {85-89%} · Z3 {90-94%} · Z4 {95-99%} · Z5 {100%+}.

## Pace bands

Derived from sessions, not from Garmin's threshold speed or race predictor.

| Band | Pace | HR cap | Evidence |
|---|---|---|---|
| Easy | | | |
| Steady | | | |
| Threshold | | | {N reps of 5+ min at LTHR-10..LTHR, dates} or {estimate from RACE, to confirm} |
| Goal | | | goal time over the race distance |

## Watch

- **Device:** {model}. Running power: {yes/no}. Running dynamics (ground contact, vertical oscillation): {yes/no}.
- **Watch distance factor:** {1.000}. Source: {RACE on DATE: watch 10.07 km on a certified 10 km} or "no certified race yet; assume 1.000".

## Personal records (official chip times only)

| Distance | Time | Race | Date | Chip time confirmed |
|---|---|---|---|---|
| | | | | {yes | no: watch time only, not a PR until confirmed} |

## Recovery baselines

- **HRV baseline:** {low}-{high} ms (mean of 21+ nights, plus or minus one standard deviation). Derived {date}. Re-derive if the regime shifts for two weeks or more.
- **Sleep:** typical score {n}.
- **Notes that change how signals are read:** {altitude, illness, cycle tracking, shift work, or none}.

## Running form at known paces

| Run | Pace | Cadence | Stride | Ground contact | Vertical ratio |
|---|---|---|---|---|---|
| Easy | | | | | |
| Threshold | | | | | |
| Race | | | | | |

## Training context

- **Typical week:** {distance} over {n} runs. Longest run in the last 8 weeks: {distance}.
- **Available days:** {days}. **Key-session day:** {day}. **Long-run day:** {day}. **Never:** {days}.
- **Strength training:** {none | what and how often}.
- **Shoes:** {daily pair}, {race pair and its mileage}.
- **Fueling and caffeine habits:** {what has been practiced}.
- **Injury history and current niggles:** {list or none}. Anything here is for a clinician, not this profile, to rule on.

## Goal race

- **Race:** {name}, {date}, {distance}. **Goal:** {time, or "finish", or "personal best"}. Plan file: `plan.json`.

## Open questions

1. {for example: confirm max heart rate with the test in week 2}
2. {for example: official chip time for RACE}
