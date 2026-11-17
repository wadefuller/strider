"""Find stale values after a plan change.

When a goal time or pace band changes, the old number tends to survive
somewhere: a calendar description, the athlete profile, a note. After any
change, sweep every surface for the old values and fix each hit.
"""
from __future__ import annotations

import os

from .units import fmt_clock, fmt_pace

TEXT_EXT = (".json", ".md", ".html", ".js", ".ics", ".txt")


def _goal_strings(plan):
    out = set()
    goal = plan["goal"]
    times = [goal["time_s"]] + [t["goal_time_s"] for t in (goal.get("decision") or {}).get("tiers", [])]
    for t in times:
        out.add(fmt_clock(t, True))
    for band in plan["bands"].values():
        for p in band.get("pace_s_per_km") or []:
            for units in ("km", "mi"):
                out.add(fmt_pace(p, units))
    return out


def stale_values(before, after):
    """Formatted goal times and paces present in the old plan but not the new one."""
    return sorted(_goal_strings(before) - _goal_strings(after))


def sweep(paths, old_values):
    """Return [(path, line_number, value, line)] for every occurrence of an old value."""
    files = []
    for p in paths:
        if os.path.isdir(p):
            for root, _, names in os.walk(p):
                files += [os.path.join(root, n) for n in names if n.endswith(TEXT_EXT)]
        elif os.path.exists(p):
            files.append(p)
    hits = []
    for path in sorted(set(files)):
        with open(path, errors="replace") as fh:
            for i, line in enumerate(fh, 1):
                for v in old_values:
                    if v and v in line:
                        hits.append((path, i, v, line.strip()[:160]))
    return hits
