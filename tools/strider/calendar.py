"""Calendar events from the plan.

`events()` returns plain dicts the build-block skill can hand to a calendar
connector. `to_ics()` writes the same events as an iCalendar file, so the plan
still reaches a phone when no calendar connector is available.
"""
from __future__ import annotations

import datetime as dt

from .plan import RUN_KINDS, all_days, rule
from .workout import describe_steps

DONE_PREFIX = {"done": "Done: ", "moved": "Moved: ", "missed": "Missed: ", "skipped": "Skipped: "}


def events(plan):
    units = plan["units"]
    by_date = {}
    for item in plan.get("logistics", []):
        by_date.setdefault(item["date"], []).append(item)
    out, used = [], set()
    for week, day in all_days(plan):
        if day["kind"] == "rest":
            continue
        lines = []
        if day["kind"] in RUN_KINDS:
            lines.append(describe_steps(day, units))
        if day["kind"] in ("key", "test"):
            lines.append("Go/no-go: under %dh of recovery time left, go. %d to %dh, the heart-rate cap is absolute. "
                         "Over %dh, move it a day." % (rule(plan, "recovery_go_h"), rule(plan, "recovery_go_h"),
                                                       rule(plan, "recovery_move_h"), rule(plan, "recovery_move_h")))
        if day.get("notes"):
            lines.append(day["notes"])
        for item in by_date.get(day["date"], []):
            lines.append("%s: %s" % (item["kind"].capitalize(), item["text"]))
        used.add(day["date"])
        ev = {"uid": "strider-%s-%s" % (plan["race"]["date"], day["date"]), "date": day["date"],
              "title": DONE_PREFIX.get(day["status"], "") + "W%d %s" % (week["n"], day["title"]),
              "description": "\n".join(x for x in lines if x), "all_day": True,
              "event_id": day.get("calendar_event_id")}
        if day["kind"] == "race":
            ev.update({"all_day": False, "start": plan["race"]["start"], "tz": plan["race"]["tz"],
                       "location": plan["race"].get("location", "")})
        out.append(ev)
    for date, items in sorted(by_date.items()):
        if date in used:
            continue
        out.append({"uid": "strider-%s-%s-notes" % (plan["race"]["date"], date), "date": date,
                    "title": "; ".join(i["kind"].capitalize() for i in items),
                    "description": "\n".join("%s: %s" % (i["kind"].capitalize(), i["text"]) for i in items),
                    "all_day": True, "event_id": None})
    out.sort(key=lambda e: e["date"])
    return out


def _esc(text):
    return (text or "").replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def _fold(line):
    chunks = []
    while len(line.encode("utf-8")) > 73:
        cut = 73
        while len(line[:cut].encode("utf-8")) > 73:
            cut -= 1
        chunks.append(line[:cut])
        line = " " + line[cut:]
    chunks.append(line)
    return "\r\n".join(chunks)


def to_ics(plan, stamp=None):
    stamp = stamp or dt.datetime(2000, 1, 1)
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//strider//training plan//EN", "CALSCALE:GREGORIAN"]
    for ev in events(plan):
        day = dt.date.fromisoformat(ev["date"])
        lines += ["BEGIN:VEVENT", "UID:%s@strider" % ev["uid"], "DTSTAMP:%s" % stamp.strftime("%Y%m%dT%H%M%SZ")]
        if ev["all_day"]:
            lines += ["DTSTART;VALUE=DATE:%s" % day.strftime("%Y%m%d"),
                      "DTEND;VALUE=DATE:%s" % (day + dt.timedelta(days=1)).strftime("%Y%m%d")]
        else:
            hh, mm = ev["start"].split(":")
            start = dt.datetime(day.year, day.month, day.day, int(hh), int(mm))
            lines += ["DTSTART;TZID=%s:%s" % (ev["tz"], start.strftime("%Y%m%dT%H%M%S")),
                      "DURATION:PT4H"]
            if ev.get("location"):
                lines.append("LOCATION:" + _esc(ev["location"]))
        lines += ["SUMMARY:" + _esc(ev["title"]), "DESCRIPTION:" + _esc(ev["description"]), "END:VEVENT"]
    lines.append("END:VCALENDAR")
    return "\r\n".join(_fold(l) for l in lines) + "\r\n"
