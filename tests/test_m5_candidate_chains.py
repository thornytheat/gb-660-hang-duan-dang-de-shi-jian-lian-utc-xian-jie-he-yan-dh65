"""DST 重叠驱动的候选 UTC 航链与整链衔接判定测试。"""
import pytest

from app.modules.m4_itinerary.candidates import build_chains, leg_candidates
from app.modules.m5_connections.assessment import check_chains
from app.modules.m5_connections.demo_chain import DEMO_ROWS, demo_bundle


def test_overlap_arrival_produces_two_chain_candidates():
    bundle = build_chains(DEMO_ROWS)
    # BA185 到达落在回拨重叠小时：一个当地时刻，两条候选 UTC 航链。
    assert bundle["candidate_count"] == 2
    ambiguous = [leg for chain in bundle["chains"] for leg in chain["legs"] if leg["flight_no"] == "BA185"]
    assert {leg["arrival_fold"] for leg in ambiguous} == {0, 1}


def test_nonexistent_local_time_quarantines_leg():
    rows = [{
        "flight_no": "BA178", "flight_date": "2026-03-08", "origin": "JFK", "destination": "LHR",
        "departure_local": "2026-03-08T02:30", "arrival_local": "2026-03-08T14:00",
        "departure_fold": "", "arrival_fold": "",
    }]
    bundle = build_chains(rows)
    assert bundle["candidate_count"] == 0
    assert bundle["quarantined"][0]["reason_code"] == "NONEXISTENT_LOCAL_TIME"


def test_unknown_airport_quarantines_leg():
    options, evidence = leg_candidates({
        "flight_no": "CA981", "flight_date": "2026-11-17", "origin": "PEK", "destination": "XXX",
        "departure_local": "2026-11-17T12:00", "arrival_local": "2026-11-17T13:00",
    })
    assert not options and evidence["reason_code"] == "UNKNOWN_REFERENCE"


def test_diverging_candidates_are_pending_not_valid():
    # 60 与 120 分钟跨 90 分钟 MCT：不能把赶不上的航班判成可转。
    connections = check_chains(demo_bundle()["chains"])
    by_key = {item["connection_key"]: item for item in connections}
    pending = by_key["BA185->BA178@JFK"]
    assert pending["decision"] == "PENDING_CONFIRMATION"
    assert pending["status"] == "PENDING_CONFIRMATION"
    assert set(pending["verdicts"]) == {"TOO_SHORT", "VALID"}
    assert (pending["wait_minutes_min"], pending["wait_minutes_max"]) == (60, 120)


def test_unanimous_candidates_are_determined():
    connections = check_chains(demo_bundle()["chains"])
    by_key = {item["connection_key"]: item for item in connections}
    determined = by_key["BA178->BA168@LHR"]
    assert determined["decision"] == "DETERMINED"
    assert determined["status"] == "VALID" and determined["wait_minutes"] == 330


def test_each_candidate_waits_are_computed_on_full_utc_chain():
    # 等待时间必须来自具体候选链的 UTC 差值，不允许跨候选混用。
    connections = check_chains(demo_bundle()["chains"])
    pending = next(item for item in connections if item["connection_key"] == "BA185->BA178@JFK")
    waits = sorted(item["wait_minutes"] for item in pending["candidates"])
    assert waits == [60, 120]


def test_broken_chain_marked_not_silently_connected():
    bundle = build_chains([
        {"flight_no": "A1", "flight_date": "2026-11-16", "origin": "PVG", "destination": "JFK",
         "departure_local": "2026-11-16T09:00", "arrival_local": "2026-11-16T10:30"},
        {"flight_no": "B2", "flight_date": "2026-11-16", "origin": "LHR", "destination": "PVG",
         "departure_local": "2026-11-16T20:00", "arrival_local": "2026-11-17T16:00"},
    ])
    connections = check_chains(bundle["chains"])
    assert connections[0]["status"] == "CHAIN_BROKEN"
