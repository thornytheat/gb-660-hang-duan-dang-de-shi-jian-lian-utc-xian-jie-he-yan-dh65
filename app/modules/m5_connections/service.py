"""衔接判定服务：候选链判定、航司确认、晚到失效重算。

确认分两类：
- fold：航司确认 DST 重叠当地时刻采用哪个解释，消除候选链；
- late_arrival：航司晚到确认新到达 UTC，旧判定立即失效并按新时刻重算。
同一条确认重跑（同 run、同类型、同航段、同负载哈希）幂等，不新增确认也不新增判定。
"""
from hashlib import sha256
from json import dumps

from app import store
from app.manifest import run_id
from .assessment import check_chains, parse_utc
from .demo_chain import demo_bundle
from .rules import required_minutes, connection_result
from .windows import waiting_minutes

DEMO_PAYLOAD = b"flightclock-connections-demo"
DEFAULT_MAX_MINUTES = 720


def _determination_id(run: str, key: str, round_no: int) -> str:
    return f"{run}|{key}|r{round_no}"


def _persist(run: str, connections: list[dict]) -> int:
    store.replace_determinations(run, [item["connection_key"] for item in connections])
    round_no = _next_round(run)
    added = 0
    for item in connections:
        record = {
            "determination_id": _determination_id(run, item["connection_key"], round_no),
            "run_id": run,
            "connection_key": item["connection_key"],
            "decision": item["decision"],
            "status": item["status"],
            "wait_minutes": item["wait_minutes"],
            "required_minutes": item["required_minutes"],
        }
        added += int(store.save_determination(record))
    return added


def _next_round(run: str) -> int:
    existing = store.list_determinations(run, include_superseded=True)
    rounds = [int(item["determination_id"].rsplit("r", 1)[1]) for item in existing if "|r" in item["determination_id"]]
    return (max(rounds) + 1) if rounds else 1


def check_demo() -> dict:
    return check_bundle(demo_bundle(), DEMO_PAYLOAD)


def check_bundle(bundle: dict, payload: bytes) -> dict:
    run = run_id(payload)
    connections = check_chains(bundle["chains"], DEFAULT_MAX_MINUTES)
    added = _persist(run, connections)
    return {
        "run_id": run,
        "candidate_chains": bundle["candidate_count"],
        "ambiguous_legs": bundle["ambiguous_legs"],
        "quarantined": bundle["quarantined"],
        "connections": connections,
        "determinations_persisted": added,
        "board": store.list_determinations(run),
    }


def _confirmation_hash(payload: dict) -> str:
    return sha256(dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


def _leg_key(leg: dict) -> str:
    return f"{leg['flight_no']}|{leg['flight_date']}|{leg['origin']}|{leg['destination']}"


def _find_leg(bundle: dict, leg_key: str) -> dict | None:
    for chain in bundle["chains"]:
        for leg in chain["legs"]:
            if _leg_key(leg) == leg_key:
                return leg
    return None


def apply_confirmation(payload: dict | None = None) -> dict:
    payload = payload or {
        "run_id": run_id(DEMO_PAYLOAD),
        "kind": "fold",
        "leg_key": "BA185|2026-10-31|LHR|JFK",
        "fold": 1,
    }
    run = payload["run_id"]
    kind = payload["kind"]
    leg_key = payload["leg_key"]
    payload_hash = _confirmation_hash(payload)
    confirmation = {
        "confirmation_id": f"{run}|{kind}|{leg_key}|{payload_hash[:12]}",
        "run_id": run,
        "kind": kind,
        "leg_key": leg_key,
        "payload_hash": payload_hash,
    }
    created = store.record_confirmation(confirmation)
    if not created:
        # 同一条确认重跑：幂等返回当前台账，不新增判定。
        return {
            "run_id": run, "confirmation_created": False, "recomputed": False,
            "confirmations": store.list_confirmations(run), "board": store.list_determinations(run),
        }

    bundle = demo_bundle()
    if kind == "fold":
        _apply_fold(bundle, leg_key, int(payload["fold"]))
    elif kind == "late_arrival":
        _apply_late_arrival(bundle, leg_key, payload["arrival_utc"])
    else:
        raise ValueError("BAD_CONFIRMATION_KIND")

    connections = check_chains(bundle["chains"], DEFAULT_MAX_MINUTES)
    added = _persist(run, connections)
    return {
        "run_id": run,
        "confirmation_created": True,
        "recomputed": True,
        "superseded_note": "航司晚到确认到达，旧判定已失效并重算" if kind == "late_arrival" else None,
        "confirmations": store.list_confirmations(run),
        "connections": connections,
        "determinations_persisted": added,
        "board": store.list_determinations(run),
        "history": store.list_determinations(run, include_superseded=True),
    }


def _apply_fold(bundle: dict, leg_key: str, fold: int) -> None:
    # fold=0 取较早的 UTC 解释，fold=1 取较晚的解释；只保留航司确认的那一条候选链。
    for chain in bundle["chains"]:
        chain["legs"] = [leg for leg in chain["legs"] if not (_leg_key(leg) == leg_key and leg["arrival_fold"] == fold)]
    bundle["chains"] = [chain for chain in bundle["chains"] if chain["legs"]]
    bundle["candidate_count"] = len(bundle["chains"])


def _apply_late_arrival(bundle: dict, leg_key: str, arrival_utc: str) -> None:
    """晚到确认：用航司给的新到达 UTC 替换候选到达时刻，再在整条链上重算等待。"""
    new_arrival = parse_utc(arrival_utc)
    for chain in bundle["chains"]:
        for leg in chain["legs"]:
            if _leg_key(leg) == leg_key:
                departure = parse_utc(leg["departure_utc"])
                leg["arrival_utc"] = arrival_utc if arrival_utc.endswith("Z") else arrival_utc.replace("+00:00", "Z")
                leg["duration_minutes"] = waiting_minutes(departure, new_arrival)
                leg["ambiguous"] = False
                leg["late_arrival_confirmed"] = True


def get_board(run: str | None = None) -> dict:
    run = run or run_id(DEMO_PAYLOAD)
    return {
        "run_id": run,
        "confirmations": store.list_confirmations(run),
        "board": store.list_determinations(run),
        "history": store.list_determinations(run, include_superseded=True),
    }


# ---------- 兼容旧接口的单连接演示（e2e 依赖 status=VALID） ----------

def run(payload: dict | None = None) -> dict:
    payload = payload or {"arrival_utc": "2026-11-16T10:00:00+00:00", "departure_utc": "2026-11-16T12:30:00+00:00", "airport": "JFK", "arrival_terminal": "T4", "departure_terminal": "T1"}
    wait = waiting_minutes(parse_utc(payload["arrival_utc"]), parse_utc(payload["departure_utc"]))
    required = required_minutes(payload["airport"], payload["arrival_terminal"], payload["departure_terminal"])
    return connection_result(wait, required, DEFAULT_MAX_MINUTES)


def demo() -> dict:
    return run()
