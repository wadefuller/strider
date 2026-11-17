"""Draft a training block for a 5K, 10K, half marathon or marathon.

This produces a first draft that already passes validation. The build-block
skill then adjusts it around the runner's real constraints. What changes with
distance (block length, key-session types, long-run growth, taper, fueling)
lives in PROFILE; the reasoning and sources are in docs/methodology.md.
"""
from __future__ import annotations

import datetime as dt

from . import paces as P
from .plan import DEFAULT_RULES, WEEKDAYS
from .units import DISTANCES, DISTANCE_NAMES, MI, fmt_clock

PROFILE = {
    "5k": {"weeks": (6, 8, 12), "taper": [0.65], "race_week": 0.45, "peak_gain": 1.20,
           "long_cap_m": 14000, "long_step_m": 1000, "long_share": 0.33,
           "decision_weeks_out": 2, "fuel": False,
           "cycle": {"base": ["threshold"], "build": ["vo2", "threshold"], "specific": ["goal", "vo2"]}},
    "10k": {"weeks": (8, 10, 14), "taper": [0.65], "race_week": 0.45, "peak_gain": 1.25,
            "long_cap_m": 18000, "long_step_m": 1500, "long_share": 0.33,
            "decision_weeks_out": 2, "fuel": False,
            "cycle": {"base": ["threshold"], "build": ["threshold", "vo2"], "specific": ["goal", "threshold"]}},
    "half": {"weeks": (7, 12, 16), "taper": [0.70], "race_week": 0.40, "peak_gain": 1.30,
             "long_cap_m": 22000, "long_step_m": 2000, "long_share": 0.40,
             "decision_weeks_out": 3, "fuel": True,
             "cycle": {"base": ["threshold"], "build": ["threshold"], "specific": ["goal"]}},
    "marathon": {"weeks": (12, 16, 20), "taper": [0.80, 0.60], "race_week": 0.30, "peak_gain": 1.40,
                 "long_cap_m": 32000, "long_step_m": 2500, "long_share": 0.48,
                 "decision_weeks_out": 5, "fuel": True,
                 "cycle": {"base": ["threshold"], "build": ["threshold", "goal"], "specific": ["goal"]}},
}

# (reps, seconds per rep, jog seconds). Time-based so they read the same in km or miles.
THRESHOLD = [(4, 300, 60), (3, 480, 90), (3, 600, 120), (4, 480, 90), (2, 900, 150), (3, 720, 120)]
VO2 = [(5, 180, 150), (6, 180, 150), (5, 240, 180), (6, 240, 180), (5, 300, 210)]
# Goal-pace reps by distance: (reps, rep length in the runner's unit, jog seconds).
GOAL = {
    "km": {"5k": [(5, 1, 90), (6, 1, 75), (3, 2, 150)],
           "10k": [(4, 2, 120), (5, 2, 120), (3, 3, 150)],
           "half": [(3, 3, 120), (2, 5, 180), (3, 4, 150)],
           "marathon": [(2, 5, 120), (1, 10, 0), (2, 7, 180), (1, 14, 0)]},
    "mi": {"5k": [(6, 0.5, 75), (8, 0.5, 60), (3, 1, 120)],
           "10k": [(3, 1.5, 120), (4, 1.5, 120), (3, 2, 150)],
           "half": [(3, 2, 120), (2, 3, 180), (3, 2.5, 150)],
           "marathon": [(2, 3, 120), (1, 6, 0), (2, 4, 180), (1, 8, 0)]},
}
DECISION = {"km": {"5k": (5, 1, 90), "10k": (3, 3, 150), "half": (2, 5, 180), "marathon": (2, 8, 180)},
            "mi": {"5k": (3, 1, 120), "10k": (3, 2, 150), "half": (2, 3, 180), "marathon": (2, 5, 180)}}
SHARPEN = {"km": {"5k": (4, 0.4, 90), "10k": (3, 1, 120), "half": (3, 1, 120), "marathon": (2, 2, 120)},
           "mi": {"5k": (4, 0.25, 90), "10k": (3, 0.5, 120), "half": (3, 1, 120), "marathon": (2, 1, 120)}}


def _mid(band):
    return (band[0] + band[1]) / 2


def _num(x):
    return ("%g" % x)


def _round5(seconds):
    return int(round(seconds / 5.0) * 5)


class Builder:
    def __init__(self, spec):
        self.s = spec
        self.units = spec.get("units", "km")
        self.unit_m = MI if self.units == "mi" else 1000.0
        self.distance = spec["race"]["distance"]
        self.p = PROFILE[self.distance]
        a = spec["athlete"]
        self.bands = P.build_bands(
            {"pace_s_per_km": spec["threshold_pace_s_per_km"],
             "source": spec.get("threshold_source", "supplied by the runner; confirm with a threshold session")},
            a["lthr"], a["max_hr"], self.distance, spec["goal_time_s"])
        self.easy_pace = _mid(self.bands["easy"]["pace_s_per_km"])

    # -- steps -------------------------------------------------------------
    def work(self, band, distance_m=None, time_s=None, note=None):
        b = self.bands[band]
        step = {"type": "work", "pace_s_per_km": b["pace_s_per_km"], "hr_cap": b["hr_cap"], "band": band}
        if distance_m:
            step["distance_m"] = round(distance_m, 1)
        else:
            step["time_s"] = time_s
        if note:
            step["note"] = note
        return step

    def step_m(self, step):
        if step["type"] == "repeat":
            return step["count"] * sum(self.step_m(x) for x in step["steps"])
        if "distance_m" in step:
            return step["distance_m"]
        pace = _mid(step["pace_s_per_km"]) if step.get("pace_s_per_km") else self.easy_pace * (1.25 if step["type"] == "recovery" else 1)
        return step.get("time_s", 0) / pace * 1000

    def session(self, title, kind, session, body, warm_m=None, cool_m=2000):
        warm_m = warm_m or (3000 if self.s["current_weekly_m"] >= 40000 else 2500)
        cap = self.bands["easy"]["hr_cap"]
        steps = [{"type": "warmup", "distance_m": warm_m, "hr_cap": cap, "note": "easy, then 4 strides"}]
        steps += body
        steps.append({"type": "cooldown", "distance_m": cool_m, "hr_cap": cap})
        total = sum(self.step_m(x) for x in steps)
        return {"kind": kind, "session": session, "title": title, "steps": steps,
                "distance_m": round(total / 100.0) * 100}

    def reps(self, band, n, jog_s, distance_m=None, time_s=None):
        w = self.work(band, distance_m, time_s)
        if n == 1 or not jog_s:
            return [w] if n == 1 else [{"type": "repeat", "count": n, "steps": [w]}]
        return [{"type": "repeat", "count": n, "steps": [w, {"type": "recovery", "time_s": jog_s, "note": "jog"}]}]

    def time_label(self, n, sec):
        return "%d x %s min" % (n, _num(sec / 60.0))

    def dist_label(self, n, units_len):
        return "%s%s %s" % (("%d x " % n) if n > 1 else "", _num(units_len), self.units)

    def key(self, kind, level, cap_m, decision=False, sharpen=False):
        """Pick the hardest entry at or below `level` whose work fits under cap_m."""
        if kind == "threshold":
            table, band = THRESHOLD, "threshold"
        elif kind == "vo2":
            table, band = VO2, "vo2"
        else:
            table, band = GOAL[self.units][self.distance], "goal"
        if decision or sharpen:
            n, length, jog = (DECISION if decision else SHARPEN)[self.units][self.distance]
            body = self.reps("goal", n, jog, distance_m=length * self.unit_m)
            name = "race pace" if self.distance != "marathon" else "marathon pace"
            title = "%s at %s%s" % (self.dist_label(n, length), name,
                                    ", the decision session" if decision else ", sharpen")
            sess = self.session(title, "key", "marathon_pace" if self.distance == "marathon" else "goal_pace", body)
            if decision:
                sess["decision"] = True
            return sess
        i = min(level, len(table) - 1)
        while i > 0:
            n, length, jog = table[i]
            work_m = n * (length * self.unit_m if kind == "goal" else length / _mid(self.bands[band]["pace_s_per_km"]) * 1000)
            if work_m <= cap_m:
                break
            i -= 1
        n, length, jog = table[i]
        if kind == "goal":
            body = self.reps("goal", n, jog, distance_m=length * self.unit_m)
            name = "marathon pace" if self.distance == "marathon" else "race pace"
            return self.session("%s at %s" % (self.dist_label(n, length), name), "key",
                                "marathon_pace" if self.distance == "marathon" else "goal_pace", body)
        body = self.reps(band, n, jog, time_s=length)
        label = "threshold" if kind == "threshold" else "5K effort"
        return self.session("%s at %s" % (self.time_label(n, length), label), "key", kind, body)

    def max_hr_test(self):
        cap = self.s["athlete"]["max_hr"]
        vo2 = self.bands["vo2"]
        hard = {"type": "work", "time_s": 180, "pace_s_per_km": vo2["pace_s_per_km"], "hr_cap": cap, "band": "vo2",
                "note": "hard, uphill if you have one"}
        body = [{"type": "repeat", "count": 2, "steps": [hard, {"type": "recovery", "time_s": 120, "note": "jog"}]},
                {"type": "work", "time_s": 120, "note": "all-out to the top; the highest heart rate you see is the number"}]
        sess = self.session("Max heart rate test: 2 x 3 min hard, then 2 min all-out", "test", "max_hr_test", body)
        sess["notes"] = ("Sets the ceiling every zone hangs from. Only run it healthy and rested; skip and "
                         "reschedule within a week rather than dropping it.")
        return sess

    # -- block -------------------------------------------------------------
    def build(self):
        s, p = self.s, self.p
        race_date = dt.date.fromisoformat(s["race"]["date"])
        race_monday = race_date - dt.timedelta(days=race_date.weekday())
        lo, default, hi = p["weeks"]
        if s.get("start"):
            start = dt.date.fromisoformat(s["start"])
            start -= dt.timedelta(days=start.weekday())
            n = (race_monday - start).days // 7 + 1
        else:
            n = s.get("weeks") or default
            start = race_monday - dt.timedelta(days=7 * (n - 1))
        notes = []
        if n < lo:
            notes.append("%d weeks is shorter than the %d this distance normally needs; the plan holds fitness "
                         "and sharpens rather than builds." % (n, lo))
        if n > hi:
            notes.append("%d weeks is longer than one block should run (%d); add a base phase or a tune-up race first." % (n, hi))

        keep = max(0, min(len(p["taper"]), n - 3))
        taper = p["taper"][len(p["taper"]) - keep:] if keep else []
        build_n = n - 1 - len(taper)
        base_n = max(1, round(build_n * 0.3))
        spec_n = max(1, round(build_n * 0.35))
        phases = (["base"] * base_n + ["build"] * max(0, build_n - base_n - spec_n) + ["specific"] * spec_n)[:build_n]
        phases += ["taper"] * (len(taper) + 1)

        # weekly volume
        v0 = float(s["current_weekly_m"])
        peak = v0 * p["peak_gain"]
        vols, down, v = [], [], v0
        for i in range(build_n):
            is_down = (i % 4 == 3) and i < build_n - 1
            if is_down:
                vols.append(v * 0.8)
            else:
                v = min(peak, v * (1.08 if i else 1.0))
                vols.append(v)
            down.append(is_down)
        top = max(vols) if vols else v0
        for f in taper:
            vols.append(top * f)
            down.append(False)

        # long run
        longs, cur = [], max(float(s.get("longest_recent_m") or 0), v0 * 0.25)
        cur = min(cur, p["long_cap_m"])
        for i in range(build_n):
            if down[i]:
                longs.append(cur * 0.75)
                continue
            if i:
                cur = min(p["long_cap_m"], cur + p["long_step_m"])
            longs.append(min(cur, vols[i] * p["long_share"]))
        peak_long = max(longs) if longs else cur
        for j, f in enumerate(taper):
            longs.append(peak_long * (0.7 if j == len(taper) - 1 else 0.8))

        run_days = [x for x in WEEKDAYS if x in s["run_days"]]
        key_day, long_day = s["key_day"], s["long_day"]
        decision_week = max(2, n - p["decision_weeks_out"])
        test_week = 2 if not s["athlete"]["max_hr_verified"] else None
        if decision_week == test_week:
            test_week = 1
        used = {"threshold": 0, "vo2": 0, "goal": 0}
        weeks, logistics, decision_date = [], [], None

        for i in range(n):
            wk = i + 1
            monday = start + dt.timedelta(days=7 * i)
            phase = phases[i]
            is_race_week = i == n - 1
            days = []

            def date_of(name, monday=monday):
                return (monday + dt.timedelta(days=WEEKDAYS.index(name))).isoformat()

            if is_race_week:
                train = top * p["race_week"]
                before = [x for x in run_days if monday + dt.timedelta(days=WEEKDAYS.index(x)) < race_date]
                sharp_day = None
                for x in before:
                    gap = (race_date - (monday + dt.timedelta(days=WEEKDAYS.index(x)))).days
                    if 3 <= gap <= 5 and (sharp_day is None or x == key_day):
                        sharp_day = x
                for x in before:
                    gap = (race_date - (monday + dt.timedelta(days=WEEKDAYS.index(x)))).days
                    if x == sharp_day:
                        sess = self.key("goal", 0, 0, sharpen=True)
                        sess["notes"] = "Last run in race shoes. Short on purpose: you are checking the pace, not building."
                    else:
                        m = max(3000, min(6000, train / max(1, len(before)) * 0.8))
                        sess = self.easy(m, strides=(gap <= 2))
                    sess.update({"date": date_of(x), "status": "planned"})
                    days.append(sess)
                goal_band = self.bands["goal"]
                days.append({
                    "date": race_date.isoformat(), "kind": "race", "session": "race",
                    "title": "%s: goal %s" % (s["race"]["name"], fmt_clock(s["goal_time_s"])),
                    "distance_m": DISTANCES[self.distance], "status": "planned",
                    "steps": [{"type": "work", "distance_m": DISTANCES[self.distance],
                               "pace_s_per_km": goal_band["pace_s_per_km"], "hr_cap": goal_band["hr_cap"], "band": "goal"}],
                    "notes": "Pace by the elapsed-time chart at course markers, not the watch's average pace.",
                })
            else:
                vol, long_m = vols[i], longs[i]
                cap_m = max(3000.0, vol * 0.22) * (0.6 if phase == "taper" else 1.0)
                if wk == test_week:
                    key = self.max_hr_test()
                elif wk == decision_week:
                    key = self.key("goal", 0, 0, decision=True)
                    decision_date = date_of(key_day)
                else:
                    cycle = p["cycle"]["specific" if phase == "taper" else phase]
                    kind = cycle[sum(1 for q in phases[:i] if q == phase) % len(cycle)]
                    key = self.key(kind, used[kind], cap_m)
                    used[kind] += 1
                key.update({"date": date_of(key_day), "status": "planned"})
                long_sess = self.long(long_m, phase, i)
                long_sess.update({"date": date_of(long_day), "status": "planned"})
                others = [x for x in run_days if x not in (key_day, long_day)]
                rest = max(0.0, vol - key["distance_m"] - long_sess["distance_m"])
                each = max(4000.0, min(rest / max(1, len(others)), long_sess["distance_m"] * 0.7)) if others else 0
                for j, x in enumerate(others):
                    e = self.easy(each, strides=(j == 0))
                    e.update({"date": date_of(x), "status": "planned"})
                    days.append(e)
                days += [key, long_sess]
            days.sort(key=lambda x: x["date"])
            week = {"n": wk, "start": monday.isoformat(), "phase": phase,
                    "planned_m": round(sum(x.get("distance_m", 0) for x in days) / 100.0) * 100, "days": days}
            if i < len(down) and down[i]:
                week["down_week"] = True
            weeks.append(week)

            # dated logistics
            long_date = date_of(long_day)
            if not is_race_week:
                lifts = s.get("strength") == "lifts"
                if (race_date - dt.date.fromisoformat(date_of(key_day))).days > 10:
                    logistics.append({"date": date_of(key_day), "kind": "strength", "text": (
                        "Strength, after the session: maintenance only (2 sets of your usual lower-body lifts, nothing new)."
                        if lifts else
                        "Strength, 10 minutes after the run: calf raises, side planks, single-leg balance. Low soreness only; "
                        "heavy lifting waits for the next block.")})
                if p["fuel"] and phase in ("build", "specific") and longs[i] >= 14000:
                    logistics.append({"date": long_date, "kind": "fuel", "text": (
                        "Long run: practise race fueling. Take the gel or drink you will race with every 30 minutes and note "
                        "how your stomach handles it." if self.distance == "marathon" else
                        "Long run: practise one race gel around 40 minutes in, with the breakfast you plan for race morning.")})

        # decision rule
        goal = s["goal_time_s"]
        gpace = goal / (DISTANCES[self.distance] / 1000)
        gcap = self.bands["goal"]["hr_cap"]
        plan_goal = {"time_s": goal, "status": "provisional"}
        if s.get("baseline_pace_s_per_km"):
            plan_goal["baseline_pace_s_per_km"] = s["baseline_pace_s_per_km"]
        if decision_date:
            plan_goal["decision"] = {
                "session_date": decision_date,
                "tiers": [
                    {"id": "stretch", "goal_time_s": _round5(goal * 0.985),
                     "when": {"slowest_rep_pace_max_s_per_km": round(gpace * 0.985, 1), "highest_rep_hr_max": gcap - 2}},
                    {"id": "goal", "goal_time_s": goal,
                     "when": {"slowest_rep_pace_max_s_per_km": round(gpace * 1.005, 1), "highest_rep_hr_max": gcap}},
                    {"id": "conservative", "goal_time_s": _round5(goal * 1.015), "when": "otherwise"},
                ],
                "borderline": {"pace_s_per_km": 1.5, "hr_bpm": 1, "default": "slower_tier"},
                "runner_confirms": True,
            }
            for week in weeks:
                for day in week["days"]:
                    if day["date"] == decision_date:
                        # run the session inside a band that spans the stretch and goal tiers
                        for st in day["steps"]:
                            for leaf in st.get("steps", [st]):
                                if leaf["type"] == "work":
                                    leaf["pace_s_per_km"] = [round(gpace * 0.985, 1), round(gpace * 1.005, 1)]
                        day["notes"] = ("Decides the race goal. Run it rested, in race shoes, by effort inside the band; "
                                        "the heart-rate cap matters more than the fast end of the band.")
            logistics.append({"date": decision_date, "kind": "shoes",
                              "text": "Run the decision session in the shoes you intend to race in. Decide today, not race week."})
            logistics.append({"date": decision_date, "kind": "caffeine",
                              "text": "If you will use caffeine on race day, take the same dose at the same lead time before this session."})

        def before(n_days):
            return (race_date - dt.timedelta(days=n_days)).isoformat()

        if s.get("strength") == "lifts":
            logistics.append({"date": before(10), "kind": "strength", "text": "Last lower-body lifting session before the race."})
        logistics += [
            {"date": before(7), "kind": "check", "text": "First look at the race-day forecast. Note start-time temperature and wind."},
            {"date": before(2), "kind": "check", "text": "Final forecast, final kit choice, and confirm the race workout and pace chart are on the watch."},
            {"date": before(1), "kind": "gear", "text": "Lay out kit, bib, shoes, gels. Charge the watch."},
        ]
        if p["fuel"]:
            logistics.append({"date": before(3 if self.distance == "marathon" else 1), "kind": "fuel", "text": (
                "Start carbohydrate loading: raise carbohydrate at each meal for the last three days." if self.distance == "marathon"
                else "Carbohydrate-rich dinner; nothing new.")})
        logistics.sort(key=lambda x: x["date"])

        rules = dict(DEFAULT_RULES)
        if s.get("blocked_weekdays"):
            rules["blocked_weekdays"] = s["blocked_weekdays"]
        race = dict(s["race"])
        race["distance_m"] = DISTANCES[self.distance]
        plan = {"schema_version": 1, "units": self.units, "athlete": s["athlete"], "race": race,
                "goal": plan_goal, "bands": self.bands, "rules": rules, "weeks": weeks,
                "logistics": logistics, "log": []}
        warning = P.goal_check(s["threshold_pace_s_per_km"], self.distance, goal)
        if warning:
            notes.append(warning)
        return plan, notes

    def easy(self, metres, strides=False):
        cap = self.bands["easy"]["hr_cap"]
        m = self.half_units(metres)
        steps = [{"type": "easy", "distance_m": m, "hr_cap": cap, "band": "easy"}]
        title = "Easy %s" % self.fmt(m)
        if strides:
            steps.append({"type": "strides", "count": 6, "time_s": 20, "note": "6 x 20 s relaxed and fast, walk back"})
            title += " + 6 strides"
        return {"kind": "easy", "session": "strides" if strides else "easy", "title": title,
                "distance_m": m, "hr_cap": cap, "steps": steps}

    def long(self, metres, phase, index):
        cap = self.bands["easy"]["hr_cap"]
        m = self.half_units(metres)
        finish_band = None
        if self.distance == "marathon" and phase in ("build", "specific") and index % 2 == 1:
            finish_band, share, label = "goal", 0.35, "marathon pace"
        elif self.distance == "half" and phase == "specific":
            finish_band, share, label = "steady", 0.25, "steady"
        if not finish_band:
            return {"kind": "long", "session": "long", "title": "Long %s easy" % self.fmt(m), "distance_m": m,
                    "hr_cap": cap, "steps": [{"type": "easy", "distance_m": m, "hr_cap": cap, "band": "easy"}]}
        fin = self.half_units(m * share)
        b = self.bands[finish_band]
        return {"kind": "long", "session": "long_steady_finish",
                "title": "Long %s, last %s %s" % (self.fmt(m), self.fmt(fin), label), "distance_m": m, "hr_cap": b["hr_cap"],
                "steps": [{"type": "easy", "distance_m": m - fin, "hr_cap": cap, "band": "easy"},
                          {"type": "steady", "distance_m": fin, "pace_s_per_km": b["pace_s_per_km"], "hr_cap": b["hr_cap"],
                           "band": finish_band}]}

    def half_units(self, metres):
        """Round to half a kilometre or half a mile, so titles and distances agree."""
        return round(round(metres / self.unit_m * 2) / 2.0 * self.unit_m, 1)

    def fmt(self, metres):
        return "%s %s" % (_num(round(metres / self.unit_m * 2) / 2.0), self.units)


def build_block(spec):
    """spec -> (plan, notes). See examples/*/block-input.json for the input shape."""
    return Builder(spec).build()


def describe(distance):
    p = PROFILE[distance]
    return "%s: %d-%d weeks (default %d), long run to %.0f km, %d-week taper" % (
        DISTANCE_NAMES[distance], p["weeks"][0], p["weeks"][2], p["weeks"][1], p["long_cap_m"] / 1000,
        len(p["taper"]) + 1)
