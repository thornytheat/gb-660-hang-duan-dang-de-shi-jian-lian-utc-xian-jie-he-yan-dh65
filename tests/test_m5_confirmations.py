"""航司确认台账：fold 确认、晚到失效重算、同确认幂等。"""
import pytest

import app.store as store
from app.manifest import run_id
from app.modules.m5_connections import service
from app.modules.m5_connections.service import DEMO_PAYLOAD


@pytest.fixture()
def isolated_db(tmp_path, monkeypatch):
    path = tmp_path / "board.sqlite3"
    monkeypatch.setattr(store, "DATABASE_PATH", path)
    store.init_db()
    yield path


@pytest.fixture()
def demo_run(isolated_db):
    result = service.check_demo()
    return result["run_id"]


def test_initial_check_persists_determinations(demo_run):
    board = store.list_determinations(demo_run)
    assert {item["status"] for item in board} == {"VALID", "PENDING_CONFIRMATION"}
    assert all(item["superseded"] == 0 for item in board)


def test_fold_confirmation_resolves_pending_connection(demo_run):
    payload = {"run_id": demo_run, "kind": "fold", "leg_key": "BA185|2026-10-31|LHR|JFK", "fold": 1}
    result = service.apply_confirmation(payload)
    assert result["confirmation_created"] and result["recomputed"]
    jfk = next(item for item in result["board"] if item["connection_key"] == "BA185->BA178@JFK")
    assert jfk["decision"] == "DETERMINED" and jfk["status"] == "VALID" and jfk["wait_minutes"] == 120


def test_earlier_fold_keeps_too_short_verdict(demo_run):
    payload = {"run_id": demo_run, "kind": "fold", "leg_key": "BA185|2026-10-31|LHR|JFK", "fold": 0}
    result = service.apply_confirmation(payload)
    jfk = next(item for item in result["board"] if item["connection_key"] == "BA185->BA178@JFK")
    assert jfk["status"] == "TOO_SHORT" and jfk["wait_minutes"] == 60


def test_same_confirmation_rerun_is_idempotent(demo_run):
    payload = {"run_id": demo_run, "kind": "fold", "leg_key": "BA185|2026-10-31|LHR|JFK", "fold": 1}
    first = service.apply_confirmation(payload)
    second = service.apply_confirmation(payload)
    assert first["confirmation_created"] and not second["confirmation_created"]
    assert second["recomputed"] is False
    assert len(store.list_confirmations(demo_run)) == 1


def test_late_arrival_supersedes_old_determination_and_recomputes(isolated_db):
    run = service.check_demo()["run_id"]
    # 先给一个 fold 判定，再用晚到确认覆盖。
    service.apply_confirmation({"run_id": run, "kind": "fold", "leg_key": "BA185|2026-10-31|LHR|JFK", "fold": 1})
    late = {"run_id": run, "kind": "late_arrival", "leg_key": "BA185|2026-10-31|LHR|JFK", "arrival_utc": "2026-11-01T07:00:00Z"}
    result = service.apply_confirmation(late)
    assert result["recomputed"] and result["superseded_note"]
    jfk = next(item for item in result["board"] if item["connection_key"] == "BA185->BA178@JFK")
    assert jfk["wait_minutes"] == 30 and jfk["status"] == "TOO_SHORT"
    history = result["history"]
    assert any(item["superseded"] == 1 for item in history)
    assert all(item["superseded"] == 0 for item in result["board"])


def test_late_arrival_rerun_does_not_add_determination(isolated_db):
    run = service.check_demo()["run_id"]
    late = {"run_id": run, "kind": "late_arrival", "leg_key": "BA185|2026-10-31|LHR|JFK", "arrival_utc": "2026-11-01T07:00:00Z"}
    first = service.apply_confirmation(late)
    before = len(store.list_determinations(run, include_superseded=True))
    second = service.apply_confirmation(late)
    after = len(store.list_determinations(run, include_superseded=True))
    assert first["confirmation_created"] and not second["confirmation_created"]
    assert before == after


def test_board_exposes_pending_vs_determined(demo_run):
    board = service.get_board(demo_run)
    assert {item["decision"] for item in board["board"]} == {"DETERMINED", "PENDING_CONFIRMATION"}


def test_run_id_stable_for_same_demo_payload():
    assert run_id(DEMO_PAYLOAD) == run_id(DEMO_PAYLOAD)
