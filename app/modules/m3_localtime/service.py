from .resolve import classify_local, resolve_local
from .evidence import offset_evidence


def run(payload: dict | None = None) -> dict:
    payload = payload or {"local": "2026-11-16T09:00", "timezone": "Asia/Shanghai", "fold": None}
    resolved = resolve_local(payload["local"], payload["timezone"], payload.get("fold"))
    return offset_evidence(resolved)


def review(payload: dict | None = None) -> dict:
    """把当地时刻的全部 UTC 候选摆到台面上：唯一才直接判定，重叠则挂起等确认。"""
    payload = payload or {"local": "2026-11-01T01:30", "timezone": "America/New_York", "fold": None}
    classified = classify_local(payload["local"], payload["timezone"], payload.get("fold"))
    candidates = [offset_evidence(item) for item in classified["candidates"]]
    response = {
        "local": payload["local"],
        "timezone": payload["timezone"],
        "state": classified["state"],
        "candidate_count": len(candidates),
        "candidates": candidates,
        "selected": offset_evidence(classified["selected"]) if classified["selected"] else None,
        "pending_confirmation": classified["state"] == "AMBIGUOUS",
    }
    if classified["selected"] is not None:
        response.update(offset_evidence(classified["selected"]))
    return response


def demo() -> dict:
    return run()
