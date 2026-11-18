"""把当地时刻候选传播成完整 UTC 航链。

关键约束：夏令时回拨产生的每个当地时刻候选都必须沿用到整条航链，
衔接判定只能在具体的 UTC 候选链上计算等待时间，不能混用候选。
"""
from itertools import product
from datetime import timezone

from app.modules.m2_airports.registry import airport_version
from app.modules.m3_localtime.resolve import classify_local, utc_iso

MAX_FLIGHT_MINUTES = 18 * 60


def _local_date(local_value: str) -> str:
    return local_value[:10]


def leg_candidates(row: dict) -> tuple[list[dict], dict | None]:
    """展开单航段的全部 UTC 候选。

    返回 (候选列表, 隔离证据)。起飞或到达任一时刻落在 DST gap、
    引用未知机场、或没有任何候选组合满足时长约束时隔离该航段。
    """
    origin = row["origin"].strip().upper()
    destination = row["destination"].strip().upper()
    try:
        dep_version = airport_version(origin, _local_date(row["departure_local"]))
        arr_version = airport_version(destination, _local_date(row["arrival_local"]))
    except ValueError as exc:
        return [], {"line_no": row.get("line_no"), "reason_code": "UNKNOWN_REFERENCE", "raw": dict(row), "detail": str(exc)}

    dep = classify_local(row["departure_local"], dep_version["timezone"], _optional_fold(row.get("departure_fold")))
    arr = classify_local(row["arrival_local"], arr_version["timezone"], _optional_fold(row.get("arrival_fold")))
    if dep["state"] == "NONEXISTENT" or arr["state"] == "NONEXISTENT":
        return [], {"line_no": row.get("line_no"), "reason_code": "NONEXISTENT_LOCAL_TIME", "raw": dict(row)}

    ambiguous = dep["state"] in ("AMBIGUOUS", "RESOLVED") or arr["state"] in ("AMBIGUOUS", "RESOLVED")
    options: list[dict] = []
    for dep_aware, arr_aware in product(dep["candidates"], arr["candidates"]):
        dep_utc = dep_aware.astimezone(timezone.utc)
        arr_utc = arr_aware.astimezone(timezone.utc)
        minutes = int((arr_utc - dep_utc).total_seconds() // 60)
        if minutes <= 0 or minutes > MAX_FLIGHT_MINUTES:
            continue
        options.append(
            {
                "flight_no": row["flight_no"].strip().upper(),
                "flight_date": row["flight_date"],
                "origin": origin,
                "destination": destination,
                "origin_terminal": dep_version["terminal"],
                "destination_terminal": arr_version["terminal"],
                "departure_local": row["departure_local"],
                "arrival_local": row["arrival_local"],
                "departure_fold": dep_aware.fold,
                "arrival_fold": arr_aware.fold,
                "departure_utc": utc_iso(dep_utc),
                "arrival_utc": utc_iso(arr_utc),
                "duration_minutes": minutes,
                "ambiguous": ambiguous,
            }
        )
    if not options:
        return [], {"line_no": row.get("line_no"), "reason_code": "INVALID_FLIGHT_DURATION", "raw": dict(row)}
    return options, None


def _optional_fold(value) -> int | None:
    if value is None or str(value).strip() == "":
        return None
    return int(value)


def _chain_key(chain: list[dict]) -> tuple:
    return (chain[0]["departure_utc"], chain[0]["flight_no"])


def build_chains(rows: list[dict]) -> dict:
    """笛卡尔展开全部候选航链，并按 UTC 起飞时刻稳定排序（TRAP-13）。"""
    accepted: list[list[dict]] = []
    quarantined: list[dict] = []
    ambiguous_legs: list[str] = []
    for index, row in enumerate(rows):
        options, evidence = leg_candidates(row)
        if evidence is not None:
            quarantined.append(evidence)
            continue
        if any(option["ambiguous"] for option in options):
            ambiguous_legs.append(options[0]["flight_no"])
        accepted.append(options)

    chains = []
    if accepted:
        for combination in product(*accepted):
            chain = sorted(combination, key=lambda leg: (leg["departure_utc"], leg["flight_no"]))
            chains.append(
                {
                    "chain_id": "|".join(f"{leg['flight_no']}@{leg['departure_fold']}-{leg['arrival_fold']}" for leg in chain),
                    "legs": chain,
                    "chain_valid": _continuous(chain),
                    "ambiguous": any(leg["ambiguous"] for leg in chain),
                }
            )
        chains.sort(key=lambda item: _chain_key(item["legs"]))
    return {
        "input": len(rows),
        "accepted": len(accepted),
        "quarantined": quarantined,
        "candidate_count": len(chains),
        "ambiguous_legs": ambiguous_legs,
        "chains": chains,
    }


def _continuous(chain: list[dict]) -> bool:
    for index, leg in enumerate(chain):
        if index and chain[index - 1]["destination"] != leg["origin"]:
            return False
    return True
