"""Per-second form analysis: does running form break down late in a rep?

Lap averages hide this. A rep can hold pace to the end while ground contact
time creeps up and cadence drops, which is the earliest sign the rep length is
at the runner's limit.

Records come from the activity's FIT file, by either route:
  - `download_activity_file` (garmin_mcp) saves the .fit to disk; reading it
    here needs the optional `fitparse` package;
  - `get_activity_fit_messages(include_records=True, message_types=["record"])`
    saved as JSON. Fine for a short run, token-heavy for a long one.
"""
from __future__ import annotations

import datetime as dt
import json

SKIP_START_S = 30        # acceleration and heart-rate lag at the start of a rep
SAME_PACE_PCT = 2.0
GCT_RISE_PCT = 4.0
CADENCE_DROP_PCT = 2.0
VR_RISE_PCT = 4.0
MIN_REP_S = 150

FIELDS = {"distance": "distance_m", "enhanced_speed": "speed_mps", "speed": "speed_mps", "heart_rate": "hr",
          "power": "power", "stance_time": "gct_ms", "step_length": "step_mm",
          "vertical_oscillation": "vert_osc_mm", "vertical_ratio": "vert_ratio_pct"}


def _normalize(rows):
    """rows: dicts of FIT record field name -> value. Returns records with seconds from the start."""
    out, t0 = [], None
    for row in rows:
        stamp = row.get("timestamp")
        if stamp is None:
            continue
        if isinstance(stamp, str):
            stamp = dt.datetime.fromisoformat(stamp.replace("Z", ""))
        if t0 is None:
            t0 = stamp
        rec = {"t": (stamp - t0).total_seconds(), "time": stamp.isoformat()}
        for src, dst in FIELDS.items():
            if row.get(src) is not None and dst not in rec:
                rec[dst] = row[src]
        if row.get("cadence") is not None:
            # FIT running cadence is per leg, with a fractional part stored separately
            rec["cadence"] = (row["cadence"] + (row.get("fractional_cadence") or 0)) * 2
        out.append(rec)
    return out


def records_from_messages(payload):
    """From a saved `get_activity_fit_messages` result (one or more pages merged)."""
    rows = []
    for msg in payload.get("messages") or []:
        if msg.get("type") == "record":
            rows.append(dict((f["name"], f.get("value")) for f in msg.get("fields") or []))
    return _normalize(rows)


def records_from_fit(path):
    try:
        import fitparse  # optional dependency
    except ImportError:
        raise SystemExit("Reading .fit files needs the fitparse package: pip install fitparse\n"
                         "Or save get_activity_fit_messages output as JSON and pass that instead.")
    fit = fitparse.FitFile(path)
    return _normalize([dict((f.name, f.value) for f in m) for m in fit.get_messages("record")])


def load_records(path):
    if path.lower().endswith(".fit"):
        return records_from_fit(path)
    with open(path) as fh:
        body = json.load(fh)
    if isinstance(body, dict) and "result" in body:
        body = body["result"]
    if isinstance(body, dict) and "messages" in body:
        return records_from_messages(body)
    if isinstance(body, dict) and "records" in body:
        body = body["records"]
    return _normalize(body) if body and "t" not in body[0] else body


def windows_from_laps(lap_list, summary, records):
    """Rep time windows (seconds from the start) from the lap list's start times."""
    if not records or not lap_list or not lap_list[0].get("start_time_gmt"):
        return []
    t0 = dt.datetime.fromisoformat(records[0]["time"])
    wins = []
    for rep in summary["reps"]:
        first, last = lap_list[rep["lap_indexes"][0]], lap_list[rep["lap_indexes"][-1]]
        a = dt.datetime.fromisoformat(first["start_time_gmt"].split(".")[0])
        b = dt.datetime.fromisoformat(last["start_time_gmt"].split(".")[0]) + dt.timedelta(seconds=last["duration_seconds"])
        wins.append(((a - t0).total_seconds(), (b - t0).total_seconds()))
    return wins


def detect_windows(records, min_s=MIN_REP_S):
    """Find reps without laps: stretches at 90% or more of the session's fast speed."""
    speeds = sorted(r["speed_mps"] for r in records if r.get("speed_mps"))
    if not speeds:
        return []
    fast = speeds[int(len(speeds) * 0.9)]
    wins, start, last = [], None, None
    for r in records:
        on = (r.get("speed_mps") or 0) >= 0.9 * fast
        if on and start is None:
            start = r["t"]
        if on:
            last = r["t"]
        if start is not None and (not on) and r["t"] - last > 10:
            if last - start >= min_s:
                wins.append((start, last))
            start = None
    if start is not None and last - start >= min_s:
        wins.append((start, last))
    return wins


def _mean(records, key):
    vals = [r[key] for r in records if r.get(key)]
    return sum(vals) / len(vals) if vals else None


def rep_form(records, window):
    """Compare the last third of a rep with the first third."""
    a, b = window
    body = [r for r in records if a + SKIP_START_S <= r["t"] <= b]
    if len(body) < 60:
        return None
    third = (b - a - SKIP_START_S) / 3.0
    first = [r for r in body if r["t"] < a + SKIP_START_S + third]
    last = [r for r in body if r["t"] >= b - third]
    out = {"start_s": round(a), "duration_s": round(b - a)}
    for key in ("speed_mps", "hr", "cadence", "gct_ms", "step_mm", "vert_ratio_pct", "power"):
        x, y = _mean(first, key), _mean(last, key)
        out[key] = {"first": round(x, 2), "last": round(y, 2), "pct": round((y - x) / x * 100, 1)} if x and y else None

    def pct(key):
        return out[key]["pct"] if out[key] else None

    held = pct("speed_mps") is not None and abs(pct("speed_mps")) <= SAME_PACE_PCT
    breakdown = bool(held and pct("gct_ms") is not None and pct("gct_ms") >= GCT_RISE_PCT and (
        (pct("cadence") is not None and pct("cadence") <= -CADENCE_DROP_PCT)
        or (pct("vert_ratio_pct") is not None and pct("vert_ratio_pct") >= VR_RISE_PCT)))
    out["pace_held"] = held
    out["breakdown"] = breakdown
    if breakdown and out["gct_ms"]:
        # when did ground contact first sit 4% above the first third and stay there?
        limit = out["gct_ms"]["first"] * (1 + GCT_RISE_PCT / 100)
        onset = None
        for r in reversed(body):
            win = [q["gct_ms"] for q in body if r["t"] - 30 <= q["t"] <= r["t"] and q.get("gct_ms")]
            if win and sum(win) / len(win) >= limit:
                onset = r["t"] - 30
            else:
                break
        if onset is not None:
            out["breakdown_from_s"] = max(0, round(onset - a))
    return out


def analyze(records, windows=None):
    windows = windows or detect_windows(records)
    reps = [x for x in (rep_form(records, w) for w in windows) if x]
    broken = [i + 1 for i, r in enumerate(reps) if r["breakdown"]]
    lines = []
    if not reps:
        lines.append("No rep long enough to read form from (needs %d s or more)." % MIN_REP_S)
    elif broken:
        lines.append("Form broke down late in rep %s while pace held: ground contact up, cadence or bounce worse. "
                     "Hold this rep length next week rather than extending it." % ", ".join(map(str, broken)))
    else:
        lines.append("Form held to the end of every rep. Rep length can progress as planned.")
    return {"reps": reps, "breakdown_reps": broken, "lines": lines}
