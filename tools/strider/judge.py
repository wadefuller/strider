"""Judge a run against what the plan prescribed, and apply the decision rule.

The output is facts and a verdict, never a plan change. Changing the goal is the
runner's call; see reference/decision-rules.md.
"""
from __future__ import annotations

from . import laps as L
from .plan import flat_steps, rule
from .units import fmt_band, fmt_dist, fmt_pace


def _work_targets(day):
    return [s for s in flat_steps(day.get("steps")) if s["type"] == "work"]


def judge_key(summary, day, plan):
    """Compare each rep with its pace band and heart-rate cap."""
    units = plan["units"]
    tol = rule(plan, "pace_tolerance_s_per_km")
    targets = _work_targets(day)
    rows, lines = [], []
    for i, rep in enumerate(summary["reps"]):
        t = targets[min(i, len(targets) - 1)] if targets else None
        band = t.get("pace_s_per_km") if t else None
        cap = t.get("hr_cap") if t else None
        if band is None:
            pace_status = "no_target"
        elif rep["pace_s_per_km"] < band[0] - tol:
            pace_status = "fast"
        elif rep["pace_s_per_km"] > band[1] + tol:
            pace_status = "slow"
        else:
            pace_status = "in"
        if not rep["hr_reliable"] or rep["hr"] is None or cap is None:
            hr_status = "excluded"
        else:
            hr_status = "over" if rep["hr"] > cap else "ok"
        fade_flag = bool(rep["fade_pct"] is not None and rep["power_reliable"]
                         and rep["fade_pct"] > rule(plan, "fade_pct"))
        rows.append({"n": rep["n"], "pace_s_per_km": rep["pace_s_per_km"], "band": band,
                     "pace_status": pace_status, "hr": rep["hr"], "hr_cap": cap, "hr_status": hr_status,
                     "fade_pct": rep["fade_pct"], "fade_flag": fade_flag})

    banded = [r for r in rows if r["band"]]
    fast = sum(1 for r in banded if r["pace_status"] == "fast")
    slow = sum(1 for r in banded if r["pace_status"] == "slow")
    if banded and fast * 2 > len(banded):
        pace_status = "fast"
    elif banded and slow * 2 > len(banded):
        pace_status = "slow"
    else:
        pace_status = "in"
    hr_over = [r["n"] for r in rows if r["hr_status"] == "over"]

    paces = [r["pace_s_per_km"] for r in rows]
    spread = max(paces) - min(paces) if len(paces) > 1 else 0
    shape = []
    if len(paces) > 1 and rows[0]["pace_status"] == "fast" and paces[0] < min(paces[1:]) - tol:
        shape.append("fast_opener")
    same_target = len(set(tuple(r["band"] or ()) for r in rows)) == 1
    if same_target and spread > rule(plan, "rep_spread_s_per_km"):
        shape.append("uneven")
    if any(r["fade_flag"] for r in rows):
        shape.append("fade")
    jog = summary["jog_hr"]
    if len(jog) > 1 and all(b >= a for a, b in zip(jog, jog[1:])) and jog[-1] - jog[0] >= 5:
        shape.append("jog_hr_climbing")

    if hr_over:
        verdict = "over_hr_cap"
    elif "uneven" in shape:
        verdict = "uneven"
    elif pace_status == "fast":
        verdict = "faster_than_prescribed"
    elif pace_status == "slow":
        verdict = "slower_than_prescribed"
    else:
        verdict = "on_target"

    if targets and len(summary["reps"]) != len(targets):
        lines.append("Ran %d reps; the plan had %d." % (len(summary["reps"]), len(targets)))
    if banded:
        lines.append("Reps at %s against %s: %s." % (
            ", ".join(fmt_pace(p, units, False) for p in paces), fmt_band(banded[0]["band"], units),
            {"fast": "faster than prescribed", "slow": "slower than prescribed", "in": "inside the band"}[pace_status]))
    if hr_over:
        lines.append("Heart rate over the cap on rep %s." % ", ".join(str(n) for n in hr_over))
    if "fast_opener" in shape:
        lines.append("Opened faster than the band on rep 1, then settled.")
    if "uneven" in shape:
        lines.append("Uneven: %d s per km between fastest and slowest rep." % round(spread))
    if "fade" in shape:
        lines.append("Power faded more than %s%% inside a rep: that rep was too hard to hold."
                     % rule(plan, "fade_pct"))
    if "jog_hr_climbing" in shape:
        lines.append("Jog heart rate climbed from %d to %d across recoveries." % (jog[0], jog[-1]))

    return {"type": "key", "reps": rows, "pace_status": pace_status, "hr_over_reps": hr_over,
            "shape": shape, "spread_s_per_km": round(spread, 1), "verdict": verdict,
            "over_prescribed": pace_status == "fast", "lines": lines}


def judge_long(lap_list, day, plan, factor, typed=None):
    """Whole-run heart rate against the cap, plus any prescribed finish segment."""
    units = plan["units"]
    tol = rule(plan, "pace_tolerance_s_per_km")
    whole = L.whole_run(lap_list, factor)
    if not whole:
        return None
    cap = day.get("hr_cap")
    out = {"type": day["kind"], "whole": whole, "hr_cap": cap, "lines": [], "flags": [],
           "over_prescribed": False, "verdict": "on_target"}
    steady = [s for s in flat_steps(day.get("steps")) if s["type"] == "steady"]
    if steady:
        s = steady[-1]
        want_m = s.get("distance_m") or 0
        seg = L.tail_segment(lap_list, want_m, factor) if want_m else None
        if seg is None and typed:
            seg = L.tail_segment(L.typed_run_segments(typed), want_m, factor)
        if seg is None:
            out["flags"].append({"code": "structure_unknown", "rep": None,
                                 "detail": "The run is one lap, so the laps cannot show whether the prescribed "
                                           "finish was run. Check typed splits or the per-second file before saying it was."})
            out["verdict"] = "unknown"
        else:
            band = s.get("pace_s_per_km")
            status = "in"
            if band and seg["pace_s_per_km"] < band[0] - tol:
                status = "fast"
            elif band and seg["pace_s_per_km"] > band[1] + tol:
                status = "slow"
            over = bool(s.get("hr_cap") and seg["hr"] and seg["hr"] > s["hr_cap"])
            out["finish"] = {"pace_s_per_km": seg["pace_s_per_km"], "hr": seg["hr"], "band": band,
                             "hr_cap": s.get("hr_cap"), "pace_status": status, "hr_over": over,
                             "distance_m": seg["distance_m"]}
            out["lines"].append("Finish segment %s at %s bpm%s." % (
                fmt_pace(seg["pace_s_per_km"], units), seg["hr"],
                (", against %s and a cap of %s" % (fmt_band(band, units), s.get("hr_cap"))) if band else ""))
            if over:
                out["verdict"] = "over_hr_cap"
            elif status == "fast":
                out["verdict"] = "faster_than_prescribed"
            elif status == "slow":
                out["verdict"] = "slower_than_prescribed"
            out["over_prescribed"] = status == "fast"
    elif cap and whole["hr"] and whole["hr"] > cap:
        out["verdict"] = "over_hr_cap"
        out["over_prescribed"] = True
        out["lines"].append("Average heart rate %d is over the %d cap for this run." % (whole["hr"], cap))
    if not out["lines"]:
        out["lines"].append("%s at %s, heart rate %s%s." % (
            fmt_dist(whole["distance_m"], units), fmt_pace(whole["pace_s_per_km"], units), whole["hr"],
            (" under the %d cap" % cap) if cap and whole["hr"] and whole["hr"] <= cap else ""))
    return out


def evaluate_decision(decision, summary):
    """Apply the plan's goal-setting tiers to a decision session.

    Tiers are tried fastest first. The slowest reliable rep and the highest
    reliable rep heart rate are tested, so a mixed session (one rep in each
    tier) lands in the slower tier. A result that only just qualifies is
    borderline and takes the slower tier by default. The runner confirms.
    """
    reps = [r for r in summary["reps"]]
    slowest = max(r["pace_s_per_km"] for r in reps)
    hrs = [r["hr"] for r in reps if r["hr"] is not None and r["hr_reliable"]]
    top_hr = max(hrs) if hrs else None
    margin = decision["borderline"]
    tiers = decision["tiers"]
    qualified, borderline, why = len(tiers) - 1, False, []
    for i, tier in enumerate(tiers):
        when = tier["when"]
        if when == "otherwise":
            qualified = i
            break
        pmax = when.get("slowest_rep_pace_max_s_per_km")
        hmax = when.get("highest_rep_hr_max")
        ok_pace = pmax is None or slowest <= pmax
        ok_hr = hmax is None or (top_hr is not None and top_hr <= hmax)
        if ok_pace and ok_hr:
            qualified = i
            if pmax is not None and pmax - slowest < margin["pace_s_per_km"]:
                borderline = True
                why.append("slowest rep is within %s s per km of the tier limit" % margin["pace_s_per_km"])
            if hmax is not None and top_hr is not None and hmax - top_hr < margin["hr_bpm"]:
                borderline = True
                why.append("highest rep heart rate is at the tier limit")
            break
    applied = min(qualified + 1, len(tiers) - 1) if borderline else qualified
    return {
        "slowest_rep_pace_s_per_km": slowest, "highest_rep_hr": top_hr,
        "qualified_tier": tiers[qualified]["id"], "borderline": borderline, "borderline_why": why,
        "applied_tier": tiers[applied]["id"], "goal_time_s": tiers[applied]["goal_time_s"],
        "needs_runner_confirmation": True,
    }


def over_prescription_streak(judgements):
    """How many of the most recent judged sessions in a row were run faster than prescribed.

    `judgements` is oldest first. Sessions with no verdict are skipped.
    """
    streak = 0
    for j in reversed([j for j in judgements if j and j.get("verdict") not in (None, "unknown")]):
        if j.get("over_prescribed"):
            streak += 1
        else:
            break
    return streak
