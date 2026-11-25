"""The decisions log: what the runner told the coach, kept so it is never asked twice.

`decisions.md` lives in the training folder next to `athlete.md` and outlives any one block. The
plan's own `log` records what happened to this plan; this file records what the coach must keep
doing from now on: a corrected number, a preference, an override and why, a standing exception.

Format (plain Markdown, one entry per heading, newest last):

    ## 2027-02-11 · correction
    - What: The bridge loop reads 3% long on the watch; use the mapped distance there.
    - Why: Runner measured it against the mapped route.
    - Applies: standing          (standing | until YYYY-MM-DD | once)
    - Source: runner             (runner | data | coach)
    - Replaces: 2027-01-30       (optional: retires the entries of that date with the same kind)

Skills read the active entries before deciding anything, and add one whenever the runner corrects
the coach, overrides a verdict, or sets a preference that should hold.
"""
from __future__ import annotations

import datetime as dt
import os
import re

KINDS = ("correction", "preference", "override", "exception", "goal", "note")
SOURCES = ("runner", "data", "coach")
FIELDS = ("what", "why", "applies", "source", "replaces")

TEMPLATE = """# Coaching decisions

<!-- What the coach must remember. Newest last. Skills read the active entries before every decision
     and add one when you correct them, override a verdict, or set a preference that should hold.
     Keep this file in your training folder, not in a public repository. Format: tools/strider/decisions.py -->
"""

_HEAD = re.compile(r"^##\s+(\d{4}-\d{2}-\d{2})\s*[·\-|]\s*(\w+)\s*$")
_FIELD = re.compile(r"^-\s*(What|Why|Applies|Source|Replaces)\s*:\s*(.*)$", re.I)


def parse(text):
    """Entries in file order: [{"date","kind","what","why","applies","source","line"}]."""
    out, cur = [], None
    for i, line in enumerate(text.splitlines(), 1):
        m = _HEAD.match(line.strip())
        if m:
            cur = {"date": m.group(1), "kind": m.group(2).lower(), "what": "", "why": "",
                   "applies": "standing", "source": "runner", "replaces": "", "line": i}
            out.append(cur)
            continue
        f = _FIELD.match(line.strip())
        if f and cur is not None:
            cur[f.group(1).lower()] = f.group(2).strip()
    return out


def problems(entries):
    """Entries a skill should not rely on until fixed."""
    bad = []
    for e in entries:
        where = "line %d (%s)" % (e["line"], e["date"])
        if e["kind"] not in KINDS:
            bad.append("%s: kind %r is not one of %s" % (where, e["kind"], ", ".join(KINDS)))
        if not e["what"]:
            bad.append("%s: no What line" % where)
        if not _applies(e["applies"]):
            bad.append("%s: Applies %r should be standing, once, or until YYYY-MM-DD" % (where, e["applies"]))
        if e["source"] not in SOURCES:
            bad.append("%s: Source %r is not one of %s" % (where, e["source"], ", ".join(SOURCES)))
    return bad


def _applies(text):
    t = text.strip().lower()
    if t in ("standing", "once"):
        return (t, None)
    m = re.match(r"until\s+(\d{4}-\d{2}-\d{2})$", t)
    return ("until", m.group(1)) if m else None


def active(entries, on):
    """Entries still in force on date `on` (YYYY-MM-DD), so the list is what the coach must apply today.

    `once` entries count only on their own date. An entry is retired by a later one that names its date
    in Replaces with the same kind, or that has exactly the same What.
    """
    keep = {}
    retired = set((e["replaces"], e["kind"]) for e in entries if e["replaces"] and e["date"] <= on)
    for e in entries:
        if (e["date"], e["kind"]) in retired:
            continue
        a = _applies(e["applies"])
        if not a or e["date"] > on:
            continue
        kind, until = a
        if kind == "once" and e["date"] != on:
            continue
        if kind == "until" and until < on:
            continue
        keep[e["what"].strip().lower()] = e
    return sorted(keep.values(), key=lambda e: (e["date"], e["line"]))


def entry_text(date, kind, what, why, applies="standing", source="runner", replaces=None):
    if kind not in KINDS:
        raise ValueError("kind must be one of " + ", ".join(KINDS))
    if not _applies(applies):
        raise ValueError("applies must be standing, once, or until YYYY-MM-DD")
    if source not in SOURCES:
        raise ValueError("source must be one of " + ", ".join(SOURCES))
    dt.date.fromisoformat(date)
    text = "\n## %s · %s\n- What: %s\n- Why: %s\n- Applies: %s\n- Source: %s\n" % (
        date, kind, " ".join(what.split()), " ".join(why.split()), applies, source)
    if replaces:
        dt.date.fromisoformat(replaces)
        text += "- Replaces: %s\n" % replaces
    return text


def add(path, **kw):
    """Append one entry, creating the file from the template if needed. Returns the text written."""
    text = entry_text(**kw)
    new = not os.path.exists(path)
    with open(path, "a") as fh:
        if new:
            fh.write(TEMPLATE)
        fh.write(text)
    return text
