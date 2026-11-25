"""Today's call: what the plan says, what recovery says, and what to do. Pure code, no judgement.

The verdict itself comes from snapshot.recovery_verdict (the standing go/no-go rule). This module adds
three things around it:

- Stale data is never today's verdict. If the newest Garmin data is older than `max_snapshot_age_h`,
  the call is `unknown`, not yesterday's answer in today's clothes.
- Thin data is not a green light. A `go` that rests on fewer than two of the four recovery signals
  (overnight HRV, sleep score, resting heart rate, Garmin's training readiness) becomes `cap_firm`.
- The verdict is applied to today's session by its kind: it governs key sessions, tests and long runs,
  only trims easy runs, and never moves a race.
"""
from __future__ import annotations

import datetime as dt

from . import snapshot as S
from .plan import find_day, flat_steps, rule
from .units import fmt_band, unit_m

SIGNALS = ("hrv", "sleep", "rhr", "readiness")
MIN_SIGNALS_FOR_GO = 2

ACTIONS = {
    "go": "Run it as written.",
    "cap_firm": "Run it, but the heart-rate cap is absolute: let pace give way to stay under it.",
    "by_heart_rate": "Keep the session, drop the pace target, and hold the heart-rate cap.",
    "move": "Move it one day (never onto a blocked weekday). Today is rest or an easy jog.",
    "easy_instead": "Today becomes an easy run. The session is not made up later this week.",
    "unknown": "Recovery could not be checked. Run by heart rate: the cap is absolute.",
}
DEMANDING = ("key", "test", "long")


def _age_hours(fetched, now):
    ages = []
    ref = now if now.tzinfo else now.replace(tzinfo=dt.timezone.utc)
    for at in fetched.values():
        try:
            stamp = dt.datetime.fromisoformat(str(at).replace("Z", "+00:00"))
        except ValueError:
            continue
        stamp = stamp if stamp.tzinfo else stamp.replace(tzinfo=dt.timezone.utc)
        ages.append((ref - stamp).total_seconds() / 3600)
    return max(ages) if ages else None


def _signals(rec, plan):
    """The recovery signals present today, each with the sentence that explains it."""
    out = {}
    base = rec.get("hrv_baseline_ms")
    if rec.get("hrv_last") is not None:
        txt = "HRV last night %d ms" % rec["hrv_last"]
        if base:
            txt += " (baseline %d to %d; 7-day %s ms)" % (base[0], base[1], rec.get("hrv_7d", "?"))
        out["hrv"] = {"value": rec["hrv_last"], "low": bool(base and rec["hrv_last"] < base[0]), "text": txt}
    if rec.get("sleep_nights"):
        floor = rule(plan, "sleep_floor")
        out["sleep"] = {"value": rec["sleep_avg"], "low": rec.get("sleep_low_run", 0) >= 3,
                        "text": "sleep score averaging %d over %d nights (floor %d; %d low in a row)"
                                % (rec["sleep_avg"], rec["sleep_nights"], floor, rec.get("sleep_low_run", 0))}
    if rec.get("rhr_last") is not None:
        resting = plan["athlete"].get("resting_hr")
        out["rhr"] = {"value": rec["rhr_last"], "low": rec.get("rhr_up_days", 0) >= 2,
                      "text": "resting HR %d bpm (normal %s; %d days up %d+ bpm)"
                              % (rec["rhr_last"], resting, rec.get("rhr_up_days", 0), rule(plan, "rhr_rise_bpm"))}
    if rec.get("readiness") is not None:
        out["readiness"] = {"value": rec["readiness"], "low": rec["readiness"] < rule(plan, "readiness_floor"),
                            "text": "Garmin training readiness %d (%s)" % (rec["readiness"], rec.get("readiness_kind"))}
    return out


def _session(day, plan):
    if not day:
        return None
    out = {"date": day["date"], "kind": day["kind"], "title": day["title"], "status": day.get("status")}
    if day.get("distance_m") and plan["units"] not in day["title"]:
        out["distance"] = "%.1f %s" % (day["distance_m"] / unit_m(plan["units"]), plan["units"])
    steps = flat_steps(day.get("steps"))
    main = [s for s in steps if s.get("pace_s_per_km") and s["type"] not in ("warmup", "cooldown")]
    capped = [s for s in steps if s.get("hr_cap")]
    if main:
        out["target"] = fmt_band(main[0]["pace_s_per_km"], plan["units"])
        if main[0].get("hr_cap"):
            out["target"] += ", HR under %d" % main[0]["hr_cap"]
    elif capped:
        out["target"] = "HR under %d" % capped[0]["hr_cap"]
    return out


def call(plan, raw, fetched, now):
    """Today's call as a dict. `now` is a datetime; its date is today."""
    today = now.date().isoformat()
    rec = S.recovery_block(plan, raw, now.date())
    rec.update(S.recovery_verdict(rec, plan, now))
    sig = _signals(rec, plan)
    age = _age_hours(fetched, now)
    stale = age is None or age > rule(plan, "max_snapshot_age_h")
    verdict, reasons = rec["verdict"], list(rec.get("flags", []))
    stale_now = stale
    if rec.get("swap_key_for_easy"):
        reasons.insert(0, "7-day HRV under baseline and resting HR up two days running")
    if rec.get("recovery_hours_now") is not None and not stale_now:
        reasons.append("Garmin recovery time left: %.0f h (go under %d, move over %d)" % (
            rec["recovery_hours_now"], rule(plan, "recovery_go_h"), rule(plan, "recovery_move_h")))
    if stale:
        verdict = "unknown"
        reasons.insert(0, "the newest Garmin data is %s old; refresh before trusting a verdict" % (
            "of unknown age" if age is None else "%.0f hours" % age))
    elif verdict == "go" and len(sig) < MIN_SIGNALS_FOR_GO:
        verdict = "cap_firm"
        reasons.append("only %d of 4 recovery signals today; thin data is not a green light" % len(sig))

    day = find_day(plan, today)
    kind = day["kind"] if day else None
    if not day:
        action, applies = "No run planned today.", False
    elif day.get("status") not in (None, "planned"):
        action = "Today's session is already logged as %s." % day["status"]
        applies = False
    elif kind == "race":
        action = ("Race day. The verdict is information, not a reason to move it: start at the slow end of the "
                  "goal band and hold the heart-rate cap for the first third." if verdict != "go" else
                  "Race day. Run the plan.")
        applies = False
    elif kind in DEMANDING:
        action, applies = ACTIONS[verdict], True
    else:   # easy
        applies = verdict in ("move", "easy_instead", "unknown")
        action = ("Keep it easy and on the short side; stop early if it feels heavy." if applies else
                  "Easy as written. The cap is the limit, not the target.")
    return {
        "date": today,
        "verdict": verdict,
        "verdict_applies": applies,
        "action": action,
        "session": _session(day, plan),
        "reasons": reasons,
        "signals": dict((k, sig[k]["text"]) for k in SIGNALS if k in sig),
        "missing_signals": [k for k in SIGNALS if k not in sig],
        "stale": stale,
        "data_age_h": None if age is None else round(age, 1),
    }


def text(c):
    """Phone-readable lines."""
    lines = ["%s  %s" % (c["date"], c["verdict"].upper().replace("_", " "))]
    s = c["session"]
    if s:
        lines.append("Today: %s%s" % (s["title"], " (%s)" % s["distance"] if s.get("distance") else ""))
        if s.get("target"):
            lines.append("Target: " + s["target"])
    lines.append("Do: " + c["action"])
    for r in c["reasons"]:
        lines.append("  because " + r)
    for k, v in c["signals"].items():
        lines.append("  - " + v)
    if c["missing_signals"]:
        lines.append("  - missing: " + ", ".join(c["missing_signals"]))
    if c.get("decisions"):
        lines.append("Standing decisions:")
        for e in c["decisions"]:
            lines.append("  - %s (%s, %s)" % (e["what"], e["kind"], e["applies"]))
    return "\n".join(lines)
