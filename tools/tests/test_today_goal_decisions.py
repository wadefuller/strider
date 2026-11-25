"""Today's call, the goal realism check, and the decisions log."""
import copy
import datetime as dt
import os

import pytest

from strider import blockgen, decisions, paces, snapshot, today
from strider import plan as P

HERE = os.path.dirname(os.path.abspath(__file__))
EX = os.path.join(HERE, "..", "..", "examples", "half-marathon")
NOW = dt.datetime(2027, 3, 26, 8, 0)          # the example's own "now"


@pytest.fixture
def ex():
    plan = P.load(os.path.join(EX, "plan.json"))
    raw, fetched = snapshot.load_raw(os.path.join(EX, "raw"))
    return plan, raw, fetched


def fresh(fetched, now=NOW):
    return dict((k, (now - dt.timedelta(hours=1)).isoformat()) for k in fetched)


def key_day(plan):
    return next(d for _, d in P.all_days(plan) if d["kind"] == "key" and d["status"] == "planned")


def at(day, hour=7):
    return dt.datetime.fromisoformat(day["date"] + "T%02d:00:00" % hour)


# ----------------------------------------------------------------- today

def test_example_morning_is_go_with_four_signals(ex):
    plan, raw, fetched = ex
    c = today.call(plan, raw, fetched, NOW)
    assert c["verdict"] == "go" and not c["stale"]
    assert set(c["signals"]) == set(today.SIGNALS) and c["missing_signals"] == []


def test_stale_data_is_unknown_not_yesterdays_verdict(ex):
    plan, raw, fetched = ex
    c = today.call(plan, raw, fetched, NOW + dt.timedelta(days=2))
    assert c["stale"] and c["verdict"] == "unknown"
    assert "hours old" in c["reasons"][0]


def test_thin_data_downgrades_go_to_cap_firm(ex):
    plan, raw, fetched = ex
    day = key_day(plan)
    thin = copy.deepcopy(raw)
    for k in ("sleep", "rhr", "readiness"):
        thin.pop(k, None)
    c = today.call(plan, thin, fresh(fetched, at(day)), at(day))
    assert c["verdict"] == "cap_firm" and c["verdict_applies"]
    assert any("thin data" in r for r in c["reasons"])
    assert sorted(c["missing_signals"]) == ["readiness", "rhr", "sleep"]


def test_hrv_and_rhr_together_swap_a_key_session_for_easy(ex):
    plan, raw, fetched = ex
    day = key_day(plan)
    now = at(day)
    bad = copy.deepcopy(raw)
    base = plan["athlete"]["hrv_baseline_ms"][0]
    for r in bad["hrv_trend"]["trend"]:
        r["weekly_avg_hrv_ms"] = base - 6
        r["last_night_avg_hrv_ms"] = base - 6
    bad["rhr"] = {"days": [{"date": (now.date() - dt.timedelta(days=i)).isoformat(),
                            "resting_hr_bpm": plan["athlete"]["resting_hr"] + 7} for i in (2, 1, 0)]}
    c = today.call(plan, bad, fresh(fetched, now), now)
    assert c["verdict"] == "easy_instead" and c["session"]["kind"] == "key"
    assert c["action"] == today.ACTIONS["easy_instead"]


def test_easy_day_is_not_governed_by_a_go(ex):
    plan, raw, fetched = ex
    c = today.call(plan, raw, fetched, NOW)
    assert c["session"]["kind"] == "easy" and not c["verdict_applies"]


def test_race_is_never_moved(ex):
    plan, raw, fetched = ex
    race = next(d for _, d in P.all_days(plan) if d["kind"] == "race")
    hot = copy.deepcopy(raw)
    hot["recovery_time"] = {"remaining_hours": 40, "as_of": race["date"] + "T06:00:00"}
    c = today.call(plan, hot, fresh(fetched, at(race)), at(race))
    assert c["verdict"] == "move" and not c["verdict_applies"] and "Race day" in c["action"]


def test_cli_exit_code_three_when_stale(capsys):
    import coach
    args = [os.path.join(EX, "plan.json"), "--raw", os.path.join(EX, "raw")]
    assert coach.main(["today"] + args + ["--now", "2027-03-26T08:00:00"]) == 0
    assert coach.main(["today"] + args + ["--now", "2027-03-29T08:00:00"]) == 3
    assert "UNKNOWN" in capsys.readouterr().out


# ----------------------------------------------------------------- goal realism

@pytest.mark.parametrize("distance,goal,recent,verdict", [
    ("half", "1:30:00", ("10k", "48:30"), "unlikely"),      # 16% faster than the 10k says
    ("half", "1:44:30", ("10k", "48:30"), "realistic"),
    ("half", "1:42:30", ("10k", "48:30"), "stretch"),
    ("half", "1:47:00", ("10k", "48:30"), "within_reach"),
    ("half", "1:58:00", ("10k", "48:30"), "conservative"),
    ("5k", "21:00", ("10k", "45:00"), "stretch"),
    ("5k", "21:40", ("10k", "45:00"), "within_reach"),
])
def test_goal_verdicts(distance, goal, recent, verdict):
    from strider.units import parse_clock
    r = paces.goal_realism(distance, parse_clock(goal), 10, {"distance": recent[0], "time_s": parse_clock(recent[1])})
    assert r["verdict"] == verdict, r["summary"]


def test_unrealistic_goal_comes_with_three_options():
    r = paces.goal_realism("half", 5400, 10, {"distance": "10k", "time_s": 2910})
    assert [o["id"] for o in r["options"]] == ["softer_goal", "next_block", "more_time"]
    soft = r["options"][0]["goal_time_s"]
    assert 5400 < soft < r["predicted_s"]


def test_marathon_uses_the_typical_case_not_riegel_best_case():
    r = paces.goal_realism("marathon", 12600, 16, {"distance": "half", "time_s": 6000})
    assert r["predicted_s"] - paces.predict("marathon", {"distance": "half", "time_s": 6000})["best_case_s"] == 600
    assert "Vickers" in r["summary"]


def test_block_gain_is_capped():
    r = paces.goal_realism("10k", 2400, 40, threshold_pace=250)
    assert r["block_gain_pct"] == paces.BLOCK_GAIN_CAP * 100


def test_no_basis_is_unknown():
    assert paces.goal_realism("10k", 2400, 8)["verdict"] == "unknown"


def test_block_records_realism_and_notes_an_unlikely_goal():
    s = {"units": "km", "goal_time_s": 5400, "threshold_pace_s_per_km": 300,
         "race": {"name": "Test", "date": "2027-10-17", "start": "08:00", "tz": "Etc/UTC", "distance": "half"},
         "athlete": {"lthr": 165, "max_hr": 184, "max_hr_verified": False, "watch_distance_factor": 1.0},
         "current_weekly_m": 40000, "longest_recent_m": 14000, "recent_race": {"distance": "10k", "time_s": 2910},
         "run_days": ["Tue", "Wed", "Fri", "Sun"], "key_day": "Wed", "long_day": "Sun", "weeks": 10}
    plan, notes = blockgen.build_block(s)
    assert plan["goal"]["realism"]["verdict"] == "unlikely"
    assert sum(1 for n in notes if n.startswith("option: ")) == 3
    assert P.validate(plan)[0] == []


# ----------------------------------------------------------------- decisions

def test_decisions_round_trip_and_expiry(tmp_path):
    path = str(tmp_path / "decisions.md")
    decisions.add(path, date="2027-02-11", kind="correction", what="Loop reads long", why="mapped it")
    decisions.add(path, date="2027-02-14", kind="exception", what="No key sessions", why="trip",
                  applies="until 2027-02-20")
    decisions.add(path, date="2027-02-15", kind="override", what="Ran it anyway", why="felt fine", applies="once")
    entries = decisions.parse(open(path).read())
    assert decisions.problems(entries) == []
    assert [e["kind"] for e in decisions.active(entries, "2027-02-15")] == ["correction", "exception", "override"]
    assert [e["kind"] for e in decisions.active(entries, "2027-02-16")] == ["correction", "exception"]
    assert [e["kind"] for e in decisions.active(entries, "2027-02-21")] == ["correction"]
    assert decisions.active(entries, "2027-02-10") == []


def test_a_later_entry_replaces_an_earlier_one(tmp_path):
    path = str(tmp_path / "decisions.md")
    decisions.add(path, date="2027-02-01", kind="preference", what="Long run on Sunday", why="family")
    decisions.add(path, date="2027-03-01", kind="preference", what="Long run on Saturday", why="new job",
                  replaces="2027-02-01")
    live = decisions.active(decisions.parse(open(path).read()), "2027-03-02")
    assert [e["what"] for e in live] == ["Long run on Saturday"]


def test_problems_are_reported():
    text = "## 2027-02-01 · vibe\n- Why: none\n- Applies: forever\n- Source: friend\n"
    bad = decisions.problems(decisions.parse(text))
    assert len(bad) == 4


def test_bad_input_is_refused(tmp_path):
    with pytest.raises(ValueError):
        decisions.add(str(tmp_path / "d.md"), date="2027-02-01", kind="note", what="x", why="y", applies="sometimes")


def test_today_lists_active_decisions(tmp_path, capsys):
    import coach
    path = str(tmp_path / "decisions.md")
    decisions.add(path, date="2027-03-01", kind="correction", what="Loop reads long", why="mapped it")
    coach.main(["today", os.path.join(EX, "plan.json"), "--raw", os.path.join(EX, "raw"),
                "--now", "2027-03-26T08:00:00", "--decisions", path])
    assert "Loop reads long" in capsys.readouterr().out
