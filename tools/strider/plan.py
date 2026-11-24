"""Load, validate and walk a plan file.

Validation has two layers: the JSON Schema (structure) and the coaching checks
(the rules a plan must satisfy before any workout is generated from it).
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re

SCHEMA_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "schema", "plan.schema.json")
RUN_KINDS = ("key", "long", "easy", "test", "race")
SPIKE_LIMIT = 1.10        # no run more than 10% past the longest of the previous 30 days (Frandsen et al. 2025)
SPIKE_WINDOW_DAYS = 30
WEEKDAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")

DEFAULT_RULES = {
    "recovery_go_h": 12, "recovery_move_h": 24, "match_window_days": 2,
    "pace_tolerance_s_per_km": 3, "fade_pct": 3, "rep_spread_s_per_km": 12,
    "sleep_floor": 70, "readiness_floor": 50, "rhr_rise_bpm": 5,
    "vo2_noise": 0.5, "max_snapshot_age_h": 26,
}


def load(path):
    with open(path) as fh:
        return json.load(fh)


def save(plan, path):
    with open(path, "w") as fh:
        json.dump(plan, fh, indent=2)
        fh.write("\n")


def rule(plan, name):
    return plan.get("rules", {}).get(name, DEFAULT_RULES.get(name))


def d(text):
    return dt.date.fromisoformat(text)


def all_days(plan):
    for week in plan["weeks"]:
        for day in week["days"]:
            yield week, day


def find_day(plan, date):
    for _, day in all_days(plan):
        if day["date"] == date:
            return day
    return None


def flat_steps(steps):
    """Expand repeat groups into the order the steps are run."""
    out = []
    for s in steps or []:
        if s["type"] == "repeat":
            for _ in range(s.get("count", 1)):
                out.extend(flat_steps(s.get("steps")))
        else:
            out.append(s)
    return out


def leaf_steps(steps):
    """Every non-repeat step once, however many times it is repeated."""
    out = []
    for s in steps or []:
        if s["type"] == "repeat":
            out.extend(leaf_steps(s.get("steps")))
        else:
            out.append(s)
    return out


# ---------------------------------------------------------------- JSON Schema

_TYPES = {"string": str, "boolean": bool, "array": list, "object": dict, "null": type(None)}


def _is_type(value, name):
    if name == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if name == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    return isinstance(value, _TYPES[name])


def _check(value, schema, root, path, errors):
    if "$ref" in schema:
        node = root
        for part in schema["$ref"].lstrip("#/").split("/"):
            node = node[part]
        return _check(value, node, root, path, errors)
    if "const" in schema and value != schema["const"]:
        errors.append("%s: must be %r" % (path, schema["const"]))
    if "enum" in schema and value not in schema["enum"]:
        errors.append("%s: %r is not one of %s" % (path, value, schema["enum"]))
    if "oneOf" in schema:
        matches = 0
        for option in schema["oneOf"]:
            sub = []
            _check(value, option, root, path, sub)
            matches += not sub
        if matches != 1:
            errors.append("%s: must match exactly one allowed shape" % path)
    if "type" in schema:
        names = schema["type"] if isinstance(schema["type"], list) else [schema["type"]]
        if not any(_is_type(value, n) for n in names):
            errors.append("%s: expected %s" % (path, " or ".join(names)))
            return
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if "minimum" in schema and value < schema["minimum"]:
            errors.append("%s: %s is below %s" % (path, value, schema["minimum"]))
        if "maximum" in schema and value > schema["maximum"]:
            errors.append("%s: %s is above %s" % (path, value, schema["maximum"]))
    if isinstance(value, str) and "pattern" in schema and not re.search(schema["pattern"], value):
        errors.append("%s: %r does not match %s" % (path, value, schema["pattern"]))
    if isinstance(value, list):
        if len(value) < schema.get("minItems", 0):
            errors.append("%s: needs at least %d items" % (path, schema["minItems"]))
        if "maxItems" in schema and len(value) > schema["maxItems"]:
            errors.append("%s: at most %d items" % (path, schema["maxItems"]))
        if "items" in schema:
            for i, item in enumerate(value):
                _check(item, schema["items"], root, "%s[%d]" % (path, i), errors)
    if isinstance(value, dict):
        props = schema.get("properties", {})
        for name in schema.get("required", []):
            if name not in value:
                errors.append("%s: missing %r" % (path, name))
        if len(value) < schema.get("minProperties", 0):
            errors.append("%s: needs at least %d properties" % (path, schema["minProperties"]))
        extra = schema.get("additionalProperties", True)
        for name, item in value.items():
            if name in props:
                _check(item, props[name], root, "%s.%s" % (path, name), errors)
            elif extra is False:
                errors.append("%s: unknown property %r" % (path, name))
            elif isinstance(extra, dict):
                _check(item, extra, root, "%s.%s" % (path, name), errors)


def schema_errors(plan, schema=None):
    """Validate against schema/plan.schema.json with a small built-in validator.

    It covers the subset of JSON Schema the plan schema uses, so the tools need
    no third-party packages. The test suite cross-checks it against the
    `jsonschema` package.
    """
    if schema is None:
        schema = load(SCHEMA_PATH)
    errors = []
    _check(plan, schema, schema, "plan", errors)
    return errors


# ------------------------------------------------------------ coaching checks

def coaching_checks(plan):
    """Return (errors, warnings). Errors block generating workouts."""
    errors, warnings = [], []
    weeks = plan["weeks"]
    race = plan["race"]

    for i, week in enumerate(weeks):
        start = d(week["start"])
        if week["n"] != i + 1:
            errors.append("week %d: numbered %d" % (i + 1, week["n"]))
        if i and (start - d(weeks[i - 1]["start"])).days != 7:
            errors.append("week %d: does not start 7 days after week %d" % (week["n"], weeks[i - 1]["n"]))
        for day in week["days"]:
            if not 0 <= (d(day["date"]) - start).days <= 6:
                errors.append("%s: outside week %d" % (day["date"], week["n"]))

    race_days = [day for _, day in all_days(plan) if day["kind"] == "race"]
    if len(race_days) != 1 or race_days[0]["date"] != race["date"]:
        errors.append("the plan needs exactly one race day, on race.date (%s)" % race["date"])

    blocked = set(rule(plan, "blocked_weekdays") or [])
    previous_key = None
    for week, day in all_days(plan):
        where = "%s (%s)" % (day["date"], day["title"])
        steps = leaf_steps(day.get("steps"))
        for s in steps:
            band = s.get("pace_s_per_km")
            if band and band[0] > band[1]:
                errors.append("%s: pace band is [fast, slow]; %s is reversed" % (where, band))
            if s["type"] == "work" and day.get("session") != "max_hr_test" and (not band or not s.get("hr_cap")):
                errors.append("%s: every work step needs a pace band and a heart-rate cap" % where)
            if s["type"] == "steady" and not s.get("hr_cap"):
                errors.append("%s: every steady or finishing segment needs a heart-rate cap" % where)
        if day["kind"] in ("easy", "long") and not day.get("hr_cap"):
            errors.append("%s: easy and long runs need a heart-rate cap" % where)
        if day["kind"] in ("key", "test") and not any(s["type"] == "work" for s in steps):
            errors.append("%s: a key session needs at least one work step" % where)
        if day["kind"] in RUN_KINDS and not day.get("distance_m"):
            errors.append("%s: run days need distance_m (planned total)" % where)
        if day["kind"] == "key":
            if WEEKDAYS[d(day["date"]).weekday()] in blocked:
                errors.append("%s: key session on a blocked weekday" % where)
            if previous_key and (d(day["date"]) - previous_key).days == 1:
                warnings.append("%s: key sessions on consecutive days" % where)
            previous_key = d(day["date"])

    # Decision rule: must partition every outcome.
    decision = plan["goal"].get("decision")
    if decision:
        tiers = decision["tiers"]
        if tiers[-1]["when"] != "otherwise":
            errors.append("goal.decision: the last tier must be `otherwise`, so every result lands in a tier")
        for t in tiers[:-1]:
            if t["when"] == "otherwise":
                errors.append("goal.decision: tier %s is `otherwise` but is not last; later tiers can never match" % t["id"])
        times = [t["goal_time_s"] for t in tiers]
        if times != sorted(times):
            errors.append("goal.decision: tiers must run from fastest goal to slowest")
        conds = [t["when"] for t in tiers[:-1] if isinstance(t["when"], dict)]
        for a, b in zip(conds, conds[1:]):
            pa, pb = a.get("slowest_rep_pace_max_s_per_km"), b.get("slowest_rep_pace_max_s_per_km")
            if pa is not None and pb is not None and pb < pa:
                errors.append("goal.decision: a later tier demands a faster pace than an earlier one")
        day = find_day(plan, decision["session_date"])
        if not day or not day.get("decision"):
            errors.append("goal.decision.session_date must be a day marked \"decision\": true")
    elif plan["goal"]["status"] == "provisional":
        warnings.append("goal is provisional but there is no decision rule to confirm it")

    # Max-HR test early, unless verified or waived with a reason.
    athlete = plan["athlete"]
    if not athlete["max_hr_verified"] and not rule(plan, "max_hr_test_waived"):
        tests = [week["n"] for week, day in all_days(plan) if day.get("session") == "max_hr_test"]
        limit = max(2, -(-len(weeks) // 3))
        if not tests:
            errors.append("max HR is unverified and no max_hr_test session is scheduled "
                          "(or set rules.max_hr_test_waived to the reason)")
        elif min(tests) > limit:
            errors.append("max_hr_test is in week %d; schedule it by week %d so it cannot slip off the end"
                          % (min(tests), limit))

    # Volume shape.
    # training volume per week; the race itself is not training load to ramp toward
    planned = [w["planned_m"] - sum(day.get("distance_m", 0) for day in w["days"] if day["kind"] == "race")
               for w in weeks]
    for i, week in enumerate(weeks):
        total = sum(day.get("distance_m", 0) for day in week["days"] if day["kind"] in RUN_KINDS)
        if week["planned_m"] and abs(total - week["planned_m"]) / week["planned_m"] > 0.1:
            warnings.append("week %d: days add up to %.1f km but planned_m says %.1f km"
                            % (week["n"], total / 1000, week["planned_m"] / 1000))
        if i and planned[i - 1] and not weeks[i - 1].get("down_week") and planned[i] > planned[i - 1] * 1.12:
            warnings.append("week %d: volume rises %.0f%% on the week before"
                            % (week["n"], (planned[i] / planned[i - 1] - 1) * 100))
    if len(weeks) >= 4:
        peak = max(planned[:-1])
        final_training = planned[-1]
        if final_training > 0.6 * peak:
            warnings.append("race week still holds %.0f%% of peak volume before the race; a taper cuts it to about half"
                            % (final_training / peak * 100))

    # Single-run spikes. The race itself is exempt: it is meant to be the longest run.
    runs = [(day["date"], day.get("distance_m", 0), day["title"]) for _, day in all_days(plan)
            if day["kind"] in RUN_KINDS and day["kind"] != "race" and day.get("distance_m")]
    for spike in run_spikes(runs, plan.get("baseline")):
        errors.append("%s (%s): %.1f km is %.0f%% longer than the longest run in the previous 30 days (%.1f km); "
                      "keep each run within %d%% of it" % (spike["date"], spike["label"], spike["meters"] / 1000,
                                                           spike["pct_over"], spike["reference_m"] / 1000,
                                                           round((SPIKE_LIMIT - 1) * 100)))

    kinds = set(item["kind"] for item in plan.get("logistics", []))
    for needed, why in (("strength", "strength work"), ("shoes", "race-shoe decision"),
                        ("check", "weather and watch checks")):
        if needed not in kinds:
            warnings.append("logistics has no dated %s entry (%s)" % (needed, why))
    if race["distance"] in ("half", "marathon") and "fuel" not in kinds:
        warnings.append("logistics has no dated fuel rehearsal; gels and breakfast are only used on race day if practiced")
    return errors, warnings


def run_spikes(runs, baseline=None, limit=SPIKE_LIMIT, window=SPIKE_WINDOW_DAYS):
    """Runs longer than `limit` x the longest run in the previous `window` days.

    runs: [(date_str, meters, label)]. baseline: {"as_of", "longest_run_m"} for the time before
    the first run listed; it counts while its as_of date is inside the window.
    Returns [{"date", "meters", "reference_m", "label", "pct_over"}]. A run with nothing to
    compare against (no earlier run and no baseline) is not flagged.
    """
    out = []
    runs = sorted(runs, key=lambda r: r[0])
    for date, meters, label in runs:
        day = d(date)
        ref = [m for dt_, m, _ in runs if 0 < (day - d(dt_)).days <= window]
        if baseline and baseline.get("longest_run_m") and 0 <= (day - d(baseline["as_of"])).days <= window:
            ref.append(baseline["longest_run_m"])
        if ref and meters > limit * max(ref) + 1:
            out.append({"date": date, "meters": meters, "reference_m": max(ref), "label": label,
                        "pct_over": round((meters / max(ref) - 1) * 100, 1)})
    return out


def validate(plan):
    errors = schema_errors(plan)
    if errors:
        return errors, []
    return coaching_checks(plan)
