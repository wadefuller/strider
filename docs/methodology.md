# Methodology

How Strider chooses sessions, and where each choice comes from. Two kinds of claim appear here: those with a published **source**, and **coaching heuristics**, which are common practice written down as simple rules. Heuristics are labelled. Neither kind is medical advice, and none of it replaces a coach who knows you.

The numbers below are the defaults in `tools/strider/blockgen.py` and `tools/strider/paces.py`. The generator writes a first draft; the `build-block` skill then fits it to the runner.

## Principles

1. **Most running is easy.** Easy and long runs carry a heart-rate cap at the top of zone 2. Successful endurance athletes do roughly 80% of sessions at low intensity (Seiler 2010), and world-class distance runners keep at least 80% of their running volume easy all year (Haugen et al. 2022). One or two hard sessions a week is the design, not a limitation. Elite programs tend to run a pyramidal mix (most easy, some threshold, a little faster) through preparation and shift toward polarized nearer competition (Casado et al. 2022); Strider follows that shape. A meta-analysis found polarized training better than other mixes only for VO2max and only in programs under 12 weeks, with no advantage on performance measures (Oliveira, Boppre & Fonseca 2024), so Strider does not claim one distribution is best.
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

**Is the goal realistic?** Before a block is drafted, `coach.py goal` (and the generator, which stores the result in `goal.realism`) predicts the race from a recent race result, or from threshold pace treated as one-hour race pace, using Riegel's model (Riegel 1981). It then allows for improvement during the block: about 1% of race time per four weeks, capped at 4%. That allowance is a heuristic, chosen to be modest so the runner hears an honest answer early. The verdict is *within reach* (within 0.5% of the prediction), *realistic* (needs no more than the allowance), *stretch* (up to twice it), *unlikely* (more), or *conservative* (more than 3% slower than the prediction). A stretch or unlikely goal comes with three options: a softer goal for this block, the same goal for a later block, or more training time. The runner chooses; the decision session can still move the goal.

Riegel's model is well calibrated up to the half marathon but optimistic for the marathon: in a study of recreational runners it underestimated marathon time by 10 minutes or more for about half of them (Vickers & Vertosick 2016). For a marathon predicted from a shorter race, the check therefore adds 10 minutes to the Riegel time and uses that typical case, not the best case.

## What changes with the distance

| | 5K | 10K | Half marathon | Marathon |
|---|---|---|---|---|
| Block length, weeks (min / default / max) | 6 / 8 / 12 | 8 / 10 / 14 | 7 / 12 / 16 | 12 / 16 / 20 |
| Key sessions, base | threshold | threshold | threshold | threshold |
| Key sessions, build | fast reps, threshold | threshold, fast reps | threshold, lengthening | threshold, marathon pace |
| Key sessions, specific | race pace, fast reps | race pace, threshold | race pace | marathon pace |
| Long run grows to (each run at most 10% past the longest of the previous 30 days) | 14 km | 18 km | 22 km | 32 km |
| Long run share of the week, at most | 33% | 33% | 40% | 48% |
| Long-run content | easy | easy | steady finish in the specific phase | marathon-pace finish on alternate weeks |
| Peak weekly volume over starting volume | +20% | +25% | +30% | +40% |
| Taper | race week + 1 | race week + 1 | race week + 1 | race week + 2 |
| Decision session | 5 × 1 km (3 × 1 mi) at goal | 3 × 3 km (3 × 2 mi) | 2 × 5 km (2 × 3 mi) | 2 × 8 km (2 × 5 mi) |
| Decision session, weeks before race | 2 | 2 | 3 | 5 |
| Fuel during the race | none | none | 30 to 60 g carbohydrate per hour if rehearsed | 60 g per hour, building to 90 g if rehearsed |

Session types by distance follow the general pattern in Daniels (*Daniels' Running Formula*) and Pfitzinger (*Faster Road Racing* with Latter for 5K to half marathon; *Advanced Marathoning* with Douglas for marathon-pace long runs and the three-week marathon taper). The specific numbers in the table are this project's defaults and are *heuristics*.

**Single-run spikes.** No run is more than 10% longer than the longest run of the previous 30 days. In 5,205 runners tracked with Garmin devices for 18 months, the injury rate rose once a single session exceeded the longest run of the previous 30 days by more than 10%, and rose further with larger spikes (Frandsen et al. 2025). The generator grows long runs within that limit, shortens a workout's warm-up, cool-down or reps when it would break it, and `coach.py validate` rejects any planned run that does. The race itself is exempt. Logged runs that break the rule are flagged in the run review.

**Volume.** Weekly distance rises by at most 8% a week with a lighter week (−20%) every fourth week. *Heuristic.* The familiar "10% rule" has little direct evidence; the best data point is that novice runners who increased weekly distance by more than 30% over two weeks had more injuries than those who increased by under 10% (Nielsen et al. 2014). The validator warns above 12%.

**Quality volume.** Work in a key session is capped at about 22% of the week's distance. *Heuristic.*

**Taper.** Volume falls to roughly half over the final one to three weeks while run frequency and some race-pace running stay. A meta-analysis found the largest gains from a two-week taper that cut volume by 41 to 60% without changing intensity or frequency (Bosquet et al. 2007); a 2023 meta-analysis of endurance athletes found the same 41 to 60% cut effective over tapers of up to 21 days (Wang et al. 2023). For the marathon the taper is three weeks: in Strava data from 158,117 recreational marathoners, strict three-week tapers went with finishes about 2.6% faster than minimal tapers (Smyth & Lawlor 2021; an observational association, not a trial).

**Max heart rate test.** Scheduled in week 2 when max is unverified: two hard 3-minute efforts, then 2 minutes all-out, uphill if possible. *Heuristic.* It is early on purpose. A test left for late in a block gets skipped for the sessions that feel more important.

## Fueling, caffeine, strength, shoes

These are dated entries in the plan (`logistics`), not advice given once in conversation.

- **Carbohydrate during running.** 30 to 60 g per hour for efforts of 1 to 2.5 hours, up to 90 g per hour beyond that, and 10 to 12 g per kg per day for the 36 to 48 hours before events over 90 minutes (Thomas, Erdman & Burke 2016). Intake should be personalized and trained: the gut adapts to what it practices (Podlogar & Wallis 2022). Strider schedules half-marathon rehearsals at 30 to 60 g per hour and marathon rehearsals starting at 60 g per hour and building toward 90 g, and uses on race day only what was rehearsed.
- **Caffeine.** 3 to 6 mg per kg about an hour before improves endurance performance for most people, with individual variation and side effects at higher doses (Guest et al. 2021). Rehearsed at the decision session or not used.
- **Strength.** Strength training improves running economy in distance runners (Blagrove, Howatson & Hayes 2018). In a 2024 meta-analysis, heavy loads (80% of one-rep max or more) and combined heavy-plus-plyometric training improved running performance in middle- and long-distance runners, with moderate and large effects; plyometric training alone did not reach significance (Llanos-Lagos et al. 2024; certainty of evidence very low to moderate). Runners who already lift therefore do heavy work, 3 to 4 sets of 3 to 5 reps plus jumps, after the key session and once more mid-week in the base and build phases, dropping to 2 to 3 sets in the specific phase, with the last lower-body session about ten days out. Runners who do not lift start with low-soreness work only; starting heavy lifting mid-block is deferred to the next block, since new heavy work brings soreness that would cost key sessions. *The scheduling is a heuristic.*
- **Shoes.** Race shoes are chosen by the decision session and worn for it and for the race-week sharpen. *Heuristic.*

## Racing

- **Pace by course markers.** GPS watch distance drifts from the certified course: in a test of eight sport watches, distances were underestimated in urban and forest areas, by up to 9%, and overestimated on a track (Gilgen-Ammann, Schweizer & Wyss 2020). The watch's average pace is therefore off in a direction that depends on the course. The race plan is an elapsed-time chart at each marker.
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
- Casado A, González-Mohíno F, González-Ravé JM, Foster C. Training periodization, methods, intensity distribution, and volume in highly trained and elite distance runners: a systematic review. *International Journal of Sports Physiology and Performance*. 2022;17(6):820-833.
- Daniels J. *Daniels' Running Formula*. Human Kinetics.
- Frandsen JSB, et al. How much running is too much? Identifying high-risk running sessions in a 5200-person cohort study. *British Journal of Sports Medicine*. 2025;59(17):1203-1210.
- Friel J. *The Triathlete's Training Bible*. VeloPress.
- Gilgen-Ammann R, Schweizer T, Wyss T. Accuracy of distance recordings in eight positioning-enabled sport watches: instrument validation study. *JMIR mHealth and uHealth*. 2020;8(6):e17118.
- Guest NS, VanDusseldorp TA, Nelson MT, et al. International Society of Sports Nutrition position stand: caffeine and exercise performance. *Journal of the International Society of Sports Nutrition*. 2021;18(1):1.
- Haugen T, Sandbakk Ø, Seiler S, Tønnessen E. The training characteristics of world-class distance runners: an integration of scientific literature and results-proven practice. *Sports Medicine - Open*. 2022;8:46.
- Llanos-Lagos C, Ramirez-Campillo R, Moran J, Sáez de Villarreal E. The effect of strength training methods on middle-distance and long-distance runners' athletic performance: a systematic review with meta-analysis. *Sports Medicine*. 2024;54(7):1801-1833.
- Nielsen RO, Parner ET, Nohr EA, Sørensen H, Lind M, Rasmussen S. Excessive progression in weekly running distance and risk of running-related injuries. *Journal of Orthopaedic & Sports Physical Therapy*. 2014;44(10):739-747.
- Oliveira PS, Boppre G, Fonseca H. Comparison of polarized versus other types of endurance training intensity distribution on athletes' endurance performance: a systematic review with meta-analysis. *Sports Medicine*. 2024;54(8):2071-2095.
- Pfitzinger P, Douglas S. *Advanced Marathoning*. Human Kinetics.
- Pfitzinger P, Latter P. *Faster Road Racing*. Human Kinetics.
- Podlogar T, Wallis GA. New horizons in carbohydrate research and application for endurance athletes. *Sports Medicine*. 2022;52(Suppl 1):5-23.
- Riegel PS. Athletic records and human endurance. *American Scientist*. 1981;69(3):285-290.
- Seiler S. What is best practice for training intensity and duration distribution in endurance athletes? *International Journal of Sports Physiology and Performance*. 2010;5(3):276-291.
- Smyth B, Lawlor A. Longer disciplined tapers improve marathon performance for recreational runners. *Frontiers in Sports and Active Living*. 2021;3:735220.
- Thomas DT, Erdman KA, Burke LM. American College of Sports Medicine joint position statement: nutrition and athletic performance. *Medicine & Science in Sports & Exercise*. 2016;48(3):543-568.
- Vickers AJ, Vertosick EA. An empirical study of race times in recreational endurance runners. *BMC Sports Science, Medicine and Rehabilitation*. 2016;8:26.
- Wang Z, Wang YT, Gao W, Zhong Y. Effects of tapering on performance in endurance athletes: a systematic review and meta-analysis. *PLoS ONE*. 2023;18(5):e0282838.
