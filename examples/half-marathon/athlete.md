# Athlete profile: Robin Example

> **Synthetic example.** This runner does not exist. Every number here was invented by `examples/generate.py`
> to show the format that the `setup` skill produces from schema/athlete.md.

Generated 2027-02-08 from simulated history. Units: mi.

## Physiology

- **Threshold heart rate (LTHR):** 166 bpm. Source: invented. Cross-check: none (example).
- **Max heart rate:** 185 bpm. **Verified: no.**
- **Resting heart rate:** 47 bpm, 28-day typical.
- **Heart-rate zones** (Friel, anchored to LTHR): Z1 under 141 · Z2 141-148 · Z3 149-157 · Z4 158-165 · Z5 166+.

## Pace bands

Derived from sessions, not from Garmin's threshold speed or race predictor.

| Band | Pace | HR cap | Evidence |
|---|---|---|---|
| Easy | 8:43 to 10:02/mi | 148 | threshold pace +20% to +38%; cap is the top of zone 2 (heuristic) |
| Steady | 7:51 to 8:17/mi | 156 | threshold pace +8% to +14%; cap is the top of zone 3 (heuristic) |
| Threshold | 7:10 to 7:23/mi | 166 | synthetic example: 4 reps of 5+ min at 156-166 bpm in the month before the block |
| Vo2 | 6:41 to 6:54/mi | 174 | threshold pace -5% to -8% (heuristic); heart rate lags in short reps, so read the cap on the last rep |
| Goal | 7:26 to 7:31/mi | 164 | goal time over the race distance, +/-0.5% |

## Watch

- **Watch distance factor:** 1.008. Source: invented certified race (example).

## Personal records (official chip times only)

| Distance | Time | Race | Date | Chip time confirmed |
|---|---|---|---|---|
| (none recorded in this example) | | | | |

## Recovery baselines

- **HRV baseline:** 48-60 ms. Derived from 21 simulated nights.

## Training context

- **Typical week:** 26 mi over 4 runs. Longest run in the last 8 weeks: 9 mi.
- **Available days:** Tue, Wed, Fri, Sun. **Key-session day:** Wed. **Long-run day:** Sun. **Never:** none.
- **Strength training:** none.

## Goal race

- **Race:** Riverbend Half Marathon (example), 2027-04-18. **Goal:** 1:38:00 (provisional until the decision session). Plan file: `plan.json`.

## Open questions

1. Confirm max heart rate with the week 2 test.
