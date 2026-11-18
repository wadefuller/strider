"""Plan validation, block generation by distance, and everything generated from a plan."""
import copy
import datetime as dt
import glob
import json
import os

import pytest

from strider import blockgen, calendar, fitform, race, snapshot, sweep, workout
from strider import plan as P
from strider.units import DISTANCES, fmt_pace, parse_clock, fmt_clock

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..", "..")
EXAMPLES = sorted(glob.glob(os.path.join(ROOT, "examples", "*", "plan.json")))


def spec(distance, units="km", weeks=None, verified=False):
    goal = {"5k": 1260, "10k": 2640, "half": 5820, "marathon": 12300}[distance]
    s = {"units": units, "goal_time_s": goal, "threshold_pace_s_per_km": 268,
         "race": {"name": "Test race", "date": "2027-10-17", "start": "08:00", "tz": "Etc/UTC", "distance": distance},
         "athlete": {"lthr": 165, "max_hr": 184, "max_hr_verified": verified, "watch_distance_factor": 1.006},
         "current_weekly_m": 45000, "longest_recent_m": 15000,
         "run_days": ["Tue", "Wed", "Fri", "Sun"], "key_day": "Wed", "long_day": "Sun"}
    if weeks:
        s["weeks"] = weeks
    return s


# ----------------------------------------------------------------- validation

def test_there_are_examples_for_at_least_two_distances():
    assert len(set(P.load(p)["race"]["distance"] for p in EXAMPLES)) >= 2


@pytest.mark.parametrize("path", EXAMPLES)
def test_example_plans_validate(path):
    plan = P.load(path)
    assert plan["synthetic"] is True
    errors, _ = P.validate(plan)
    assert errors == []


@pytest.mark.parametrize("path", EXAMPLES)
def test_builtin_validator_agrees_with_jsonschema(path):
    jsonschema = pytest.importorskip("jsonschema")
    schema = P.load(P.SCHEMA_PATH)
    plan = P.load(path)
    jsonschema.Draft202012Validator.check_schema(schema)
    assert list(jsonschema.Draft202012Validator(schema).iter_errors(plan)) == []
    for breakage in (lambda p: p.pop("units"), lambda p: p["race"].update(distance="ultra"),
                     lambda p: p["weeks"][0]["days"][0].update(surprise=1),
                     lambda p: p["bands"]["goal"].update(pace_s_per_km=[240]),
                     lambda p: p["goal"]["decision"].update(runner_confirms=False)):
        bad = copy.deepcopy(plan)
        breakage(bad)
        assert P.schema_errors(bad, schema) and list(jsonschema.Draft202012Validator(schema).iter_errors(bad))


def test_validator_enforces_the_lessons():
    plan, _ = blockgen.build_block(spec("half"))

    def errors_after(change):
        bad = copy.deepcopy(plan)
        change(bad)
        return " | ".join(P.validate(bad)[0])

    def drop_cap(p):
        key = [d for d in p["weeks"][2]["days"] if d["kind"] == "key"][0]
        del key["steps"][1]["steps"][0]["hr_cap"]

    def drop_long_cap(p):
        del [d for d in p["weeks"][0]["days"] if d["kind"] == "long"][0]["hr_cap"]

    def late_test(p):
        day = [d for d in p["weeks"][1]["days"] if d.get("session") == "max_hr_test"][0]
        p["weeks"][1]["days"].remove(day)
        day["date"] = (P.d(p["weeks"][7]["start"]) + dt.timedelta(days=3)).isoformat()
        p["weeks"][7]["days"].append(day)

    assert "pace band and a heart-rate cap" in errors_after(drop_cap)
    assert "easy and long runs need a heart-rate cap" in errors_after(drop_long_cap)
    assert "schedule it by week" in errors_after(late_test)
    assert "blocked weekday" in errors_after(lambda p: p["rules"].update(blocked_weekdays=["Wed"]))
    assert "exactly one race day" in errors_after(lambda p: p["race"].update(date="2027-10-16"))


# ------------------------------------------------------------ block generator

@pytest.mark.parametrize("distance", sorted(DISTANCES))
@pytest.mark.parametrize("units", ["km", "mi"])
def test_generated_blocks_validate_for_every_distance(distance, units):
    plan, _ = blockgen.build_block(spec(distance, units))
    errors, _ = P.validate(plan)
    assert errors == []
    decision = plan["goal"]["decision"]
    assert decision["tiers"][-1]["when"] == "otherwise" and plan["goal"]["status"] == "provisional"
    kinds = set(i["kind"] for i in plan["logistics"])
    assert {"strength", "shoes", "caffeine", "check"} <= kinds
    assert ("fuel" in kinds) == (distance in ("half", "marathon"))


def test_the_block_depends_on_the_distance():
    plans = dict((d, blockgen.build_block(spec(d))[0]) for d in DISTANCES)
    weeks = dict((d, len(p["weeks"])) for d, p in plans.items())
    assert weeks["5k"] < weeks["half"] < weeks["marathon"]

    def longest(p):
        return max(d["distance_m"] for _, d in P.all_days(p) if d["kind"] == "long")

    assert longest(plans["5k"]) < longest(plans["half"]) < longest(plans["marathon"])
    sessions = dict((d, set(day.get("session") for _, day in P.all_days(p))) for d, p in plans.items())
    assert "vo2" in sessions["5k"] and "vo2" not in sessions["marathon"]
    assert "marathon_pace" in sessions["marathon"] and "goal_pace" in sessions["10k"]
    taper = dict((d, sum(1 for w in p["weeks"] if w["phase"] == "taper")) for d, p in plans.items())
    assert taper["marathon"] > taper["5k"]
    caps = dict((d, p["bands"]["goal"]["hr_cap"]) for d, p in plans.items())
    assert caps["marathon"] < caps["half"] < caps["10k"] <= caps["5k"]


def test_max_hr_test_is_early_unless_verified():
    plan, _ = blockgen.build_block(spec("10k"))
    tests = [w["n"] for w, d in P.all_days(plan) if d.get("session") == "max_hr_test"]
    assert tests and tests[0] <= 2
    verified, _ = blockgen.build_block(spec("10k", verified=True))
    assert not [d for _, d in P.all_days(verified) if d.get("session") == "max_hr_test"]


def test_short_block_and_ambitious_goal_are_said_plainly():
    s = spec("marathon", weeks=8)
    s["goal_time_s"] = 10200
    _, notes = blockgen.build_block(s)
    assert any("shorter than" in n for n in notes) and any("provisional" in n for n in notes)


# ------------------------------------------------------------------ surfaces

def all_steps(steps):
    for s in steps:
        yield s
        for inner in all_steps(s.get("workoutSteps", [])):
            yield inner


@pytest.mark.parametrize("path", EXAMPLES)
def test_garmin_workout_follows_the_documented_dto_rules(path):
    plan = P.load(path)
    for week, day in P.all_days(plan):
        if not day.get("steps") or day["kind"] not in P.RUN_KINDS:
            continue
        w = workout.to_garmin(day, plan, week["n"])
        steps = list(all_steps(w["workoutSegments"][0]["workoutSteps"]))
        assert [s["stepOrder"] for s in steps] == list(range(1, len(steps) + 1))       # one depth-first counter
        for s in steps:
            assert "targetValueOne" not in s.get("targetType", {})
            if s["type"] == "RepeatGroupDTO":
                assert s["endCondition"] == {"conditionTypeId": 7, "conditionTypeKey": "iterations"}
            elif s["targetType"]["workoutTargetTypeKey"] == "pace.zone":
                assert s["targetType"]["workoutTargetTypeId"] == 6
                assert 2.0 < s["targetValueOne"] <= s["targetValueTwo"] < 7.0             # m/s, slower bound first
            elif s["targetType"]["workoutTargetTypeKey"] == "heart.rate.zone":
                assert s["targetType"]["workoutTargetTypeId"] == 4 and s["targetValueOne"] < s["targetValueTwo"]


def test_pace_target_is_converted_for_a_watch_that_reads_long():
    plan = P.load(EXAMPLES[0])
    day = [d for _, d in P.all_days(plan) if d["kind"] == "key"][0]
    plan["athlete"]["watch_distance_factor"] = 1.0
    plain = workout.to_garmin(day, plan)["workoutSegments"][0]["workoutSteps"][1]["workoutSteps"][0]["targetValueOne"]
    plan["athlete"]["watch_distance_factor"] = 1.01
    long_ = workout.to_garmin(day, plan)["workoutSegments"][0]["workoutSteps"][1]["workoutSteps"][0]["targetValueOne"]
    assert long_ == pytest.approx(plain * 1.01, rel=1e-3)


@pytest.mark.parametrize("path", EXAMPLES)
def test_calendar_has_an_event_per_run_day_and_valid_ics(path):
    plan = P.load(path)
    events = calendar.events(plan)
    run_days = [d for _, d in P.all_days(plan) if d["kind"] in P.RUN_KINDS]
    assert len([e for e in events if not e["uid"].endswith("notes")]) == len(run_days)
    key = [e for e in events if "decision session" in e["title"]][0]
    assert "Go/no-go" in key["description"] and "Shoes:" in key["description"]
    ics = calendar.to_ics(plan)
    assert ics.count("BEGIN:VEVENT") == len(events) == ics.count("END:VEVENT")
    assert all(len(line.encode()) <= 75 for line in ics.split("\r\n"))


def test_changing_the_goal_is_one_edit_and_the_sweep_finds_what_is_stale(tmp_path):
    before = P.load(EXAMPLES[0])
    s = P.load(os.path.join(os.path.dirname(EXAMPLES[0]), "block-input.json"))
    s["goal_time_s"] += 60
    after, _ = blockgen.build_block(s)
    old = sweep.stale_values(before, after)
    assert fmt_clock(before["goal"]["time_s"], True) in old
    (tmp_path / "event.md").write_text("Race goal %s\nnothing here\n" % fmt_clock(before["goal"]["time_s"], True))
    (tmp_path / "plan.json").write_text(json.dumps(after))
    hits = sweep.sweep([str(tmp_path)], old)
    assert [os.path.basename(h[0]) for h in hits] == ["event.md"]


def test_pace_chart_reaches_the_goal_and_shows_watch_distance():
    plan = P.load(EXAMPLES[0])
    chart = race.pace_chart(plan)
    assert chart["rows"][-1]["marker"] == "finish" and chart["rows"][-1]["elapsed_s"] == plan["goal"]["time_s"]
    assert chart["rows"][-1]["watch_reads_m"] > plan["race"]["distance_m"]
    assert chart["watch_pace"] <= chart["pace"]


def test_race_review_waits_for_the_chip_time():
    plan = P.load(EXAMPLES[0])
    plan["athlete"]["watch_distance_factor"] = 1.0
    n = 10
    lap_list = [{"distance_meters": 1010.0, "duration_seconds": 250.0 - i, "avg_hr_bpm": 160 + i} for i in range(n)]
    r = race.review(plan, lap_list)
    assert r["official"] is False and r["watch_distance_factor"] is None
    assert any("chip time" in line for line in r["lines"])
    assert r["split_delta_s"] < 0                                     # negative split
    official = race.review(plan, lap_list, chip_time_s=parse_clock("40:50"))
    assert official["official"] and official["watch_distance_factor"] == pytest.approx(1.01)


def test_post_race_recovery_check():
    plan = P.load(EXAMPLES[0])
    race_day = P.d(plan["race"]["date"])
    good = {"hrv_7d": plan["athlete"]["hrv_baseline_ms"][0] + 4, "rhr_last": plan["athlete"]["resting_hr"],
            "recovery_hours_now": 0, "sleep_avg": 80}
    assert race.recovery_check(plan, good, race_day + dt.timedelta(days=4))["verdict"] == "easy_running_ok"
    assert race.recovery_check(plan, good, race_day + dt.timedelta(days=9))["verdict"] == "quality_ok"
    bad = dict(good, hrv_7d=plan["athlete"]["hrv_baseline_ms"][0] - 6)
    assert race.recovery_check(plan, bad, race_day + dt.timedelta(days=9))["verdict"] == "easy_only"
    assert race.recovery_check(plan, {}, race_day + dt.timedelta(days=4))["verdict"] == "unknown"


# --------------------------------------------------------- snapshot and rules

@pytest.mark.parametrize("path", EXAMPLES)
def test_snapshot_from_example_raw_data(path):
    folder = os.path.dirname(path)
    plan = P.load(path)
    shipped = P.load(os.path.join(folder, "dashboard", "snapshot.json"))
    raw, fetched = snapshot.load_raw(os.path.join(folder, "raw"))
    now = dt.datetime.fromisoformat(shipped["generated_at"])
    snap = snapshot.build(plan, raw, fetched, now)
    assert json.loads(json.dumps(snap)) == shipped                    # the bundled snapshot is reproducible
    assert snap["stale"] is False
    assert snapshot.build(plan, raw, fetched, now + dt.timedelta(days=3))["stale"] is True
    statuses = set(e["status"] for e in snap["days"].values())
    assert "moved" in statuses and "done" in statuses
    for date, e in snap["days"].items():
        if e.get("activity_id") and P.find_day(plan, date)["kind"] in ("key", "test"):
            assert "summary" in e and e["summary"]["reps"]            # judged from laps


def test_recovery_go_no_go_thresholds():
    plan = P.load(EXAMPLES[0])
    now = dt.datetime(2027, 1, 6, 7, 0)

    def verdict(hours, **extra):
        rec = dict({"recovery_hours": hours, "recovery_as_of": "2027-01-06T07:00:00.0", "hrv_last": 70}, **extra)
        return snapshot.recovery_verdict(rec, plan, now)["verdict"]

    assert verdict(11) == "go" and verdict(13) == "cap_firm" and verdict(25) == "move"
    assert verdict(5, by_heart_rate=True) == "by_heart_rate"
    assert verdict(5, swap_key_for_easy=True) == "easy_instead"
    # Garmin's clock counts down: 30 h read 8 h ago is 22 h now
    later = snapshot.recovery_verdict({"recovery_hours": 30, "recovery_as_of": "2027-01-05T23:00:00.0", "hrv_last": 70}, plan, now)
    assert later["recovery_hours_now"] == 22.0 and later["verdict"] == "cap_firm"


def test_hrv_rule_needs_both_signals():
    plan = P.load(EXAMPLES[0])
    lo = plan["athlete"]["hrv_baseline_ms"][0]
    rest = plan["athlete"]["resting_hr"]
    trend = [{"date": "2027-01-%02d" % d, "last_night_avg_hrv_ms": lo - 6, "weekly_avg_hrv_ms": lo - 5} for d in range(1, 8)]
    high = {"days": [{"date": "2027-01-%02d" % d, "resting_hr_bpm": rest + 6} for d in range(5, 8)]}
    normal = {"days": [{"date": "2027-01-%02d" % d, "resting_hr_bpm": rest} for d in range(5, 8)]}
    today = dt.date(2027, 1, 7)
    assert snapshot.recovery_block(plan, {"hrv_trend": {"trend": trend}, "rhr": high}, today)["swap_key_for_easy"] is True
    only_hrv = snapshot.recovery_block(plan, {"hrv_trend": {"trend": trend}, "rhr": normal}, today)
    assert only_hrv["swap_key_for_easy"] is False and only_hrv["by_heart_rate"] is True


# ---------------------------------------------------------- per-second form

def records(drift):
    out, t = [], 0
    start = dt.datetime(2027, 1, 6, 6, 30)
    for rep in range(2):
        for i in range(120):                                           # jog
            out.append({"timestamp": (start + dt.timedelta(seconds=t)).isoformat(), "enhanced_speed": 2.6,
                        "heart_rate": 140, "cadence": 82, "fractional_cadence": 0.0, "stance_time": 265.0,
                        "vertical_ratio": 8.6, "step_length": 950.0})
            t += 1
        for i in range(480):                                           # 8-minute rep at steady speed
            late = drift and rep == 1 and i > 330
            out.append({"timestamp": (start + dt.timedelta(seconds=t)).isoformat(), "enhanced_speed": 4.1,
                        "heart_rate": 160 + i // 60, "cadence": 86 if late else 89, "fractional_cadence": 0.5,
                        "stance_time": 240.0 if late else 226.0, "vertical_ratio": 7.0 if late else 6.6,
                        "step_length": 1400.0})
            t += 1
    return out


def test_form_breakdown_late_in_a_rep_is_detected_while_pace_holds():
    recs = fitform.load_records.__globals__["_normalise"](records(drift=True))
    assert recs[200]["cadence"] == 179.0                               # per-leg cadence doubled
    out = fitform.analyse(recs)
    assert len(out["reps"]) == 2 and out["breakdown_reps"] == [2]
    assert 250 <= out["reps"][1]["breakdown_from_s"] <= 340
    clean = fitform.analyse(fitform.load_records.__globals__["_normalise"](records(drift=False)))
    assert clean["breakdown_reps"] == [] and "progress" in clean["lines"][0]


def test_fit_messages_shape_is_read():
    payload = {"messages": [{"type": "record", "fields": [
        {"name": "timestamp", "value": "2027-01-06T06:30:%02d" % i}, {"name": "enhanced_speed", "value": 3.0, "units": "m/s"},
        {"name": "cadence", "value": 87}, {"name": "fractional_cadence", "value": 0.5},
        {"name": "stance_time", "value": 250.0}]} for i in range(3)] + [{"type": "lap", "fields": []}]}
    recs = fitform.records_from_messages(payload)
    assert len(recs) == 3 and recs[2]["t"] == 2.0 and recs[0]["cadence"] == 175.0 and recs[0]["gct_ms"] == 250.0


def test_units_only_change_display():
    assert fmt_pace(300, "km") == "5:00/km" and fmt_pace(300, "mi") == "8:03/mi"
    km, _ = blockgen.build_block(spec("half", "km"))
    mi, _ = blockgen.build_block(spec("half", "mi"))
    assert km["bands"] == mi["bands"]                                  # stored metric either way


# ------------------------------------------------------- skill front matter

SKILLS = sorted(glob.glob(os.path.join(ROOT, "skills", "*", "SKILL.md")))


def front_matter(path):
    lines = open(path).read().split("\n")
    assert lines[0] == "---", "front matter must open on line 1"
    return lines[1:lines.index("---", 1)]


@pytest.mark.parametrize("path", SKILLS)
def test_skill_front_matter_is_valid(path):
    """GitHub and Claude both parse this as YAML. A bare ': ' inside a description breaks it,
    so descriptions are always written as double-quoted strings."""
    fields = dict(line.split(": ", 1) for line in front_matter(path))
    assert set(fields) == {"name", "description"}
    assert fields["name"] == os.path.basename(os.path.dirname(path))
    assert fields["description"].startswith('"') and json.loads(fields["description"])
    yaml = pytest.importorskip("yaml")
    parsed = yaml.safe_load("\n".join(front_matter(path)))
    assert parsed["name"] == fields["name"] and parsed["description"] == json.loads(fields["description"])
