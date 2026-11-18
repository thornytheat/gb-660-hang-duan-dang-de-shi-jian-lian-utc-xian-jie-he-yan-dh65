"""演示航链：覆盖 DST 重叠、待确认与可先确定的连接。

- BA185 LHR→JFK：到达 JFK 落在 2026-11-01 回拨重叠小时 01:30，两个 UTC 候选；
- BA178 JFK→LHR：02:30 出发（回拨后唯一），两个候选等待 120/60 分钟，
  跨 90 分钟 MCT 分叉 → PENDING_CONFIRMATION；
- BA168 LHR→PVG：两端均唯一，可先给出 DETERMINED/VALID。
"""
from app.modules.m4_itinerary.candidates import build_chains

DEMO_ROWS = [
    {
        "flight_no": "BA185", "flight_date": "2026-10-31", "origin": "LHR", "destination": "JFK",
        "departure_local": "2026-10-31T20:00", "arrival_local": "2026-11-01T01:30",
        "departure_fold": "", "arrival_fold": "",
    },
    {
        "flight_no": "BA178", "flight_date": "2026-11-01", "origin": "JFK", "destination": "LHR",
        "departure_local": "2026-11-01T02:30", "arrival_local": "2026-11-01T15:00",
        "departure_fold": "", "arrival_fold": "",
    },
    {
        "flight_no": "BA168", "flight_date": "2026-11-01", "origin": "LHR", "destination": "PVG",
        "departure_local": "2026-11-01T20:30", "arrival_local": "2026-11-02T16:30",
        "departure_fold": "", "arrival_fold": "",
    },
]


def demo_bundle() -> dict:
    return build_chains(DEMO_ROWS)
