from .builder import build_leg
from .validate import validate_chain
from .candidates import build_chains
from .demo_rows import DEMO_ROWS


def run() -> dict:
    leg = build_leg({"flight_no": "MU5101", "origin": "PVG", "destination": "JFK", "departure_local": "2026-11-16T09:00", "arrival_local": "2026-11-16T10:30"})
    return {**leg, "chain_valid": validate_chain([leg])}


def run_chains(rows: list[dict] | None = None) -> dict:
    """构建全部候选 UTC 航链：当地时刻有几种解释，就有几条候选链。"""
    return build_chains(rows or DEMO_ROWS)


def demo() -> dict:
    return run()
