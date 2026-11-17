# Examples

Everything in this folder is **synthetic**. The runners, races, heart rates, paces and health data were invented by `generate.py`, which simulates Garmin tool results in the shapes garmin_mcp returns. No real person's data is here.

| Folder | Runner | Units | Block | Shown at |
|---|---|---|---|---|
| `half-marathon/` | Robin Example | miles | 10 weeks, max heart rate unverified | week 7, the day after the decision session |
| `10k/` | Kai Example | kilometres | 8 weeks, one blocked weekday, lifts | week 5, two sessions in a row faster than prescribed |

Each folder holds what a real training folder holds:

```
athlete.md         the profile (format: ../schema/athlete.md)
block-input.json   what build-block feeds the generator
plan.json          the plan: the single source of truth
plan.ics           calendar export for when no calendar connector is used
raw/               saved Garmin tool results
dashboard/         index.html + data.js + snapshot.json, written by `coach.py sync`
```

Things the simulated history is built to show: a rep with cold-start heart-rate lag, a session with power fade, form drift on a last rep, a long run moved a day, a swapped workout and easy day, a missed easy run, a max-heart-rate test that found a higher max than the profile, and a decision session waiting for the runner to confirm the goal.

Open `half-marathon/dashboard/index.html` in a browser, or `../dashboard/index.html?example=10k`.

Regenerate with `python3 examples/generate.py`. The output is deterministic; the test suite checks that the shipped snapshots match.
