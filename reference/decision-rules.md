# Decision rules

A decision rule turns a result into an action without anyone improvising on the day. The plan carries two kinds: the goal-setting rule (`goal.decision`) and the standing rules (`rules`).

## What every rule must do

1. **Cover every outcome.** Tiers are tried in order, fastest goal first, and the first match wins. The last tier is `"when": "otherwise"`. `coach.py validate` rejects a rule without it, because a result that fits no tier is the moment people start negotiating with themselves.
2. **Resolve mixed results by construction.** The rule tests the *slowest* reliable rep and the *highest* reliable rep heart rate. One rep in the fast tier and one in the slow tier is therefore the slow tier. No judgement call.
3. **Name the default for a borderline result.** A result within `borderline.pace_s_per_km` or `borderline.hr_bpm` of a tier's limit only just qualified. It takes the slower tier by default (`"default": "slower_tier"`), and the report says it was borderline and why.
4. **Leave the goal to the runner.** `runner_confirms` is always true. The rule produces a recommendation. The goal in the plan changes only after the runner says yes, in their own words, in the conversation. A scheduled or unattended run proposes and never writes.
5. **Ignore unreliable data.** A rep flagged for heart-rate lag does not count toward the heart-rate test (reference/data-quality.md).

## Applying the goal-setting rule

1. Run `coach.py analyze plan.json --date <decision date> --splits <file>`. The `decision` block gives `qualified_tier`, `borderline`, `applied_tier` and `goal_time_s`.
2. Tell the runner: the reps, the tier they qualified for, whether it was borderline, and the goal that follows. Give the conservative reading first.
3. Ask: "Do you want the goal set to {time}?" Wait for the answer.
4. On yes: set `goal.time_s`, `goal.status: "confirmed"`, `goal.set_on`, store the result in `goal.decision.result`, rebuild the `goal` band, regenerate what changed, and sweep (reference/propagation.md).
5. On no, or no answer: leave the goal provisional and log that the decision is open.

## Standing rules

| Rule | Default | Meaning |
|---|---|---|
| Recovery go/no-go | 12 h / 24 h | Under 12 h of Garmin recovery time left before a key session: go. 12 to 24 h: run it, heart-rate cap absolute (back off pace to stay under). Over 24 h: move it one day. Never onto a blocked weekday. |
| HRV rule | 7-day HRV under baseline **and** resting HR up 5+ bpm for 2+ days | The next key session becomes an easy run. Both signals are required; one alone means "run by heart rate, not pace". |
| By heart rate | last-night HRV under baseline, or readiness under 50, or sleep under 70 three nights running | Keep the session, drop the pace target, hold the heart-rate cap. |
| Missed easy run | | Move it only if it fits without touching the next key session. Otherwise drop it. Never stack it onto a key day. |
| Moved long run | | Free the original day (rest). |
| Faster than prescribed | | Count consecutive sessions run faster than the band and state the number every time. From two in a row, the next brief's cue is to open at the slow end of the band. |
| Form drift | | If form broke down late in the reps while pace held, hold the rep length next week instead of extending it. |

These thresholds are coaching heuristics chosen to be simple enough to follow at 6 a.m. They live in `plan.rules`, so a runner or coach can change them in one place.
