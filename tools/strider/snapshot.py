"""Build the snapshot the dashboard and the skills read.

Raw Garmin tool results are saved as JSON under a raw folder (layout in
reference/garmin.md). This module reads them with the plan, does every
calculation once, and writes:

  snapshot.json   the computed state, for skills and for diffing
  data.js         `window.STRIDER = {plan, snapshot}` for the static dashboard

The dashboard renders; it does not re-derive session metrics.
"""
from __future__ import annotations

import datetime as dt
import glob
import json
import os

from . import judge as J
from . import laps as L
from . import match as M
from .plan import RUN_KINDS, all_days, d, rule


def _unwrap(path):
    with open(path) as fh:
        body = json.load(fh)
    if isinstance(body, dict) and "result" in body and "fetched_at" in body:
        return body["result"], body["fetched_at"]
    stamp = dt.datetime.fromtimestamp(os.path.getmtime(path), dt.timezone.utc)
    return body, stamp.isoformat(timespec="seconds")


def load_raw(raw_dir):
    """Read every saved tool result. Returns (data, fetched_at_by_source)."""
    data = {"activities": [], "splits": {}, "typed_splits": {}}
    fetched = {}
    seen = set()
    for path in sorted(glob.glob(os.path.join(raw_dir, "activities*.json"))):
        body, at = _unwrap(path)
        fetched["activities"] = max(at, fetched.get("activities", ""))
        for a in (body.get("activities") if isinstance(body, dict) else body) or []:
            if a.get("id") not in seen:
                seen.add(a.get("id"))
                data["activities"].append(a)
    for folder in ("splits", "typed_splits"):
        for path in glob.glob(os.path.join(raw_dir, folder, "*.json")):
            body, _ = _unwrap(path)
            key = os.path.splitext(os.path.basename(path))[0]
            data[folder][key] = body.get("laps") if folder == "splits" and isinstance(body, dict) else body
    for name in ("hrv_trend", "readiness", "recovery_time", "sleep", "vo2max_trend", "rhr"):
        path = os.path.join(raw_dir, name + ".json")
        if os.path.exists(path):
            data[name], fetched[name] = _unwrap(path)
    return data, fetched


def _date_of(row):
    return row.get("date") or row.get("calendar_date") or row.get("calendarDate")


def recovery_block(plan, raw, today):
    """Everything the go/no-go rule needs, with the flags already worked out.

    Recovery hours are stored with the time Garmin reported them; readers count
    them down from that time rather than showing a stale number.
    """
    athlete = plan["athlete"]
    base = athlete.get("hrv_baseline_ms")
    rec = {"hrv_baseline_ms": base}
    trend = (raw.get("hrv_trend") or {}).get("trend") or []
    nights = [r for r in trend if r.get("last_night_avg_hrv_ms") is not None]
    if nights:
        rec["hrv_last"] = nights[-1]["last_night_avg_hrv_ms"]
        rec["hrv_status"] = nights[-1].get("status")
        rec["hrv_missing_nights"] = len(trend) - len(nights)
        weekly = [r["weekly_avg_hrv_ms"] for r in trend if r.get("weekly_avg_hrv_ms") is not None]
        last7 = [r["last_night_avg_hrv_ms"] for r in nights[-7:]]
        rec["hrv_7d"] = weekly[-1] if weekly else round(sum(last7) / len(last7))
    readiness = raw.get("readiness")
    rows = readiness if isinstance(readiness, list) else (readiness or {}).get("readiness") or []
    if rows:
        morning = [r for r in rows if r.get("context") == "AFTER_WAKEUP_RESET"]
        pick = morning[0] if morning else rows[0]
        rec["readiness"] = pick.get("score")
        rec["readiness_kind"] = "morning" if morning else "latest"
    rt = raw.get("recovery_time") or {}
    if rt.get("remaining_hours") is not None:
        rec["recovery_hours"] = rt["remaining_hours"]
        rec["recovery_as_of"] = rt.get("as_of") or rt.get("timestamp")
    scored = [n for n in (raw.get("sleep") or {}).get("nights") or [] if isinstance(n.get("sleep_score"), (int, float))]
    if scored:
        floor = rule(plan, "sleep_floor")
        run = 0
        for n in scored:
            run = run + 1 if n["sleep_score"] < floor else 0
        rec["sleep_avg"] = round(sum(n["sleep_score"] for n in scored) / len(scored))
        rec["sleep_low_run"] = run
        rec["sleep_nights"] = len(scored)
    rhr_days = sorted((raw.get("rhr") or {}).get("days") or [], key=lambda r: r["date"])
    if rhr_days and athlete.get("resting_hr"):
        limit = athlete["resting_hr"] + rule(plan, "rhr_rise_bpm")
        up = 0
        for r in rhr_days:
            up = up + 1 if r["resting_hr_bpm"] >= limit else 0
        rec["rhr_last"] = rhr_days[-1]["resting_hr_bpm"]
        rec["rhr_up_days"] = up

    flags = []
    if base and rec.get("hrv_last") is not None and rec["hrv_last"] < base[0]:
        flags.append("HRV last night %d ms is below your %d to %d baseline" % (rec["hrv_last"], base[0], base[1]))
    if rec.get("readiness") is not None and rec["readiness"] < rule(plan, "readiness_floor"):
        flags.append("readiness under %d" % rule(plan, "readiness_floor"))
    if rec.get("sleep_low_run", 0) >= 3:
        flags.append("sleep under %d for %d nights running" % (rule(plan, "sleep_floor"), rec["sleep_low_run"]))
    rec["by_heart_rate"] = bool(flags)
    rec["flags"] = flags
    rec["swap_key_for_easy"] = bool(base and rec.get("hrv_7d") is not None and rec["hrv_7d"] < base[0]
                                    and rec.get("rhr_up_days", 0) >= 2)
    return rec


def recovery_verdict(rec, plan, now):
    """The go/no-go rule, in one place. `now` is an aware or naive datetime."""
    hours = None
    if rec.get("recovery_hours") is not None and rec.get("recovery_as_of"):
        try:
            as_of = dt.datetime.fromisoformat(str(rec["recovery_as_of"]).split(".")[0])
            elapsed = (now.replace(tzinfo=None) - as_of.replace(tzinfo=None)).total_seconds() / 3600
            hours = max(0.0, rec["recovery_hours"] - max(0.0, elapsed))
        except ValueError:
            hours = rec["recovery_hours"]
    if rec.get("swap_key_for_easy"):
        verdict = "easy_instead"
    elif hours is not None and hours > rule(plan, "recovery_move_h"):
        verdict = "move"
    elif rec.get("by_heart_rate"):
        verdict = "by_heart_rate"
    elif hours is not None and hours > rule(plan, "recovery_go_h"):
        verdict = "cap_firm"
    elif hours is None and not rec.get("hrv_last"):
        verdict = "unknown"
    else:
        verdict = "go"
    return {"verdict": verdict, "recovery_hours_now": None if hours is None else round(hours, 1)}


def build(plan, raw, fetched, now):
    """Compute the snapshot. `now` is a datetime; its date is 'today'."""
    today = now.date()
    factor = plan["athlete"]["watch_distance_factor"]
    splits, typed = raw["splits"], raw["typed_splits"]
    matched, extras = M.match(plan, raw["activities"], splits, today)
    acts = dict((a["id"], a) for a in raw["activities"])

    days, judged = {}, []
    for _, day in all_days(plan):
        if day["kind"] not in RUN_KINDS:
            continue
        m = matched.get(day["date"])
        if not m:
            continue
        entry = dict(m)
        aid = m.get("activity_id")
        lap_list = splits.get(str(aid)) if aid else None
        if aid and lap_list:
            terrain = day.get("terrain") or ("track" if "track" in str(acts[aid].get("type")) else "rolling")
            use_factor = 1.0 if terrain == "track" else factor
            if day["kind"] in ("key", "test"):
                summary = L.summarize(lap_list, use_factor, terrain)
                if summary:
                    judgement = J.judge_key(summary, day, plan)
                    form = L.form_by_rep(typed.get(str(aid)), summary)
                    entry.update({"summary": summary, "judgement": judgement, "flags": summary["flags"]})
                    if form:
                        entry["form"] = {"reps": form, "drift": L.form_drift(form)}
                    if day.get("decision") and plan["goal"].get("decision"):
                        entry["decision"] = J.evaluate_decision(plan["goal"]["decision"], summary)
                    judged.append((m["ran_on"], judgement))
            else:
                judgement = J.judge_long(lap_list, day, plan, use_factor, typed.get(str(aid)))
                if judgement:
                    entry.update({"judgement": judgement, "flags": judgement.get("flags", [])})
                    # only runs with a pace prescription count toward the faster-than-prescribed streak
                    if judgement.get("finish") or judgement["over_prescribed"]:
                        judged.append((m["ran_on"], judgement))
        elif aid:
            entry["flags"] = [{"code": "no_laps", "rep": None,
                               "detail": "No laps saved for this run, so it has not been judged. "
                                         "A session is never described from its whole-run average."}]
        days[day["date"]] = entry

    weeks = []
    for week in plan["weeks"]:
        start = d(week["start"])
        end = start + dt.timedelta(days=6)
        run_m = sum(a.get("distance_meters") or 0 for a in raw["activities"]
                    if M.is_run(a) and M.activity_date(a) and start <= d(M.activity_date(a)) <= end)
        weeks.append({"n": week["n"], "planned_m": week["planned_m"],
                      "run_m": round(run_m, 1) if start <= today else None})

    easy = []
    for _, day in all_days(plan):
        e = days.get(day["date"], {})
        j = e.get("judgement")
        if day["kind"] == "easy" and j and j["whole"].get("efficiency"):
            easy.append({"date": e["ran_on"], "efficiency": j["whole"]["efficiency"],
                         "gain_m_per_km": j["whole"]["gain_m_per_km"]})

    vo2 = [{"date": _date_of(t), "value": t["vo2_max"]}
           for t in (raw.get("vo2max_trend") or {}).get("trend") or [] if isinstance(t.get("vo2_max"), (int, float))]
    vo2_note = None
    if len(vo2) >= 2:
        cutoff = d(vo2[-1]["date"]) - dt.timedelta(days=28)
        earlier = [p for p in vo2 if d(p["date"]) <= cutoff] or vo2[:1]
        delta = vo2[-1]["value"] - earlier[-1]["value"]
        noise = rule(plan, "vo2_noise")
        vo2_note = {"delta_4wk": round(delta, 1),
                    "direction": "flat" if abs(delta) < noise else ("up" if delta > 0 else "down")}

    block_start = d(plan["weeks"][0]["start"])
    max_seen = None
    for a in raw["activities"]:
        hr = a.get("max_hr_bpm")
        if M.is_run(a) and isinstance(hr, (int, float)) and M.activity_date(a) and d(M.activity_date(a)) >= block_start:
            if max_seen is None or hr > max_seen["bpm"]:
                max_seen = {"bpm": int(hr), "date": M.activity_date(a)}

    rec = recovery_block(plan, raw, today)
    rec.update(recovery_verdict(rec, plan, now))

    notices = []
    athlete = plan["athlete"]
    if not athlete["max_hr_verified"]:
        notices.append({"code": "max_hr_unverified",
                        "detail": "Max heart rate has not been confirmed by an all-out effort. Heart-rate caps come from "
                                  "threshold heart rate and stand; anything stated as a share of max is provisional."})
    if max_seen and max_seen["bpm"] > athlete["max_hr"]:
        notices.append({"code": "new_max_hr",
                        "detail": "A run on %s recorded %d bpm, above the %d in the profile. Check it is not a sensor "
                                  "spike, then update athlete.md and the plan." % (max_seen["date"], max_seen["bpm"], athlete["max_hr"])})
    judged.sort(key=lambda x: x[0])
    ages = []
    for at in fetched.values():
        try:
            stamp = dt.datetime.fromisoformat(at.replace("Z", "+00:00"))
            ref = now if now.tzinfo else now.replace(tzinfo=dt.timezone.utc)
            stamp = stamp if stamp.tzinfo else stamp.replace(tzinfo=dt.timezone.utc)
            ages.append((ref - stamp).total_seconds() / 3600)
        except ValueError:
            pass
    oldest = max(ages) if ages else None
    return {
        "generated_at": now.isoformat(timespec="seconds"),
        "as_of": today.isoformat(),
        "fetched_at": fetched,
        "stale": bool(oldest is None or oldest > rule(plan, "max_snapshot_age_h")),
        "days": days,
        "extras": extras,
        "notices": notices,
        "weeks": weeks,
        "over_prescription_streak": J.over_prescription_streak([j for _, j in judged]),
        "recovery": rec,
        "vo2": vo2[-90:],
        "vo2_note": vo2_note,
        "easy_efficiency": easy[-8:],
        "max_hr_seen": max_seen,
    }


def apply_to_plan(plan, snapshot):
    """Write statuses and actuals from the snapshot back into the plan. Returns changed dates."""
    changed = []
    for _, day in all_days(plan):
        e = snapshot["days"].get(day["date"])
        if not e or day["status"] == "skipped" or e["status"] == "planned":
            continue
        actual = None
        j = e.get("judgement")
        if j and j.get("type") == "key":
            s = e["summary"]
            actual = {"pace_s_per_km": s["pace_s_per_km"], "hr": s["hr"],
                      "reps_pace_s_per_km": [r["pace_s_per_km"] for r in s["reps"]],
                      "verdict": j["verdict"], "activity_id": e.get("activity_id")}
        elif j:
            w = j["whole"]
            actual = {"distance_m": w["distance_m"], "pace_s_per_km": w["pace_s_per_km"], "hr": w["hr"],
                      "verdict": j["verdict"], "activity_id": e.get("activity_id")}
        before = (day["status"], day.get("ran_on"), day.get("actual"))
        day["status"] = e["status"]
        if e.get("ran_on") and e["ran_on"] != day["date"]:
            day["ran_on"] = e["ran_on"]
        if actual:
            day["actual"] = actual
        if before != (day["status"], day.get("ran_on"), day.get("actual")):
            changed.append(day["date"])
    return changed


def write(plan, snapshot, out_dir, dashboard_src=None):
    """Write snapshot.json and data.js, and copy the dashboard page beside them."""
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "snapshot.json"), "w") as fh:
        json.dump(snapshot, fh, indent=1)
        fh.write("\n")
    with open(os.path.join(out_dir, "data.js"), "w") as fh:
        fh.write("/* Generated by `coach.py sync`. Do not edit: change the plan and sync again. */\n")
        fh.write("window.STRIDER = ")
        json.dump({"plan": plan, "snapshot": snapshot}, fh, separators=(",", ":"))
        fh.write(";\n")
    if dashboard_src and os.path.abspath(os.path.dirname(dashboard_src)) != os.path.abspath(out_dir):
        with open(dashboard_src) as src, open(os.path.join(out_dir, "index.html"), "w") as dst:
            dst.write(src.read())
