"""Turn a planned day into the workout JSON garmin_mcp's `upload_workout` accepts.

Format rules followed here come from the garmin_mcp documentation:
  - regular steps are ExecutableStepDTO, repeats are RepeatGroupDTO with an
    iterations end condition (conditionTypeId 7);
  - stepOrder is one depth-first counter across the whole workout;
  - pace targets are speeds in meters per second (target type 6, pace.zone);
  - a custom heart-rate range is target type 4 with targetValueOne/Two in bpm;
  - target values sit on the step, beside targetType, never inside it.

A Garmin step carries one target. Work steps get the pace band and the
heart-rate cap goes in the step note; steps with only a cap get a heart-rate
target. The watch measures its own distance, so pace targets are converted
with the runner's watch_distance_factor (not on a track).
"""
from __future__ import annotations

from .units import fmt_band, fmt_dist, fmt_clock

RUNNING = {"sportTypeId": 1, "sportTypeKey": "running"}
STEP_TYPE = {"warmup": (1, "warmup"), "cooldown": (2, "cooldown"), "work": (3, "interval"),
             "steady": (3, "interval"), "easy": (3, "interval"), "recovery": (4, "recovery")}
NO_TARGET = {"workoutTargetTypeId": 1, "workoutTargetTypeKey": "no.target"}
HR_RANGE_BELOW_CAP = 30


def _end(step):
    if step.get("distance_m"):
        return {"endCondition": {"conditionTypeId": 3, "conditionTypeKey": "distance"},
                "endConditionValue": float(round(step["distance_m"], 1))}
    if step.get("time_s"):
        return {"endCondition": {"conditionTypeId": 2, "conditionTypeKey": "time"},
                "endConditionValue": float(step["time_s"])}
    return {"endCondition": {"conditionTypeId": 1, "conditionTypeKey": "lap.button"}}


def _target(step, factor):
    band = step.get("pace_s_per_km")
    if band:
        # true pace -> the pace the watch will display for it
        slow, fast = band[1] / factor, band[0] / factor
        return {"targetType": {"workoutTargetTypeId": 6, "workoutTargetTypeKey": "pace.zone"},
                "targetValueOne": round(1000.0 / slow, 4), "targetValueTwo": round(1000.0 / fast, 4)}
    if step.get("hr_cap"):
        return {"targetType": {"workoutTargetTypeId": 4, "workoutTargetTypeKey": "heart.rate.zone"},
                "targetValueOne": step["hr_cap"] - HR_RANGE_BELOW_CAP, "targetValueTwo": step["hr_cap"]}
    return {"targetType": dict(NO_TARGET)}


def to_garmin(day, plan, week_n=None):
    """Build the workout_data dict for one planned day."""
    units = plan["units"]
    factor = 1.0 if day.get("terrain") == "track" else plan["athlete"]["watch_distance_factor"]
    counter = [0]

    def order():
        counter[0] += 1
        return counter[0]

    def group(count, children):
        n = order()
        return {"type": "RepeatGroupDTO", "stepOrder": n, "stepType": {"stepTypeId": 6, "stepTypeKey": "repeat"},
                "numberOfIterations": count,
                "endCondition": {"conditionTypeId": 7, "conditionTypeKey": "iterations"},
                "endConditionValue": float(count),
                "workoutSteps": [conv(c) for c in children]}

    def conv(step):
        if step["type"] == "repeat":
            return group(step.get("count", 1), step.get("steps") or [])
        if step["type"] == "strides":
            return group(step.get("count", 6), [
                {"type": "work", "time_s": step.get("time_s", 20), "note": "relaxed and fast"},
                {"type": "recovery", "time_s": 60, "note": "walk back"}])
        type_id, key = STEP_TYPE[step["type"]]
        out = {"type": "ExecutableStepDTO", "stepOrder": order(),
               "stepType": {"stepTypeId": type_id, "stepTypeKey": key}}
        out.update(_end(step))
        out.update(_target(step, factor))
        notes = []
        if step.get("pace_s_per_km") and step.get("hr_cap"):
            notes.append("HR cap %d" % step["hr_cap"])
        if step.get("note"):
            notes.append(step["note"])
        if notes:
            out["description"] = ". ".join(notes)
        return out

    steps = [conv(s) for s in day.get("steps") or []]
    prefix = ("W%d " % week_n) if week_n else ""
    name = (prefix + day["title"])[:60]
    desc = [describe_steps(day, units)]
    if day.get("notes"):
        desc.append(day["notes"])
    return {"workoutName": name, "description": " ".join(desc)[:1000], "sportType": dict(RUNNING),
            "workoutSegments": [{"segmentOrder": 1, "sportType": dict(RUNNING), "workoutSteps": steps}]}


def _step_text(step, units):
    if step["type"] == "repeat":
        inner = ", ".join(_step_text(s, units) for s in step.get("steps") or [])
        return "%d x (%s)" % (step.get("count", 1), inner)
    if step["type"] == "strides":
        return "%d x %d s strides" % (step.get("count", 6), step.get("time_s", 20))
    size = fmt_dist(step["distance_m"], units) if step.get("distance_m") else (
        fmt_clock(step["time_s"]) + " min" if step.get("time_s") else "")
    label = {"warmup": "warm-up", "cooldown": "cool-down", "work": "", "steady": "steady",
             "easy": "easy", "recovery": "jog"}[step["type"]]
    text = " ".join(x for x in (size, label) if x)
    if step.get("pace_s_per_km"):
        text += " at " + fmt_band(step["pace_s_per_km"], units)
    if step.get("hr_cap") and step["type"] in ("work", "steady"):
        text += ", HR cap %d" % step["hr_cap"]
    return text


def describe_steps(day, units):
    """One line a runner can read on a phone: warm-up, main set, cool-down, with targets."""
    parts = [_step_text(s, units) for s in day.get("steps") or []]
    text = "; ".join(p for p in parts if p)
    if day.get("hr_cap") and day["kind"] in ("easy", "long"):
        text += ". HR cap %d" % day["hr_cap"]
    return text + ("." if text and not text.endswith(".") else "")
