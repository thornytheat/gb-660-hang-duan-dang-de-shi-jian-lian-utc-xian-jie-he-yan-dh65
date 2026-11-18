"""在整条 UTC 航链上计算衔接等待，并汇总候选链上的判定。

判定纪律：
- 等待时间只用具体 UTC 时刻相减，候选之间不许混用；
- 所有候选链给出同一结论时才下确定判定（DETERMINED）；
- 候选之间结论分叉时挂起（PENDING_CONFIRMATION），先放行能确定的连接，
  分叉的连接等航司确认，绝不把赶不上的航班判成可转。
"""
from datetime import datetime

from .rules import required_minutes, connection_result
from .windows import waiting_minutes

DEFAULT_MAX_MINUTES = 720


def parse_utc(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def connection_key(inbound: dict, outbound: dict) -> str:
    return f"{inbound['flight_no']}->{outbound['flight_no']}@{inbound['destination']}"


def assess_connection(inbound: dict, outbound: dict, maximum: int = DEFAULT_MAX_MINUTES) -> dict:
    airport = inbound["destination"]
    if outbound["origin"] != airport:
        return {
            "connection_key": connection_key(inbound, outbound),
            "airport": airport,
            "inbound_flight": inbound["flight_no"],
            "outbound_flight": outbound["flight_no"],
            "wait_minutes": None,
            "required_minutes": None,
            "status": "CHAIN_BROKEN",
        }
    wait = waiting_minutes(parse_utc(inbound["arrival_utc"]), parse_utc(outbound["departure_utc"]))
    required = required_minutes(airport, inbound["destination_terminal"], outbound["origin_terminal"])
    result = connection_result(wait, required, maximum)
    result.update(
        {
            "connection_key": connection_key(inbound, outbound),
            "airport": airport,
            "inbound_flight": inbound["flight_no"],
            "outbound_flight": outbound["flight_no"],
            "inbound_fold": inbound["arrival_fold"],
            "outbound_fold": outbound["departure_fold"],
        }
    )
    return result


def check_chains(chains: list[dict], maximum: int = DEFAULT_MAX_MINUTES) -> list[dict]:
    """对每条候选 UTC 航链逐段评估，再按连接聚合候选判定。"""
    grouped: dict[str, list[dict]] = {}
    order: list[str] = []
    for chain in chains:
        legs = chain["legs"]
        for index in range(len(legs) - 1):
            assessment = assess_connection(legs[index], legs[index + 1], maximum)
            assessment["chain_id"] = chain["chain_id"]
            key = assessment["connection_key"]
            if key not in grouped:
                grouped[key] = []
                order.append(key)
            grouped[key].append(assessment)

    connections = []
    for key in order:
        candidates = grouped[key]
        verdicts = sorted({item["status"] for item in candidates})
        waits = [item["wait_minutes"] for item in candidates if item["wait_minutes"] is not None]
        first = candidates[0]
        determined = len(verdicts) == 1
        connections.append(
            {
                "connection_key": key,
                "airport": first["airport"],
                "inbound_flight": first["inbound_flight"],
                "outbound_flight": first["outbound_flight"],
                "decision": "DETERMINED" if determined else "PENDING_CONFIRMATION",
                "status": verdicts[0] if determined else "PENDING_CONFIRMATION",
                "verdicts": verdicts,
                "wait_minutes": waits[0] if determined and waits else None,
                "wait_minutes_min": min(waits) if waits else None,
                "wait_minutes_max": max(waits) if waits else None,
                "required_minutes": next((item["required_minutes"] for item in candidates if item["required_minutes"] is not None), None),
                "candidate_count": len(candidates),
                "candidates": candidates,
            }
        )
    return connections
