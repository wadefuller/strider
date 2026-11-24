"""Pace bands and heart-rate caps, derived from what the runner has actually run.

Garmin's lactate-threshold speed and race predictor are not used as targets.
Threshold pace comes from recent reps run at or just under threshold heart
rate; when there are none, it is estimated from a race and marked as an
estimate to confirm.

The percentages below are coaching heuristics unless a source is named.
See docs/methodology.md.
"""
from __future__ import annotations

from .units import DISTANCES, fmt_clock, riegel

# Friel's running zones are anchored to lactate-threshold heart rate (LTHR):
# Z1 <85%, Z2 85-89%, Z3 90-94%, Z4 95-99%, Z5 100%+ (Friel, The Triathlete's Training Bible).
ZONES = (("Z1", 0.0, 0.85), ("Z2", 0.85, 0.90), ("Z3", 0.90, 0.95), ("Z4", 0.95, 1.00), ("Z5", 1.00, 9.9))

# Goal-pace heart-rate cap as a fraction of LTHR, by race distance (heuristic).
GOAL_HR_FACTOR = {"5k": 1.05, "10k": 1.02, "half": 0.99, "marathon": 0.93}
# Where goal pace normally sits relative to threshold pace (heuristic sanity range).
GOAL_VS_THRESHOLD = {"5k": (0.92, 0.98), "10k": (0.96, 1.01), "half": (1.01, 1.07), "marathon": (1.07, 1.16)}


def zones(lthr):
    out = []
    for name, lo, hi in ZONES:
        out.append({"zone": name, "low": round(lthr * lo) if lo else None,
                    "high": round(lthr * hi) - 1 if hi < 9 else None})
    return out


def derive_threshold(reps, lthr, min_rep_s=300, hr_window=10):
    """Threshold pace from recent reps.

    reps: [{"pace_s_per_km", "hr", "duration_s", "date"}] from lap analysis,
      already corrected for watch distance.
    Uses reps lasting five minutes or more whose heart rate sat within
    `hr_window` beats below LTHR and not above it. Returns None when fewer
    than two reps qualify; the caller then falls back to a race estimate.
    """
    good = [r for r in reps if r.get("hr") and r["duration_s"] >= min_rep_s
            and lthr - hr_window <= r["hr"] <= lthr]
    if len(good) < 2:
        return None
    total = sum(r["duration_s"] for r in good)
    pace = sum(r["pace_s_per_km"] * r["duration_s"] for r in good) / total
    dates = sorted(set(r.get("date", "") for r in good))
    return {"pace_s_per_km": round(pace, 1), "reps_used": len(good),
            "source": "%d reps of 5+ min at %d-%d bpm, %s to %s" % (
                len(good), lthr - hr_window, lthr, dates[0] or "?", dates[-1] or "?")}


def threshold_from_race(time_s, distance_m):
    """Estimate threshold pace as the pace of a one-hour race (Riegel 1981). An estimate to confirm."""
    lo, hi = 3000.0, 30000.0
    for _ in range(60):
        mid = (lo + hi) / 2
        if riegel(time_s, distance_m, mid) > 3600:
            hi = mid
        else:
            lo = mid
    return {"pace_s_per_km": round(3600 / (lo / 1000), 1), "reps_used": 0,
            "source": "estimated from a race result as one-hour race pace; confirm with a threshold session"}


def build_bands(threshold, lthr, max_hr, distance, goal_time_s):
    """All the bands a plan uses. Paces are [fast, slow] s/km of true distance."""
    t = threshold["pace_s_per_km"]
    goal_pace = goal_time_s / (DISTANCES[distance] / 1000)
    ceiling = max_hr - 3

    def band(lo, hi):
        return [round(t * lo, 1), round(t * hi, 1)]

    return {
        "easy": {"pace_s_per_km": band(1.20, 1.38), "hr_cap": round(lthr * 0.89),
                 "source": "threshold pace +20% to +38%; cap is the top of zone 2 (heuristic)"},
        "steady": {"pace_s_per_km": band(1.08, 1.14), "hr_cap": round(lthr * 0.94),
                   "source": "threshold pace +8% to +14%; cap is the top of zone 3 (heuristic)"},
        "threshold": {"pace_s_per_km": band(0.985, 1.015), "hr_cap": lthr, "source": threshold["source"]},
        "vo2": {"pace_s_per_km": band(0.92, 0.95), "hr_cap": min(round(lthr * 1.05), ceiling),
                "source": "threshold pace -5% to -8% (heuristic); heart rate lags in short reps, so read the cap on the last rep"},
        "goal": {"pace_s_per_km": [round(goal_pace * 0.995, 1), round(goal_pace * 1.005, 1)],
                 "hr_cap": min(round(lthr * GOAL_HR_FACTOR[distance]), ceiling),
                 "source": "goal time over the race distance, +/-0.5%"},
    }


def goal_check(threshold_pace, distance, goal_time_s):
    """Is the goal plausible next to current threshold pace? Returns a warning string or None."""
    goal_pace = goal_time_s / (DISTANCES[distance] / 1000)
    lo, hi = GOAL_VS_THRESHOLD[distance]
    ratio = goal_pace / threshold_pace
    if ratio < lo:
        return ("Goal pace is %.0f%% of current threshold pace; for this distance it usually sits at %.0f-%.0f%%. "
                "The goal needs threshold to improve during the block. Keep it provisional until the decision session."
                % (ratio * 100, lo * 100, hi * 100))
    if ratio > hi:
        return ("Goal pace is slower than current fitness suggests (%.0f%% of threshold pace, usual range %.0f-%.0f%%). "
                "Fine for a first race at the distance; otherwise consider a faster goal." % (ratio * 100, lo * 100, hi * 100))
    return None


MARATHON_RIEGEL_GAP_S = 600   # Riegel underestimated marathon time by 10+ minutes for about half of runners


def race_prediction(recent_time_s, recent_distance, target_distance, goal_time_s=None):
    """Predict a target-race time from a recent race with Riegel (1981), and say how far to trust it.

    Riegel is well calibrated up to the half marathon but optimistic for the marathon: in
    Vickers & Vertosick (2016), recreational runners' marathon times were underestimated by
    10 minutes or more for about half of them. For a marathon the prediction is a best case.
    Returns {"riegel_s", "best_case", "note"}; note is None when there is nothing to say.
    """
    pred = riegel(recent_time_s, DISTANCES[recent_distance], DISTANCES[target_distance])
    marathon = target_distance == "marathon" and recent_distance != "marathon"
    note = None
    if goal_time_s is not None and goal_time_s < pred:
        note = ("Goal %s is faster than the Riegel prediction from your recent %s (%s)%s. Keep it provisional "
                "until the decision session." % (fmt_clock(goal_time_s), recent_distance, fmt_clock(pred),
                                                  ", which is already a best case for a marathon" if marathon else ""))
    elif marathon and goal_time_s is not None and goal_time_s < pred + MARATHON_RIEGEL_GAP_S:
        note = ("Goal %s is within 10 minutes of the Riegel prediction from your %s (%s). Riegel runs optimistic "
                "for the marathon: for about half of recreational runners the real time was 10 or more minutes "
                "slower (Vickers & Vertosick 2016). Keep the goal provisional until the decision session."
                % (fmt_clock(goal_time_s), recent_distance, fmt_clock(pred)))
    return {"riegel_s": round(pred), "best_case": marathon, "note": note}
