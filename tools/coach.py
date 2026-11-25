#!/usr/bin/env python3
"""Strider command line. Python 3.9+, standard library only.

  coach.py validate PLAN
  coach.py block INPUT.json -o plan.json
  coach.py threshold --raw DIR --lthr N [--factor F]
  coach.py workouts PLAN -o DIR [--from DATE] [--to DATE]
  coach.py calendar PLAN -o plan.ics | --json
  coach.py analyze PLAN --date DATE --splits FILE [--typed FILE]
  coach.py sync PLAN --raw DIR --out DIR [--now ISO] [--write-plan]
  coach.py form --records FILE [--splits FILE]
  coach.py chart PLAN [--goal H:MM:SS]
  coach.py review PLAN --splits FILE [--chip H:MM:SS]
  coach.py recovery-check PLAN --raw DIR [--now ISO]
  coach.py today PLAN --raw DIR [--now ISO] [--json] [--decisions FILE]       exit 3 when there is no fresh data
  coach.py goal --distance D --goal H:MM:SS --weeks N [--recent D:H:MM:SS] [--threshold M:SS] [--units km|mi]
  coach.py decisions FILE [--on DATE] [--json]
  coach.py decide FILE --kind K --what TEXT --why TEXT [--applies standing|once|until:DATE] [--source runner|data|coach] [--date DATE] [--replaces DATE]
  coach.py sweep --old VALUE ... | --before OLD.json --after NEW.json  PATH ...
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from strider import blockgen, calendar, decisions, fitform, judge, laps, paces, race, snapshot, sweep, today, workout  # noqa: E402
from strider import plan as P  # noqa: E402
from strider.units import fmt_clock, fmt_pace, parse_clock  # noqa: E402

DASHBOARD = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "dashboard", "index.html")


def _json(obj):
    print(json.dumps(obj, indent=2))


def _laps(path):
    body = P.load(path)
    if isinstance(body, dict) and "result" in body:
        body = body["result"]
    return body["laps"] if isinstance(body, dict) else body


def _now(text):
    return dt.datetime.fromisoformat(text) if text else dt.datetime.now()


def cmd_validate(a):
    errors, warnings = P.validate(P.load(a.plan))
    for w in warnings:
        print("warning: " + w)
    for e in errors:
        print("ERROR: " + e)
    print("%s: %d errors, %d warnings" % (a.plan, len(errors), len(warnings)))
    return 1 if errors else 0


def cmd_block(a):
    plan, notes = blockgen.build_block(P.load(a.input))
    errors, warnings = P.validate(plan)
    P.save(plan, a.out)
    for n in notes:
        print("note: " + n)
    for w in warnings:
        print("warning: " + w)
    for e in errors:
        print("ERROR: " + e)
    print("wrote %s: %d weeks, goal %s (provisional)" % (a.out, len(plan["weeks"]), fmt_clock(plan["goal"]["time_s"], True)))
    return 1 if errors else 0


def cmd_threshold(a):
    reps = []
    data, _ = snapshot.load_raw(a.raw)
    dates = dict((str(x["id"]), str(x.get("start_time", ""))[:10]) for x in data["activities"])
    for aid, lap_list in data["splits"].items():
        s = laps.summarize(lap_list, a.factor)
        for r in (s or {}).get("reps", []):
            if r["hr_reliable"]:
                reps.append({"pace_s_per_km": r["pace_s_per_km"], "hr": r["hr"], "duration_s": r["duration_s"],
                             "date": dates.get(aid, "")})
    found = paces.derive_threshold(reps, a.lthr)
    if not found:
        print("Fewer than two reps of 5+ minutes at %d-%d bpm. Estimate from a race instead, and say it is an estimate."
              % (a.lthr - 10, a.lthr))
        return 1
    found["pace_km"] = fmt_pace(found["pace_s_per_km"], "km")
    found["pace_mi"] = fmt_pace(found["pace_s_per_km"], "mi")
    _json(found)
    return 0


def cmd_workouts(a):
    plan = P.load(a.plan)
    os.makedirs(a.out, exist_ok=True)
    n = 0
    for week, day in P.all_days(plan):
        if not day.get("steps") or day["kind"] not in P.RUN_KINDS or day["status"] != "planned":
            continue
        if (a.start and day["date"] < a.start) or (a.end and day["date"] > a.end):
            continue
        with open(os.path.join(a.out, day["date"] + ".json"), "w") as fh:
            json.dump(workout.to_garmin(day, plan, week["n"]), fh, indent=2)
        n += 1
    print("wrote %d workouts to %s (one file per date; pass each to upload_workout, then schedule_workout)" % (n, a.out))
    return 0


def cmd_calendar(a):
    plan = P.load(a.plan)
    if a.json:
        _json(calendar.events(plan))
    else:
        with open(a.out, "w", newline="") as fh:
            fh.write(calendar.to_ics(plan))
        print("wrote %s" % a.out)
    return 0


def cmd_analyze(a):
    plan = P.load(a.plan)
    day = P.find_day(plan, a.date)
    if not day:
        print("no planned day on %s" % a.date)
        return 1
    lap_list = _laps(a.splits)
    typed = P.load(a.typed) if a.typed else None
    terrain = day.get("terrain") or "rolling"
    factor = 1.0 if terrain == "track" else plan["athlete"]["watch_distance_factor"]
    out = {"date": a.date, "title": day["title"]}
    if day["kind"] in ("key", "test"):
        s = laps.summarize(lap_list, factor, terrain)
        if not s:
            print("no usable work laps")
            return 1
        out.update({"summary": s, "judgement": judge.judge_key(s, day, plan)})
        form = laps.form_by_rep(typed, s)
        if form:
            out["form"] = {"reps": form, "drift": laps.form_drift(form)}
        if day.get("decision") and plan["goal"].get("decision"):
            out["decision"] = judge.evaluate_decision(plan["goal"]["decision"], s)
    else:
        out["judgement"] = judge.judge_long(lap_list, day, plan, factor, typed)
    _json(out)
    return 0


def cmd_sync(a):
    plan = P.load(a.plan)
    errors, _ = P.validate(plan)
    if errors:
        print("plan does not validate; run `coach.py validate` first")
        return 1
    raw, fetched = snapshot.load_raw(a.raw)
    snap = snapshot.build(plan, raw, fetched, _now(a.now))
    if a.write_plan:
        changed = snapshot.apply_to_plan(plan, snap)
        if changed:
            P.save(plan, a.plan)
        print("plan days updated: %s" % (", ".join(changed) or "none"))
    snapshot.write(plan, snap, a.out, DASHBOARD)
    print("wrote %s/snapshot.json, data.js and index.html" % a.out)
    if snap["stale"]:
        print("STALE: the newest Garmin data is more than %d hours old. Refresh before drawing conclusions."
              % P.rule(plan, "max_snapshot_age_h"))
    if snap["over_prescription_streak"]:
        print("sessions in a row run faster than prescribed: %d" % snap["over_prescription_streak"])
    return 0


def cmd_form(a):
    records = fitform.load_records(a.records)
    windows = None
    if a.splits:
        lap_list = _laps(a.splits)
        s = laps.summarize(lap_list)
        windows = fitform.windows_from_laps(lap_list, s, records) if s else None
    _json(fitform.analyze(records, windows))
    return 0


def cmd_chart(a):
    plan = P.load(a.plan)
    chart = race.pace_chart(plan, parse_clock(a.goal) if a.goal else None)
    print("Goal %s: %s by the course markers (watch will show about %s)" % (
        fmt_clock(chart["goal_time_s"], True), chart["pace"], chart["watch_pace"]))
    for r in chart["rows"]:
        print("  %-9s %s" % (r["marker"], r["elapsed"]))
    return 0


def cmd_review(a):
    plan = P.load(a.plan)
    _json(race.review(plan, _laps(a.splits), parse_clock(a.chip) if a.chip else None))
    return 0


def cmd_recovery(a):
    plan = P.load(a.plan)
    raw, _ = snapshot.load_raw(a.raw)
    now = _now(a.now)
    rec = snapshot.recovery_block(plan, raw, now.date())
    rec.update(snapshot.recovery_verdict(rec, plan, now))
    _json(race.recovery_check(plan, rec, now.date()))
    return 0


def cmd_today(a):
    plan = P.load(a.plan)
    raw, fetched = snapshot.load_raw(a.raw)
    c = today.call(plan, raw, fetched, _now(a.now))
    path = a.decisions or os.path.join(os.path.dirname(os.path.abspath(a.plan)), "decisions.md")
    if os.path.exists(path):
        with open(path) as fh:
            c["decisions"] = [dict((k, e[k]) for k in ("date", "kind", "what", "applies"))
                              for e in decisions.active(decisions.parse(fh.read()), c["date"])]
    if a.json:
        _json(c)
    else:
        print(today.text(c))
    return 3 if c["stale"] else 0


def cmd_goal(a):
    recent = None
    if a.recent:
        dist, _, clock = a.recent.partition(":")
        recent = {"distance": dist, "time_s": parse_clock(clock)}
    thr = None
    if a.threshold:
        thr = parse_clock(a.threshold) * (1000 / 1609.344 if a.units == "mi" else 1)
    r = paces.goal_realism(a.distance, parse_clock(a.goal), a.weeks, recent, thr)
    if a.json:
        _json(r)
        return 0
    print("%s: %s" % (r["verdict"].upper().replace("_", " "), r["summary"]))
    for i, opt in enumerate(r["options"], 1):
        print("  %d. %s" % (i, opt["text"]))
    return 0


def cmd_decisions(a):
    if not os.path.exists(a.file):
        print("no decisions file at %s yet" % a.file)
        return 0
    with open(a.file) as fh:
        entries = decisions.parse(fh.read())
    on = a.on or dt.date.today().isoformat()
    live = decisions.active(entries, on)
    bad = decisions.problems(entries)
    if a.json:
        _json({"on": on, "active": live, "problems": bad})
    else:
        for e in live:
            print("%s  %-10s %s  [%s; %s]" % (e["date"], e["kind"], e["what"], e["applies"], e["source"]))
        for b in bad:
            print("PROBLEM: " + b)
        print("%d active of %d entries on %s" % (len(live), len(entries), on))
    return 1 if bad else 0


def cmd_decide(a):
    applies = a.applies.replace("until:", "until ")
    text = decisions.add(a.file, date=a.date or dt.date.today().isoformat(), kind=a.kind, what=a.what,
                         why=a.why, applies=applies, source=a.source, replaces=a.replaces)
    print(text.strip())
    return 0


def cmd_sweep(a):
    old = list(a.old or [])
    if a.before and a.after:
        old += sweep.stale_values(P.load(a.before), P.load(a.after))
    if not old:
        print("nothing to look for: pass --old or --before/--after")
        return 1
    hits = sweep.sweep(a.paths, old)
    for path, line, value, text in hits:
        print("%s:%d: [%s] %s" % (path, line, value, text))
    print("looked for %s: %d stale hits" % (", ".join(old), len(hits)))
    return 1 if hits else 0


def main(argv=None):
    ap = argparse.ArgumentParser(prog="coach.py", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    def add(name, fn, plan=True):
        p = sub.add_parser(name)
        p.set_defaults(fn=fn)
        if plan:
            p.add_argument("plan")
        return p

    add("validate", cmd_validate)
    p = add("block", cmd_block, plan=False); p.add_argument("input"); p.add_argument("-o", "--out", required=True)
    p = add("threshold", cmd_threshold, plan=False)
    p.add_argument("--raw", required=True); p.add_argument("--lthr", type=int, required=True); p.add_argument("--factor", type=float, default=1.0)
    p = add("workouts", cmd_workouts); p.add_argument("-o", "--out", required=True)
    p.add_argument("--from", dest="start"); p.add_argument("--to", dest="end")
    p = add("calendar", cmd_calendar); p.add_argument("-o", "--out", default="plan.ics"); p.add_argument("--json", action="store_true")
    p = add("analyze", cmd_analyze); p.add_argument("--date", required=True); p.add_argument("--splits", required=True); p.add_argument("--typed")
    p = add("sync", cmd_sync); p.add_argument("--raw", required=True); p.add_argument("--out", required=True)
    p.add_argument("--now"); p.add_argument("--write-plan", action="store_true")
    p = add("form", cmd_form, plan=False); p.add_argument("--records", required=True); p.add_argument("--splits")
    p = add("chart", cmd_chart); p.add_argument("--goal")
    p = add("review", cmd_review); p.add_argument("--splits", required=True); p.add_argument("--chip")
    p = add("recovery-check", cmd_recovery); p.add_argument("--raw", required=True); p.add_argument("--now")
    p = add("today", cmd_today); p.add_argument("--raw", required=True); p.add_argument("--now"); p.add_argument("--json", action="store_true")
    p.add_argument("--decisions", help="decisions.md (default: next to the plan)")
    p = add("goal", cmd_goal, plan=False)
    p.add_argument("--distance", required=True, choices=sorted(paces.DISTANCES)); p.add_argument("--goal", required=True)
    p.add_argument("--weeks", type=int, required=True); p.add_argument("--recent", help="distance:time, e.g. 10k:45:00")
    p.add_argument("--threshold", help="threshold pace per --units, e.g. 4:30"); p.add_argument("--units", default="km", choices=("km", "mi"))
    p.add_argument("--json", action="store_true")
    p = add("decisions", cmd_decisions, plan=False); p.add_argument("file"); p.add_argument("--on"); p.add_argument("--json", action="store_true")
    p = add("decide", cmd_decide, plan=False); p.add_argument("file")
    p.add_argument("--kind", required=True, choices=decisions.KINDS); p.add_argument("--what", required=True); p.add_argument("--why", required=True)
    p.add_argument("--applies", default="standing"); p.add_argument("--source", default="runner", choices=decisions.SOURCES); p.add_argument("--date"); p.add_argument("--replaces")
    p = add("sweep", cmd_sweep, plan=False)
    p.add_argument("--old", action="append"); p.add_argument("--before"); p.add_argument("--after"); p.add_argument("paths", nargs="+")
    a = ap.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
