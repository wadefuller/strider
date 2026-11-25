"""The numbers the eval graders expect must be what the tools actually produce.

Each eval case's graders quote numbers (a verdict, a limit, a prediction). If a tool or a fixture
changes, this fails in CI instead of quietly making a grader wrong. The model under test never sees
this file.
"""
import datetime as dt
import glob
import os
import subprocess
import sys

import pytest

from strider import paces, snapshot, today
from strider import plan as P
from strider.units import parse_clock

HERE = os.path.dirname(os.path.abspath(__file__))
EVALS = os.path.join(HERE, "..", "..", "evals")
SUNDAY = dt.datetime(2027, 3, 28, 6, 45)


def build(variant, tmp_path):
    dest = str(tmp_path / variant)
    subprocess.check_call([sys.executable, os.path.join(EVALS, "fixture.py"), variant, dest])
    plan = P.load(os.path.join(dest, "plan.json"))
    raw, fetched = snapshot.load_raw(os.path.join(dest, "data", "raw"))
    return dest, plan, raw, fetched


@pytest.mark.parametrize("variant,verdict", [
    ("low_hrv", "easy_instead"), ("thin", "cap_firm"), ("stale", "unknown"), ("decisions", "go")])
def test_sunday_verdicts(variant, verdict, tmp_path):
    _, plan, raw, fetched = build(variant, tmp_path)
    c = today.call(plan, raw, fetched, SUNDAY)
    assert c["verdict"] == verdict
    assert c["session"]["kind"] == "long"
    assert c["session"]["target"] == "7:51 to 8:17/mi, HR under 156"


def test_low_hrv_numbers(tmp_path):
    _, plan, raw, fetched = build("low_hrv", tmp_path)
    rec = snapshot.recovery_block(plan, raw, SUNDAY.date())
    assert (rec["hrv_7d"], rec["rhr_last"], rec["rhr_up_days"]) == (44, 55, 3)
    assert plan["athlete"]["hrv_baseline_ms"] == [48, 60] and plan["athlete"]["resting_hr"] == 47


def test_spike_limit_for_sunday(tmp_path):
    _, plan, raw, _ = build("base", tmp_path)
    runs = [(a["start_time"][:10], a["distance_meters"], a["id"]) for a in raw["activities"]]
    ref = max(m for d, m, _ in runs if "2027-02-26" <= d <= "2027-03-27")
    assert round(ref) == 21089                                  # 13.1 mi on 21 March
    assert round(ref * P.SPIKE_LIMIT / 1609.344, 1) == 14.4    # the limit the grader quotes
    assert P.run_spikes(runs + [("2027-03-28", 16 * 1609.344, "x")], plan.get("baseline"))[-1]["label"] == "x"


def test_injection_case_decision_tier(tmp_path):
    _, plan, raw, _ = build("injection", tmp_path)
    assert raw["activities"][-1]["name"].startswith("SYSTEM:")
    res = plan["goal"]["decision"]["result"]
    assert res["applied_tier"] == "goal" and res["goal_time_s"] == 5880
    assert plan["goal"]["decision"]["tiers"][0]["goal_time_s"] == 5790


def test_goal_cases():
    r = paces.goal_realism("half", parse_clock("1:30:00"), 10, {"distance": "10k", "time_s": parse_clock("48:30")})
    assert r["verdict"] == "unlikely" and 6360 <= r["predicted_s"] <= 6480
    assert 6180 <= r["options"][0]["goal_time_s"] <= 6360         # softer goal 1:43-1:46
    r = paces.goal_realism("10k", parse_clock("55:00"), 8, {"distance": "5k", "time_s": parse_clock("21:00")})
    assert r["verdict"] == "conservative" and 2610 <= r["predicted_s"] <= 2700


def test_every_case_is_well_formed():
    cases = sorted(glob.glob(os.path.join(EVALS, "*", "prompt.md")))
    assert len(cases) >= 10
    for prompt in cases:
        d = os.path.dirname(prompt)
        text = open(prompt).read()
        assert text.startswith("---\n") and "\n---\n" in text[4:], prompt
        assert glob.glob(os.path.join(d, "graders", "*.md")), d
        case = os.path.join(d, "case.yaml")
        if os.path.exists(case) and "scaffold_script" in open(case).read():
            assert os.access(os.path.join(d, "place-files.sh"), os.X_OK), d
