from datetime import datetime, timezone
from zoneinfo import ZoneInfo

def local_candidates(local_value: str, zone_name: str) -> list[datetime]:
    naive = datetime.fromisoformat(local_value)
    zone = ZoneInfo(zone_name)
    result = []
    for fold in (0, 1):
        aware = naive.replace(tzinfo=zone, fold=fold)
        roundtrip = aware.astimezone(timezone.utc).astimezone(zone).replace(tzinfo=None)
        if roundtrip == naive and all(existing.utcoffset() != aware.utcoffset() for existing in result):
            result.append(aware)
    return result

def resolve_local(local_value: str, zone_name: str, fold: int | None = None) -> datetime:
    candidates = local_candidates(local_value, zone_name)
    if not candidates:
        raise ValueError("NONEXISTENT_LOCAL_TIME")
    if len(candidates) > 1 and fold is None:
        raise ValueError("AMBIGUOUS_LOCAL_TIME")
    if fold is None:
        return candidates[0]
    selected = [item for item in candidates if item.fold == fold]
    if not selected:
        raise ValueError("BAD_FOLD")
    return selected[0]

def classify_local(local_value: str, zone_name: str, fold: int | None = None) -> dict:
    """返回当地时刻的全部 UTC 候选，而不是替业务静默选一个解释。

    state 取值：
    - UNIQUE：唯一解释，可直接出确定结论；
    - AMBIGUOUS：夏令时回拨重叠，两个候选都成立，必须等航司确认 fold；
    - NONEXISTENT：夏令时跳时（gap），该墙上时间不存在，记录隔离。
    """
    candidates = local_candidates(local_value, zone_name)
    if not candidates:
        return {"state": "NONEXISTENT", "candidates": [], "selected": None}
    if len(candidates) == 1:
        return {"state": "UNIQUE", "candidates": candidates, "selected": candidates[0]}
    if fold is None:
        return {"state": "AMBIGUOUS", "candidates": candidates, "selected": None}
    selected = [item for item in candidates if item.fold == fold]
    if not selected:
        return {"state": "AMBIGUOUS", "candidates": candidates, "selected": None}
    return {"state": "RESOLVED", "candidates": candidates, "selected": selected[0]}

def utc_iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")

