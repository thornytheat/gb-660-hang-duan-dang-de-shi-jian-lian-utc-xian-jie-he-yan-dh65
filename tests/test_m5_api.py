"""衔接页面与确认接口的 HTTP 级测试。"""
import pytest
from fastapi.testclient import TestClient

from app.main import app
import app.store as store


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DATABASE_PATH", tmp_path / "api.sqlite3")
    store.init_db()
    return TestClient(app)


def test_connection_page_distinguishes_pending_and_determined(client):
    response = client.get("/connections")
    assert response.status_code == 200
    assert "待确认" in response.text and "已判定" in response.text
    assert "badge--pending" in response.text and "badge--ok" in response.text


def test_check_chain_endpoint_returns_board(client):
    response = client.post("/api/connections/check-chain", json={})
    assert response.status_code == 200
    data = response.json()
    assert data["candidate_chains"] == 2 and data["determinations_persisted"] == 2
    decisions = {item["decision"] for item in data["board"]}
    assert decisions == {"DETERMINED", "PENDING_CONFIRMATION"}


def test_confirm_endpoint_fold_flow(client):
    run_id = client.post("/api/connections/check-chain", json={}).json()["run_id"]
    response = client.post("/api/connections/confirm", json={
        "run_id": run_id, "kind": "fold",
        "leg_key": "BA185|2026-10-31|LHR|JFK", "fold": 1,
    })
    data = response.json()
    assert data["confirmation_created"] and data["recomputed"]
    jfk = next(item for item in data["board"] if item["connection_key"] == "BA185->BA178@JFK")
    assert jfk["status"] == "VALID" and jfk["decision"] == "DETERMINED"


def test_board_endpoint_lists_history(client):
    run_id = client.post("/api/connections/check-chain", json={}).json()["run_id"]
    client.post("/api/connections/confirm", json={
        "run_id": run_id, "kind": "late_arrival",
        "leg_key": "BA185|2026-10-31|LHR|JFK", "arrival_utc": "2026-11-01T07:00:00Z",
    })
    data = client.get(f"/api/connections/board?run_id={run_id}").json()
    assert data["confirmations"] and data["board"]
    assert any(item["superseded"] == 1 for item in data["history"])


def test_local_time_review_endpoint(client):
    data = client.post("/api/local-time/review", json={
        "local": "2026-11-01T01:30", "timezone": "America/New_York",
    }).json()
    assert data["state"] == "AMBIGUOUS" and data["pending_confirmation"]


def test_itinerary_chains_endpoint(client):
    data = client.post("/api/itineraries/chains", json={}).json()
    assert data["candidate_count"] == 2 and data["ambiguous_legs"] == ["BA185"]


def test_legacy_check_endpoint_still_valid(client):
    data = client.post("/api/connections/check").json()
    assert data["status"] == "VALID" and data["wait_minutes"] == 150
