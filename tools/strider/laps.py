"""Lap analysis: turn Garmin laps into reps, and check the data before judging it.

Input is the `laps` list returned by garmin_mcp's `get_activity_splits`
(fields: distance_meters, duration_seconds, avg_hr_bpm, avg_power_watts,
avg_cadence, intensity_type, elevation_gain_meters, elevation_loss_meters).

Nothing here looks at whole-run averages. A session is described by its work
reps, with warm-up, recoveries and cool-down removed.
"""
from __future__ import annotations

from .units import KM

MIN_LAP_M = 120          # shorter laps are button noise
MIN_LAP_S = 60
LONG_LAP_S = 150         # unlabelled laps must last this long to count as work
WORK_SPEED_FRACTION = 0.82   # ... and run at least this fraction of the fastest
HR_LAG_BPM = 12          # a rep this far under the session median is sensor lag
HILL_CLIMB_M = 25        # net climb in a rep that inflates wrist power
FLAT_GAIN_M_PER_KM = 8   # more "climb" than this on a track or flat route is altimeter error

WORK_LABELS = ("INTERVAL", "ACTIVE")
REST_LABELS = ("RECOVERY", "REST")


def _kind(lap):
    return str(lap.get("intensity_type") or "").upper()


def _pos(value):
    return isinstance(value, (int, float)) and value > 0


def work_lap_indexes(laps):
    """Indexes of the laps that are work, not warm-up, jog or cool-down."""
    real = [i for i, l in enumerate(laps or [])
            if l and (l.get("distance_meters") or 0) > MIN_LAP_M
            and (l.get("duration_seconds") or 0) > MIN_LAP_S]
    if not real:
        return []
    kinds = set(_kind(laps[i]) for i in real)
    if len(kinds) > 1:
        labelled = [i for i in real if _kind(laps[i]) in WORK_LABELS]
        if labelled:
            longest = max(laps[i]["distance_meters"] for i in labelled)
            if longest >= 3000:
                labelled = [i for i in labelled if laps[i]["distance_meters"] >= 800]
            return labelled
    # Labels carry no signal (a plain run, or a manual-lap session): use effort.
    long_laps = [i for i in real if laps[i]["duration_seconds"] >= LONG_LAP_S]
    if not long_laps:
        return real

    def speed(i):
        return laps[i]["distance_meters"] / laps[i]["duration_seconds"]

    vmax = max(speed(i) for i in long_laps)
    return [i for i in long_laps if speed(i) >= WORK_SPEED_FRACTION * vmax]


def _new_rep():
    return {"distance_m": 0.0, "duration_s": 0.0, "_hrw": 0.0, "_hrd": 0.0,
            "_pw": 0.0, "_pd": 0.0, "_cw": 0.0, "_cd": 0.0, "_lap_power": [],
            "climb_m": 0.0, "lap_indexes": [], "_gap": None}


def build_reps(laps):
    """Join consecutive work laps into reps and attach the jog that follows each.

    Garmin auto-laps inside long reps, so a 3 km rep can arrive as three laps.
    """
    work = set(work_lap_indexes(laps))
    reps, cur, gap = [], None, None
    for i, lap in enumerate(laps or []):
        d = lap.get("duration_seconds") or 0
        if i in work:
            if cur is None:
                cur = _new_rep()
                reps.append(cur)
                gap = None
            cur["distance_m"] += lap.get("distance_meters") or 0
            cur["duration_s"] += d
            cur["lap_indexes"].append(i)
            cur["climb_m"] += (lap.get("elevation_gain_meters") or 0) - (lap.get("elevation_loss_meters") or 0)
            if _pos(lap.get("avg_hr_bpm")):
                cur["_hrw"] += lap["avg_hr_bpm"] * d
                cur["_hrd"] += d
            if _pos(lap.get("avg_power_watts")):
                cur["_pw"] += lap["avg_power_watts"] * d
                cur["_pd"] += d
                cur["_lap_power"].append(lap["avg_power_watts"])
            if _pos(lap.get("avg_cadence")):
                cur["_cw"] += lap["avg_cadence"] * d
                cur["_cd"] += d
        else:
            if cur is not None:
                gap = {"hrw": 0.0, "hrd": 0.0, "labelled": 0}
                cur["_gap"] = gap
                cur = None
            if gap is not None and d > 20 and _pos(lap.get("avg_hr_bpm")):
                kind = _kind(lap)
                if kind == "COOLDOWN":
                    gap = None
                    continue
                gap["hrw"] += lap["avg_hr_bpm"] * d
                gap["hrd"] += d
                if kind in REST_LABELS:
                    gap["labelled"] += 1
    # The jog after the final rep only counts when the watch labelled it a recovery.
    if reps and reps[-1]["_gap"] and not reps[-1]["_gap"]["labelled"]:
        reps[-1]["_gap"] = None
    return reps


def _efficiency(reps, excluded):
    p = pd = h = hd = 0.0
    for i, r in enumerate(reps):
        if i in excluded or not r["_hrd"] or not r["_pd"]:
            continue
        p += r["_pw"]
        pd += r["_pd"]
        h += r["_hrw"]
        hd += r["_hrd"]
    return (p / pd) / (h / hd) if pd and hd else None


def summarize(laps, distance_factor=1.0, terrain="rolling"):
    """Describe a session by its reps.

    distance_factor: watch distance / true distance for this runner (1.01 means
      the watch reads 1% long). Paces are corrected to true distance. Pass 1.0
      for track sessions, where the distance is measured.
    terrain: "track", "flat", "rolling" or "hilly". On track or flat routes an
      altimeter reading that shows real climbing is treated as sensor error.

    Returns None when there is no usable work.
    """
    reps = build_reps(laps)
    dist = sum(r["distance_m"] for r in reps)
    dur = sum(r["duration_s"] for r in reps)
    if dist < 400 or dur < 120:
        return None

    flags = []
    total_m = sum((l.get("distance_meters") or 0) for l in laps)
    total_gain = sum((l.get("elevation_gain_meters") or 0) for l in laps)
    altimeter_bad = (terrain in ("track", "flat") and total_m > 0
                     and total_gain / (total_m / KM) > FLAT_GAIN_M_PER_KM)
    if altimeter_bad:
        flags.append({"code": "altimeter_implausible", "rep": None,
                      "detail": "%d m of climb recorded over %.1f km on a %s route. Elevation, "
                                "power, fade and efficiency are not judged for this session."
                                % (round(total_gain), total_m / KM, terrain)})

    rep_hrs = sorted(r["_hrw"] / r["_hrd"] for r in reps if r["_hrd"])
    median_hr = rep_hrs[len(rep_hrs) // 2] if rep_hrs else None
    hr_excluded = set()
    out = []
    for i, r in enumerate(reps):
        hr = r["_hrw"] / r["_hrd"] if r["_hrd"] else None
        power = r["_pw"] / r["_pd"] if r["_pd"] else None
        lp = r["_lap_power"]
        fade = (lp[0] - lp[-1]) / lp[0] * 100 if len(lp) > 1 and lp[0] else None
        hilly = abs(r["climb_m"]) > HILL_CLIMB_M and not altimeter_bad
        if hr is not None and median_hr is not None and len(reps) > 1 and hr < median_hr - HR_LAG_BPM:
            hr_excluded.add(i)
            flags.append({"code": "hr_lag" if i == 0 else "hr_low_outlier", "rep": i + 1,
                          "detail": "Rep %d heart rate %d is %d under the session median. Treated as "
                                    "sensor lag: left out of efficiency and heart-rate cap checks."
                                    % (i + 1, round(hr), round(median_hr - hr))})
        if hilly:
            flags.append({"code": "hill_power", "rep": i + 1,
                          "detail": "Rep %d has %+d m net climb, which inflates wrist power. "
                                    "Its power and fade are not judged." % (i + 1, round(r["climb_m"]))})
        gap = r["_gap"]
        out.append({
            "n": i + 1,
            "distance_m": round(r["distance_m"], 1),
            "duration_s": round(r["duration_s"], 1),
            "pace_s_per_km": round(r["duration_s"] / (r["distance_m"] / KM) * distance_factor, 1),
            "hr": round(hr) if hr is not None else None,
            "hr_reliable": i not in hr_excluded,
            "power": round(power) if power is not None else None,
            "power_reliable": bool(power is not None and not hilly and not altimeter_bad),
            "fade_pct": round(fade, 1) if fade is not None else None,
            "cadence": round(r["_cw"] / r["_cd"], 1) if r["_cd"] else None,
            "climb_m": round(r["climb_m"], 1),
            "jog_hr": round(gap["hrw"] / gap["hrd"]) if gap and gap["hrd"] else None,
            "lap_indexes": r["lap_indexes"],
        })

    hrw = sum(r["_hrw"] for i, r in enumerate(reps) if i not in hr_excluded)
    hrd = sum(r["_hrd"] for i, r in enumerate(reps) if i not in hr_excluded)
    pw = sum(r["_pw"] for r in reps)
    pd = sum(r["_pd"] for r in reps)
    power_ok = not altimeter_bad and not any(f["code"] == "hill_power" for f in flags)
    eff = _efficiency(reps, hr_excluded) if not altimeter_bad else None
    return {
        "reps": out,
        "pace_s_per_km": round(dur / (dist / KM) * distance_factor, 1),
        "hr": round(hrw / hrd) if hrd else None,
        "power": round(pw / pd) if pd else None,
        "power_reliable": power_ok and bool(pd),
        "efficiency": round(eff, 3) if eff else None,
        "jog_hr": [r["jog_hr"] for r in out if r["jog_hr"] is not None],
        "work_distance_m": round(dist, 1),
        "work_duration_s": round(dur, 1),
        "distance_factor": distance_factor,
        "flags": flags,
    }


def whole_run(laps, distance_factor=1.0):
    """Lap-weighted totals for an easy or long run (still built from laps)."""
    dist = dur = hrw = hrd = pw = pd = 0.0
    for l in laps or []:
        d = l.get("duration_seconds") or 0
        dist += l.get("distance_meters") or 0
        dur += d
        if _pos(l.get("avg_hr_bpm")):
            hrw += l["avg_hr_bpm"] * d
            hrd += d
        if _pos(l.get("avg_power_watts")) and _pos(l.get("avg_hr_bpm")):
            pw += l["avg_power_watts"] * d
            pd += d
    if dist < 400 or dur < 120:
        return None
    return {
        "distance_m": round(dist, 1), "duration_s": round(dur, 1),
        "pace_s_per_km": round(dur / (dist / KM) * distance_factor, 1),
        "hr": round(hrw / hrd) if hrd else None,
        "efficiency": round((pw / pd) / (hrw / hrd), 3) if pd and hrd else None,
        "gain_m_per_km": round(sum((l.get("elevation_gain_meters") or 0) for l in laps) / (dist / KM), 1),
        "lap_count": len(laps),
    }


def tail_segment(laps, distance_m, distance_factor=1.0):
    """The last `distance_m` of a run, from whole laps, ignoring a labelled cool-down.

    Used to check whether a prescribed steady or fast finish was actually run.
    Returns None when the run is a single lap, because one lap cannot show it;
    the caller should then try typed splits or per-second data.
    """
    body = [l for l in (laps or []) if _kind(l) != "COOLDOWN" and (l.get("distance_meters") or 0) > MIN_LAP_M]
    if len(body) < 2:
        return None
    picked, covered = [], 0.0
    for lap in reversed(body):
        picked.append(lap)
        covered += lap.get("distance_meters") or 0
        if covered >= distance_m * 0.9:
            break
    if covered < distance_m * 0.6:
        return None
    seg = whole_run(list(reversed(picked)), distance_factor)
    if seg:
        seg["laps_used"] = len(picked)
    return seg


def typed_run_segments(typed):
    """Run segments from `get_activity_typed_splits`, as lap-shaped dicts.

    A run recorded as one lap still has typed splits: the watch breaks the
    activity wherever running stopped and restarted. That recovers some
    structure (for example strides at the end) that the lap list hides.
    """
    out = []
    for s in (typed or {}).get("splits") or []:
        if s.get("type") != "RWD_RUN" or (s.get("distance") or 0) <= MIN_LAP_M:
            continue
        out.append({
            "distance_meters": s.get("distance"), "duration_seconds": s.get("duration"),
            "avg_hr_bpm": s.get("averageHR"), "avg_power_watts": s.get("averagePower"),
            "avg_cadence": s.get("averageRunCadence"),
            "elevation_gain_meters": s.get("elevationGain"), "elevation_loss_meters": s.get("elevationLoss"),
            "intensity_type": "",
        })
    return out


def form_by_rep(typed, summary):
    """Per-rep running form from typed splits (INTERVAL_ACTIVE entries).

    Returns one dict per rep with cadence (steps/min), ground contact time (ms),
    stride length (cm), vertical oscillation (cm) and vertical ratio (%), or an
    empty list when the watch did not record a structured workout.
    """
    if not typed or not summary:
        return []
    active = [s for s in typed.get("splits") or []
              if s.get("type") == "INTERVAL_ACTIVE" and (s.get("duration") or 0) > MIN_LAP_S
              and s.get("lapIndexes")]
    by_first_lap = dict((s["lapIndexes"][0] - 1, s) for s in active)
    rows = []
    for rep in summary["reps"]:
        s = by_first_lap.get(rep["lap_indexes"][0])
        if not s or not s.get("groundContactTime"):
            continue
        rows.append({
            "n": rep["n"],
            "speed_mps": s.get("averageSpeed"),
            "cadence": round(s.get("averageRunCadence") or 0, 1) or None,
            "gct_ms": round(s.get("groundContactTime"), 1),
            "stride_cm": round(s.get("strideLength") or 0, 1) or None,
            "vert_osc_cm": round(s.get("verticalOscillation") or 0, 2) or None,
            "vert_ratio_pct": round(s.get("verticalRatio") or 0, 2) or None,
        })
    return rows


FORM_GCT_RISE_PCT = 4.0
FORM_CADENCE_DROP_PCT = 2.0
FORM_VR_RISE_PCT = 4.0
FORM_SAME_PACE_PCT = 2.0


def form_drift(rows):
    """Compare the last rep's form with the first at matching pace.

    Coaching heuristic: ground contact time up 4% or more, together with cadence
    down 2% or vertical ratio up 4%, while speed is within 2%, means form is
    breaking down before pace does.
    """
    if len(rows) < 2:
        return None
    a, b = rows[0], rows[-1]

    def pct(key):
        if not a.get(key) or not b.get(key):
            return None
        return round((b[key] - a[key]) / a[key] * 100, 1)

    d = {"speed_pct": pct("speed_mps"), "gct_pct": pct("gct_ms"), "cadence_pct": pct("cadence"),
         "vert_ratio_pct": pct("vert_ratio_pct"), "stride_pct": pct("stride_cm")}
    same_pace = d["speed_pct"] is not None and abs(d["speed_pct"]) <= FORM_SAME_PACE_PCT
    drift = bool(same_pace and d["gct_pct"] is not None and d["gct_pct"] >= FORM_GCT_RISE_PCT and (
        (d["cadence_pct"] is not None and d["cadence_pct"] <= -FORM_CADENCE_DROP_PCT)
        or (d["vert_ratio_pct"] is not None and d["vert_ratio_pct"] >= FORM_VR_RISE_PCT)))
    d["comparable"] = same_pace
    d["drift"] = drift
    return d
