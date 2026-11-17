# Methodology

How Strider chooses sessions, and where each choice comes from. Two kinds of claim appear here: those with a published **source**, and **coaching heuristics**, which are common practice written down as simple rules. Heuristics are labelled. Neither kind is medical advice, and none of it replaces a coach who knows you.

The numbers below are the defaults in `tools/strider/blockgen.py` and `tools/strider/paces.py`. The generator writes a first draft; the `build-block` skill then fits it to the runner.

## Principles

1. **Most running is easy.** Easy and long runs carry a heart-rate cap at the top of zone 2. Successful endurance athletes do roughly 80% of sessions at low intensity (Seiler 2010). One or two hard sessions a week is the design, not a limitation.
2. **Every quality session has a pace band and a heart-rate cap.** Pace says what to run; the cap says when today is not the day for it. Steady and finishing segments carry a cap too. *Heuristic.*
3. **Targets come from the runner's own running.** Threshold pace is taken from recent reps of five minutes or more at or just under threshold heart rate. Watch-estimated threshold speed and race predictions are not used. *Heuristic, from experience of both being wrong.*
4. **Reps get longer and recoveries shorter** as a block progresses, at the same pace band, rather than the same reps getting faster. *Heuristic; consistent with Daniels' cruise-interval progressions.*
5. **Decisions are written before they are needed.** The goal is set by a rule over one session, with every outcome covered (`reference/decision-rules.md`).
6. **The runner decides the goal.** The system recommends.

## Intensity bands

Heart-rate zones follow Friel, anchored to lactate-threshold heart rate (LTHR): zone 1 under 85%, zone 2 85 to 89%, zone 3 90 to 94%, zone 4 95 to 99%, zone 5 at and above LTHR.

| Band | Pace | Heart-rate cap | Basis |
|---|---|---|---|
| Easy | threshold pace +20% to +38% | 89% of LTHR (top of zone 2) | *Heuristic* |
| Steady | threshold pace +8% to +14% | 94% of LTHR (top of zone 3) | *Heuristic* |
| Threshold | threshold pace ±1.5% | LTHR | Daniels' "T" pace: comfortably hard, about one-hour race effort |
| Fast reps ("5K effort") | threshold pace −5% to −8% | 105% of LTHR, at most max − 3 | Daniels' "I" pace; the percentage is a *heuristic* |
| Goal | goal time over the distance, ±0.5% | by distance, below | |

Goal-pace heart-rate caps as a share of LTHR: 5K 105%, 10K 102%, half marathon 99%, marathon 93%. *Heuristic.* The generator also checks the goal against threshold pace (5K goal pace usually sits at 92 to 98% of threshold pace, 10K 96 to 101%, half 101 to 107%, marathon 107 to 116%; *heuristic*) and says so when the goal is outside the range.

When there are no qualifying reps, threshold pace is estimated as one-hour race pace from a race result using Riegel's model (Riegel 1981) and marked as an estimate to confirm.

## What changes with the distance

| | 5K | 10K | Half marathon | Marathon |
|---|---|---|---|---|
| Block length, weeks (min / default / max) | 6 / 8 / 12 | 8 / 10 / 14 | 7 / 12 / 16 | 12 / 16 / 20 |
| Key sessions, base | threshold | threshold | threshold | threshold |
| Key sessions, build | fast reps, threshold | threshold, fast reps | threshold, lengthening | threshold, marathon pace |
| Key sessions, specific | race pace, fast reps | race pace, threshold | race pace | marathon pace |
| Long run grows to | 14 km | 18 km | 22 km | 32 km |
| Long run share of the week, at most | 33% | 33% | 40% | 48% |
| Long-run content | easy | easy | steady finish in the specific phase | marathon-pace finish on alternate weeks |
| Peak weekly volume over starting volume | +20% | +25% | +30% | +40% |
| Taper | race week + 1 | race week + 1 | race week + 1 | race week + 2 |
| Decision session | 5 × 1 km (3 × 1 mi) at goal | 3 × 3 km (3 × 2 mi) | 2 × 5 km (2 × 3 mi) | 2 × 8 km (2 × 5 mi) |
| Decision session, weeks before race | 2 | 2 | 3 | 5 |
| Fuel during the race | none | none | optional gel if rehearsed | 30 to 60 g carbohydrate per hour, up to 90 g if rehearsed |

Session types by distance follow the general pattern in Daniels (*Daniels' Running Formula*) and Pfitzinger (*Faster Road Racing* with Latter for 5K to half marathon; *Advanced Marathoning* with Douglas for marathon-pace long runs and the three-week marathon taper). The specific numbers in the table are this project's defaults and are *heuristics*.

**Volume.** Weekly distance rises by at most 8% a week with a lighter week (−20%) every fourth week. *Heuristic.* The familiar "10% rule" has little direct evidence; the best data point is that novice runners who increased weekly distance by more than 30% over two weeks had more injuries than those who increased by under 10% (Nielsen et al. 2014). The validator warns above 12%.

**Quality volume.** Work in a key session is capped at about 22% of the week's distance. *Heuristic.*

**Taper.** Volume falls to roughly half over the final one to three weeks while run frequency and some race-pace running stay. A meta-analysis found the largest gains from a two-week taper that cut volume by 41 to 60% without changing intensity or frequency (Bosquet et al. 2007).

**Max heart rate test.** Scheduled in week 2 when max is unverified: two hard 3-minute efforts, then 2 minutes all-out, uphill if possible. *Heuristic.* It is early on purpose. A test left for late in a block gets skipped for the sessions that feel more important.

## Fueling, caffeine, strength, shoes

These are dated entries in the plan (`logistics`), not advice given once in conversation.

- **Carbohydrate during running.** 30 to 60 g per hour for efforts of 1 to 2.5 hours, up to 90 g per hour beyond that, and 10 to 12 g per kg per day for the 36 to 48 hours before events over 90 minutes (Thomas, Erdman & Burke 2016). Strider schedules rehearsals on long runs and uses on race day only what was rehearsed.
- **Caffeine.** 3 to 6 mg per kg about an hour before improves endurance performance for most people, with individual variation and side effects at higher doses (Guest et al. 2021). Rehearsed at the decision session or not used.
- **Strength.** Strength training improves running economy in distance runners (Blagrove, Howatson & Hayes 2018). Runners who already lift keep maintenance work on hard days with the last lower-body session about ten days out; runners who do not start with low-soreness work only. Starting heavy lifting mid-block is deferred to the next block. *The scheduling is a heuristic.*
- **Shoes.** Race shoes are chosen by the decision session and worn for it and for the race-week sharpen. *Heuristic.*

## Racing

- **Pace by course markers.** GPS watches typically read slightly long, so the watch's average pace is faster than true pace. The race plan is an elapsed-time chart at each marker.
- **Even or slightly negative splits** are the default plan. *Heuristic.*
- **A PR is a chip time.** GPS times are never adjusted into results.
- **After the race.** About one easy day per mile raced before the next hard session, and only once HRV, resting heart rate and recovery time are back to normal. *Heuristic, often attributed to Jack Foster.*

## Limits of this method

- It has been run end to end by one real athlete for one half-marathon block. The 5K, 10K and marathon templates are built from the sources above and have not yet been through a full block with this system.
- It assumes a healthy adult who already runs regularly. It is not a beginner couch-to-5K plan or a return-from-injury plan.
- Garmin's recovery time, readiness, HRV status and VO2max are proprietary estimates. The rules use them as signals, with the runner's own baseline where one exists.
- Ultras, trail and mountain races, triathlon, track racing under 5K and walking plans are out of scope.

## Sources

- Blagrove RC, Howatson G, Hayes PR. Effects of strength training on the physiological determinants of middle- and long-distance running performance: a systematic review. *Sports Medicine*. 2018;48(5):1117-1149.
- Bosquet L, Montpetit J, Arvisais D, Mujika I. Effects of tapering on performance: a meta-analysis. *Medicine & Science in Sports & Exercise*. 2007;39(8):1358-1365.
- Daniels J. *Daniels' Running Formula*. Human Kinetics.
- Friel J. *The Triathlete's Training Bible*. VeloPress.
- Guest NS, VanDusseldorp TA, Nelson MT, et al. International Society of Sports Nutrition position stand: caffeine and exercise performance. *Journal of the International Society of Sports Nutrition*. 2021;18(1):1.
- Nielsen RO, Parner ET, Nohr EA, Sørensen H, Lind M, Rasmussen S. Excessive progression in weekly running distance and risk of running-related injuries. *Journal of Orthopaedic & Sports Physical Therapy*. 2014;44(10):739-747.
- Pfitzinger P, Douglas S. *Advanced Marathoning*. Human Kinetics.
- Pfitzinger P, Latter P. *Faster Road Racing*. Human Kinetics.
- Riegel PS. Athletic records and human endurance. *American Scientist*. 1981;69(3):285-290.
- Seiler S. What is best practice for training intensity and duration distribution in endurance athletes? *International Journal of Sports Physiology and Performance*. 2010;5(3):276-291.
- Thomas DT, Erdman KA, Burke LM. American College of Sports Medicine joint position statement: nutrition and athletic performance. *Medicine & Science in Sports & Exercise*. 2016;48(3):543-568.
