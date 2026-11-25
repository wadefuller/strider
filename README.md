# Strider

[![ci](https://github.com/wadefuller/strider/actions/workflows/ci.yml/badge.svg)](https://github.com/wadefuller/strider/actions/workflows/ci.yml)

An AI running coach for runners with a Garmin watch. Claude builds a training block for your race (5K to marathon) as one plan file, puts the workouts on your watch, judges every run from its laps, and keeps a dashboard current. You decide the goal; the plan's rules are written down before they are needed.

![The dashboard, showing a synthetic example runner](docs/img/dashboard.png)

*The runner and race in the screenshot are invented. See [examples/](examples/).*

## What you get

Each step produces something you can open, keep and change.

| You ask Claude | You get | Where it lives |
|---|---|---|
| "Set up my running profile" | An **athlete profile**: threshold and max heart rate (with where each came from), heart-rate zones, pace bands taken from sessions you actually ran, HRV baseline, your watch's distance error, and official PRs | `athlete.md` |
| "Build a plan for my race" | **An honest goal check first**: your goal pace against a prediction from a recent race or your threshold pace, how much a block that long can plausibly bring, and a verdict (within reach, realistic, stretch, unlikely, or slower than you need). If the goal is off, you get three options and choose. | In chat; `plan.json` (`goal.realism`) |
| | A **training plan**, week by week, for a 5K, 10K, half or marathon. Every hard session has a pace band and a heart-rate cap, and no run is more than 10% longer than your longest run of the previous 30 days. It includes a max-heart-rate test, the taper, and dated strength, shoe, caffeine and fueling rehearsals. | `plan.json` |
| | **Structured workouts on your watch**, scheduled on their dates, with pace targets adjusted for your watch's distance error | Garmin Connect |
| | **A calendar event for every run**: targets, the go/no-go rule on hard days, and that day's to-dos | Your calendar, or `plan.ics` to import |
| | **A rule that sets your race goal** from one key session, covering every possible result. The goal only changes when you say yes. | `plan.json` |
| | **A dashboard**: days to race and the block's phases; pace against goal; the next key session drawn to scale; a recovery meter with the go/no-go rule marked; HRV against your baseline, sleep and resting heart rate; per-rep pace and heart-rate charts for every key session; where your decision session lands among the goal tiers; the block week by week; and every run against the 10% ceiling. Each chart has a tooltip and a table view. | `dashboard/index.html` |
| "I ran today" | A **verdict on each run** from its laps: pace against the band, heart rate against the cap, power fade, recovery heart rate, and form late in the reps. Data-quality warnings come first. Every surface is updated in one pass. | In chat; `plan.json` log; dashboard |
| "Weekly review" | **Planned against run**, recovery trend, fitness direction, and next week's sessions adjusted and pushed to your watch | In chat, or sent to you on a schedule |
| "What's my workout today?" | A **morning brief**: go, cap firm, run by heart rate, easy instead, or move it a day, computed in code (`coach.py today`) with the numbers behind the call. Old data gives "unknown", never yesterday's answer, and a go resting on fewer than two recovery signals becomes "cap firm". Then the exact session, a check that your watch has it, weather, and one pacing cue from your recent runs | In chat, or sent on hard-session mornings |
| "It's race week" | A **race plan**: goal confirmed, elapsed time at every course marker, an effort plan, the forecast, kit and fueling (only what you rehearsed), and a timeline to the start | In chat; race-day calendar event |
| "Remember that..." (or any correction) | A **decisions log**: corrections, preferences, overrides and dated exceptions, in your words, read by every skill before it decides, so you never say the same thing twice | `decisions.md` |
| "How did my race go?" | A **race review** from your laps, then a **recovery check** four days later that says when hard training can resume | In chat; `athlete.md` PRs |

The dashboard is a single HTML file. It opens from your disk with no account, no server and no network requests.

## Quickstart

You need: a Garmin watch that syncs to Garmin Connect, [Claude Code](https://claude.com/claude-code) or the Claude desktop app, Python 3.9 or newer, and [uv](https://docs.astral.sh/uv/) (for the Garmin server).

1. **See it first.** Clone this repository and open `dashboard/index.html` in a browser. It shows a synthetic half-marathon runner. Add `?example=10k` to the address for the other example, or `?theme=light` / `?theme=dark` to override your system's color scheme.

2. **Connect Garmin.** Sign in once, then add the server to Claude (details in [Garmin setup](#garmin-setup)):

   ```bash
   uvx --python 3.12 --from git+https://github.com/Taxuspt/garmin_mcp garmin-mcp-auth
   ```

3. **Install the plugin.** In Claude Code:

   ```
   /plugin marketplace add wadefuller/strider
   /plugin install strider@strider
   ```

   Or skip the plugin and copy the Markdown files in `skills/` into your own setup; they are plain text.

4. **Make a training folder and build your profile.** Create an empty folder for your own data (it will hold health data, so keep it private), open Claude there, and say: *"Set up my running profile."* Claude reads your Garmin history and asks a handful of questions.

5. **Build your block.** Tell Claude the race, its date and what you want from it, for example:

   > *"Build a plan for the Lakeside Half Marathon on April 18, 2027. I'd like to break 1:40. I can run Tuesday, Wednesday, Friday and Sunday, and Thursdays are out."*

   Any race works; leave out the goal for a finish-focused plan, and leave out the days and Claude asks. It drafts the plan and shows it to you week by week. Only after you approve does it put the workouts on your watch, create the calendar events and write the dashboard to `dashboard/index.html` in your folder.

After that: *"I ran today"* after a run, *"weekly review"* at the end of the week, *"what's my workout today"* on a hard day.

## Garmin setup

Strider talks to Garmin through [Taxuspt/garmin_mcp](https://github.com/Taxuspt/garmin_mcp), an open-source MCP server (MIT license). It is a separate project that you install; none of its code is included here.

1. Authenticate once (command above). Your email, password and any MFA code go to Garmin from your machine. Tokens are saved in `~/.garminconnect` and last about six months.
2. Add the server to your Claude configuration, without credentials:

   ```json
   {
     "mcpServers": {
       "garmin": {
         "command": "uvx",
         "args": ["--python", "3.12", "--from", "git+https://github.com/Taxuspt/garmin_mcp", "garmin-mcp"]
       }
     }
   }
   ```

3. Restart Claude and ask *"what was my last run?"* to confirm it works.

**Make it reliable.** The connection is the weakest part of the system: the server runs on your computer, so it stops when the computer sleeps, and a tool call can wait unseen on an approval prompt.

- Pre-allow the read-only tools so nothing stalls. In your training folder's `.claude/settings.json`:

  ```json
  {
    "permissions": {
      "allow": [
        "mcp__garmin__get_activities_by_date", "mcp__garmin__get_activity_splits",
        "mcp__garmin__get_activity_typed_splits", "mcp__garmin__get_activity",
        "mcp__garmin__get_activity_weather", "mcp__garmin__get_hrv_trend",
        "mcp__garmin__get_hrv_data", "mcp__garmin__get_sleep_summary_range",
        "mcp__garmin__get_rhr_day", "mcp__garmin__get_training_readiness",
        "mcp__garmin__get_recovery_time_remaining", "mcp__garmin__get_vo2max_trend",
        "mcp__garmin__get_lactate_threshold", "mcp__garmin__get_user_profile",
        "mcp__garmin__get_unit_system", "mcp__garmin__get_scheduled_workouts",
        "mcp__garmin__get_workout_by_id"
      ]
    }
  }
  ```

  Leave the write tools (`upload_workout`, `schedule_workout`, `unschedule_workout`) on ask until you trust the setup.
- Schedule a daily sync so the dashboard is never more than a day old. The dashboard says so in red when its data is older than 26 hours.
- If Garmin cannot be reached, Claude stops and asks for a screenshot of the lap table instead. It does not update anything from a guess.

The exact tools Strider calls, and the fallback procedure, are in [reference/garmin.md](reference/garmin.md).

## How the pieces fit

```
          Garmin Connect  <──────────────────────────────┐
                │  read (garmin_mcp)                     │ upload + schedule workouts
                ▼                                        │
   athlete.md ──┐                                        │
                ├──>  plan.json  ──┬──> workouts/*.json ─┘
   your race ───┘   (source of     ├──> calendar events, or plan.ics
   and week          truth)        └──> dashboard/data.js ──> dashboard/index.html
                         ▲
                         │  statuses, actuals, log
   data/raw/*.json ──> coach.py sync  (laps → reps → checks → verdicts)
```

| Skill | When | What it does |
|---|---|---|
| [`setup`](skills/setup/SKILL.md) | once, and after each block | Builds `athlete.md` from Garmin history; asks only what cannot be derived |
| [`build-block`](skills/build-block/SKILL.md) | per race | Drafts, validates and shows the plan, then generates every surface |
| [`log-run`](skills/log-run/SKILL.md) | after runs | Pulls laps, judges sessions, applies rules, updates everything, sweeps for stale values |
| [`weekly-review`](skills/weekly-review/SKILL.md) | weekly, or scheduled | Planned against run, recovery trend, next week |
| [`session-brief`](skills/session-brief/SKILL.md) | hard days, or scheduled | Go/no-go, exact targets, watch check, one cue |
| [`race-week`](skills/race-week/SKILL.md) | 7 and 2 days out | Goal confirmed, pace chart at course markers, forecast, kit, timeline |
| [`race-review`](skills/race-review/SKILL.md) | after the race, and 4 days later | Race analysis from laps, chip time, recovery check |

Shared rules live once in [`reference/`](reference/) and the skills point to them: [data-quality checks](reference/data-quality.md), [decision rules](reference/decision-rules.md), [the decisions log](reference/decisions.md), [propagation checklist](reference/propagation.md).

The tools are plain Python with no third-party dependencies:

```bash
python3 tools/coach.py validate examples/10k/plan.json
python3 tools/coach.py chart examples/half-marathon/plan.json
python3 tools/coach.py sync examples/10k/plan.json --raw examples/10k/raw --out /tmp/demo --now 2027-04-23T08:00:00
python3 tools/coach.py today examples/half-marathon/plan.json --raw examples/half-marathon/raw --now 2027-03-26T08:00:00
python3 tools/coach.py goal --distance half --goal 1:30:00 --weeks 10 --recent 10k:48:30
python3 tools/coach.py decide decisions.md --kind preference --what "Long run on Saturdays" --why "family Sundays"
```

`coach.py today` exits 3 when the Garmin data is stale, so a scheduled job can tell "not synced" from "rest day".

Run the tests with `uv run --with pytest --with jsonschema --with pyyaml pytest`. CI runs them on Python 3.9 and 3.13, with and without the optional packages, plus lint, a front-matter and link check, plan validation, a check that the examples regenerate byte for byte, and a personal-data check ([scripts/check_repo.py](scripts/check_repo.py)).

## Evals

The coaching itself (what Claude says, not only what the tools compute) is tested with `claude plugin eval`. The [evals/](evals/) folder has ten cases on the synthetic runner: a low-HRV morning, stale data, thin data, an unrealistic goal, a too-easy goal, a long run past the 10% limit, decisions applied without being repeated, a correction saved, an instruction hidden in an activity name, and rising calf pain. Each one runs with and without the plugin, so the report shows what Strider adds.

```bash
claude plugin eval . --scaffold --allow-tools Bash Write Edit --runs 2
```

These are real model runs on your Claude account. Results are not published here yet; they will be added after the first full run. A test ([test_eval_fixtures.py](tools/tests/test_eval_fixtures.py)) checks in CI that every number a grader quotes is what the tools actually produce.

Background reading: [how sessions are chosen, with sources](docs/methodology.md) and [what each metric means and which decision it changes](docs/metrics.md).

**Optional surfaces.** Google Calendar (or any calendar connector) is optional; without one, Strider writes `plan.ics` for you to import. Publishing the dashboard as a Claude artifact is optional too; the file works on its own. Units are a profile setting: the plan stores metric values and displays kilometers or miles.

## The research behind it

Each rule in Strider either rests on a published study or is labeled a coaching heuristic: common practice written down as a simple rule. The specific numbers (for example, an 8% weekly rise or a 3% fade limit) are heuristics unless a paper below supports them. Full references, and which rule uses each, are in [docs/methodology.md](docs/methodology.md) and [docs/metrics.md](docs/metrics.md).

| What it shapes | Source |
|---|---|
| Long runs that grow no more than 10% past the longest run of the previous 30 days; a flag on any run that does | Frandsen et al., *BJSM* 2025: single-session spikes and injury in 5,205 runners tracked with Garmin devices |
| Most running easy, one or two hard sessions a week | Seiler, *IJSPP* 2010; Haugen et al., *Sports Medicine - Open* 2022 (world-class distance runners); Casado et al., *IJSPP* 2022 (elite periodization) |
| Not claiming one intensity mix is best | Oliveira, Boppre & Fonseca, *Sports Medicine* 2024: polarized training helped VO2max only in programs under 12 weeks |
| Taper: cut volume by about half over the final weeks, keep intensity and frequency; three weeks for the marathon | Bosquet et al., *MSSE* 2007 and Wang et al., *PLoS ONE* 2023 (meta-analyses of tapering); Smyth & Lawlor, *Frontiers* 2021 (158,117 recreational marathoners) |
| Cap on how fast weekly distance rises | Nielsen et al., *JOSPT* 2014: weekly distance progression and injury in novice runners |
| Threshold pace estimated from a race when there are no qualifying sessions | Riegel, *American Scientist* 1981: the endurance time model |
| The goal check: a prediction from a recent race or threshold pace, and about 1% of race time per 4 weeks of training as the most a block can plausibly bring (capped at 4%) | Riegel 1981 for the prediction; the improvement allowance is a heuristic, deliberately modest |
| Treating a Riegel marathon prediction as a best case | Vickers & Vertosick, *BMC Sports Sci Med Rehabil* 2016: Riegel underestimated marathon time by 10+ minutes for about half of runners |
| A per-runner watch-distance correction, and pacing races by course markers | Gilgen-Ammann et al., *JMIR mHealth* 2020: sport-watch GPS runs short among buildings and trees, long in the open |
| Reading HRV as a 7-day trend against your own baseline, used to adjust sessions rather than drive the plan | Plews et al., *Sports Medicine* 2013; Manresa-Rocamora et al., *IJERPH* 2021 (meta-analysis of HRV-guided training) |
| Checking whether form holds late in reps and races | Maunder et al., *Sports Medicine* 2021: durability in endurance athletes |
| Heavy strength work for runners who already lift | Blagrove, Howatson & Hayes, *Sports Medicine* 2018; Llanos-Lagos et al., *Sports Medicine* 2024 (heavy and combined training improved performance) |
| Carbohydrate before and during long races, rehearsed and built up in training | Thomas, Erdman & Burke, *MSSE* 2016 (ACSM position); Podlogar & Wallis, *Sports Medicine* 2022 (personalized carbohydrate) |
| Caffeine dose and timing, rehearsed before race day | Guest et al., *JISSN* 2021: ISSN position on caffeine |
| Not chasing a cadence number | Moore, *Sports Medicine* 2016: running technique and economy |
| Not acting on Garmin's acute:chronic load ratio | Impellizzeri et al., *IJSPP* 2020: conceptual problems with the ratio |
| Heart-rate zones anchored to threshold heart rate; session types by distance | Friel, *The Triathlete's Training Bible*; Daniels, *Daniels' Running Formula*; Pfitzinger and co-authors, *Faster Road Racing* and *Advanced Marathoning* (coaching books, not trials) |

## Limits

- **Distances.** Road 5K, 10K, half marathon and marathon. Not ultras, trail or mountain races, triathlon, track racing under 5K, walking plans, or return-from-injury programs.
- **Field testing.** The system was developed over one real half-marathon block. The 5K, 10K and marathon templates are built from published coaching sources and have not yet been through a full block with this system. Treat them as a first draft.
- **Who it is for.** Healthy adults who already run regularly. It is not a beginner program.
- **Garmin only**, through an unofficial API (below). Running power and form metrics need a watch that records them; everything degrades to pace and heart rate without them.
- **The lap-analysis tools were rewritten for this release** from the behavior of the original private scripts, and are covered by tests against synthetic laps. Garmin workout upload follows the server's documented format but has been exercised less than the read path.
- **Per-second form analysis** needs the optional `fitparse` package and a downloaded `.fit` file.
- Claude is doing the coaching. It follows the rules in this repository, but it can still be wrong. The checks exist because it was.

## Disclaimers

- **Not medical advice.** Strider is a training aid, not a doctor, physiotherapist or dietitian. Get medical clearance before hard training if you have any doubt about your health, and see a clinician for pain that changes how you run, chest symptoms, or illness. Heart-rate and HRV readings from a watch are estimates.
- **Unofficial Garmin API.** garmin_mcp uses an unofficial interface to Garmin Connect. It can break without notice, and using it is at your own risk under Garmin's terms. Strider is not affiliated with or endorsed by Garmin or Anthropic.
- **Your credentials stay on your machine.** Sign-in happens between your computer and Garmin; tokens are stored locally by garmin_mcp. Strider never asks for, stores or transmits them. Your training folder (`athlete.md`, `plan.json`, `decisions.md`, `data/`) holds health data: do not commit it to a public repository. The `.gitignore` here excludes the usual file names as a backstop.

## Acknowledgements

- [Taxuspt/garmin_mcp](https://github.com/Taxuspt/garmin_mcp) and [python-garminconnect](https://github.com/cyberjunky/python-garminconnect), which make the Garmin connection possible.
- The `training-intel` plugin by Jamie, whose idea of a single athlete profile file that every skill reads first is where this started. No text from it is included here.
- The coaches and researchers cited in [docs/methodology.md](docs/methodology.md).

## License

MIT. See [LICENSE](LICENSE).
