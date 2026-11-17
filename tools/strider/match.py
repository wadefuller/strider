"""Match recorded runs to planned days.

People move sessions: the long run lands on Saturday, the Wednesday workout on
Thursday. So a run is matched to a planned day by what kind of run it is,
within a window of days, not by date alone.
"""
from __future__ import annotations

import datetime as dt
import math

from . import laps as L
from .plan import RUN_KINDS, all_days, d, rule

ORDER = ("race", "key", "test", "long", "easy")
MAX_SCORE = 3.5


def is_run(activity):
    return "run" in str(activity.get("type") or "").lower()


def activity_date(activity):
    return str(activity.get("start_time") or "")[:10]


def is_structured(lap_list):
    """True when the laps show a workout rather than one continuous run."""
    if not lap_list:
        return False
    kinds = set(L._kind(l) for l in lap_list if (l.get("distance_meters") or 0) > L.MIN_LAP_M)
    if len(kinds) > 1 and kinds & set(L.WORK_LABELS):
        return True
    return len(L.build_reps(lap_list)) >= 2


def outings(activities, splits):
    """Group a day's runs (warm-up, session, cool-down recorded separately) into one outing."""
    by_date = {}
    for a in activities:
        if is_run(a) and activity_date(a):
            by_date.setdefault(activity_date(a), []).append(a)
    out = {}
    for date, acts in by_date.items():
        structured = [a for a in acts if is_structured(splits.get(str(a["id"])))]
        pool = structured or acts
        main = max(pool, key=lambda a: a.get("distance_meters") or 0)
        out[date] = {
            "date": date, "main": main, "activities": acts, "structured": bool(structured),
            "distance_m": sum(a.get("distance_meters") or 0 for a in acts),
            "main_distance_m": main.get("distance_meters") or 0,
        }
    return out


def match(plan, activities, splits, today):
    """Return {plan_date: {...}} plus the list of runs that match nothing.

    today: datetime.date. Days after today stay "planned".
    """
    window = rule(plan, "match_window_days")
    outs = outings(activities, splits)
    used = set()
    result = {}
    days = [day for _, day in all_days(plan) if day["kind"] in RUN_KINDS]
    for kind in ORDER:
        # score every (planned day, outing) pair of this kind, then take the best pairs first,
        # so an unrun day cannot grab a run that sits closer to another day
        pairs = []
        for day in (x for x in days if x["kind"] == kind and x["status"] != "skipped"):
            day_date = d(day["date"])
            planned = day.get("distance_m") or 0
            for date, o in outs.items():
                offset = abs((d(date) - day_date).days)
                if date in used or offset > window or d(date) > today:
                    continue
                score = float(offset)
                size = o["main_distance_m"] if kind in ("key", "test", "race") else o["distance_m"]
                if planned and size:
                    score += abs(math.log(size / planned)) * 3
                if kind in ("key", "test") and not o["structured"]:
                    score += 2
                if kind in ("easy", "long") and o["structured"]:
                    score += 1.5
                if score <= MAX_SCORE:
                    pairs.append((score, day["date"], date))
        for score, day_date, date in sorted(pairs):
            if day_date in result or date in used:
                continue
            used.add(date)
            o = outs[date]
            result[day_date] = {
                "status": "done" if date == day_date else "moved",
                "ran_on": date, "activity_id": o["main"]["id"],
                "activity_ids": [a["id"] for a in o["activities"]],
                "distance_m": round(o["distance_m"], 1),
            }
    for day in days:
        if day["date"] in result or day["status"] == "skipped":
            continue
        overdue = (today - d(day["date"])).days
        if overdue > window:
            result[day["date"]] = {"status": "missed"}
        elif overdue >= 0 and day["status"] == "planned":
            result[day["date"]] = {"status": "planned", "note": "not found yet; may still be run within the window"}
    extras = [{"date": date, "activity_id": o["main"]["id"], "distance_m": round(o["distance_m"], 1)}
              for date, o in sorted(outs.items()) if date not in used
              and d(plan["weeks"][0]["start"]) <= d(date) <= today]
    return result, extras


def week_of(plan, date):
    for week in plan["weeks"]:
        start = d(week["start"])
        if start <= d(date) <= start + dt.timedelta(days=6):
            return week
    return None
