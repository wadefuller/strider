# Athlete profile: Kai Example

> **Synthetic example.** This runner does not exist. Every number here was invented by `examples/generate.py`
> to show the format that the `setup` skill produces from schema/athlete.md.

Generated 2027-03-22 from simulated history. Units: km.

## Physiology

- **Threshold heart rate (LTHR):** 168 bpm. Source: invented. Cross-check: none (example).
- **Max heart rate:** 186 bpm. **Verified: yes (example).**
- **Resting heart rate:** 52 bpm, 28-day typical.
- **Heart-rate zones** (Friel, anchored to LTHR): Z1 under 143 · Z2 143-150 · Z3 151-159 · Z4 160-167 · Z5 168+.

## Pace bands

Derived from sessions, not from Garmin's threshold speed or race predictor.

| Band | Pace | HR cap | Evidence |
|---|---|---|---|
| Easy | 4:54 to 5:38/km | 150 | threshold pace +20% to +38%; cap is the top of zone 2 (heuristic) |
| Steady | 4:25 to 4:39/km | 158 | threshold pace +8% to +14%; cap is the top of zone 3 (heuristic) |
| Threshold | 4:01 to 4:09/km | 168 | synthetic example: 5 reps of 5+ min at 158-168 bpm in the month before the block |
| Vo2 | 3:45 to 3:53/km | 176 | threshold pace -5% to -8% (heuristic); heart rate lags in short reps, so read the cap on the last rep |
| Goal | 4:03 to 4:06/km | 171 | goal time over the race distance, +/-0.5% |

## Watch

- **Watch distance factor:** 1.004. Source: invented certified race (example).

## Personal records (official chip times only)

| Distance | Time | Race | Date | Chip time confirmed |
|---|---|---|---|---|
| (none recorded in this example) | | | | |

## Recovery baselines

- **HRV baseline:** 61-75 ms. Derived from 21 simulated nights.

## Training context

- **Typical week:** 38 km over 4 runs. Longest run in the last 8 weeks: 12 km.
- **Available days:** Mon, Wed, Thu, Sat. **Key-session day:** Wed. **Long-run day:** Sat. **Never:** Fri.
- **Strength training:** lifts twice a week.

## Goal race

- **Race:** Harbour Lights 10K (example), 2027-05-16. **Goal:** 40:45 (provisional until the decision session). Plan file: `plan.json`.

## Open questions

1. None.
