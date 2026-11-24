#!/usr/bin/env python3
"""Regenerate the bundled examples. Everything here is invented.

Two made-up runners, two distances, two unit systems:

  half-marathon/   "Robin Example", miles, 10-week block, shown in week 7
  10k/             "Kai Example", kilometers, 8-week block, shown in week 5

For each: block-input.json -> plan.json (blockgen) -> raw/ (simulated Garmin
tool results in the shapes garmin_mcp returns) -> dashboard/ (sync).
The simulation is seeded, so re-running it reproduces the same files.

    python3 examples/generate.py
"""
from __future__ import annotations

import datetime as dt
import json
import os
import random
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "tools"))

from strider import blockgen, calendar, snapshot  # noqa: E402
from strider import plan as P  # noqa: E402
from strider.units import MI, fmt_band, fmt_clock, fmt_dist  # noqa: E402

EXAMPLES = {
    "half-marathon": {
        "now": "2027-03-26T08:00:00",
        "input": {
            "units": "mi",
            "race": {"name": "Riverbend Half Marathon (example)", "date": "2027-04-18", "start": "08:00",
                     "tz": "Etc/UTC", "distance": "half", "location": "Example City", "terrain": "flat",
                     "course_notes": "Invented race. Flat out-and-back."},
            "goal_time_s": 5880,
            "athlete": {"name": "Robin Example", "lthr": 166, "max_hr": 185, "max_hr_verified": False,
                        "resting_hr": 47, "hrv_baseline_ms": [48, 60], "watch_distance_factor": 1.008},
            "threshold_pace_s_per_km": 271,
            "threshold_source": "synthetic example: 4 reps of 5+ min at 156-166 bpm in the month before the block",
            "baseline_pace_s_per_km": 289,
            "current_weekly_m": 42000, "longest_recent_m": 15000,
            "recent_race": {"distance": "10k", "time_s": 2700},
            "start": "2027-02-08",
            "run_days": ["Tue", "Wed", "Fri", "Sun"], "key_day": "Wed", "long_day": "Sun",
            "strength": "none",
        },
        # week -> pace offset (s/km) on work reps; negative is faster than the band middle
        "key_offsets": {1: 1, 3: -9, 4: -10, 5: 0, 6: 1, 7: -1},
        "moved": {"2027-03-14": "2027-03-13"},      # long run a day early
        "missed": ["2027-03-19"],
        "hr_lag_week": 1, "fade_week": 4, "form_drift_week": 6,
    },
    "10k": {
        "now": "2027-04-23T08:00:00",
        "input": {
            "units": "km",
            "race": {"name": "Harbour Lights 10K (example)", "date": "2027-05-16", "start": "09:00",
                     "tz": "Etc/UTC", "distance": "10k", "location": "Example Town", "terrain": "rolling",
                     "course_notes": "Invented race. Two laps, one short hill each lap."},
            "goal_time_s": 2445,
            "athlete": {"name": "Kai Example", "lthr": 168, "max_hr": 186, "max_hr_verified": True,
                        "resting_hr": 52, "hrv_baseline_ms": [61, 75], "watch_distance_factor": 1.004},
            "threshold_pace_s_per_km": 245,
            "threshold_source": "synthetic example: 5 reps of 5+ min at 158-168 bpm in the month before the block",
            "baseline_pace_s_per_km": 252,
            "current_weekly_m": 38000, "longest_recent_m": 12000,
            "start": "2027-03-22",
            "run_days": ["Mon", "Wed", "Thu", "Sat"], "key_day": "Wed", "long_day": "Sat",
            "blocked_weekdays": ["Fri"], "strength": "lifts",
        },
        "key_offsets": {1: 0, 2: 2, 3: -1, 4: -8, 5: -9},
        "moved": {"2027-04-07": "2027-04-08", "2027-04-08": "2027-04-07"},   # workout and easy day swapped
        "missed": [],
        "hr_lag_week": None, "fade_week": None, "form_drift_week": None,
    },
}


def mid(band):
    return (band[0] + band[1]) / 2.0


class Sim:
    def __init__(self, plan, cfg, seed):
        self.plan, self.cfg = plan, cfg
        self.rng = random.Random(seed)
        self.unit = MI if plan["units"] == "mi" else 1000.0
        self.factor = plan["athlete"]["watch_distance_factor"]
        self.easy = plan["bands"]["easy"]
        self.next_id = 9100000001 + seed * 1000

    def lap(self, laps, clock, true_m, pace, hr, kind, power_scale=1.0, cadence_shift=0.0, peak=4):
        dur = true_m * pace / 1000.0
        speed = 1000.0 / pace
        laps.append({
            "lap_number": len(laps) + 1, "start_time_gmt": clock[0].isoformat() + ".0",
            "distance_meters": round(true_m * self.factor, 2), "duration_seconds": round(dur, 3),
            "avg_hr_bpm": float(round(hr)), "max_hr_bpm": float(round(hr) + peak),
            "avg_cadence": round(160 + speed * 3.6 + cadence_shift + self.rng.uniform(-0.6, 0.6), 2),
            "avg_power_watts": float(round(speed * 76 * power_scale + self.rng.uniform(-2, 2))),
            "intensity_type": kind,
            "elevation_gain_meters": float(round(true_m / 1000 * self.rng.uniform(1, 4))),
            "elevation_loss_meters": float(round(true_m / 1000 * self.rng.uniform(1, 4))),
        })
        clock[0] += dt.timedelta(seconds=dur)

    def chunks(self, meters):
        out = []
        while meters > self.unit * 1.3:
            out.append(self.unit)
            meters -= self.unit
        out.append(meters)
        return out

    def run(self, week, day, ran_on):
        rng, cfg = self.rng, self.cfg
        laps, groups = [], []          # groups: (typed kind, [lap numbers], drift)
        clock = [dt.datetime.fromisoformat(ran_on + "T06:30:00")]
        easy_pace = mid(self.easy["pace_s_per_km"]) + rng.uniform(-6, 6)
        easy_hr = self.easy["hr_cap"] - rng.uniform(7, 13)
        offset = cfg["key_offsets"].get(week["n"], 0)
        rep = 0
        structured = day["kind"] in ("key", "test")
        work_steps = [s for s in P.flat_steps(day.get("steps")) if s["type"] == "work"]
        for step in P.flat_steps(day.get("steps")):
            first = len(laps) + 1
            t = step["type"]
            if t in ("warmup", "cooldown", "easy"):
                kind = {"warmup": "WARMUP", "cooldown": "COOLDOWN"}.get(t, "ACTIVE") if structured else "ACTIVE"
                for i, m in enumerate(self.chunks(step["distance_m"])):
                    self.lap(laps, clock, m, easy_pace + rng.uniform(-4, 4), easy_hr + min(i, 4) * 1.2, kind)
                groups.append(("INTERVAL_" + kind, list(range(first, len(laps) + 1)), 0))
            elif t == "steady":
                for i, m in enumerate(self.chunks(step["distance_m"])):
                    self.lap(laps, clock, m, mid(step["pace_s_per_km"]) + rng.uniform(-3, 3),
                             step["hr_cap"] - 5 + i, "ACTIVE")
            elif t == "work":
                rep += 1
                band = step.get("pace_s_per_km") or [self.plan["bands"]["vo2"]["pace_s_per_km"][0] * 0.94] * 2
                pace = mid(band) + offset + rng.uniform(-1.5, 1.5)
                cap = step.get("hr_cap") or self.plan["athlete"]["max_hr"]
                hr = cap - 7 + rep * 1.3 + (-0.15 * offset)
                if day.get("session") == "max_hr_test":
                    hr -= 2
                if not step.get("pace_s_per_km"):
                    hr = self.plan["athlete"]["max_hr"] + 1          # the all-out effort finds a new max
                if cfg["hr_lag_week"] == week["n"] and rep == 1:
                    hr -= 16                                         # cold-start sensor lag
                true_m = step.get("distance_m") or step["time_s"] / pace * 1000
                parts = self.chunks(true_m) if true_m >= 1.9 * self.unit else [true_m / 2.0, true_m / 2.0] if true_m > 1500 else [true_m]
                last_rep = rep == len(work_steps)
                for i, m in enumerate(parts):
                    scale = 1.0
                    if cfg["fade_week"] == week["n"] and last_rep and i == len(parts) - 1 and len(parts) > 1:
                        scale = 0.955                                # power fades inside the rep
                    self.lap(laps, clock, m, pace, hr + i * 0.8, "ACTIVE", scale, peak=4 if step.get("pace_s_per_km") else 3)
                drift = 1 if (cfg["form_drift_week"] == week["n"] and last_rep) else 0
                groups.append(("INTERVAL_ACTIVE", list(range(first, len(laps) + 1)), drift))
            elif t == "recovery":
                jog = easy_pace * 1.28
                self.lap(laps, clock, step["time_s"] / jog * 1000, jog,
                         self.plan["bands"]["threshold"]["hr_cap"] - 26 + rep * 1.5, "RECOVERY")
                groups.append(("INTERVAL_RECOVERY", [len(laps)], 0))
        dist = sum(l["distance_meters"] for l in laps)
        dur = sum(l["duration_seconds"] for l in laps)
        hr = sum(l["avg_hr_bpm"] * l["duration_seconds"] for l in laps) / dur
        aid = self.next_id
        self.next_id += 1
        activity = {"id": aid, "name": "Example run", "type": "running", "event_type": "uncategorized",
                    "start_time": ran_on + " 06:30:00", "distance_meters": round(dist, 2),
                    "duration_seconds": round(dur, 2), "avg_hr_bpm": float(round(hr)),
                    "max_hr_bpm": float(round(max(l["max_hr_bpm"] for l in laps))),
                    "elevation_gain_meters": sum(l["elevation_gain_meters"] for l in laps),
                    "elevation_loss_meters": sum(l["elevation_loss_meters"] for l in laps)}
        typed = None
        if structured:
            splits = []
            for kind, nums, drift in groups:
                ls = [laps[n - 1] for n in nums]
                d = sum(l["distance_meters"] for l in ls)
                s = sum(l["duration_seconds"] for l in ls)
                speed = d / s
                cadence = sum(l["avg_cadence"] * l["duration_seconds"] for l in ls) / s * (0.972 if drift else 1)
                gct = (300 - 18 * speed) * (1.052 if drift else 1) + self.rng.uniform(-1, 1)
                vr = (9.6 - 0.75 * speed) * (1.05 if drift else 1)
                splits.append({"type": kind, "lapIndexes": nums, "distance": round(d, 2), "duration": round(s, 3),
                               "averageSpeed": round(speed, 3), "averageHR": round(sum(l["avg_hr_bpm"] * l["duration_seconds"] for l in ls) / s),
                               "averagePower": round(sum(l["avg_power_watts"] * l["duration_seconds"] for l in ls) / s),
                               "averageRunCadence": round(cadence, 2), "groundContactTime": round(gct, 1),
                               "strideLength": round(speed / (cadence / 60.0) * 100, 1),
                               "verticalOscillation": round(vr * speed / (cadence / 60.0) / 10, 2), "verticalRatio": round(vr, 2)})
            typed = {"activityId": aid, "splits": splits}
        return activity, laps, typed


def health(plan, now, rng):
    today = now.date()
    lo, hi = plan["athlete"]["hrv_baseline_ms"]
    center = (lo + hi) / 2.0
    trend, week = [], []
    for i in range(27, -1, -1):
        day = today - dt.timedelta(days=i)
        v = None if i == 11 else round(center + rng.uniform(-5, 5))
        if v is not None:
            week = (week + [v])[-7:]
        trend.append({"date": day.isoformat(), "last_night_avg_hrv_ms": v,
                      "weekly_avg_hrv_ms": round(sum(week) / len(week)) if week else None,
                      "status": "BALANCED"})
    nights = [{"date": (today - dt.timedelta(days=i)).isoformat(), "sleep_score": rng.randint(72, 88)} for i in range(6, -1, -1)]
    start = today - dt.timedelta(days=84)
    vo2, v = [], 48.3 if lo < 55 else 51.2
    for i in range(0, 85, 3):
        v += rng.choice([0, 0, 0.1, 0.1, -0.1, 0.2]) * 0.6
        vo2.append({"date": (start + dt.timedelta(days=i)).isoformat(), "vo2_max": round(v, 1)})
    rest = plan["athlete"]["resting_hr"]
    stamp = today.isoformat() + "T07:12:00.0"
    return {
        "hrv_trend": {"trend": trend},
        "readiness": [{"date": today.isoformat(), "timestamp": stamp, "context": "AFTER_WAKEUP_RESET", "score": 71,
                       "level": "HIGH", "recovery_time_hours": 9.0}],
        "recovery_time": {"remaining_hours": 9.0, "value_type": "snapshot", "as_of": stamp, "state": "recovering",
                          "source": "training_readiness", "date": today.isoformat()},
        "sleep": {"nights": nights},
        "vo2max_trend": {"trend": vo2},
        "rhr": {"days": [{"date": (today - dt.timedelta(days=i)).isoformat(), "resting_hr_bpm": rest + rng.randint(-1, 2)}
                         for i in range(6, -1, -1)]},
    }


def athlete_md(plan, cfg):
    a, u, b, race = plan["athlete"], plan["units"], plan["bands"], plan["race"]
    z = [round(a["lthr"] * f) for f in (0.85, 0.90, 0.95, 1.0)]
    rows = "\n".join("| %s | %s | %s | %s |" % (k.capitalize(), fmt_band(v["pace_s_per_km"], u), v["hr_cap"], v["source"])
                     for k, v in b.items())
    return """# Athlete profile: {name}

> **Synthetic example.** This runner does not exist. Every number here was invented by `examples/generate.py`
> to show the format that the `setup` skill produces from schema/athlete.md.

Generated {start} from simulated history. Units: {u}.

## Physiology

- **Threshold heart rate (LTHR):** {lthr} bpm. Source: invented. Cross-check: none (example).
- **Max heart rate:** {max} bpm. **Verified: {ver}.**
- **Resting heart rate:** {rest} bpm, 28-day typical.
- **Heart-rate zones** (Friel, anchored to LTHR): Z1 under {z0} · Z2 {z0}-{z1b} · Z3 {z1}-{z2b} · Z4 {z2}-{z3b} · Z5 {z3}+.

## Pace bands

Derived from sessions, not from Garmin's threshold speed or race predictor.

| Band | Pace | HR cap | Evidence |
|---|---|---|---|
{rows}

## Watch

- **Watch distance factor:** {factor}. Source: invented certified race (example).

## Personal records (official chip times only)

| Distance | Time | Race | Date | Chip time confirmed |
|---|---|---|---|---|
| (none recorded in this example) | | | | |

## Recovery baselines

- **HRV baseline:** {h0}-{h1} ms. Derived from 21 simulated nights.

## Training context

- **Typical week:** {week} over {n} runs. Longest run in the last 8 weeks: {long}.
- **Available days:** {days}. **Key-session day:** {key}. **Long-run day:** {longday}. **Never:** {never}.
- **Strength training:** {strength}.

## Goal race

- **Race:** {race}, {date}. **Goal:** {goal} (provisional until the decision session). Plan file: `plan.json`.

## Open questions

1. {open}
""".format(name=a["name"], start=plan["weeks"][0]["start"], u=u, lthr=a["lthr"], max=a["max_hr"],
           ver="yes (example)" if a["max_hr_verified"] else "no",
           rest=a["resting_hr"], z0=z[0], z1=z[1], z1b=z[1] - 1, z2=z[2], z2b=z[2] - 1, z3=z[3], z3b=z[3] - 1,
           rows=rows, factor=a["watch_distance_factor"], h0=a["hrv_baseline_ms"][0], h1=a["hrv_baseline_ms"][1],
           week=fmt_dist(cfg["input"]["current_weekly_m"], u, 0), n=len(cfg["input"]["run_days"]),
           long=fmt_dist(cfg["input"]["longest_recent_m"], u, 0), days=", ".join(cfg["input"]["run_days"]),
           key=cfg["input"]["key_day"], longday=cfg["input"]["long_day"],
           never=", ".join(cfg["input"].get("blocked_weekdays", [])) or "none",
           strength="lifts twice a week" if cfg["input"].get("strength") == "lifts" else "none",
           race=race["name"], date=race["date"], goal=fmt_clock(plan["goal"]["time_s"]),
           open="Confirm max heart rate with the week 2 test." if not a["max_hr_verified"] else "None.")


def dump(path, body, fetched_at=None):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as fh:
        json.dump({"fetched_at": fetched_at, "result": body} if fetched_at else body, fh, indent=1)
        fh.write("\n")


def build(name, cfg, seed):
    out = os.path.join(HERE, name)
    for sub in ("raw", "dashboard"):
        shutil.rmtree(os.path.join(out, sub), ignore_errors=True)
    dump(os.path.join(out, "block-input.json"), cfg["input"])
    plan, notes = blockgen.build_block(cfg["input"])
    plan["synthetic"] = True
    now = dt.datetime.fromisoformat(cfg["now"])
    fetched = (now - dt.timedelta(minutes=45)).isoformat()
    sim = Sim(plan, cfg, seed)
    activities = []
    for week, day in P.all_days(plan):
        if day["kind"] not in P.RUN_KINDS or day["date"] in cfg["missed"]:
            continue
        ran_on = cfg["moved"].get(day["date"], day["date"])
        if dt.date.fromisoformat(ran_on) >= now.date():
            continue
        activity, laps, typed = sim.run(week, day, ran_on)
        activities.append(activity)
        dump(os.path.join(out, "raw", "splits", "%d.json" % activity["id"]),
             {"activity_id": activity["id"], "lap_count": len(laps), "laps": laps}, fetched)
        if typed:
            dump(os.path.join(out, "raw", "typed_splits", "%d.json" % activity["id"]), typed, fetched)
    dump(os.path.join(out, "raw", "activities.json"), {"count": len(activities), "activities": activities}, fetched)
    for key, body in health(plan, now, sim.rng).items():
        dump(os.path.join(out, "raw", key + ".json"), body, fetched)

    raw, stamps = snapshot.load_raw(os.path.join(out, "raw"))
    snap = snapshot.build(plan, raw, stamps, now)
    snapshot.apply_to_plan(plan, snap)
    decision = [e["decision"] for e in snap["days"].values() if e.get("decision")]
    if decision:
        plan["goal"]["decision"]["result"] = decision[0]
        plan["log"].append({"date": plan["goal"]["decision"]["session_date"],
                            "text": "Decision session run. Applied tier: %s. Waiting for the runner to confirm the goal."
                                    % decision[0]["applied_tier"]})
    errors, warnings = P.validate(plan)
    assert not errors, errors
    P.save(plan, os.path.join(out, "plan.json"))
    with open(os.path.join(out, "athlete.md"), "w") as fh:
        fh.write(athlete_md(plan, cfg))
    with open(os.path.join(out, "plan.ics"), "w", newline="") as fh:
        fh.write(calendar.to_ics(plan))
    snap = snapshot.build(plan, raw, stamps, now)
    snapshot.write(plan, snap, os.path.join(out, "dashboard"),
                   os.path.join(HERE, "..", "dashboard", "index.html"))
    print("%s: %d weeks, %d runs simulated, %d warnings, notes: %s" % (name, len(plan["weeks"]), len(activities), len(warnings), notes))
    for w in warnings:
        print("   warning:", w)


if __name__ == "__main__":
    for i, (name, cfg) in enumerate(sorted(EXAMPLES.items())):
        build(name, cfg, i + 1)
    # dashboard/ ships with the half-marathon example so the page shows something on first open
    shutil.copy(os.path.join(HERE, "half-marathon", "dashboard", "data.js"), os.path.join(HERE, "..", "dashboard", "data.js"))
