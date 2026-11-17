"""Lap analysis, data-quality checks, session judging and the decision rule."""
import copy
import itertools
import json
import os

import pytest

from strider import judge, laps, match
from strider import plan as P

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..", "..")


def fixture(name):
    with open(os.path.join(HERE, "fixtures", name)) as fh:
        return json.load(fh)["laps"]


def lap(dist, dur, hr=150, power=250, kind="", gain=1.0, loss=1.0):
    return {"distance_meters": dist, "duration_seconds": dur, "avg_hr_bpm": hr, "avg_power_watts": power,
            "avg_cadence": 172.0, "intensity_type": kind, "elevation_gain_meters": gain, "elevation_loss_meters": loss}


@pytest.fixture
def plan():
    return P.load(os.path.join(ROOT, "examples", "10k", "plan.json"))


def key_day(pace=(238, 244), cap=168, reps=3):
    work = {"type": "work", "distance_m": 2000, "pace_s_per_km": list(pace), "hr_cap": cap}
    return {"date": "2027-01-06", "kind": "key", "title": "3 x 2 km", "status": "planned", "distance_m": 11000,
            "steps": [{"type": "warmup", "distance_m": 2000},
                      {"type": "repeat", "count": reps, "steps": [work, {"type": "recovery", "time_s": 120}]},
                      {"type": "cooldown", "distance_m": 1500}]}


# ---------------------------------------------------------------- lap analysis

def test_reps_are_joined_and_warmup_recovery_cooldown_removed():
    s = laps.summarise(fixture("key_3x2km_labelled.json"))
    assert [r["distance_m"] for r in s["reps"]] == [2000, 2000, 2000]
    assert [r["lap_indexes"] for r in s["reps"]] == [[2, 3], [6, 7], [9, 10]]   # 10 m button lap ignored
    assert s["work_distance_m"] == 6000


def test_session_is_never_the_whole_run_average():
    lap_list = fixture("key_3x2km_labelled.json")
    whole = laps.whole_run(lap_list)
    s = laps.summarise(lap_list)
    assert s["pace_s_per_km"] == pytest.approx(240, abs=1)
    assert whole["pace_s_per_km"] > s["pace_s_per_km"] + 25      # the average hides the session


def test_jog_hr_and_final_jog_only_when_labelled():
    lap_list = fixture("key_3x2km_labelled.json")
    assert laps.summarise(lap_list)["jog_hr"] == [141, 144]       # cool-down after rep 3 is not a jog
    lap_list[-1]["intensity_type"] = "RECOVERY"
    assert len(laps.summarise(lap_list)["jog_hr"]) == 3


def test_power_fade_is_first_lap_against_last_lap_of_a_rep():
    s = laps.summarise(fixture("key_3x2km_labelled.json"))
    assert s["reps"][2]["fade_pct"] == pytest.approx((302 - 288) / 302 * 100, abs=0.1)
    assert s["reps"][0]["fade_pct"] < 1


def test_unlabelled_laps_fall_back_to_effort():
    lap_list = [lap(1000, 330), lap(1600, 400), lap(400, 160), lap(1600, 398), lap(400, 165), lap(1000, 340)]
    s = laps.summarise(lap_list)
    assert len(s["reps"]) == 2 and s["reps"][0]["distance_m"] == 1600


def test_cold_start_hr_lag_is_flagged_and_excluded():
    lap_list = fixture("key_3x2km_labelled.json")
    for i in (2, 3):
        lap_list[i]["avg_hr_bpm"] = 140                         # rep 1 reads 20+ beats low
    s = laps.summarise(lap_list)
    assert s["flags"][0]["code"] == "hr_lag" and s["reps"][0]["hr_reliable"] is False
    assert s["hr"] >= 164                                       # session HR ignores the lagging rep
    clean = laps.summarise(fixture("key_3x2km_labelled.json"))
    assert s["efficiency"] < clean["efficiency"] + 0.05         # not inflated by the low reading


def test_hill_inflated_power_is_not_judged():
    lap_list = fixture("key_3x2km_labelled.json")
    lap_list[6]["elevation_gain_meters"] = 40
    s = laps.summarise(lap_list)
    assert [f["code"] for f in s["flags"]] == ["hill_power"]
    assert s["reps"][1]["power_reliable"] is False and s["reps"][0]["power_reliable"] is True


def test_implausible_altimeter_on_a_track_switches_off_power_and_efficiency():
    s = laps.summarise(fixture("track_bad_altimeter.json"), terrain="track")
    assert s["flags"][0]["code"] == "altimeter_implausible"
    assert s["efficiency"] is None and s["power_reliable"] is False
    assert not any(f["code"] == "hill_power" for f in s["flags"])      # the "hills" are sensor error
    assert laps.summarise(fixture("track_bad_altimeter.json"), terrain="hilly")["efficiency"] is not None


def test_watch_distance_factor_slows_the_pace():
    lap_list = fixture("key_3x2km_labelled.json")
    assert laps.summarise(lap_list, 1.01)["pace_s_per_km"] == pytest.approx(laps.summarise(lap_list)["pace_s_per_km"] * 1.01, abs=0.1)


def test_finish_segment_from_laps_and_unknown_for_a_single_lap():
    seg = laps.tail_segment(fixture("long_16km_steady_finish.json"), 4000)
    assert seg["pace_s_per_km"] == pytest.approx(282, abs=0.5) and seg["laps_used"] == 4
    assert laps.tail_segment([lap(16000, 5000)], 4000) is None


def test_typed_splits_recover_run_segments():
    typed = {"splits": [{"type": "RWD_RUN", "distance": 9000, "duration": 2900, "averageHR": 140},
                        {"type": "RWD_STAND", "duration": 0}, {"type": "INTERVAL_ACTIVE", "distance": 12000, "duration": 3800},
                        {"type": "RWD_RUN", "distance": 3000, "duration": 840, "averageHR": 158}]}
    segs = laps.typed_run_segments(typed)
    assert [s["distance_meters"] for s in segs] == [9000, 3000]
    assert laps.tail_segment(segs, 3000)["pace_s_per_km"] == pytest.approx(280)


def test_form_drift_needs_matching_pace():
    rows = [{"n": 1, "speed_mps": 4.1, "cadence": 178, "gct_ms": 226, "vert_ratio_pct": 6.5, "stride_cm": 138},
            {"n": 2, "speed_mps": 4.1, "cadence": 173.5, "gct_ms": 237, "vert_ratio_pct": 6.9, "stride_cm": 141}]
    assert laps.form_drift(rows)["drift"] is True
    rows[1]["speed_mps"] = 3.8                                  # slowed down: that is fade, not form drift
    assert laps.form_drift(rows)["drift"] is False


# -------------------------------------------------------------------- judging

def test_verdicts(plan):
    s = laps.summarise(fixture("key_3x2km_labelled.json"))
    assert judge.judge_key(s, key_day(), plan)["verdict"] == "on_target"
    fast = judge.judge_key(s, key_day(pace=(250, 256)), plan)
    assert fast["verdict"] == "faster_than_prescribed" and fast["over_prescribed"]
    assert judge.judge_key(s, key_day(pace=(225, 230)), plan)["verdict"] == "slower_than_prescribed"
    over = judge.judge_key(s, key_day(cap=163), plan)
    assert over["verdict"] == "over_hr_cap" and over["hr_over_reps"] == [2, 3]


def test_lagging_rep_cannot_break_or_pass_the_hr_cap(plan):
    lap_list = fixture("key_3x2km_labelled.json")
    for i in (2, 3):
        lap_list[i]["avg_hr_bpm"] = 140
    j = judge.judge_key(laps.summarise(lap_list), key_day(), plan)
    assert j["reps"][0]["hr_status"] == "excluded"


def test_uneven_session(plan):
    lap_list = fixture("key_3x2km_labelled.json")
    for i in (9, 10):
        lap_list[i]["duration_seconds"] = 262
    assert judge.judge_key(laps.summarise(lap_list), key_day(), plan)["verdict"] == "uneven"


def test_long_run_finish_and_unknown_structure(plan):
    day = {"date": "2027-01-10", "kind": "long", "title": "Long", "status": "planned", "distance_m": 16000, "hr_cap": 150,
           "steps": [{"type": "easy", "distance_m": 12000, "hr_cap": 150},
                     {"type": "steady", "distance_m": 4000, "pace_s_per_km": [262, 272], "hr_cap": 160}]}
    j = judge.judge_long(fixture("long_16km_steady_finish.json"), day, plan, 1.0)
    assert j["verdict"] == "slower_than_prescribed" and j["finish"]["hr_over"] is False
    one = judge.judge_long([lap(16000, 5000)], day, plan, 1.0)
    assert one["verdict"] == "unknown" and one["flags"][0]["code"] == "structure_unknown"


def test_streak_counts_consecutive_recent_sessions():
    j = lambda over: {"verdict": "x", "over_prescribed": over}
    assert judge.over_prescription_streak([j(True), j(False), j(True), j(True)]) == 2
    assert judge.over_prescription_streak([j(True), j(False)]) == 0
    assert judge.over_prescription_streak([j(True), {"verdict": "unknown", "over_prescribed": False}]) == 1


# -------------------------------------------------------------- decision rule

def summary(paces, hrs):
    return {"reps": [{"pace_s_per_km": p, "hr": h, "hr_reliable": True} for p, h in zip(paces, hrs)]}


def test_decision_tiers_partition_every_outcome(plan):
    decision = plan["goal"]["decision"]
    ids = [t["id"] for t in decision["tiers"]]
    for p1, p2, h1, h2 in itertools.product(range(225, 270, 3), range(225, 270, 3), range(160, 186, 3), range(160, 186, 3)):
        r = judge.evaluate_decision(decision, summary([p1, p2], [h1, h2]))
        assert r["applied_tier"] in ids and r["needs_runner_confirmation"] is True


def test_mixed_result_lands_in_the_slower_tier(plan):
    decision = plan["goal"]["decision"]
    stretch, goal = decision["tiers"][0]["when"], decision["tiers"][1]["when"]
    r = judge.evaluate_decision(decision, summary(
        [stretch["slowest_rep_pace_max_s_per_km"] - 4, goal["slowest_rep_pace_max_s_per_km"] - 3], [165, 166]))
    assert r["qualified_tier"] == "goal"


def test_borderline_result_defaults_to_the_slower_tier(plan):
    decision = plan["goal"]["decision"]
    limit = decision["tiers"][1]["when"]["slowest_rep_pace_max_s_per_km"]
    r = judge.evaluate_decision(decision, summary([limit - 0.5, limit - 0.5], [165, 165]))
    assert r["qualified_tier"] == "goal" and r["borderline"] and r["applied_tier"] == "conservative"
    clear = judge.evaluate_decision(decision, summary([limit - 3, limit - 3], [165, 165]))
    assert clear["applied_tier"] == "goal" and not clear["borderline"]


def test_validator_rejects_a_rule_that_leaves_outcomes_uncovered(plan):
    bad = copy.deepcopy(plan)
    bad["goal"]["decision"]["tiers"][-1]["when"] = {"highest_rep_hr_max": 180}
    errors, _ = P.validate(bad)
    assert any("otherwise" in e for e in errors)


# ------------------------------------------------------------------- matching

def act(i, date, dist, kind="running"):
    return {"id": i, "type": kind, "start_time": date + " 06:30:00", "distance_meters": dist, "duration_seconds": dist / 3.0}


def test_match_by_type_not_date(plan):
    import datetime as dt
    p = copy.deepcopy(plan)
    week = p["weeks"][0]
    for day in week["days"]:
        day["status"] = "planned"
    key = [d for d in week["days"] if d["kind"] == "key"][0]
    easy = [d for d in week["days"] if d["kind"] == "easy"][1]
    assert (P.d(easy["date"]) - P.d(key["date"])).days == 1
    # the runner swapped them: easy run on the key day, workout a day late
    acts = [act(1, key["date"], easy["distance_m"]), act(2, easy["date"], key["distance_m"])]
    splits = {"1": [lap(1000, 330, kind="ACTIVE")] * 8, "2": fixture("key_3x2km_labelled.json")}
    got, extras = match.match(p, acts, splits, P.d(easy["date"]) + dt.timedelta(days=1))
    assert got[key["date"]]["status"] == "moved" and got[key["date"]]["activity_id"] == 2
    assert got[easy["date"]]["activity_id"] == 1


def test_missed_and_fragments(plan):
    import datetime as dt
    p = copy.deepcopy(plan)
    week = p["weeks"][0]
    for day in week["days"]:
        day["status"] = "planned"
    first = week["days"][0]
    key = [d for d in week["days"] if d["kind"] == "key"][0]
    acts = [act(1, key["date"], 2000), act(2, key["date"], 7000), act(3, key["date"], 1500)]   # warm-up, session, cool-down
    splits = {"2": fixture("key_3x2km_labelled.json")}
    got, _ = match.match(p, acts, splits, P.d(week["start"]) + dt.timedelta(days=6))
    assert got[first["date"]]["status"] == "missed"
    assert got[key["date"]]["activity_id"] == 2 and got[key["date"]]["distance_m"] == 10500
