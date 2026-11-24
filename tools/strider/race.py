"""Race week, race review and the post-race recovery check."""
from __future__ import annotations

import datetime as dt

from .plan import d, rule
from .units import KM, MI, fmt_clock, fmt_pace


def pace_chart(plan, goal_time_s=None):
    """Elapsed time at each course marker for an even-paced race.

    The watch measures its own distance, which drifts from the certified course (long on open
    roads and tracks, short among tall buildings and trees), so its average
    pace flatters you. The chart is checked against the course markers instead.
    `watch_reads` is roughly what the watch will show when you pass each marker.
    """
    goal = goal_time_s or plan["goal"]["time_s"]
    dist = plan["race"]["distance_m"]
    unit = MI if plan["units"] == "mi" else KM
    factor = plan["athlete"]["watch_distance_factor"]
    pace = goal / dist  # s per meter of course
    marks, m = [], unit
    while m < dist - 1:
        marks.append(m)
        m += unit
    half = dist / 2
    rows = []
    for m in sorted(set(marks + [half, dist])):
        label = "finish" if m == dist else ("halfway" if m == half else "%d %s" % (round(m / unit), plan["units"]))
        rows.append({"marker": label, "course_m": round(m, 1), "elapsed_s": round(m * pace),
                     "elapsed": fmt_clock(m * pace, goal >= 3600), "watch_reads_m": round(m * factor)})
    return {"goal_time_s": goal, "pace_s_per_km": round(pace * KM, 1),
            "pace": fmt_pace(pace * KM, plan["units"]),
            "watch_pace": fmt_pace(pace * KM / factor, plan["units"]),
            "watch_distance_factor": factor, "rows": rows}


def review(plan, lap_list, chip_time_s=None, gps_distance_m=None):
    """Read a race from its laps: pacing shape, heart-rate drift, result against the goal.

    chip_time_s is the official time. Until the runner supplies it the result is
    marked as watch time, and no PR or watch correction is recorded.
    """
    units = plan["units"]
    race_m = plan["race"]["distance_m"]
    lap_list = [l for l in lap_list if (l.get("distance_meters") or 0) > 0 and (l.get("duration_seconds") or 0) > 0]
    gps_m = gps_distance_m or sum(l["distance_meters"] for l in lap_list)
    watch_s = sum(l["duration_seconds"] for l in lap_list)
    factor = gps_m / race_m if 0.97 < gps_m / race_m < 1.04 else None
    result_s = chip_time_s or watch_s
    true_pace = result_s / (race_m / KM)

    # halves by distance, interpolating inside the lap that crosses halfway
    half_m, run_m, first_s = gps_m / 2, 0.0, 0.0
    hr1 = hr2 = d1 = d2 = 0.0
    for l in lap_list:
        m, s, hr = l["distance_meters"], l["duration_seconds"], l.get("avg_hr_bpm") or 0
        before = max(0.0, min(m, half_m - run_m))
        share = before / m
        first_s += s * share
        if hr:
            hr1 += hr * s * share
            d1 += s * share
            hr2 += hr * s * (1 - share)
            d2 += s * (1 - share)
        run_m += m
    second_s = watch_s - first_s
    out = {
        "official": bool(chip_time_s), "result_s": round(result_s), "result": fmt_clock(result_s, True),
        "pace": fmt_pace(true_pace, units), "watch_time_s": round(watch_s), "watch_distance_m": round(gps_m),
        "watch_distance_factor": round(factor, 4) if factor and chip_time_s else None,
        "first_half_s": round(first_s), "second_half_s": round(second_s), "split_delta_s": round(second_s - first_s),
        "lines": [],
    }
    goal = plan["goal"]["time_s"]
    out["vs_goal_s"] = round(result_s - goal)

    full = [l for l in lap_list if l["distance_meters"] > 0.8 * (MI if units == "mi" else KM)]
    if len(full) >= 4:
        paces = [l["duration_seconds"] / (l["distance_meters"] / KM) for l in full]
        even = sum(paces) / len(paces)
        k = max(1, len(paces) // 5)
        opener = sum(paces[:k]) / k
        closer = sum(paces[-k:]) / k
        middle = paces[k:-k] or paces
        mid = sum(middle) / len(middle)
        tol = rule(plan, "pace_tolerance_s_per_km")
        out.update({"opener_vs_even_s_per_km": round(opener - even, 1), "closer_vs_middle_s_per_km": round(closer - mid, 1),
                    "middle_spread_s_per_km": round(max(middle) - min(middle), 1)})
        if opener < even - 2 * tol:
            out["lines"].append("Went out %d s per km faster than the average pace over the first fifth." % round(even - opener))
        elif opener > even + 2 * tol:
            out["lines"].append("Opened conservatively, %d s per km slower than the average pace." % round(opener - even))
        else:
            out["lines"].append("Opened at race pace.")
        if closer > mid + 2 * tol:
            out["lines"].append("Faded %d s per km over the last fifth." % round(closer - mid))
        elif closer < mid - tol:
            out["lines"].append("Closed %d s per km faster than the middle of the race." % round(mid - closer))
        else:
            out["lines"].append("Held pace to the finish.")
    if d1 and d2:
        s1, s2 = (half_m / first_s), (half_m / second_s)
        drift = ((hr2 / d2) / s2) / ((hr1 / d1) / s1) - 1
        out["hr_first_half"] = round(hr1 / d1)
        out["hr_second_half"] = round(hr2 / d2)
        out["decoupling_pct"] = round(drift * 100, 1)
        out["lines"].append("Heart rate per unit of speed %s %.1f%% from the first half to the second (%s)." % (
            "rose" if drift >= 0 else "fell", abs(drift) * 100, "well coupled" if drift < 0.05 else "moderate drift" if drift < 0.10 else "large drift"))
    out["lines"].append("%s %s, %s the %s goal by %s." % (
        "Official time" if chip_time_s else "Watch time (official time not entered yet)",
        fmt_clock(result_s, True), "inside" if result_s <= goal else "outside", fmt_clock(goal, True),
        fmt_clock(abs(result_s - goal))))
    if not chip_time_s:
        out["lines"].append("Ask for the official chip time before recording a PR or a watch-distance correction.")
    elif factor:
        out["lines"].append("Watch measured %.2f%% %s than the certified distance; store watch_distance_factor %.4f." % (
            abs(factor - 1) * 100, "longer" if factor > 1 else "shorter", factor))
    return out


# Coaching heuristic: about one easy day per mile raced before the next hard session.
def earliest_quality_date(race_date, distance_m):
    return d(race_date) + dt.timedelta(days=int(round(distance_m / MI)))


def recovery_check(plan, recovery, today):
    """Post-race check: have the recovery signals come back to normal?

    `recovery` is the block from snapshot.recovery_block(). Returns the signals,
    which are back, and what kind of running that clears.
    """
    race = plan["race"]
    base = plan["athlete"].get("hrv_baseline_ms")
    checks = []
    if base and recovery.get("hrv_7d") is not None:
        checks.append({"signal": "HRV 7-day", "value": recovery["hrv_7d"], "ok": recovery["hrv_7d"] >= base[0],
                       "want": "at or above %d ms" % base[0]})
    if recovery.get("rhr_last") is not None and plan["athlete"].get("resting_hr"):
        limit = plan["athlete"]["resting_hr"] + 3
        checks.append({"signal": "Resting HR", "value": recovery["rhr_last"], "ok": recovery["rhr_last"] <= limit,
                       "want": "%d bpm or lower" % limit})
    if recovery.get("recovery_hours_now") is not None:
        checks.append({"signal": "Recovery time left", "value": recovery["recovery_hours_now"],
                       "ok": recovery["recovery_hours_now"] <= rule(plan, "recovery_go_h"),
                       "want": "under %d h" % rule(plan, "recovery_go_h")})
    if recovery.get("sleep_avg") is not None:
        checks.append({"signal": "Sleep, 7-day", "value": recovery["sleep_avg"],
                       "ok": recovery["sleep_avg"] >= rule(plan, "sleep_floor"), "want": "%d or higher" % rule(plan, "sleep_floor")})
    quality_from = earliest_quality_date(race["date"], race["distance_m"])
    days_since = (today - d(race["date"])).days
    signals_ok = bool(checks) and all(c["ok"] for c in checks)
    if not checks:
        verdict = "unknown"
    elif not signals_ok:
        verdict = "easy_only"
    elif today >= quality_from:
        verdict = "quality_ok"
    else:
        verdict = "easy_running_ok"
    return {"days_since_race": days_since, "checks": checks, "signals_normal": signals_ok,
            "earliest_quality_date": quality_from.isoformat(), "verdict": verdict,
            "ask": ["Any pain that changes how you run?", "Soreness on stairs, 0 to 10?", "Do you want to run yet?"]}

