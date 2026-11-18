"""M3 候选审查：重叠挂起、gap 隔离、fold 确认后落定。"""
import pytest

from app.modules.m3_localtime.resolve import classify_local
from app.modules.m3_localtime.service import review


def test_classify_unique_local_time():
    result = classify_local("2026-11-16T09:00", "Asia/Shanghai")
    assert result["state"] == "UNIQUE" and len(result["candidates"]) == 1
    assert result["selected"] is not None


def test_classify_overlap_is_pending_until_fold():
    result = classify_local("2026-11-01T01:30", "America/New_York")
    assert result["state"] == "AMBIGUOUS" and len(result["candidates"]) == 2
    assert result["selected"] is None


def test_classify_gap_is_nonexistent():
    result = classify_local("2026-03-08T02:30", "America/New_York")
    assert result["state"] == "NONEXISTENT" and result["candidates"] == []


def test_review_marks_pending_confirmation():
    result = review({"local": "2026-11-01T01:30", "timezone": "America/New_York", "fold": None})
    assert result["pending_confirmation"] is True
    assert result["candidate_count"] == 2
    assert {item["fold"] for item in result["candidates"]} == {0, 1}


def test_review_with_fold_selects_one_utc():
    result = review({"local": "2026-11-01T01:30", "timezone": "America/New_York", "fold": 1})
    assert result["state"] == "RESOLVED" and result["selected"]["fold"] == 1
    assert result["utc"].endswith("Z") and not result["pending_confirmation"]
